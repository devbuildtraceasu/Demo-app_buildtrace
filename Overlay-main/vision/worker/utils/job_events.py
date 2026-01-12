"""Helpers for persisting job event timelines."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4


def create_job_event(
    *,
    job_type: str,
    job_id: str,
    status: str,
    event_type: str,
    drawing_id: Optional[str] = None,
    sheet_id: Optional[str] = None,
    block_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    llm_usage: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Create a job event dict for the events timeline.

    Args:
        job_type: Job type identifier (e.g., "vision.sheet.preprocess")
        job_id: Job UUID
        status: Current job status
        event_type: Event type ("created", "started", "completed", "failed")
        drawing_id: Optional drawing UUID
        sheet_id: Optional sheet UUID
        block_id: Optional block UUID
        metadata: Optional custom metadata dict
        llm_usage: Optional LLM usage dict from LLMUsage.to_event_dict()
            Format: {"models": {...}, "totalCostUsd": float}

    Returns:
        Event dict for appending to Job.events
    """
    event: Dict[str, Any] = {
        "id": str(uuid4()),
        "jobType": job_type,
        "jobId": job_id,
        "status": status,
        "eventType": event_type,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "drawingId": drawing_id,
        "sheetId": sheet_id,
        "blockId": block_id,
        "metadata": metadata,
    }
    if llm_usage is not None:
        event["llmUsage"] = llm_usage
    return event


def has_event_type(current: Any, event_type: str) -> bool:
    if not isinstance(current, list):
        return False
    for item in current:
        if isinstance(item, dict) and item.get("eventType") == event_type:
            return True
    return False


def append_job_event(current: Any, event: Dict[str, Any]) -> list[Dict[str, Any]]:
    if isinstance(current, list):
        return [*current, event]
    return [event]


def append_job_event_if_missing(current: Any, event: Dict[str, Any]) -> Any:
    if has_event_type(current, event.get("eventType")):
        return current
    return append_job_event(current, event)
