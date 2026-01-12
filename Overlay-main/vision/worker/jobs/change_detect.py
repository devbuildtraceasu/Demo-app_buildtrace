"""Change detection job handler.

This module handles AI-powered change detection from overlay images,
including trade classification and cost/schedule impact estimation.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field
from sqlmodel import Session

from clients.storage import get_storage_client
from config import config
from jobs.envelope import JobEnvelope
from jobs.types import JobType
from models import Block, Job, JobStatus, Overlay
from utils.id_utils import generate_cuid
from utils.job_events import append_job_event_if_missing, create_job_event
from utils.log_utils import log_job_completed, log_job_started, log_phase
from utils.storage_utils import extract_remote_path

logger = logging.getLogger(__name__)


class ChangeDetectPayload(BaseModel):
    """Input payload for change detection job messages."""

    model_config = {"extra": "forbid"}

    overlay_id: str = Field(..., description="UUID of the overlay to analyze")
    include_cost_estimate: bool = Field(default=True, description="Include cost/schedule estimates")


class DetectedChange(BaseModel):
    """A single detected change."""

    type: str  # "added", "removed", "modified"
    title: str
    description: str | None = None
    bounds: dict[str, float] | None = None  # {"xmin": 0, "ymin": 0, "xmax": 100, "ymax": 100}
    trade: str | None = None
    discipline: str | None = None
    estimated_cost: str | None = None
    schedule_impact: str | None = None
    confidence: float = 0.0


class ChangeDetectionResult(BaseModel):
    """Result from change detection."""

    changes: list[DetectedChange]
    total_cost_impact: str | None = None
    total_schedule_impact: str | None = None
    biggest_cost_driver: str | None = None
    analysis_summary: str | None = None


CHANGE_DETECTION_PROMPT = """You are an expert construction document analyst. Analyze this overlay comparison image where:
- RED areas indicate elements that were REMOVED (present in old drawing, absent in new)
- GREEN areas indicate elements that were ADDED (absent in old drawing, present in new)
- GRAY/unchanged areas indicate elements that remain the same

For each significant change detected:
1. Classify the type: "added", "removed", or "modified"
2. Identify the trade/discipline (Architectural, Structural, Mechanical, Electrical, Plumbing, Fire Protection, etc.)
3. Provide a descriptive title
4. Estimate the approximate bounding box location (as percentages: 0-100 for x and y)
5. Estimate the cost impact (in USD, use ranges like "$5,000 - $10,000")
6. Estimate the schedule impact (in days, like "+2 days" or "-1 day")

Focus on significant changes that would require construction coordination or cost impact.
Ignore minor drafting changes or text revisions unless they affect construction.

Respond with a JSON object containing:
{
  "changes": [
    {
      "type": "added" | "removed" | "modified",
      "title": "Brief description",
      "description": "Detailed explanation",
      "bounds": {"xmin": 0, "ymin": 0, "xmax": 100, "ymax": 100},
      "trade": "Trade name",
      "discipline": "Discipline",
      "estimated_cost": "$X,XXX - $X,XXX",
      "schedule_impact": "+X days",
      "confidence": 0.0-1.0
    }
  ],
  "total_cost_impact": "$XX,XXX",
  "total_schedule_impact": "+X days",
  "biggest_cost_driver": "Description of biggest cost driver",
  "analysis_summary": "Brief summary of all changes"
}
"""


def _encode_image_for_openai(image_bytes: bytes) -> str:
    """Encode image bytes to base64 for OpenAI API."""
    import base64
    return base64.b64encode(image_bytes).decode("utf-8")


def _analyze_overlay_with_openai(
    overlay_bytes: bytes,
    include_cost_estimate: bool = True,
) -> ChangeDetectionResult:
    """Analyze overlay image using OpenAI Vision API.

    Args:
        overlay_bytes: PNG bytes of the overlay image
        include_cost_estimate: Whether to include cost/schedule estimates

    Returns:
        ChangeDetectionResult with detected changes and estimates
    """
    client = OpenAI(api_key=config.openai_api_key)

    prompt = CHANGE_DETECTION_PROMPT
    if not include_cost_estimate:
        prompt += "\n\nDo not include cost or schedule estimates."

    image_base64 = _encode_image_for_openai(overlay_bytes)

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an expert construction document analyst specializing in change detection and cost estimation.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content
    if not response_text:
        raise RuntimeError("No response from OpenAI")

    result_data = json.loads(response_text)

    # Parse changes
    changes = []
    for change_data in result_data.get("changes", []):
        changes.append(
            DetectedChange(
                type=change_data.get("type", "modified"),
                title=change_data.get("title", "Unnamed Change"),
                description=change_data.get("description"),
                bounds=change_data.get("bounds"),
                trade=change_data.get("trade"),
                discipline=change_data.get("discipline"),
                estimated_cost=change_data.get("estimated_cost"),
                schedule_impact=change_data.get("schedule_impact"),
                confidence=change_data.get("confidence", 0.5),
            )
        )

    return ChangeDetectionResult(
        changes=changes,
        total_cost_impact=result_data.get("total_cost_impact"),
        total_schedule_impact=result_data.get("total_schedule_impact"),
        biggest_cost_driver=result_data.get("biggest_cost_driver"),
        analysis_summary=result_data.get("analysis_summary"),
    )


def run_change_detect_job(
    session: Session,
    payload: ChangeDetectPayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    """Execute change detection job."""
    job_type = JobType.CHANGE_DETECT
    job = session.get(Job, envelope.job_id)
    if not job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] change detect job {job.id} canceled before start")
        return

    metadata = {"overlayId": payload.overlay_id}

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
        metadata=metadata,
    )
    job.events = append_job_event_if_missing(job.events, started_event)
    session.add(job)
    session.commit()

    try:
        # Load overlay
        overlay = session.get(Overlay, payload.overlay_id)
        if not overlay:
            raise ValueError(f"Overlay {payload.overlay_id} not found")

        if not overlay.uri:
            raise ValueError("Overlay missing image URI for change detection")

        # Download overlay image
        storage_client = get_storage_client()
        with log_phase(logger, "Download overlay image", overlay_id=payload.overlay_id):
            remote_path = extract_remote_path(overlay.uri)
            overlay_bytes = storage_client.download_to_bytes(remote_path)

        # Analyze with AI
        with log_phase(logger, "Analyze changes with AI", overlay_id=payload.overlay_id):
            result = _analyze_overlay_with_openai(
                overlay_bytes,
                include_cost_estimate=payload.include_cost_estimate,
            )

        # Update overlay with detected changes
        overlay.changes = [
            {
                "id": generate_cuid(),
                "type": c.type,
                "title": c.title,
                "description": c.description,
                "bounds": c.bounds,
                "trade": c.trade,
                "discipline": c.discipline,
                "estimated_cost": c.estimated_cost,
                "schedule_impact": c.schedule_impact,
                "confidence": c.confidence,
            }
            for c in result.changes
        ]
        overlay.summary = {
            "total_cost_impact": result.total_cost_impact,
            "total_schedule_impact": result.total_schedule_impact,
            "biggest_cost_driver": result.biggest_cost_driver,
            "analysis_summary": result.analysis_summary,
            "change_count": len(result.changes),
        }
        overlay.updated_at = datetime.now(UTC)
        session.add(overlay)

        # Complete job
        completed_metadata = {
            **metadata,
            "changeCount": len(result.changes),
            "totalCostImpact": result.total_cost_impact,
            "totalScheduleImpact": result.total_schedule_impact,
        }

        job.status = JobStatus.COMPLETED
        job.updated_at = datetime.now(UTC)
        completed_event = create_job_event(
            job_type=job_type,
            job_id=str(job.id),
            status=JobStatus.COMPLETED.value,
            event_type="completed",
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
            job_id=str(envelope.job_id),
        )

    except Exception as error:
        session.rollback()
        job.status = JobStatus.FAILED
        job.updated_at = datetime.now(UTC)
        failed_event = create_job_event(
            job_type=job_type,
            job_id=str(job.id),
            status=JobStatus.FAILED.value,
            event_type="failed",
            metadata={
                **metadata,
                "errorType": type(error).__name__,
                "errorMessage": str(error),
            },
        )
        job.events = append_job_event_if_missing(job.events, failed_event)
        session.add(job)
        session.commit()
        raise


# Aliases for registry compatibility
ComputeChangesPayload = ChangeDetectPayload
run_compute_changes_job = run_change_detect_job


def resolve_overlay_job_id(session: Session, payload: ComputeChangesPayload) -> str | None:
    """Resolve the overlay job ID for change detection."""
    overlay = session.get(Overlay, payload.overlay_id)
    if overlay:
        return overlay.job_id
    return None
