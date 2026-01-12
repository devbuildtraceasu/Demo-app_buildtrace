"""Helpers for building naive overlay change/clash reports."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import cv2
import numpy as np
from sqlmodel import Session, select

from clients.storage import get_storage_client
from lib.sift_alignment import _load_image_from_bytes
from models import Overlay
from utils.log_utils import log_storage_download
from utils.storage_utils import extract_remote_path

MIN_REGION_AREA = 120
CHANGE_MASK_THRESHOLD = 200
MORPH_KERNEL_SIZE = 3


def resolve_overlay_for_job(
    session: Session,
    overlay_job_id: str | None = None,
    *,
    overlay_id: str | None = None,
) -> Overlay | None:
    if overlay_id:
        overlay = session.get(Overlay, overlay_id)
        if overlay and overlay.deleted_at is None:
            return overlay
    if not overlay_job_id:
        return None
    return session.exec(
        select(Overlay).where(
            Overlay.job_id == overlay_job_id,
            Overlay.deleted_at.is_(None),
        )
    ).first()


def load_overlay_images(
    overlay: Overlay,
    *,
    logger,
) -> dict[str, np.ndarray | None]:
    storage_client = get_storage_client()
    return {
        "addition": _download_image(storage_client, overlay.addition_uri, logger=logger),
        "deletion": _download_image(storage_client, overlay.deletion_uri, logger=logger),
        "overlay": _download_image(storage_client, overlay.uri, logger=logger),
    }


def _download_image(storage_client, uri: str | None, *, logger) -> np.ndarray | None:
    if not uri:
        return None
    remote_path = extract_remote_path(uri)
    start = time.time()
    data = storage_client.download_to_bytes(remote_path)
    log_storage_download(
        logger,
        remote_path,
        size_bytes=len(data),
        duration_ms=int((time.time() - start) * 1000),
    )
    return _load_image_from_bytes(data)


def extract_regions(
    image: np.ndarray | None,
    *,
    label: str,
    min_area: int = MIN_REGION_AREA,
) -> list[dict[str, Any]]:
    if image is None:
        return []
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    mask = gray < CHANGE_MASK_THRESHOLD
    if not np.any(mask):
        return []
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE))
    cleaned = cv2.morphologyEx(mask.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel, iterations=1)
    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        cleaned, connectivity=8
    )
    regions: list[dict[str, Any]] = []
    for label_idx in range(1, num_labels):
        x, y, w, h, area = stats[label_idx]
        if area < min_area:
            continue
        regions.append(
            {
                "description": f"{label} region",
                "xMin": int(x),
                "xMax": int(x + w),
                "yMin": int(y),
                "yMax": int(y + h),
            }
        )
    return regions


def build_change_report(
    *,
    overlay_id: str,
    addition_items: list[dict[str, Any]],
    deletion_items: list[dict[str, Any]],
    addition_uri: str | None,
    deletion_uri: str | None,
) -> dict[str, Any]:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    addition_count = len(addition_items)
    deletion_count = len(deletion_items)
    total_count = addition_count + deletion_count
    if total_count == 0:
        summary = "No changes detected in this overlay."
    else:
        summary = f"Detected {addition_count} additions and {deletion_count} deletions."
    report_lines = [
        "## Change report",
        "",
        f"{summary}",
        "",
        "### What to review",
        "- Focus on clusters of additions/deletions rather than isolated pixels.",
        "- Confirm whether the marked areas represent actual design changes.",
        "",
        "### Notes",
        "- Automated detection uses overlay imagery and may include minor artifacts.",
        f"- Generated: {timestamp}",
        f"- Overlay image available: {'Yes' if addition_uri or deletion_uri else 'No'}",
    ]
    return {
        "report": "\n".join(report_lines),
        "changes": [*addition_items, *deletion_items],
    }


def build_clash_report(
    *,
    overlay_id: str,
    clash_items: list[dict[str, Any]],
    overlay_uri: str | None,
    addition_uri: str | None,
    deletion_uri: str | None,
) -> dict[str, Any]:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    clash_count = len(clash_items)
    if clash_count == 0:
        summary = "No potential clashes detected in this overlay."
    else:
        summary = f"Detected {clash_count} potential clashes to review."
    report_lines = [
        "## Clash report",
        "",
        f"{summary}",
        "",
        "### What to review",
        "- Validate clashes visually in the overlay before taking action.",
        "- Prioritize areas where additions overlap deletions or dense geometry.",
        "",
        "### Notes",
        "- Automated detection flags candidates; confirm in the overlay view.",
        f"- Generated: {timestamp}",
        f"- Overlay image available: {'Yes' if overlay_uri else 'No'}",
    ]
    return {
        "report": "\n".join(report_lines),
        "clashes": clash_items,
    }
