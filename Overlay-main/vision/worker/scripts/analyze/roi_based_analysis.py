"""
ROI-based Change Analysis Pipeline

This script:
1. Extracts ROI bounding boxes from addition and deletion diff images using tight segmentation
2. Merges overlapping boxes from both images using IoU (Intersection over Union)
3. Crops the overlay image using merged ROIs
4. Feeds each cropped ROI to Gemini for change analysis
5. Combines all change lists and maps local coordinates to global coordinates
6. Draws final bounding boxes on the full overlay image
"""

import base64
import json
import os
import sys
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
class BoundingBox:
    """Bounding box in pixel coordinates"""

    x: int
    y: int
    w: int
    h: int

    @property
    def x2(self) -> int:
        return self.x + self.w

    @property
    def y2(self) -> int:
        return self.y + self.h

    @property
    def area(self) -> int:
        return self.w * self.h


class Location(BaseModel):
    xmin: int = Field(description="Left X coordinate (0-1000)")
    ymin: int = Field(description="Top Y coordinate (0-1000)")
    xmax: int = Field(description="Right X coordinate (0-1000)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000)")


class Change(BaseModel):
    action: str = Field(description="Type of change: 'Add', 'Remove', 'Dimension Change', 'Move'")
    element: str = Field(description="The item or object that is changing or modified")
    direction: str | None = Field(None, description="Direction of change")
    value: list[str] | None = Field(
        None, description="List of [start_value, final_value] if applicable"
    )
    location: Location = Field(description="Bounding box of the change")


class ChangeList(BaseModel):
    changes: list[Change] = Field(description="List of detected changes")


SYSTEM_PROMPT_OVERLAY = """You are an expert architectural document analyzer.
Your task is to identify and locate all changes visible in this construction drawing overlay.

The overlay shows:
- GREEN areas: NEW/ADDED features from the previous version
- RED areas: REMOVED/DELETED features from the previous version
- Areas with both colors may indicate MOVED or MODIFIED elements

CRITICAL INSTRUCTION: You must identify EVERY SINGLE distinct change in this image crop. Focusing only on the green and red areas.
Be exhaustive. Group related elements (e.g. a door and its tag) if they are close, otherwise bound them separately.

For each distinct change:
1. Identify the element type (wall, door, window, text, symbol, equipment, etc.)
2. Determine the action: 'Add' (green only), 'Remove' (red only), 'Move' (both colors offset), 'Dimension Change' (both colors, same element resized)
3. Applicable direction of change: 'up', 'down', 'left', 'right' (only if the change is a move)
4. Value of the change: 'start_value', 'final_value' (only if the change is a dimension change)
5. Provide a tight bounding box around the change

The bounding box coordinates should be normalized to 1000x1000 grid (0-1000).
"""


def extract_rois_tight(image_path: str) -> list[BoundingBox]:
    """
    Extract ROI bounding boxes using tight segmentation algorithm.
    Returns list of BoundingBox objects in pixel coordinates.
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

    # Aggressive Dilation for Detection
    k_w = max(3, int(w * 0.015))
    k_h = max(3, int(h * 0.015))

    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (k_w, 1))
    dilated_h = cv2.dilate(content, kernel_h, iterations=1)

    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, k_h))
    dilated = cv2.dilate(dilated_h, kernel_v, iterations=3)

    # Find Contours
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Filter and Refine
    min_area = (w * h) * 0.001
    boxes = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch

        if area > min_area:
            # Refine bounding box using original content
            roi = content[y : y + ch, x : x + cw]
            roi_contours, _ = cv2.findContours(roi, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if roi_contours:
                all_points = np.vstack(roi_contours)
                rx, ry, rw, rh = cv2.boundingRect(all_points)

                # Convert to image coordinates with padding
                pad_x = max(3, int(rw * 0.02))
                pad_y = max(3, int(rh * 0.02))

                tight_x = max(0, x + rx - pad_x)
                tight_y = max(0, y + ry - pad_y)
                tight_w = min(w - tight_x, rw + 2 * pad_x)
                tight_h = min(h - tight_y, rh + 2 * pad_y)

                boxes.append(BoundingBox(tight_x, tight_y, tight_w, tight_h))

    return boxes


def compute_iou(box1: BoundingBox, box2: BoundingBox) -> float:
    """Compute Intersection over Union between two boxes."""
    # Intersection coordinates
    ix1 = max(box1.x, box2.x)
    iy1 = max(box1.y, box2.y)
    ix2 = min(box1.x2, box2.x2)
    iy2 = min(box1.y2, box2.y2)

    # No intersection
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    intersection = (ix2 - ix1) * (iy2 - iy1)
    union = box1.area + box2.area - intersection

    return intersection / union if union > 0 else 0.0


def compute_intersection_over_smaller(box1: BoundingBox, box2: BoundingBox) -> float:
    """
    Compute intersection over the smaller box's area.
    This catches cases where a small box is mostly inside a larger one.
    """
    ix1 = max(box1.x, box2.x)
    iy1 = max(box1.y, box2.y)
    ix2 = min(box1.x2, box2.x2)
    iy2 = min(box1.y2, box2.y2)

    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0

    intersection = (ix2 - ix1) * (iy2 - iy1)
    smaller_area = min(box1.area, box2.area)

    return intersection / smaller_area if smaller_area > 0 else 0.0


def merge_box_pair(box1: BoundingBox, box2: BoundingBox) -> BoundingBox:
    """Merge two boxes into their bounding union."""
    x = min(box1.x, box2.x)
    y = min(box1.y, box2.y)
    x2 = max(box1.x2, box2.x2)
    y2 = max(box1.y2, box2.y2)
    return BoundingBox(x, y, x2 - x, y2 - y)


def merge_overlapping_boxes(
    boxes: list[BoundingBox], iou_threshold: float = 0.3, containment_threshold: float = 0.7
) -> list[BoundingBox]:
    """
    Merge boxes that overlap significantly.

    Uses two criteria:
    1. IoU >= iou_threshold: Standard overlap measure
    2. Intersection/SmallerArea >= containment_threshold: Catches contained boxes

    Args:
        boxes: List of bounding boxes
        iou_threshold: Minimum IoU for merging (default 0.3)
        containment_threshold: Minimum containment ratio (default 0.7)

    Returns:
        List of merged bounding boxes
    """
    if not boxes:
        return []

    # Sort by area (largest first) for stability
    boxes = sorted(boxes, key=lambda b: b.area, reverse=True)
    merged = []
    used = set()

    for i, box1 in enumerate(boxes):
        if i in used:
            continue

        current = box1
        changed = True

        while changed:
            changed = False
            for j, box2 in enumerate(boxes):
                if j in used or j == i:
                    continue

                iou = compute_iou(current, box2)
                containment = compute_intersection_over_smaller(current, box2)

                if iou >= iou_threshold or containment >= containment_threshold:
                    current = merge_box_pair(current, box2)
                    used.add(j)
                    changed = True

        merged.append(current)
        used.add(i)

    return merged


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def analyze_roi_gemini(image_path: str, roi_index: int) -> ChangeList | None:
    """Analyze a single ROI crop with Gemini."""
    print(f"  Analyzing ROI {roi_index} with Gemini...")

    base64_image = image_to_base64(image_path)
    client = genai.Client(api_key=GEMINI_API_KEY)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=SYSTEM_PROMPT_OVERLAY),
                        types.Part.from_bytes(
                            mime_type="image/png", data=base64.b64decode(base64_image)
                        ),
                    ],
                )
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ChangeList,
                media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
                thinking_config=types.ThinkingConfig(
                    thinkingLevel="low",
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


def transform_to_global(
    local_change: Change, roi: BoundingBox, img_width: int, img_height: int
) -> Change:
    """
    Transform a change from local ROI coordinates to global image coordinates.

    Local coordinates are 0-1000 within the ROI.
    Global coordinates are 0-1000 within the full image.
    """
    loc = local_change.location

    # Local normalized (0-1000) -> Local pixels
    local_x1 = loc.xmin * roi.w / 1000
    local_y1 = loc.ymin * roi.h / 1000
    local_x2 = loc.xmax * roi.w / 1000
    local_y2 = loc.ymax * roi.h / 1000

    # Local pixels -> Global pixels
    global_x1 = local_x1 + roi.x
    global_y1 = local_y1 + roi.y
    global_x2 = local_x2 + roi.x
    global_y2 = local_y2 + roi.y

    # Global pixels -> Global normalized (0-1000)
    norm_x1 = int(global_x1 * 1000 / img_width)
    norm_y1 = int(global_y1 * 1000 / img_height)
    norm_x2 = int(global_x2 * 1000 / img_width)
    norm_y2 = int(global_y2 * 1000 / img_height)

    return Change(
        action=local_change.action,
        element=local_change.element,
        direction=local_change.direction,
        value=local_change.value,
        location=Location(xmin=norm_x1, ymin=norm_y1, xmax=norm_x2, ymax=norm_y2),
    )


def draw_results(
    overlay_path: str, change_list: ChangeList, merged_rois: list[BoundingBox], output_path: str
):
    """Draw bounding boxes on the overlay image."""
    img = cv2.imread(overlay_path)
    if img is None:
        print(f"Error: Could not read image {overlay_path}")
        return

    h, w = img.shape[:2]

    # Draw ROI boxes in cyan (for reference)
    for i, roi in enumerate(merged_rois):
        cv2.rectangle(img, (roi.x, roi.y), (roi.x2, roi.y2), (255, 255, 0), 2)
        cv2.putText(
            img, f"ROI {i}", (roi.x, roi.y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2
        )

    # Draw change boxes in blue
    color = (255, 0, 0)  # Blue in BGR

    for change in change_list.changes:
        loc = change.location
        x1 = int(loc.xmin * w / 1000)
        y1 = int(loc.ymin * h / 1000)
        x2 = int(loc.xmax * w / 1000)
        y2 = int(loc.ymax * h / 1000)

        cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

        label = f"{change.action}: {change.element}"
        # Truncate long labels
        if len(label) > 40:
            label = label[:37] + "..."
        cv2.putText(img, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    cv2.imwrite(output_path, img)
    print(f"Saved result to {output_path}")


def run_roi_analysis(
    addition_path: str,
    deletion_path: str,
    overlay_path: str,
    output_dir: str,
    output_name: str = "roi_analysis_result.png",
) -> ChangeList:
    """
    Run the full ROI-based analysis pipeline.

    Args:
        addition_path: Path to addition diff image
        deletion_path: Path to deletion diff image
        overlay_path: Path to overlay image
        output_dir: Directory for output files
        output_name: Name of output file

    Returns:
        Combined ChangeList with all detected changes
    """
    os.makedirs(output_dir, exist_ok=True)
    temp_dir = os.path.join(output_dir, "temp_rois")
    os.makedirs(temp_dir, exist_ok=True)

    # Read overlay for dimensions
    overlay_img = cv2.imread(overlay_path)
    if overlay_img is None:
        print(f"Error: Could not read overlay image {overlay_path}")
        return ChangeList(changes=[])

    img_h, img_w = overlay_img.shape[:2]
    print(f"Image dimensions: {img_w}x{img_h}")

    # Step 1: Extract ROIs from addition and deletion images
    print("\n=== Step 1: Extracting ROIs ===")
    print(f"Processing addition image: {addition_path}")
    addition_rois = extract_rois_tight(addition_path)
    print(f"  Found {len(addition_rois)} ROIs in addition image")

    print(f"Processing deletion image: {deletion_path}")
    deletion_rois = extract_rois_tight(deletion_path)
    print(f"  Found {len(deletion_rois)} ROIs in deletion image")

    # Combine all ROIs
    all_rois = addition_rois + deletion_rois
    print(f"Total ROIs before merge: {len(all_rois)}")

    # Step 2: Merge overlapping boxes
    print("\n=== Step 2: Merging Overlapping ROIs ===")
    merged_rois = merge_overlapping_boxes(all_rois, iou_threshold=0.3, containment_threshold=0.7)
    print(f"ROIs after merge: {len(merged_rois)}")

    for i, roi in enumerate(merged_rois):
        print(f"  ROI {i}: ({roi.x}, {roi.y}) - {roi.w}x{roi.h} = {roi.area} px")

    # Step 3: Crop overlay and analyze each ROI
    print("\n=== Step 3: Analyzing ROIs with Gemini ===")
    all_changes = []

    for i, roi in enumerate(merged_rois):
        # Crop the overlay image
        crop = overlay_img[roi.y : roi.y2, roi.x : roi.x2]
        crop_path = os.path.join(temp_dir, f"roi_{i}.png")
        cv2.imwrite(crop_path, crop)

        # Analyze with Gemini
        result = analyze_roi_gemini(crop_path, i)

        if result:
            print(f"  ROI {i}: Found {len(result.changes)} changes")

            # Transform coordinates to global
            for change in result.changes:
                global_change = transform_to_global(change, roi, img_w, img_h)
                all_changes.append(global_change)
                print(f"    - {change.action}: {change.element}")
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
    addition_path = os.path.join(dataset_dir, "page_0_addition.png")
    deletion_path = os.path.join(dataset_dir, "page_0_deletion.png")
    overlay_path = os.path.join(dataset_dir, "page_0_overlay.png")

    # Verify files exist
    for path in [addition_path, deletion_path, overlay_path]:
        if not os.path.exists(path):
            print(f"Error: File not found: {path}")
            sys.exit(1)

    # Run analysis
    result = run_roi_analysis(
        addition_path=addition_path,
        deletion_path=deletion_path,
        overlay_path=overlay_path,
        output_dir=output_dir,
        output_name="roi_analysis_result.png",
    )
