"""Pydantic schemas for API requests and responses."""

from api.schemas.auth import TokenResponse, UserCreate, UserLogin, UserResponse
from api.schemas.comparison import (
    ComparisonCreate,
    ComparisonResponse,
    ComparisonUpdate,
    ChangeCreate,
    ChangeResponse,
    ChangeUpdate,
)
from api.schemas.drawing import (
    DrawingCreate,
    DrawingResponse,
    SheetResponse,
    BlockResponse,
)
from api.schemas.job import JobCreate, JobResponse, JobStatus
from api.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from api.schemas.upload import SignedUrlRequest, SignedUrlResponse

__all__ = [
    # Auth
    "TokenResponse",
    "UserCreate",
    "UserLogin",
    "UserResponse",
    # Comparison
    "ComparisonCreate",
    "ComparisonResponse",
    "ComparisonUpdate",
    "ChangeCreate",
    "ChangeResponse",
    "ChangeUpdate",
    # Drawing
    "DrawingCreate",
    "DrawingResponse",
    "SheetResponse",
    "BlockResponse",
    # Job
    "JobCreate",
    "JobResponse",
    "JobStatus",
    # Project
    "ProjectCreate",
    "ProjectResponse",
    "ProjectUpdate",
    # Upload
    "SignedUrlRequest",
    "SignedUrlResponse",
]

