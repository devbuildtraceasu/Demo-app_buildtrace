"""Configuration for the BuildTrace API."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Server
    port: int = 8000
    debug: bool = False
    log_level: str = "INFO"

    # CORS - can be JSON string or comma-separated
    cors_origins: str = '["http://localhost:3000", "http://localhost:5000"]'
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from JSON string or comma-separated string."""
        import json
        if not self.cors_origins:
            return ["http://localhost:3000", "http://localhost:5000"]
        try:
            # Try parsing as JSON first
            parsed = json.loads(self.cors_origins)
            if isinstance(parsed, list):
                return parsed
            return [str(parsed)]
        except (json.JSONDecodeError, TypeError):
            # If not JSON, treat as comma-separated string
            return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    # Database
    database_url: str = "postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev"
    
    # Cloud SQL components (for constructing DATABASE_URL in GCP)
    db_user: str | None = None
    db_password: str | None = None
    db_name: str | None = None
    cloud_sql_connection_name: str | None = None
    
    def get_database_url(self) -> str:
        """Get database URL, constructing from components if in GCP environment."""
        # If Cloud SQL components are provided, construct the connection string
        if self.cloud_sql_connection_name and self.db_user and self.db_password and self.db_name:
            return f"postgresql://{self.db_user}:{self.db_password}@/{self.db_name}?host=/cloudsql/{self.cloud_sql_connection_name}"
        # Otherwise use the configured database_url
        return self.database_url

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
    google_redirect_uri: str | None = None  # Override redirect URI if set
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

