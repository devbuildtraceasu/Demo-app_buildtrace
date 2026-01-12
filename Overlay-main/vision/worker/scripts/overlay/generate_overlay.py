"""Generate aligned images and overlay outputs from raw old/new image pairs.

This script performs:
1. Grid-based alignment (if ≥2 grid lines per axis detected)
2. SIFT-based refinement (constrained to small adjustments after grid alignment)
3. Overlay generation (red/green/gray change visualization)
4. Deletion extraction (black on white)
5. Addition extraction (black on white)

Usage:
    python generate_overlay.py --old path/to/old.png --new path/to/new.png --output-dir path/to/output
"""

import argparse
import gc
import io
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import scipy.optimize
from PIL import Image
from pydantic import BaseModel, Field

Image.MAX_IMAGE_PIXELS = 250_000_000

worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(worker_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(worker_root, ".env"))

from google import genai
from google.genai import types

from lib.sift_alignment import (
    _convert_to_grayscale,
    _load_image_from_bytes,
    apply_transformation,
    estimate_transformation,
    extract_sift_features,
    match_features,
)

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3-pro-preview"
TARGET_DPI = 100

SCRIPT_DIR = Path(__file__).parent
DATASET_DIR = SCRIPT_DIR / "dataset"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "output"


# =============================================================================
# Token Usage Tracking
# =============================================================================

_token_usage: dict[str, dict[str, int]] = {}


def _track_token_usage(model: str, usage_metadata) -> None:
    """Track token usage from a response's usage_metadata."""
    if usage_metadata is None:
        return

    if model not in _token_usage:
        _token_usage[model] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "cached_tokens": 0,
        }

    _token_usage[model]["input_tokens"] += getattr(usage_metadata, "prompt_token_count", 0) or 0
    _token_usage[model]["output_tokens"] += getattr(usage_metadata, "candidates_token_count", 0) or 0
    _token_usage[model]["thinking_tokens"] += getattr(usage_metadata, "thoughts_token_count", 0) or 0
    _token_usage[model]["cached_tokens"] += getattr(usage_metadata, "cached_content_token_count", 0) or 0


def calculate_llm_cost(cost_per_model: dict[str, dict[str, float]]) -> dict[str, float]:
    """Calculate total LLM cost based on token usage (costs per 1M tokens)."""
    costs: dict[str, float] = {}
    total = 0.0

    for model, usage in _token_usage.items():
        model_costs = cost_per_model.get(model, {"input": 0, "output": 0, "cached": 0})
        cached = usage["cached_tokens"]
        non_cached_input = usage["input_tokens"] - cached
        cached_cost = (cached / 1_000_000) * model_costs.get("cached", 0)
        input_cost = (non_cached_input / 1_000_000) * model_costs.get("input", 0)
        output_cost = ((usage["output_tokens"] + usage["thinking_tokens"]) / 1_000_000) * model_costs.get("output", 0)
        model_total = input_cost + cached_cost + output_cost
        costs[model] = model_total
        total += model_total

    costs["total"] = total
    return costs


def print_token_usage_summary(cost_per_model: dict[str, dict[str, float]] | None = None) -> None:
    """Print a summary of token usage and optionally costs."""
    if not _token_usage:
        return

    print("\n" + "=" * 60)
    print("LLM Token Usage Summary")
    print("=" * 60)

    for model, usage in _token_usage.items():
        cached = usage["cached_tokens"]
        non_cached = usage["input_tokens"] - cached
        print(f"\n{model}:")
        print(f"  Input (non-cached): {non_cached:,}")
        print(f"  Input (cached):     {cached:,}")
        print(f"  Output tokens:      {usage['output_tokens']:,}")
        if usage["thinking_tokens"] > 0:
            print(f"  Thinking tokens:    {usage['thinking_tokens']:,}")

    if cost_per_model:
        costs = calculate_llm_cost(cost_per_model)
        print("\nEstimated Costs:")
        for model, cost in costs.items():
            if model != "total":
                print(f"  {model}: ${cost:.4f}")
        print(f"  Total: ${costs['total']:.4f}")


# =============================================================================
# Grid Detection (from grid_align_gemini.py)
# =============================================================================

class GridCalloutBBox(BaseModel):
    label: str = Field(description="The alphanumeric label inside the circle")
    xmin: int = Field(description="Left X coordinate (0-1000 normalized)")
    ymin: int = Field(description="Top Y coordinate (0-1000 normalized)")
    xmax: int = Field(description="Right X coordinate (0-1000 normalized)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000 normalized)")
    edge: str = Field(description="Which edge: 'top', 'bottom', 'left', 'right'")


class GridCalloutsResponse(BaseModel):
    callouts: list[GridCalloutBBox]


@dataclass
class DetectedGridLine:
    orientation: str  # 'horizontal' or 'vertical'
    position: float   # y for horizontal, x for vertical
    label: str


@dataclass
class GridMatch:
    label: str
    orientation: str
    old_position: float
    new_position: float


@dataclass
class AlignmentTransform:
    scale_x: float
    scale_y: float
    translate_x: float
    translate_y: float
    h_matches: int
    v_matches: int


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


def detect_callouts_with_gemini(image_path: Path, w: int, h: int) -> list[tuple[str, tuple[int, int, int, int], str]]:
    """Use Gemini to detect grid callout bounding boxes."""
    if not GEMINI_API_KEY:
        print("  Warning: GEMINI_API_KEY not found, skipping grid detection")
        return []

    img = Image.open(image_path)
    scale = TARGET_DPI / 300.0
    img_small = img.resize((int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    img_small.save(buffer, format='PNG')
    png_bytes = buffer.getvalue()

    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=[
                types.Part.from_bytes(mime_type="image/png", data=png_bytes),
                types.Part.from_text(text=GRID_SYSTEM_PROMPT),
                types.Part.from_text(text="Find all grid reference callouts in this construction drawing."),
            ])],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GridCalloutsResponse,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
                media_resolution="MEDIA_RESOLUTION_HIGH",
                temperature=0.0,
            ),
        )

        # Track token usage
        _track_token_usage(GEMINI_MODEL, response.usage_metadata)

        parsed = GridCalloutsResponse(**json.loads(response.text))
        results = []
        for c in parsed.callouts:
            x1, y1 = int(c.xmin * w / 1000), int(c.ymin * h / 1000)
            x2, y2 = int(c.xmax * w / 1000), int(c.ymax * h / 1000)
            results.append((c.label, (x1, y1, x2, y2), c.edge))
        return results

    except Exception as e:
        print(f"  Gemini error: {e}")
        return []


def detect_circle_in_crop(crop: np.ndarray, min_radius: int, max_radius: int) -> Optional[tuple[int, int, int]]:
    """Detect circle in cropped region. Returns (cx, cy, radius) or None."""
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop
    circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=min_radius * 2,
                                param1=100, param2=30, minRadius=min_radius, maxRadius=max_radius)
    if circles is None or len(circles[0]) == 0:
        return None
    c = np.uint16(np.around(circles[0][0]))
    return (int(c[0]), int(c[1]), int(c[2]))


def detect_grid_line(gray: np.ndarray, cx: int, cy: int, radius: int, edge: str) -> Optional[tuple[str, float]]:
    """Detect grid line touching circle. Returns (orientation, position) or None."""
    h, w = gray.shape
    search_dist = 300

    if edge in ['left', 'right']:
        orientation = 'horizontal'
        y1, y2 = max(0, cy - radius - 20), min(h, cy + radius + 20)
        if edge == 'left':
            x1, x2 = cx + radius - 10, min(w, cx + radius + search_dist)
        else:
            x1, x2 = max(0, cx - radius - search_dist), cx - radius + 10
    else:
        orientation = 'vertical'
        x1, x2 = max(0, cx - radius - 20), min(w, cx + radius + 20)
        if edge == 'top':
            y1, y2 = cy + radius - 10, min(h, cy + radius + search_dist)
        else:
            y1, y2 = max(0, cy - radius - search_dist), cy - radius + 10

    if x2 <= x1 or y2 <= y1:
        return None

    region = gray[y1:y2, x1:x2]
    if region.size == 0:
        return None

    edges = cv2.Canny(region, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, 30, minLineLength=30, maxLineGap=20)

    if lines is None:
        return None

    for line in lines:
        lx1, ly1, lx2, ly2 = line[0]
        angle = np.degrees(np.arctan2(ly2 - ly1, lx2 - lx1))
        if orientation == 'horizontal' and (abs(angle) < 20 or abs(abs(angle) - 180) < 20):
            return (orientation, float(cy))
        if orientation == 'vertical' and abs(abs(angle) - 90) < 20:
            return (orientation, float(cx))

    return None


def process_callout(
    full_image: np.ndarray,
    gray: np.ndarray,
    label: str,
    bbox: tuple[int, int, int, int],
    edge: str,
    idx: int = 0,
) -> Optional[DetectedGridLine]:
    """Process a single callout: detect circle and grid line."""
    h, w = full_image.shape[:2]
    x1, y1, x2, y2 = bbox
    padding = 50

    crop_x1, crop_y1 = max(0, x1 - padding), max(0, y1 - padding)
    crop_x2, crop_y2 = min(w, x2 + padding), min(h, y2 + padding)
    crop = full_image[crop_y1:crop_y2, crop_x1:crop_x2]

    if crop.size == 0:
        return None

    bbox_w, bbox_h = x2 - x1, y2 - y1
    est_radius = min(bbox_w, bbox_h) // 2
    min_r, max_r = max(10, est_radius - 100), est_radius + 100

    circle = detect_circle_in_crop(crop, min_r, max_r)
    if circle is None:
        print(f"    [{idx}] '{label}': No circle found, skipping")
        return None

    cx_crop, cy_crop, radius = circle
    cx, cy = cx_crop + crop_x1, cy_crop + crop_y1

    # Detect grid line
    line_result = detect_grid_line(gray, cx, cy, radius, edge)

    if line_result:
        orientation, position = line_result
        print(f"    [{idx}] '{label}': ({cx}, {cy}) r={radius}, {orientation} @ {position:.0f}")
        return DetectedGridLine(orientation=orientation, position=position, label=label)
    else:
        # Fallback: use callout position as grid line
        orientation = 'horizontal' if edge in ['left', 'right'] else 'vertical'
        position = float(cy) if orientation == 'horizontal' else float(cx)
        print(f"    [{idx}] '{label}': ({cx}, {cy}) r={radius}, {orientation} @ {position:.0f} (fallback)")
        return DetectedGridLine(orientation=orientation, position=position, label=label)


def detect_grid_lines_from_image(image_path: Path, image_bgr: np.ndarray) -> list[DetectedGridLine]:
    """Detect grid lines in an image using Gemini + OpenCV."""
    h, w = image_bgr.shape[:2]

    gemini_results = detect_callouts_with_gemini(image_path, w, h)
    if not gemini_results:
        return []

    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    grid_lines = []

    for idx, (label, bbox, edge) in enumerate(gemini_results):
        grid_line = process_callout(image_bgr, gray, label, bbox, edge, idx)
        if grid_line:
            grid_lines.append(grid_line)

    return grid_lines


def match_grid_lines(old_lines: list[DetectedGridLine], new_lines: list[DetectedGridLine]) -> list[GridMatch]:
    """Match grid lines between images by label."""
    new_h = {l.label: l for l in new_lines if l.orientation == 'horizontal'}
    new_v = {l.label: l for l in new_lines if l.orientation == 'vertical'}

    matches = []
    for old in old_lines:
        if old.orientation == 'horizontal' and old.label in new_h:
            matches.append(GridMatch(old.label, 'horizontal', old.position, new_h[old.label].position))
        elif old.orientation == 'vertical' and old.label in new_v:
            matches.append(GridMatch(old.label, 'vertical', old.position, new_v[old.label].position))

    return matches


def calculate_grid_transformation(matches: list[GridMatch]) -> Optional[AlignmentTransform]:
    """Calculate affine transformation from matched grid lines."""
    h_matches = [m for m in matches if m.orientation == 'horizontal']
    v_matches = [m for m in matches if m.orientation == 'vertical']

    if len(h_matches) < 2 or len(v_matches) < 2:
        return None

    # Y-axis from horizontal matches (least squares)
    old_y = np.array([m.old_position for m in h_matches])
    new_y = np.array([m.new_position for m in h_matches])
    A = np.vstack([old_y, np.ones(len(old_y))]).T
    scale_y, translate_y = np.linalg.lstsq(A, new_y, rcond=None)[0]

    # X-axis from vertical matches
    old_x = np.array([m.old_position for m in v_matches])
    new_x = np.array([m.new_position for m in v_matches])
    A = np.vstack([old_x, np.ones(len(old_x))]).T
    scale_x, translate_x = np.linalg.lstsq(A, new_x, rcond=None)[0]

    return AlignmentTransform(scale_x, scale_y, translate_x, translate_y, len(h_matches), len(v_matches))


# =============================================================================
# Image Loading/Saving
# =============================================================================

def load_image(path: Path) -> np.ndarray:
    """Load image as RGB numpy array."""
    print(f"Loading {path.name}...", flush=True)
    with open(path, "rb") as f:
        png_bytes = f.read()
    return _load_image_from_bytes(png_bytes)


def save_image(img: np.ndarray, output_path: Path, also_pdf: bool = False) -> None:
    """Save RGB numpy array as PNG and optionally as PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pil_img = Image.fromarray(img, mode='RGB')
    pil_img.save(output_path)
    print(f"Saved: {output_path}", flush=True)

    if also_pdf:
        pdf_path = output_path.with_suffix('.pdf')
        pil_img.save(pdf_path, 'PDF', resolution=100.0)
        print(f"Saved: {pdf_path}", flush=True)


# =============================================================================
# Alignment Functions
# =============================================================================

def align_with_grid(
    old_img: np.ndarray,
    new_img: np.ndarray,
    old_path: Path,
    new_path: Path,
) -> tuple[Optional[np.ndarray], Optional[np.ndarray], Optional[dict]]:
    """
    Attempt grid-based alignment.

    Returns (aligned_old, aligned_new, stats) or (None, None, None) if insufficient grid lines.
    """
    print("Detecting grid lines in old image...")
    old_bgr = cv2.cvtColor(old_img, cv2.COLOR_RGB2BGR)
    old_lines = detect_grid_lines_from_image(old_path, old_bgr)
    h_old = sum(1 for l in old_lines if l.orientation == 'horizontal')
    v_old = sum(1 for l in old_lines if l.orientation == 'vertical')
    print(f"  Old: {len(old_lines)} lines (H={h_old}, V={v_old})")

    print("Detecting grid lines in new image...")
    new_bgr = cv2.cvtColor(new_img, cv2.COLOR_RGB2BGR)
    new_lines = detect_grid_lines_from_image(new_path, new_bgr)
    h_new = sum(1 for l in new_lines if l.orientation == 'horizontal')
    v_new = sum(1 for l in new_lines if l.orientation == 'vertical')
    print(f"  New: {len(new_lines)} lines (H={h_new}, V={v_new})")

    # Check minimum requirements
    if h_old < 2 or v_old < 2 or h_new < 2 or v_new < 2:
        print("  Insufficient grid lines (need ≥2 per axis on both images)")
        return None, None, None

    # Match and calculate transformation
    matches = match_grid_lines(old_lines, new_lines)
    h_matches = sum(1 for m in matches if m.orientation == 'horizontal')
    v_matches = sum(1 for m in matches if m.orientation == 'vertical')
    print(f"  Matched: {len(matches)} lines (H={h_matches}, V={v_matches})")

    if h_matches < 2 or v_matches < 2:
        print("  Insufficient matches (need ≥2 per axis)")
        return None, None, None

    transform = calculate_grid_transformation(matches)
    if transform is None:
        return None, None, None

    print(f"  Transform: scale=({transform.scale_x:.4f}, {transform.scale_y:.4f}), "
          f"translate=({transform.translate_x:.1f}, {transform.translate_y:.1f})")

    # Apply transformation
    old_h, old_w = old_img.shape[:2]
    new_h, new_w = new_img.shape[:2]

    # Calculate bounding box for transformed old image
    old_corners = np.array([[0, 0], [old_w, 0], [old_w, old_h], [0, old_h]], dtype=np.float64)
    transformed_corners = old_corners * [transform.scale_x, transform.scale_y] + [transform.translate_x, transform.translate_y]

    combined_x_min = min(0, np.min(transformed_corners[:, 0]))
    combined_y_min = min(0, np.min(transformed_corners[:, 1]))
    combined_x_max = max(new_w, np.max(transformed_corners[:, 0]))
    combined_y_max = max(new_h, np.max(transformed_corners[:, 1]))

    offset_x = -combined_x_min if combined_x_min < 0 else 0
    offset_y = -combined_y_min if combined_y_min < 0 else 0
    expanded_w = int(np.ceil(combined_x_max - combined_x_min))
    expanded_h = int(np.ceil(combined_y_max - combined_y_min))

    # Build affine matrix
    matrix = np.array([
        [transform.scale_x, 0, transform.translate_x + offset_x],
        [0, transform.scale_y, transform.translate_y + offset_y]
    ], dtype=np.float64)

    # Apply transformation
    aligned_old = cv2.warpAffine(
        cv2.cvtColor(old_img, cv2.COLOR_RGB2BGR), matrix, (expanded_w, expanded_h),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255)
    )
    aligned_old = cv2.cvtColor(aligned_old, cv2.COLOR_BGR2RGB)

    # Place new image on expanded canvas
    aligned_new = np.full((expanded_h, expanded_w, 3), 255, dtype=np.uint8)
    new_x_start, new_y_start = int(offset_x), int(offset_y)
    aligned_new[new_y_start:new_y_start + new_h, new_x_start:new_x_start + new_w] = new_img

    stats = {
        "method": "grid",
        "h_matches": h_matches,
        "v_matches": v_matches,
        "scale_x": transform.scale_x,
        "scale_y": transform.scale_y,
        "translate_x": transform.translate_x,
        "translate_y": transform.translate_y,
        "expanded_width": expanded_w,
        "expanded_height": expanded_h,
        "offset_x": offset_x,
        "offset_y": offset_y,
    }

    return aligned_old, aligned_new, stats


def basic_sift_align(
    old_img: np.ndarray,
    new_img: np.ndarray,
    downsample_scale: float = 0.5,
    n_features: int = 10000,
    ratio_threshold: float = 0.6,
    reproj_threshold: float = 10.0,
    max_iters: int = 10000,
    expand_canvas: bool = False,
    scale_min: float | None = None,
    scale_max: float | None = None,
    rotation_deg_min: float | None = None,
    rotation_deg_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Align images using SIFT feature matching with post-hoc constraint checking.

    Args:
        old_img: Source image to transform
        new_img: Target/reference image
        downsample_scale: Scale factor for SIFT processing (lower = faster)
        n_features: Max SIFT features to extract
        ratio_threshold: Lowe's ratio test threshold (lower = stricter)
        reproj_threshold: RANSAC reprojection threshold
        max_iters: RANSAC max iterations
        expand_canvas: If True, expand output to fit both images
        scale_min: If set, reject if scale < this value
        scale_max: If set, reject if scale > this value
        rotation_deg_min: If set, reject if rotation < this value
        rotation_deg_max: If set, reject if rotation > this value

    Returns:
        (aligned_old, aligned_new, stats)

    Raises:
        RuntimeError: If alignment fails or constraints violated
    """
    has_constraints = any(x is not None for x in [scale_min, scale_max, rotation_deg_min, rotation_deg_max])

    if has_constraints:
        constraints_str = []
        if scale_min is not None or scale_max is not None:
            constraints_str.append(f"scale[{scale_min or '-∞'},{scale_max or '∞'}]")
        if rotation_deg_min is not None or rotation_deg_max is not None:
            constraints_str.append(f"rot[{rotation_deg_min or '-∞'}°,{rotation_deg_max or '∞'}°]")
        print(f"Basic SIFT alignment ({', '.join(constraints_str)})...")
    else:
        print(f"SIFT alignment ({downsample_scale*100:.0f}% scale)...")

    # Downsample for SIFT
    old_small = cv2.resize(old_img, None, fx=downsample_scale, fy=downsample_scale, interpolation=cv2.INTER_AREA)
    new_small = cv2.resize(new_img, None, fx=downsample_scale, fy=downsample_scale, interpolation=cv2.INTER_AREA)

    old_gray = _convert_to_grayscale(old_small)
    new_gray = _convert_to_grayscale(new_small)

    del old_small, new_small
    gc.collect()

    # Extract and match features
    kp1, desc1 = extract_sift_features(old_gray, n_features=n_features, exclude_margin=0.1)
    kp2, desc2 = extract_sift_features(new_gray, n_features=n_features, exclude_margin=0.1)
    print(f"  Features: old={len(kp1)}, new={len(kp2)}")

    if len(kp1) < 10 or len(kp2) < 10:
        raise RuntimeError("Insufficient SIFT features")

    matches = match_features(desc1, desc2, ratio_threshold=ratio_threshold)
    print(f"  Matches: {len(matches)}")

    if len(matches) < 10:
        raise RuntimeError("Insufficient SIFT matches")

    # Estimate transformation
    matrix, mask, inlier_count, total_matches = estimate_transformation(
        kp1, kp2, matches, reproj_threshold=reproj_threshold, max_iters=max_iters, confidence=0.95
    )

    if matrix is None:
        raise RuntimeError("Failed to estimate SIFT transformation")

    del old_gray, new_gray, kp1, kp2, desc1, desc2, matches, mask
    gc.collect()

    # Scale matrix back to full resolution
    scale_factor = 1.0 / downsample_scale
    matrix[0, 2] *= scale_factor
    matrix[1, 2] *= scale_factor

    # Extract transformation parameters
    scale = np.sqrt(matrix[0, 0]**2 + matrix[1, 0]**2)
    rotation_deg = np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))
    tx, ty = matrix[0, 2], matrix[1, 2]

    print(f"  Transform: scale={scale:.4f}, rotation={rotation_deg:.2f}°, translate=({tx:.1f}, {ty:.1f})")
    print(f"  Inliers: {inlier_count}/{total_matches}")

    # Check constraints if specified (hard rejection)
    if scale_min is not None and scale < scale_min:
        raise RuntimeError(f"Scale {scale:.4f} below minimum {scale_min}")
    if scale_max is not None and scale > scale_max:
        raise RuntimeError(f"Scale {scale:.4f} above maximum {scale_max}")
    if rotation_deg_min is not None and rotation_deg < rotation_deg_min:
        raise RuntimeError(f"Rotation {rotation_deg:.2f}° below minimum {rotation_deg_min}°")
    if rotation_deg_max is not None and rotation_deg > rotation_deg_max:
        raise RuntimeError(f"Rotation {rotation_deg:.2f}° above maximum {rotation_deg_max}°")

    # Apply transformation
    old_h, old_w = old_img.shape[:2]
    new_h, new_w = new_img.shape[:2]

    if expand_canvas:
        # Calculate expanded canvas to fit both images
        old_corners = np.array([[0, 0, 1], [old_w, 0, 1], [old_w, old_h, 1], [0, old_h, 1]], dtype=np.float64).T
        transformed_corners = matrix @ old_corners

        combined_x_min = min(0, np.min(transformed_corners[0]))
        combined_y_min = min(0, np.min(transformed_corners[1]))
        combined_x_max = max(new_w, np.max(transformed_corners[0]))
        combined_y_max = max(new_h, np.max(transformed_corners[1]))

        offset_x = -combined_x_min if combined_x_min < 0 else 0
        offset_y = -combined_y_min if combined_y_min < 0 else 0
        output_w = int(np.ceil(combined_x_max - combined_x_min))
        output_h = int(np.ceil(combined_y_max - combined_y_min))

        adjusted_matrix = matrix.copy()
        adjusted_matrix[0, 2] += offset_x
        adjusted_matrix[1, 2] += offset_y

        aligned_old = apply_transformation(old_img, adjusted_matrix, output_shape=(output_w, output_h))

        aligned_new = np.full((output_h, output_w, 3), 255, dtype=new_img.dtype)
        new_x_start, new_y_start = int(offset_x), int(offset_y)
        aligned_new[new_y_start:new_y_start + new_h, new_x_start:new_x_start + new_w] = new_img
    else:
        # Keep same canvas size as new image
        output_w, output_h = new_w, new_h
        aligned_old = apply_transformation(old_img, matrix, output_shape=(output_w, output_h))
        aligned_new = new_img

    stats = {
        "method": "sift",
        "scale": scale,
        "rotation_deg": rotation_deg,
        "translate_x": tx,
        "translate_y": ty,
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_count / total_matches if total_matches > 0 else 0,
        "output_width": output_w,
        "output_height": output_h,
        # For re-applying transform to other images
        "matrix": adjusted_matrix if expand_canvas else matrix,
        "offset_x": offset_x if expand_canvas else 0,
        "offset_y": offset_y if expand_canvas else 0,
        "expanded_width": output_w,
        "expanded_height": output_h,
    }

    return aligned_old, aligned_new, stats


def _run_constrained_optimizer(
    from_points: np.ndarray,
    to_points: np.ndarray,
    scale_min: float | None = None,
    scale_max: float | None = None,
    rotation_deg_min: float | None = None,
    rotation_deg_max: float | None = None,
) -> np.ndarray:
    """Run constrained optimization on matched points to find best affine transform."""
    if from_points.shape[0] < 2:
        raise RuntimeError("At least 2 points required for optimization")

    def objective_func(params):
        scale, theta_rad, tx, ty = params
        cos_theta, sin_theta = np.cos(theta_rad), np.sin(theta_rad)
        m = np.array([
            [scale * cos_theta, -scale * sin_theta, tx],
            [scale * sin_theta, scale * cos_theta, ty]
        ])
        from_hom = np.hstack([from_points, np.ones((from_points.shape[0], 1))])
        transformed = (m @ from_hom.T).T
        return np.sum((to_points - transformed) ** 2)

    # Initial estimate using OpenCV
    initial_m, _ = cv2.estimateAffinePartial2D(from_points, to_points)
    if initial_m is not None:
        s_init = np.sqrt(initial_m[0, 0] ** 2 + initial_m[1, 0] ** 2)
        theta_init = np.arctan2(initial_m[1, 0], initial_m[0, 0])
        tx_init, ty_init = initial_m[0, 2], initial_m[1, 2]
    else:
        s_init, theta_init = 1.0, 0.0
        tx_init = np.mean(to_points[:, 0] - from_points[:, 0])
        ty_init = np.mean(to_points[:, 1] - from_points[:, 1])

    initial_guess = [s_init, theta_init, tx_init, ty_init]
    rot_min = np.deg2rad(rotation_deg_min) if rotation_deg_min is not None else -np.inf
    rot_max = np.deg2rad(rotation_deg_max) if rotation_deg_max is not None else np.inf
    bounds = [(scale_min, scale_max), (rot_min, rot_max), (None, None), (None, None)]

    result = scipy.optimize.minimize(objective_func, initial_guess, bounds=bounds, method="L-BFGS-B")

    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")

    scale_opt, theta_opt, tx_opt, ty_opt = result.x
    cos_opt, sin_opt = np.cos(theta_opt), np.sin(theta_opt)
    return np.array([
        [scale_opt * cos_opt, -scale_opt * sin_opt, tx_opt],
        [scale_opt * sin_opt, scale_opt * cos_opt, ty_opt],
    ])


def _estimate_affine_constrained(
    from_points: np.ndarray,
    to_points: np.ndarray,
    ransac_threshold: float = 3.0,
    max_iters: int = 2000,
    confidence: float = 0.99,
    scale_min: float | None = None,
    scale_max: float | None = None,
    rotation_deg_min: float | None = None,
    rotation_deg_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Estimate constrained affine transformation using RANSAC with optimization.

    Returns (matrix, inlier_mask) or raises RuntimeError on failure.
    """
    num_points = from_points.shape[0]
    if num_points < 2:
        raise RuntimeError("Need at least 2 points")

    rot_min = np.deg2rad(rotation_deg_min) if rotation_deg_min is not None else -np.inf
    rot_max = np.deg2rad(rotation_deg_max) if rotation_deg_max is not None else np.inf

    hypotheses = []
    best_inlier_count = -1
    from_hom = np.hstack([from_points, np.ones((num_points, 1))])

    for _ in range(max_iters):
        # Sample 2 points
        idx = np.random.choice(num_points, 2, replace=False)
        p1, p2 = from_points[idx]
        q1, q2 = to_points[idx]

        # Compute candidate
        v_from, v_to = p2 - p1, q2 - q1
        len_from = np.linalg.norm(v_from)
        if np.isclose(len_from, 0):
            continue

        # Check scale constraint
        scale = np.linalg.norm(v_to) / len_from
        if (scale_min is not None and scale < scale_min) or (scale_max is not None and scale > scale_max):
            continue

        # Check rotation constraint
        angle_from = np.arctan2(v_from[1], v_from[0])
        angle_to = np.arctan2(v_to[1], v_to[0])
        theta = angle_to - angle_from
        if not (rot_min <= theta <= rot_max or rot_min <= theta + 2*np.pi <= rot_max or rot_min <= theta - 2*np.pi <= rot_max):
            continue

        # Form candidate matrix
        cos_t, sin_t = np.cos(theta), np.sin(theta)
        tx = q1[0] - (p1[0] * scale * cos_t - p1[1] * scale * sin_t)
        ty = q1[1] - (p1[0] * scale * sin_t + p1[1] * scale * cos_t)
        m_cand = np.array([[scale * cos_t, -scale * sin_t, tx], [scale * sin_t, scale * cos_t, ty]])

        # Count inliers
        transformed = (m_cand @ from_hom.T).T
        errors = np.linalg.norm(to_points - transformed, axis=1)
        inlier_mask = errors < ransac_threshold
        inlier_count = np.sum(inlier_mask)

        hypotheses.append((inlier_count, inlier_mask))

        if inlier_count > best_inlier_count:
            best_inlier_count = inlier_count
            inlier_ratio = inlier_count / num_points
            if inlier_ratio > 0:
                new_max = int(np.log(1 - confidence) / np.log(1 - inlier_ratio**2))
                if new_max < max_iters:
                    max_iters = new_max

    # Sort by inlier count and try optimization
    hypotheses.sort(key=lambda x: x[0], reverse=True)

    for _, inlier_mask in hypotheses:
        from_inliers = from_points[inlier_mask]
        to_inliers = to_points[inlier_mask]

        try:
            final_matrix = _run_constrained_optimizer(
                from_inliers, to_inliers, scale_min, scale_max, rotation_deg_min, rotation_deg_max
            )
            return final_matrix, inlier_mask.astype(np.uint8).reshape(-1, 1)
        except RuntimeError:
            pass

    raise RuntimeError("All optimization attempts failed")


def scipy_sift_align(
    old_img: np.ndarray,
    new_img: np.ndarray,
    downsample_scale: float = 0.5,
    n_features: int = 10000,
    ratio_threshold: float = 0.6,
    ransac_threshold: float = 10.0,
    max_iters: int = 10000,
    expand_canvas: bool = False,
    scale_min: float | None = None,
    scale_max: float | None = None,
    rotation_deg_min: float | None = None,
    rotation_deg_max: float | None = None,
    normalize_size: bool = True,
    contrast_threshold: float = 0.02,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """
    Align images using SIFT with constrained optimization.

    Uses scipy L-BFGS-B optimizer for bounded scale/rotation constraints,
    providing better results than post-hoc constraint checking.

    Args:
        old_img: Source image to transform
        new_img: Target/reference image
        downsample_scale: Scale factor for SIFT processing (lower = faster)
        n_features: Max SIFT features to extract
        ratio_threshold: Lowe's ratio test threshold (lower = stricter)
        ransac_threshold: RANSAC reprojection threshold in pixels
        max_iters: RANSAC max iterations
        expand_canvas: If True, expand output to fit both images
        scale_min: Minimum allowed scale (e.g., 0.95 for ±5%)
        scale_max: Maximum allowed scale (e.g., 1.05 for ±5%)
        rotation_deg_min: Minimum rotation in degrees (e.g., -3.0)
        rotation_deg_max: Maximum rotation in degrees (e.g., 3.0)
        normalize_size: If True, pre-scale images to similar size before SIFT
        contrast_threshold: SIFT contrast threshold (lower = more features)

    Returns:
        (aligned_old, aligned_new, stats)

    Raises:
        RuntimeError: If alignment fails
    """
    constraints = []
    if scale_min is not None or scale_max is not None:
        constraints.append(f"scale[{scale_min or '-∞'},{scale_max or '∞'}]")
    if rotation_deg_min is not None or rotation_deg_max is not None:
        constraints.append(f"rot[{rotation_deg_min or '-∞'}°,{rotation_deg_max or '∞'}°]")

    if constraints:
        print(f"Optimized SIFT alignment ({', '.join(constraints)})...")
    else:
        print(f"Optimized SIFT alignment ({downsample_scale*100:.0f}% scale)...")

    # Pre-scale images to similar size for better SIFT matching
    old_h, old_w = old_img.shape[:2]
    new_h, new_w = new_img.shape[:2]
    old_prescale = 1.0
    new_prescale = 1.0

    if normalize_size:
        # Scale larger image down to match smaller image's diagonal
        old_diag = np.sqrt(old_h**2 + old_w**2)
        new_diag = np.sqrt(new_h**2 + new_w**2)
        if old_diag > new_diag * 1.5:  # Old is significantly larger
            old_prescale = new_diag / old_diag
            print(f"  Pre-scaling old image by {old_prescale:.3f} to normalize size")
        elif new_diag > old_diag * 1.5:  # New is significantly larger
            new_prescale = old_diag / new_diag
            print(f"  Pre-scaling new image by {new_prescale:.3f} to normalize size")

    # Downsample for SIFT (combined with prescale)
    old_scale = downsample_scale * old_prescale
    new_scale = downsample_scale * new_prescale
    old_small = cv2.resize(old_img, None, fx=old_scale, fy=old_scale, interpolation=cv2.INTER_AREA)
    new_small = cv2.resize(new_img, None, fx=new_scale, fy=new_scale, interpolation=cv2.INTER_AREA)
    print(f"  SIFT image sizes: old={old_small.shape[:2]}, new={new_small.shape[:2]}")

    old_gray = _convert_to_grayscale(old_small)
    new_gray = _convert_to_grayscale(new_small)

    del old_small, new_small
    gc.collect()

    # Extract and match features
    kp1, desc1 = extract_sift_features(old_gray, n_features=n_features, exclude_margin=0.1, contrast_threshold=contrast_threshold)
    kp2, desc2 = extract_sift_features(new_gray, n_features=n_features, exclude_margin=0.1, contrast_threshold=contrast_threshold)
    print(f"  Features: old={len(kp1)}, new={len(kp2)}")

    if len(kp1) < 10 or len(kp2) < 10:
        raise RuntimeError("Insufficient SIFT features")

    matches = match_features(desc1, desc2, ratio_threshold=ratio_threshold)
    print(f"  Matches: {len(matches)}")

    if len(matches) < 10:
        raise RuntimeError("Insufficient SIFT matches")

    # Convert matches to point arrays
    pts1 = np.array([kp1[m.queryIdx].pt for m in matches], dtype=np.float32)
    pts2 = np.array([kp2[m.trainIdx].pt for m in matches], dtype=np.float32)

    del old_gray, new_gray, kp1, kp2, desc1, desc2, matches
    gc.collect()

    # Run constrained optimization
    matrix, mask = _estimate_affine_constrained(
        pts1, pts2,
        ransac_threshold=ransac_threshold,
        max_iters=max_iters,
        scale_min=scale_min,
        scale_max=scale_max,
        rotation_deg_min=rotation_deg_min,
        rotation_deg_max=rotation_deg_max,
    )

    inlier_count = int(np.sum(mask))
    total_matches = len(pts1)

    # Scale matrix back to full resolution
    # Matrix transforms old_small coords to new_small coords
    # Need to adjust for different prescale factors
    matrix[:, :2] *= (old_scale / new_scale)  # Scale/rotation components
    matrix[:, 2] /= new_scale  # Translation components

    # Extract transformation parameters
    scale = np.sqrt(matrix[0, 0]**2 + matrix[1, 0]**2)
    rotation_deg = np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))
    tx, ty = matrix[0, 2], matrix[1, 2]

    print(f"  Transform: scale={scale:.4f}, rotation={rotation_deg:.2f}°, translate=({tx:.1f}, {ty:.1f})")
    print(f"  Inliers: {inlier_count}/{total_matches}")

    # Apply transformation
    old_h, old_w = old_img.shape[:2]
    new_h, new_w = new_img.shape[:2]

    if expand_canvas:
        old_corners = np.array([[0, 0, 1], [old_w, 0, 1], [old_w, old_h, 1], [0, old_h, 1]], dtype=np.float64).T
        transformed_corners = matrix @ old_corners

        combined_x_min = min(0, np.min(transformed_corners[0]))
        combined_y_min = min(0, np.min(transformed_corners[1]))
        combined_x_max = max(new_w, np.max(transformed_corners[0]))
        combined_y_max = max(new_h, np.max(transformed_corners[1]))

        offset_x = -combined_x_min if combined_x_min < 0 else 0
        offset_y = -combined_y_min if combined_y_min < 0 else 0
        output_w = int(np.ceil(combined_x_max - combined_x_min))
        output_h = int(np.ceil(combined_y_max - combined_y_min))

        adjusted_matrix = matrix.copy()
        adjusted_matrix[0, 2] += offset_x
        adjusted_matrix[1, 2] += offset_y

        aligned_old = apply_transformation(old_img, adjusted_matrix, output_shape=(output_w, output_h))

        aligned_new = np.full((output_h, output_w, 3), 255, dtype=new_img.dtype)
        new_x_start, new_y_start = int(offset_x), int(offset_y)
        aligned_new[new_y_start:new_y_start + new_h, new_x_start:new_x_start + new_w] = new_img
    else:
        output_w, output_h = new_w, new_h
        aligned_old = apply_transformation(old_img, matrix, output_shape=(output_w, output_h))
        aligned_new = new_img

    stats = {
        "method": "sift_optimized",
        "scale": scale,
        "rotation_deg": rotation_deg,
        "translate_x": tx,
        "translate_y": ty,
        "inlier_count": inlier_count,
        "inlier_ratio": inlier_count / total_matches if total_matches > 0 else 0,
        "output_width": output_w,
        "output_height": output_h,
        # For re-applying transform to other images
        "matrix": adjusted_matrix if expand_canvas else matrix,
        "offset_x": offset_x if expand_canvas else 0,
        "offset_y": offset_y if expand_canvas else 0,
        "expanded_width": output_w,
        "expanded_height": output_h,
    }

    return aligned_old, aligned_new, stats


def apply_alignment_to_images(
    old_img: np.ndarray,
    new_img: np.ndarray,
    align_stats: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply alignment transformation from stats to a pair of images.

    Use this to apply the same alignment computed on binarized images
    to the original images.
    """
    matrix = align_stats["matrix"]
    offset_x = align_stats["offset_x"]
    offset_y = align_stats["offset_y"]
    output_w = align_stats["expanded_width"]
    output_h = align_stats["expanded_height"]

    # Apply transformation to old image
    aligned_old = apply_transformation(old_img, matrix, output_shape=(output_w, output_h))

    # Place new image on expanded canvas
    new_h, new_w = new_img.shape[:2]
    aligned_new = np.full((output_h, output_w, 3), 255, dtype=new_img.dtype)
    new_x_start, new_y_start = int(offset_x), int(offset_y)
    aligned_new[new_y_start:new_y_start + new_h, new_x_start:new_x_start + new_w] = new_img

    return aligned_old, aligned_new


# =============================================================================
# Overlay Generation
# =============================================================================

def convert_to_grayscale(rgb_image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(rgb_image, cv2.COLOR_RGB2GRAY)


def count_pixels(img: np.ndarray) -> int:
    gray = convert_to_grayscale(img)
    return np.sum(gray < 128)


def generate_overlay(
    aligned_old: np.ndarray,
    new: np.ndarray,
    ink_threshold: int = 200,
    diff_threshold: int = 40,
    morph_kernel_size: int = 1,
    skip_morph: bool = False,
    shift_tolerance: int = 3,
    binarize: str = "none",
    tint_strength: float = 0.5,
    merge_mode: bool = False,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate overlay, deletion, and addition images from aligned image pairs.

    Compares two aligned images to detect additions and deletions:
    1. Content detection via binarization (or ink_threshold if binarize="none")
    2. Change detection: only differences > diff_threshold count as real changes
    3. Removed = was ink in old, not in new, with significant difference
    4. Added = is ink in new, wasn't in old, with significant difference

    Args:
        aligned_old: Old image aligned to new image coordinate space (H, W, 3) RGB
        new: New/reference image (H, W, 3) RGB
        ink_threshold: Only used when binarize="none". Pixels darker than this
            are considered "ink/content" (0-255). Default 200.
        diff_threshold: Minimum pixel intensity difference to count as real change (0-255).
            Filters out noise/artifacts. Lower = more sensitive. Default 40.
        morph_kernel_size: Kernel size for morphological opening to clean noise.
        skip_morph: If True, skip morphological cleaning.
        shift_tolerance: Pixels within this distance of content in the other image
            are not counted as changes (handles minor alignment errors).
        binarize: Binarization method for content detection. One of:
            "none" (use ink_threshold), "basic", "remove-fills", "canny-edge".
        tint_strength: Blend factor for diff coloring (0.0 = pure grayscale,
            1.0 = pure red/green). Default 0.5 preserves grayscale detail
            while clearly showing the tint.
        merge_mode: If True, merge both images with red/green tint instead of
            showing discrete diffs. Old image tinted red, new tinted green,
            overlapping areas appear gray. Ignores diff_threshold, morph, etc.

    Returns:
        Tuple of (overlay, deletion, addition):
        - overlay: RGB image with red=removed, green=added, gray=unchanged
        - deletion: Black pixels on white showing removed content
        - addition: Black pixels on white showing added content
    """
    old_gray = convert_to_grayscale(aligned_old)
    new_gray = convert_to_grayscale(new)

    # Merge mode: simple red/green overlay without diff detection
    if merge_mode:
        # R=new_gray (red where old-only), G=old_gray (green where new-only)
        # Overlapping areas have low R and G → neutral gray/black
        old_f = old_gray.astype(np.float32)
        new_f = new_gray.astype(np.float32)

        # Base merge: R=new, G=old, B=min for neutral overlap
        r_base = new_f
        g_base = old_f
        b_base = np.minimum(old_f, new_f)

        # Apply tint_strength: blend between grayscale average and tinted
        gray_avg = (old_f + new_f) / 2
        r = r_base * tint_strength + gray_avg * (1 - tint_strength)
        g = g_base * tint_strength + gray_avg * (1 - tint_strength)
        b = b_base * tint_strength + gray_avg * (1 - tint_strength)

        overlay = np.stack([r, g, b], axis=-1).astype(np.uint8)

        # In merge mode, deletion/addition are empty (no discrete diff)
        deletion = np.full_like(aligned_old, 255, dtype=np.uint8)
        addition = np.full_like(new, 255, dtype=np.uint8)

        return overlay, deletion, addition

    # Content detection: binarization determines content, or use ink_threshold for "none"
    if binarize == "none":
        old_mask = old_gray < ink_threshold
        new_mask = new_gray < ink_threshold
    else:
        binarize_fn = BINARIZE_FUNCTIONS[binarize]
        old_bin = convert_to_grayscale(binarize_fn(aligned_old))
        new_bin = convert_to_grayscale(binarize_fn(new))
        # Binarized output: black (0) = content, white (255) = background
        old_mask = old_bin < 128
        new_mask = new_bin < 128

    # Change detection: only count differences above diff_threshold
    diff = cv2.absdiff(old_gray, new_gray)
    strong_diff_mask = diff > diff_threshold

    removed = old_mask & ~new_mask & strong_diff_mask
    added = new_mask & ~old_mask & strong_diff_mask

    if not skip_morph:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (morph_kernel_size, morph_kernel_size))
        removed = cv2.morphologyEx(removed.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel) > 0
        added = cv2.morphologyEx(added.astype(np.uint8) * 255, cv2.MORPH_OPEN, kernel) > 0

    if shift_tolerance > 0:
        shift_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (shift_tolerance, shift_tolerance))
        dilated_new = cv2.dilate(new_mask.astype(np.uint8), shift_kernel) > 0
        dilated_old = cv2.dilate(old_mask.astype(np.uint8), shift_kernel) > 0
        removed = removed & ~(removed & dilated_new)
        added = added & ~(added & dilated_old)

    unchanged = old_mask & new_mask

    overlay = np.full_like(aligned_old, 255, dtype=np.uint8)

    # Removed areas: blend original grayscale with red tint
    if np.any(removed):
        removed_gray = old_gray[removed].astype(np.float32)
        removed_rgb = np.column_stack([removed_gray, removed_gray, removed_gray])
        red_tint = np.array([255.0, 0.0, 0.0])
        overlay[removed] = np.clip(
            removed_rgb * (1 - tint_strength) + red_tint * tint_strength,
            0, 255
        ).astype(np.uint8)

    # Added areas: blend original grayscale with green tint
    if np.any(added):
        added_gray = new_gray[added].astype(np.float32)
        added_rgb = np.column_stack([added_gray, added_gray, added_gray])
        green_tint = np.array([0.0, 255.0, 0.0])
        overlay[added] = np.clip(
            added_rgb * (1 - tint_strength) + green_tint * tint_strength,
            0, 255
        ).astype(np.uint8)

    overlay[unchanged] = np.stack([old_gray[unchanged]] * 3, axis=-1)

    deletion = np.full_like(aligned_old, 255, dtype=np.uint8)
    deletion[removed] = [0, 0, 0]

    addition = np.full_like(new, 255, dtype=np.uint8)
    addition[added] = [0, 0, 0]

    return overlay, deletion, addition


# =============================================================================
# Binarization Functions
# =============================================================================

def binarize_none(img: np.ndarray) -> np.ndarray:
    """No binarization - return image as-is."""
    return img


def binarize_basic(img: np.ndarray, intensity_thresh: int = 220) -> np.ndarray:
    """Simple intensity threshold binarization."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    binary = np.where(gray < intensity_thresh, 0, 255).astype(np.uint8)
    return np.stack([binary, binary, binary], axis=-1)


def binarize_remove_fills(img: np.ndarray, intensity_thresh: int = 220, saturation_thresh: int = 50) -> np.ndarray:
    """Remove colored fills using saturation filtering, then binarize."""
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    saturation = hsv[:, :, 1]
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    # Set saturated pixels (colored fills) to white
    gray[saturation > saturation_thresh] = 255
    binary = np.where(gray < intensity_thresh, 0, 255).astype(np.uint8)
    return np.stack([binary, binary, binary], axis=-1)


def binarize_canny_edge(img: np.ndarray, low_thresh: int = 50, high_thresh: int = 150) -> np.ndarray:
    """Extract edges using Canny edge detection."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, low_thresh, high_thresh)
    # Invert: edges become black on white background
    binary = 255 - edges
    return np.stack([binary, binary, binary], axis=-1)


BINARIZE_FUNCTIONS = {
    "none": binarize_none,
    "basic": binarize_basic,
    "remove-fills": binarize_remove_fills,
    "canny-edge": binarize_canny_edge,
}


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Align images and generate overlay outputs")
    parser.add_argument("--old", required=True, help="Path to old image")
    parser.add_argument("--new", required=True, help="Path to new image")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--prefix", default="")

    # Binarization options
    parser.add_argument(
        "--binarize",
        choices=["none", "basic", "remove-fills", "canny-edge"],
        default="canny-edge",
        help="Binarization method",
    )

    # Alignment options
    parser.add_argument(
        "--align",
        choices=["grid", "scipy-sift", "basic-sift"],
        default="grid",
        help="Alignment method: grid (with SIFT refinement), scipy-sift (optimized), basic-sift (simple)",
    )
    parser.add_argument("--sift-scale", type=float, default=1.0, help="SIFT downsample scale")
    parser.add_argument("--ratio-threshold", type=float, default=0.75, help="Lowe's ratio test threshold (lower=stricter, default=0.75)")
    parser.add_argument("--contrast-threshold", type=float, default=0.02, help="SIFT contrast threshold (lower=more features, default=0.02)")
    parser.add_argument("--no-normalize-size", action="store_true", help="Disable pre-scaling images to similar size")

    # Overlay options
    parser.add_argument("--ink-threshold", type=int, default=200, help="Pixels darker than this are 'ink' (0-255, default 200)")
    parser.add_argument("--diff-threshold", type=int, default=40, help="Min pixel difference to count as change (0-255, default 40)")
    parser.add_argument("--morph-kernel", type=int, default=1)
    parser.add_argument("--skip-morph", action="store_true")
    parser.add_argument("--shift-tolerance", type=int, default=3, help="Ignore changes within this pixel distance of content in other image (default: 3)")
    parser.add_argument("--tint-strength", type=float, default=0.5, help="Diff color blend (0=grayscale, 1=pure color, default: 0.5)")
    parser.add_argument("--merge-mode", action="store_true", help="Merge both images: old=red tint, new=green tint, overlap=gray")
    parser.add_argument(
        "--overlay-binarize",
        choices=["none", "basic", "remove-fills", "canny-edge"],
        default="none",
        help="Binarization method for overlay generation (default: none)",
    )

    args = parser.parse_args()

    old_path = Path(args.old)
    new_path = Path(args.new)
    base_output_dir = Path(args.output_dir)

    if not old_path.exists() or not new_path.exists():
        print("Error: Input files not found")
        return

    # Create subfolder named "oldname_to_newname"
    subfolder_name = f"{old_path.stem}_to_{new_path.stem}"
    output_dir = base_output_dir / subfolder_name
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"{args.prefix}_" if args.prefix else ""

    print("=" * 60)
    print("Image Alignment + Overlay Generation")
    print("=" * 60)
    print(f"Output: {output_dir}")

    # Load original images
    old_img_original = load_image(old_path)
    new_img_original = load_image(new_path)
    print(f"Old: {old_img_original.shape}, New: {new_img_original.shape}")

    # Binarize copies for alignment (keep originals)
    binarize_fn = BINARIZE_FUNCTIONS[args.binarize]
    old_img_bin = binarize_fn(old_img_original)
    new_img_bin = binarize_fn(new_img_original)
    print(f"Alignment binarization: {args.binarize}")
    save_image(old_img_bin, output_dir / f"{prefix}binarized_old.png")
    save_image(new_img_bin, output_dir / f"{prefix}binarized_new.png")

    # Step 1: Alignment (using binarized images)
    print()
    print("-" * 60)
    print(f"Step 1: Alignment ({args.align})")
    print("-" * 60)

    if args.align == "grid":
        _, _, align_stats = align_with_grid(old_img_bin, new_img_bin, old_path, new_path)

    elif args.align == "scipy-sift":
        _, _, align_stats = scipy_sift_align(
            old_img_bin, new_img_bin,
            downsample_scale=args.sift_scale,
            n_features=20000,
            ratio_threshold=args.ratio_threshold,
            ransac_threshold=15.0,
            max_iters=10000,
            rotation_deg_min=-3.0,
            rotation_deg_max=3.0,
            scale_min=0.2,
            scale_max=5.0,
            expand_canvas=True,
            normalize_size=not args.no_normalize_size,
            contrast_threshold=args.contrast_threshold,
        )

    elif args.align == "basic-sift":
        _, _, align_stats = basic_sift_align(
            old_img_bin, new_img_bin,
            downsample_scale=args.sift_scale,
            n_features=20000,
            ratio_threshold=args.ratio_threshold,
            reproj_threshold=15.0,
            max_iters=10000,
            scale_min=0.2,
            scale_max=5.0,
            rotation_deg_min=-3.0,
            rotation_deg_max=3.0,
            expand_canvas=True,
        )
        align_stats["method"] = "basic-sift"

    del old_img_bin, new_img_bin
    gc.collect()

    # Apply alignment transform to original images
    print("  Applying transform to original images...")
    aligned_old, aligned_new = apply_alignment_to_images(old_img_original, new_img_original, align_stats)

    del old_img_original, new_img_original
    gc.collect()

    # Step 2: Overlay generation
    print()
    print("-" * 60)
    print("Step 2: Overlay Generation")
    print("-" * 60)
    overlay, deletion, addition = generate_overlay(
        aligned_old, aligned_new,
        ink_threshold=args.ink_threshold,
        diff_threshold=args.diff_threshold,
        morph_kernel_size=args.morph_kernel,
        skip_morph=args.skip_morph,
        shift_tolerance=args.shift_tolerance,
        binarize=args.overlay_binarize,
        tint_strength=args.tint_strength,
        merge_mode=args.merge_mode,
    )

    # Step 3: Save outputs
    print()
    print("-" * 60)
    print("Step 3: Saving Outputs")
    print("-" * 60)
    save_image(aligned_old, output_dir / f"{prefix}aligned_old.png")
    save_image(aligned_new, output_dir / f"{prefix}aligned_new.png")
    save_image(overlay, output_dir / f"{prefix}overlay.png")
    save_image(deletion, output_dir / f"{prefix}deletion.png")
    save_image(addition, output_dir / f"{prefix}addition.png")

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Alignment binarization: {args.binarize}")
    print(f"Overlay binarization: {args.overlay_binarize}")
    print(f"Overlay mode: {'merge (red/green tint)' if args.merge_mode else 'diff'}")
    print(f"Alignment: {args.align}")
    method = align_stats.get('method', '')
    if method == 'grid':
        print(f"  Grid matches: H={align_stats['h_matches']}, V={align_stats['v_matches']}")
        print(f"  Scale: ({align_stats['scale_x']:.4f}, {align_stats['scale_y']:.4f})")
        if align_stats.get('sift_refined'):
            print(f"  SIFT refined: scale={align_stats['sift_scale']:.4f}, rot={align_stats['sift_rotation']:.2f}°")
    else:
        print(f"  Inlier ratio: {align_stats.get('inlier_ratio', 0):.1%}")
        print(f"  Scale: {align_stats.get('scale', 1):.4f}, Rotation: {align_stats.get('rotation_deg', 0):.2f}°")
    print(f"Canvas: {align_stats.get('expanded_width', 0)}x{align_stats.get('expanded_height', 0)}")
    print(f"Deletions: {count_pixels(deletion):,} pixels")
    print(f"Additions: {count_pixels(addition):,} pixels")
    print(f"\nOutputs: {output_dir}")
    print("=" * 60)

    # Print token usage summary with cost estimates (per 1M tokens)
    model_costs = {
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cached": 0.03},
        "gemini-3-flash": {"input": 0.50, "output": 3.00, "cached": 0.05},
        "gemini-3-pro-preview": {"input": 2.00, "output": 12.00, "cached": 0.20},
    }
    print_token_usage_summary(model_costs)


if __name__ == "__main__":
    main()
