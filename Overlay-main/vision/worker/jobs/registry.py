"""Job registry for vision worker jobs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel
from sqlmodel import Session

from jobs.block_overlay_generate import (
    BlockOverlayGeneratePayload,
    run_block_overlay_generate_job,
)
from jobs.change_detect import (
    ComputeChangesPayload,
    run_compute_changes_job,
)
from jobs.change_detect import (
    resolve_overlay_job_id as resolve_changes_overlay_job_id,
)
from jobs.clash_detect import (
    ComputeClashesPayload,
    run_compute_clashes_job,
)
from jobs.clash_detect import (
    resolve_overlay_job_id as resolve_clashes_overlay_job_id,
)
from jobs.drawing_overlay_generate import (
    DrawingOverlayGeneratePayload,
    run_drawing_overlay_generate_job,
)
from jobs.drawing_preprocess import DrawingJobPayload, run_drawing_job
from jobs.envelope import JobEnvelope
from jobs.sheet_overlay_generate import (
    SheetOverlayGeneratePayload,
    run_sheet_overlay_generate_job,
)
from jobs.sheet_preprocess import SheetJobPayload, run_sheet_job
from jobs.types import JobType

PayloadT = TypeVar("PayloadT", bound=BaseModel)


@dataclass(frozen=True)
class JobSpec(Generic[PayloadT]):
    job_type: str
    payload_model: type[PayloadT]
    handler: Callable[[Session, PayloadT, str | None, JobEnvelope], None]
    log_context: Callable[[PayloadT], dict[str, str | None]] | None = None


JOB_SPECS: dict[str, JobSpec[Any]] = {
    JobType.DRAWING_PREPROCESS: JobSpec(
        job_type=JobType.DRAWING_PREPROCESS,
        payload_model=DrawingJobPayload,
        handler=run_drawing_job,
        log_context=lambda payload: {"drawing_id": payload.drawing_id},
    ),
    JobType.SHEET_PREPROCESS: JobSpec(
        job_type=JobType.SHEET_PREPROCESS,
        payload_model=SheetJobPayload,
        handler=run_sheet_job,
        log_context=lambda payload: {"sheet_id": payload.sheet_id},
    ),
    JobType.DRAWING_OVERLAY_GENERATE: JobSpec(
        job_type=JobType.DRAWING_OVERLAY_GENERATE,
        payload_model=DrawingOverlayGeneratePayload,
        handler=run_drawing_overlay_generate_job,
        log_context=lambda payload: {"drawing_id": payload.drawing_a_id},
    ),
    JobType.SHEET_OVERLAY_GENERATE: JobSpec(
        job_type=JobType.SHEET_OVERLAY_GENERATE,
        payload_model=SheetOverlayGeneratePayload,
        handler=run_sheet_overlay_generate_job,
        log_context=lambda payload: {"sheet_id": payload.sheet_a_id},
    ),
    JobType.BLOCK_OVERLAY_GENERATE: JobSpec(
        job_type=JobType.BLOCK_OVERLAY_GENERATE,
        payload_model=BlockOverlayGeneratePayload,
        handler=run_block_overlay_generate_job,
        log_context=lambda payload: {"block_id": payload.block_a_id},
    ),
    JobType.OVERLAY_CHANGE_DETECT: JobSpec(
        job_type=JobType.OVERLAY_CHANGE_DETECT,
        payload_model=ComputeChangesPayload,
        handler=run_compute_changes_job,
        log_context=lambda payload: {"overlay_id": payload.overlay_id},
    ),
    JobType.OVERLAY_CLASH_DETECT: JobSpec(
        job_type=JobType.OVERLAY_CLASH_DETECT,
        payload_model=ComputeClashesPayload,
        handler=run_compute_clashes_job,
        log_context=lambda payload: {"overlay_id": payload.overlay_id},
    ),
}
