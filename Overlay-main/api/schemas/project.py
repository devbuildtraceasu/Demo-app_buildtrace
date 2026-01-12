"""Project schemas."""

from datetime import datetime

from pydantic import BaseModel


class ProjectCreate(BaseModel):
    """Project creation request."""

    name: str
    description: str | None = None
    organization_id: str | None = None


class ProjectUpdate(BaseModel):
    """Project update request."""

    name: str | None = None
    description: str | None = None


class ProjectResponse(BaseModel):
    """Project response."""

    id: str
    name: str
    description: str | None = None
    organization_id: str
    created_at: datetime
    updated_at: datetime
    drawing_count: int = 0
    comparison_count: int = 0

    class Config:
        from_attributes = True

