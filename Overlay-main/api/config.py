"""Configuration for the BuildTrace API."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5000"]

    # Database
    database_url: str = "postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev"

    # Storage (GCS or S3-compatible)
    storage_backend: str = "s3"  # "s3" or "gcs"
    storage_bucket: str = "overlay-uploads"
    storage_endpoint: str = "http://localhost:9000"  # Internal endpoint (Docker network)
    storage_external_url: str = "http://localhost:9000"  # External endpoint (browser accessible)
    storage_access_key: str = "minio"
    storage_secret_key: str = "minio123"
    storage_region: str = "us-east-1"

    # Pub/Sub
    pubsub_project_id: str = "local-dev"
    pubsub_emulator_host: str | None = "localhost:8681"
    vision_topic: str = "vision"

    # Auth
    google_client_id: str | None = None
    google_client_secret: str | None = None
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()

