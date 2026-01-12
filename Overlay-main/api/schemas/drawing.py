"""Drawing schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DrawingCreate(BaseModel):
    """Drawing creation request."""

    project_id: str
    filename: str
    name: str | None = None
    uri: str


class DrawingResponse(BaseModel):
    """Drawing response."""

    id: str
    project_id: str
    filename: str
    name: str | None = None
    uri: str
    created_at: datetime
    updated_at: datetime
    sheet_count: int = 0
    job_id: str | None = None  # Preprocessing job ID for tracking progress
    status: str = "pending"  # pending, processing, completed, failed

    class Config:
        from_attributes = True


class SheetResponse(BaseModel):
    """Sheet response."""

    id: str
    drawing_id: str
    index: int
    uri: str
    title: str | None = None
    sheet_number: str | None = None
    discipline: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BlockResponse(BaseModel):
    """Block response."""

    id: str
    sheet_id: str
    type: str | None = None
    uri: str | None = None
    bounds: dict[str, Any] | None = None
    ocr: str | None = None
    description: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

