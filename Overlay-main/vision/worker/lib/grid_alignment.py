"""Grid-based image alignment using Gemini API for grid callout detection.

This module provides grid-based alignment for construction drawings that have
structural grid reference callouts. Uses Gemini API to detect grid callout
bounding boxes, then matches grid lines between images for alignment.

Key functions:
- align_with_grid(): Main entry point for grid-based alignment
- detect_callouts_with_gemini(): Detect grid callouts using Gemini API
- match_grid_lines(): Match grid lines between two images
"""

import gc
import io
import json
import logging
import os
from pathlib import Path
from typing import Literal

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from lib.sift_alignment import AlignmentStats, apply_transformation

logger = logging.getLogger(__name__)


# =============================================================================
# Pydantic Models
# =============================================================================


class DetectedGridLine(BaseModel):
    """A detected grid line from callout detection."""

    orientation: Literal["horizontal", "vertical"]
    position: float  # y-coordinate for horizontal, x for vertical
    label: str  # Grid label (e.g., "A", "1", "D.5")


class GridMatch(BaseModel):
    """A matched grid line between two images."""

    label: str
    orientation: Literal["horizontal", "vertical"]
    position_a: float  # Position in image A
    position_b: float  # Position in image B


class AlignmentTransform(BaseModel):
    """Affine transformation calculated from grid matches."""

    scale_x: float
    scale_y: float
    translate_x: float
    translate_y: float
    h_matches: int  # Horizontal grid matches used
    v_matches: int  # Vertical grid matches used


class GridCalloutBBox(BaseModel):
    """Bounding box for a grid callout detected by Gemini."""

    label: str = Field(description="The alphanumeric label inside the circle")
    xmin: int = Field(description="Left X coordinate (0-1000 normalized)")
    ymin: int = Field(description="Top Y coordinate (0-1000 normalized)")
    xmax: int = Field(description="Right X coordinate (0-1000 normalized)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000 normalized)")
    edge: str = Field(description="Which edge: 'top', 'bottom', 'left', 'right'")


class GridCalloutsResponse(BaseModel):
    """Response from Gemini grid callout detection."""

    callouts: list[GridCalloutBBox]


# =============================================================================
# Constants
# =============================================================================

# Note: GEMINI_API_KEY is loaded lazily from config to ensure .env is loaded first
GEMINI_MODEL = "gemini-3-pro-preview"


def _get_gemini_api_key() -> str | None:
    """Get Gemini API key from config (loads .env lazily)."""
    from config import config
    return config.gemini_api_key
TARGET_DPI = 100

GRID_SYSTEM_PROMPT = """You are an expert at analyzing architectural and construction drawings.

Your task is to identify and locate all GRID REFERENCE CALLOUTS (also called grid bubbles or grid markers) in this drawing.

Grid reference callouts are:
- Small circles (bubbles) located at the EDGES of the drawing
- Each circle contains a letter (A, B, C, etc.) or number (1, 2, 3, etc.) or decimal (D.5, 4.5)
- They mark the positions of structural grid lines
- Letters typically mark vertical grid lines (columns)
- Numbers typically mark horizontal grid lines (rows)

For each callout found, provide:
1. The label text inside the circle
2. A bounding box around the full circle (xmin, ymin, xmax, ymax) normalized to 0-1000.
3. Which edge of the drawing it's on (top, bottom, left, right)

IMPORTANT:
- Only detect the CIRCULAR GRID CALLOUTS, not other text or symbols
- Return coordinates normalized to a 1000x1000 grid
- Be thorough - find ALL grid callouts visible in the drawing
- The bounding box should be tight around the circle, not oversized.
- The bounding box should be a square in the absolute coordinate space of the image."""


# =============================================================================
# Grid Callout Detection
# =============================================================================


def detect_callouts_with_gemini(
    image_path: Path,
    width: int,
    height: int,
) -> list[tuple[str, tuple[int, int, int, int], str]]:
    """Detect grid callout bounding boxes using Gemini API.

    Args:
        image_path: Path to image file
        width: Original image width
        height: Original image height

    Returns:
        List of (label, (x1, y1, x2, y2), edge) tuples
        - label: Grid label (e.g., "A", "1", "D.5")
        - (x1, y1, x2, y2): Bounding box in original coordinates
        - edge: "top" | "bottom" | "left" | "right"

    Raises:
        RuntimeError: If Gemini API fails or GEMINI_API_KEY not configured
    """
    gemini_api_key = _get_gemini_api_key()
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY not configured")

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        raise RuntimeError("google-genai package not installed")

    # Load and downsample image for Gemini
    img = Image.open(image_path)
    scale = TARGET_DPI / 300.0
    img_small = img.resize(
        (int(img.width * scale), int(img.height * scale)),
        Image.Resampling.LANCZOS,
    )
    buffer = io.BytesIO()
    img_small.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    client = genai.Client(api_key=gemini_api_key)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(mime_type="image/png", data=png_bytes),
                        types.Part.from_text(text=GRID_SYSTEM_PROMPT),
                        types.Part.from_text(
                            text="Find all grid reference callouts in this construction drawing."
                        ),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GridCalloutsResponse,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
                media_resolution="MEDIA_RESOLUTION_HIGH",
                temperature=0.0,
            ),
        )

        parsed = GridCalloutsResponse(**json.loads(response.text))
        results = []
        for c in parsed.callouts:
            x1 = int(c.xmin * width / 1000)
            y1 = int(c.ymin * height / 1000)
            x2 = int(c.xmax * width / 1000)
            y2 = int(c.ymax * height / 1000)
            results.append((c.label, (x1, y1, x2, y2), c.edge))
        return results

    except Exception as e:
        raise RuntimeError(f"Gemini API error: {e}")


def _detect_circle_in_crop(
    crop: np.ndarray,
    min_radius: int,
    max_radius: int,
) -> tuple[int, int, int] | None:
    """Detect circle in cropped region using Hough circles.

    Returns (cx, cy, radius) or None if no circle found.
    """
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=min_radius * 2,
        param1=100,
        param2=30,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    if circles is None or len(circles[0]) == 0:
        return None
    c = np.uint16(np.around(circles[0][0]))
    return (int(c[0]), int(c[1]), int(c[2]))


def _detect_grid_line(
    gray: np.ndarray,
    cx: int,
    cy: int,
    radius: int,
    edge: str,
) -> tuple[str, float] | None:
    """Detect grid line touching circle.

    Returns (orientation, position) or None if no line found.
    """
    h, w = gray.shape
    search_dist = 300

    if edge in ["left", "right"]:
        orientation = "horizontal"
        y1, y2 = max(0, cy - radius - 20), min(h, cy + radius + 20)
        if edge == "left":
            x1, x2 = cx + radius - 10, min(w, cx + radius + search_dist)
        else:
            x1, x2 = max(0, cx - radius - search_dist), cx - radius + 10
    else:
        orientation = "vertical"
        x1, x2 = max(0, cx - radius - 20), min(w, cx + radius + 20)
        if edge == "top":
            y1, y2 = cy + radius - 10, min(h, cy + radius + search_dist)
        else:
            y1, y2 = max(0, cy - radius - search_dist), cy - radius + 10

    if x2 <= x1 or y2 <= y1:
        return None

    region = gray[y1:y2, x1:x2]
    if region.size == 0:
        return None

    edges = cv2.Canny(region, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 30, minLineLength=30, maxLineGap=20)

    if lines is None:
        return None

    for line in lines:
        lx1, ly1, lx2, ly2 = line[0]
        angle = np.degrees(np.arctan2(ly2 - ly1, lx2 - lx1))
        if orientation == "horizontal" and (abs(angle) < 20 or abs(abs(angle) - 180) < 20):
            return (orientation, float(cy))
        if orientation == "vertical" and abs(abs(angle) - 90) < 20:
            return (orientation, float(cx))

    return None


def _process_callout(
    full_image: np.ndarray,
    gray: np.ndarray,
    label: str,
    bbox: tuple[int, int, int, int],
    edge: str,
) -> DetectedGridLine | None:
    """Process a single callout to extract grid line.

    Args:
        full_image: Full image in BGR format
        gray: Grayscale version of full image
        label: Callout label
        bbox: Bounding box (x1, y1, x2, y2)
        edge: Edge where callout is located

    Returns:
        DetectedGridLine or None if detection fails
    """
    h, w = full_image.shape[:2]
    x1, y1, x2, y2 = bbox
    padding = 50

    crop_x1 = max(0, x1 - padding)
    crop_y1 = max(0, y1 - padding)
    crop_x2 = min(w, x2 + padding)
    crop_y2 = min(h, y2 + padding)
    crop = full_image[crop_y1:crop_y2, crop_x1:crop_x2]

    if crop.size == 0:
        return None

    bbox_w, bbox_h = x2 - x1, y2 - y1
    est_radius = min(bbox_w, bbox_h) // 2
    min_r, max_r = max(10, est_radius - 100), est_radius + 100

    circle = _detect_circle_in_crop(crop, min_r, max_r)
    if circle is None:
        # Fallback: use callout center as grid line position
        orientation = "horizontal" if edge in ["left", "right"] else "vertical"
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        position = float(center_y) if orientation == "horizontal" else float(center_x)
        return DetectedGridLine(orientation=orientation, position=position, label=label)

    cx_crop, cy_crop, radius = circle
    cx, cy = cx_crop + crop_x1, cy_crop + crop_y1

    # Try to detect grid line
    line_result = _detect_grid_line(gray, cx, cy, radius, edge)

    if line_result:
        orientation, position = line_result
        return DetectedGridLine(orientation=orientation, position=position, label=label)
    else:
        # Fallback: use callout center
        orientation = "horizontal" if edge in ["left", "right"] else "vertical"
        position = float(cy) if orientation == "horizontal" else float(cx)
        return DetectedGridLine(orientation=orientation, position=position, label=label)


def detect_grid_lines_from_image(
    image_path: Path,
    image_bgr: np.ndarray,
) -> list[DetectedGridLine]:
    """Detect grid lines in an image using Gemini + OpenCV.

    Args:
        image_path: Path to image file (for Gemini)
        image_bgr: Image in BGR format (for OpenCV)

    Returns:
        List of DetectedGridLine with orientation, position, and label

    Raises:
        RuntimeError: If Gemini API fails
    """
    h, w = image_bgr.shape[:2]

    gemini_results = detect_callouts_with_gemini(image_path, w, h)
    if not gemini_results:
        return []

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    grid_lines = []

    for label, bbox, edge in gemini_results:
        grid_line = _process_callout(image_bgr, gray, label, bbox, edge)
        if grid_line:
            grid_lines.append(grid_line)

    return grid_lines


# =============================================================================
# Grid Matching and Transformation
# =============================================================================


def match_grid_lines(
    lines_a: list[DetectedGridLine],
    lines_b: list[DetectedGridLine],
) -> list[GridMatch]:
    """Match grid lines between two images by label.

    Args:
        lines_a: Grid lines from image A
        lines_b: Grid lines from image B

    Returns:
        List of GridMatch for lines with matching labels
    """
    # Build lookup maps for image B
    b_horizontal = {line.label: line for line in lines_b if line.orientation == "horizontal"}
    b_vertical = {line.label: line for line in lines_b if line.orientation == "vertical"}

    matches = []
    for line_a in lines_a:
        if line_a.orientation == "horizontal" and line_a.label in b_horizontal:
            line_b = b_horizontal[line_a.label]
            matches.append(
                GridMatch(
                    label=line_a.label,
                    orientation="horizontal",
                    position_a=line_a.position,
                    position_b=line_b.position,
                )
            )
        elif line_a.orientation == "vertical" and line_a.label in b_vertical:
            line_b = b_vertical[line_a.label]
            matches.append(
                GridMatch(
                    label=line_a.label,
                    orientation="vertical",
                    position_a=line_a.position,
                    position_b=line_b.position,
                )
            )

    return matches


def calculate_grid_transformation(
    matches: list[GridMatch],
) -> AlignmentTransform | None:
    """Calculate affine transformation from matched grid lines.

    Args:
        matches: List of matched grid lines

    Returns:
        AlignmentTransform with scale/translate params, or None if insufficient matches

    Note:
        Requires ≥2 horizontal and ≥2 vertical matches
    """
    h_matches = [m for m in matches if m.orientation == "horizontal"]
    v_matches = [m for m in matches if m.orientation == "vertical"]

    if len(h_matches) < 2 or len(v_matches) < 2:
        return None

    # Y-axis transformation from horizontal matches (least squares)
    a_y = np.array([m.position_a for m in h_matches])
    b_y = np.array([m.position_b for m in h_matches])
    A = np.vstack([a_y, np.ones(len(a_y))]).T
    scale_y, translate_y = np.linalg.lstsq(A, b_y, rcond=None)[0]

    # X-axis transformation from vertical matches
    a_x = np.array([m.position_a for m in v_matches])
    b_x = np.array([m.position_b for m in v_matches])
    A = np.vstack([a_x, np.ones(len(a_x))]).T
    scale_x, translate_x = np.linalg.lstsq(A, b_x, rcond=None)[0]

    return AlignmentTransform(
        scale_x=scale_x,
        scale_y=scale_y,
        translate_x=translate_x,
        translate_y=translate_y,
        h_matches=len(h_matches),
        v_matches=len(v_matches),
    )


# =============================================================================
# Main Alignment Function
# =============================================================================


def align_with_grid(
    img_a: np.ndarray,
    img_b: np.ndarray,
    path_a: Path,
    path_b: Path,
) -> tuple[np.ndarray, np.ndarray, AlignmentStats] | tuple[None, None, None]:
    """Perform grid-based alignment of two images.

    Args:
        img_a: Image A in RGB format
        img_b: Image B in RGB format
        path_a: Path to image A file (for Gemini)
        path_b: Path to image B file (for Gemini)

    Returns:
        (aligned_a, aligned_b, stats) on success
        (None, None, None) if insufficient grid lines

    Raises:
        RuntimeError: If Gemini API fails
    """
    logger.info("Detecting grid lines in image A...")
    bgr_a = cv2.cvtColor(img_a, cv2.COLOR_RGB2BGR)
    lines_a = detect_grid_lines_from_image(path_a, bgr_a)
    h_a = sum(1 for line in lines_a if line.orientation == "horizontal")
    v_a = sum(1 for line in lines_a if line.orientation == "vertical")
    logger.info(f"Image A: {len(lines_a)} grid lines (H={h_a}, V={v_a})")

    logger.info("Detecting grid lines in image B...")
    bgr_b = cv2.cvtColor(img_b, cv2.COLOR_RGB2BGR)
    lines_b = detect_grid_lines_from_image(path_b, bgr_b)
    h_b = sum(1 for line in lines_b if line.orientation == "horizontal")
    v_b = sum(1 for line in lines_b if line.orientation == "vertical")
    logger.info(f"Image B: {len(lines_b)} grid lines (H={h_b}, V={v_b})")

    # Check minimum requirements
    if h_a < 2 or v_a < 2 or h_b < 2 or v_b < 2:
        logger.warning("Insufficient grid lines (need ≥2 per axis on both images)")
        return None, None, None

    # Match and calculate transformation
    matches = match_grid_lines(lines_a, lines_b)
    h_matches = sum(1 for m in matches if m.orientation == "horizontal")
    v_matches = sum(1 for m in matches if m.orientation == "vertical")
    logger.info(f"Matched: {len(matches)} lines (H={h_matches}, V={v_matches})")

    if h_matches < 2 or v_matches < 2:
        logger.warning("Insufficient grid matches (need ≥2 per axis)")
        return None, None, None

    transform = calculate_grid_transformation(matches)
    if transform is None:
        return None, None, None

    logger.info(
        f"Transform: scale=({transform.scale_x:.4f}, {transform.scale_y:.4f}), "
        f"translate=({transform.translate_x:.1f}, {transform.translate_y:.1f})"
    )

    # Apply transformation
    h_a_orig, w_a_orig = img_a.shape[:2]
    h_b_orig, w_b_orig = img_b.shape[:2]

    # Calculate bounding box for transformed image A
    corners = np.array(
        [[0, 0], [w_a_orig, 0], [w_a_orig, h_a_orig], [0, h_a_orig]], dtype=np.float64
    )
    transformed_corners = corners * [transform.scale_x, transform.scale_y] + [
        transform.translate_x,
        transform.translate_y,
    ]

    x_min = min(0, np.min(transformed_corners[:, 0]))
    y_min = min(0, np.min(transformed_corners[:, 1]))
    x_max = max(w_b_orig, np.max(transformed_corners[:, 0]))
    y_max = max(h_b_orig, np.max(transformed_corners[:, 1]))

    offset_x = -x_min if x_min < 0 else 0
    offset_y = -y_min if y_min < 0 else 0
    expanded_w = int(np.ceil(x_max - x_min))
    expanded_h = int(np.ceil(y_max - y_min))

    # Build affine matrix
    matrix = np.array(
        [
            [transform.scale_x, 0, transform.translate_x + offset_x],
            [0, transform.scale_y, transform.translate_y + offset_y],
        ],
        dtype=np.float64,
    )

    # Apply transformation to image A
    aligned_a = apply_transformation(img_a, matrix, output_shape=(expanded_w, expanded_h))

    # Place image B on expanded canvas
    aligned_b = np.full((expanded_h, expanded_w, 3), 255, dtype=np.uint8)
    b_x_start, b_y_start = int(offset_x), int(offset_y)
    aligned_b[b_y_start : b_y_start + h_b_orig, b_x_start : b_x_start + w_b_orig] = img_b

    gc.collect()

    stats = AlignmentStats(
        method="grid",
        scale_x=transform.scale_x,
        scale_y=transform.scale_y,
        translate_x=transform.translate_x,
        translate_y=transform.translate_y,
        h_matches=h_matches,
        v_matches=v_matches,
        expanded_width=expanded_w,
        expanded_height=expanded_h,
        offset_x=offset_x,
        offset_y=offset_y,
        matrix=matrix.tolist(),
    )

    return aligned_a, aligned_b, stats
