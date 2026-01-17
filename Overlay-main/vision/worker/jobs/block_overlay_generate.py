"""Block overlay generation job handler.

This module handles the generation of overlay images between two blocks.

Alignment Strategy:
- SIFT (Scale-Invariant Feature Transform) is always used as the primary
  alignment method. It's fast (~5-10 seconds) and works well for most cases.
- If SIFT fails completely (e.g., not enough feature matches), Grid alignment
  is attempted as a fallback using Gemini Vision API (~2-3 minutes).
- SIFT results are always used regardless of confidence level - low confidence
  alignments may produce suboptimal overlays but will not fail the job.

Rendering:
- Merge-mode rendering is used for visual differentiation between old/new blocks.
"""

import gc
import logging
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from clients.storage import get_storage_client
from config import config
from jobs.envelope import JobEnvelope
from jobs.types import JobType
from lib.grid_alignment import align_with_grid
from lib.overlay_render import generate_overlay_merge_mode
from lib.sift_alignment import (
    AlignmentStats,
    _encode_image_to_png,
    _load_image_from_bytes,
    sift_align,
)
from models import Block, BlockType, Job, JobStatus, Overlay
from utils.id_utils import generate_cuid
from utils.job_errors import is_permanent_job_error
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
LOW_CONFIDENCE_SCORE = 0.05

# VIEW block types that support overlay generation
VIEW_BLOCK_TYPES = {
    BlockType.PLAN,
    BlockType.ELEVATION,
    BlockType.SECTION,
    BlockType.DETAIL,
}


class BlockOverlayGeneratePayload(BaseModel):
    """Input payload for block overlay generation job messages."""

    model_config = {"extra": "forbid"}

    block_a_id: str = Field(..., description="UUID of the source block (old)")
    block_b_id: str = Field(..., description="UUID of the target block (new)")
    sheet_a_id: str | None = Field(default=None, description="UUID of the source sheet")
    sheet_b_id: str | None = Field(default=None, description="UUID of the target sheet")
    drawing_a_id: str | None = Field(default=None, description="UUID of the source drawing")
    drawing_b_id: str | None = Field(default=None, description="UUID of the target drawing")


def ensure_overlay(
    session: Session,
    payload: BlockOverlayGeneratePayload,
    job_id: str | None,
) -> Overlay:
    overlay = session.exec(
        select(Overlay).where(
            Overlay.block_a_id == payload.block_a_id,
            Overlay.block_b_id == payload.block_b_id,
            Overlay.deleted_at.is_(None),
        )
    ).first()
    if overlay:
        if job_id and overlay.job_id != job_id:
            overlay.job_id = job_id
            overlay.updated_at = datetime.now(UTC)
            session.add(overlay)
            session.commit()
            session.refresh(overlay)
        return overlay

    block_a = session.get(Block, payload.block_a_id)
    block_b = session.get(Block, payload.block_b_id)
    if not block_a:
        raise ValueError(f"Block A not found: {payload.block_a_id}")
    if not block_b:
        raise ValueError(f"Block B not found: {payload.block_b_id}")
    if block_a.deleted_at is not None:
        raise ValueError(f"Block A has been deleted: {payload.block_a_id}")
    if block_b.deleted_at is not None:
        raise ValueError(f"Block B has been deleted: {payload.block_b_id}")
    if not block_a.uri:
        raise ValueError(f"Block A ({payload.block_a_id}) is missing image URI")
    if not block_b.uri:
        raise ValueError(f"Block B ({payload.block_b_id}) is missing image URI")

    overlay = Overlay(
        id=generate_cuid(),
        job_id=job_id,
        block_a_id=block_a.id,
        block_b_id=block_b.id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(overlay)
    session.commit()
    session.refresh(overlay)
    return overlay


def _download_block_image(storage_client, uri: str) -> bytes:
    """Download block image from storage."""
    remote_path = extract_remote_path(uri)
    start = time.time()
    data = storage_client.download_to_bytes(remote_path)
    log_storage_download(
        logger,
        remote_path,
        size_bytes=len(data),
        duration_ms=int((time.time() - start) * 1000),
    )
    return data


# SIFT inlier ratio threshold for logging warnings (does not block alignment)
# Alignments below this threshold will log a warning but still proceed
SIFT_CONFIDENCE_THRESHOLD = 0.3


def _align_blocks(
    img_a: np.ndarray,
    img_b: np.ndarray,
    path_a: Path | None,
    path_b: Path | None,
    _has_grid: bool = False,
) -> tuple[np.ndarray, np.ndarray, AlignmentStats]:
    """Align two block images using SIFT alignment with Grid fallback.

    Alignment Strategy:
    1. SIFT alignment is always attempted first (~5-10 seconds)
    2. SIFT results are always used if successful, regardless of confidence
    3. If SIFT fails completely (RuntimeError), Grid fallback is attempted
    4. Grid alignment uses Gemini Vision API (~2-3 minutes) to detect grid lines
    5. If both methods fail, the original SIFT error is raised

    Note: Low confidence SIFT alignments (inlier_ratio < 0.3) will log a warning
    but still proceed. This may result in suboptimal overlays for difficult cases.

    Args:
        img_a: Image A in RGB format (old/source)
        img_b: Image B in RGB format (new/target)
        path_a: Path to image A file (required for grid alignment fallback)
        path_b: Path to image B file (required for grid alignment fallback)
        _has_grid: Unused, kept for API compatibility

    Returns:
        (aligned_a, aligned_b, stats) - AlignmentStats contains method used

    Raises:
        RuntimeError: If all alignment methods fail
    """
    sift_error = None

    # Step 1: Try SIFT alignment first (primary method)
    try:
        aligned_a, aligned_b, stats = sift_align(
            img_a,
            img_b,
            downsample_scale=0.5,
            n_features=config.sift_n_features,
            ratio_threshold=config.sift_ratio_threshold,
            ransac_threshold=config.ransac_reproj_threshold,
            max_iters=config.ransac_max_iters,
            scale_min=config.transform_scale_min,
            scale_max=config.transform_scale_max,
            rotation_deg_min=config.transform_rotation_deg_min,
            rotation_deg_max=config.transform_rotation_deg_max,
            normalize_size=True,
            contrast_threshold=0.02,
            expand_canvas=True,
        )

        logger.info(
            "[alignment.sift] scale=%.4f rotation=%.2f inlier_ratio=%.2f inliers=%d",
            stats.scale,
            stats.rotation_deg,
            stats.inlier_ratio,
            stats.inlier_count,
        )

        # SIFT succeeded - return result (even if low confidence)
        if stats.inlier_ratio < SIFT_CONFIDENCE_THRESHOLD:
            logger.warning(
                "[alignment.sift.low_confidence] inlier_ratio=%.2f < threshold=%.2f (proceeding anyway)",
                stats.inlier_ratio,
                SIFT_CONFIDENCE_THRESHOLD,
            )

        return aligned_a, aligned_b, stats

    except RuntimeError as e:
        sift_error = e
        logger.warning("[alignment.sift.failed] %s - trying grid fallback", str(e))

    # Step 2: Try Grid alignment as fallback (if paths available)
    if path_a is not None and path_b is not None:
        try:
            logger.info("[alignment.grid] Starting grid alignment fallback...")
            result = align_with_grid(img_a, img_b, path_a, path_b)
            if result[0] is not None:
                aligned_a, aligned_b, stats = result
                logger.info(
                    "[alignment.grid.success] h_matches=%d v_matches=%d",
                    stats.h_matches,
                    stats.v_matches,
                )
                return aligned_a, aligned_b, stats

            logger.warning("[alignment.grid.failed] insufficient grid lines")
        except RuntimeError as e:
            # Gemini API errors should fail the job immediately
            if "Gemini API" in str(e) or "GEMINI_API_KEY" in str(e):
                raise
            logger.warning("[alignment.grid.failed] %s", str(e))
    else:
        logger.warning("[alignment.grid.skipped] missing image file paths for grid fallback")

    # Both methods failed
    if sift_error:
        raise sift_error
    raise RuntimeError("Alignment failed: no successful alignment method")


def _generate_overlay_assets(
    img_a_bytes: bytes,
    img_b_bytes: bytes,
    block_a: Block,
) -> tuple[bytes, bytes, bytes, float, AlignmentStats]:
    """Generate overlay assets from block images.

    Uses SIFT-first alignment with Grid fallback, and merge-mode rendering.

    Args:
        img_a_bytes: PNG bytes for block A (old)
        img_b_bytes: PNG bytes for block B (new)
        block_a: Block A model for metadata access

    Returns:
        (overlay_bytes, addition_bytes, deletion_bytes, overlay_score, alignment_stats)

    Raises:
        RuntimeError: If alignment fails
    """
    # Always write temp files for potential Grid fallback when SIFT fails
    path_a: Path | None = None
    path_b: Path | None = None

    # Write PNG bytes directly - needed for Grid fallback
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_a:
        path_a = Path(f_a.name)
        f_a.write(img_a_bytes)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f_b:
        path_b = Path(f_b.name)
        f_b.write(img_b_bytes)

    # Decode images to numpy arrays
    img_a = _load_image_from_bytes(img_a_bytes)
    img_b = _load_image_from_bytes(img_b_bytes)

    try:
        # Align blocks using SIFT-first with Grid fallback
        aligned_a, aligned_b, stats = _align_blocks(img_a, img_b, path_a, path_b, has_grid)

        # Release original images - no longer needed after alignment
        del img_a, img_b
        gc.collect()

        # Calculate overlay score
        if stats.method == "grid":
            # For grid alignment, use match count as score proxy
            total_matches = (stats.h_matches or 0) + (stats.v_matches or 0)
            overlay_score = min(1.0, total_matches / 10.0)  # Normalize to 0-1
        else:
            # For SIFT, use inlier ratio
            overlay_score = stats.inlier_ratio or 0.0

        # Generate overlay using merge-mode (FR-005, FR-006)
        # Note: merge mode returns None for deletion/addition to save memory
        h, w = aligned_a.shape[:2]
        overlay_img, _, _ = generate_overlay_merge_mode(
            aligned_a,
            aligned_b,
            tint_strength=0.5,  # Default from generate_overlay.py
        )

        # Release aligned images - no longer needed after overlay generation
        del aligned_a, aligned_b
        gc.collect()

        # Encode overlay first, then create white images lazily (one at a time)
        overlay_bytes = _encode_image_to_png(overlay_img)
        del overlay_img
        gc.collect()

        # Create and encode deletion (white image) - lazy to reduce peak memory
        deletion_img = np.full((h, w, 3), 255, dtype=np.uint8)
        deletion_bytes = _encode_image_to_png(deletion_img)
        del deletion_img
        gc.collect()

        # Create and encode addition (white image) - lazy to reduce peak memory
        addition_img = np.full((h, w, 3), 255, dtype=np.uint8)
        addition_bytes = _encode_image_to_png(addition_img)
        del addition_img
        gc.collect()

        return overlay_bytes, addition_bytes, deletion_bytes, overlay_score, stats

    finally:
        # Clean up temporary files
        if path_a and path_a.exists():
            path_a.unlink()
        if path_b and path_b.exists():
            path_b.unlink()


def _upload_overlay_assets(
    storage_client,
    overlay_id: str,
    overlay_bytes: bytes,
    addition_bytes: bytes,
    deletion_bytes: bytes,
) -> tuple[str, str, str]:
    """Upload overlay assets to storage."""
    overlay_path = f"block-overlays/{overlay_id}.png"
    addition_path = f"block-additions/{overlay_id}.png"
    deletion_path = f"block-deletions/{overlay_id}.png"

    overlay_uri = storage_client.upload_from_bytes(
        overlay_bytes,
        overlay_path,
        content_type="image/png",
    )
    log_storage_upload(logger, overlay_path, size_bytes=len(overlay_bytes))

    addition_uri = storage_client.upload_from_bytes(
        addition_bytes,
        addition_path,
        content_type="image/png",
    )
    log_storage_upload(logger, addition_path, size_bytes=len(addition_bytes))

    deletion_uri = storage_client.upload_from_bytes(
        deletion_bytes,
        deletion_path,
        content_type="image/png",
    )
    log_storage_upload(logger, deletion_path, size_bytes=len(deletion_bytes))

    return overlay_uri, addition_uri, deletion_uri


def run_block_overlay_generate_job(
    session: Session,
    payload: BlockOverlayGeneratePayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    """Execute block overlay generation job."""
    job_type = JobType.BLOCK_OVERLAY_GENERATE
    job = session.get(Job, envelope.job_id)
    if not job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] block overlay job {job.id} canceled before start")
        return

    overlay = ensure_overlay(session, payload, str(envelope.job_id))
    metadata = {
        "blockAId": payload.block_a_id,
        "blockBId": payload.block_b_id,
        "overlayId": overlay.id,
        **({"sheetAId": payload.sheet_a_id} if payload.sheet_a_id else {}),
        **({"sheetBId": payload.sheet_b_id} if payload.sheet_b_id else {}),
        **({"drawingAId": payload.drawing_a_id} if payload.drawing_a_id else {}),
        **({"drawingBId": payload.drawing_b_id} if payload.drawing_b_id else {}),
    }

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
        job_type=job_type,
        job_id=str(job.id),
        status=job.status.value,
        event_type="started",
        block_id=payload.block_a_id,
        metadata=metadata,
    )
    job.events = append_job_event_if_missing(job.events, started_event)
    session.add(job)
    session.commit()

    try:
        # Check if overlay already exists
        if overlay.uri and overlay.addition_uri and overlay.deletion_uri:
            overlay_score = overlay.score
            job.status = JobStatus.COMPLETED
            job.updated_at = datetime.now(UTC)
            completed_event = create_job_event(
                job_type=job_type,
                job_id=str(job.id),
                status=JobStatus.COMPLETED.value,
                event_type="completed",
                block_id=payload.block_a_id,
                metadata={
                    **metadata,
                    **({"overlayScore": overlay_score} if overlay_score is not None else {}),
                    **(
                        {"overlayLowConfidence": overlay_score < LOW_CONFIDENCE_SCORE}
                        if overlay_score is not None
                        else {}
                    ),
                },
            )
            job.events = append_job_event_if_missing(job.events, completed_event)
            session.add(job)
            session.commit()
            log_job_completed(
                logger,
                job_type,
                message_id or "",
                start_time,
                block_id=payload.block_a_id,
                job_id=str(envelope.job_id),
            )
            return

        # Load blocks
        block_a = session.get(Block, payload.block_a_id)
        block_b = session.get(Block, payload.block_b_id)
        if not block_a or not block_b:
            raise ValueError("Blocks not found for overlay generation")
        if not block_a.uri or not block_b.uri:
            raise ValueError("Blocks missing image URI for overlay generation")

        storage_client = get_storage_client()

        with log_phase(logger, "Download block images", block_id=payload.block_a_id):
            img_a_bytes = _download_block_image(storage_client, block_a.uri)
            img_b_bytes = _download_block_image(storage_client, block_b.uri)

        with log_phase(logger, "Align and render overlay", block_id=payload.block_a_id):
            (
                overlay_bytes,
                addition_bytes,
                deletion_bytes,
                overlay_score,
                alignment_stats,
            ) = _generate_overlay_assets(img_a_bytes, img_b_bytes, block_a)

        if overlay_score < LOW_CONFIDENCE_SCORE:
            logger.warning(
                "[overlay.low_confidence] score=%.3f method=%s",
                overlay_score,
                alignment_stats.method,
            )

        with log_phase(logger, "Upload overlay assets", overlay_id=overlay.id):
            overlay_uri, addition_uri, deletion_uri = _upload_overlay_assets(
                storage_client,
                overlay.id,
                overlay_bytes,
                addition_bytes,
                deletion_bytes,
            )

        # Update overlay record
        overlay.uri = overlay_uri
        overlay.addition_uri = addition_uri
        overlay.deletion_uri = deletion_uri
        overlay.score = overlay_score
        overlay.updated_at = datetime.now(UTC)
        session.add(overlay)

        # Build completed event metadata with alignment stats
        completed_metadata = {
            **metadata,
            "overlayScore": overlay_score,
            "overlayLowConfidence": overlay_score < LOW_CONFIDENCE_SCORE,
            "alignmentMethod": alignment_stats.method,
        }

        # Add method-specific stats
        if alignment_stats.method == "sift":
            completed_metadata["alignmentInliers"] = alignment_stats.inlier_count
            completed_metadata["alignmentMatches"] = (
                int(alignment_stats.inlier_count / alignment_stats.inlier_ratio)
                if alignment_stats.inlier_ratio and alignment_stats.inlier_ratio > 0
                else 0
            )
        elif alignment_stats.method == "grid":
            completed_metadata["gridHMatches"] = alignment_stats.h_matches
            completed_metadata["gridVMatches"] = alignment_stats.v_matches

        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.now(UTC)
        completed_event = create_job_event(
            job_type=job_type,
            job_id=str(job.id),
            status=JobStatus.COMPLETED.value,
            event_type="completed",
            block_id=payload.block_a_id,
            metadata=completed_metadata,
        )
        job.events = append_job_event_if_missing(job.events, completed_event)
        session.add(job)
        session.commit()

        log_job_completed(
            logger,
            job_type,
            message_id or "",
            start_time,
            block_id=payload.block_a_id,
            job_id=str(envelope.job_id),
        )
    except Exception as error:
        _fail_job(
            session,
            job,
            job_type=job_type,
            metadata=metadata,
            block_id=payload.block_a_id,
            error=error,
        )
        raise


def _fail_job(
    session: Session,
    job: Job,
    *,
    job_type: str,
    metadata: dict[str, object],
    block_id: str,
    error: Exception,
) -> None:
    """Mark job as failed with error details."""
    session.rollback()
    job.status = JobStatus.FAILED
    job.updated_at = datetime.now(UTC)
    failed_event = create_job_event(
        job_type=job_type,
        job_id=str(job.id),
        status=JobStatus.FAILED.value,
        event_type="failed",
        block_id=block_id,
        metadata={
            **metadata,
            "errorType": type(error).__name__,
            "errorMessage": str(error),
            "permanent": is_permanent_job_error(error),
        },
    )
    job.events = append_job_event_if_missing(job.events, failed_event)
    session.add(job)
    session.commit()
