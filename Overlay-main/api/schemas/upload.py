"""Upload schemas."""

from pydantic import BaseModel


class SignedUrlRequest(BaseModel):
    """Request for generating a signed upload URL."""

    filename: str
    content_type: str = "application/pdf"
    project_id: str | None = None


class SignedUrlResponse(BaseModel):
    """Response with signed upload URL."""

    upload_url: str
    remote_path: str
    expires_in: int = 3600

