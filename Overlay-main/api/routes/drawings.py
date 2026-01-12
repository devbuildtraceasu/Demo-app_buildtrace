"""Drawing routes."""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, SQLModel, select

from api.config import settings
from api.dependencies import CurrentUser, OptionalUser, SessionDep, get_pubsub_client
from api.schemas.drawing import BlockResponse, DrawingCreate, DrawingResponse, SheetResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# SQLModel for Drawing (matches Prisma schema)
class Drawing(SQLModel, table=True):
    """Drawing database model."""

    __tablename__ = "drawings"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    project_id: str
    filename: str
    name: str | None = None
    uri: str


class Sheet(SQLModel, table=True):
    """Sheet database model."""

    __tablename__ = "sheets"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    drawing_id: str
    index: int
    uri: str
    title: str | None = None
    sheet_number: str | None = None
    discipline: str | None = None
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSON))


class Block(SQLModel, table=True):
    """Block database model."""

    __tablename__ = "blocks"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: datetime | None = None
    sheet_id: str
    type: str | None = None
    uri: str | None = None
    bounds: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))
    ocr: str | None = None
    description: str | None = None
    metadata_: dict[str, Any] | None = Field(default=None, sa_column=Column("metadata", JSON))


def generate_cuid() -> str:
    """Generate a CUID-like ID."""
    import secrets
    import time

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = secrets.token_hex(8)
    return f"c{timestamp}{random_part}"[:25]


@router.get("/project/{project_id}", response_model=list[DrawingResponse])
async def list_drawings(project_id: str, session: SessionDep, user: OptionalUser = None):
    """List all drawings for a project."""
    statement = select(Drawing).where(
        Drawing.project_id == project_id,
        Drawing.deleted_at.is_(None),
    )
    drawings = session.exec(statement).all()

    return [
        DrawingResponse(
            id=d.id,
            project_id=d.project_id,
            filename=d.filename,
            name=d.name,
            uri=d.uri,
            created_at=d.created_at,
            updated_at=d.updated_at,
        )
        for d in drawings
    ]


@router.post("", response_model=DrawingResponse, status_code=status.HTTP_201_CREATED)
async def create_drawing(
    drawing_data: DrawingCreate,
    session: SessionDep,
    user: CurrentUser,
):
    """Create a new drawing and automatically trigger preprocessing."""
    from api.routes.jobs import Job as JobModel
    
    drawing = Drawing(
        id=generate_cuid(),
        project_id=drawing_data.project_id,
        filename=drawing_data.filename,
        name=drawing_data.name,
        uri=drawing_data.uri,
    )

    session.add(drawing)
    session.commit()
    session.refresh(drawing)
    
    # Create preprocessing job
    job_id = generate_cuid()
    job = JobModel(
        id=job_id,
        project_id=drawing.project_id,
        target_type="drawing",
        target_id=drawing.id,
        type="vision.drawing.preprocess",
        status="Queued",
        payload={"drawing_id": drawing.id},
    )
    session.add(job)
    session.commit()
    
    # Publish preprocessing job to Pub/Sub
    job_payload = {
        "type": "vision.drawing.preprocess",
        "id": job_id,
        "payload": {
            "drawingId": drawing.id,
        },
    }
    
    try:
        logger.info(f"Publishing preprocessing job {job_id} for drawing {drawing.id}")
        pubsub = get_pubsub_client()
        topic_path = pubsub.topic_path(settings.pubsub_project_id, settings.vision_topic)
        
        future = pubsub.publish(
            topic_path,
            json.dumps(job_payload).encode("utf-8"),
            type="vision.drawing.preprocess",
            id=job_id,
        )
        message_id = future.result(timeout=10.0)
        logger.info(f"Successfully published preprocessing job {job_id}, message_id={message_id}")
    except Exception as e:
        logger.error(f"Failed to publish preprocessing job {job_id}: {e}", exc_info=True)
        # Update job status to indicate publish failure
        job.status = "Failed"
        job.events = job.events or []
        job.events.append({
            "type": "failed",
            "event_type": "publish_failed",
            "metadata": {"error": str(e)},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        session.add(job)
        session.commit()

    return DrawingResponse(
        id=drawing.id,
        project_id=drawing.project_id,
        filename=drawing.filename,
        name=drawing.name,
        uri=drawing.uri,
        created_at=drawing.created_at,
        updated_at=drawing.updated_at,
        job_id=job_id,  # Include job_id so frontend can track progress
    )


@router.get("/blocks", response_model=list[BlockResponse])
async def list_all_blocks(session: SessionDep, user: OptionalUser = None, block_type: str | None = None):
    """List all blocks, optionally filtered by type."""
    if block_type:
        statement = select(Block).where(
            Block.deleted_at.is_(None),
            Block.type == block_type,
        )
    else:
        statement = select(Block).where(Block.deleted_at.is_(None))
    blocks = session.exec(statement).all()

    return [
        BlockResponse(
            id=b.id,
            sheet_id=b.sheet_id,
            type=b.type,
            uri=b.uri,
            bounds=b.bounds,
            ocr=b.ocr,
            description=b.description,
            metadata=b.metadata_,
            created_at=b.created_at,
            updated_at=b.updated_at,
        )
        for b in blocks
    ]


@router.get("/{drawing_id}", response_model=DrawingResponse)
async def get_drawing(drawing_id: str, session: SessionDep, user: OptionalUser = None):
    """Get a drawing by ID."""
    drawing = session.get(Drawing, drawing_id)

    if not drawing or drawing.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drawing not found",
        )

    return DrawingResponse(
        id=drawing.id,
        project_id=drawing.project_id,
        filename=drawing.filename,
        name=drawing.name,
        uri=drawing.uri,
        created_at=drawing.created_at,
        updated_at=drawing.updated_at,
    )


@router.get("/{drawing_id}/sheets", response_model=list[SheetResponse])
async def list_sheets(drawing_id: str, session: SessionDep, user: CurrentUser):
    """List all sheets for a drawing."""
    statement = select(Sheet).where(
        Sheet.drawing_id == drawing_id,
        Sheet.deleted_at.is_(None),
    ).order_by(Sheet.index)
    sheets = session.exec(statement).all()

    return [
        SheetResponse(
            id=s.id,
            drawing_id=s.drawing_id,
            index=s.index,
            uri=s.uri,
            title=s.title,
            sheet_number=s.sheet_number,
            discipline=s.discipline,
            metadata=s.metadata_,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in sheets
    ]


@router.get("/sheets/{sheet_id}", response_model=SheetResponse)
async def get_sheet(sheet_id: str, session: SessionDep, user: CurrentUser):
    """Get a sheet by ID."""
    sheet = session.get(Sheet, sheet_id)

    if not sheet or sheet.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sheet not found",
        )

    return SheetResponse(
        id=sheet.id,
        drawing_id=sheet.drawing_id,
        index=sheet.index,
        uri=sheet.uri,
        title=sheet.title,
        sheet_number=sheet.sheet_number,
        discipline=sheet.discipline,
        metadata=sheet.metadata_,
        created_at=sheet.created_at,
        updated_at=sheet.updated_at,
    )


@router.get("/sheets/{sheet_id}/blocks", response_model=list[BlockResponse])
async def list_blocks(sheet_id: str, session: SessionDep, user: OptionalUser = None):
    """List all blocks for a sheet."""
    statement = select(Block).where(
        Block.sheet_id == sheet_id,
        Block.deleted_at.is_(None),
    )
    blocks = session.exec(statement).all()

    return [
        BlockResponse(
            id=b.id,
            sheet_id=b.sheet_id,
            type=b.type,
            uri=b.uri,
            bounds=b.bounds,
            ocr=b.ocr,
            description=b.description,
            metadata=b.metadata_,
            created_at=b.created_at,
            updated_at=b.updated_at,
        )
        for b in blocks
    ]


@router.get("/{drawing_id}/blocks", response_model=list[BlockResponse])
async def list_blocks_by_drawing(drawing_id: str, session: SessionDep, user: OptionalUser = None):
    """List all blocks for a drawing (across all sheets)."""
    # First get all sheets for this drawing
    sheets = session.exec(
        select(Sheet).where(
            Sheet.drawing_id == drawing_id,
            Sheet.deleted_at.is_(None),
        )
    ).all()
    
    sheet_ids = [s.id for s in sheets]
    if not sheet_ids:
        return []
    
    # Get all blocks for these sheets
    statement = select(Block).where(
        Block.sheet_id.in_(sheet_ids),
        Block.deleted_at.is_(None),
    )
    blocks = session.exec(statement).all()

    return [
        BlockResponse(
            id=b.id,
            sheet_id=b.sheet_id,
            type=b.type,
            uri=b.uri,
            bounds=b.bounds,
            ocr=b.ocr,
            description=b.description,
            metadata=b.metadata_,
            created_at=b.created_at,
            updated_at=b.updated_at,
        )
        for b in blocks
    ]


@router.get("/{drawing_id}/status")
async def get_drawing_status(drawing_id: str, session: SessionDep, user: OptionalUser = None):
    """Get the preprocessing status of a drawing.
    
    Status is determined by:
    1. vision.drawing.preprocess job - converts PDF to PNG, creates sheets
    2. vision.sheet.preprocess jobs - extracts blocks from each sheet using Gemini
    
    Status is only 'completed' when ALL jobs are done.
    """
    from api.routes.jobs import Job as JobModel
    
    drawing = session.get(Drawing, drawing_id)
    if not drawing or drawing.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Drawing not found",
        )
    
    # Find the drawing preprocessing job
    drawing_job = session.exec(
        select(JobModel).where(
            JobModel.target_id == drawing_id,
            JobModel.target_type == "drawing",
            JobModel.type == "vision.drawing.preprocess",
        ).order_by(JobModel.created_at.desc())
    ).first()
    
    # Count sheets and blocks
    sheets = session.exec(
        select(Sheet).where(
            Sheet.drawing_id == drawing_id,
            Sheet.deleted_at.is_(None),
        )
    ).all()
    
    sheet_ids = [s.id for s in sheets]
    blocks = []
    
    # Find sheet preprocessing jobs (these extract blocks using Gemini)
    sheet_jobs = []
    if sheet_ids:
        blocks = session.exec(
            select(Block).where(
                Block.sheet_id.in_(sheet_ids),
                Block.deleted_at.is_(None),
            )
        ).all()
        
        # Check if any sheet preprocessing jobs are still running
        sheet_jobs = session.exec(
            select(JobModel).where(
                JobModel.target_id.in_(sheet_ids),
                JobModel.target_type == "sheet",
                JobModel.type == "vision.sheet.preprocess",
            )
        ).all()
    
    status_map = {
        "Queued": "pending",
        "Started": "processing",
        "Completed": "completed",
        "Failed": "failed",
        "Canceled": "failed",
    }
    
    # Determine overall status:
    # - If drawing job is pending/processing -> pending/processing
    # - If drawing job is completed but sheet jobs are still running -> processing
    # - If all jobs are completed -> completed
    # - If any job failed -> failed
    
    overall_status = "pending"
    
    if drawing_job:
        if drawing_job.status in ("Queued", "Started"):
            overall_status = status_map.get(drawing_job.status, "pending")
        elif drawing_job.status in ("Failed", "Canceled"):
            overall_status = "failed"
        elif drawing_job.status == "Completed":
            # Drawing job done, check sheet jobs
            if not sheets:
                overall_status = "completed"  # No sheets = done
            elif not sheet_jobs:
                # Sheets exist but no sheet jobs yet - still processing
                overall_status = "processing"
            else:
                # Check all sheet jobs
                any_running = any(j.status in ("Queued", "Started") for j in sheet_jobs)
                any_failed = any(j.status in ("Failed", "Canceled") for j in sheet_jobs)
                
                if any_failed:
                    overall_status = "failed"
                elif any_running:
                    overall_status = "processing"
                else:
                    overall_status = "completed"
    
    # Calculate progress percentage
    progress = 0
    if drawing_job:
        if drawing_job.status == "Completed":
            progress = 20  # Drawing preprocessing done (20%)
            if sheet_jobs:
                completed_sheets = sum(1 for j in sheet_jobs if j.status == "Completed")
                total_sheets = len(sheet_jobs)
                if total_sheets > 0:
                    # Remaining 80% is for sheet preprocessing
                    progress = 20 + int(80 * completed_sheets / total_sheets)
        elif drawing_job.status == "Started":
            progress = 10
    
    return {
        "drawing_id": drawing_id,
        "status": overall_status,
        "job_id": drawing_job.id if drawing_job else None,
        "sheet_count": len(sheets),
        "block_count": len(blocks),
        "progress": progress,
        "blocks": [
            {
                "id": b.id,
                "type": b.type,
                "description": b.description,
                "uri": b.uri,
            }
            for b in blocks
        ],
    }

