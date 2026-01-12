"""Drawing overlay generation job handler.

This module handles the generation of overlay jobs between two drawings by
matching sheets by their sheet_number field (case-insensitive).
"""

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from clients.pubsub import get_pubsub_client
from config import config
from jobs.envelope import JobEnvelope, build_job_envelope
from jobs.types import JobType
from models import Drawing, Job, JobStatus, Sheet
from utils.id_utils import generate_cuid
from utils.job_events import append_job_event_if_missing, create_job_event
from utils.log_utils import log_coordination_published, log_job_completed, log_job_started

logger = logging.getLogger(__name__)


class DrawingOverlayGeneratePayload(BaseModel):
    """Input payload for drawing overlay generation job messages."""

    model_config = {"extra": "forbid"}

    drawing_a_id: str = Field(..., description="UUID of the source drawing")
    drawing_b_id: str = Field(..., description="UUID of the target drawing")


class SheetMatchingStats(BaseModel):
    """Statistics for sheet matching by sheet_number."""

    sheets_matched_by_number: int = 0
    sheets_skipped_no_number: int = 0
    sheets_skipped_no_match: int = 0


def _get_sheet_number(sheet: Sheet) -> str | None:
    """Extract normalized sheet number from a sheet.

    Args:
        sheet: Sheet to extract number from

    Returns:
        Normalized sheet number (lowercase, stripped) or None if not present
    """
    if sheet.sheet_number and isinstance(sheet.sheet_number, str):
        stripped = sheet.sheet_number.strip()
        if stripped:
            return stripped.lower()
    return None


def _build_sheet_number_map(sheets: list[Sheet]) -> dict[str, Sheet]:
    """Build a lookup map from sheet_number.lower() to sheet.

    Only includes sheets that have a valid sheet_number.

    Args:
        sheets: List of sheets to build map from

    Returns:
        Dict mapping sheet_number (lowercase) to Sheet
    """
    sheet_map: dict[str, Sheet] = {}
    for sheet in sheets:
        number = _get_sheet_number(sheet)
        if number and sheet.id:
            # First sheet with this number wins (no duplicates)
            if number not in sheet_map:
                sheet_map[number] = sheet
            else:
                logger.warning(
                    "[overlay.sheet_number.duplicate] sheet_number=%s sheet_id=%s "
                    "already_mapped_to=%s",
                    number,
                    sheet.id,
                    sheet_map[number].id,
                )
    return sheet_map


def _pair_sheets_by_number(
    sheets_a: list[Sheet],
    sheets_b: list[Sheet],
) -> tuple[list[tuple[Sheet, Sheet, str]], SheetMatchingStats]:
    """Pair sheets between two drawings by sheet_number (case-insensitive).

    Args:
        sheets_a: Sheets from drawing A (source/old)
        sheets_b: Sheets from drawing B (target/new)

    Returns:
        Tuple of (paired_sheets, stats) where:
        - paired_sheets: List of (sheet_a, sheet_b, "number") tuples
        - stats: SheetMatchingStats with matching statistics
    """
    stats = SheetMatchingStats()
    paired: list[tuple[Sheet, Sheet, str]] = []

    # Build sheet_number map for drawing A
    sheet_map_a = _build_sheet_number_map(sheets_a)

    # Iterate sheets in B and match to A
    for sheet_b in sheets_b:
        if not sheet_b.id:
            continue

        number = _get_sheet_number(sheet_b)
        if not number:
            stats.sheets_skipped_no_number += 1
            logger.info(
                "[overlay.sheet.no_number] sheet_id=%s drawing_id=%s",
                sheet_b.id,
                sheet_b.drawing_id,
            )
            continue

        # Look up matching sheet in A
        sheet_a = sheet_map_a.get(number)
        if not sheet_a or not sheet_a.id:
            stats.sheets_skipped_no_match += 1
            logger.info(
                "[overlay.sheet.no_match] sheet_id=%s sheet_number=%s",
                sheet_b.id,
                number,
            )
            continue

        # Found a match
        paired.append((sheet_a, sheet_b, "number"))
        stats.sheets_matched_by_number += 1
        logger.info(
            "[overlay.sheet.matched] sheet_a_id=%s sheet_b_id=%s sheet_number=%s",
            sheet_a.id,
            sheet_b.id,
            number,
        )

    return paired, stats


def _sheet_sort_key(sheet: Sheet) -> tuple:
    if sheet.sheet_number:
        return (0, sheet.sheet_number.lower())
    return (1, sheet.index, sheet.id or "")


def _sheet_title(sheet: Sheet) -> str | None:
    title = sheet.title
    if isinstance(title, str) and title.strip():
        return title.strip().lower()
    return None


def _sheet_discipline(sheet: Sheet) -> str | None:
    discipline = sheet.discipline
    if isinstance(discipline, str) and discipline.strip():
        return discipline.strip().lower()
    return None


def _normalize_sheet_key(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def _pair_sheets(
    sheets_a: list[Sheet],
    sheets_b: list[Sheet],
) -> list[tuple[Sheet, Sheet, str]]:
    paired: list[tuple[Sheet, Sheet, str]] = []
    used_a: set[str] = set()
    used_b: set[str] = set()

    indexed_b = {}
    for sheet in sheets_b:
        if not sheet.sheet_number:
            continue
        key = _normalize_sheet_key(sheet.sheet_number)
        if key:
            indexed_b[key] = sheet
    for sheet_a in sheets_a:
        if not sheet_a.sheet_number:
            continue
        key = _normalize_sheet_key(sheet_a.sheet_number)
        sheet_b = indexed_b.get(key)
        if not sheet_b or not sheet_a.id or not sheet_b.id:
            continue
        paired.append((sheet_a, sheet_b, "number"))
        used_a.add(sheet_a.id)
        used_b.add(sheet_b.id)

    title_b = {_sheet_title(sheet): sheet for sheet in sheets_b if _sheet_title(sheet)}
    for sheet_a in sheets_a:
        if sheet_a.id in used_a:
            continue
        title = _sheet_title(sheet_a)
        if not title:
            continue
        sheet_b = title_b.get(title)
        if not sheet_b or not sheet_b.id or sheet_b.id in used_b:
            continue
        paired.append((sheet_a, sheet_b, "title"))
        used_a.add(sheet_a.id)
        used_b.add(sheet_b.id)

    discipline_b: dict[str, list[Sheet]] = {}
    for sheet in sheets_b:
        discipline = _sheet_discipline(sheet)
        if not discipline:
            continue
        discipline_b.setdefault(discipline, []).append(sheet)

    for sheet_a in sheets_a:
        if sheet_a.id in used_a:
            continue
        discipline = _sheet_discipline(sheet_a)
        if not discipline:
            continue
        candidates = discipline_b.get(discipline, [])
        candidates = [sheet for sheet in candidates if sheet.id not in used_b]
        if not candidates:
            continue
        candidates.sort(key=_sheet_sort_key)
        sheet_b = candidates[0]
        if not sheet_b.id:
            continue
        paired.append((sheet_a, sheet_b, "discipline"))
        used_a.add(sheet_a.id)
        used_b.add(sheet_b.id)

    remaining_a = [sheet for sheet in sheets_a if sheet.id not in used_a]
    remaining_b = [sheet for sheet in sheets_b if sheet.id not in used_b]
    for sheet_a, sheet_b in zip(
        sorted(remaining_a, key=_sheet_sort_key),
        sorted(remaining_b, key=_sheet_sort_key),
    ):
        if not sheet_a.id or not sheet_b.id:
            continue
        if sheet_a.discipline and sheet_b.discipline and sheet_a.discipline != sheet_b.discipline:
            continue
        paired.append((sheet_a, sheet_b, "order"))

    return paired


def run_drawing_overlay_generate_job(
    session: Session,
    payload: DrawingOverlayGeneratePayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    job_type = JobType.DRAWING_OVERLAY_GENERATE

    job = session.get(Job, envelope.job_id)
    if not job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] drawing overlay job {job.id} canceled before start")
        return

    drawing_a = session.get(Drawing, payload.drawing_a_id)
    drawing_b = session.get(Drawing, payload.drawing_b_id)
    if not drawing_a or not drawing_b:
        raise ValueError("Drawings not found for overlay generation")

    start_time = log_job_started(
        logger,
        job_type,
        message_id or "",
        job_id=str(envelope.job_id),
    )

    if job.status == JobStatus.QUEUED:
        job.status = JobStatus.STARTED
        job.updated_at = datetime.now(UTC)

    started_event = create_job_event(
        job_type=job.type,
        job_id=str(job.id),
        status=job.status.value,
        event_type="started",
        metadata={
            "drawingAId": payload.drawing_a_id,
            "drawingBId": payload.drawing_b_id,
        },
    )
    job.events = append_job_event_if_missing(job.events, started_event)
    session.add(job)
    session.commit()

    pubsub_client = get_pubsub_client()

    sheets_a = session.exec(
        select(Sheet).where(
            Sheet.drawing_id == payload.drawing_a_id,
            Sheet.deleted_at.is_(None),
        )
    ).all()
    sheets_b = session.exec(
        select(Sheet).where(
            Sheet.drawing_id == payload.drawing_b_id,
            Sheet.deleted_at.is_(None),
        )
    ).all()

    # Use sheet number matching (US4: FR-012, FR-013, FR-014)
    sheet_pairs, sheet_stats = _pair_sheets_by_number(sheets_a, sheets_b)
    sheet_jobs: list[Job] = []
    skipped_existing = 0

    if not sheet_pairs:
        logger.warning(
            "[overlay.pairing.empty] drawingA=%s drawingB=%s "
            "sheets_matched=0 sheets_skipped_no_number=%d sheets_skipped_no_match=%d",
            payload.drawing_a_id,
            payload.drawing_b_id,
            sheet_stats.sheets_skipped_no_number,
            sheet_stats.sheets_skipped_no_match,
        )
    try:
        for sheet_a, sheet_b, pairing_method in sheet_pairs:
            existing_job = session.exec(
                select(Job).where(
                    Job.parent_id == job.id,
                    Job.type == JobType.SHEET_OVERLAY_GENERATE,
                    Job.target_id == sheet_b.id,
                )
            ).first()
            if existing_job and existing_job.status in {
                JobStatus.QUEUED,
                JobStatus.STARTED,
                JobStatus.COMPLETED,
            }:
                skipped_existing += 1
                continue

            job_id = generate_cuid()
            job_payload = {
                "sheetAId": sheet_a.id,
                "sheetBId": sheet_b.id,
                "drawingAId": payload.drawing_a_id,
                "drawingBId": payload.drawing_b_id,
            }
            sheet_job = Job(
                id=job_id,
                parent_id=job.id,
                type=JobType.SHEET_OVERLAY_GENERATE,
                status=JobStatus.QUEUED,
                organization_id=job.organization_id,
                project_id=job.project_id,
                actor_id=job.actor_id,
                target_type="sheet",
                target_id=sheet_b.id,
                payload=job_payload,
                events=[
                    create_job_event(
                        job_type=JobType.SHEET_OVERLAY_GENERATE,
                        job_id=str(job_id),
                        status=JobStatus.QUEUED.value,
                        event_type="created",
                        sheet_id=sheet_a.id,
                        metadata={**job_payload, "pairingMethod": pairing_method},
                    )
                ],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(sheet_job)
            sheet_jobs.append(sheet_job)
        session.commit()

        for sheet_job in sheet_jobs:
            pubsub_client.publish(
                config.vision_topic,
                build_job_envelope(
                    job_type=sheet_job.type,
                    job_id=str(sheet_job.id),
                    payload=sheet_job.payload,
                ),
                attributes={"type": sheet_job.type, "id": str(sheet_job.id)},
            )

        log_coordination_published(
            logger,
            config.vision_topic,
            len(sheet_jobs),
            drawing_id=payload.drawing_a_id,
            job_id=str(envelope.job_id),
        )

        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.now(UTC)
        completed_event = create_job_event(
            job_type=job.type,
            job_id=str(job.id),
            status=JobStatus.COMPLETED.value,
            event_type="completed",
            metadata={
                "drawingAId": payload.drawing_a_id,
                "drawingBId": payload.drawing_b_id,
                "sheetsTotalA": len(sheets_a),
                "sheetsTotalB": len(sheets_b),
                # Sheet number matching stats (US4: FR-014)
                "sheetsMatchedByNumber": sheet_stats.sheets_matched_by_number,
                "sheetsSkippedNoNumber": sheet_stats.sheets_skipped_no_number,
                "sheetsSkippedNoMatch": sheet_stats.sheets_skipped_no_match,
                # Job creation stats
                "sheetsQueued": len(sheet_jobs),
                "sheetsSkippedExisting": skipped_existing,
            },
        )
        job.events = append_job_event_if_missing(job.events, completed_event)
        session.add(job)
        session.commit()
    except Exception:
        session.rollback()
        job.status = JobStatus.FAILED
        job.updated_at = datetime.now(UTC)
        failed_event = create_job_event(
            job_type=job.type,
            job_id=str(job.id),
            status=JobStatus.FAILED.value,
            event_type="failed",
            metadata={
                "drawingAId": payload.drawing_a_id,
                "drawingBId": payload.drawing_b_id,
            },
        )
        job.events = append_job_event_if_missing(job.events, failed_event)
        session.add(job)
        session.commit()
        raise

    log_job_completed(
        logger,
        job_type,
        message_id or "",
        start_time,
        drawing_id=payload.drawing_a_id,
        job_id=str(envelope.job_id),
    )
