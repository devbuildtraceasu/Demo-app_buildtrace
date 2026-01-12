"""Configuration management for vision worker."""

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Vision worker configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    db_host: str
    db_port: int = 5432
    db_name: str = "odin_dev"
    db_user: str
    db_password: str

    # Storage Backend Configuration
    storage_backend: Literal["s3", "gcs"] = Field(
        default="gcs",
        description="Storage backend to use: 's3' for MinIO/S3, 'gcs' for Google Cloud Storage",
    )
    storage_bucket: str = Field(description="Storage bucket name (used for both S3 and GCS)")

    # S3/MinIO Configuration (for local development)
    storage_endpoint: str | None = Field(
        default=None, description="S3 endpoint URL (e.g., http://localhost:9000 for MinIO)"
    )
    storage_access_key: str | None = Field(default=None, description="S3 access key ID")
    storage_secret_key: str | None = Field(default=None, description="S3 secret access key")
    storage_region: str = Field(default="us-east-1", description="S3 region (default: us-east-1)")

    # Google Cloud Storage Configuration (for production)
    google_application_credentials: str | None = Field(
        default=None, description="Path to GCP service account JSON file"
    )

    # PubSub Configuration
    pubsub_project_id: str
    vision_topic: str = "vision"
    vision_subscription: str = "vision.worker"
    pubsub_max_delivery_attempts: int | None = Field(
        default=None,
        description="Max delivery attempts before Pub/Sub dead-letters messages.",
    )

    # OpenAI Configuration (for GPT-5-mini OCR and identifier extraction, GPT-5.1 for change analysis)
    openai_api_key: str
    openai_model: str = Field(
        default="gpt-5.1", description="OpenAI model for change analysis (default: gpt-5.1)"
    )
    gemini_api_key: str | None = Field(
        default=None,
        description="Gemini API key for non-Vertex usage (optional)",
    )
    vertex_ai_project: str | None = Field(default=None, description="GCP project ID for Vertex AI")

    # PDF Conversion Configuration
    pdf_conversion_dpi: int = Field(
        default=300, description="DPI for PDF to PNG conversion (default: 300)"
    )
    overlay_output_dpi: int = Field(
        default=100, description="DPI for overlay/deletion/addition output images (default: 100)"
    )

    # Worker Configuration
    worker_poll_interval: int = 10
    worker_max_retries: int = 3
    worker_log_level: str = Field(default="INFO", description="Logging level")
    worker_max_concurrent_messages: int = Field(
        default=3,
        description="Max concurrent messages per subscription (recommended: 2-3 for 1GB RAM machines)",
    )
    worker_max_memory_bytes: int = Field(
        default=500 * 1024 * 1024,  # 500MB
        description="Max memory for in-flight messages in bytes (recommended: 500MB for 1GB RAM machines)",
    )
    worker_max_lease_duration_seconds: int = Field(
        default=1_800,
        description="Max time to hold a Pub/Sub message lease during processing (seconds)",
    )

    # Web app configuration
    app_url: str = Field(
        default="http://localhost:5173",
        description="Base URL for the web app (used for job credit rates)",
    )

    # SIFT Feature Detection Parameters (Job 4: Overlay Generation)
    sift_n_features: int = Field(
        default=1_000, description="Maximum number of SIFT features to detect per image"
    )
    sift_exclude_margin: float = Field(
        default=0.2,
        description="Margin exclusion ratio (0.2 = exclude 20% from each edge for feature detection)",
    )
    sift_ratio_threshold: float = Field(
        default=0.75,
        description="Lowe's ratio test threshold for feature matching (0.75 recommended)",
    )

    # RANSAC Parameters (Job 4: Overlay Generation)
    ransac_reproj_threshold: float = Field(
        default=15.0, description="RANSAC reprojection threshold in pixels"
    )
    ransac_max_iters: int = Field(default=5_000, description="Maximum RANSAC iterations")
    ransac_confidence: float = Field(
        default=0.95, description="RANSAC confidence level (0.95 = 95% confidence)"
    )

    # Transformation Constraints (Job 4: Overlay Generation)
    transform_scale_min: float = Field(default=0.3, description="Minimum allowed scale factor")
    transform_scale_max: float = Field(default=3.0, description="Maximum allowed scale factor")
    transform_rotation_deg_min: float = Field(
        default=-30.0, description="Minimum allowed rotation in degrees"
    )
    transform_rotation_deg_max: float = Field(
        default=30.0, description="Maximum allowed rotation in degrees"
    )

    # Overlay Artifact Filtering (Job 4: Overlay Generation)
    overlay_intensity_threshold: int = Field(
        default=40,
        description="Minimum intensity difference (0-255) to classify as real change vs artifact",
    )

    @field_validator("storage_backend")
    @classmethod
    def validate_storage_backend(cls, v: str) -> str:
        """Validate storage backend value."""
        if v not in ("s3", "gcs"):
            raise ValueError("storage_backend must be either 's3' or 'gcs'")
        return v


_config: Config | None = None


class _LazyConfig:
    """Proxy that lazily loads config on first attribute access."""

    def __getattr__(self, name: str):
        global _config
        if _config is None:
            _config = Config()
        return getattr(_config, name)


config = _LazyConfig()
