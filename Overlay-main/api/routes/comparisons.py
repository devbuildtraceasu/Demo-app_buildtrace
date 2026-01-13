"""Comparison routes."""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, SQLModel, select

from api.config import settings
from api.dependencies import CurrentUser, OptionalUser, SessionDep, StorageDep, get_pubsub_client, get_storage_client
from api.schemas.comparison import (
    ChangeCreate,
    ChangeResponse,
    ChangeUpdate,
    ComparisonCreate,
    ComparisonResponse,
    ComparisonUpdate,
)

router = APIRouter()


# SQLModel for Overlay (matches Prisma schema)
class Overlay(SQLModel, table=True):
    """Overlay database model."""

    __tablename__ = "overlays"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    block_a_id: str
    block_b_id: str
    job_id: str | None = None
    uri: str | None = None
    addition_uri: str | None = None
    deletion_uri: str | None = None
    score: float | None = None
    summary: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    changes: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))
    clashes: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSON))


# Change model for frontend compatibility
class Change(SQLModel, table=True):
    """Change database model (for detected changes)."""

    __tablename__ = "changes"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    overlay_id: str
    type: str  # "added", "removed", "modified"
    title: str
    description: str | None = None
    bounds: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    trade: str | None = None
    discipline: str | None = None
    estimated_cost: str | None = None
    schedule_impact: str | None = None
    status: str = "open"
    assignee: str | None = None


def generate_cuid() -> str:
    """Generate a CUID-like ID."""
    import secrets
    import time

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = secrets.token_hex(8)
    return f"c{timestamp}{random_part}"[:25]


def s3_uri_to_download_url(uri: str | None, storage) -> str | None:
    """Convert an S3 URI to a browser-accessible download URL."""
    if not uri:
        return None
    # Parse s3://bucket/path format
    if uri.startswith("s3://"):
        parts = uri[5:].split("/", 1)
        if len(parts) == 2:
            _, path = parts
            return storage.generate_download_url(path)
    return uri


@router.get("/project/{project_id}", response_model=list[ComparisonResponse])
async def list_comparisons(project_id: str, session: SessionDep, storage: StorageDep, user: OptionalUser = None):
    """List all comparisons for a project."""
    # For now, return overlays grouped by their parent job
    # In production, you'd have a proper Comparison table
    statement = select(Overlay).where(Overlay.deleted_at.is_(None))
    overlays = session.exec(statement).all()

    return [
        ComparisonResponse(
            id=o.id,
            project_id=project_id,
            drawing_a_id=o.block_a_id,
            drawing_b_id=o.block_b_id,
            status="completed" if o.uri else "processing",
            created_at=o.created_at,
            updated_at=o.updated_at,
            overlay_uri=s3_uri_to_download_url(o.uri, storage),
            addition_uri=s3_uri_to_download_url(o.addition_uri, storage),
            deletion_uri=s3_uri_to_download_url(o.deletion_uri, storage),
            score=o.score,
            change_count=len(o.changes) if o.changes else 0,
        )
        for o in overlays
    ]


@router.post("", response_model=ComparisonResponse, status_code=status.HTTP_201_CREATED)
async def create_comparison(
    comparison_data: ComparisonCreate,
    session: SessionDep,
    user: OptionalUser = None,
):
    """Create a new comparison and submit job to worker."""
    import logging
    logger = logging.getLogger(__name__)
    from api.routes.projects import Project
    
    # Validate that project exists
    if comparison_data.project_id:
        project = session.get(Project, comparison_data.project_id)
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project not found: {comparison_data.project_id}. Please create the project first.",
            )
        if project.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project has been deleted: {comparison_data.project_id}",
            )
    
    # Get block IDs (use sheet_a_id/sheet_b_id if provided, otherwise drawing_a_id/drawing_b_id)
    block_a_id = comparison_data.sheet_a_id or comparison_data.drawing_a_id
    block_b_id = comparison_data.sheet_b_id or comparison_data.drawing_b_id
    
    # Validate that blocks exist and are not deleted
    from api.routes.drawings import Block
    block_a = session.get(Block, block_a_id)
    block_b = session.get(Block, block_b_id)
    
    if not block_a:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block A not found: {block_a_id}",
        )
    if block_a.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block A has been deleted: {block_a_id}",
        )
    if not block_b:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block B not found: {block_b_id}",
        )
    if block_b.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Block B has been deleted: {block_b_id}",
        )
    if not block_a.uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Block A ({block_a_id}) is missing image URI",
        )
    if not block_b.uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Block B ({block_b_id}) is missing image URI",
        )
    
    logger.info(f"Creating comparison: block_a={block_a_id}, block_b={block_b_id}")
    
    overlay_id = generate_cuid()

    # Create overlay record (job_id will be set after job creation)
    overlay = Overlay(
        id=overlay_id,
        block_a_id=block_a_id,
        block_b_id=block_b_id,
    )
    session.add(overlay)
    session.commit()

    # Submit job to Pub/Sub
    import logging
    logger = logging.getLogger("api.routes.comparisons")
    
    # Log at the start to ensure logging works
    print(f"[COMPARISON] Creating comparison: block_a={block_a_id}, block_b={block_b_id}", flush=True)
    logger.info(f"=== Creating comparison: block_a={block_a_id}, block_b={block_b_id} ===")
    
    job_id = generate_cuid()
    
    # Create Job record in database first (worker expects it to exist)
    from api.routes.jobs import Job as JobModel
    job = JobModel(
        id=job_id,
        project_id=comparison_data.project_id,
        target_type="overlay",
        target_id=overlay_id,
        type="vision.block.overlay.generate",
        status="Queued",
        payload={
            "block_a_id": block_a_id,
            "block_b_id": block_b_id,
        },
    )
    session.add(job)
    session.commit()  # Commit job first
    
    # Update overlay with job_id (job now exists in DB)
    overlay.job_id = job_id
    session.commit()
    
    # Worker expects: { "type": "...", "id": "...", "payload": {...} }
    job_payload = {
        "type": "vision.block.overlay.generate",
        "id": job_id,
        "payload": {
            "blockAId": block_a_id,
            "blockBId": block_b_id,
        },
    }

    # Publish to Pub/Sub
    try:
        print(f"[COMPARISON] Publishing job {job_id} to Pub/Sub...", flush=True)
        logger.info(f"Publishing job {job_id} to topic {settings.vision_topic}")
        
        pubsub = get_pubsub_client()
        topic_path = pubsub.topic_path(settings.pubsub_project_id, settings.vision_topic)
        
        print(f"[COMPARISON] Topic path: {topic_path}", flush=True)
        print(f"[COMPARISON] Payload: {json.dumps(job_payload)}", flush=True)
        
        future = pubsub.publish(
            topic_path,
            json.dumps(job_payload).encode("utf-8"),
            type="vision.block.overlay.generate",
            id=job_id,
        )
        message_id = future.result(timeout=10.0)
        print(f"[COMPARISON] Successfully published job {job_id}, message_id={message_id}", flush=True)
        logger.info(f"Successfully published job {job_id}, message_id={message_id}")
    except Exception as e:
        # Log error but don't fail - job can be retried manually
        print(f"[COMPARISON] ERROR: Failed to publish job {job_id} to Pub/Sub: {e}", flush=True)
        import traceback
        print(f"[COMPARISON] Traceback: {traceback.format_exc()}", flush=True)
        logger.error(f"Failed to publish job {job_id} to Pub/Sub: {e}", exc_info=True)
        # Update job status to indicate publish failure
        job.status = "Failed"
        job.events = job.events or []
        job.events.append({
            "type": "failed",
            "status": "Failed",
            "event_type": "publish_failed",
            "metadata": {
                "error": str(e),
                "errorType": type(e).__name__,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        session.add(job)
        session.commit()

    return ComparisonResponse(
        id=overlay.id,
        project_id=comparison_data.project_id,
        drawing_a_id=comparison_data.drawing_a_id,
        drawing_b_id=comparison_data.drawing_b_id,
        sheet_a_id=comparison_data.sheet_a_id,
        sheet_b_id=comparison_data.sheet_b_id,
        status="processing",
        created_at=overlay.created_at,
        updated_at=overlay.updated_at,
    )


@router.get("/{comparison_id}", response_model=ComparisonResponse)
async def get_comparison(comparison_id: str, session: SessionDep, storage: StorageDep, user: OptionalUser = None):
    """Get a comparison by ID."""
    overlay = session.get(Overlay, comparison_id)

    if not overlay or overlay.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comparison not found",
        )

    # Check job status to determine comparison status
    status_value = "processing"
    if overlay.uri:
        status_value = "completed"
    elif overlay.job_id:
        # Check if the associated job has failed
        from api.routes.jobs import Job
        job = session.get(Job, overlay.job_id)
        if job:
            if job.status == "Failed":
                status_value = "failed"
            elif job.status == "Completed":
                # Job completed but overlay URI not set - might be an error or still processing
                status_value = "processing"  # Keep as processing until URI is set
            elif job.status in ("Queued", "Started"):
                status_value = "processing"
            else:
                # Unknown status, default to processing
                status_value = "processing"
        else:
            # Job ID exists but job not found - might be deleted or not created yet
            status_value = "processing"
    # If no job_id, status remains "processing" (job might not have been created yet)

    return ComparisonResponse(
        id=overlay.id,
        project_id="",  # Would need to join with job/project
        drawing_a_id=overlay.block_a_id,
        drawing_b_id=overlay.block_b_id,
        status=status_value,
        created_at=overlay.created_at,
        updated_at=overlay.updated_at,
        overlay_uri=s3_uri_to_download_url(overlay.uri, storage),
        addition_uri=s3_uri_to_download_url(overlay.addition_uri, storage),
        deletion_uri=s3_uri_to_download_url(overlay.deletion_uri, storage),
        score=overlay.score,
        change_count=len(overlay.changes) if overlay.changes else 0,
    )


@router.get("/{comparison_id}/changes", response_model=list[ChangeResponse])
async def list_changes(comparison_id: str, session: SessionDep, user: OptionalUser = None):
    """List all changes for a comparison."""
    statement = select(Change).where(
        Change.overlay_id == comparison_id,
        Change.deleted_at.is_(None),
    )
    changes = session.exec(statement).all()

    return [
        ChangeResponse(
            id=c.id,
            comparison_id=c.overlay_id,
            type=c.type,
            title=c.title,
            description=c.description,
            bounds=c.bounds,
            trade=c.trade,
            discipline=c.discipline,
            estimated_cost=c.estimated_cost,
            schedule_impact=c.schedule_impact,
            status=c.status,
            assignee=c.assignee,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in changes
    ]


@router.post("/{comparison_id}/changes", response_model=ChangeResponse, status_code=status.HTTP_201_CREATED)
async def create_change(
    comparison_id: str,
    change_data: ChangeCreate,
    session: SessionDep,
    user: OptionalUser = None,
):
    """Create a new change for a comparison."""
    # Validate that overlay exists
    overlay = session.get(Overlay, comparison_id)
    if not overlay:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison (overlay) not found: {comparison_id}",
        )
    if overlay.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Comparison (overlay) has been deleted: {comparison_id}",
        )
    
    change = Change(
        id=generate_cuid(),
        overlay_id=comparison_id,
        type=change_data.type,
        title=change_data.title,
        description=change_data.description,
        bounds=change_data.bounds,
        trade=change_data.trade,
        discipline=change_data.discipline,
        estimated_cost=change_data.estimated_cost,
        schedule_impact=change_data.schedule_impact,
    )

    session.add(change)
    session.commit()
    session.refresh(change)

    return ChangeResponse(
        id=change.id,
        comparison_id=change.overlay_id,
        type=change.type,
        title=change.title,
        description=change.description,
        bounds=change.bounds,
        trade=change.trade,
        discipline=change.discipline,
        estimated_cost=change.estimated_cost,
        schedule_impact=change.schedule_impact,
        status=change.status,
        assignee=change.assignee,
        created_at=change.created_at,
        updated_at=change.updated_at,
    )


@router.patch("/changes/{change_id}", response_model=ChangeResponse)
async def update_change(
    change_id: str,
    change_data: ChangeUpdate,
    session: SessionDep,
    user: CurrentUser,
):
    """Update a change."""
    change = session.get(Change, change_id)

    if not change or change.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    if change_data.title is not None:
        change.title = change_data.title
    if change_data.description is not None:
        change.description = change_data.description
    if change_data.status is not None:
        change.status = change_data.status
    if change_data.assignee is not None:
        change.assignee = change_data.assignee
    if change_data.estimated_cost is not None:
        change.estimated_cost = change_data.estimated_cost
    if change_data.schedule_impact is not None:
        change.schedule_impact = change_data.schedule_impact

    change.updated_at = datetime.now(timezone.utc)
    session.add(change)
    session.commit()
    session.refresh(change)

    return ChangeResponse(
        id=change.id,
        comparison_id=change.overlay_id,
        type=change.type,
        title=change.title,
        description=change.description,
        bounds=change.bounds,
        trade=change.trade,
        discipline=change.discipline,
        estimated_cost=change.estimated_cost,
        schedule_impact=change.schedule_impact,
        status=change.status,
        assignee=change.assignee,
        created_at=change.created_at,
        updated_at=change.updated_at,
    )


@router.delete("/changes/{change_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_change(change_id: str, session: SessionDep, user: CurrentUser):
    """Soft delete a change."""
    change = session.get(Change, change_id)

    if not change or change.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Change not found",
        )

    change.deleted_at = datetime.now(timezone.utc)
    change.updated_at = datetime.now(timezone.utc)
    session.add(change)
    session.commit()

    return None

