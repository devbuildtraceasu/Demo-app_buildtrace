"""Sheet job handler - analyzes sheets into blocks and metadata."""

import logging
import time
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from clients.gemini import get_gemini_client
from clients.storage import StorageClient, get_storage_client
from jobs.envelope import JobEnvelope
from jobs.types import JobType
from lib.llm_usage import start_tracking, stop_tracking
from lib.sheet_analyzer import SheetAnalysisResult, analyze_sheet
from models import Block, BlockType, Job, JobStatus, Sheet
from utils.id_utils import generate_cuid
from utils.job_events import append_job_event_if_missing, create_job_event
from utils.log_utils import (
    log_job_completed,
    log_job_started,
    log_phase,
    log_storage_download,
    log_storage_upload,
)
from utils.storage_utils import extract_remote_path

logger = logging.getLogger(__name__)


class SheetJobPayload(BaseModel):
    """Input payload for sheet job messages."""

    model_config = {"extra": "forbid"}

    sheet_id: str = Field(..., description="UUID of the sheet")
    drawing_id: str | None = Field(default=None, description="UUID of the drawing")


def _extract_remote_path(uri: str) -> str:
    return extract_remote_path(uri)


def _download_sheet_image(storage_client: StorageClient, uri: str, sheet_id: str) -> bytes:
    remote_path = _extract_remote_path(uri)
    start = time.time()
    data = storage_client.download_to_bytes(remote_path)
    duration_ms = int((time.time() - start) * 1000)
    log_storage_download(
        logger,
        remote_path,
        size_bytes=len(data),
        duration_ms=duration_ms,
        sheet_id=sheet_id,
    )
    return data


def _upload_block_image(
    storage_client: StorageClient,
    sheet_id: str,
    index: int,
    block_type: str,
    data: bytes,
) -> str:
    safe_type = block_type.replace("/", "_")
    remote_path = f"blocks/{sheet_id}/block_{index}_{safe_type}.png"
    start = time.time()
    uri = storage_client.upload_from_bytes(data, remote_path, content_type="image/png")
    duration_ms = int((time.time() - start) * 1000)
    log_storage_upload(logger, remote_path, size_bytes=len(data), duration_ms=duration_ms)
    return uri


def _map_block_type(block_type: str) -> BlockType:
    mapping = {
        "plan": BlockType.PLAN,
        "elevation": BlockType.ELEVATION,
        "section": BlockType.SECTION,
        "detail": BlockType.DETAIL,
        "legend": BlockType.LEGEND,
        "diagram": BlockType.DIAGRAM,
        "key_plan": BlockType.KEY_PLAN,
        "north_arrow": BlockType.NORTH_ARROW,
        "schedule": BlockType.SCHEDULE,
        "revision_history": BlockType.REVISION_HISTORY,
        "project_info": BlockType.PROJECT_INFO,
        "general_notes": BlockType.GENERAL_NOTES,
        "key_notes": BlockType.KEY_NOTES,
        "sheet_notes": BlockType.SHEET_NOTES,
        "abbreviations": BlockType.ABBREVIATIONS,
        "code_references": BlockType.CODE_REFERENCES,
        "notes": BlockType.NOTES,
        "title_block": BlockType.TITLE_BLOCK,
        "consultants": BlockType.CONSULTANTS,
        "seals": BlockType.SEALS,
    }
    return mapping.get(block_type, BlockType.PLAN)


def _soft_delete_existing_blocks(session: Session, sheet_id: str) -> None:
    existing = session.exec(
        select(Block).where(Block.sheet_id == sheet_id, Block.deleted_at.is_(None))
    ).all()
    if not existing:
        return
    now = datetime.now(UTC)
    for block in existing:
        block.deleted_at = now
        block.updated_at = now
        session.add(block)
    session.commit()


def _apply_sheet_metadata(sheet: Sheet, analysis: SheetAnalysisResult) -> None:
    sheet.metadata_ = analysis.metadata
    title_block = analysis.metadata.get("title_block") if analysis.metadata else None
    if isinstance(title_block, dict):
        sheet.sheet_number = title_block.get("sheet_number") or sheet.sheet_number
        sheet.title = title_block.get("sheet_title") or sheet.title
    sheet.updated_at = datetime.now(UTC)


def run_sheet_job(
    session: Session,
    payload: SheetJobPayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    client = get_gemini_client()
    storage_client = get_storage_client()

    start_time = log_job_started(
        logger,
        JobType.SHEET_PREPROCESS,
        message_id or "",
        job_id=str(envelope.job_id),
    )

    sheet = session.get(Sheet, payload.sheet_id)
    if not sheet:
        raise ValueError(f"Sheet {payload.sheet_id} not found")
    if sheet.deleted_at is not None:
        raise ValueError(f"Sheet {payload.sheet_id} has been deleted")
    if not sheet.uri:
        raise ValueError(f"Sheet {payload.sheet_id} is missing URI")

    sheet_job = session.get(Job, envelope.job_id)
    if not sheet_job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if sheet_job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] sheet job {sheet_job.id} canceled before start")
        return

    if sheet_job.status == JobStatus.QUEUED:
        sheet_job.status = JobStatus.STARTED
        sheet_job.updated_at = datetime.now(UTC)

    started_event = create_job_event(
        job_type=sheet_job.type,
        job_id=str(sheet_job.id),
        status=sheet_job.status.value,
        event_type="started",
        sheet_id=payload.sheet_id,
    )
    updated_events = append_job_event_if_missing(sheet_job.events, started_event)
    should_commit = False
    if updated_events is not sheet_job.events:
        sheet_job.events = updated_events
        should_commit = True
    if sheet_job.status == JobStatus.STARTED:
        should_commit = True
    if should_commit:
        sheet_job.updated_at = datetime.now(UTC)
        session.add(sheet_job)
        session.commit()

    # Start LLM usage tracking for this job
    start_tracking()

    try:
        with log_phase(logger, "Download sheet image", sheet_id=payload.sheet_id):
            png_bytes = _download_sheet_image(storage_client, sheet.uri, payload.sheet_id)

        with log_phase(logger, "Analyze sheet", sheet_id=payload.sheet_id):
            analysis = analyze_sheet(png_bytes, client)

        with log_phase(logger, "Upload blocks", sheet_id=payload.sheet_id):
            _soft_delete_existing_blocks(session, sheet.id)

            new_blocks: list[Block] = []
            for index, block in enumerate(analysis.blocks):
                block_uri = _upload_block_image(
                    storage_client,
                    sheet.id,
                    index,
                    block.block_type,
                    block.crop_bytes,
                )
                metadata = {
                    "name": block.name,
                    "storage_type": block.storage_type,
                    "identifier": block.identifier,
                    "has_grid_callouts": block.has_grid_callouts,
                }
                new_blocks.append(
                    Block(
                        id=generate_cuid(),
                        sheet_id=sheet.id,
                        type=_map_block_type(block.block_type),
                        uri=block_uri,
                        bounds={
                            "xmin": block.bbox.xmin,
                            "ymin": block.bbox.ymin,
                            "xmax": block.bbox.xmax,
                            "ymax": block.bbox.ymax,
                            "normalized": True,
                        },
                        ocr=block.ocr_text,
                        description=block.description,
                        metadata_=metadata,
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )

            for block in new_blocks:
                session.add(block)

            _apply_sheet_metadata(sheet, analysis)
            session.add(sheet)

        # Stop tracking and get LLM usage
        llm_usage = stop_tracking()
        llm_usage_dict = (
            llm_usage.to_event_dict() if llm_usage and not llm_usage.is_empty() else None
        )

        sheet_job.status = JobStatus.COMPLETED
        sheet_job.updated_at = datetime.now(UTC)
        completed_event = create_job_event(
            job_type=sheet_job.type,
            job_id=str(sheet_job.id),
            status=JobStatus.COMPLETED.value,
            event_type="completed",
            sheet_id=payload.sheet_id,
            llm_usage=llm_usage_dict,
        )
        sheet_job.events = append_job_event_if_missing(sheet_job.events, completed_event)
        session.add(sheet_job)

        session.commit()
    except Exception:
        # Stop tracking and get LLM usage (even on failure)
        llm_usage = stop_tracking()
        llm_usage_dict = (
            llm_usage.to_event_dict() if llm_usage and not llm_usage.is_empty() else None
        )

        session.rollback()
        sheet_job.status = JobStatus.FAILED
        sheet_job.updated_at = datetime.now(UTC)
        failed_event = create_job_event(
            job_type=sheet_job.type,
            job_id=str(sheet_job.id),
            status=JobStatus.FAILED.value,
            event_type="failed",
            sheet_id=payload.sheet_id,
            llm_usage=llm_usage_dict,
        )
        sheet_job.events = append_job_event_if_missing(sheet_job.events, failed_event)
        session.add(sheet_job)
        session.commit()
        raise

    log_job_completed(
        logger,
        JobType.SHEET_PREPROCESS,
        message_id or "",
        start_time,
        sheet_id=payload.sheet_id,
        job_id=str(envelope.job_id),
    )
