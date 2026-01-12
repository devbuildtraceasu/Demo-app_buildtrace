"""Job message envelope for vision worker jobs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from utils.case_utils import to_snake_case


class JobEnvelope(BaseModel):
    model_config = {"extra": "ignore", "populate_by_name": True}

    version: str = Field(default="v1")
    job_type: str = Field(alias="type")
    job_id: str = Field(alias="id")
    context: dict[str, Any] | None = None
    payload: dict[str, Any]
    metadata: dict[str, Any] | None = None

    @classmethod
    def from_message(
        cls,
        data: dict[str, Any],
        *,
        job_type_hint: str | None = None,
    ) -> "JobEnvelope":
        if "type" not in data or "id" not in data:
            raise ValueError("Job payload missing envelope metadata")
        envelope = cls.model_validate(data)
        payload = to_snake_case(envelope.payload)
        context = to_snake_case(envelope.context) if envelope.context else None
        return envelope.model_copy(update={"payload": payload, "context": context})


def build_job_envelope(
    *,
    job_type: str,
    job_id: str,
    payload: dict[str, Any],
    context: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    envelope = JobEnvelope(
        job_type=job_type,
        job_id=job_id,
        payload=payload,
        context=context,
        metadata=metadata,
    )
    return envelope.model_dump(by_alias=True, exclude_none=True)
