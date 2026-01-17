"""Drawing job handler - converts drawing PDFs into sheets and enqueues sheet jobs."""

import logging
import time
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from clients.pubsub import get_pubsub_client
from clients.storage import StorageClient, get_storage_client
from config import config
from jobs.envelope import JobEnvelope, build_job_envelope
from jobs.types import JobType
from lib.pdf_converter import IndexedPages, convert_pdf_bytes_to_png_bytes
from models import Drawing, Job, JobStatus, Sheet
from utils.id_utils import generate_cuid
from utils.job_events import append_job_event_if_missing, create_job_event
from utils.log_utils import (
    log_coordination_published,
    log_job_completed,
    log_job_started,
    log_pdf_converted,
    log_phase,
    log_storage_download,
    log_storage_upload,
)
from utils.storage_utils import extract_remote_path

logger = logging.getLogger(__name__)


class DrawingJobPayload(BaseModel):
    """Input payload for drawing job messages."""

    model_config = {"extra": "forbid"}

    drawing_id: str = Field(..., description="UUID of the drawing")


def _extract_remote_path(uri: str) -> str:
    return extract_remote_path(uri)


def _download_pdf(
    storage_client: StorageClient,
    uri: str,
    drawing_id: str,
) -> bytes:
    remote_path = _extract_remote_path(uri)
    start = time.time()
    pdf_bytes = storage_client.download_to_bytes(remote_path)
    duration_ms = int((time.time() - start) * 1000)
    log_storage_download(
        logger,
        remote_path,
        size_bytes=len(pdf_bytes),
        duration_ms=duration_ms,
        drawing_id=drawing_id,
    )
    return pdf_bytes


def _validate_pdf_bytes(pdf_bytes: bytes, drawing_id: str) -> None:
    if not pdf_bytes:
        raise ValueError(f"Drawing {drawing_id} PDF is empty")
    # PDF header should start with %PDF- after optional whitespace.
    header = pdf_bytes.lstrip()[:5]
    if header != b"%PDF-":
        snippet = pdf_bytes[:12]
        raise ValueError(
            f"Drawing {drawing_id} is not a valid PDF (header={header!r}, bytes={snippet!r})"
        )


def _upload_sheet_image(
    storage_client: StorageClient,
    drawing_id: str,
    page_index: int,
    png_bytes: bytes,
) -> str:
    remote_path = f"sheets/{drawing_id}/sheet_{page_index}.png"
    start = time.time()
    uri = storage_client.upload_from_bytes(
        png_bytes,
        remote_path,
        content_type="image/png",
    )
    duration_ms = int((time.time() - start) * 1000)
    log_storage_upload(logger, remote_path, size_bytes=len(png_bytes), duration_ms=duration_ms)
    return uri


def _upsert_sheets(
    session: Session,
    drawing_id: str,
    indexed_pages: IndexedPages,
    storage_client: StorageClient,
) -> list[Sheet]:
    existing = session.exec(
        select(Sheet).where(Sheet.drawing_id == drawing_id, Sheet.deleted_at.is_(None))
    ).all()
    existing_by_index = {sheet.index: sheet for sheet in existing}

    sheets: list[Sheet] = []
    for index in indexed_pages.indices:
        png_bytes = indexed_pages[index]
        uri = _upload_sheet_image(storage_client, drawing_id, index, png_bytes)
        sheet = existing_by_index.get(index)
        if sheet:
            sheet.uri = uri
            sheet.updated_at = datetime.now(UTC)
            session.add(sheet)
        else:
            sheet = Sheet(
                id=generate_cuid(),
                drawing_id=drawing_id,
                index=index,
                uri=uri,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(sheet)
        sheets.append(sheet)

    session.commit()
    for sheet in sheets:
        session.refresh(sheet)
    return sheets


def _create_sheet_jobs(
    session: Session,
    *,
    sheets: list[Sheet],
    drawing_id: str,
    drawing_job: Job,
) -> list[Job]:
    """Create sheet preprocessing jobs, skipping sheets that already have active jobs.
    
    This prevents duplicate jobs from being created if the drawing job is retried
    or if sheets are re-processed.
    """
    jobs: list[Job] = []
    for sheet in sheets:
        # Check if a job already exists for this sheet
        existing_job = session.exec(
            select(Job).where(
                Job.target_id == sheet.id,
                Job.target_type == "sheet",
                Job.type == JobType.SHEET_PREPROCESS,
            ).order_by(Job.created_at.desc())
        ).first()
        
        # Skip if job already exists and is in a non-terminal state
        if existing_job and existing_job.status in (JobStatus.QUEUED, JobStatus.STARTED, JobStatus.COMPLETED):
            logger.info(
                f"[job.skip.duplicate] Sheet {sheet.id} already has a {existing_job.status.value} job "
                f"({existing_job.id}), skipping creation"
            )
            jobs.append(existing_job)
            continue
        
        # Create new job if no existing job or if existing job is in terminal failure state
        job_id = generate_cuid()
        job = Job(
            id=job_id,
            type=JobType.SHEET_PREPROCESS,
            status=JobStatus.QUEUED,
            organization_id=drawing_job.organization_id,
            project_id=drawing_job.project_id,
            actor_id=drawing_job.actor_id,
            target_type="sheet",
            target_id=sheet.id,
            payload={"sheetId": sheet.id, "drawingId": drawing_id},
            events=[
                create_job_event(
                    job_type=JobType.SHEET_PREPROCESS,
                    job_id=str(job_id),
                    status=JobStatus.QUEUED.value,
                    event_type="created",
                    sheet_id=sheet.id,
                    drawing_id=drawing_id,
                )
            ],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(job)
        jobs.append(job)
        logger.info(
            f"[job.created] Created new sheet preprocessing job {job_id} for sheet {sheet.id}"
        )
    
    session.commit()
    for job in jobs:
        session.refresh(job)
    return jobs


def run_drawing_job(
    session: Session,
    payload: DrawingJobPayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    storage_client = get_storage_client()
    pubsub_client = get_pubsub_client()

    start_time = log_job_started(
        logger,
        JobType.DRAWING_PREPROCESS,
        message_id or "",
        job_id=str(envelope.job_id),
    )

    drawing = session.get(Drawing, payload.drawing_id)
    if not drawing:
        raise ValueError(f"Drawing {payload.drawing_id} not found")
    if drawing.deleted_at is not None:
        raise ValueError(f"Drawing {payload.drawing_id} has been deleted")
    if not drawing.uri:
        raise ValueError(f"Drawing {payload.drawing_id} is missing URI")

    drawing_job = session.get(Job, envelope.job_id)
    if not drawing_job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if drawing_job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] drawing job {drawing_job.id} canceled before start")
        return

    if drawing_job.status == JobStatus.QUEUED:
        drawing_job.status = JobStatus.STARTED
        drawing_job.updated_at = datetime.now(UTC)

    started_event = create_job_event(
        job_type=drawing_job.type,
        job_id=str(drawing_job.id),
        status=drawing_job.status.value,
        event_type="started",
        drawing_id=payload.drawing_id,
    )
    updated_events = append_job_event_if_missing(drawing_job.events, started_event)
    should_commit = False
    if updated_events is not drawing_job.events:
        drawing_job.events = updated_events
        should_commit = True
    if drawing_job.status == JobStatus.STARTED:
        should_commit = True
    if should_commit:
        drawing_job.updated_at = datetime.now(UTC)
        session.add(drawing_job)
        session.commit()

    indexed_pages = IndexedPages(pages=[])
    sheet_jobs: list[Job] = []
    sheets: list[Sheet] = []
    try:
        with log_phase(logger, "Download PDF", drawing_id=payload.drawing_id):
            pdf_bytes = _download_pdf(storage_client, drawing.uri, payload.drawing_id)
            _validate_pdf_bytes(pdf_bytes, payload.drawing_id)

        with log_phase(logger, "Convert PDF to PNG", drawing_id=payload.drawing_id):
            conversion_start = time.time()
            indexed_pages = convert_pdf_bytes_to_png_bytes(
                pdf_bytes=pdf_bytes,
                dpi=config.pdf_conversion_dpi,
            )
            conversion_ms = int((time.time() - conversion_start) * 1000)
            if indexed_pages.page_count > 0:
                log_pdf_converted(
                    logger,
                    indexed_pages.page_count,
                    conversion_ms,
                    drawing_id=payload.drawing_id,
                )

        with log_phase(logger, "Upload sheets", drawing_id=payload.drawing_id):
            sheets = _upsert_sheets(session, payload.drawing_id, indexed_pages, storage_client)
            sheet_jobs = _create_sheet_jobs(
                session,
                sheets=sheets,
                drawing_id=payload.drawing_id,
                drawing_job=drawing_job,
            )

        with log_phase(logger, "Publish sheet jobs", drawing_id=payload.drawing_id):
            for job, sheet in zip(sheet_jobs, sheets):
                # Always publish Queued jobs, even if they're duplicates
                # This ensures jobs that were created but never published get into the queue
                if job.status == JobStatus.QUEUED:
                    pubsub_client.publish(
                        config.vision_topic,
                        build_job_envelope(
                            job_type=job.type,
                            job_id=str(job.id),
                            payload={"sheetId": sheet.id, "drawingId": payload.drawing_id},
                        ),
                        attributes={"type": job.type, "id": str(job.id)},
                    )

        log_coordination_published(
            logger,
            config.vision_topic,
            len(sheet_jobs),
            drawing_id=payload.drawing_id,
        )

        drawing_job.status = JobStatus.COMPLETED
        drawing_job.updated_at = datetime.now(UTC)
        completed_event = create_job_event(
            job_type=drawing_job.type,
            job_id=str(drawing_job.id),
            status=JobStatus.COMPLETED.value,
            event_type="completed",
            drawing_id=payload.drawing_id,
        )
        drawing_job.events = append_job_event_if_missing(drawing_job.events, completed_event)
        session.add(drawing_job)
        session.commit()
    except Exception:
        session.rollback()
        drawing_job.status = JobStatus.FAILED
        drawing_job.updated_at = datetime.now(UTC)
        failed_event = create_job_event(
            job_type=drawing_job.type,
            job_id=str(drawing_job.id),
            status=JobStatus.FAILED.value,
            event_type="failed",
            drawing_id=payload.drawing_id,
        )
        drawing_job.events = append_job_event_if_missing(drawing_job.events, failed_event)
        session.add(drawing_job)
        session.commit()
        raise

    log_job_completed(
        logger,
        JobType.DRAWING_PREPROCESS,
        message_id or "",
        start_time,
        drawing_id=payload.drawing_id,
        job_id=str(envelope.job_id),
        pages_total=len(indexed_pages),
        pages_new=len(indexed_pages),
        pages_existing=0,
    )
