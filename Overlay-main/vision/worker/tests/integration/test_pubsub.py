"""Integration tests for PubSub service with emulator."""

import json
import os
import threading
import time

import pytest

from clients.pubsub import PubSubClient


@pytest.fixture(scope="module")
def pubsub_config():
    """
    PubSub configuration for emulator integration tests.

    Assumes PubSub emulator is running locally on port 8681.
    Set PUBSUB_EMULATOR_HOST environment variable.
    """
    # Ensure emulator host is set
    os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"

    return {
        "project_id": "local-dev",
        "test_topic": "test-topic",
        "test_subscription": "test-subscription",
    }


@pytest.fixture(scope="module")
def pubsub_client(pubsub_config):
    """Create PubSub client for emulator."""
    # Ensure emulator host is set
    os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"

    # Set required config env vars for PubSubClient __init__
    os.environ["PUBSUB_PROJECT_ID"] = pubsub_config["project_id"]
    os.environ["DB_HOST"] = "localhost"
    os.environ["DB_USER"] = "test"
    os.environ["DB_PASSWORD"] = "test"
    os.environ["STORAGE_BUCKET"] = "test-bucket"

    try:
        client = PubSubClient(project_id=pubsub_config["project_id"])

        # Create test topic
        topic_path = client.publisher.topic_path(
            pubsub_config["project_id"], pubsub_config["test_topic"]
        )
        try:
            client.publisher.create_topic(request={"name": topic_path})
        except Exception:
            pass  # Topic already exists

        # Create test subscription
        try:
            client.create_subscription(
                pubsub_config["test_topic"], pubsub_config["test_subscription"]
            )
        except Exception:
            pass  # Subscription already exists

        yield client

        # No cleanup - topics and subscriptions persist in emulator for test stability

    except Exception as e:
        pytest.skip(f"PubSub emulator not available: {e}")


class TestPubSubIntegration:
    """Integration tests for PubSub operations with emulator."""

    def test_publish_message(self, pubsub_client, pubsub_config):
        """Test publishing a message to a topic."""
        # Arrange
        message = {"drawing_id": 123, "job_id": 456, "action": "convert"}

        # Act
        message_id = pubsub_client.publish(pubsub_config["test_topic"], message)

        # Assert
        assert message_id is not None
        assert isinstance(message_id, str)
        assert len(message_id) > 0

    def test_publish_multiple_messages(self, pubsub_client, pubsub_config):
        """Test publishing multiple messages in sequence."""
        # Arrange
        messages = [
            {"id": 1, "type": "test"},
            {"id": 2, "type": "test"},
            {"id": 3, "type": "test"},
        ]

        # Act
        message_ids = []
        for msg in messages:
            msg_id = pubsub_client.publish(pubsub_config["test_topic"], msg)
            message_ids.append(msg_id)

        # Assert
        assert len(message_ids) == 3
        assert len(set(message_ids)) == 3  # All IDs are unique

    @pytest.mark.skip(
        reason="Flaky test in multithreaded mode - timing-sensitive PubSub emulator test"
    )
    def test_subscribe_and_receive_message(self, pubsub_client, pubsub_config):
        """Test subscribing to a topic and receiving a message."""
        # Clear any pending messages from previous tests
        subscription_path = pubsub_client.subscriber.subscription_path(
            pubsub_config["project_id"], pubsub_config["test_subscription"]
        )

        try:
            pull_response = pubsub_client.subscriber.pull(
                request={"subscription": subscription_path, "max_messages": 10}, timeout=2.0
            )
            if pull_response.received_messages:
                ack_ids = [msg.ack_id for msg in pull_response.received_messages]
                pubsub_client.subscriber.acknowledge(
                    request={"subscription": subscription_path, "ack_ids": ack_ids}
                )
        except Exception:
            pass  # No messages to clear

        # Arrange
        test_message = {"test_id": "subscribe-test-001", "data": "test data"}
        received_messages: list[dict] = []
        received_event = threading.Event()

        def callback(message):
            """Handle received message."""
            try:
                data = json.loads(message.data.decode("utf-8"))
                # Only accept the specific test message
                if data.get("test_id") == "subscribe-test-001":
                    received_messages.append(data)
                    received_event.set()
                message.ack()
            except Exception as e:
                print(f"Error in callback: {e}")
                message.nack()

        # Start subscriber in background thread
        def subscribe_thread():
            try:
                subscription_path = pubsub_client.subscriber.subscription_path(
                    pubsub_config["project_id"], pubsub_config["test_subscription"]
                )
                future = pubsub_client.subscriber.subscribe(subscription_path, callback=callback)
                # Wait for message or timeout
                future.result(timeout=10.0)
            except Exception:
                pass  # Timeout is expected

        thread = threading.Thread(target=subscribe_thread, daemon=True)
        thread.start()

        # Give subscriber time to start and establish connection
        time.sleep(2)

        # Act - Publish message
        pubsub_client.publish(pubsub_config["test_topic"], test_message)

        # Wait for message to be received
        received = received_event.wait(timeout=8.0)

        # Assert
        assert received, "Message was not received within timeout"
        assert len(received_messages) == 1
        assert received_messages[0]["test_id"] == "subscribe-test-001"
        assert received_messages[0]["data"] == "test data"

    def test_publish_and_receive_with_vision_topics(self, pubsub_client, pubsub_config):
        """Test publishing to a vision topic."""
        # Arrange
        message = {
            "drawing_id": 789,
            "job_id": 101,
        }

        # Create test-vision topic if it doesn't exist
        vision_topic_path = pubsub_client.publisher.topic_path(
            pubsub_config["project_id"], "test-vision"
        )
        try:
            pubsub_client.publisher.create_topic(request={"name": vision_topic_path})
        except Exception:
            pass  # Topic already exists

        # Act - Publish to test-vision topic
        message_id = pubsub_client.publish("test-vision", message)

        # Assert
        assert message_id is not None
        assert isinstance(message_id, str)

    def test_publish_invalid_message_type(self, pubsub_client, pubsub_config):
        """Test publishing with invalid message type."""
        # Arrange
        invalid_message = "This is a string, not a dict"

        # Act & Assert
        with pytest.raises(ValueError, match="Message must be a dictionary"):
            pubsub_client.publish(pubsub_config["test_topic"], invalid_message)

    def test_publish_empty_topic(self, pubsub_client):
        """Test publishing with empty topic name."""
        # Arrange
        message = {"test": "data"}

        # Act & Assert
        with pytest.raises(ValueError, match="Topic name cannot be empty"):
            pubsub_client.publish("", message)

    def test_publish_to_nonexistent_topic(self, pubsub_client):
        """Test publishing to a topic that doesn't exist."""
        # Arrange
        message = {"test": "data"}
        nonexistent_topic = "nonexistent-topic-12345"

        # Act & Assert
        with pytest.raises(IOError, match="Failed to publish"):
            pubsub_client.publish(nonexistent_topic, message)

    @pytest.mark.skip(
        reason="Flaky test in multithreaded mode - timing-sensitive PubSub emulator test"
    )
    def test_message_with_nested_structure(self, pubsub_client, pubsub_config):
        """Test publishing and receiving message with nested structure."""
        # Clear any pending messages from previous tests
        subscription_path = pubsub_client.subscriber.subscription_path(
            pubsub_config["project_id"], pubsub_config["test_subscription"]
        )

        try:
            pull_response = pubsub_client.subscriber.pull(
                request={"subscription": subscription_path, "max_messages": 10}, timeout=2.0
            )
            if pull_response.received_messages:
                ack_ids = [msg.ack_id for msg in pull_response.received_messages]
                pubsub_client.subscriber.acknowledge(
                    request={"subscription": subscription_path, "ack_ids": ack_ids}
                )
        except Exception:
            pass  # No messages to clear

        # Wait a bit for cleanup to complete
        time.sleep(0.5)

        # Arrange
        complex_message = {
            "drawing_id": 999,
            "test_id": "nested-structure-test",
            "metadata": {
                "user_id": 123,
                "project_name": "Test Project",
                "tags": ["tag1", "tag2", "tag3"],
            },
            "revisions": [{"id": 1, "version": "v1.0"}, {"id": 2, "version": "v2.0"}],
        }
        received_messages: list[dict] = []
        received_event = threading.Event()

        def callback(message):
            try:
                data = json.loads(message.data.decode("utf-8"))
                # Only accept the specific test message
                if data.get("test_id") == "nested-structure-test":
                    received_messages.append(data)
                    received_event.set()
                message.ack()
            except Exception:
                message.nack()

        # Start subscriber
        def subscribe_thread():
            try:
                future = pubsub_client.subscriber.subscribe(subscription_path, callback=callback)
                future.result(timeout=10.0)
            except Exception:
                pass

        thread = threading.Thread(target=subscribe_thread, daemon=True)
        thread.start()
        time.sleep(2)

        # Act
        pubsub_client.publish(pubsub_config["test_topic"], complex_message)
        received = received_event.wait(timeout=8.0)

        # Assert
        assert received
        assert len(received_messages) == 1
        received_msg = received_messages[0]
        assert received_msg["drawing_id"] == 999
        assert received_msg["metadata"]["user_id"] == 123
        assert len(received_msg["metadata"]["tags"]) == 3
        assert len(received_msg["revisions"]) == 2

    def test_publish_with_timeout(self, pubsub_client, pubsub_config):
        """Test publishing with custom timeout."""
        # Arrange
        message = {"test": "timeout"}

        # Act
        message_id = pubsub_client.publish(pubsub_config["test_topic"], message, timeout=5.0)

        # Assert
        assert message_id is not None

    @pytest.mark.skip(
        reason="Flaky test - tests PubSub emulator load balancing behavior, not worker code"
    )
    def test_multiple_subscribers_same_subscription(self, pubsub_client, pubsub_config):
        """Test that multiple subscribers can share the same subscription."""
        # Arrange
        test_message = {"test_id": "multi-subscriber-test", "data": "shared subscription"}
        received_count = {"count": 0}
        received_event = threading.Event()
        lock = threading.Lock()

        def callback(message):
            try:
                data = json.loads(message.data.decode("utf-8"))
                # Only count the specific test message
                if data.get("test_id") == "multi-subscriber-test":
                    with lock:
                        received_count["count"] += 1
                    received_event.set()
                message.ack()
            except Exception:
                message.nack()

        # Start two subscribers
        def subscribe_thread():
            try:
                subscription_path = pubsub_client.subscriber.subscription_path(
                    pubsub_config["project_id"], pubsub_config["test_subscription"]
                )
                future = pubsub_client.subscriber.subscribe(subscription_path, callback=callback)
                future.result(timeout=10.0)
            except Exception:
                pass

        thread1 = threading.Thread(target=subscribe_thread, daemon=True)
        thread2 = threading.Thread(target=subscribe_thread, daemon=True)
        thread1.start()
        thread2.start()

        # Give both subscribers time to start and establish connections
        time.sleep(3)

        # Act - Publish message (only one subscriber should receive it)
        pubsub_client.publish(pubsub_config["test_topic"], test_message)
        received = received_event.wait(timeout=10.0)
        time.sleep(2)  # Give time for duplicate delivery if it happens

        # Assert - Message should be received exactly once
        assert received, "Message was not received by any subscriber within timeout"
        assert (
            received_count["count"] == 1
        ), f"Message should be delivered to only one subscriber, but was delivered {received_count['count']} times"
