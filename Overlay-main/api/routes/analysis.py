"""AI Analysis routes for change detection and cost estimation."""

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.config import settings
from api.dependencies import CurrentUser, OptionalUser, SessionDep, get_pubsub_client
from api.routes.jobs import Job  # Import existing Job model

router = APIRouter()


class DetectChangesRequest(BaseModel):
    """Request to detect changes in an overlay."""

    overlay_id: str = Field(..., description="ID of the overlay to analyze")
    include_cost_estimate: bool = Field(default=True, description="Include cost/schedule estimates")


class CostAnalysisRequest(BaseModel):
    """Request for cost analysis."""

    overlay_id: str = Field(..., description="ID of the overlay to analyze")
    project_id: str = Field(..., description="ID of the project")


class AnalysisJobResponse(BaseModel):
    """Response for analysis job submission."""

    job_id: str
    overlay_id: str
    status: str = "queued"
    message: str


def generate_cuid() -> str:
    """Generate a CUID-like ID."""
    import secrets
    import time

    timestamp = hex(int(time.time() * 1000))[2:]
    random_part = secrets.token_hex(8)
    return f"c{timestamp}{random_part}"[:25]


@router.post("/detect-changes", response_model=AnalysisJobResponse)
async def detect_changes(
    request: DetectChangesRequest,
    session: SessionDep,
    user: CurrentUser,
):
    """Submit a change detection job for an overlay.

    Uses AI vision to identify added/removed/modified elements
    and classify them by trade with cost/schedule estimates.
    """
    job_id = generate_cuid()

    # Create job record in database first
    job = Job(
        id=job_id,
        type="vision.overlay.change.detect",
        target_type="overlay",
        target_id=request.overlay_id,
        status="Queued",
        payload={
            "overlay_id": request.overlay_id,
            "include_cost_estimate": request.include_cost_estimate,
        },
    )
    session.add(job)
    session.commit()

    # Submit job to Pub/Sub
    try:
        pubsub = get_pubsub_client()
        topic_path = pubsub.topic_path(settings.pubsub_project_id, settings.vision_topic)

        job_payload = {
            "type": "vision.overlay.change.detect",
            "id": job_id,
            "payload": {
                "overlayId": request.overlay_id,
                "includeCostEstimate": request.include_cost_estimate,
            },
        }

        pubsub.publish(
            topic_path,
            json.dumps(job_payload).encode("utf-8"),
            type="vision.overlay.change.detect",
        )
    except Exception as e:
        import logging

        logging.warning(f"Failed to publish change detection job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit change detection job",
        )

    return AnalysisJobResponse(
        job_id=job_id,
        overlay_id=request.overlay_id,
        status="queued",
        message="Change detection job submitted. Results will be available shortly.",
    )


@router.post("/cost-analysis", response_model=AnalysisJobResponse)
async def analyze_costs(
    request: CostAnalysisRequest,
    session: SessionDep,
    user: CurrentUser,
):
    """Submit a cost analysis job for an overlay.

    Analyzes detected changes to estimate cost and schedule impact
    with trade-by-trade breakdown and recommendations.
    """
    job_id = generate_cuid()

    # Submit job to Pub/Sub
    try:
        pubsub = get_pubsub_client()
        topic_path = pubsub.topic_path(settings.pubsub_project_id, settings.vision_topic)

        job_payload = {
            "type": "vision.overlay.cost.analysis",
            "id": job_id,
            "payload": {
                "overlayId": request.overlay_id,
                "projectId": request.project_id,
                "includeSchedule": True,
            },
        }

        pubsub.publish(
            topic_path,
            json.dumps(job_payload).encode("utf-8"),
            type="vision.overlay.cost.analysis",
        )
    except Exception as e:
        import logging

        logging.warning(f"Failed to publish cost analysis job: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit cost analysis job",
        )

    return AnalysisJobResponse(
        job_id=job_id,
        overlay_id=request.overlay_id,
        status="queued",
        message="Cost analysis job submitted. Results will be available shortly.",
    )


@router.get("/summary/{overlay_id}")
async def get_analysis_summary(
    overlay_id: str,
    session: SessionDep,
    user: OptionalUser = None,
):
    """Get the analysis summary for an overlay.

    Returns detected changes and cost analysis if available.
    """
    from sqlmodel import select
    
    # Import Overlay model - need to query the database
    try:
        from sqlalchemy import text
        
        # Query the overlay directly
        result = session.execute(
            text("SELECT id, changes, summary FROM overlays WHERE id = :overlay_id"),
            {"overlay_id": overlay_id}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Overlay {overlay_id} not found",
            )
        
        overlay_id, changes, summary = row
        
        return {
            "overlay_id": overlay_id,
            "status": "completed" if changes else "pending",
            "changes": changes or [],
            "summary": summary,
            "cost_analysis": {
                "total_cost_impact": summary.get("total_cost_impact") if summary else None,
                "total_schedule_impact": summary.get("total_schedule_impact") if summary else None,
                "biggest_cost_driver": summary.get("biggest_cost_driver") if summary else None,
                "analysis_summary": summary.get("analysis_summary") if summary else None,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Error fetching analysis summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch analysis summary",
        )

