"""Vision worker entrypoint - handles drawing and sheet jobs."""

import inspect
import json
import logging
import os
import signal
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from google.cloud.pubsub_v1.types import FlowControl
from sqlmodel import select

from clients.db import close_engine, get_engine, get_session
from clients.pubsub import get_pubsub_client
from config import config
from models import Drawing, Sheet
from utils.job_errors import is_permanent_job_error
from utils.log_utils import (
    clear_trace_context,
    configure_logging,
    extract_trace_context,
    log_connection_established,
    log_job_failed_permanent,
    log_job_failed_transient,
    log_message_acked,
    log_message_nacked,
    log_worker_config,
    log_worker_ready,
    log_worker_shutdown,
    log_worker_starting,
    set_trace_context,
)

# Configure logging and PIL settings
configure_logging(config.worker_log_level)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False
worker_healthy = False  # Set to True once worker is ready


class HealthCheckHandler(BaseHTTPRequestHandler):
    """Simple HTTP handler for Cloud Run health checks."""
    
    def do_GET(self):
        """Handle GET requests for health checks."""
        if self.path == "/health" or self.path == "/":
            if worker_healthy:
                self.send_response(200)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(503)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not Ready")
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging to avoid noise."""
        pass


def start_health_server():
    """Start HTTP server for Cloud Run health checks."""
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    logger.info(f"[health.server] listening on port {port}")
    server.serve_forever()


def signal_handler(signum, frame):
    """Handle shutdown signals (SIGINT, SIGTERM)."""
    global shutdown_flag
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    shutdown_flag = True


def validate_database_connectivity() -> bool:
    """
    Validate database connectivity by querying required tables.

    Returns:
        bool: True if database is accessible and tables exist

    Raises:
        Exception: If database connection fails
    """
    import os
    
    try:
        # If using Cloud SQL Unix socket, verify the socket path exists
        if config.db_host and config.db_host.startswith("/cloudsql/"):
            socket_path = config.db_host
            if not os.path.exists(socket_path):
                logger.warning(f"[db.socket.missing] Unix socket path does not exist: {socket_path}")
                logger.warning("[db.socket.missing] This might indicate Cloud SQL proxy is not running")
                logger.warning("[db.socket.missing] Waiting 5 seconds for Cloud SQL proxy to initialize...")
                import time
                time.sleep(5)
                if not os.path.exists(socket_path):
                    raise ConnectionError(
                        f"Cloud SQL Unix socket not found at {socket_path}. "
                        "Ensure Cloud SQL proxy is running and the volume is mounted correctly."
                    )
            else:
                logger.info(f"[db.socket.found] Unix socket exists: {socket_path}")
        
        get_engine()  # Verify engine can be created

        # Try to connect and query tables
        with get_session() as session:
            # Check drawings table (avoid legacy columns)
            statement = select(Drawing).limit(1)
            session.exec(statement).first()

            # Check sheets table (avoid legacy columns)
            statement = select(Sheet).limit(1)
            session.exec(statement).first()

        return True

    except Exception as e:
        logger.error(f"[db.connection.failed] {type(e).__name__}: {e}")
        raise


def validate_pubsub_connectivity(pubsub_client) -> bool:
    """
    Validate Pub/Sub connectivity by confirming access to required queues.

    Args:
        pubsub_client: PubSubClient instance

    Returns:
        bool: True if Pub/Sub is accessible

    Raises:
        Exception: If Pub/Sub connection fails
    """
    try:
        topics = [config.vision_topic]
        subscriptions = [config.vision_subscription]

        for topic in topics:
            pubsub_client.publisher.topic_path(config.pubsub_project_id, topic)

        for subscription in subscriptions:
            pubsub_client.subscriber.subscription_path(config.pubsub_project_id, subscription)

        return True

    except Exception as e:
        logger.error(f"[pubsub.connection.failed] {type(e).__name__}: {e}")
        raise


def connect_with_retry(connection_func, max_retries: int = 3, base_delay: float = 1.0) -> bool:
    """
    Attempt connection with exponential backoff retry logic.

    Args:
        connection_func: Function to call for connection attempt
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        bool: True if connection succeeded

    Raises:
        Exception: If all retries fail
    """
    for attempt in range(max_retries):
        try:
            connection_func()
            return True
        except Exception:
            if attempt == max_retries - 1:
                logger.error(f"[connection.failed] max attempts ({max_retries}) reached")
                raise

            delay = base_delay * (2**attempt)
            logger.warning(
                f"[connection.retry] attempt {attempt + 1}/{max_retries} (retry in {delay:.1f}s)"
            )
            time.sleep(delay)

    return False


def main():
    """Main worker entrypoint."""
    global shutdown_flag, worker_healthy

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    log_worker_starting(logger)

    # Start health check server in background thread (for Cloud Run)
    health_thread = threading.Thread(
        target=start_health_server,
        name="HealthServer",
        daemon=True,
    )
    health_thread.start()

    try:
        topics = [config.vision_topic]
        subscriptions = [config.vision_subscription]

        log_worker_config(
            logger,
            db_host=config.db_host,
            db_port=config.db_port,
            db_name=config.db_name,
            storage_backend=config.storage_backend,
            storage_bucket=config.storage_bucket,
            pubsub_project=config.pubsub_project_id,
            topics=topics,
            subscriptions=subscriptions,
            max_concurrent=config.worker_max_concurrent_messages,
            max_memory_bytes=config.worker_max_memory_bytes,
            max_lease_seconds=config.worker_max_lease_duration_seconds,
        )

        flow_control_kwargs = {
            "max_messages": config.worker_max_concurrent_messages,
            "max_bytes": config.worker_max_memory_bytes,
        }
        try:
            flow_control_params = set(inspect.signature(FlowControl).parameters)
        except (TypeError, ValueError):
            flow_control_params = set()
        if "max_lease_duration" in flow_control_params:
            flow_control_kwargs["max_lease_duration"] = config.worker_max_lease_duration_seconds

        # Configure flow control to allow long-running jobs without redelivery.
        flow_control = FlowControl(**flow_control_kwargs)

        # Connect to database with retry
        connect_with_retry(
            validate_database_connectivity,
            max_retries=config.worker_max_retries,
        )
        log_connection_established(
            logger, "db", f"{config.db_host}:{config.db_port}/{config.db_name}"
        )

        # Connect to Pub/Sub with retry
        pubsub_client = get_pubsub_client()
        connect_with_retry(
            lambda: validate_pubsub_connectivity(pubsub_client),
            max_retries=config.worker_max_retries,
        )
        log_connection_established(
            logger,
            "pubsub",
            f"{config.pubsub_project_id}/{config.vision_subscription}",
        )

        log_worker_ready(logger)
        worker_healthy = True  # Mark as healthy for Cloud Run health checks

        from jobs.runner import JobRunner

        job_runner = JobRunner(logger=logger)

        def handle_job_message(message):
            """Handle incoming job messages."""
            trace_context = extract_trace_context(message.attributes, config.pubsub_project_id)
            set_trace_context(trace_context)
            job_type = None
            if message.attributes:
                job_type = message.attributes.get("type") or message.attributes.get("job_type")
            job_label = job_type or "job"
            try:
                data = json.loads(message.data.decode("utf-8"))
                job_runner.run_message(
                    data,
                    message_id=message.message_id,
                    job_type_hint=job_type,
                )

                log_message_acked(logger, message.message_id, job_label)
                message.ack()

            except Exception as e:
                if is_permanent_job_error(e):
                    log_job_failed_permanent(logger, job_label, message.message_id, e)
                    log_message_acked(
                        logger,
                        message.message_id,
                        job_label,
                        reason="permanent_failure",
                    )
                    message.ack()
                else:
                    log_job_failed_transient(logger, job_label, message.message_id, e)
                    log_message_nacked(
                        logger,
                        message.message_id,
                        job_label,
                        reason="transient_error",
                    )
                    message.nack()
            finally:
                clear_trace_context()

        def subscribe_to_job_queue():
            """Subscribe to job queue (blocking)."""
            try:
                logger.info("Starting subscription to job queue...")
                pubsub_client.subscribe(
                    config.vision_subscription,
                    callback=handle_job_message,
                    flow_control=flow_control,
                )
            except Exception as e:
                logger.error(f"Job subscription error: {e}", exc_info=True)
                raise

        # Run subscription in a separate thread so it can block safely.
        job_thread = threading.Thread(
            target=subscribe_to_job_queue,
            name="JobSubscriber",
            daemon=True,
        )

        # Start subscription thread
        job_thread.start()

        logger.info("Worker is now listening for jobs...")

        # Keep main thread alive while subscriptions run in background
        try:
            while not shutdown_flag:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
            shutdown_flag = True

        # Wait for thread to finish (should exit when shutdown_flag is set)
        job_thread.join(timeout=5)

    except KeyboardInterrupt:
        logger.info("[worker.interrupted] keyboard interrupt received")
    except Exception as e:
        logger.error(f"[worker.fatal] {type(e).__name__}: {e}", exc_info=True)
        sys.exit(1)
    finally:
        log_worker_shutdown(logger)
        close_engine()
        logger.info("[db.closed] connection pool closed")
        logger.info("[worker.stopped]")


if __name__ == "__main__":
    main()
