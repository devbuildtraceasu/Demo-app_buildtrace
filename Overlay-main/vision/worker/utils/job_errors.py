"""Job error classification helpers."""

from __future__ import annotations

from pydantic import ValidationError

PERMANENT_JOB_ERRORS = (ValidationError, ValueError, FileNotFoundError)


def is_permanent_job_error(error: BaseException) -> bool:
    return isinstance(error, PERMANENT_JOB_ERRORS)
