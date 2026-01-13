"""Database models for BuildTrace API."""

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def generate_cuid() -> str:
    """Generate a CUID-like ID."""
    import secrets
    import time

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = secrets.token_hex(8)
    return f"c{timestamp}{random_part}"[:25]


class User(SQLModel, table=True):
    """User database model."""

    __tablename__ = "users"

    id: str = Field(primary_key=True, default_factory=generate_cuid)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    email: str = Field(unique=True, index=True)
    password_hash: str
    first_name: str | None = None
    last_name: str | None = None
    profile_image_url: str | None = None
    organization_id: str | None = None  # Link to organization


class Organization(SQLModel, table=True):
    """Organization database model."""

    __tablename__ = "organizations"

    id: str = Field(primary_key=True, default_factory=generate_cuid)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    name: str
