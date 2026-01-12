"""Compute clashes job handler (stub)."""

import logging
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlmodel import Session

from jobs.envelope import JobEnvelope
from jobs.overlay_reports import (
    build_clash_report,
    extract_regions,
    load_overlay_images,
    resolve_overlay_for_job,
)
from jobs.types import JobType
from models import Job, JobStatus
from utils.job_events import append_job_event_if_missing, create_job_event
from utils.log_utils import log_job_completed, log_job_started

logger = logging.getLogger(__name__)


class ComputeClashesPayload(BaseModel):
    """Input payload for compute clashes job messages."""

    model_config = {"extra": "forbid"}

    overlay_job_id: str | None = None
    block_overlay_job_id: str | None = None
    sheet_overlay_job_id: str | None = None
    drawing_overlay_job_id: str | None = None
    overlay_id: str | None = None


def run_compute_clashes_job(
    session: Session,
    payload: ComputeClashesPayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    overlay_job_id = resolve_overlay_job_id(payload)
    start_time = log_job_started(
        logger,
        JobType.OVERLAY_CLASH_DETECT,
        message_id or "",
        job_id=overlay_job_id,
    )
    job = session.get(Job, envelope.job_id)
    if not job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] compute clashes job {job.id} canceled before start")
        return

    if job.status == JobStatus.QUEUED:
        job.status = JobStatus.STARTED
        job.updated_at = datetime.now(UTC)

    started_metadata = {"overlayJobId": overlay_job_id}
    if payload.overlay_id:
        started_metadata["overlayId"] = payload.overlay_id
    started_event = create_job_event(
        job_type=job.type,
        job_id=str(job.id),
        status=job.status.value,
        event_type="started",
        metadata=started_metadata,
    )
    job.events = append_job_event_if_missing(job.events, started_event)
    session.add(job)
    session.commit()

    try:
        overlay = resolve_overlay_for_job(session, overlay_job_id, overlay_id=payload.overlay_id)
        if not overlay:
            raise ValueError("Overlay not found for overlay job")

        images = load_overlay_images(overlay, logger=logger)
        addition_items = extract_regions(images["addition"], label="Addition")
        deletion_items = extract_regions(images["deletion"], label="Deletion")
        clash_items = [
            {
                **item,
                "description": f"Potential clash ({item.get('description')})",
            }
            for item in [*addition_items, *deletion_items]
        ]

        report = build_clash_report(
            overlay_id=str(overlay.id),
            clash_items=clash_items,
            overlay_uri=overlay.uri,
            addition_uri=overlay.addition_uri,
            deletion_uri=overlay.deletion_uri,
        )

        existing_reports = overlay.clashes or []
        overlay.clashes = [*existing_reports, report]
        overlay.updated_at = datetime.now(UTC)
        session.add(overlay)
        session.commit()

        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.now(UTC)
        completed_event = create_job_event(
            job_type=job.type,
            job_id=str(job.id),
            status=JobStatus.COMPLETED.value,
            event_type="completed",
            metadata={
                "overlayJobId": overlay_job_id,
                "overlayId": str(overlay.id),
                "clashCount": len(report["clashes"]),
            },
        )
        job.events = append_job_event_if_missing(job.events, completed_event)
        session.add(job)
        session.commit()
        log_job_completed(
            logger,
            JobType.OVERLAY_CLASH_DETECT,
            message_id or "",
            start_time,
            job_id=overlay_job_id,
        )
    except Exception as error:
        _fail_job(
            session,
            job,
            overlay_job_id=overlay_job_id,
            overlay_id=payload.overlay_id,
            error=error,
        )
        raise


def resolve_overlay_job_id(payload: ComputeClashesPayload) -> str:
    for value in (
        payload.overlay_job_id,
        payload.block_overlay_job_id,
        payload.sheet_overlay_job_id,
        payload.drawing_overlay_job_id,
        payload.overlay_id,
    ):
        if isinstance(value, str) and value:
            return value
    raise ValueError("Compute clashes job missing overlay identifier")


def _fail_job(
    session: Session,
    job: Job,
    *,
    overlay_job_id: str,
    overlay_id: str | None,
    error: Exception,
) -> None:
    session.rollback()
    job.status = JobStatus.FAILED
    job.updated_at = datetime.now(UTC)
    failed_metadata = {
        "overlayJobId": overlay_job_id,
        "errorType": type(error).__name__,
        "errorMessage": str(error),
    }
    if overlay_id:
        failed_metadata["overlayId"] = overlay_id
    failed_event = create_job_event(
        job_type=job.type,
        job_id=str(job.id),
        status=JobStatus.FAILED.value,
        event_type="failed",
        metadata=failed_metadata,
    )
    job.events = append_job_event_if_missing(job.events, failed_event)
    session.add(job)
    session.commit()
