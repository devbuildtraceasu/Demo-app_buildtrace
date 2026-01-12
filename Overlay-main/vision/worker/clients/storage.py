"""Cloud storage client supporting both S3 (MinIO) and Google Cloud Storage."""

from io import BytesIO
from typing import Protocol

import boto3
from botocore.exceptions import ClientError
from google.cloud import storage

from config import config


class StorageClient(Protocol):
    """Protocol defining the storage client interface."""

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a file to cloud storage."""
        ...

    def download_file(self, remote_path: str, local_path: str) -> str:
        """Download a file from cloud storage."""
        ...

    def upload_from_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload bytes to cloud storage."""
        ...

    def download_to_bytes(self, remote_path: str) -> bytes:
        """Download a file from cloud storage to bytes."""
        ...

    def file_exists(self, remote_path: str) -> bool:
        """Check if a file exists in cloud storage."""
        ...


class S3StorageClient:
    """Client for S3-compatible storage (MinIO, AWS S3)."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
    ):
        """
        Initialize S3 storage client.

        Args:
            bucket_name: Name of the S3 bucket
            endpoint_url: S3 endpoint URL (e.g., http://localhost:9000 for MinIO)
            access_key: S3 access key ID
            secret_key: S3 secret access key
            region: AWS region (default: us-east-1)

        Raises:
            ValueError: If required parameters are missing
        """
        if not bucket_name:
            raise ValueError("Bucket name is required")
        if not endpoint_url:
            raise ValueError("Endpoint URL is required for S3 storage")
        if not access_key or not secret_key:
            raise ValueError("Access key and secret key are required for S3 storage")

        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url

        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload a file to S3 storage.

        Args:
            local_path: Path to local file
            remote_path: Destination path in bucket (e.g., "pdfs/drawing.pdf")
            content_type: MIME type (default: application/octet-stream)

        Returns:
            Full S3 URI (e.g., "s3://bucket/pdfs/drawing.pdf")

        Raises:
            FileNotFoundError: If local_path does not exist
            IOError: If upload fails (network error, permission denied)
            ValueError: If remote_path is invalid
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            self.client.upload_file(
                local_path,
                self.bucket_name,
                remote_path,
                ExtraArgs={"ContentType": content_type},
            )
            return f"s3://{self.bucket_name}/{remote_path}"
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Local file not found: {local_path}") from e
        except ClientError as e:
            raise OSError(f"Upload failed for {local_path}: {str(e)}") from e
        except Exception as e:
            raise OSError(f"Upload failed for {local_path}: {str(e)}") from e

    def download_file(self, remote_path: str, local_path: str) -> str:
        """
        Download a file from S3 storage.

        Args:
            remote_path: Source path in bucket (e.g., "pdfs/drawing.pdf")
            local_path: Destination path for downloaded file

        Returns:
            Path to downloaded file (same as local_path)

        Raises:
            FileNotFoundError: If remote file does not exist
            IOError: If download fails (network error, permission denied)
            ValueError: If local_path directory does not exist
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            # Check if file exists first
            if not self.file_exists(remote_path):
                raise FileNotFoundError(
                    f"Remote file not found: s3://{self.bucket_name}/{remote_path}"
                )

            self.client.download_file(self.bucket_name, remote_path, local_path)
            return local_path
        except FileNotFoundError:
            raise
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(
                    f"Remote file not found: s3://{self.bucket_name}/{remote_path}"
                ) from e
            raise OSError(f"Download failed for {remote_path}: {str(e)}") from e
        except Exception as e:
            raise OSError(f"Download failed for {remote_path}: {str(e)}") from e

    def upload_from_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload bytes to S3 storage.

        Args:
            data: Bytes to upload
            remote_path: Destination path in bucket (e.g., "pdfs/drawing.pdf")
            content_type: MIME type (default: application/octet-stream)

        Returns:
            Full S3 URI (e.g., "s3://bucket/pdfs/drawing.pdf")

        Raises:
            IOError: If upload fails (network error, permission denied)
            ValueError: If remote_path is invalid
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            file_obj = BytesIO(data)
            self.client.upload_fileobj(
                file_obj,
                self.bucket_name,
                remote_path,
                ExtraArgs={"ContentType": content_type},
            )
            return f"s3://{self.bucket_name}/{remote_path}"
        except ClientError as e:
            raise OSError(f"Upload failed for {remote_path}: {str(e)}") from e
        except Exception as e:
            raise OSError(f"Upload failed for {remote_path}: {str(e)}") from e

    def download_to_bytes(self, remote_path: str) -> bytes:
        """
        Download a file from S3 storage to bytes.

        Args:
            remote_path: Source path in bucket (e.g., "pdfs/drawing.pdf")

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If remote file does not exist
            IOError: If download fails (network error, permission denied)
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            # Check if file exists first
            if not self.file_exists(remote_path):
                raise FileNotFoundError(
                    f"Remote file not found: s3://{self.bucket_name}/{remote_path}"
                )

            file_obj = BytesIO()
            self.client.download_fileobj(self.bucket_name, remote_path, file_obj)
            return file_obj.getvalue()
        except FileNotFoundError:
            raise
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise FileNotFoundError(
                    f"Remote file not found: s3://{self.bucket_name}/{remote_path}"
                ) from e
            raise OSError(f"Download failed for {remote_path}: {str(e)}") from e
        except Exception as e:
            raise OSError(f"Download failed for {remote_path}: {str(e)}") from e

    def file_exists(self, remote_path: str) -> bool:
        """
        Check if a file exists in S3 storage.

        Args:
            remote_path: Path in bucket to check

        Returns:
            True if file exists, False otherwise

        Raises:
            IOError: If bucket is inaccessible
        """
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=remote_path)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise OSError(f"Failed to check file existence: {str(e)}") from e
        except Exception as e:
            raise OSError(f"Failed to check file existence: {str(e)}") from e


class GCSStorageClient:
    """Client for Google Cloud Storage."""

    def __init__(self, bucket_name: str):
        """
        Initialize GCS storage client.

        Args:
            bucket_name: Name of the GCS bucket

        Raises:
            ValueError: If bucket_name is empty
        """
        if not bucket_name:
            raise ValueError("Bucket name is required")

        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(self.bucket_name)

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload a file to GCS storage.

        Args:
            local_path: Path to local file
            remote_path: Destination path in bucket (e.g., "pdfs/drawing.pdf")
            content_type: MIME type (default: application/octet-stream)

        Returns:
            Full GCS URI (e.g., "gs://bucket/pdfs/drawing.pdf")

        Raises:
            FileNotFoundError: If local_path does not exist
            IOError: If upload fails (network error, permission denied)
            ValueError: If remote_path is invalid
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            blob = self.bucket.blob(remote_path)
            blob.upload_from_filename(local_path, content_type=content_type)
            return f"gs://{self.bucket_name}/{remote_path}"
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Local file not found: {local_path}") from e
        except Exception as e:
            raise OSError(f"Upload failed for {local_path}: {str(e)}") from e

    def download_file(self, remote_path: str, local_path: str) -> str:
        """
        Download a file from GCS storage.

        Args:
            remote_path: Source path in bucket (e.g., "pdfs/drawing.pdf")
            local_path: Destination path for downloaded file

        Returns:
            Path to downloaded file (same as local_path)

        Raises:
            FileNotFoundError: If remote file does not exist
            IOError: If download fails (network error, permission denied)
            ValueError: If local_path directory does not exist
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            blob = self.bucket.blob(remote_path)

            if not blob.exists():
                raise FileNotFoundError(
                    f"Remote file not found: gs://{self.bucket_name}/{remote_path}"
                )

            blob.download_to_filename(local_path)
            return local_path
        except FileNotFoundError:
            raise
        except Exception as e:
            raise OSError(f"Download failed for {remote_path}: {str(e)}") from e

    def upload_from_bytes(
        self,
        data: bytes,
        remote_path: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload bytes to GCS storage.

        Args:
            data: Bytes to upload
            remote_path: Destination path in bucket (e.g., "pdfs/drawing.pdf")
            content_type: MIME type (default: application/octet-stream)

        Returns:
            Full GCS URI (e.g., "gs://bucket/pdfs/drawing.pdf")

        Raises:
            IOError: If upload fails (network error, permission denied)
            ValueError: If remote_path is invalid
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            blob = self.bucket.blob(remote_path)
            blob.upload_from_string(data, content_type=content_type)
            return f"gs://{self.bucket_name}/{remote_path}"
        except Exception as e:
            raise OSError(f"Upload failed for {remote_path}: {str(e)}") from e

    def download_to_bytes(self, remote_path: str) -> bytes:
        """
        Download a file from GCS storage to bytes.

        Args:
            remote_path: Source path in bucket (e.g., "pdfs/drawing.pdf")

        Returns:
            File content as bytes

        Raises:
            FileNotFoundError: If remote file does not exist
            IOError: If download fails (network error, permission denied)
        """
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        try:
            blob = self.bucket.blob(remote_path)

            if not blob.exists():
                raise FileNotFoundError(
                    f"Remote file not found: gs://{self.bucket_name}/{remote_path}"
                )

            return blob.download_as_bytes()
        except FileNotFoundError:
            raise
        except Exception as e:
            raise OSError(f"Download failed for {remote_path}: {str(e)}") from e

    def file_exists(self, remote_path: str) -> bool:
        """
        Check if a file exists in GCS storage.

        Args:
            remote_path: Path in bucket to check

        Returns:
            True if file exists, False otherwise

        Raises:
            IOError: If bucket is inaccessible
        """
        try:
            blob = self.bucket.blob(remote_path)
            return blob.exists()
        except Exception as e:
            raise OSError(f"Failed to check file existence: {str(e)}") from e


# Module-level singleton instance
_storage_client = None


def get_storage_client() -> StorageClient:
    """
    Get or create the singleton storage client instance.

    Returns the appropriate storage client based on configuration:
    - S3StorageClient for local development (MinIO)
    - GCSStorageClient for production (Google Cloud Storage)

    Returns:
        StorageClient: Configured storage client (singleton)

    Raises:
        ValueError: If storage configuration is invalid
    """
    global _storage_client

    if _storage_client is None:
        if config.storage_backend == "s3":
            _storage_client = S3StorageClient(
                bucket_name=config.storage_bucket,
                endpoint_url=config.storage_endpoint,
                access_key=config.storage_access_key,
                secret_key=config.storage_secret_key,
                region=config.storage_region,
            )
        elif config.storage_backend == "gcs":
            _storage_client = GCSStorageClient(bucket_name=config.storage_bucket)
        else:
            raise ValueError(f"Unsupported storage backend: {config.storage_backend}")

    return _storage_client


def close_storage_client():
    """Close and reset the storage client singleton."""
    global _storage_client
    _storage_client = None
