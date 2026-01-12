import argparse
import base64
import json
import os
import sys
from enum import Enum

import cv2
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Add worker root to path to allow imports if needed, though we are running as a script
# Assuming script is at odin/apps/vision/worker/scripts/analyze/detect_changes.py
# Worker root is at odin/apps/vision/worker
worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(worker_root)

# Load .env from worker root
load_dotenv(os.path.join(worker_root, ".env"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-3-pro-preview"

if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment.")
    sys.exit(1)


class AnalysisMode(str, Enum):
    CHANGE_DETECTION = "change_detection"
    DISCREPANCY = "discrepancy"


class Location(BaseModel):
    xmin: int = Field(description="Left X coordinate (0-1000)")
    ymin: int = Field(description="Top Y coordinate (0-1000)")
    xmax: int = Field(description="Right X coordinate (0-1000)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000)")


# Change Detection Models
class Change(BaseModel):
    action: str = Field(description="Type of change: 'Add', 'Remove', 'Dimension Change', 'Move'")
    elements: list[str] = Field(description="The items or objects that are changing or modified")
    description: str = Field(
        description="Human-readable description of the change in plain English"
    )
    direction: str | None = Field(None, description="Direction of change")
    value: list[str] | None = Field(
        None, description="List of [start_value, final_value] if applicable"
    )
    location: Location = Field(description="Bounding box of the change")


class ChangeList(BaseModel):
    changes: list[Change] = Field(description="List of detected changes")


# Discrepancy Detection Models
class Discrepancy(BaseModel):
    description: str = Field(
        description="Verbatim description of the discrepancy from the provided list"
    )
    identifier: str = Field(
        description="Reference identifier combining category letter and item number (e.g., 'a.1', 'b.2', 'c.1') matching the discrepancy list in the <discrepancies_and_complications> section"
    )
    severity: str = Field(description="Severity level: 'Critical', 'Major', 'Minor'")
    elements: list[str] = Field(
        description="List of construction elements involved in the discrepancy"
    )
    location: Location = Field(description="Bounding box of the discrepancy")


class DiscrepancyList(BaseModel):
    discrepancies: list[Discrepancy] = Field(description="List of detected discrepancies")


SYSTEM_PROMPT_OVERLAY = """You are an expert architectural document analyzer.
Your task is to identify and locate all REAL architectural changes visible in this construction drawing overlay.

The overlay shows:
- GREEN areas: NEW/ADDED features from the previous version
- RED areas: REMOVED/DELETED features from the previous version
- Areas with both colors may indicate MOVED or MODIFIED elements

## Context Images Provided
You will receive the main OVERLAY IMAGE first, followed by context images from both the OLD and NEW drawings:
- **OLD DRAWING context**: Legend, general notes, key notes, ceiling types, and other reference materials from the previous version
- **NEW DRAWING context**: Legend, general notes, ceiling types, and other reference materials from the updated version

Use these context images to:
- Identify symbols and their meanings from the legends
- Understand material specifications from general notes
- Reference key notes for specific callouts
- Compare ceiling types or other specifications between versions

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

**Custom Elements:**
These are elements that are not in the lists above, but are relevant to the analysis.
- Legend: The legend of the drawing, including the symbols and their meanings. Where possible use the legend to identify the element and refer to them in the description.
- General Notes
- Key Notes

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
3. **description**: A clear, human-readable description of the change in plain English. Be specific about what changed and where. Use information from the legends and notes to provide precise terminology. Examples:
   - "Added a new door on the south wall of the conference room"
   - "Removed toilet fixture from the restroom"
   - "Moved staircase 3 feet to the left"
   - "Wall thickness changed from 6 inches to 8 inches"
   - "Changed ceiling type from ACT-1 (Acoustic Tile) to GYP-1 (Gypsum Board)"
4. **direction**: 'up', 'down', 'left', 'right' (only for Move actions)
5. **value**: ['start_value', 'final_value'] (only for Dimension Change)
6. **location**: Tight bounding box, coordinates should be normalized to 1000x1000 grid (0-1000).
"""

SYSTEM_PROMPT_MECHANICAL_OVERLAY = """You are an expert mechanical drawing and blueprint analyzer.
Your task is to identify and locate all REAL mechanical design changes visible in this construction drawing overlay.

The overlay shows:
- GREEN areas: NEW/ADDED features from the previous version
- RED areas: REMOVED/DELETED features from the previous version
- Areas with both colors may indicate MOVED or MODIFIED elements

Interpret the drawings using standard mechanical drafting conventions:

## Context Images Provided
You will receive the main OVERLAY IMAGE first, followed by context images from both the OLD and NEW drawings:
- **OLD DRAWING context**: Title block, revision block, general notes, legends, GD&T notes, material and finish specifications from the previous version
- **NEW DRAWING context**: Title block, revision block, general notes, legends, GD&T notes, material and finish specifications from the updated version

## Mechanical Element Types to Detect

Focus on PHYSICAL, FUNCTIONAL FEATURES of parts and assemblies, not on pure annotation changes.

**Primary part geometry:**

**Holes and threaded features:**

**Shafts, rotating elements, and power transmission:**

**Fasteners and hardware:**

**Welded and joint features:**

**Fluid, pneumatic, and hydraulic features (if present):**

**Assembly and interface features:**

**Custom or drawing-specific elements:**
- Legends explaining custom symbols
- Special callouts for coatings, heat treatment, or assembly instructions

## Elements to EXCLUDE (Pure Annotations)
Do NOT report changes that are ONLY annotation or documentation differences with no clear underlying physical change, such as:
- Free-standing text notes, title text, company logos
- Dimension text changes where the underlying geometry clearly did NOT move or resize
- Leaders, arrows, center marks, construction lines
- Revision clouds, markup, grid lines, view labels
- Detail/section/elevation callout symbols by themselves

If a DIFFERENCE in dimension, GD&T, or note clearly indicates a real physical change to the part or assembly (e.g., a hole diameter changed, a tolerance loosened/tightened, or a surface finish requirement changed), you SHOULD report that as a design change even if the geometry shift is subtle.

## Instructions

CRITICAL:
- EVERY SINGLE real mechanical design change in the GREEN and RED areas should be covered by a bounding box.
- Group closely related features that function as a unit (e.g., a bolt set with washer and nut; a shaft step with keyway and retaining ring) if spatially close, but do not group unrelated features.
- When multiple features all move together (for example, an entire bolt pattern or a mounting bracket shifts), report them as a single change, typically a "Move" or "Dimension Change" for that group or interface.
- When encountering a 'Remove', 'Add' or 'Dimension Change' action, think carefully about whether it is actually a 'Move' by looking around in the vicinity and determining whether the feature is simply shifted.

For each change provide:
1. **elements**: The mechanical element types from the lists above (e.g., "through hole", "tapped hole pattern", "shaft keyway", "mounting bracket", "gear", "bearing seat").
2. **action**:
   - 'Add' (green only) for newly introduced physical features
   - 'Remove' (red only) for deleted features
   - 'Move' (both colors offset) when a feature or group of features has shifted location but is otherwise similar
   - 'Dimension Change' (resized or specification-changed) when geometry, size, tolerance, or critical spec changes
3. **description**: A clear, human-readable description of the change in plain English. Be specific about WHAT changed and WHERE, and use mechanical terminology from the legends, GD&T, and notes when possible. Examples:
4. **direction**: 'up', 'down', 'left', 'right' (only for Move actions, based on the drawing orientation).
5. **value**: ['start_value', 'final_value'] (only for Dimension Change). Use concise numeric/spec values when available, such as:
6. **location**: Tight bounding box around the physical area of change, not the entire sheet. Coordinates should be normalized to a 1000x1000 grid (0-1000).
"""

SYSTEM_PROMPT_DISCREPANCIES = """You are an expert construction manager and superintendent, experienced in reading construction drawings and identifying discrepancies between multiple drawings of different disciplines.

Your task is to locate all discrepancies_and_complications that have already been identified between the two drawings provided, A and B, using bounding boxes.
The drawing is a color coded overlay of the two drawings, showing:
- GREEN pixels: features that are present in B but not in A
- RED pixels: features that are present in A but not in B
- BLACK or GREY pixels: overlapping features that are present in both A and B.

## Context Images Provided
You will receive the main OVERLAY IMAGE first, followed by context images from both drawings:
- **DRAWING A context**: Legend, general notes, key notes, and other reference materials from drawing A
- **DRAWING B context**: Legend, general notes, and other reference materials from drawing B

Use these context images to:
- Identify symbols and their meanings from the legends
- Understand material specifications from general notes
- Reference key notes for specific callouts

## Instructions

For each discrepancy provide:
1. **description**: The exactly, verbatim description of the discrepancy and complication from the discrepancies_and_complications section below.
2. **identifier**: Reference identifier combining category letter and item number (e.g., 'a.1', 'a.2', 'b.1', 'b.2', 'c.1', 'c.2') matching the discrepancy list.
3. **severity**: Assess the severity level - 'Critical' (safety/structural), 'Major' (requires redesign), 'Minor' (coordination issue).
4. **elements**: List of construction elements involved in the discrepancy.
5. **location**: Tight bounding box, coordinates should be normalized to 1000x1000 grid (0-1000).

<discrepancies_and_complications>
a. Chimneys / vertical elements vs walls and doors

1. At the south ends of the three long cleanroom bays (around gridlines H-5, J-5, K-5), the green "chimneys"/vertical plenums land right on top of red partition lines instead of inside a room or clearly on one side of the wall.
2. In several cases the green chimney edge lies exactly where a door frame or jamb is shown in red in the chases and corridor below (rooms 102-107 area). → This is consistent with your field condition where a chimney is tight against a 1-hr rated wall and blocks the door.

b. Cleanroom ceiling boundary vs partition lines

1. Along the south edge of the plenum (between grids G-K and 5-6), **the cleanroom ceiling line in green does not follow the red corridor/room walls.** Portions of the plenum extend over spaces that the framing drawings show as separate rooms or chases, and in other spots the walls fall directly below main plenum beams.
2. **Result: some partitions that are intended to be separation walls (including rated ones) are directly under major plenum members with no allowance for required clearances, access panels, or door heads.**

c. Room geometry below vs plenum module grid

1. **The red wall layout of the small chase rooms 101-107 is not centered on the green module grid.** Walls consistently cut across the ends of FFU rows and across the support steel.
2. That means light fixtures/FFUs/returns that are on a regular green grid will end up half-bay or more out of alignment with the framed openings and corridors below.
</discrepancies_and_complications>

First, think through the individual discrepancies and complications one by one described in the <discrepancies_and_complications> section, and then provide the bounding boxes for each.
"""


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def load_context_images(folder_path: str) -> dict:
    """Load all context images from the folder structure.

    Expected structure:
    folder_path/
        overlay.png          # Main overlay image
        context/
            old/             # Context images from old drawing
                *.png
            new/             # Context images from new drawing
                *.png

    Returns dict with keys: 'overlay', 'old_context', 'new_context'
    """
    result = {"overlay": None, "old_context": [], "new_context": []}

    # Load main overlay image
    overlay_path = os.path.join(folder_path, "overlay.png")
    if os.path.exists(overlay_path):
        result["overlay"] = overlay_path
    else:
        print(f"Warning: overlay.png not found in {folder_path}")

    # Load old context images
    old_context_dir = os.path.join(folder_path, "context", "old")
    if os.path.isdir(old_context_dir):
        for filename in sorted(os.listdir(old_context_dir)):
            if filename.lower().endswith(".png"):
                result["old_context"].append(os.path.join(old_context_dir, filename))
        print(f"Found {len(result['old_context'])} OLD context images")

    # Load new context images
    new_context_dir = os.path.join(folder_path, "context", "new")
    if os.path.isdir(new_context_dir):
        for filename in sorted(os.listdir(new_context_dir)):
            if filename.lower().endswith(".png"):
                result["new_context"].append(os.path.join(new_context_dir, filename))
        print(f"Found {len(result['new_context'])} NEW context images")

    return result


def analyze_overlay_gemini(
    image_path: str,
    old_context_images: list[str] = None,
    new_context_images: list[str] = None,
    region_description: str = "full image",
    mode: AnalysisMode = AnalysisMode.CHANGE_DETECTION,
) -> ChangeList | DiscrepancyList | None:
    """Analyze an overlay image for changes or discrepancies.

    Args:
        image_path: Path to the main overlay image
        old_context_images: List of paths to context images from drawing A/old
        new_context_images: List of paths to context images from drawing B/new
        region_description: Description of the region being analyzed
        mode: Analysis mode - CHANGE_DETECTION or DISCREPANCY

    Returns:
        ChangeList for change detection mode, DiscrepancyList for discrepancy mode
    """
    mode_str = (
        "change detection" if mode == AnalysisMode.CHANGE_DETECTION else "discrepancy detection"
    )
    print(f"Processing {region_description} with Gemini ({GEMINI_MODEL}) in {mode_str} mode...")

    old_context_images = old_context_images or []
    new_context_images = new_context_images or []

    client = genai.Client(api_key=GEMINI_API_KEY, http_options={"api_version": "v1alpha"})

    # Select prompt and schema based on mode
    if mode == AnalysisMode.CHANGE_DETECTION:
        system_prompt = SYSTEM_PROMPT_OVERLAY
        response_schema = ChangeList
    else:
        system_prompt = SYSTEM_PROMPT_DISCREPANCIES
        response_schema = DiscrepancyList

    # Build parts list
    parts = [
        types.Part.from_text(text=system_prompt),
    ]

    # Add context images (labeled appropriately based on mode)
    context_a_label = (
        "OLD DRAWING" if mode == AnalysisMode.CHANGE_DETECTION else "Framing Drawing A"
    )
    context_b_label = "NEW DRAWING" if mode == AnalysisMode.CHANGE_DETECTION else "Plenum Drawing B"

    if old_context_images:
        parts.append(types.Part.from_text(text=f"\n## {context_a_label} CONTEXT:"))
        for ctx_path in old_context_images:
            filename = os.path.basename(ctx_path)
            parts.append(types.Part.from_text(text=f"### {filename}:"))
            parts.append(
                types.Part.from_bytes(
                    mime_type="image/png",
                    data=base64.b64decode(image_to_base64(ctx_path)),
                    media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
                )
            )

    if new_context_images:
        parts.append(types.Part.from_text(text=f"\n## {context_b_label} CONTEXT:"))
        for ctx_path in new_context_images:
            filename = os.path.basename(ctx_path)
            parts.append(types.Part.from_text(text=f"### {filename}:"))
            parts.append(
                types.Part.from_bytes(
                    mime_type="image/png",
                    data=base64.b64decode(image_to_base64(ctx_path)),
                    media_resolution=types.MediaResolution.MEDIA_RESOLUTION_MEDIUM,
                )
            )

    parts.append(types.Part.from_text(text="## MAIN OVERLAY IMAGE (analyze this):"))
    parts.append(
        types.Part.from_bytes(
            mime_type="image/png",
            data=base64.b64decode(image_to_base64(image_path)),
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        )
    )

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=response_schema,
                thinking_config=types.ThinkingConfig(
                    thinkingLevel="high",
                ),
            ),
        )
        print(f"Usage: {response.usage_metadata}")
        try:
            result_dict = json.loads(response.text)
            if mode == AnalysisMode.CHANGE_DETECTION:
                return ChangeList(**result_dict)
            else:
                return DiscrepancyList(**result_dict)
        except json.JSONDecodeError:
            print(f"Error decoding JSON response: {response.text}")
            return None
        except Exception as e:
            print(f"Error parsing response: {e}")
            return None

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None


def analyze_with_tiling(
    image_path: str,
    output_dir: str,
    old_context_images: list[str] = None,
    new_context_images: list[str] = None,
    mode: AnalysisMode = AnalysisMode.CHANGE_DETECTION,
) -> ChangeList | DiscrepancyList:
    """Analyze image using tiling with optional context images.

    Args:
        image_path: Path to the main overlay image
        output_dir: Directory for output files
        old_context_images: List of paths to context images from drawing A/old
        new_context_images: List of paths to context images from drawing B/new
        mode: Analysis mode - CHANGE_DETECTION or DISCREPANCY
    """
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image {image_path}")
        if mode == AnalysisMode.CHANGE_DETECTION:
            return ChangeList(changes=[])
        else:
            return DiscrepancyList(discrepancies=[])

    old_context_images = old_context_images or []
    new_context_images = new_context_images or []

    h, w = img.shape[:2]

    # Define 2x2 grid with overlap
    # Overlap of 10% or fixed pixels
    overlap = 100  # pixels

    mid_x = w // 2
    mid_y = h // 2

    tiles = [
        # (name, x, y, width, height)
        ("top_left", 0, 0, mid_x + overlap, mid_y + overlap),
        ("top_right", mid_x - overlap, 0, w - (mid_x - overlap), mid_y + overlap),
        ("bottom_left", 0, mid_y - overlap, mid_x + overlap, h - (mid_y - overlap)),
        (
            "bottom_right",
            mid_x - overlap,
            mid_y - overlap,
            w - (mid_x - overlap),
            h - (mid_y - overlap),
        ),
    ]

    all_items = []

    temp_dir = os.path.join(output_dir, "temp_tiles")
    os.makedirs(temp_dir, exist_ok=True)

    for name, tx, ty, tw, th in tiles:
        tile_img = img[ty : ty + th, tx : tx + tw]
        tile_path = os.path.join(temp_dir, f"tile_{name}.png")
        cv2.imwrite(tile_path, tile_img)

        print(f"Analyzing tile: {name} ({tw}x{th})")
        result = analyze_overlay_gemini(
            tile_path,
            old_context_images=old_context_images,
            new_context_images=new_context_images,
            region_description=f"{name} quadrant",
            mode=mode,
        )

        if result:
            # Get items based on mode
            items = (
                result.changes if mode == AnalysisMode.CHANGE_DETECTION else result.discrepancies
            )

            for item in items:
                # Transform coordinates back to global 0-1000
                # Local 0-1000 -> Local Pixels -> Global Pixels -> Global 0-1000

                loc = item.location

                # Local normalized to Local pixels
                lx1 = loc.xmin * tw / 1000
                ly1 = loc.ymin * th / 1000
                lx2 = loc.xmax * tw / 1000
                ly2 = loc.ymax * th / 1000

                # Global pixels
                gx1 = lx1 + tx
                gy1 = ly1 + ty
                gx2 = lx2 + tx
                gy2 = ly2 + ty

                # Global normalized
                nx1 = int(gx1 * 1000 / w)
                ny1 = int(gy1 * 1000 / h)
                nx2 = int(gx2 * 1000 / w)
                ny2 = int(gy2 * 1000 / h)

                # Update location
                item.location = Location(xmin=nx1, ymin=ny1, xmax=nx2, ymax=ny2)
                all_items.append(item)

    if mode == AnalysisMode.CHANGE_DETECTION:
        return ChangeList(changes=all_items)
    else:
        return DiscrepancyList(discrepancies=all_items)


def draw_bounding_boxes(
    image_path: str,
    result: ChangeList | DiscrepancyList,
    output_path: str,
    mode: AnalysisMode = AnalysisMode.CHANGE_DETECTION,
):
    """Draw bounding boxes on the image for changes or discrepancies."""
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image {image_path}")
        return

    h, w = img.shape[:2]

    if mode == AnalysisMode.CHANGE_DETECTION:
        # Colors for change detection (all blue as requested)
        colors = {
            "Add": (255, 0, 0),  # Blue
            "Remove": (255, 0, 0),  # Blue
            "Dimension Change": (255, 0, 0),  # Blue
            "Move": (255, 0, 0),  # Blue
        }
        items = result.changes
        print(f"Found {len(items)} changes:")

        for change in items:
            color = colors.get(change.action, (255, 0, 255))  # Default Magenta

            loc = change.location
            x1 = int(loc.xmin * w / 1000)
            y1 = int(loc.ymin * h / 1000)
            x2 = int(loc.xmax * w / 1000)
            y2 = int(loc.ymax * h / 1000)

            cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

            label_text = f"{change.action}: {', '.join(change.elements)}"
            cv2.putText(img, label_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            print(f"- {change.action} [{', '.join(change.elements)}]: {change.description}")
    else:
        # Colors for discrepancy detection by severity
        severity_colors = {
            "Critical": (0, 0, 255),  # Red (BGR)
            "Major": (0, 165, 255),  # Orange (BGR)
            "Minor": (0, 255, 255),  # Yellow (BGR)
        }
        items = result.discrepancies
        print(f"Found {len(items)} discrepancies:")

        for discrepancy in items:
            color = severity_colors.get(discrepancy.severity, (255, 0, 255))  # Default Magenta

            loc = discrepancy.location
            x1 = int(loc.xmin * w / 1000)
            y1 = int(loc.ymin * h / 1000)
            x2 = int(loc.xmax * w / 1000)
            y2 = int(loc.ymax * h / 1000)

            cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)

            label_text = f"[{discrepancy.identifier}] {discrepancy.severity}"
            cv2.putText(img, label_text, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

            print(
                f"- [{discrepancy.identifier}] {discrepancy.severity}: {discrepancy.description[:80]}..."
            )

    cv2.imwrite(output_path, img)
    print(f"Saved result to {output_path}")


def save_results(
    result: ChangeList | DiscrepancyList,
    output_dir: str,
    base_name: str,
    img_width: int,
    img_height: int,
    mode: AnalysisMode = AnalysisMode.CHANGE_DETECTION,
) -> None:
    """Save results to JSON and CSV files with pixel coordinates."""
    output_data = {
        "image_width": img_width,
        "image_height": img_height,
        "mode": mode.value,
    }

    if mode == AnalysisMode.CHANGE_DETECTION:
        output_data["changes"] = []
        for change in result.changes:
            loc = change.location
            x1_px = int(loc.xmin * img_width / 1000)
            y1_px = int(loc.ymin * img_height / 1000)
            x2_px = int(loc.xmax * img_width / 1000)
            y2_px = int(loc.ymax * img_height / 1000)

            change_data = {
                "action": change.action,
                "elements": change.elements,
                "description": change.description,
                "direction": change.direction,
                "value": change.value,
                "location": {"xmin": x1_px, "ymin": y1_px, "xmax": x2_px, "ymax": y2_px},
            }
            output_data["changes"].append(change_data)
    else:
        output_data["discrepancies"] = []
        for discrepancy in result.discrepancies:
            loc = discrepancy.location
            x1_px = int(loc.xmin * img_width / 1000)
            y1_px = int(loc.ymin * img_height / 1000)
            x2_px = int(loc.xmax * img_width / 1000)
            y2_px = int(loc.ymax * img_height / 1000)

            discrepancy_data = {
                "identifier": discrepancy.identifier,
                "severity": discrepancy.severity,
                "description": discrepancy.description,
                "elements": discrepancy.elements,
                "location": {"xmin": x1_px, "ymin": y1_px, "xmax": x2_px, "ymax": y2_px},
            }
            output_data["discrepancies"].append(discrepancy_data)

    # Save JSON
    json_path = os.path.join(output_dir, f"{base_name}.json")
    with open(json_path, "w") as f:
        json.dump(output_data, f, indent=2)
    print(f"Saved JSON to {json_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze overlay images for changes or discrepancies"
    )
    parser.add_argument(
        "--mode",
        "-m",
        type=str,
        choices=["change", "discrepancy"],
        default="change",
        help="Analysis mode: 'change' for change detection, 'discrepancy' for discrepancy detection (default: change)",
    )
    parser.add_argument(
        "--folder",
        "-f",
        type=str,
        default="M201",
        help="Target folder name in dataset directory (default: M201)",
    )
    parser.add_argument(
        "--tiling",
        "-t",
        action="store_true",
        help="Enable tiling mode to split image into quadrants for analysis (default: disabled)",
    )

    args = parser.parse_args()

    # Convert mode string to enum
    analysis_mode = (
        AnalysisMode.CHANGE_DETECTION if args.mode == "change" else AnalysisMode.DISCREPANCY
    )

    # Default paths
    dataset_dir = os.path.join(os.path.dirname(__file__), "dataset")
    target_folder = args.folder
    input_folder = os.path.join(dataset_dir, target_folder)
    output_dir = os.path.join(os.path.dirname(__file__), "outputs", target_folder)

    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isdir(input_folder):
        print(f"Error: Input folder not found at {input_folder}")
        sys.exit(1)

    # Load context images from folder structure
    context = load_context_images(input_folder)

    if not context["overlay"]:
        print(f"Error: No overlay.png found in {input_folder}")
        sys.exit(1)

    overlay_path = context["overlay"]
    output_image_path = os.path.join(output_dir, "overlay_annotated.png")

    print(f"Analysis mode: {analysis_mode.value}")
    print(f"Tiling: {'enabled' if args.tiling else 'disabled'}")
    print(f"Analyzing folder: {target_folder}")
    print(f"  Overlay: {overlay_path}")
    print(f"  Drawing A context images: {len(context['old_context'])}")
    for img_path in context["old_context"]:
        print(f"    - {os.path.basename(img_path)}")
    print(f"  Drawing B context images: {len(context['new_context'])}")
    for img_path in context["new_context"]:
        print(f"    - {os.path.basename(img_path)}")

    # Analyze overlay
    if args.tiling:
        result = analyze_with_tiling(
            overlay_path,
            output_dir,
            old_context_images=context["old_context"],
            new_context_images=context["new_context"],
            mode=analysis_mode,
        )
    else:
        result = analyze_overlay_gemini(
            overlay_path,
            old_context_images=context["old_context"],
            new_context_images=context["new_context"],
            region_description="full image",
            mode=analysis_mode,
        )

    if result:
        draw_bounding_boxes(overlay_path, result, output_image_path, mode=analysis_mode)
        # Save results to JSON and CSV with pixel coordinates
        img = cv2.imread(overlay_path)
        img_h, img_w = img.shape[:2]
        # Output filename: 'changes' or 'discrepancies' based on mode
        output_name = (
            "changes" if analysis_mode == AnalysisMode.CHANGE_DETECTION else "discrepancies"
        )
        save_results(result, output_dir, output_name, img_w, img_h, mode=analysis_mode)
