"""Storage URI helpers for worker jobs."""

from __future__ import annotations

from urllib.parse import unquote, urlparse


def extract_remote_path(uri: str) -> str:
    """Extract the bucket-relative path from a storage URI."""
    if not uri:
        raise ValueError("Storage URI is empty")

    if uri.startswith("gs://") or uri.startswith("s3://"):
        parts = uri.split("/", 3)
        if len(parts) < 4 or not parts[3]:
            raise ValueError(f"Invalid storage URI: {uri}")
        return parts[3]

    if uri.startswith("http://") or uri.startswith("https://"):
        parsed = urlparse(uri)
        path = parsed.path.lstrip("/")
        if not path or "/" not in path:
            raise ValueError(f"Invalid storage URI: {uri}")
        _, key = path.split("/", 1)
        if not key:
            raise ValueError(f"Invalid storage URI: {uri}")
        return unquote(key)

    raise ValueError(f"Unsupported storage URI format: {uri}")
