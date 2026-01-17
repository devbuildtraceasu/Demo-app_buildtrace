"""Upload routes for file handling."""

import uuid
from datetime import datetime

from fastapi import APIRouter, File, UploadFile, HTTPException, status

from api.config import settings
from api.dependencies import CurrentUser, OptionalUser, StorageDep
from api.schemas.upload import SignedUrlRequest, SignedUrlResponse

router = APIRouter()

# File validation constants
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".dwg", ".dxf"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/jpg",
    "application/x-dwg",
    "application/dxf",
    "application/octet-stream",  # For DWG/DXF files
}
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB


def validate_file_type(filename: str, content_type: str) -> None:
    """Validate file extension and content type."""
    # Check file extension
    extension = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Supported types: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Check content type
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Content type '{content_type}' not allowed. Supported types: PDF, PNG, JPG, DWG, DXF",
        )


def validate_file_size(size: int) -> None:
    """Validate file size."""
    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )


@router.post("/signed-url", response_model=SignedUrlResponse)
async def get_signed_upload_url(
    request: SignedUrlRequest,
    storage: StorageDep,
    user: OptionalUser,  # Allow unauthenticated in dev mode
):
    """Generate a signed URL for uploading a file to storage."""
    # Validate file type
    validate_file_type(request.filename, request.content_type)

    # Generate unique remote path
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    extension = request.filename.rsplit(".", 1)[-1] if "." in request.filename else "pdf"

    if request.project_id:
        remote_path = f"projects/{request.project_id}/uploads/{timestamp}-{unique_id}.{extension}"
    else:
        remote_path = f"uploads/{timestamp}-{unique_id}.{extension}"

    try:
        upload_url = storage.generate_signed_url(remote_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate signed URL: {str(e)}",
        )

    return SignedUrlResponse(
        upload_url=upload_url,
        remote_path=remote_path,
        expires_in=3600,
    )


@router.post("/direct")
async def upload_file_directly(
    file: UploadFile = File(...),
    project_id: str | None = None,
    storage: StorageDep = None,
    user: OptionalUser = None,  # Allow unauthenticated in dev mode
):
    """Upload a file directly (for smaller files or when signed URLs aren't supported)."""
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage not configured",
        )

    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    validate_file_type(file.filename, file.content_type or "application/octet-stream")

    # Read file contents and validate size
    contents = await file.read()
    validate_file_size(len(contents))

    # Generate unique remote path
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    extension = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "pdf"

    if project_id:
        remote_path = f"projects/{project_id}/uploads/{timestamp}-{unique_id}.{extension}"
    else:
        remote_path = f"uploads/{timestamp}-{unique_id}.{extension}"

    try:
        uri = storage.upload_from_bytes(
            contents,
            remote_path,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )

    return {
        "uri": uri,
        "remote_path": remote_path,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(contents),
    }


@router.get("/download-url/{remote_path:path}")
async def get_download_url(
    remote_path: str,
    storage: StorageDep,
    user: OptionalUser,  # Allow unauthenticated in dev mode
):
    """Generate a signed URL for downloading a file."""
    try:
        download_url = storage.generate_download_url(remote_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate download URL: {str(e)}",
        )

    return {
        "download_url": download_url,
        "remote_path": remote_path,
        "expires_in": 3600,
    }


@router.post("/public/upload")
async def public_upload(
    file: UploadFile = File(...),
    storage: StorageDep = None,
):
    """Public upload endpoint for Try a Project feature. No authentication required.
    Files are stored in a temp folder for public comparisons.
    """
    if storage is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Storage not configured",
        )

    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    validate_file_type(file.filename, file.content_type or "application/octet-stream")

    # Read file contents and validate size
    contents = await file.read()
    validate_file_size(len(contents))

    # Generate unique remote path in temp folder
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    extension = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "pdf"

    remote_path = f"temp/public/{timestamp}-{unique_id}.{extension}"

    try:
        uri = storage.upload_from_bytes(
            contents,
            remote_path,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}",
        )

    return {
        "uri": uri,
        "remote_path": remote_path,
        "filename": file.filename,
        "content_type": file.content_type,
        "size": len(contents),
    }

