"""Sheet overlay generation job handler.

This module handles the generation of overlay jobs between two sheets by
matching VIEW blocks (plan, elevation, section, detail) by their identifier field.
"""

import logging
from datetime import UTC, datetime

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from clients.pubsub import get_pubsub_client
from config import config
from jobs.envelope import JobEnvelope, build_job_envelope
from jobs.types import JobType
from models import Block, BlockType, Job, JobStatus, Overlay, Sheet
from utils.id_utils import generate_cuid
from utils.job_events import append_job_event_if_missing, create_job_event
from utils.log_utils import log_coordination_published, log_job_completed, log_job_started

logger = logging.getLogger(__name__)

# VIEW block types that support overlay generation
VIEW_BLOCK_TYPES = {
    BlockType.PLAN,
    BlockType.ELEVATION,
    BlockType.SECTION,
    BlockType.DETAIL,
}


def _is_view_block(block: Block) -> bool:
    """Check if a block is a VIEW block type.

    Args:
        block: Block to check

    Returns:
        True if block type is in VIEW_BLOCK_TYPES, False otherwise
    """
    if block.type is None:
        return False
    try:
        block_type = BlockType(block.type)
        return block_type in VIEW_BLOCK_TYPES
    except ValueError:
        return False


def _filter_view_blocks(blocks: list[Block]) -> list[Block]:
    """Filter blocks to only include VIEW block types.

    Args:
        blocks: List of blocks to filter

    Returns:
        List of blocks that are VIEW block types
    """
    return [block for block in blocks if _is_view_block(block)]


def _get_block_identifier(block: Block) -> str | None:
    """Extract identifier from block metadata.

    The identifier is used to match blocks between sheets.
    Common identifiers are like "A1", "1", "101", etc.

    Args:
        block: Block to extract identifier from

    Returns:
        Normalized identifier string (lowercase, stripped) or None if not present
    """
    metadata = block.metadata_ or {}
    identifier = metadata.get("identifier")
    if isinstance(identifier, str) and identifier.strip():
        return identifier.strip().lower()
    return None


def _build_identifier_map(blocks: list[Block]) -> dict[str, Block]:
    """Build a lookup map from identifier to block.

    Only includes blocks that have a valid identifier.

    Args:
        blocks: List of blocks to build map from

    Returns:
        Dict mapping identifier (lowercase) to Block
    """
    identifier_map: dict[str, Block] = {}
    for block in blocks:
        identifier = _get_block_identifier(block)
        if identifier and block.id:
            # First block with identifier wins (no duplicates)
            if identifier not in identifier_map:
                identifier_map[identifier] = block
            else:
                logger.warning(
                    "[overlay.identifier.duplicate] identifier=%s block_id=%s already_mapped_to=%s",
                    identifier,
                    block.id,
                    identifier_map[identifier].id,
                )
    return identifier_map


class SheetOverlayGeneratePayload(BaseModel):
    """Input payload for sheet overlay generation job messages."""

    model_config = {"extra": "forbid"}

    sheet_a_id: str = Field(..., description="UUID of the source sheet")
    sheet_b_id: str = Field(..., description="UUID of the target sheet")
    drawing_a_id: str | None = Field(default=None, description="UUID of the source drawing")
    drawing_b_id: str | None = Field(default=None, description="UUID of the target drawing")


def _block_sort_key(block: Block) -> tuple:
    bounds = block.bounds or {}
    if {"xmin", "ymin"} <= bounds.keys():
        return (0, bounds["ymin"], bounds["xmin"])
    return (1, block.created_at or datetime.min, block.id or "")


def _block_name(block: Block) -> str | None:
    metadata = block.metadata_ or {}
    name = metadata.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip().lower()
    return None


def _block_text_signature(block: Block) -> str | None:
    candidate = block.description or block.ocr
    if not candidate or not isinstance(candidate, str):
        return None
    normalized = "".join(char.lower() if char.isalnum() else " " for char in candidate)
    cleaned = " ".join(normalized.split())
    if not cleaned:
        return None
    return cleaned[:60]


def _block_signature(block: Block) -> tuple[float, float, float, float] | None:
    bounds = block.bounds or {}
    if not {"xmin", "ymin", "xmax", "ymax"} <= bounds.keys():
        return None

    xmin = float(bounds["xmin"])
    ymin = float(bounds["ymin"])
    xmax = float(bounds["xmax"])
    ymax = float(bounds["ymax"])
    width = xmax - xmin
    height = ymax - ymin
    if width <= 0 or height <= 0:
        return None

    cx = xmin + width / 2
    cy = ymin + height / 2
    area = width * height
    aspect = width / height
    return cx, cy, area, aspect


def _block_pair_score(
    signature_a: tuple[float, float, float, float],
    signature_b: tuple[float, float, float, float],
) -> float:
    cx_a, cy_a, area_a, aspect_a = signature_a
    cx_b, cy_b, area_b, aspect_b = signature_b
    centroid_distance = (cx_a - cx_b) ** 2 + (cy_a - cy_b) ** 2
    area_ratio = area_b / area_a if area_a > 0 else 1.0
    aspect_ratio = aspect_b / aspect_a if aspect_a > 0 else 1.0
    return centroid_distance + abs(area_ratio - 1.0) + abs(aspect_ratio - 1.0)


def _signatures_compatible(
    signature_a: tuple[float, float, float, float],
    signature_b: tuple[float, float, float, float],
) -> bool:
    _cx_a, _cy_a, area_a, aspect_a = signature_a
    _cx_b, _cy_b, area_b, aspect_b = signature_b
    if area_a <= 0 or area_b <= 0 or aspect_a <= 0 or aspect_b <= 0:
        return False
    area_ratio = area_b / area_a
    aspect_ratio = aspect_b / aspect_a
    return 0.25 <= area_ratio <= 4.0 and 0.25 <= aspect_ratio <= 4.0


def _pair_blocks(
    blocks_a: list[Block],
    blocks_b: list[Block],
) -> list[tuple[Block, Block, str]]:
    paired: list[tuple[Block, Block, str]] = []
    used_a: set[str] = set()
    used_b: set[str] = set()

    types_a = {block.type for block in blocks_a if block.type is not None}
    types_b = {block.type for block in blocks_b if block.type is not None}
    for block_type in sorted(types_a & types_b, key=str):
        group_a = sorted(
            [block for block in blocks_a if block.type == block_type],
            key=_block_sort_key,
        )
        group_b = sorted(
            [block for block in blocks_b if block.type == block_type],
            key=_block_sort_key,
        )
        for block_a in group_a:
            if not block_a.id or block_a.id in used_a:
                continue
            name = _block_name(block_a)
            if not name:
                continue
            matching_block = next(
                (
                    block
                    for block in group_b
                    if block.id and block.id not in used_b and _block_name(block) == name
                ),
                None,
            )
            if not matching_block or not matching_block.id:
                continue
            paired.append((block_a, matching_block, "name"))
            used_a.add(block_a.id)
            used_b.add(matching_block.id)
        for block_a in group_a:
            if not block_a.id or block_a.id in used_a:
                continue
            signature = _block_text_signature(block_a)
            if not signature:
                continue
            matching_block = next(
                (
                    block
                    for block in group_b
                    if block.id
                    and block.id not in used_b
                    and _block_text_signature(block) == signature
                ),
                None,
            )
            if not matching_block or not matching_block.id:
                continue
            paired.append((block_a, matching_block, "text"))
            used_a.add(block_a.id)
            used_b.add(matching_block.id)
        for block_a in group_a:
            if not block_a.id or block_a.id in used_a:
                continue
            signature_a = _block_signature(block_a)
            best_block = None
            best_score = None
            for block_b in group_b:
                if not block_b.id or block_b.id in used_b:
                    continue
                signature_b = _block_signature(block_b)
                if signature_a and signature_b and _signatures_compatible(signature_a, signature_b):
                    score = _block_pair_score(signature_a, signature_b)
                    if best_score is None or score < best_score:
                        best_score = score
                        best_block = block_b

            if best_block is None:
                best_block = next(
                    (block for block in group_b if block.id and block.id not in used_b),
                    None,
                )

            if not best_block or not best_block.id:
                continue

            paired.append((block_a, best_block, "bounds"))
            used_a.add(block_a.id)
            used_b.add(best_block.id)

    remaining_a = [block for block in blocks_a if block.id not in used_a]
    remaining_b = [block for block in blocks_b if block.id not in used_b]
    for block_a, block_b in zip(
        sorted(remaining_a, key=_block_sort_key),
        sorted(remaining_b, key=_block_sort_key),
    ):
        if not block_a.id or not block_b.id:
            continue
        if block_a.type is not None and block_b.type is not None and block_a.type != block_b.type:
            continue
        paired.append((block_a, block_b, "order"))

    return paired


class ViewBlockMatchingStats(BaseModel):
    """Statistics for VIEW block matching by identifier."""

    view_blocks_matched: int = 0
    view_blocks_skipped_no_identifier: int = 0
    view_blocks_skipped_no_match: int = 0
    non_view_blocks_skipped: int = 0


def _pair_view_blocks_by_identifier(
    blocks_a: list[Block],
    blocks_b: list[Block],
) -> tuple[list[tuple[Block, Block, str]], ViewBlockMatchingStats]:
    """Pair VIEW blocks between two sheets by identifier.

    Only matches VIEW block types (plan, elevation, section, detail) using their
    identifier field in metadata. Non-VIEW blocks are skipped entirely.

    Args:
        blocks_a: Blocks from sheet A (source/old)
        blocks_b: Blocks from sheet B (target/new)

    Returns:
        Tuple of (paired_blocks, stats) where:
        - paired_blocks: List of (block_a, block_b, "identifier") tuples
        - stats: ViewBlockMatchingStats with matching statistics
    """
    stats = ViewBlockMatchingStats()
    paired: list[tuple[Block, Block, str]] = []

    # Filter to VIEW blocks only
    view_blocks_a = _filter_view_blocks(blocks_a)
    view_blocks_b = _filter_view_blocks(blocks_b)

    # Count non-VIEW blocks skipped
    stats.non_view_blocks_skipped = len(blocks_a) - len(view_blocks_a)

    # Build identifier map for sheet B
    identifier_map_b = _build_identifier_map(view_blocks_b)

    # Match VIEW blocks from A to B by identifier
    for block_a in view_blocks_a:
        if not block_a.id:
            continue

        identifier = _get_block_identifier(block_a)
        if not identifier:
            stats.view_blocks_skipped_no_identifier += 1
            logger.info(
                "[overlay.view_block.no_identifier] block_id=%s type=%s",
                block_a.id,
                block_a.type,
            )
            continue

        # Look up matching block in B
        block_b = identifier_map_b.get(identifier)
        if not block_b or not block_b.id:
            stats.view_blocks_skipped_no_match += 1
            logger.info(
                "[overlay.view_block.no_match] block_id=%s identifier=%s",
                block_a.id,
                identifier,
            )
            continue

        # Found a match
        paired.append((block_a, block_b, "identifier"))
        stats.view_blocks_matched += 1
        logger.info(
            "[overlay.view_block.matched] block_a_id=%s block_b_id=%s identifier=%s",
            block_a.id,
            block_b.id,
            identifier,
        )

    return paired, stats


def run_sheet_overlay_generate_job(
    session: Session,
    payload: SheetOverlayGeneratePayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    job_type = JobType.SHEET_OVERLAY_GENERATE

    job = session.get(Job, envelope.job_id)
    if not job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] sheet overlay job {job.id} canceled before start")
        return

    sheet_a = session.get(Sheet, payload.sheet_a_id)
    sheet_b = session.get(Sheet, payload.sheet_b_id)
    if not sheet_a or not sheet_b:
        raise ValueError("Sheets not found for overlay generation")

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
        sheet_id=payload.sheet_a_id,
        metadata={
            "sheetAId": payload.sheet_a_id,
            "sheetBId": payload.sheet_b_id,
            "drawingAId": payload.drawing_a_id,
            "drawingBId": payload.drawing_b_id,
        },
    )
    job.events = append_job_event_if_missing(job.events, started_event)
    session.add(job)
    session.commit()

    pubsub_client = get_pubsub_client()

    blocks_a = session.exec(
        select(Block).where(
            Block.sheet_id == payload.sheet_a_id,
            Block.deleted_at.is_(None),
        )
    ).all()
    blocks_b = session.exec(
        select(Block).where(
            Block.sheet_id == payload.sheet_b_id,
            Block.deleted_at.is_(None),
        )
    ).all()

    # Use VIEW block matching by identifier (US3: FR-008, FR-009, FR-010, FR-011)
    block_pairs, view_stats = _pair_view_blocks_by_identifier(blocks_a, blocks_b)
    block_jobs: list[Job] = []
    skipped_missing_uri = 0
    skipped_existing = 0
    skipped_inflight = 0

    if not block_pairs:
        logger.warning(
            "[overlay.pairing.empty] sheetA=%s sheetB=%s view_blocks_matched=0 non_view_skipped=%d",
            payload.sheet_a_id,
            payload.sheet_b_id,
            view_stats.non_view_blocks_skipped,
        )
    try:
        for block_a, block_b, pairing_method in block_pairs:
            if not block_a.uri or not block_b.uri:
                skipped_missing_uri += 1
                continue

            existing_overlay = session.exec(
                select(Overlay).where(
                    Overlay.block_a_id == block_a.id,
                    Overlay.block_b_id == block_b.id,
                    Overlay.deleted_at.is_(None),
                )
            ).first()
            if (
                existing_overlay
                and existing_overlay.uri
                and existing_overlay.addition_uri
                and existing_overlay.deletion_uri
            ):
                skipped_existing += 1
                continue

            if existing_overlay and existing_overlay.job_id:
                existing_job = session.get(Job, existing_overlay.job_id)
                if existing_job and existing_job.status in {
                    JobStatus.QUEUED,
                    JobStatus.STARTED,
                }:
                    skipped_inflight += 1
                    continue
            elif not existing_overlay:
                existing_job = session.exec(
                    select(Job).where(
                        Job.parent_id == job.id,
                        Job.type == JobType.BLOCK_OVERLAY_GENERATE,
                        Job.target_id == block_b.id,
                    )
                ).first()
                if existing_job and existing_job.status in {
                    JobStatus.QUEUED,
                    JobStatus.STARTED,
                }:
                    skipped_inflight += 1
                    continue

            job_id = generate_cuid()
            overlay = existing_overlay
            if not overlay:
                overlay = Overlay(
                    id=generate_cuid(),
                    job_id=job_id,
                    block_a_id=block_a.id,
                    block_b_id=block_b.id,
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
                session.add(overlay)
            else:
                overlay.job_id = job_id
                overlay.updated_at = datetime.now(UTC)
                session.add(overlay)

            job_payload = {
                "blockAId": block_a.id,
                "blockBId": block_b.id,
                "sheetAId": payload.sheet_a_id,
                "sheetBId": payload.sheet_b_id,
                "drawingAId": payload.drawing_a_id,
                "drawingBId": payload.drawing_b_id,
            }
            job_event_metadata = {
                **job_payload,
                "overlayId": overlay.id,
                "pairingMethod": pairing_method,
            }
            block_job = Job(
                id=job_id,
                parent_id=job.id,
                type=JobType.BLOCK_OVERLAY_GENERATE,
                status=JobStatus.QUEUED,
                organization_id=job.organization_id,
                project_id=job.project_id,
                actor_id=job.actor_id,
                target_type="block",
                target_id=block_b.id,
                payload=job_payload,
                events=[
                    create_job_event(
                        job_type=JobType.BLOCK_OVERLAY_GENERATE,
                        job_id=str(job_id),
                        status=JobStatus.QUEUED.value,
                        event_type="created",
                        block_id=block_a.id,
                        metadata=job_event_metadata,
                    )
                ],
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            session.add(block_job)
            block_jobs.append(block_job)
        session.commit()

        for block_job in block_jobs:
            pubsub_client.publish(
                config.vision_topic,
                build_job_envelope(
                    job_type=block_job.type,
                    job_id=str(block_job.id),
                    payload=block_job.payload,
                ),
                attributes={"type": block_job.type, "id": str(block_job.id)},
            )

        log_coordination_published(
            logger,
            config.vision_topic,
            len(block_jobs),
            sheet_id=payload.sheet_a_id,
            job_id=str(envelope.job_id),
        )

        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.now(UTC)
        completed_event = create_job_event(
            job_type=job.type,
            job_id=str(job.id),
            status=JobStatus.COMPLETED.value,
            event_type="completed",
            sheet_id=payload.sheet_a_id,
            metadata={
                "sheetAId": payload.sheet_a_id,
                "sheetBId": payload.sheet_b_id,
                "drawingAId": payload.drawing_a_id,
                "drawingBId": payload.drawing_b_id,
                "blocksTotalA": len(blocks_a),
                "blocksTotalB": len(blocks_b),
                # VIEW block matching stats (US3: FR-011)
                "viewBlocksMatched": view_stats.view_blocks_matched,
                "viewBlocksSkippedNoIdentifier": view_stats.view_blocks_skipped_no_identifier,
                "viewBlocksSkippedNoMatch": view_stats.view_blocks_skipped_no_match,
                "nonViewBlocksSkipped": view_stats.non_view_blocks_skipped,
                # Job creation stats
                "blocksQueued": len(block_jobs),
                "blocksSkippedMissingUri": skipped_missing_uri,
                "blocksSkippedExisting": skipped_existing,
                "blocksSkippedInflight": skipped_inflight,
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
            sheet_id=payload.sheet_a_id,
            metadata={
                "sheetAId": payload.sheet_a_id,
                "sheetBId": payload.sheet_b_id,
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
        sheet_id=payload.sheet_a_id,
        job_id=str(envelope.job_id),
    )
