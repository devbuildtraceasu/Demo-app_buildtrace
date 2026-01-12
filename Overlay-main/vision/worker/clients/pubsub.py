"""PubSub client for Google Cloud Pub/Sub messaging operations."""

import json
from collections.abc import Callable

from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.types import FlowControl

from config import config
from utils.log_utils import get_trace_attributes


class PubSubClient:
    """Client for Pub/Sub messaging operations."""

    def __init__(self, project_id: str | None = None):
        """
        Initialize PubSub client.

        Args:
            project_id: Google Cloud project ID (defaults to config value)

        Raises:
            ValueError: If project_id is empty
        """
        self.project_id = project_id or config.pubsub_project_id

        if not self.project_id:
            raise ValueError("Project ID is required")

        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()

    def publish(
        self,
        topic_name: str,
        message: dict,
        timeout: float = 30.0,
        attributes: dict | None = None,
    ) -> str:
        """
        Publish a message to a topic.

        Args:
            topic_name: Name of the topic (e.g., "vision")
            message: Message payload as dictionary (will be JSON-encoded)
            timeout: Maximum time to wait for publish confirmation (seconds)
            attributes: Optional Pub/Sub attributes (used for subscription filters)

        Returns:
            Message ID assigned by Pub/Sub

        Raises:
            ValueError: If topic_name is empty or message is invalid
            TimeoutError: If publish does not complete within timeout
            IOError: If topic does not exist or publish fails
        """
        if not topic_name:
            raise ValueError("Topic name cannot be empty")

        if not isinstance(message, dict):
            raise ValueError("Message must be a dictionary")

        topic_path = self.publisher.topic_path(self.project_id, topic_name)

        try:
            # Encode message as JSON bytes
            data = json.dumps(message).encode("utf-8")

            # Publish and wait for result
            trace_attributes = get_trace_attributes()
            merged_attributes = {
                **trace_attributes,
                **(attributes or {}),
            }
            cleaned_attributes = {
                str(key): str(value) for key, value in (merged_attributes or {}).items()
            }
            future = self.publisher.publish(topic_path, data, **cleaned_attributes)
            message_id = future.result(timeout=timeout)

            return message_id
        except TimeoutError as e:
            raise TimeoutError(f"Publish to {topic_name} timed out after {timeout}s") from e
        except Exception as e:
            raise OSError(f"Failed to publish to {topic_name}: {str(e)}") from e

    def subscribe(
        self,
        subscription_name: str,
        callback: Callable,
        flow_control: FlowControl | None = None,
    ) -> None:
        """
        Subscribe to messages from a subscription (blocking).

        Args:
            subscription_name: Name of the subscription (e.g., "vision.worker")
            callback: Function to call for each message: callback(message)
            flow_control: Flow control settings for message concurrency and memory limits.
                         If None, uses Google Cloud defaults (10 concurrent, 1000 max messages).

        Raises:
            ValueError: If subscription_name is empty
            IOError: If subscription does not exist

        Example:
            from google.cloud.pubsub_v1.types import FlowControl

            def handle_message(message):
                data = json.loads(message.data.decode("utf-8"))
                print(f"Received: {data}")
                message.ack()

            flow_control = FlowControl(
                max_messages=3,
                max_bytes=500 * 1024 * 1024,  # 500MB
            )

            client.subscribe("vision.worker", handle_message, flow_control)
        """
        if not subscription_name:
            raise ValueError("Subscription name cannot be empty")

        subscription_path = self.subscriber.subscription_path(self.project_id, subscription_name)

        try:
            # Start streaming pull (blocking)
            streaming_pull_future = self.subscriber.subscribe(
                subscription_path, callback=callback, flow_control=flow_control
            )

            # Block and listen for messages
            streaming_pull_future.result()
        except Exception as e:
            raise OSError(f"Failed to subscribe to {subscription_name}: {str(e)}") from e

    def create_subscription(self, topic_name: str, subscription_name: str) -> str:
        """
        Create a subscription for a topic.

        Args:
            topic_name: Topic to subscribe to
            subscription_name: Name for the new subscription

        Returns:
            Subscription path

        Raises:
            ValueError: If names are invalid
            IOError: If subscription already exists or topic does not exist
        """
        if not topic_name or not subscription_name:
            raise ValueError("Topic and subscription names are required")

        topic_path = self.publisher.topic_path(self.project_id, topic_name)
        subscription_path = self.subscriber.subscription_path(self.project_id, subscription_name)

        try:
            self.subscriber.create_subscription(
                request={"name": subscription_path, "topic": topic_path}
            )
            return subscription_path
        except Exception as e:
            raise OSError(f"Failed to create subscription {subscription_name}: {str(e)}") from e


# Module-level singleton instance
_pubsub_client = None


def get_pubsub_client() -> PubSubClient:
    """
    Get or create the singleton PubSub client instance.

    Returns:
        PubSubClient: Configured PubSub client (singleton)
    """
    global _pubsub_client

    if _pubsub_client is None:
        _pubsub_client = PubSubClient()

    return _pubsub_client


def close_pubsub_client():
    """Close and reset the PubSub client singleton."""
    global _pubsub_client
    # PubSub clients don't have explicit close methods, just reset reference
    _pubsub_client = None
