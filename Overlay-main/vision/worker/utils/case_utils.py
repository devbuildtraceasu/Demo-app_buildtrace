"""Key conversion helpers for job envelopes."""

from __future__ import annotations

import re
from typing import Any


_CAMEL_RE = re.compile(r"(?<!^)(?=[A-Z])")


def to_snake_case(value: Any) -> Any:
    """Recursively convert dict keys from camelCase to snake_case."""
    if isinstance(value, dict):
        return {to_snake_key(key): to_snake_case(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_snake_case(item) for item in value]
    return value


def to_snake_key(key: Any) -> str:
    if not isinstance(key, str):
        return str(key)
    normalized = key.replace("-", "_")
    return _CAMEL_RE.sub("_", normalized).lower()
