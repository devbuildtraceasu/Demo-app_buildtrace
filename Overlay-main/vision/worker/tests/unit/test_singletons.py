"""Unit tests for singleton client implementations."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Import worker modules
import clients.db as db
import clients.pubsub as pubsub
import clients.storage as storage


# Mock environment variables for tests
@pytest.fixture(autouse=True)
def mock_env():
    """Mock environment variables required for configuration."""
    env_vars = {
        "DB_HOST": "localhost",
        "DB_USER": "test_user",
        "DB_PASSWORD": "test_password",
        "GCS_BUCKET": "test-bucket",
        "PUBSUB_PROJECT_ID": "test-project",
    }
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture(autouse=True)
def mock_google_clients():
    """Mock Google Cloud clients to avoid requiring credentials."""
    with (
        patch("google.cloud.pubsub_v1.PublisherClient") as mock_publisher,
        patch("google.cloud.pubsub_v1.SubscriberClient") as mock_subscriber,
        patch("google.cloud.storage.Client") as mock_storage,
    ):
        # Configure mocks
        mock_publisher.return_value = MagicMock()
        mock_subscriber.return_value = MagicMock()
        mock_storage.return_value = MagicMock()

        yield {
            "publisher": mock_publisher,
            "subscriber": mock_subscriber,
            "storage": mock_storage,
        }


@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset all singletons before each test for isolation."""
    # Reset before test
    db.close_engine()
    pubsub.close_pubsub_client()
    storage.close_storage_client()

    yield

    # Reset after test
    db.close_engine()
    pubsub.close_pubsub_client()
    storage.close_storage_client()


class TestDatabaseEngineSingleton:
    """Tests for database engine singleton pattern."""

    def test_get_engine_returns_same_instance(self):
        """Should return the same engine instance on multiple calls."""
        engine1 = db.get_engine()
        engine2 = db.get_engine()
        engine3 = db.get_engine()

        assert engine1 is engine2
        assert engine2 is engine3

    def test_close_engine_resets_singleton(self):
        """Should reset singleton and return new instance after close."""
        engine1 = db.get_engine()
        db.close_engine()
        engine2 = db.get_engine()

        assert engine1 is not engine2


class TestPubSubClientSingleton:
    """Tests for PubSub client singleton pattern."""

    def test_get_pubsub_client_returns_same_instance(self):
        """Should return the same PubSub client instance on multiple calls."""
        client1 = pubsub.get_pubsub_client()
        client2 = pubsub.get_pubsub_client()
        client3 = pubsub.get_pubsub_client()

        assert client1 is client2
        assert client2 is client3

    def test_close_pubsub_client_resets_singleton(self):
        """Should reset singleton and return new instance after close."""
        client1 = pubsub.get_pubsub_client()
        pubsub.close_pubsub_client()
        client2 = pubsub.get_pubsub_client()

        assert client1 is not client2

    def test_singleton_has_publisher_and_subscriber(self):
        """Should have publisher and subscriber clients initialized."""
        client = pubsub.get_pubsub_client()

        assert hasattr(client, "publisher")
        assert hasattr(client, "subscriber")
        assert client.publisher is not None
        assert client.subscriber is not None


class TestStorageClientSingleton:
    """Tests for storage client singleton pattern."""

    def test_get_storage_client_returns_same_instance(self):
        """Should return the same storage client instance on multiple calls."""
        client1 = storage.get_storage_client()
        client2 = storage.get_storage_client()
        client3 = storage.get_storage_client()

        assert client1 is client2
        assert client2 is client3

    def test_close_storage_client_resets_singleton(self):
        """Should reset singleton and return new instance after close."""
        client1 = storage.get_storage_client()
        storage.close_storage_client()
        client2 = storage.get_storage_client()

        assert client1 is not client2

    def test_singleton_has_bucket_name(self):
        """Should have bucket_name initialized."""
        client = storage.get_storage_client()

        # All storage clients must have bucket_name
        assert hasattr(client, "bucket_name")
        assert client.bucket_name is not None

        # GCSStorageClient has 'bucket' attribute, S3StorageClient does not
        if hasattr(client, "bucket"):
            assert client.bucket is not None
