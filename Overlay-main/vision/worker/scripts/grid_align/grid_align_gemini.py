"""
Grid-Based Image Alignment using Gemini Vision + OpenCV

Usage:
    python grid_align_gemini.py --old old.png --new new.png
    python grid_align_gemini.py --single --old image.png  # Debug single image
"""

import argparse
import io
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from google import genai
from google.genai import types

Image.MAX_IMAGE_PIXELS = 250_000_000

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3-pro-preview"
TARGET_DPI = 100

SCRIPT_DIR = Path(__file__).parent
DATASET_DIR = SCRIPT_DIR / "dataset"
OUTPUT_DIR = SCRIPT_DIR / "outputs"
INTERMEDIATE_DIR = SCRIPT_DIR / "intermediates"

# Colors (BGR)
COLORS = {
    "circle": (255, 0, 255),  # Magenta
    "bbox": (0, 255, 255),  # Yellow
    "horizontal": (255, 0, 0),  # Blue
    "vertical": (0, 255, 0),  # Green
    "label": (0, 165, 255),  # Orange
}


# Pydantic models for Gemini response
class GridCalloutBBox(BaseModel):
    label: str = Field(description="The alphanumeric label inside the circle")
    xmin: int = Field(description="Left X coordinate (0-1000 normalized)")
    ymin: int = Field(description="Top Y coordinate (0-1000 normalized)")
    xmax: int = Field(description="Right X coordinate (0-1000 normalized)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000 normalized)")
    edge: str = Field(description="Which edge: 'top', 'bottom', 'left', 'right'")


class GridCalloutsResponse(BaseModel):
    callouts: list[GridCalloutBBox]


# Data classes
@dataclass
class DetectedCallout:
    label: str
    center_x: int
    center_y: int
    radius: int
    edge: str
    bbox: tuple[int, int, int, int]


@dataclass
class DetectedGridLine:
    orientation: str  # 'horizontal' or 'vertical'
    position: float  # y for horizontal, x for vertical
    callout: DetectedCallout


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


SYSTEM_PROMPT = """You are an expert at analyzing architectural and construction drawings.

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


def detect_callouts_with_gemini(
    image_path: Path, w: int, h: int
) -> list[tuple[str, tuple[int, int, int, int], str]]:
    """Use Gemini to detect grid callout bounding boxes."""
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not found")
        sys.exit(1)

    # Downscale for Gemini
    img = Image.open(image_path)
    scale = TARGET_DPI / 300.0
    img_small = img.resize(
        (int(img.width * scale), int(img.height * scale)), Image.Resampling.LANCZOS
    )
    buffer = io.BytesIO()
    img_small.save(buffer, format="PNG")
    png_bytes = buffer.getvalue()

    print(f"[Gemini] Detecting callouts ({img_small.width}x{img_small.height})...")

    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=SYSTEM_PROMPT),
                        types.Part.from_text(
                            text="Find all grid reference callouts in this construction drawing."
                        ),
                        types.Part.from_bytes(mime_type="image/png", data=png_bytes),
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
            x1 = int(c.xmin * w / 1000)
            y1 = int(c.ymin * h / 1000)
            x2 = int(c.xmax * w / 1000)
            y2 = int(c.ymax * h / 1000)
            results.append((c.label, (x1, y1, x2, y2), c.edge))

        print(f"  Found {len(results)} callouts")
        return results

    except Exception as e:
        print(f"  Error: {e}")
        return []


def detect_circle_in_crop(
    crop: np.ndarray, min_radius: int, max_radius: int
) -> tuple[int, int, int] | None:
    """Detect circle in cropped region. Returns (cx, cy, radius) or None."""
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


def detect_grid_line(
    gray: np.ndarray, cx: int, cy: int, radius: int, edge: str
) -> tuple[str, float] | None:
    """Detect grid line touching circle. Returns (orientation, position) or None."""
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


def process_callout(
    full_image: np.ndarray,
    gray: np.ndarray,
    label: str,
    bbox: tuple[int, int, int, int],
    edge: str,
    save_debug: bool = False,
    debug_dir: Path | None = None,
    idx: int = 0,
) -> tuple[DetectedCallout, DetectedGridLine | None] | None:
    """Process a single callout: detect circle and grid line."""
    h, w = full_image.shape[:2]
    x1, y1, x2, y2 = bbox
    padding = 50

    crop_x1, crop_y1 = max(0, x1 - padding), max(0, y1 - padding)
    crop_x2, crop_y2 = min(w, x2 + padding), min(h, y2 + padding)
    crop = full_image[crop_y1:crop_y2, crop_x1:crop_x2].copy()

    if crop.size == 0:
        return None

    bbox_w, bbox_h = x2 - x1, y2 - y1
    est_radius = min(bbox_w, bbox_h) // 2
    min_r, max_r = max(10, est_radius - 100), est_radius + 100

    circle = detect_circle_in_crop(crop, min_r, max_r)

    # Debug visualization
    crop_debug = crop.copy()
    bbox_in_crop = (x1 - crop_x1, y1 - crop_y1, x2 - crop_x1, y2 - crop_y1)
    cv2.rectangle(
        crop_debug,
        (bbox_in_crop[0], bbox_in_crop[1]),
        (bbox_in_crop[2], bbox_in_crop[3]),
        COLORS["bbox"],
        2,
    )

    if circle is None:
        print(f"  [{idx}] '{label}': No circle found, skipping")
        if save_debug and debug_dir:
            cv2.imwrite(str(debug_dir / f"{idx:02d}_{label}_FAILED.png"), crop_debug)
        return None

    cx_crop, cy_crop, radius = circle
    cx, cy = cx_crop + crop_x1, cy_crop + crop_y1

    cv2.circle(crop_debug, (cx_crop, cy_crop), radius, COLORS["circle"], 3)
    cv2.circle(crop_debug, (cx_crop, cy_crop), 5, COLORS["circle"], -1)

    # Detect grid line
    line_result = detect_grid_line(gray, cx, cy, radius, edge)
    grid_line = None

    if line_result:
        orientation, position = line_result
        grid_line = DetectedGridLine(orientation=orientation, position=position, callout=None)

        # Draw line on debug
        if orientation == "horizontal":
            ly = int(position - crop_y1)
            if 0 <= ly < crop_debug.shape[0]:
                cv2.line(crop_debug, (0, ly), (crop_debug.shape[1], ly), COLORS["horizontal"], 2)
        else:
            lx = int(position - crop_x1)
            if 0 <= lx < crop_debug.shape[1]:
                cv2.line(crop_debug, (lx, 0), (lx, crop_debug.shape[0]), COLORS["vertical"], 2)

    if save_debug and debug_dir:
        cv2.imwrite(str(debug_dir / f"{idx:02d}_{label}.png"), crop_debug)

    callout = DetectedCallout(
        label=label, center_x=cx, center_y=cy, radius=radius, edge=edge, bbox=bbox
    )
    if grid_line:
        grid_line.callout = callout

    orientation_str = grid_line.orientation if grid_line else "fallback"
    pos = grid_line.position if grid_line else (cy if edge in ["left", "right"] else cx)
    print(f"  [{idx}] '{label}': ({cx}, {cy}) r={radius}, {orientation_str} @ {pos:.0f}")

    return (callout, grid_line)


def process_image(image_path: Path, save_debug: bool = False, debug_dir: Path | None = None):
    """Process single image to detect grid callouts and lines."""
    print(f"\nProcessing: {image_path.name}")

    full_image = cv2.imread(str(image_path))
    if full_image is None:
        raise ValueError(f"Could not read: {image_path}")

    h, w = full_image.shape[:2]
    gray = cv2.cvtColor(full_image, cv2.COLOR_BGR2GRAY)
    print(f"  Size: {w}x{h}")

    if save_debug and debug_dir:
        debug_dir.mkdir(parents=True, exist_ok=True)

    gemini_results = detect_callouts_with_gemini(image_path, w, h)
    if not gemini_results:
        return [], [], full_image

    callouts, grid_lines = [], []
    for idx, (label, bbox, edge) in enumerate(gemini_results):
        result = process_callout(full_image, gray, label, bbox, edge, save_debug, debug_dir, idx)
        if result:
            callout, grid_line = result
            callouts.append(callout)
            if grid_line:
                grid_lines.append(grid_line)
            else:
                # Fallback: use callout position as grid line
                orientation = "horizontal" if edge in ["left", "right"] else "vertical"
                position = callout.center_y if orientation == "horizontal" else callout.center_x
                grid_lines.append(
                    DetectedGridLine(orientation=orientation, position=position, callout=callout)
                )

    print(f"  Result: {len(callouts)} callouts, {len(grid_lines)} grid lines")

    # Create visualization
    vis = full_image.copy()
    for line in grid_lines:
        color = COLORS[line.orientation]
        if line.orientation == "horizontal":
            cv2.line(vis, (0, int(line.position)), (w, int(line.position)), color, 3)
        else:
            cv2.line(vis, (int(line.position), 0), (int(line.position), h), color, 3)

    for c in callouts:
        cv2.rectangle(vis, (c.bbox[0], c.bbox[1]), (c.bbox[2], c.bbox[3]), COLORS["bbox"], 2)
        cv2.circle(vis, (c.center_x, c.center_y), c.radius, COLORS["circle"], 3)
        cv2.putText(
            vis,
            c.label,
            (c.center_x - 20, c.center_y - c.radius - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            COLORS["label"],
            2,
        )

    return callouts, grid_lines, vis


def match_grid_lines(
    old_lines: list[DetectedGridLine], new_lines: list[DetectedGridLine]
) -> list[GridMatch]:
    """Match grid lines between images by label."""
    new_h = {l.callout.label: l for l in new_lines if l.orientation == "horizontal"}
    new_v = {l.callout.label: l for l in new_lines if l.orientation == "vertical"}

    matches = []
    for old in old_lines:
        label = old.callout.label
        if old.orientation == "horizontal" and label in new_h:
            matches.append(GridMatch(label, "horizontal", old.position, new_h[label].position))
        elif old.orientation == "vertical" and label in new_v:
            matches.append(GridMatch(label, "vertical", old.position, new_v[label].position))

    return matches


def calculate_transformation(matches: list[GridMatch]) -> AlignmentTransform | None:
    """Calculate affine transformation from matched grid lines."""
    h_matches = [m for m in matches if m.orientation == "horizontal"]
    v_matches = [m for m in matches if m.orientation == "vertical"]

    if not h_matches and not v_matches:
        return None

    # Y-axis from horizontal matches
    if len(h_matches) >= 2:
        old_y = np.array([m.old_position for m in h_matches])
        new_y = np.array([m.new_position for m in h_matches])
        A = np.vstack([old_y, np.ones(len(old_y))]).T
        scale_y, translate_y = np.linalg.lstsq(A, new_y, rcond=None)[0]
    elif len(h_matches) == 1:
        scale_y, translate_y = 1.0, h_matches[0].new_position - h_matches[0].old_position
    else:
        scale_y, translate_y = 1.0, 0.0

    # X-axis from vertical matches
    if len(v_matches) >= 2:
        old_x = np.array([m.old_position for m in v_matches])
        new_x = np.array([m.new_position for m in v_matches])
        A = np.vstack([old_x, np.ones(len(old_x))]).T
        scale_x, translate_x = np.linalg.lstsq(A, new_x, rcond=None)[0]
    elif len(v_matches) == 1:
        scale_x, translate_x = 1.0, v_matches[0].new_position - v_matches[0].old_position
    else:
        scale_x, translate_x = 1.0, 0.0

    return AlignmentTransform(
        scale_x, scale_y, translate_x, translate_y, len(h_matches), len(v_matches)
    )


def apply_transformation(
    image: np.ndarray, transform: AlignmentTransform, output_size: tuple[int, int]
) -> np.ndarray:
    """Apply affine transformation."""
    matrix = np.array(
        [
            [transform.scale_x, 0, transform.translate_x],
            [0, transform.scale_y, transform.translate_y],
        ],
        dtype=np.float64,
    )
    return cv2.warpAffine(
        image,
        matrix,
        output_size,
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255),
    )


def create_overlay(new_image: np.ndarray, aligned_old: np.ndarray) -> np.ndarray:
    """Create red/cyan overlay visualization."""
    h, w = new_image.shape[:2]
    if aligned_old.shape[:2] != (h, w):
        aligned_old = cv2.resize(aligned_old, (w, h))

    old_gray = (
        cv2.cvtColor(aligned_old, cv2.COLOR_BGR2GRAY)
        if len(aligned_old.shape) == 3
        else aligned_old
    )
    new_gray = (
        cv2.cvtColor(new_image, cv2.COLOR_BGR2GRAY) if len(new_image.shape) == 3 else new_image
    )

    overlay = np.zeros((h, w, 3), dtype=np.uint8)
    overlay[:, :, 2] = old_gray  # Red = old
    overlay[:, :, 1] = new_gray  # Green = new
    overlay[:, :, 0] = new_gray  # Blue = new
    return overlay


def align_images(old_path: Path, new_path: Path, output_dir: Path) -> AlignmentTransform | None:
    """Main alignment pipeline."""
    _, old_lines, old_vis = process_image(old_path)
    _, new_lines, new_vis = process_image(new_path)

    cv2.imwrite(str(output_dir / "01_grid_old.png"), old_vis)
    cv2.imwrite(str(output_dir / "01_grid_new.png"), new_vis)

    matches = match_grid_lines(old_lines, new_lines)
    print(f"\nMatched {len(matches)} grid lines:")
    for m in matches:
        print(f"  '{m.label}' ({m.orientation}): {m.old_position:.0f} -> {m.new_position:.0f}")

    if not matches:
        print("ERROR: No matching grid lines!")
        return None

    transform = calculate_transformation(matches)
    if not transform:
        print("ERROR: Could not calculate transformation!")
        return None

    old_image = cv2.imread(str(old_path))
    new_image = cv2.imread(str(new_path))
    new_h, new_w = new_image.shape[:2]

    aligned_old = apply_transformation(old_image, transform, (new_w, new_h))

    cv2.imwrite(str(output_dir / "02_aligned_old.png"), aligned_old)
    cv2.imwrite(str(output_dir / "02_new.png"), new_image)
    cv2.imwrite(str(output_dir / "03_overlay.png"), create_overlay(new_image, aligned_old))

    print(
        f"\nTransform: scale=({transform.scale_x:.4f}, {transform.scale_y:.4f}), "
        f"translate=({transform.translate_x:.1f}, {transform.translate_y:.1f})"
    )
    print(f"Matches: H={transform.h_matches}, V={transform.v_matches}")

    return transform


def main():
    parser = argparse.ArgumentParser(description="Grid-based image alignment")
    parser.add_argument("--old", default=str(DATASET_DIR / "bower_ceiling_2.png"))
    parser.add_argument("--new", default=str(DATASET_DIR / "bower_plenum_2.png"))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    parser.add_argument(
        "--single", action="store_true", help="Process single image with debug output"
    )

    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.single:
        image_path = Path(args.old)
        if not image_path.exists():
            print(f"Error: {image_path} not found")
            sys.exit(1)

        debug_dir = INTERMEDIATE_DIR / image_path.stem
        callouts, grid_lines, vis = process_image(image_path, save_debug=True, debug_dir=debug_dir)
        cv2.imwrite(str(output_dir / f"grid_{image_path.stem}.png"), vis)
        print(f"\nOutput: {output_dir / f'grid_{image_path.stem}.png'}")
        print(f"Debug: {debug_dir}")
    else:
        old_path, new_path = Path(args.old), Path(args.new)
        if not old_path.exists() or not new_path.exists():
            print("Error: Input files not found")
            sys.exit(1)

        transform = align_images(old_path, new_path, output_dir)
        if transform:
            print(f"\nOutputs saved to: {output_dir}")
        else:
            sys.exit(1)


if __name__ == "__main__":
    main()
