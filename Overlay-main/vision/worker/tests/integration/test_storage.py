"""Integration tests for storage service with MinIO."""

import os
import tempfile
from pathlib import Path

import pytest

from clients.storage import S3StorageClient


@pytest.fixture(scope="module")
def storage_config():
    """
    Storage configuration for MinIO integration tests.

    Assumes MinIO is running locally on port 9000.
    Credentials from docker-compose.yml: minio/minio123
    """
    return {
        "bucket_name": "odin-test",
        "endpoint_url": "http://localhost:9000",
        "access_key": "minio",
        "secret_key": "minio123",
        "region": "us-east-1",
    }


@pytest.fixture(scope="module")
def storage_client(storage_config):
    """Create S3 storage client for MinIO."""
    client = S3StorageClient(**storage_config)

    # Ensure bucket exists
    try:
        client.client.create_bucket(Bucket=storage_config["bucket_name"])
    except client.client.exceptions.BucketAlreadyOwnedByYou:
        pass  # Bucket already exists
    except Exception as e:
        pytest.skip(f"MinIO not available: {e}")

    # Cleanup: delete all test files BEFORE running tests
    try:
        bucket = storage_config["bucket_name"]
        response = client.client.list_objects_v2(Bucket=bucket)
        if "Contents" in response:
            for obj in response["Contents"]:
                client.client.delete_object(Bucket=bucket, Key=obj["Key"])
    except Exception:
        pass  # Best effort cleanup

    yield client

    # Keep objects after tests for inspection (no teardown cleanup)


@pytest.fixture
def sample_pdf_path():
    """Path to the 5-page sample PDF."""
    return Path(__file__).parent.parent / "assets" / "pdfs" / "pdf_sample_5_pages.pdf"


class TestStorageIntegration:
    """Integration tests for storage operations with MinIO."""

    def test_upload_file(self, storage_client, sample_pdf_path):
        """Test uploading a PDF file to MinIO."""
        # Arrange
        remote_path = "test-uploads/sample.pdf"

        # Act
        uri = storage_client.upload_file(
            local_path=str(sample_pdf_path), remote_path=remote_path, content_type="application/pdf"
        )

        # Assert
        assert uri == f"s3://{storage_client.bucket_name}/{remote_path}"
        assert storage_client.file_exists(remote_path)

    def test_file_exists(self, storage_client, sample_pdf_path):
        """Test checking if a file exists in MinIO."""
        # Arrange
        remote_path = "test-uploads/exists-check.pdf"
        storage_client.upload_file(local_path=str(sample_pdf_path), remote_path=remote_path)

        # Act & Assert
        assert storage_client.file_exists(remote_path) is True
        assert storage_client.file_exists("nonexistent/file.pdf") is False

    def test_download_file(self, storage_client, sample_pdf_path):
        """Test downloading a file from MinIO."""
        # Arrange
        remote_path = "test-uploads/download-test.pdf"
        storage_client.upload_file(local_path=str(sample_pdf_path), remote_path=remote_path)

        # Act
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "downloaded.pdf")
            result_path = storage_client.download_file(remote_path, download_path)

            # Assert
            assert result_path == download_path
            assert os.path.exists(download_path)

            # Verify file integrity by comparing sizes
            original_size = os.path.getsize(sample_pdf_path)
            downloaded_size = os.path.getsize(download_path)
            assert downloaded_size == original_size

    def test_upload_and_download_round_trip(self, storage_client, sample_pdf_path):
        """Test complete upload/download cycle with file integrity check."""
        # Arrange
        remote_path = "test-uploads/round-trip.pdf"

        # Act - Upload
        storage_client.upload_file(
            local_path=str(sample_pdf_path), remote_path=remote_path, content_type="application/pdf"
        )

        # Act - Download
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "round-trip.pdf")
            storage_client.download_file(remote_path, download_path)

            # Assert - Verify integrity
            with open(sample_pdf_path, "rb") as original:
                with open(download_path, "rb") as downloaded:
                    original_content = original.read()
                    downloaded_content = downloaded.read()
                    assert original_content == downloaded_content
                    assert len(original_content) > 0  # Sanity check

    def test_download_nonexistent_file(self, storage_client):
        """Test downloading a file that doesn't exist."""
        # Arrange
        remote_path = "nonexistent/file.pdf"

        # Act & Assert
        with tempfile.TemporaryDirectory() as tmpdir:
            download_path = os.path.join(tmpdir, "should-not-exist.pdf")
            with pytest.raises(FileNotFoundError, match="Remote file not found"):
                storage_client.download_file(remote_path, download_path)

    def test_upload_nonexistent_file(self, storage_client):
        """Test uploading a file that doesn't exist locally."""
        # Arrange
        local_path = "/nonexistent/local/file.pdf"
        remote_path = "test-uploads/should-fail.pdf"

        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Local file not found"):
            storage_client.upload_file(local_path, remote_path)

    def test_upload_with_nested_path(self, storage_client, sample_pdf_path):
        """Test uploading to a nested directory structure."""
        # Arrange
        remote_path = "test-uploads/deeply/nested/path/sample.pdf"

        # Act
        uri = storage_client.upload_file(
            local_path=str(sample_pdf_path), remote_path=remote_path, content_type="application/pdf"
        )

        # Assert
        assert uri == f"s3://{storage_client.bucket_name}/{remote_path}"
        assert storage_client.file_exists(remote_path)
