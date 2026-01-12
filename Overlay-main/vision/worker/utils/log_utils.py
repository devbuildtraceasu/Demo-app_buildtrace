"""Logging utilities for vision worker.

Provides consistent, readable logging with bracket notation and context indentation.
Format: [event.name] context | human message
"""

import contextlib
import json
import logging
import os
import re
import sys
import time
import warnings
from collections.abc import Generator
from contextvars import ContextVar

from PIL import Image

# Try to import psutil for memory tracking, but make it optional
try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

TRACE_CONTEXT = ContextVar("trace_context", default=None)

CLOUD_TRACE_CONTEXT_RE = re.compile(r"^([a-fA-F0-9]{32})(?:/([0-9]+))?(?:;o=([01]))?$")
TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")


class TraceLoggingFilter(logging.Filter):
    """Inject trace context into log records when available."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = TRACE_CONTEXT.get()
        if context:
            record.trace = context.get("trace")
            record.trace_sampled = context.get("trace_sampled")
        return True


class GCPJsonFormatter(logging.Formatter):
    """Format logs as JSON with severity field for GCP Cloud Logging."""

    LEVEL_TO_SEVERITY = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "WARNING",
        logging.ERROR: "ERROR",
        logging.CRITICAL: "CRITICAL",
    }

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "severity": self.LEVEL_TO_SEVERITY.get(record.levelno, "INFO"),
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": self.formatTime(record, self.datefmt),
        }
        if getattr(record, "trace", None):
            log_entry["logging.googleapis.com/trace"] = record.trace
        if getattr(record, "trace_sampled", None) is not None:
            log_entry["logging.googleapis.com/trace_sampled"] = record.trace_sampled
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


class LocalDevFormatter(logging.Formatter):
    """Human-readable format for local development."""

    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.LEVEL_COLORS.get(record.levelno, "")
        level = record.levelname[:4]
        timestamp = self.formatTime(record, "%H:%M:%S")
        message = record.getMessage()

        formatted = f"{color}{timestamp} {level}{self.RESET} {message}"

        if record.exc_info:
            formatted += f"\n{self.formatException(record.exc_info)}"

        return formatted


def _is_local_dev() -> bool:
    """Check if running in local development environment."""
    return os.environ.get("PUBSUB_EMULATOR_HOST") is not None


def parse_log_level(level_str: str) -> int:
    """Convert string log level to logging constant.

    Args:
        level_str: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        logging level constant (defaults to INFO for invalid input)
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_str.upper(), logging.INFO)


def configure_logging(level: str | int = logging.INFO) -> None:
    """
    Configure logging with appropriate format for the environment.

    - Local dev (PUBSUB_EMULATOR_HOST set): Human-readable colored output
    - Production: GCP-compatible JSON format

    Also configures PIL to handle large construction drawings:
    - Raises decompression bomb limit to 250M pixels
    - Suppresses DecompressionBombWarning

    Args:
        level: Logging level as string ("DEBUG", "INFO", etc.) or int constant
    """
    if isinstance(level, str):
        level = parse_log_level(level)

    handler = logging.StreamHandler(sys.stdout)

    if _is_local_dev():
        handler.setFormatter(LocalDevFormatter())
    else:
        handler.setFormatter(GCPJsonFormatter())
        handler.addFilter(TraceLoggingFilter())

    logging.basicConfig(level=level, handlers=[handler])

    # Suppress noisy library logs (even at DEBUG level)
    for noisy_logger in [
        "google_genai",
        "google.genai",
        "google.cloud.pubsub_v1",
        "google.cloud.pubsub_v1.subscriber",
        "google.cloud.pubsub_v1.subscriber._protocol",
        "google.cloud.pubsub_v1.subscriber._protocol.streaming_pull_manager",
        "google.cloud.pubsub_v1.publisher",
        "google.api_core",
        "google.api_core.bidi",
        "httpx",
        "httpcore",
        "PIL",
        "PIL.PngImagePlugin",
        "urllib3",
        "google.auth",
        "botocore",
        "boto3",
        "s3transfer",
        "grpc",
        "grpc._channel",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Raise PIL decompression bomb limit for large construction drawings
    Image.MAX_IMAGE_PIXELS = 250_000_000  # 250 million pixels (~16,000 x 16,000)
    warnings.filterwarnings("ignore", category=Image.DecompressionBombWarning)


def set_trace_context(trace_context: dict | None) -> None:
    """Store trace context for the current worker thread."""
    TRACE_CONTEXT.set(trace_context)


def clear_trace_context() -> None:
    """Clear trace context for the current worker thread."""
    TRACE_CONTEXT.set(None)


def extract_trace_context(attributes: dict | None, project_id: str) -> dict | None:
    """Extract trace context from Pub/Sub attributes."""
    if not attributes:
        return None

    cloud_header = attributes.get("x-cloud-trace-context")
    traceparent = attributes.get("traceparent")

    trace_id = None
    span_id_dec = None
    span_id_hex = None
    sampled = False

    if cloud_header:
        parsed = _parse_cloud_trace_context(cloud_header)
        if parsed:
            trace_id, span_id_dec, sampled = parsed
            if span_id_dec:
                span_id_hex = _span_id_dec_to_hex(span_id_dec)

    if not trace_id and traceparent:
        parsed = _parse_traceparent(traceparent)
        if parsed:
            trace_id, span_id_hex, sampled = parsed
            if span_id_hex:
                span_id_dec = _span_id_hex_to_dec(span_id_hex)

    if not trace_id:
        return None

    if not span_id_dec or not span_id_hex:
        span_id_hex = _generate_span_id_hex()
        span_id_dec = _span_id_hex_to_dec(span_id_hex)

    cloud_trace_context = f"{trace_id}/{span_id_dec};o={1 if sampled else 0}"
    traceparent_value = f"00-{trace_id}-{span_id_hex}-{'01' if sampled else '00'}"

    return {
        "trace": f"projects/{project_id}/traces/{trace_id}",
        "trace_id": trace_id,
        "trace_sampled": sampled,
        "cloud_trace_context": cloud_trace_context,
        "traceparent": traceparent_value,
    }


def get_trace_attributes() -> dict[str, str]:
    """Return trace propagation attributes for Pub/Sub publishes."""
    context = TRACE_CONTEXT.get()
    if not context:
        return {}
    attributes: dict[str, str] = {}
    cloud_trace_context = context.get("cloud_trace_context")
    if cloud_trace_context:
        attributes["x-cloud-trace-context"] = cloud_trace_context
    traceparent = context.get("traceparent")
    if traceparent:
        attributes["traceparent"] = traceparent
    return attributes


def _parse_cloud_trace_context(
    header: str,
) -> tuple[str, str | None, bool] | None:
    match = CLOUD_TRACE_CONTEXT_RE.match(header.strip())
    if not match:
        return None
    trace_id, span_id, sampled = match.groups()
    return trace_id.lower(), span_id, sampled == "1"


def _parse_traceparent(header: str) -> tuple[str, str, bool] | None:
    match = TRACEPARENT_RE.match(header.strip().lower())
    if not match:
        return None
    trace_id, span_id_hex, flags = match.groups()
    sampled = int(flags, 16) % 2 == 1
    return trace_id.lower(), span_id_hex, sampled


def _span_id_dec_to_hex(span_id_dec: str) -> str | None:
    try:
        return f"{int(span_id_dec):016x}"
    except (ValueError, TypeError):
        return None


def _span_id_hex_to_dec(span_id_hex: str) -> str | None:
    try:
        return str(int(span_id_hex, 16))
    except (ValueError, TypeError):
        return None


def _generate_span_id_hex() -> str:
    return os.urandom(8).hex()


def format_size(size_bytes: int) -> str:
    """Format byte size as human-readable string.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted string (e.g., "1.2mb", "500kb", "50b")
    """
    if size_bytes >= 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f}mb"
    elif size_bytes >= 1024:
        return f"{size_bytes / 1024:.1f}kb"
    else:
        return f"{size_bytes}b"


def format_duration(duration_ms: int) -> str:
    """Format duration as human-readable string.

    Args:
        duration_ms: Duration in milliseconds

    Returns:
        Formatted string (e.g., "15.2s", "250ms")
    """
    if duration_ms >= 1000:
        return f"{duration_ms / 1000:.1f}s"
    else:
        return f"{duration_ms}ms"


def format_context(
    drawing_id: str | None = None,
    sheet_id: str | None = None,
    block_id: str | None = None,
    overlay_id: str | None = None,
    job_id: str | None = None,
) -> str:
    """Format hierarchical context IDs.

    Args:
        drawing_id: Drawing UUID (string or UUID object)
        sheet_id: Sheet UUID (string or UUID object)
        block_id: Block UUID (string or UUID object)
        overlay_id: Overlay UUID (string or UUID object)
        job_id: Job UUID (string or UUID object)

    Returns:
        Formatted string (e.g., "draw-123 > sheet-456 > block-789 > ovl-abc > job-def")
    """
    parts = []

    if drawing_id:
        drawing_str = str(drawing_id)
        short_id = drawing_str[:8] if len(drawing_str) > 8 else drawing_str
        parts.append(f"draw-{short_id}")

    if sheet_id:
        sheet_str = str(sheet_id)
        short_id = sheet_str[:8] if len(sheet_str) > 8 else sheet_str
        parts.append(f"sheet-{short_id}")

    if block_id:
        block_str = str(block_id)
        short_id = block_str[:8] if len(block_str) > 8 else block_str
        parts.append(f"block-{short_id}")

    if overlay_id:
        overlay_str = str(overlay_id)
        short_id = overlay_str[:8] if len(overlay_str) > 8 else overlay_str
        parts.append(f"ovl-{short_id}")

    if job_id:
        job_str = str(job_id)
        short_id = job_str[:8] if len(job_str) > 8 else job_str
        parts.append(f"job-{short_id}")

    return " > ".join(parts)


def format_compact_context(
    job_id: str | None = None,
) -> str:
    """Format compact context for single-line logs.

    Args:
        job_id: Job UUID (string or UUID object)

    Returns:
        Formatted string (e.g., "job-123")
    """
    parts = []

    if job_id:
        job_str = str(job_id)
        short_id = job_str[:8] if len(job_str) > 8 else job_str
        parts.append(f"job-{short_id}")

    return "/".join(parts)


def get_memory_mb() -> float | None:
    """Get current process memory usage in MB.

    Returns:
        Memory usage in MB, or None if psutil not available
    """
    if not PSUTIL_AVAILABLE:
        return None

    try:
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except Exception:
        return None


@contextlib.contextmanager
def log_phase(
    logger: logging.Logger,
    phase_name: str,
    **context_kwargs,
) -> Generator[None, None, None]:
    """Context manager for logging phase timing at DEBUG level.

    Logs processing phases with timing for performance profiling.

    Usage:
        with log_phase(logger, "Downloading PDF from storage", drawing_id=drawing_id):
            pdf_bytes = download_pdf(...)

    Output at DEBUG level:
        Downloading PDF from storage... (draw-12345678)
        Downloading PDF from storage done (2.3s)

    Args:
        logger: Logger instance
        phase_name: Descriptive name of the phase (e.g., "Downloading PDF from storage")
        **context_kwargs: Context IDs (drawing_id, sheet_id, block_id, etc.)
    """
    context = format_context(**context_kwargs)
    context_str = f" ({context})" if context else ""

    logger.debug(f"{phase_name}...{context_str}")
    start_time = time.time()

    try:
        yield
    finally:
        duration_ms = int((time.time() - start_time) * 1000)
        duration_str = format_duration(duration_ms)
        logger.debug(f"{phase_name} done ({duration_str})")


def log_job_received(
    logger: logging.Logger,
    job_type: str,
    message_id: str,
    drawing_id: str | None = None,
    sheet_id: str | None = None,
    block_id: str | None = None,
    overlay_id: str | None = None,
    job_id: str | None = None,
) -> None:
    """Log job received from queue.

    Args:
        logger: Logger instance
        job_type: Type of job (conversion, extraction)
        message_id: Pub/Sub message ID
        drawing_id: Drawing UUID
        sheet_id: Sheet UUID
        block_id: Block UUID
        overlay_id: Overlay UUID
        job_id: Job UUID
    """
    short_msg_id = message_id[:8] if len(message_id) > 8 else message_id
    context = format_context(
        drawing_id=drawing_id,
        sheet_id=sheet_id,
        block_id=block_id,
        overlay_id=overlay_id,
        job_id=job_id,
    )
    context_str = f" | {context}" if context else ""
    logger.info(f"[job.received] {job_type} msg-{short_msg_id}{context_str}")


def log_job_started(
    logger: logging.Logger,
    job_type: str,
    message_id: str,
    drawing_id: str | None = None,
    sheet_id: str | None = None,
    block_id: str | None = None,
    overlay_id: str | None = None,
    job_id: str | None = None,
) -> float:
    """Log job started and return start time.

    Args:
        logger: Logger instance
        job_type: Type of job (conversion, extraction)
        message_id: Pub/Sub message ID
        drawing_id: Drawing UUID
        sheet_id: Sheet UUID
        block_id: Block UUID
        overlay_id: Overlay UUID
        job_id: Job UUID

    Returns:
        Start time (from time.time()) for duration calculation
    """
    short_msg_id = message_id[:8] if len(message_id) > 8 else message_id
    context = format_context(
        drawing_id=drawing_id,
        sheet_id=sheet_id,
        block_id=block_id,
        overlay_id=overlay_id,
        job_id=job_id,
    )
    context_str = f" | {context}" if context else ""
    logger.info(f"[job.started] {job_type} msg-{short_msg_id}{context_str}")

    return time.time()


def log_job_completed(
    logger: logging.Logger,
    job_type: str,
    message_id: str,
    start_time: float,
    drawing_id: str | None = None,
    sheet_id: str | None = None,
    block_id: str | None = None,
    overlay_id: str | None = None,
    job_id: str | None = None,
    **metrics,
) -> None:
    """Log job completed with metrics.

    Args:
        logger: Logger instance
        job_type: Type of job (conversion, extraction)
        message_id: Pub/Sub message ID
        start_time: Start time from log_job_started()
        drawing_id: Drawing UUID
        sheet_id: Sheet UUID
        block_id: Block UUID
        overlay_id: Overlay UUID
        job_id: Job UUID
        **metrics: Additional metrics to log (pages_total, identifier, etc.)
    """
    duration_ms = int((time.time() - start_time) * 1000)
    short_msg_id = message_id[:8] if len(message_id) > 8 else message_id

    context = format_context(
        drawing_id=drawing_id,
        sheet_id=sheet_id,
        block_id=block_id,
        overlay_id=overlay_id,
        job_id=job_id,
    )

    # Format metrics
    metric_parts = []

    # Handle page metrics
    if "pages_total" in metrics:
        total = metrics["pages_total"]
        new = metrics.get("pages_new", 0)
        existing = metrics.get("pages_existing", 0)
        metric_parts.append(f"{total} pages (+{new} new, ~{existing} existing)")

    # Handle identifier
    if "identifier" in metrics:
        identifier = metrics["identifier"]
        if identifier:
            metric_parts.append(f'identifier: "{identifier}"')
        else:
            metric_parts.append("identifier: none")

    # Handle page index
    if "page_index" in metrics:
        metric_parts.append(f"index {metrics['page_index']}")

    # Add timing and memory
    duration_str = format_duration(duration_ms)
    memory_mb = get_memory_mb()

    if memory_mb is not None:
        metric_parts.append(f"{duration_str}, {memory_mb:.0f}mb")
    else:
        metric_parts.append(duration_str)

    # Build single line output
    parts = [f"[job.completed] {job_type} msg-{short_msg_id}"]
    if context:
        parts.append(f"| {context}")
    if metric_parts:
        parts.append(f"| {' | '.join(metric_parts)}")

    logger.info(" ".join(parts))


def log_status_updated(
    logger: logging.Logger,
    resource_type: str,
    resource_id: str,
    old_status: str | None = None,
    new_status: str | None = None,
) -> None:
    """Log status update.

    Args:
        logger: Logger instance
        resource_type: Type of resource (overlay, drawing, sheet, block, job)
        resource_id: Resource UUID (string or UUID object)
        old_status: Previous status
        new_status: New status
    """
    resource_str = str(resource_id)
    short_id = resource_str[:8] if len(resource_str) > 8 else resource_str

    if old_status and new_status:
        logger.info(f"[status.updated] {resource_type} {short_id}: {old_status} → {new_status}")
    elif new_status:
        logger.info(f"[status.updated] {resource_type} {short_id} → {new_status}")
    else:
        logger.info(f"[status.updated] {resource_type} {short_id}")


def log_storage_download(
    logger: logging.Logger,
    path: str,
    size_bytes: int | None = None,
    duration_ms: int | None = None,
    drawing_id: str | None = None,
    sheet_id: str | None = None,
    block_id: str | None = None,
    overlay_id: str | None = None,
    job_id: str | None = None,
) -> None:
    """Log storage download operation.

    Args:
        logger: Logger instance
        path: Storage path
        size_bytes: File size in bytes
        duration_ms: Download duration in milliseconds
        drawing_id: Drawing UUID
        sheet_id: Sheet UUID
        block_id: Block UUID
        overlay_id: Overlay UUID
        job_id: Job UUID
    """
    # Extract just the filename for readability
    filename = path.split("/")[-1] if "/" in path else path

    details = []
    if size_bytes is not None:
        details.append(format_size(size_bytes))
    if duration_ms is not None:
        details.append(format_duration(duration_ms))

    context = format_context(
        drawing_id=drawing_id,
        sheet_id=sheet_id,
        block_id=block_id,
        overlay_id=overlay_id,
        job_id=job_id,
    )

    parts = [f"[storage.download] {filename}"]
    if details:
        parts.append(f"({', '.join(details)})")
    if context:
        parts.append(f"| {context}")

    logger.info(" ".join(parts))


def log_storage_upload(
    logger: logging.Logger,
    path: str,
    size_bytes: int | None = None,
    duration_ms: int | None = None,
) -> None:
    """Log storage upload operation.

    Args:
        logger: Logger instance
        path: Storage path
        size_bytes: File size in bytes
        duration_ms: Upload duration in milliseconds
    """
    filename = path.split("/")[-1] if "/" in path else path

    details = []
    if size_bytes is not None:
        details.append(format_size(size_bytes))
    if duration_ms is not None:
        details.append(format_duration(duration_ms))

    detail_str = f" ({', '.join(details)})" if details else ""

    logger.debug(f"[storage.upload] {filename}{detail_str}")


def log_pdf_converted(
    logger: logging.Logger,
    page_count: int,
    duration_ms: int,
    drawing_id: str | None = None,
    sheet_id: str | None = None,
    block_id: str | None = None,
    overlay_id: str | None = None,
    job_id: str | None = None,
) -> None:
    """Log PDF conversion completion.

    Args:
        logger: Logger instance
        page_count: Number of pages converted
        duration_ms: Conversion duration in milliseconds
        drawing_id: Drawing UUID
        sheet_id: Sheet UUID
        block_id: Block UUID
        overlay_id: Overlay UUID
        job_id: Job UUID
    """
    duration_str = format_duration(duration_ms)
    memory_mb = get_memory_mb()

    context = format_context(
        drawing_id=drawing_id,
        sheet_id=sheet_id,
        block_id=block_id,
        overlay_id=overlay_id,
        job_id=job_id,
    )

    if memory_mb is not None:
        msg = f"[pdf.converted] {page_count} pages → {page_count} pngs ({duration_str}, peak {memory_mb:.0f}mb)"
    else:
        msg = f"[pdf.converted] {page_count} pages → {page_count} pngs ({duration_str})"

    if context:
        msg += f" | {context}"

    logger.info(msg)


def log_coordination_published(
    logger: logging.Logger,
    target_topic: str,
    job_count: int,
    drawing_id: str | None = None,
    sheet_id: str | None = None,
    block_id: str | None = None,
    overlay_id: str | None = None,
    job_id: str | None = None,
) -> None:
    """Log coordination jobs published.

    Args:
        logger: Logger instance
        target_topic: Target Pub/Sub topic
        job_count: Number of jobs published
        drawing_id: Drawing UUID
        sheet_id: Sheet UUID
        block_id: Block UUID
        overlay_id: Overlay UUID
        job_id: Job UUID
    """
    context = format_context(
        drawing_id=drawing_id,
        sheet_id=sheet_id,
        block_id=block_id,
        overlay_id=overlay_id,
        job_id=job_id,
    )
    msg = f"[coordination.published] {target_topic} × {job_count} jobs"
    if context:
        msg += f" | {context}"
    logger.info(msg)


def log_coordination_ready(
    logger: logging.Logger,
    condition: str,
    result: bool,
) -> None:
    """Log coordination condition check.

    Args:
        logger: Logger instance
        condition: Condition being checked (e.g., "all sheets identified")
        result: Whether condition is met
    """
    status = "ready" if result else "waiting"
    logger.info(f"[coordination.{status}] {condition}")


def log_message_acked(
    logger: logging.Logger,
    message_id: str,
    job_type: str,
    reason: str | None = None,
) -> None:
    """Log message acknowledged.

    Args:
        logger: Logger instance
        message_id: Pub/Sub message ID
        job_type: Type of job (conversion, extraction)
        reason: Optional reason for acking
    """
    short_msg_id = message_id[:8] if len(message_id) > 8 else message_id

    if reason:
        logger.info(f"[message.acked] {job_type} msg-{short_msg_id} ({reason})")
    else:
        logger.info(f"[message.acked] {job_type} msg-{short_msg_id}")


def log_message_nacked(
    logger: logging.Logger,
    message_id: str,
    job_type: str,
    reason: str,
) -> None:
    """Log message nacked for retry.

    Args:
        logger: Logger instance
        message_id: Pub/Sub message ID
        job_type: Type of job (conversion, extraction)
        reason: Reason for nacking
    """
    short_msg_id = message_id[:8] if len(message_id) > 8 else message_id
    logger.info(f"[message.nacked] {job_type} msg-{short_msg_id} ({reason})")


def log_job_failed_permanent(
    logger: logging.Logger,
    job_type: str,
    message_id: str,
    error: Exception,
) -> None:
    """Log permanent job failure.

    Args:
        logger: Logger instance
        job_type: Type of job (conversion, extraction)
        message_id: Pub/Sub message ID
        error: Exception that caused failure
    """
    short_msg_id = message_id[:8] if len(message_id) > 8 else message_id
    error_type = type(error).__name__

    logger.error(f"[job.failed.permanent] {job_type} msg-{short_msg_id}")
    logger.error(f"  → {error_type}: {str(error)}")
    logger.error("  → acking to remove from queue")


def log_job_failed_transient(
    logger: logging.Logger,
    job_type: str,
    message_id: str,
    error: Exception,
) -> None:
    """Log transient job failure.

    Args:
        logger: Logger instance
        job_type: Type of job (conversion, extraction)
        message_id: Pub/Sub message ID
        error: Exception that caused failure
    """
    short_msg_id = message_id[:8] if len(message_id) > 8 else message_id
    error_type = type(error).__name__

    logger.error(f"[job.failed.transient] {job_type} msg-{short_msg_id}")
    logger.error(f"  → {error_type}: {str(error)}")
    logger.error("  → nacking for retry")


def log_ocr_completed(
    logger: logging.Logger,
    method: str,
    char_count: int,
    sheet_id: str | None = None,
    sheet_index: int | None = None,
) -> None:
    """Log OCR completion.

    Args:
        logger: Logger instance
        method: OCR method used (pymupdf, vision_api)
        char_count: Number of characters extracted
        sheet_id: Sheet UUID (string or UUID object)
        sheet_index: Sheet index
    """
    parts = []
    if sheet_id:
        sheet_str = str(sheet_id)
        short_id = sheet_str[:8] if len(sheet_str) > 8 else sheet_str
        parts.append(f"sheet-{short_id}")
    if sheet_index is not None:
        parts.append(f"index {sheet_index}")

    msg = f"[ocr.completed] {method} → {char_count:,} chars"
    if parts:
        msg += f" | {' '.join(parts)}"
    logger.info(msg)


def log_identifier_extracted(
    logger: logging.Logger,
    identifier: str | None,
    sheet_id: str | None = None,
    sheet_index: int | None = None,
) -> None:
    """Log identifier extraction.

    Args:
        logger: Logger instance
        identifier: Extracted identifier or None
        sheet_id: Sheet UUID (string or UUID object)
        sheet_index: Sheet index
    """
    parts = []
    if sheet_id:
        sheet_str = str(sheet_id)
        short_id = sheet_str[:8] if len(sheet_str) > 8 else sheet_str
        parts.append(f"sheet-{short_id}")
    if sheet_index is not None:
        parts.append(f"index {sheet_index}")

    if identifier:
        msg = f'[identifier.extracted] "{identifier}"'
    else:
        msg = "[identifier.extracted] none"

    if parts:
        msg += f" | {' '.join(parts)}"
    logger.info(msg)


def log_worker_starting(logger: logging.Logger, version: str | None = None) -> None:
    """Log worker startup.

    Args:
        logger: Logger instance
        version: Optional version string
    """
    if version:
        logger.info(f"[worker.starting] vision-worker v{version}")
    else:
        logger.info("[worker.starting] vision-worker")


def log_worker_config(
    logger: logging.Logger,
    db_host: str,
    db_port: int,
    db_name: str,
    storage_backend: str,
    storage_bucket: str,
    pubsub_project: str,
    topics: list[str],
    subscriptions: list[str],
    max_concurrent: int,
    max_memory_bytes: int,
    max_lease_seconds: int,
) -> None:
    """Log worker configuration.

    Args:
        logger: Logger instance
        db_host: Database host
        db_port: Database port
        db_name: Database name
        storage_backend: Storage backend type
        storage_bucket: Storage bucket name
        pubsub_project: Pub/Sub project ID
        topics: List of topic names
        subscriptions: List of subscription names
        max_concurrent: Max concurrent messages
        max_memory_bytes: Max memory in bytes
        max_lease_seconds: Max lease duration in seconds
    """
    logger.info("[worker.config]")
    logger.info(f"  → db: {db_host}:{db_port}/{db_name}")
    logger.info(f"  → storage: {storage_backend}/{storage_bucket}")
    logger.info(f"  → pubsub: {pubsub_project} (topics: {','.join(topics)})")
    logger.info(
        f"  → limits: {max_concurrent} concurrent, {max_memory_bytes // (1024 * 1024)}mb max"
    )
    logger.info(f"  → lease: {max_lease_seconds}s max")


def log_connection_established(
    logger: logging.Logger,
    service: str,
    details: str | None = None,
) -> None:
    """Log successful connection.

    Args:
        logger: Logger instance
        service: Service name (db, pubsub, storage)
        details: Optional connection details
    """
    if details:
        logger.info(f"[{service}.connected] {details}")
    else:
        logger.info(f"[{service}.connected]")


def log_worker_ready(logger: logging.Logger) -> None:
    """Log worker ready state.

    Args:
        logger: Logger instance
    """
    logger.info("[worker.ready] all connections established")


def log_overlay_generated(
    logger: logging.Logger,
    overlay_id: str,
    quality_score: float | None = None,
    inlier_count: int | None = None,
    total_matches: int | None = None,
    duration_ms: int | None = None,
) -> None:
    """Log overlay generation completion.

    Args:
        logger: Logger instance
        overlay_id: Overlay UUID
        quality_score: Alignment quality score (inlier ratio, 0.0 to 1.0)
        inlier_count: Number of RANSAC inliers
        total_matches: Total feature matches before RANSAC
        duration_ms: Processing duration in milliseconds
    """
    overlay_str = str(overlay_id)
    short_id = overlay_str[:8] if len(overlay_str) > 8 else overlay_str

    details = []

    if quality_score is not None:
        details.append(f"quality: {quality_score:.3f}")

    if inlier_count is not None and total_matches is not None:
        details.append(f"inliers: {inlier_count}/{total_matches}")

    if duration_ms is not None:
        duration_str = format_duration(duration_ms)
        details.append(duration_str)

    msg = f"[overlay.generated] ovl-{short_id}"
    if details:
        msg += f" | {' | '.join(details)}"
    logger.info(msg)


def log_worker_shutdown(logger: logging.Logger) -> None:
    """Log worker shutdown.

    Args:
        logger: Logger instance
    """
    logger.info("[worker.shutdown] graceful shutdown initiated")
