"""SQLModel data models for drawing + sheet jobs.

These models are intentionally isolated from the existing overlay pipeline
models so we can evolve the job system without touching the legacy worker code.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.schema import FetchedValue
from sqlalchemy.types import TypeDecorator
from sqlmodel import Field, SQLModel


def _enum_values(enum_cls) -> list[str]:
    return [member.value for member in enum_cls]


class JsonArray(TypeDecorator):
    """Cross-dialect JSON array storage (ARRAY(JSONB) on Postgres, JSON elsewhere)."""

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(JSONB))
        return dialect.type_descriptor(JSON)


class JobStatus(str, Enum):
    QUEUED = "Queued"
    STARTED = "Started"
    COMPLETED = "Completed"
    FAILED = "Failed"
    CANCELED = "Canceled"


class BlockType(str, Enum):
    PLAN = "Plan"
    KEYNOTE = "Keynote"
    LEGEND = "Legend"
    GENERAL_NOTE = "General Note"
    CHANGE = "Change"
    CLASH = "Clash"
    ELEVATION = "Elevation"
    SECTION = "Section"
    DETAIL = "Detail"
    DIAGRAM = "Diagram"
    KEY_PLAN = "KeyPlan"
    NORTH_ARROW = "North Arrow"
    SCHEDULE = "Schedule"
    REVISION_HISTORY = "Revision History"
    PROJECT_INFO = "Project Info"
    GENERAL_NOTES = "General Notes"
    KEY_NOTES = "Key Notes"
    SHEET_NOTES = "Sheet Notes"
    ABBREVIATIONS = "Abbreviations"
    CODE_REFERENCES = "Code References"
    NOTES = "Notes"
    TITLE_BLOCK = "Title Block"
    CONSULTANTS = "Consultants"
    SEALS = "Seals"


class Drawing(SQLModel, table=True):
    """Represents an uploaded drawing PDF."""

    __tablename__ = "drawings"

    id: str | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": FetchedValue()},
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column("deleted_at", DateTime(timezone=True), nullable=True),
    )
    project_id: str | None = Field(default=None, sa_column=Column("project_id", String))
    filename: str | None = Field(default=None, sa_column=Column("filename", String))
    name: str | None = Field(default=None, sa_column=Column("name", String))
    uri: str = Field(sa_column=Column("uri", String, nullable=False))


class Project(SQLModel, table=True):
    """Represents a project that owns drawings and sheets."""

    __tablename__ = "projects"

    id: str | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": FetchedValue()},
    )
    organization_id: str = Field(sa_column=Column("organization_id", String, nullable=False))
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column("deleted_at", DateTime(timezone=True), nullable=True),
    )


class Sheet(SQLModel, table=True):
    """Represents a single sheet image extracted from a drawing."""

    __tablename__ = "sheets"

    id: str | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": FetchedValue()},
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column("deleted_at", DateTime(timezone=True), nullable=True),
    )
    drawing_id: str = Field(
        sa_column=Column("drawing_id", String, ForeignKey("drawings.id"), nullable=False)
    )
    index: int = Field(sa_column=Column("index", Integer, nullable=False))
    uri: str = Field(sa_column=Column("uri", String, nullable=False))
    metadata_: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("metadata", JSON, nullable=True),
    )
    title: str | None = Field(default=None, sa_column=Column("title", String))
    sheet_number: str | None = Field(
        default=None,
        sa_column=Column("sheet_number", String, nullable=True),
    )
    discipline: str | None = Field(
        default=None,
        sa_column=Column("discipline", String, nullable=True),
    )


class Block(SQLModel, table=True):
    """Represents a segmented block on a sheet."""

    __tablename__ = "blocks"

    id: str | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": FetchedValue()},
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column("deleted_at", DateTime(timezone=True), nullable=True),
    )
    sheet_id: str = Field(
        sa_column=Column("sheet_id", String, ForeignKey("sheets.id"), nullable=False)
    )
    type: BlockType | None = Field(
        default=None,
        sa_column=Column(
            "type",
            SAEnum(
                BlockType,
                name="BlockType",
                native_enum=True,
                create_type=False,
                values_callable=_enum_values,
            ),
            nullable=True,
        ),
    )
    uri: str | None = Field(default=None, sa_column=Column("uri", String))
    bounds: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("bounds", JSON, nullable=True),
    )
    ocr: str | None = Field(default=None, sa_column=Column("ocr", String))
    description: str | None = Field(default=None, sa_column=Column("description", String))
    metadata_: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("metadata", JSON, nullable=True),
    )


class Overlay(SQLModel, table=True):
    """Represents a block-to-block overlay result."""

    __tablename__ = "overlays"

    id: str | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": FetchedValue()},
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column("deleted_at", DateTime(timezone=True), nullable=True),
    )
    job_id: str | None = Field(
        default=None,
        sa_column=Column("job_id", String, ForeignKey("jobs.id"), nullable=True),
    )
    block_a_id: str = Field(
        sa_column=Column("block_a_id", String, ForeignKey("blocks.id"), nullable=False)
    )
    block_b_id: str = Field(
        sa_column=Column("block_b_id", String, ForeignKey("blocks.id"), nullable=False)
    )
    uri: str | None = Field(default=None, sa_column=Column("uri", String, nullable=True))
    addition_uri: str | None = Field(
        default=None, sa_column=Column("addition_uri", String, nullable=True)
    )
    deletion_uri: str | None = Field(
        default=None, sa_column=Column("deletion_uri", String, nullable=True)
    )
    score: float | None = Field(default=None, sa_column=Column("score", Float, nullable=True))
    summary: dict[str, Any] | None = Field(
        default=None,
        sa_column=Column("summary", JSON, nullable=True),
    )
    changes: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column("changes", JSONB, nullable=True),
    )
    clashes: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column("clashes", JSONB, nullable=True),
    )


class Job(SQLModel, table=True):
    """Tracks background processing for drawings, sheets, and overlays."""

    __tablename__ = "jobs"

    id: str | None = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"server_default": FetchedValue()},
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("created_at", DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column=Column("updated_at", DateTime(timezone=True), nullable=False),
    )
    parent_id: str | None = Field(
        default=None,
        sa_column=Column("parent_id", String, ForeignKey("jobs.id"), nullable=True),
    )
    type: str = Field(sa_column=Column("type", String, nullable=False))
    status: JobStatus = Field(
        sa_column=Column(
            "status",
            SAEnum(
                JobStatus,
                name="JobStatus",
                native_enum=True,
                create_type=False,
                values_callable=_enum_values,
            ),
            nullable=False,
        )
    )
    organization_id: str = Field(sa_column=Column("organization_id", String, nullable=False))
    project_id: str | None = Field(
        default=None, sa_column=Column("project_id", String, nullable=True)
    )
    actor_id: str | None = Field(default=None, sa_column=Column("actor_id", String, nullable=True))
    target_type: str = Field(sa_column=Column("target_type", String, nullable=False))
    target_id: str = Field(sa_column=Column("target_id", String, nullable=False))
    payload: dict[str, Any] = Field(sa_column=Column("payload", JSON, nullable=False))
    events: list[dict[str, Any]] | None = Field(
        default=None,
        sa_column=Column("events", JSON, nullable=True),
    )
