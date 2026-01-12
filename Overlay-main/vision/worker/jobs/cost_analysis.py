"""Cost analysis job handler.

This module handles AI-powered cost and schedule impact analysis
for construction drawing changes, including trade breakdown and
biggest cost driver identification.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from clients.storage import get_storage_client
from config import config
from jobs.envelope import JobEnvelope
from jobs.types import JobType
from models import Job, JobStatus, Overlay, Sheet, Block
from utils.id_utils import generate_cuid
from utils.job_events import append_job_event_if_missing, create_job_event
from utils.log_utils import log_job_completed, log_job_started, log_phase
from utils.storage_utils import extract_remote_path

logger = logging.getLogger(__name__)


class CostAnalysisPayload(BaseModel):
    """Input payload for cost analysis job messages."""

    model_config = {"extra": "forbid"}

    overlay_id: str = Field(..., description="UUID of the overlay to analyze")
    project_id: str = Field(..., description="UUID of the project")
    include_schedule: bool = Field(default=True, description="Include schedule impact analysis")


class TradeBreakdown(BaseModel):
    """Cost breakdown by trade."""

    trade: str
    item_count: int
    total_cost: str
    schedule_impact: str
    items: list[dict[str, Any]]


class CostAnalysisResult(BaseModel):
    """Result from cost analysis."""

    total_cost_impact: str
    total_schedule_impact: str
    biggest_cost_driver: str
    trade_breakdown: list[TradeBreakdown]
    recommendations: list[str]
    risk_factors: list[str]
    executive_summary: str


COST_ANALYSIS_PROMPT = """You are an expert construction cost estimator. Based on the detected changes in a construction drawing revision, provide a detailed cost and schedule impact analysis.

Here are the detected changes:
{changes_json}

Project context (if available):
{project_context}

Provide a comprehensive analysis including:
1. Total cost impact (sum of all changes)
2. Total schedule impact (critical path analysis)
3. Biggest cost driver identification
4. Trade-by-trade breakdown
5. Recommendations for cost optimization
6. Risk factors that could affect estimates

Use realistic construction cost data for the US market.
Consider labor, materials, equipment, and overhead.
Account for potential coordination impacts between trades.

Respond with a JSON object:
{{
  "total_cost_impact": "$XX,XXX",
  "total_schedule_impact": "+X days",
  "biggest_cost_driver": "Description of the biggest cost item",
  "trade_breakdown": [
    {{
      "trade": "Trade name",
      "item_count": X,
      "total_cost": "$X,XXX",
      "schedule_impact": "+X days",
      "items": [
        {{"title": "Item", "cost": "$X,XXX", "schedule": "+X days"}}
      ]
    }}
  ],
  "recommendations": [
    "Recommendation 1",
    "Recommendation 2"
  ],
  "risk_factors": [
    "Risk 1",
    "Risk 2"
  ],
  "executive_summary": "Brief summary for project stakeholders"
}}
"""


def _analyze_costs_with_openai(
    changes: list[dict[str, Any]],
    project_context: dict[str, Any] | None = None,
) -> CostAnalysisResult:
    """Analyze costs using OpenAI API.

    Args:
        changes: List of detected changes from change detection
        project_context: Optional project context (location, type, etc.)

    Returns:
        CostAnalysisResult with detailed analysis
    """
    client = OpenAI(api_key=config.openai_api_key)

    changes_json = json.dumps(changes, indent=2)
    context_str = json.dumps(project_context, indent=2) if project_context else "Not available"

    prompt = COST_ANALYSIS_PROMPT.format(
        changes_json=changes_json,
        project_context=context_str,
    )

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are an expert construction cost estimator with 20+ years of experience in commercial and industrial construction.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        max_tokens=4096,
        response_format={"type": "json_object"},
    )

    response_text = response.choices[0].message.content
    if not response_text:
        raise RuntimeError("No response from OpenAI")

    result_data = json.loads(response_text)

    # Parse trade breakdown
    trade_breakdown = []
    for trade_data in result_data.get("trade_breakdown", []):
        trade_breakdown.append(
            TradeBreakdown(
                trade=trade_data.get("trade", "Unknown"),
                item_count=trade_data.get("item_count", 0),
                total_cost=trade_data.get("total_cost", "$0"),
                schedule_impact=trade_data.get("schedule_impact", "0 days"),
                items=trade_data.get("items", []),
            )
        )

    return CostAnalysisResult(
        total_cost_impact=result_data.get("total_cost_impact", "$0"),
        total_schedule_impact=result_data.get("total_schedule_impact", "0 days"),
        biggest_cost_driver=result_data.get("biggest_cost_driver", "Unknown"),
        trade_breakdown=trade_breakdown,
        recommendations=result_data.get("recommendations", []),
        risk_factors=result_data.get("risk_factors", []),
        executive_summary=result_data.get("executive_summary", ""),
    )


def run_cost_analysis_job(
    session: Session,
    payload: CostAnalysisPayload,
    message_id: str | None,
    envelope: JobEnvelope,
) -> None:
    """Execute cost analysis job."""
    job_type = JobType.COST_ANALYSIS
    job = session.get(Job, envelope.job_id)
    if not job:
        raise ValueError(f"Job {envelope.job_id} not found")

    if job.status == JobStatus.CANCELED:
        logger.info(f"[job.canceled] cost analysis job {job.id} canceled before start")
        return

    metadata = {
        "overlayId": payload.overlay_id,
        "projectId": payload.project_id,
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
        metadata=metadata,
    )
    job.events = append_job_event_if_missing(job.events, started_event)
    session.add(job)
    session.commit()

    try:
        # Load overlay and its changes
        overlay = session.get(Overlay, payload.overlay_id)
        if not overlay:
            raise ValueError(f"Overlay {payload.overlay_id} not found")

        changes = overlay.changes or []
        if not changes:
            logger.warning(f"[cost_analysis] No changes detected for overlay {payload.overlay_id}")

        # Get project context (if available)
        project_context = None
        if job.project_id:
            # Could fetch project details here
            project_context = {"project_id": job.project_id}

        # Analyze costs with AI
        with log_phase(logger, "Analyze costs with AI", overlay_id=payload.overlay_id):
            result = _analyze_costs_with_openai(changes, project_context)

        # Update overlay with cost analysis
        overlay.summary = {
            **(overlay.summary or {}),
            "cost_analysis": {
                "total_cost_impact": result.total_cost_impact,
                "total_schedule_impact": result.total_schedule_impact,
                "biggest_cost_driver": result.biggest_cost_driver,
                "trade_breakdown": [
                    {
                        "trade": t.trade,
                        "item_count": t.item_count,
                        "total_cost": t.total_cost,
                        "schedule_impact": t.schedule_impact,
                        "items": t.items,
                    }
                    for t in result.trade_breakdown
                ],
                "recommendations": result.recommendations,
                "risk_factors": result.risk_factors,
                "executive_summary": result.executive_summary,
                "analyzed_at": datetime.now(UTC).isoformat(),
            },
        }
        overlay.updated_at = datetime.now(UTC)
        session.add(overlay)

        # Complete job
        completed_metadata = {
            **metadata,
            "totalCostImpact": result.total_cost_impact,
            "totalScheduleImpact": result.total_schedule_impact,
            "tradeCount": len(result.trade_breakdown),
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

