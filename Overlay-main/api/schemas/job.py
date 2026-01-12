"""Job schemas."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel


class JobStatus(str, Enum):
    """Job status enum."""

    QUEUED = "queued"
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class JobCreate(BaseModel):
    """Job creation request."""

    type: str
    project_id: str | None = None
    target_type: str
    target_id: str
    payload: dict[str, Any] = {}


class JobResponse(BaseModel):
    """Job response."""

    id: str
    type: str
    status: JobStatus
    project_id: str | None = None
    parent_id: str | None = None
    target_type: str
    target_id: str
    payload: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

