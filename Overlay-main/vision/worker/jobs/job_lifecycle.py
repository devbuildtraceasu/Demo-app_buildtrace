"""Shared lifecycle helpers for stub jobs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session

from models import Job, JobStatus
from utils.job_events import append_job_event_if_missing
from utils.log_utils import log_job_completed, log_job_started

EventBuilder = Callable[[str, str, dict[str, Any] | None], dict[str, Any]]
MetadataBuilder = Callable[[str, dict[str, Any] | None], dict[str, Any] | None]
PrepareMetadata = Callable[[], dict[str, Any] | None]


def run_stub_job(
    session: Session,
    *,
    logger,
    job_type: str,
    message_id: str | None,
    job_id: str,
    build_event: EventBuilder,
    build_metadata: MetadataBuilder | None = None,
    prepare_metadata: PrepareMetadata | None = None,
    cancel_log_label: str,
    log_context: dict[str, str | None] | None = None,
) -> None:
    start_time = log_job_started(
        logger,
        job_type,
        message_id or "",
        **{"job_id": job_id, **(log_context or {})},
    )

    job = session.get(Job, job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    if job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] {cancel_log_label} job {job.id} canceled before start")
        return

    if job.status == JobStatus.QUEUED:
        job.status = JobStatus.STARTED
        job.updated_at = datetime.now(UTC)

    base_metadata = prepare_metadata() if prepare_metadata else None
    started_metadata = build_metadata("started", base_metadata) if build_metadata else base_metadata
    started_event = build_event("started", job.status.value, started_metadata)
    job.events = append_job_event_if_missing(job.events, started_event)
    session.add(job)
    session.commit()

    try:
        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.now(UTC)
        completed_metadata = (
            build_metadata("completed", base_metadata) if build_metadata else base_metadata
        )
        completed_event = build_event("completed", JobStatus.COMPLETED.value, completed_metadata)
        job.events = append_job_event_if_missing(job.events, completed_event)
        session.add(job)
        session.commit()
    except Exception:
        session.rollback()
        job.status = JobStatus.FAILED
        job.updated_at = datetime.now(UTC)
        failed_metadata = (
            build_metadata("failed", base_metadata) if build_metadata else base_metadata
        )
        failed_event = build_event("failed", JobStatus.FAILED.value, failed_metadata)
        job.events = append_job_event_if_missing(job.events, failed_event)
        session.add(job)
        session.commit()
        raise

    log_job_completed(
        logger,
        job_type,
        message_id or "",
        start_time,
        **{"job_id": job_id, **(log_context or {})},
    )
