"""Job runner for handling vision job envelopes."""

from __future__ import annotations

from typing import Any

import clients.db as db
from jobs.envelope import JobEnvelope
from jobs.registry import JOB_SPECS
from utils.log_utils import log_job_received


class JobRunner:
    def __init__(self, *, logger) -> None:
        self.logger = logger

    def run_message(
        self,
        data: dict[str, Any],
        *,
        message_id: str,
        job_type_hint: str | None = None,
    ) -> None:
        envelope = JobEnvelope.from_message(data, job_type_hint=job_type_hint)
        if job_type_hint and envelope.job_type != job_type_hint:
            raise ValueError(
                f"Job type mismatch: expected {job_type_hint}, got {envelope.job_type}"
            )

        spec = JOB_SPECS.get(envelope.job_type)
        if not spec:
            raise ValueError(f"Unsupported job type: {envelope.job_type}")

        payload = spec.payload_model(**envelope.payload)
        log_fields = spec.log_context(payload) if spec.log_context else {}
        log_job_received(self.logger, envelope.job_type, message_id, **log_fields)

        with db.get_session() as session:
            spec.handler(session, payload, message_id, envelope)
