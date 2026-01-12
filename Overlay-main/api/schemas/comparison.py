"""Comparison and change schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ComparisonCreate(BaseModel):
    """Comparison creation request."""

    project_id: str
    drawing_a_id: str
    drawing_b_id: str
    sheet_a_id: str | None = None
    sheet_b_id: str | None = None


class ComparisonUpdate(BaseModel):
    """Comparison update request."""

    status: str | None = None


class ComparisonResponse(BaseModel):
    """Comparison response."""

    id: str
    project_id: str
    drawing_a_id: str
    drawing_b_id: str
    sheet_a_id: str | None = None
    sheet_b_id: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    # Overlay data
    overlay_uri: str | None = None
    addition_uri: str | None = None
    deletion_uri: str | None = None
    score: float | None = None

    # Change summary
    change_count: int = 0
    total_cost_impact: str | None = None
    total_schedule_impact: str | None = None

    class Config:
        from_attributes = True


class ChangeCreate(BaseModel):
    """Change creation request."""

    comparison_id: str
    type: str  # "added", "removed", "modified"
    title: str
    description: str | None = None
    bounds: dict[str, Any] | None = None
    trade: str | None = None
    discipline: str | None = None
    estimated_cost: str | None = None
    schedule_impact: str | None = None


class ChangeUpdate(BaseModel):
    """Change update request."""

    title: str | None = None
    description: str | None = None
    status: str | None = None
    assignee: str | None = None
    estimated_cost: str | None = None
    schedule_impact: str | None = None


class ChangeResponse(BaseModel):
    """Change response."""

    id: str
    comparison_id: str
    type: str
    title: str
    description: str | None = None
    bounds: dict[str, Any] | None = None
    trade: str | None = None
    discipline: str | None = None
    estimated_cost: str | None = None
    schedule_impact: str | None = None
    status: str = "open"
    assignee: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

