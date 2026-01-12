"""FastAPI dependencies for database, storage, and authentication."""

import os
from typing import TYPE_CHECKING, Annotated, Any, Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel import Session, create_engine

from api.config import settings

if TYPE_CHECKING:
    from google.cloud import pubsub_v1

# Database engine - use constructed URL if in GCP
database_url = settings.get_database_url()
engine = create_engine(database_url, echo=settings.debug)


def get_session() -> Generator[Session, None, None]:
    """Get database session."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]

# Auth
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict | None:
    """Get current user from JWT token."""
    if credentials is None:
        return None

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        return None


async def require_auth(
    user: Annotated[dict | None, Depends(get_current_user)],
) -> dict:
    """Require authenticated user."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


CurrentUser = Annotated[dict, Depends(require_auth)]
OptionalUser = Annotated[dict | None, Depends(get_current_user)]


# Storage client
def get_storage_client():
    """Get storage client based on configuration."""
    from io import BytesIO

    import boto3
    from google.cloud import storage

    if settings.storage_backend == "s3":
        # Set emulator host if configured
        if settings.pubsub_emulator_host:
            os.environ.setdefault("PUBSUB_EMULATOR_HOST", settings.pubsub_emulator_host)

        client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint,
            aws_access_key_id=settings.storage_access_key,
            aws_secret_access_key=settings.storage_secret_key,
            region_name=settings.storage_region,
        )
        return S3Storage(
            client, 
            settings.storage_bucket,
            internal_url=settings.storage_endpoint,
            external_url=settings.storage_external_url,
        )
    else:
        client = storage.Client()
        bucket = client.bucket(settings.storage_bucket)
        return GCSStorage(bucket)


class S3Storage:
    """S3-compatible storage wrapper."""

    def __init__(self, client, bucket_name: str, internal_url: str = "", external_url: str = ""):
        self.client = client
        self.bucket_name = bucket_name
        self.internal_url = internal_url
        self.external_url = external_url

    def _make_external(self, url: str) -> str:
        """Convert internal URL to external URL for browser access."""
        if self.internal_url and self.external_url and self.internal_url != self.external_url:
            return url.replace(self.internal_url, self.external_url)
        return url

    def generate_signed_url(self, remote_path: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for uploading."""
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket_name, "Key": remote_path},
            ExpiresIn=expiration,
        )
        return self._make_external(url)

    def generate_download_url(self, remote_path: str, expiration: int = 3600) -> str:
        """Generate a presigned URL for downloading."""
        url = self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": remote_path},
            ExpiresIn=expiration,
        )
        return self._make_external(url)

    def upload_from_bytes(
        self, data: bytes, remote_path: str, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload bytes to storage."""
        from io import BytesIO

        self.client.upload_fileobj(
            BytesIO(data),
            self.bucket_name,
            remote_path,
            ExtraArgs={"ContentType": content_type},
        )
        return f"s3://{self.bucket_name}/{remote_path}"


class GCSStorage:
    """Google Cloud Storage wrapper."""

    def __init__(self, bucket):
        self.bucket = bucket

    def generate_signed_url(self, remote_path: str, expiration: int = 3600) -> str:
        """Generate a signed URL for uploading."""
        from datetime import timedelta

        blob = self.bucket.blob(remote_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration),
            method="PUT",
        )

    def generate_download_url(self, remote_path: str, expiration: int = 3600) -> str:
        """Generate a signed URL for downloading."""
        from datetime import timedelta

        blob = self.bucket.blob(remote_path)
        return blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiration),
            method="GET",
        )

    def upload_from_bytes(
        self, data: bytes, remote_path: str, content_type: str = "application/octet-stream"
    ) -> str:
        """Upload bytes to storage."""
        blob = self.bucket.blob(remote_path)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket.name}/{remote_path}"


StorageDep = Annotated[S3Storage | GCSStorage, Depends(get_storage_client)]


# Pub/Sub client
def get_pubsub_client():
    """Get Pub/Sub client."""
    import os

    from google.cloud import pubsub_v1

    # Set emulator host if configured
    if settings.pubsub_emulator_host:
        os.environ["PUBSUB_EMULATOR_HOST"] = settings.pubsub_emulator_host

    return pubsub_v1.PublisherClient()


PubSubDep = Annotated[Any, Depends(get_pubsub_client)]  # Type is pubsub_v1.PublisherClient at runtime

