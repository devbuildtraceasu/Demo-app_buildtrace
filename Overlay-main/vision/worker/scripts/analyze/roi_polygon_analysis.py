"""
Polygon ROI-based Change Analysis Pipeline

This script:
1. Extracts polygon ROIs from addition and deletion diff images
2. Merges overlapping polygons from both images
3. Creates masked crops (rectangular with regions outside polygon whitened)
4. Feeds each masked ROI crop to Gemini for change analysis
5. Combines all change lists and maps local coordinates to global coordinates
6. Draws final results on the full overlay image
"""

import base64
import json
import os
import sys
from collections import defaultdict
from dataclasses import dataclass

import cv2
import numpy as np
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Add worker root to path
worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(worker_root)

# Add segmentation scripts to path
segmentation_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../segmentation"))
sys.path.append(segmentation_dir)

# Load .env from worker root
load_dotenv(os.path.join(worker_root, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3-pro-preview"

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment.")
    sys.exit(1)


@dataclass
class PolygonROI:
    """Polygon region of interest with bounding box for cropping."""

    polygon: np.ndarray  # Shape (N, 1, 2) - OpenCV contour format
    bounding_box: tuple[int, int, int, int]  # (x, y, w, h)
    area: float  # Polygon area
    centroid: tuple[int, int]  # (cx, cy)
    source: str = ""  # "addition" or "deletion" or "merged"

    @property
    def x(self) -> int:
        return self.bounding_box[0]

    @property
    def y(self) -> int:
        return self.bounding_box[1]

    @property
    def w(self) -> int:
        return self.bounding_box[2]

    @property
    def h(self) -> int:
        return self.bounding_box[3]

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def bbox_area(self) -> int:
        return self.w * self.h


class Location(BaseModel):
    xmin: int = Field(description="Left X coordinate (0-1000)")
    ymin: int = Field(description="Top Y coordinate (0-1000)")
    xmax: int = Field(description="Right X coordinate (0-1000)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000)")


class Change(BaseModel):
    action: str = Field(description="Type of change: 'Add', 'Remove', 'Dimension Change', 'Move'")
    elements: list[str] = Field(description="The items or objects that are changing or modified")
    direction: str | None = Field(None, description="Direction of change")
    value: list[str] | None = Field(
        None, description="List of [start_value, final_value] if applicable"
    )
    location: Location = Field(description="Bounding box of the change")


class ChangeList(BaseModel):
    changes: list[Change] = Field(description="List of detected changes")


SYSTEM_PROMPT_OVERLAY = """You are an expert architectural document analyzer.
Your task is to identify and locate all REAL architectural changes visible in this construction drawing overlay.

The overlay shows:
- GREEN areas: NEW/ADDED features from the previous version
- RED areas: REMOVED/DELETED features from the previous version
- Areas with both colors may indicate MOVED or MODIFIED elements

## Architectural Element Types to Detect

**Structural:**
Wall, Column, Beam, Foundation, Slab, Floor, Roof, Staircase, Ramp, Elevator shaft

**Openings:**
Door (single/double/sliding/pocket/revolving), Window, Opening, Skylight, Curtain wall

**Plumbing Fixtures:**
Toilet, Urinal, Sink, Lavatory, Bathtub, Shower, Floor drain, Drinking fountain, Mop sink, Baptistry/Font

**Mechanical/HVAC:**
Duct, Diffuser, Register, Return air grille, HVAC unit, Thermostat

**Electrical:**
Outlet, Receptacle, Switch, Light fixture, Electrical panel, Junction box

**Furniture/Equipment:**
Casework, Cabinet, Countertop, Shelving, Bench, Seating, Table, Equipment, Appliance

**Site/Landscape:**
Tree, Shrub, Planting, Paving, Curb, Parking space, Fence, Gate

**Accessibility:**
Handrail, Guardrail, Grab bar, Wheelchair clearance, ADA ramp

## Elements to EXCLUDE (Annotations)
Do NOT report changes to: Text, Label, Room tag, Door tag, Window tag, Section callout, Detail callout, Elevation tag, Grid line, Leader, Arrow, Revision cloud, Markup, Note, Symbol

## Instructions

CRITICAL:
- EVERY SINGLE real architectural/structural change in the GREEN and RED areas should be covered by a bounding box.
- Group related elements (e.g., a door and its swing) if spatially close, but do not group unrelated elements.
- When multiple elements all move together, report them as a single change, typically a "Move" or "Dimension Change" for an entire room, wall, or area.
- When encountering a 'Remove', 'Add' or 'Dimension Change' action, think carefully about whether it is actually a 'Move' by looking around in the vicinity and determining whether the element is simplify shifted

For each change provide:
1. **elements**: The architectural element types from the lists above
2. **action**: 'Add' (green only), 'Remove' (red only), 'Move' (both colors offset), 'Dimension Change' (resized)
3. **direction**: 'up', 'down', 'left', 'right' (only for Move actions)
4. **value**: ['start_value', 'final_value'] (only for Dimension Change)
5. **location**: Tight bounding box, coordinates should be normalized to 1000x1000 grid (0-1000).
"""


SYSTEM_PROMPT_REVIEWER = """You are an expert architectural document reviewer.
Your task is to VALIDATE and REFINE a list of detected changes in a construction drawing.

You are provided with:
1. **OVERLAY IMAGE with BOUNDING BOXES**: The diff visualization with blue boxes showing initially detected changes
2. **INITIAL CHANGE LIST**: JSON list of detected changes with their locations

## Your Review Tasks

**1. COMPLETENESS CHECK:**
- Look for GREEN or RED areas in the overlay that are NOT covered by any blue bounding box
- These are MISSED changes that should be added
- Only add changes for architectural elements (walls, doors, fixtures, etc.), NOT annotations

**2. ACCURACY CHECK:**
- Check if any blue bounding box is pointing to a GRAY area (unchanged content)
- These are FALSE POSITIVES that should be removed
- Gray areas are NOT changes - only green and red areas represent actual changes

**3. POSITION CHECK:**
- Verify each bounding box accurately covers its target change
- Adjust coordinates if a box is misaligned or too large/small

**4. CATEGORY CHECK:**
- Ensure no annotation-only changes are included (text, labels, tags, symbols, callouts)
- Remove any that slipped through

## Output

Produce a REFINED change list that:
- Keeps correctly identified changes (with adjusted positions if needed)
- Removes false positives (boxes on gray areas or annotation-only changes)
- Adds any missed architectural changes

Use the same element types: Wall, Door, Window, Column, Staircase, Toilet, Sink, Shower, etc.
Bounding box coordinates should be normalized to 1000x1000 grid (0-1000).
"""


def downsample_image(image: np.ndarray, scale: float = 1 / 3) -> np.ndarray:
    """
    Downsample image by a scale factor.
    Default scale=1/3 converts 300 DPI to 100 DPI.
    """
    if scale >= 1.0:
        return image
    new_width = int(image.shape[1] * scale)
    new_height = int(image.shape[0] * scale)
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)


def image_array_to_base64_png(image: np.ndarray) -> bytes:
    """Convert numpy image array to PNG bytes."""
    _, buffer = cv2.imencode(".png", image)
    return buffer.tobytes()


def compute_centroid(contour: np.ndarray) -> tuple[int, int]:
    """Compute centroid of a contour using moments."""
    M = cv2.moments(contour)
    if M["m00"] != 0:
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
    else:
        x, y, w, h = cv2.boundingRect(contour)
        cx, cy = x + w // 2, y + h // 2
    return (cx, cy)


def extract_polygon_rois(
    image_path: str,
    source_label: str = "",
    epsilon_factor: float = 0.005,
    min_area_ratio: float = 0.001,
) -> list[PolygonROI]:
    """
    Extract polygon ROIs from an image using the polygon segmentation algorithm.

    Args:
        image_path: Path to input image
        source_label: Label for source ("addition" or "deletion")
        epsilon_factor: Polygon simplification factor
        min_area_ratio: Minimum region area as ratio of image area

    Returns:
        List of PolygonROI objects
    """
    img = cv2.imread(image_path)
    if img is None:
        return []

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)

    h, w = img.shape[:2]

    # Line Removal (50% threshold)
    h_kernel_len = int(w * 0.50)
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (h_kernel_len, 1))
    h_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, h_kernel)

    v_kernel_len = int(h * 0.50)
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, v_kernel_len))
    v_lines = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, v_kernel)

    lines = cv2.add(h_lines, v_lines)
    content = cv2.subtract(thresh, lines)

    # Dilation to group nearby content
    k_w = max(3, int(w * 0.015))
    k_h = max(3, int(h * 0.015))

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
    dilated_h = cv2.dilate(content, kernel_h, iterations=1)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))
    dilated = cv2.dilate(dilated_h, kernel_v, iterations=3)

    # Find contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = (w * h) * min_area_ratio
    regions = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        bbox_area = cw * ch

        if bbox_area < min_area:
            continue

        # Get dilated ROI contour for polygon approximation
        dilated_roi = dilated[y : y + ch, x : x + cw]
        dilated_contours, _ = cv2.findContours(
            dilated_roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        if not dilated_contours:
            continue

        largest_dilated = max(dilated_contours, key=cv2.contourArea)

        # Apply polygon approximation
        perimeter = cv2.arcLength(largest_dilated, True)
        epsilon = epsilon_factor * perimeter
        approx_poly = cv2.approxPolyDP(largest_dilated, epsilon, True)

        # Offset to global coordinates
        approx_poly_global = approx_poly.copy()
        approx_poly_global[:, 0, 0] += x
        approx_poly_global[:, 0, 1] += y

        poly_area = cv2.contourArea(approx_poly_global)
        if poly_area < min_area:
            continue

        bbox = cv2.boundingRect(approx_poly_global)
        centroid = compute_centroid(approx_poly_global)

        region = PolygonROI(
            polygon=approx_poly_global,
            bounding_box=bbox,
            area=poly_area,
            centroid=centroid,
            source=source_label,
        )
        regions.append(region)

    regions.sort(key=lambda r: r.area, reverse=True)
    return regions


def compute_polygon_iou(poly1: np.ndarray, poly2: np.ndarray, img_shape: tuple[int, int]) -> float:
    """
    Compute IoU between two polygons using mask-based intersection.

    Args:
        poly1, poly2: Polygon contours in OpenCV format
        img_shape: (height, width) of the image for creating masks

    Returns:
        IoU value between 0 and 1
    """
    h, w = img_shape

    # Create masks for both polygons
    mask1 = np.zeros((h, w), dtype=np.uint8)
    mask2 = np.zeros((h, w), dtype=np.uint8)

    cv2.fillPoly(mask1, [poly1], 255)
    cv2.fillPoly(mask2, [poly2], 255)

    # Compute intersection and union
    intersection = cv2.bitwise_and(mask1, mask2)
    union = cv2.bitwise_or(mask1, mask2)

    intersection_area = np.sum(intersection > 0)
    union_area = np.sum(union > 0)

    return intersection_area / union_area if union_area > 0 else 0.0


def compute_polygon_containment(
    poly1: np.ndarray, poly2: np.ndarray, img_shape: tuple[int, int]
) -> float:
    """
    Compute how much of the smaller polygon is contained in the larger.

    Returns:
        Ratio of intersection to smaller polygon area
    """
    h, w = img_shape

    mask1 = np.zeros((h, w), dtype=np.uint8)
    mask2 = np.zeros((h, w), dtype=np.uint8)

    cv2.fillPoly(mask1, [poly1], 255)
    cv2.fillPoly(mask2, [poly2], 255)

    intersection = cv2.bitwise_and(mask1, mask2)

    area1 = np.sum(mask1 > 0)
    area2 = np.sum(mask2 > 0)
    intersection_area = np.sum(intersection > 0)

    smaller_area = min(area1, area2)
    return intersection_area / smaller_area if smaller_area > 0 else 0.0


def merge_polygon_pair(poly1: np.ndarray, poly2: np.ndarray) -> np.ndarray:
    """
    Merge two polygons into their convex hull union.
    """
    all_points = np.vstack([poly1, poly2])
    hull = cv2.convexHull(all_points)
    return hull


def merge_overlapping_polygons(
    polygons: list[PolygonROI],
    img_shape: tuple[int, int],
    iou_threshold: float = 0.2,
    containment_threshold: float = 0.6,
) -> list[PolygonROI]:
    """
    Merge polygons that overlap significantly.

    Args:
        polygons: List of PolygonROI objects
        img_shape: (height, width) for mask computations
        iou_threshold: Minimum IoU for merging
        containment_threshold: Minimum containment ratio for merging

    Returns:
        List of merged PolygonROI objects
    """
    if not polygons:
        return []

    # Sort by area (largest first)
    polygons = sorted(polygons, key=lambda p: p.area, reverse=True)
    merged = []
    used = set()

    for i, roi1 in enumerate(polygons):
        if i in used:
            continue

        current_poly = roi1.polygon.copy()
        current_sources = {roi1.source}
        changed = True

        while changed:
            changed = False
            for j, roi2 in enumerate(polygons):
                if j in used or j == i:
                    continue

                iou = compute_polygon_iou(current_poly, roi2.polygon, img_shape)
                containment = compute_polygon_containment(current_poly, roi2.polygon, img_shape)

                if iou >= iou_threshold or containment >= containment_threshold:
                    current_poly = merge_polygon_pair(current_poly, roi2.polygon)
                    current_sources.add(roi2.source)
                    used.add(j)
                    changed = True

        # Create merged ROI
        bbox = cv2.boundingRect(current_poly)
        centroid = compute_centroid(current_poly)
        area = cv2.contourArea(current_poly)

        source_label = "merged" if len(current_sources) > 1 else list(current_sources)[0]

        merged_roi = PolygonROI(
            polygon=current_poly,
            bounding_box=bbox,
            area=area,
            centroid=centroid,
            source=source_label,
        )
        merged.append(merged_roi)
        used.add(i)

    return merged


def create_masked_crop(
    image: np.ndarray,
    roi: PolygonROI,
    background_color: tuple[int, int, int] = (255, 255, 255),
    padding: int = 10,
) -> tuple[np.ndarray, PolygonROI]:
    """
    Create a cropped image with areas outside the polygon masked.

    Args:
        image: Source image
        roi: PolygonROI to extract
        background_color: Color for masked areas (default white)
        padding: Padding around bounding box

    Returns:
        Tuple of (masked crop image, adjusted ROI with local polygon coordinates)
    """
    h, w = image.shape[:2]

    # Create full-size mask
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(mask, [roi.polygon], 255)

    # Create masked image
    result = np.full_like(image, background_color)
    result[mask == 255] = image[mask == 255]

    # Compute crop bounds with padding
    x = max(0, roi.x - padding)
    y = max(0, roi.y - padding)
    x2 = min(w, roi.x2 + padding)
    y2 = min(h, roi.y2 + padding)

    # Crop
    cropped = result[y:y2, x:x2]

    # Adjust polygon to local coordinates
    local_polygon = roi.polygon.copy()
    local_polygon[:, 0, 0] -= x
    local_polygon[:, 0, 1] -= y

    local_roi = PolygonROI(
        polygon=local_polygon,
        bounding_box=(0, 0, x2 - x, y2 - y),
        area=roi.area,
        centroid=(roi.centroid[0] - x, roi.centroid[1] - y),
        source=roi.source,
    )

    return cropped, local_roi


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_roi_gemini_multi(
    aligned_old_crop: np.ndarray,
    new_crop: np.ndarray,
    overlay_crop: np.ndarray,
    roi_index: int,
    temp_dir: str,
) -> ChangeList | None:
    """
    Analyze a single ROI with Gemini using 3 images: aligned_old, new, and overlay.
    Images are downsampled from 300 DPI to 100 DPI before sending.
    """
    print(f"  Analyzing ROI {roi_index} with Gemini (3 images)...")

    # Downsample aligned_old and new from 300 DPI to 100 DPI (1/3 scale)
    # Overlay is already at 100 DPI - no downsampling needed
    scale = 1 / 3
    aligned_old_small = downsample_image(aligned_old_crop, scale)
    new_small = downsample_image(new_crop, scale)
    overlay_small = overlay_crop  # Already at 100 DPI

    print(
        f"    Source crops downsampled: {aligned_old_crop.shape[:2]} -> {aligned_old_small.shape[:2]}"
    )
    print(f"    Overlay crop (no downsample): {overlay_crop.shape[:2]}")

    # Save downsampled crops for inspection
    cv2.imwrite(
        os.path.join(temp_dir, f"roi_{roi_index}_aligned_old_100dpi.png"), aligned_old_small
    )
    cv2.imwrite(os.path.join(temp_dir, f"roi_{roi_index}_new_100dpi.png"), new_small)
    cv2.imwrite(os.path.join(temp_dir, f"roi_{roi_index}_overlay_100dpi.png"), overlay_small)

    # Convert to PNG bytes
    aligned_old_bytes = image_array_to_base64_png(aligned_old_small)
    new_bytes = image_array_to_base64_png(new_small)
    overlay_bytes = image_array_to_base64_png(overlay_small)

    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=SYSTEM_PROMPT_OVERLAY),
                        # types.Part.from_text(text=f"Analyze this region (ROI {roi_index}). The three images below are:"),
                        # types.Part.from_text(text="**Image 1: ALIGNED OLD (previous version)**"),
                        # types.Part.from_bytes(
                        #     mime_type="image/png",
                        #     data=aligned_old_bytes
                        # ),
                        # types.Part.from_text(text="**Image 2: NEW (current version)**"),
                        # types.Part.from_bytes(
                        #     mime_type="image/png",
                        #     data=new_bytes
                        # ),
                        types.Part.from_text(
                            text="**Image: OVERLAY (diff visualization - green=added, red=removed)**"
                        ),
                        types.Part.from_bytes(mime_type="image/png", data=overlay_bytes),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ChangeList,
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
                thinking_config=types.ThinkingConfig(
                    thinking_level="low",
                ),
            ),
        )

        try:
            change_list_dict = json.loads(response.text)
            return ChangeList(**change_list_dict)
        except json.JSONDecodeError:
            print(f"    Error decoding JSON: {response.text[:200]}")
            return None

    except Exception as e:
        print(f"    Error calling Gemini API: {e}")
        return None


def has_diff_pixels(
    overlay: np.ndarray,
    location: Location,
    red_threshold: int = 50,
    green_threshold: int = 50,
    min_pixels: int = 5,
) -> bool:
    """
    Check if a bounding box region contains red or green diff pixels.

    Args:
        overlay: BGR overlay image
        location: Normalized bounding box (0-1000 coordinates)
        red_threshold: Minimum difference for red detection (R - max(G,B))
        green_threshold: Minimum difference for green detection (G - max(R,B))
        min_pixels: Minimum number of diff pixels required

    Returns:
        True if the region contains sufficient red or green pixels
    """
    h, w = overlay.shape[:2]

    # Convert normalized coords to pixels
    x1 = int(location.xmin * w / 1000)
    y1 = int(location.ymin * h / 1000)
    x2 = int(location.xmax * w / 1000)
    y2 = int(location.ymax * h / 1000)

    # Clamp to image bounds
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w, x2), min(h, y2)

    if x2 <= x1 or y2 <= y1:
        return False

    # Extract region
    region = overlay[y1:y2, x1:x2]

    # BGR format: B=0, G=1, R=2
    b = region[:, :, 0].astype(np.int16)
    g = region[:, :, 1].astype(np.int16)
    r = region[:, :, 2].astype(np.int16)

    # Detect red pixels: R significantly higher than G and B
    red_mask = (r - np.maximum(g, b)) > red_threshold

    # Detect green pixels: G significantly higher than R and B
    green_mask = (g - np.maximum(r, b)) > green_threshold

    # Count diff pixels
    diff_pixel_count = np.sum(red_mask) + np.sum(green_mask)

    return diff_pixel_count >= min_pixels


def filter_changes_by_diff_content(
    changes: ChangeList, overlay: np.ndarray, min_pixels: int = 10
) -> ChangeList:
    """
    Filter out changes whose bounding boxes don't contain red/green diff pixels.

    Args:
        changes: List of detected changes
        overlay: BGR overlay image
        min_pixels: Minimum diff pixels required to keep a change

    Returns:
        Filtered ChangeList with only valid changes
    """
    if not changes or not changes.changes:
        return changes

    valid_changes = []
    removed_count = 0

    for change in changes.changes:
        if has_diff_pixels(overlay, change.location, min_pixels=min_pixels):
            valid_changes.append(change)
        else:
            removed_count += 1

    if removed_count > 0:
        print(f"    Filtered out {removed_count} changes with no diff pixels")

    return ChangeList(changes=valid_changes)


def draw_changes_on_image(
    image: np.ndarray,
    changes: ChangeList,
    color: tuple[int, int, int] = (255, 0, 0),
    thickness: int = 2,
) -> np.ndarray:
    """Draw bounding boxes for changes on an image."""
    result = image.copy()
    h, w = result.shape[:2]

    for i, change in enumerate(changes.changes):
        loc = change.location
        x1 = int(loc.xmin * w / 1000)
        y1 = int(loc.ymin * h / 1000)
        x2 = int(loc.xmax * w / 1000)
        y2 = int(loc.ymax * h / 1000)

        cv2.rectangle(result, (x1, y1), (x2, y2), color, thickness)
        # Add index label
        cv2.putText(result, str(i), (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    return result


def review_and_refine_changes(
    overlay_crop: np.ndarray, initial_changes: ChangeList, roi_index: int, temp_dir: str
) -> ChangeList | None:
    """
    Review and refine the initial change detection results.
    Sends the overlay with bounding boxes drawn to a reviewer model.
    """
    print(f"  Reviewing ROI {roi_index} changes...")

    if not initial_changes or len(initial_changes.changes) == 0:
        print("    No initial changes to review")
        return initial_changes

    # Draw initial bounding boxes on overlay
    overlay_with_boxes = draw_changes_on_image(overlay_crop, initial_changes)

    # Save for inspection
    cv2.imwrite(os.path.join(temp_dir, f"roi_{roi_index}_review_input.png"), overlay_with_boxes)

    # Convert to PNG bytes
    overlay_with_boxes_bytes = image_array_to_base64_png(overlay_with_boxes)

    # Format initial changes as JSON for the prompt
    initial_changes_json = json.dumps(initial_changes.model_dump(), indent=2)

    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=SYSTEM_PROMPT_REVIEWER),
                        types.Part.from_text(
                            text="**OVERLAY IMAGE with BOUNDING BOXES (blue boxes = detected changes):**"
                        ),
                        types.Part.from_bytes(mime_type="image/png", data=overlay_with_boxes_bytes),
                        types.Part.from_text(
                            text=f"**INITIAL CHANGE LIST ({len(initial_changes.changes)} changes):**\n```json\n{initial_changes_json}\n```"
                        ),
                        types.Part.from_text(
                            text="Please review and produce a REFINED change list."
                        ),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ChangeList,
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
                thinking_config=types.ThinkingConfig(
                    thinking_level="high",
                ),
            ),
        )

        try:
            refined_dict = json.loads(response.text)
            refined = ChangeList(**refined_dict)
            print(f"    Refined: {len(initial_changes.changes)} -> {len(refined.changes)} changes")
            return refined
        except json.JSONDecodeError:
            print(f"    Error decoding JSON: {response.text[:200]}")
            return initial_changes

    except Exception as e:
        print(f"    Error calling Gemini API: {e}")
        return initial_changes


def transform_to_global(
    local_change: Change,
    roi: PolygonROI,
    crop_offset: tuple[int, int],
    img_width: int,
    img_height: int,
) -> Change:
    """
    Transform a change from local ROI coordinates to global image coordinates.
    """
    loc = local_change.location
    crop_x, crop_y = crop_offset

    # Local normalized (0-1000) -> Local pixels
    local_x1 = loc.xmin * roi.w / 1000
    local_y1 = loc.ymin * roi.h / 1000
    local_x2 = loc.xmax * roi.w / 1000
    local_y2 = loc.ymax * roi.h / 1000

    # Local pixels -> Global pixels (add crop offset)
    global_x1 = local_x1 + crop_x
    global_y1 = local_y1 + crop_y
    global_x2 = local_x2 + crop_x
    global_y2 = local_y2 + crop_y

    # Global pixels -> Global normalized (0-1000)
    norm_x1 = int(global_x1 * 1000 / img_width)
    norm_y1 = int(global_y1 * 1000 / img_height)
    norm_x2 = int(global_x2 * 1000 / img_width)
    norm_y2 = int(global_y2 * 1000 / img_height)

    return Change(
        action=local_change.action,
        elements=local_change.elements,
        direction=local_change.direction,
        value=local_change.value,
        location=Location(xmin=norm_x1, ymin=norm_y1, xmax=norm_x2, ymax=norm_y2),
    )


def draw_results(
    overlay_path: str, change_list: ChangeList, merged_rois: list[PolygonROI], output_path: str
):
    """Draw polygon ROIs and change bounding boxes on the overlay image."""
    img = cv2.imread(overlay_path)
    if img is None:
        print(f"Error: Could not read image {overlay_path}")
        return

    h, w = img.shape[:2]

    # Draw ROI polygons in cyan with semi-transparent fill
    for i, roi in enumerate(merged_rois):
        overlay = img.copy()
        cv2.fillPoly(overlay, [roi.polygon], (255, 255, 0))
        cv2.addWeighted(overlay, 0.1, img, 0.9, 0, img)
        cv2.polylines(img, [roi.polygon], True, (255, 255, 0), 2)
        cv2.putText(
            img, f"ROI {i}", (roi.x, roi.y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2
        )

    # Draw change boxes in blue
    color = (255, 0, 0)

    for change in change_list.changes:
        loc = change.location
        x1 = int(loc.xmin * w / 1000)
        y1 = int(loc.ymin * h / 1000)
        x2 = int(loc.xmax * w / 1000)
        y2 = int(loc.ymax * h / 1000)

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

        label = f"{change.action}: {', '.join(change.elements)}"
        if len(label) > 40:
            label = label[:37] + "..."
        cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imwrite(output_path, img)
    print(f"Saved result to {output_path}")


@dataclass
class Tile:
    """Represents a tile of a larger image."""

    image: np.ndarray
    x_offset: int
    y_offset: int
    width: int
    height: int


def create_tiles_with_overlap(
    image: np.ndarray, tile_size: int = 1000, overlap: int = 100
) -> list[Tile]:
    """
    Break an image into overlapping tiles of specified size.

    Args:
        image: Source image to tile
        tile_size: Target tile size in pixels
        overlap: Overlap between adjacent tiles in pixels

    Returns:
        List of Tile objects with image data and offsets
    """
    h, w = image.shape[:2]
    tiles = []

    # If image fits in a single tile, return as-is
    if h <= tile_size and w <= tile_size:
        return [Tile(image=image, x_offset=0, y_offset=0, width=w, height=h)]

    # Calculate step size (tile_size - overlap)
    step = tile_size - overlap

    y = 0
    while y < h:
        x = 0
        while x < w:
            # Calculate tile bounds
            x2 = min(x + tile_size, w)
            y2 = min(y + tile_size, h)

            # Adjust start to ensure minimum tile size if at edge
            x1 = max(0, x2 - tile_size) if x2 == w else x
            y1 = max(0, y2 - tile_size) if y2 == h else y

            tile_img = image[y1:y2, x1:x2].copy()

            tiles.append(
                Tile(image=tile_img, x_offset=x1, y_offset=y1, width=x2 - x1, height=y2 - y1)
            )

            if x2 >= w:
                break
            x += step

        if y2 >= h:
            break
        y += step

    return tiles


def transform_tile_changes_to_crop(
    changes: ChangeList, tile: Tile, crop_width: int, crop_height: int
) -> list[Change]:
    """
    Transform changes from tile coordinates back to crop coordinates.

    Args:
        changes: ChangeList from tile analysis
        tile: Tile object with offset information
        crop_width: Full crop width
        crop_height: Full crop height

    Returns:
        List of Change objects with coordinates in crop space
    """
    transformed = []

    for change in changes.changes:
        loc = change.location

        # Tile normalized (0-1000) -> Tile pixels
        tile_x1 = loc.xmin * tile.width / 1000
        tile_y1 = loc.ymin * tile.height / 1000
        tile_x2 = loc.xmax * tile.width / 1000
        tile_y2 = loc.ymax * tile.height / 1000

        # Tile pixels -> Crop pixels (add tile offset)
        crop_x1 = tile_x1 + tile.x_offset
        crop_y1 = tile_y1 + tile.y_offset
        crop_x2 = tile_x2 + tile.x_offset
        crop_y2 = tile_y2 + tile.y_offset

        # Crop pixels -> Crop normalized (0-1000)
        norm_x1 = int(crop_x1 * 1000 / crop_width)
        norm_y1 = int(crop_y1 * 1000 / crop_height)
        norm_x2 = int(crop_x2 * 1000 / crop_width)
        norm_y2 = int(crop_y2 * 1000 / crop_height)

        transformed.append(
            Change(
                action=change.action,
                elements=change.elements,
                direction=change.direction,
                value=change.value,
                location=Location(xmin=norm_x1, ymin=norm_y1, xmax=norm_x2, ymax=norm_y2),
            )
        )

    return transformed


def deduplicate_changes(
    changes: list[Change],
    iou_threshold: float = 0.3,
    containment_threshold: float = 0.6,
    centroid_distance_threshold: float = 50,
) -> list[Change]:
    """
    Deduplicate and merge overlapping changes using Union-Find clustering.

    Changes are merged if they have the same action/direction/value AND
    meet any of the spatial criteria (IoU, containment, or centroid distance).

    Args:
        changes: List of changes (may have duplicates from overlapping tiles)
        iou_threshold: IoU threshold for merging (default 0.3)
        containment_threshold: Containment ratio threshold (default 0.6)
        centroid_distance_threshold: Max centroid distance in 1000x1000 space (default 50)

    Returns:
        Deduplicated and merged list of changes
    """
    if not changes:
        return []

    def box_area(c: Change) -> float:
        """Compute area of a change's bounding box."""
        l = c.location
        return (l.xmax - l.xmin) * (l.ymax - l.ymin)

    def box_intersection(c1: Change, c2: Change) -> float:
        """Compute intersection area between two bounding boxes."""
        l1, l2 = c1.location, c2.location
        x1 = max(l1.xmin, l2.xmin)
        y1 = max(l1.ymin, l2.ymin)
        x2 = min(l1.xmax, l2.xmax)
        y2 = min(l1.ymax, l2.ymax)
        if x2 <= x1 or y2 <= y1:
            return 0.0
        return (x2 - x1) * (y2 - y1)

    def box_iou(c1: Change, c2: Change) -> float:
        """Compute IoU between two change bounding boxes."""
        intersection = box_intersection(c1, c2)
        if intersection == 0:
            return 0.0
        area1 = box_area(c1)
        area2 = box_area(c2)
        union = area1 + area2 - intersection
        return intersection / union if union > 0 else 0.0

    def box_containment(c1: Change, c2: Change) -> float:
        """Compute containment ratio (intersection / smaller box area)."""
        intersection = box_intersection(c1, c2)
        if intersection == 0:
            return 0.0
        smaller_area = min(box_area(c1), box_area(c2))
        return intersection / smaller_area if smaller_area > 0 else 0.0

    def centroid_distance(c1: Change, c2: Change) -> float:
        """Compute Euclidean distance between centroids in 1000x1000 space."""
        l1, l2 = c1.location, c2.location
        cx1 = (l1.xmin + l1.xmax) / 2
        cy1 = (l1.ymin + l1.ymax) / 2
        cx2 = (l2.xmin + l2.xmax) / 2
        cy2 = (l2.ymin + l2.ymax) / 2
        return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5

    def should_merge(c1: Change, c2: Change) -> bool:
        """Check if two changes should be merged."""
        # Must have same action
        if c1.action != c2.action:
            return False
        # Must have same direction
        if c1.direction != c2.direction:
            return False
        # Must have same value
        if c1.value != c2.value:
            return False
        # Check spatial overlap using multiple criteria
        if box_iou(c1, c2) >= iou_threshold:
            return True
        if box_containment(c1, c2) >= containment_threshold:
            return True
        if centroid_distance(c1, c2) < centroid_distance_threshold:
            return True
        return False

    def merge_change_group(group: list[Change]) -> Change:
        """Merge a group of overlapping changes into one."""
        # Union of bounding boxes
        xmin = min(c.location.xmin for c in group)
        ymin = min(c.location.ymin for c in group)
        xmax = max(c.location.xmax for c in group)
        ymax = max(c.location.ymax for c in group)
        # Union of elements (deduplicated)
        all_elements = set()
        for c in group:
            all_elements.update(c.elements)
        # Action, direction, value are same within group
        return Change(
            action=group[0].action,
            elements=list(all_elements),
            direction=group[0].direction,
            value=group[0].value,
            location=Location(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax),
        )

    # Union-Find data structure
    n = len(changes)
    parent = list(range(n))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Group overlapping boxes
    for i in range(n):
        for j in range(i + 1, n):
            if should_merge(changes[i], changes[j]):
                union(i, j)

    # Collect groups
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(changes[i])

    # Merge each group
    merged = [merge_change_group(group) for group in groups.values()]
    print(f"    Deduplication: {n} changes -> {len(merged)} merged")

    return merged


def run_polygon_analysis(
    addition_path: str,
    deletion_path: str,
    overlay_path: str,
    aligned_old_path: str,
    new_path: str,
    output_dir: str,
    output_name: str = "polygon_analysis_result.png",
    max_rois: int | None = None,
    enable_review: bool = False,
    tile_size: int = 1000,
    tile_overlap: int = 100,
) -> ChangeList:
    """
    Run the full polygon ROI-based analysis pipeline with multi-image analysis.

    Args:
        addition_path: Path to addition diff image
        deletion_path: Path to deletion diff image
        overlay_path: Path to overlay image
        aligned_old_path: Path to aligned old image (300 DPI)
        new_path: Path to new image (300 DPI)
        output_dir: Output directory
        output_name: Output filename
        max_rois: Maximum number of ROIs to process (None = all)
        enable_review: Enable reviewer model to validate/refine results (default: False)
        tile_size: Max tile size for large crops (default: 1000px)
        tile_overlap: Overlap between adjacent tiles (default: 100px)
    """
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp_rois")

    # Clear and recreate temp dir
    if os.path.exists(temp_dir):
        import shutil

        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)

    # Read all images
    overlay_img = cv2.imread(overlay_path)
    aligned_old_img = cv2.imread(aligned_old_path)
    new_img = cv2.imread(new_path)

    if overlay_img is None:
        print(f"Error: Could not read overlay image {overlay_path}")
        return ChangeList(changes=[])
    if aligned_old_img is None:
        print(f"Error: Could not read aligned_old image {aligned_old_path}")
        return ChangeList(changes=[])
    if new_img is None:
        print(f"Error: Could not read new image {new_path}")
        return ChangeList(changes=[])

    img_h, img_w = overlay_img.shape[:2]
    print(f"Image dimensions: {img_w}x{img_h}")

    # Step 1: Extract polygon ROIs from addition and deletion images
    print("\n=== Step 1: Extracting Polygon ROIs ===")
    print(f"Processing addition image: {addition_path}")
    addition_rois = extract_polygon_rois(addition_path, source_label="addition")
    print(f"  Found {len(addition_rois)} polygon ROIs in addition image")

    print(f"Processing deletion image: {deletion_path}")
    deletion_rois = extract_polygon_rois(deletion_path, source_label="deletion")
    print(f"  Found {len(deletion_rois)} polygon ROIs in deletion image")

    # Combine all ROIs
    all_rois = addition_rois + deletion_rois
    print(f"Total polygon ROIs before merge: {len(all_rois)}")

    # Step 2: Merge overlapping polygons
    print("\n=== Step 2: Merging Overlapping Polygons ===")
    merged_rois = merge_overlapping_polygons(
        all_rois, img_shape=(img_h, img_w), iou_threshold=0.2, containment_threshold=0.6
    )
    print(f"Polygon ROIs after merge: {len(merged_rois)}")

    for i, roi in enumerate(merged_rois):
        fill_ratio = roi.area / roi.bbox_area if roi.bbox_area > 0 else 0
        print(
            f"  ROI {i}: bbox=({roi.x}, {roi.y}) {roi.w}x{roi.h}, "
            f"poly_area={roi.area:.0f}, fill={fill_ratio:.1%}, source={roi.source}"
        )

    # Step 3: Create masked crops and analyze each ROI
    print("\n=== Step 3: Creating Masked Crops & Analyzing with Gemini ===")
    all_changes = []
    padding = 10

    # Limit ROIs if max_rois is set
    rois_to_process = merged_rois[:max_rois] if max_rois else merged_rois
    print(f"Processing {len(rois_to_process)} of {len(merged_rois)} ROIs")

    # Compute scale factor between overlay and source images
    src_h, src_w = aligned_old_img.shape[:2]
    scale_x = src_w / img_w
    scale_y = src_h / img_h
    print(
        f"Source image scale factor: {scale_x:.1f}x (overlay: {img_w}x{img_h}, source: {src_w}x{src_h})"
    )

    for i, roi in enumerate(rois_to_process):
        # Compute crop offset for overlay (for coordinate transformation)
        crop_x = max(0, roi.x - padding)
        crop_y = max(0, roi.y - padding)
        crop_x2 = min(img_w, roi.x2 + padding)
        crop_y2 = min(img_h, roi.y2 + padding)

        # Scale coordinates for source images (may be higher DPI)
        src_crop_x = int(crop_x * scale_x)
        src_crop_y = int(crop_y * scale_y)
        src_crop_x2 = int(crop_x2 * scale_x)
        src_crop_y2 = int(crop_y2 * scale_y)

        # Create masked crop for overlay only (to focus on change regions)
        overlay_crop, local_roi = create_masked_crop(overlay_img, roi, padding=padding)

        # Simple bounding box crop for aligned_old and new (no masking - show full context)
        # Use scaled coordinates for source images
        aligned_old_crop = aligned_old_img[src_crop_y:src_crop_y2, src_crop_x:src_crop_x2].copy()
        new_crop = new_img[src_crop_y:src_crop_y2, src_crop_x:src_crop_x2].copy()

        # Save crops for inspection (full resolution)
        cv2.imwrite(os.path.join(temp_dir, f"roi_{i}_aligned_old.png"), aligned_old_crop)
        cv2.imwrite(os.path.join(temp_dir, f"roi_{i}_new.png"), new_crop)
        print(f"  Saved ROI {i} crops to temp_rois/")

        # Get crop dimensions for tiling check
        crop_h, crop_w = overlay_crop.shape[:2]
        needs_tiling = crop_h > tile_size or crop_w > tile_size

        # Step 3a: Initial analysis with Gemini (with tiling if needed)
        print(f"\n  --- ROI {i}: Initial Analysis ---")

        if needs_tiling:
            # Create tiles for large crops
            overlay_tiles = create_tiles_with_overlap(overlay_crop, tile_size, tile_overlap)
            print(
                f"    Crop {crop_w}x{crop_h} exceeds {tile_size}px, tiling into {len(overlay_tiles)} tiles"
            )

            # Analyze each tile
            tile_changes: list[Change] = []
            for t_idx, tile in enumerate(overlay_tiles):
                print(
                    f"    Analyzing tile {t_idx + 1}/{len(overlay_tiles)} at offset ({tile.x_offset}, {tile.y_offset})"
                )

                # Save tile for inspection
                cv2.imwrite(os.path.join(temp_dir, f"roi_{i}_tile_{t_idx}.png"), tile.image)

                # For tiles, we only send the overlay (already at 100 DPI)
                tile_result = analyze_roi_gemini_multi(
                    aligned_old_crop, new_crop, tile.image, f"{i}_tile_{t_idx}", temp_dir
                )

                if tile_result and len(tile_result.changes) > 0:
                    # Transform tile coordinates back to crop coordinates
                    transformed = transform_tile_changes_to_crop(tile_result, tile, crop_w, crop_h)
                    tile_changes.extend(transformed)
                    print(f"      Found {len(tile_result.changes)} changes in tile")

            # Deduplicate changes from overlapping tiles
            if tile_changes:
                deduped_changes = deduplicate_changes(tile_changes, iou_threshold=0.5)
                print(
                    f"    Merged {len(tile_changes)} tile changes -> {len(deduped_changes)} unique changes"
                )
                initial_result = ChangeList(changes=deduped_changes)
            else:
                initial_result = None
        else:
            # No tiling needed - analyze full crop
            initial_result = analyze_roi_gemini_multi(
                aligned_old_crop, new_crop, overlay_crop, i, temp_dir
            )

        # Filter out changes with no diff pixels (false positives)
        if initial_result and len(initial_result.changes) > 0:
            initial_result = filter_changes_by_diff_content(initial_result, overlay_crop)

        if initial_result and len(initial_result.changes) > 0:
            print(f"  ROI {i}: Initial detection found {len(initial_result.changes)} changes")

            # Step 3b: Review and refine the results (optional)
            if enable_review:
                print(f"\n  --- ROI {i}: Review & Refinement ---")
                refined_result = review_and_refine_changes(
                    overlay_crop, initial_result, i, temp_dir
                )
                # Use refined result if available, otherwise fall back to initial
                result = refined_result if refined_result else initial_result
            else:
                result = initial_result

            # Save result overlay for inspection
            if result:
                result_overlay = draw_changes_on_image(
                    overlay_crop, result, color=(0, 255, 0), thickness=2
                )
                cv2.imwrite(os.path.join(temp_dir, f"roi_{i}_result.png"), result_overlay)

            # Transform coordinates to global
            for change in result.changes:
                global_change = transform_to_global(
                    change, local_roi, (crop_x, crop_y), img_w, img_h
                )
                all_changes.append(global_change)
                print(f"    - {change.action}: {', '.join(change.elements)}")
        else:
            print(f"  ROI {i}: No changes detected or error")

    combined_changes = ChangeList(changes=all_changes)
    print(f"\nTotal changes detected: {len(combined_changes.changes)}")

    # Step 4: Draw results
    print("\n=== Step 4: Drawing Results ===")
    output_path = os.path.join(output_dir, output_name)
    draw_results(overlay_path, combined_changes, merged_rois, output_path)

    # Save JSON results
    json_path = os.path.join(output_dir, output_name.replace(".png", ".json"))
    with open(json_path, "w") as f:
        json.dump(combined_changes.model_dump(), f, indent=2)
    print(f"Saved JSON to {json_path}")

    return combined_changes


if __name__ == "__main__":
    # Default paths
    dataset_dir = os.path.join(os.path.dirname(__file__), "dataset")
    output_dir = os.path.join(os.path.dirname(__file__), "predicted")

    # Input files
    addition_path = os.path.join(dataset_dir, "page_1_addition.png")
    deletion_path = os.path.join(dataset_dir, "page_1_deletion.png")
    overlay_path = os.path.join(dataset_dir, "page_1_overlay.png")
    aligned_old_path = os.path.join(dataset_dir, "page_1_aligned_old.png")
    new_path = os.path.join(dataset_dir, "page_1_new.png")

    # Verify files exist
    required_files = [addition_path, deletion_path, overlay_path, aligned_old_path, new_path]
    for path in required_files:
        if not os.path.exists(path):
            print(f"Error: File not found: {path}")
            sys.exit(1)

    # Run analysis
    # - max_rois=1 for testing, set to None for all ROIs
    # - enable_review=False (default) - set to True to enable reviewer validation
    # - tile_size=1000, tile_overlap=100 - for automatic tiling of large crops
    result = run_polygon_analysis(
        addition_path=addition_path,
        deletion_path=deletion_path,
        overlay_path=overlay_path,
        aligned_old_path=aligned_old_path,
        new_path=new_path,
        output_dir=output_dir,
        output_name="polygon_analysis_result_1.png",
        max_rois=1,  # Only process first ROI for testing
        enable_review=False,  # Disabled - set to True to enable reviewer stage
    )
