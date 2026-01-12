"""Job routes for tracking processing status."""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, SQLModel, select

from api.dependencies import CurrentUser, SessionDep
from api.schemas.job import JobCreate, JobResponse, JobStatus

router = APIRouter()


# SQLModel for Job (matches Prisma schema)
class Job(SQLModel, table=True):
    """Job database model."""

    __tablename__ = "jobs"

    id: str = Field(primary_key=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    project_id: str | None = None
    parent_id: str | None = None
    target_type: str
    target_id: str
    type: str
    status: str = "Queued"
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    events: list[dict[str, Any]] | None = Field(default=None, sa_column=Column(JSON))


def generate_cuid() -> str:
    """Generate a CUID-like ID."""
    import secrets
    import time

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = secrets.token_hex(8)
    return f"c{timestamp}{random_part}"[:25]


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    session: SessionDep,
    user: CurrentUser,
    project_id: str | None = None,
    status_filter: str | None = None,
    limit: int = 50,
):
    """List jobs with optional filters."""
    statement = select(Job)

    if project_id:
        statement = statement.where(Job.project_id == project_id)
    if status_filter:
        statement = statement.where(Job.status == status_filter)

    statement = statement.order_by(Job.created_at.desc()).limit(limit)
    jobs = session.exec(statement).all()

    return [
        JobResponse(
            id=j.id,
            type=j.type,
            status=_map_status(j.status),
            project_id=j.project_id,
            parent_id=j.parent_id,
            target_type=j.target_type,
            target_id=j.target_id,
            payload=j.payload,
            events=j.events or [],
            created_at=j.created_at,
            updated_at=j.updated_at,
        )
        for j in jobs
    ]


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, session: SessionDep, user: CurrentUser):
    """Get a job by ID."""
    job = session.get(Job, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    return JobResponse(
        id=job.id,
        type=job.type,
        status=_map_status(job.status),
        project_id=job.project_id,
        parent_id=job.parent_id,
        target_type=job.target_type,
        target_id=job.target_id,
        payload=job.payload,
        events=job.events or [],
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, session: SessionDep, user: CurrentUser):
    """Cancel a job."""
    job = session.get(Job, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if job.status in ["Completed", "Failed", "Canceled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel job with status: {job.status}",
        )

    job.status = "Canceled"
    job.updated_at = datetime.now(timezone.utc)
    session.add(job)
    session.commit()
    session.refresh(job)

    return JobResponse(
        id=job.id,
        type=job.type,
        status=_map_status(job.status),
        project_id=job.project_id,
        parent_id=job.parent_id,
        target_type=job.target_type,
        target_id=job.target_id,
        payload=job.payload,
        events=job.events or [],
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# WebSocket for real-time job updates
connected_clients: dict[str, list[WebSocket]] = {}


@router.websocket("/ws/{job_id}")
async def job_status_websocket(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time job status updates."""
    await websocket.accept()

    # Add to connected clients
    if job_id not in connected_clients:
        connected_clients[job_id] = []
    connected_clients[job_id].append(websocket)

    try:
        while True:
            # Keep connection alive and wait for messages
            data = await websocket.receive_text()
            # Echo back any received data (for ping/pong)
            await websocket.send_text(f"Received: {data}")
    except WebSocketDisconnect:
        # Remove from connected clients
        if job_id in connected_clients:
            connected_clients[job_id].remove(websocket)
            if not connected_clients[job_id]:
                del connected_clients[job_id]


async def broadcast_job_update(job_id: str, status: str, data: dict):
    """Broadcast job update to all connected clients."""
    if job_id in connected_clients:
        message = {"job_id": job_id, "status": status, **data}
        for websocket in connected_clients[job_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                pass  # Client disconnected


def _map_status(db_status: str) -> JobStatus:
    """Map database status to API status enum."""
    mapping = {
        "Queued": JobStatus.QUEUED,
        "Started": JobStatus.STARTED,
        "Completed": JobStatus.COMPLETED,
        "Failed": JobStatus.FAILED,
        "Canceled": JobStatus.CANCELED,
    }
    return mapping.get(db_status, JobStatus.QUEUED)

