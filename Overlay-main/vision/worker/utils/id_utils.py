"""ID helpers aligned with Prisma defaults."""

from __future__ import annotations

import secrets
import time

_BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def _base36_encode(value: int) -> str:
    if value == 0:
        return "0"
    chars = []
    while value:
        value, remainder = divmod(value, 36)
        chars.append(_BASE36_ALPHABET[remainder])
    return "".join(reversed(chars))


def generate_cuid() -> str:
    """Generate a cuid-like identifier compatible with Prisma's string IDs."""
    timestamp_ms = int(time.time() * 1000)
    random_bits = secrets.randbits(80)
    combined = (timestamp_ms << 80) | random_bits
    encoded = _base36_encode(combined).rjust(24, "0")[-24:]
    return f"c{encoded}"
