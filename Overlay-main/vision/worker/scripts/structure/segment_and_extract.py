"""
Segment and Extract Construction Drawing Blocks

This script processes old and new construction drawing images:
1. Segments each image into blocks (plans, legends, notes, etc.)
2. For image blocks: crops and saves as PNG
3. For text blocks: runs OCR with Gemini Flash to extract markdown
4. For title_block: extracts sheet number
5. For floor_plan/elevation/section: performs alignment and overlay generation

Usage:
    python segment_and_extract.py --old path/to/old.png --new path/to/new.png

Outputs:
    outputs/old/sheet.json - Block metadata for old image
    outputs/new/sheet.json - Block metadata for new image
    outputs/old/blocks/*.png - Cropped block images
    outputs/new/blocks/*.png - Cropped block images
    outputs/comparison/*.png - Aligned and overlay images for matched blocks
"""

import argparse
import io
import json
import os
import sys
from enum import Enum
from pathlib import Path
from typing import Literal, TypeVar

import cv2
import numpy as np
from PIL import Image
from pydantic import BaseModel, Field

# Add worker root to path
worker_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
sys.path.append(worker_root)

from dotenv import load_dotenv

# Load .env from worker root
load_dotenv(os.path.join(worker_root, ".env"))

from google import genai
from google.genai import types

# Increase PIL's decompression bomb limit for large construction drawings
Image.MAX_IMAGE_PIXELS = 250_000_000

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_PRO = "gemini-3-pro-preview"
GEMINI_MODEL_FLASH = "gemini-2.5-flash"

# Token usage tracking per model
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
    _token_usage[model]["output_tokens"] += (
        getattr(usage_metadata, "candidates_token_count", 0) or 0
    )
    _token_usage[model]["thinking_tokens"] += (
        getattr(usage_metadata, "thoughts_token_count", 0) or 0
    )
    _token_usage[model]["cached_tokens"] += (
        getattr(usage_metadata, "cached_content_token_count", 0) or 0
    )


def calculate_llm_cost(cost_per_model: dict[str, dict[str, float]]) -> dict[str, float]:
    """Calculate total LLM cost based on token usage.

    Args:
        cost_per_model: Mapping of model name to token costs (per 1M tokens).
            Example: {
                "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cached": 0.03},
            }

    Returns:
        Dict with cost breakdown per model and total.
    """
    costs: dict[str, float] = {}
    total = 0.0

    for model, usage in _token_usage.items():
        model_costs = cost_per_model.get(model, {"input": 0, "output": 0, "cached": 0})
        # Cached tokens are billed at cached rate, remaining input at full rate
        cached = usage["cached_tokens"]
        non_cached_input = usage["input_tokens"] - cached
        cached_cost = (cached / 1_000_000) * model_costs.get("cached", 0)
        input_cost = (non_cached_input / 1_000_000) * model_costs.get("input", 0)
        # Thinking tokens billed at output rate
        output_cost = (
            (usage["output_tokens"] + usage["thinking_tokens"]) / 1_000_000
        ) * model_costs.get("output", 0)
        model_total = input_cost + cached_cost + output_cost
        costs[model] = model_total
        total += model_total

    costs["total"] = total
    return costs


def print_token_usage_summary(cost_per_model: dict[str, dict[str, float]] | None = None) -> None:
    """Print a summary of token usage and optionally costs."""
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


if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment.")
    sys.exit(1)

# Script directories
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"
DATASET_DIR = SCRIPT_DIR / "dataset"

# Default input images
DEFAULT_OLD = DATASET_DIR / "healthpeak_new.png"
DEFAULT_NEW = DATASET_DIR / "Bower_framing_page_0.png"


# ============== Block Type Definitions ==============


class BlockCategory(str, Enum):
    """Categories for grouping block types."""

    VIEW = "view"  # Main drawings with identifiers (plans, elevations, sections, details)
    SYMBOL = "symbol"  # Supporting graphic symbols (legends, key_plan, diagram, north_arrow)
    TABULAR = "tabular"  # Table-based content (schedule, revision_history)
    NOTES = "notes"  # Text content (general_notes, key_notes, etc.)
    METADATA = "metadata"  # Sheet info (title_block, consultants, seals)


class BlockType(str, Enum):
    """Block types found on construction drawing sheets."""

    # View blocks (category = 'view')
    PLAN = "plan"
    ELEVATION = "elevation"
    SECTION = "section"
    DETAIL = "detail"
    # Reference blocks (category = 'reference')
    LEGEND = "legend"
    DIAGRAM = "diagram"
    KEY_PLAN = "key_plan"
    NORTH_ARROW = "north_arrow"
    # Tabular blocks (category = 'tabular')
    SCHEDULE = "schedule"
    REVISION_HISTORY = "revision_history"
    PROJECT_INFO = "project_info"
    # Notes blocks (category = 'notes')
    GENERAL_NOTES = "general_notes"
    KEY_NOTES = "key_notes"
    SHEET_NOTES = "sheet_notes"
    ABBREVIATIONS = "abbreviations"
    CODE_REFERENCES = "code_references"
    NOTES = "notes"
    # Metadata blocks (category = 'metadata')
    TITLE_BLOCK = "title_block"
    CONSULTANTS = "consultants"
    SEALS = "seals"


class BlockTypeInfo(BaseModel):
    """Metadata for a block type."""

    storage_type: Literal["image", "text"]
    category: BlockCategory
    description: str


# Consolidated block type information
BLOCK_TYPE_INFO: dict[BlockType, BlockTypeInfo] = {
    # View blocks - main drawings with identifiers
    BlockType.PLAN: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Plan view: floor plan, ceiling plan, roof plan, site plan, etc.",
    ),
    BlockType.ELEVATION: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Vertical orthographic view of exterior or interior walls",
    ),
    BlockType.SECTION: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Vertical cut through building showing internal construction layers",
    ),
    BlockType.DETAIL: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Enlarged view of construction assembly, connection, or component",
    ),
    # Reference blocks - supporting graphics
    BlockType.LEGEND: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Key explaining symbols, materials, finishes, or patterns",
    ),
    BlockType.DIAGRAM: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Schematic representation: riser, single-line, or flow diagram",
    ),
    BlockType.KEY_PLAN: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Small reference plan indicating location of current view within building",
    ),
    BlockType.NORTH_ARROW: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Orientation symbol showing north direction",
    ),
    # Tabular blocks - table-based content
    BlockType.SCHEDULE: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.TABULAR,
        description="Table listing specs for repeated elements (doors, windows, finishes, etc.)",
    ),
    BlockType.REVISION_HISTORY: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.TABULAR,
        description="Table tracking drawing changes with dates and descriptions",
    ),
    BlockType.PROJECT_INFO: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.TABULAR,
        description="Project data: building area, occupancy, parking calculations, zoning info",
    ),
    BlockType.ABBREVIATIONS: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.TABULAR,
        description="List of abbreviated terms and their meanings",
    ),
    # Notes blocks - text content
    BlockType.GENERAL_NOTES: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Project-wide requirements, standards, and specifications",
    ),
    BlockType.KEY_NOTES: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Numbered callouts referenced on drawings (KN-1, KN-2, etc.)",
    ),
    BlockType.SHEET_NOTES: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Notes applicable only to the current sheet",
    ),
    BlockType.CODE_REFERENCES: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Building code citations and compliance requirements",
    ),
    BlockType.NOTES: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Generic notes if specific type cannot be determined",
    ),
    # Metadata blocks - sheet info
    BlockType.TITLE_BLOCK: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.METADATA,
        description="Project name, sheet number, date, scale, revision, and firm info",
    ),
    BlockType.CONSULTANTS: BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.METADATA,
        description="Contact information for engineers, architects, and contractors",
    ),
    BlockType.SEALS: BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.METADATA,
        description="Professional engineer/architect stamps, signatures, agency approvals and certifications",
    ),
}

# Block types that need alignment/overlay when comparing old vs new (all VIEW category blocks)
ALIGNMENT_BLOCK_TYPES = {
    block_type
    for block_type, info in BLOCK_TYPE_INFO.items()
    if info.category == BlockCategory.VIEW
}


# ============== Pydantic Models ==============


class BoundingBox(BaseModel):
    """Bounding box coordinates normalized to 0-1000 scale."""

    xmin: int = Field(description="Left X coordinate (0-1000)")
    ymin: int = Field(description="Top Y coordinate (0-1000)")
    xmax: int = Field(description="Right X coordinate (0-1000)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000)")


class TitleBlockInfo(BaseModel):
    """Extracted title block information."""

    sheet_number: str | None = Field(description="Sheet number (e.g., A101, S-201)")
    sheet_title: str | None = Field(description="Sheet title")
    project_name: str | None = Field(description="Project name")
    date: str | None = Field(description="Date on drawing")
    revision: str | None = Field(description="Current revision")
    scale: str | None = Field(description="Drawing scale")


class BlockInfoMixin(BaseModel):
    """Mixin for block name and identifier fields."""

    name: str | None = Field(
        default=None,
        description="Semantic name/title of the block (e.g., 'FIRST FLOOR PLAN', 'DOOR SCHEDULE')",
    )
    identifier: str | None = Field(
        default=None,
        description="Block identifier - number, letter, or code (e.g., '1', 'A', 'D1', 'E' for elevation)",
    )


class Block(BlockInfoMixin):
    """A block/region on a construction drawing sheet."""

    block_type: BlockType = Field(description="Block type")
    bbox: BoundingBox = Field(description="Bounding box coordinates")
    description: str = Field(description="Brief description of the content")
    storage_type: Literal["image", "text"] | None = None
    image_uri: str | None = None
    ocr_text: str | None = Field(
        default=None,
        description="Text content as markdown from the block exactly as it appears in the image. DO NOT add any other text or content. If the image is empty, return an empty string.",
    )
    title_block_info: TitleBlockInfo | None = None
    has_grid_callouts: bool | None = Field(
        default=None,
        description="Whether the view has grid reference callouts (bubbles with letters/numbers at edges)",
    )


class SegmentationResult(BaseModel):
    """Result of block segmentation."""

    blocks: list[Block] = Field(description="List of detected blocks")


class SheetMetadata(BaseModel):
    """Metadata for a full sheet."""

    image_uri: str
    sheet_number: str | None = None
    blocks: list[Block]


# ============== Segmentation ==============


def _build_block_types_prompt() -> str:
    """Build the block types section of the segmentation prompt from BLOCK_TYPE_INFO."""
    image_lines = []
    text_lines = []
    for block_type, info in BLOCK_TYPE_INFO.items():
        line = f"- {block_type.value}: {info.description}"
        if info.storage_type == "image":
            image_lines.append(line)
        else:
            text_lines.append(line)
    return (
        "IMAGE BLOCKS (visual content):\n"
        + "\n".join(image_lines)
        + "\n\nTEXT BLOCKS (text-heavy content):\n"
        + "\n".join(text_lines)
    )


SEGMENTATION_PROMPT = f"""You are an expert construction drawing analyzer.
Your task is to identify and segment the distinct "blocks" of information on a construction drawing sheet.
Analyze the construction image provided above. Return bounding boxes (0-1000 normalized) for all distinct blocks.

Block types to identify:
{_build_block_types_prompt()}

For each block, provide:
1. block_type: The block type from above
2. bbox: Bounding box with xmin, ymin, xmax, ymax coordinates normalized to 0-1000 grid
3. description: Brief description of the content

IMPORTANT INSTRUCTIONS:
1. Return coordinates as xmin, ymin, xmax, ymax normalized to 1000.
2. Be sure to separate blocks that are distinct rectangular regions.
3. Bounding boxes should not fully encompass each other, but they can partially overlap. If boxes are completely enclosed in another box, they should be separated or merged.
4. Bounding boxes should be expanded to include all relevant grid lines and grid reference callouts (grid bubbles or markers containing a letter, number or decimal), titles and labels. Do not cut off any grid line reference callouts.
5. Do not cut off parts of a text, drawing, diagram, plan or any content. Expand the box to fully encompass the unit of content.
"""


def segment_image(image_path: str, client: genai.Client) -> SegmentationResult:
    """Segment an image into blocks using Gemini Pro."""
    print(f"  Segmenting {image_path}...")

    with open(image_path, "rb") as f:
        png_bytes = f.read()

    return _llm_extract(  # type: ignore[return-value]
        png_bytes,
        SEGMENTATION_PROMPT,
        client,
        response_schema=SegmentationResult,
        media_resolution="MEDIA_RESOLUTION_HIGH",
        model=GEMINI_MODEL_PRO,
        thinking_level="low",
    )


# ============== Image Processing ==============


def load_image(path: str) -> np.ndarray:
    """Load image as RGB numpy array."""
    img = Image.open(path)
    return np.array(img.convert("RGB"), dtype=np.uint8)


def save_image(img: np.ndarray, path: Path) -> None:
    """Save RGB numpy array as PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    pil_img = Image.fromarray(img, mode="RGB")
    pil_img.save(path)


def pad_blocks(
    blocks: list[Block], image_width: int, image_height: int, padding_px: int = 10
) -> list[Block]:
    """Apply pixel padding to all block bounding boxes, respecting image boundaries.

    Args:
        blocks: List of blocks with normalized bbox coords (0-1000)
        image_width: Actual image width in pixels
        image_height: Actual image height in pixels
        padding_px: Padding in pixels to add to each side

    Returns:
        List of new Block objects with padded bounding box coordinates
    """
    padded_blocks = []
    for block in blocks:
        # Convert normalized to pixels
        x1 = int(block.bbox.xmin * image_width / 1000)
        y1 = int(block.bbox.ymin * image_height / 1000)
        x2 = int(block.bbox.xmax * image_width / 1000)
        y2 = int(block.bbox.ymax * image_height / 1000)

        # Add padding (respecting image boundaries)
        x1_padded = max(0, x1 - padding_px)
        y1_padded = max(0, y1 - padding_px)
        x2_padded = min(image_width, x2 + padding_px)
        y2_padded = min(image_height, y2 + padding_px)

        # Convert back to normalized (0-1000)
        padded_bbox = BoundingBox(
            xmin=int(x1_padded * 1000 / image_width),
            ymin=int(y1_padded * 1000 / image_height),
            xmax=int(x2_padded * 1000 / image_width),
            ymax=int(y2_padded * 1000 / image_height),
        )
        padded_blocks.append(
            Block(
                block_type=block.block_type,
                bbox=padded_bbox,
                description=block.description,
            )
        )
    return padded_blocks


def crop_block(image: np.ndarray, bbox: BoundingBox) -> np.ndarray:
    """Crop a block from the image using normalized bbox coordinates."""
    h, w = image.shape[:2]

    x1 = int(bbox.xmin * w / 1000)
    y1 = int(bbox.ymin * h / 1000)
    x2 = int(bbox.xmax * w / 1000)
    y2 = int(bbox.ymax * h / 1000)

    # Ensure bounds are valid
    x1, x2 = max(0, x1), min(w, x2)
    y1, y2 = max(0, y1), min(h, y2)

    return image[y1:y2, x1:x2].copy()


def get_storage_type(block_type: str) -> Literal["image", "text"]:
    """Determine storage type based on block type."""
    try:
        return BLOCK_TYPE_INFO[BlockType(block_type)].storage_type
    except (ValueError, KeyError):
        return "image"  # Default to image for unknown types


def draw_blocks_visualization(
    image: np.ndarray,
    blocks: list[Block],
    output_path: Path,
) -> None:
    """Draw bounding boxes on image and save as visualization."""
    h, w = image.shape[:2]

    # Convert RGB to BGR for OpenCV drawing
    vis_img = cv2.cvtColor(image.copy(), cv2.COLOR_RGB2BGR)

    # Colors for different block types (BGR format)
    colors = {
        # View blocks - greens
        BlockType.PLAN: (0, 200, 0),
        BlockType.ELEVATION: (0, 160, 0),
        BlockType.SECTION: (0, 140, 0),
        BlockType.DETAIL: (200, 100, 0),
        # Reference blocks - purples
        BlockType.LEGEND: (140, 0, 140),
        BlockType.DIAGRAM: (100, 200, 100),
        BlockType.KEY_PLAN: (200, 200, 0),
        BlockType.NORTH_ARROW: (180, 180, 0),
        # Tabular blocks - cyans
        BlockType.SCHEDULE: (0, 200, 200),
        BlockType.REVISION_HISTORY: (0, 150, 200),
        BlockType.PROJECT_INFO: (0, 180, 180),
        # Notes blocks - reds
        BlockType.GENERAL_NOTES: (0, 0, 200),
        BlockType.KEY_NOTES: (0, 50, 200),
        BlockType.SHEET_NOTES: (0, 100, 200),
        BlockType.ABBREVIATIONS: (100, 50, 200),
        BlockType.CODE_REFERENCES: (150, 50, 200),
        BlockType.NOTES: (0, 100, 255),
        # Metadata blocks - grays/blues
        BlockType.TITLE_BLOCK: (0, 0, 255),
        BlockType.CONSULTANTS: (50, 50, 200),
        BlockType.SEALS: (100, 100, 100),
    }

    for block in blocks:
        color = colors.get(block.block_type, (128, 128, 128))

        # Scale coordinates to image dimensions
        x1 = int(block.bbox.xmin * w / 1000)
        y1 = int(block.bbox.ymin * h / 1000)
        x2 = int(block.bbox.xmax * w / 1000)
        y2 = int(block.bbox.ymax * h / 1000)

        # Draw rectangle
        cv2.rectangle(vis_img, (x1, y1), (x2, y2), color, 4)

        # Draw label background
        label = block.block_type
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.0
        thickness = 2
        (text_w, text_h), baseline = cv2.getTextSize(label, font, font_scale, thickness)

        # Label position (above the box if possible)
        label_y = y1 - 10 if y1 > text_h + 10 else y1 + text_h + 10

        # Draw label background rectangle
        cv2.rectangle(
            vis_img, (x1, label_y - text_h - 5), (x1 + text_w + 10, label_y + 5), color, -1
        )

        # Draw label text
        cv2.putText(vis_img, label, (x1 + 5, label_y), font, font_scale, (255, 255, 255), thickness)

    # Convert back to RGB and save
    vis_rgb = cv2.cvtColor(vis_img, cv2.COLOR_BGR2RGB)
    save_image(vis_rgb, output_path)
    print(f"  Saved blocks visualization: {output_path}")


# ============== Shared LLM Helper ==============

T = TypeVar("T", bound=BaseModel)


def _image_to_png_bytes(image: np.ndarray) -> bytes:
    """Convert numpy array to PNG bytes."""
    pil_img = Image.fromarray(image, mode="RGB")
    buffer = io.BytesIO()
    pil_img.save(buffer, format="PNG")
    return buffer.getvalue()


def _llm_extract(
    image: np.ndarray | bytes,
    prompt: str,
    client: genai.Client,
    response_schema: type[T] | None = None,
    media_resolution: str = "MEDIA_RESOLUTION_MEDIUM",
    model: str = GEMINI_MODEL_FLASH,
    thinking_level: str | None = None,
) -> T | str:
    """Shared helper for LLM-based extraction from images.

    Args:
        image: Image as numpy array or raw PNG bytes
        prompt: The extraction prompt
        client: Gemini client
        response_schema: Pydantic model for structured JSON response, or None for raw text
        media_resolution: Resolution setting (LOW, MEDIUM, HIGH)
        model: Model to use (FLASH or PRO)
        thinking_level: Optional thinking level for reasoning models (e.g., "low", "medium", "high")

    Returns:
        Parsed model instance if response_schema provided, else raw text
    """
    # Convert to bytes if numpy array
    if isinstance(image, np.ndarray):
        png_bytes = _image_to_png_bytes(image)
    else:
        png_bytes = image

    # Build config
    config_kwargs = {
        "temperature": 0.0,
        "media_resolution": media_resolution,
    }
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema
    if thinking_level is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)

    response = client.models.generate_content(
        model=model,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(mime_type="image/png", data=png_bytes),
                    types.Part.from_text(text=prompt),
                ],
            )
        ],
        config=types.GenerateContentConfig(**config_kwargs),
    )

    # Track token usage
    _track_token_usage(model, response.usage_metadata)

    if response_schema is not None:
        result_dict = json.loads(response.text)
        return response_schema(**result_dict)
    return response.text.strip()


# ============== OCR and Text Extraction ==============

OCR_PROMPT = """You are an expert construction drawing analyzer.Extract all text from this image and format as clean Markdown.
Requirements:
- Preserve the structure and hierarchy of the content
- Use appropriate Markdown formatting:
  - Headers for section titles
  - Numbered lists for sequential items
  - Tables for tabular data
  - **Bold** for emphasis or labels
- For key notes, format as: **KN-1**: Description text
- For revision tables, use Markdown table syntax
- Output the contents exactly as it appears in the image. DO NOT add any other text or content.
- If the image is empty, return an empty string.
Return only the Markdown text, no explanations."""

TITLE_BLOCK_PROMPT = """You are an expert construction drawing analyzer. Extract information from this title block image.
Extract:
- Sheet number (e.g., A101, S-201, M1-01, also called drawing number)
- Sheet title (e.g., "Floor Plan - Level 1")
- Project name
- Date
- Current revision letter/number
- Scale
Return structured data. Use null for fields not found."""

BLOCK_NAME_PROMPT = """You are an expert construction drawing analyzer. Extract the name/title of this construction drawing block.
Look for the semantic title/description, typically found below the content in a label for a view, or above the content in a label for a tabular, legend, notes, or metadata block.
Examples: "FIRST FLOOR PLAN", "DOOR SCHEDULE", "GENERAL NOTES", "EAST ELEVATION", "TYPICAL HEPA FILTER"
Return just the name as a string. Return null if not found."""

VIEW_INFO_PROMPT = """You are an expert construction drawing analyzer. Extract information from this construction drawing view.

1. IDENTIFIER: The reference number/letter used to identify this view, typically found:
   - In a circle, hexagon, or other shape near the block title
   - For plans/sections: numbers like "1", "2", "A1"
   - For elevations: compass directions like "E", "N", "S", "W" or numbers
   - For details: alphanumeric codes like "D1", "1", "A"
   - For callout symbols: the identifier is in the top half of a divided circle (bottom half is sheet number)
   - May include a sheet reference like "1/A101" (identifier is "1", sheet is "A101")

2. GRID CALLOUTS: Determine if this view has grid reference callouts. Grid reference callouts are:
   - Small circles (bubbles) located at the EDGES of the drawing
   - Each circle contains a letter (A, B, C, etc.) or number (1, 2, 3, etc.) or decimal (D.5, 4.5)
   - They mark the positions of structural grid lines
   - Letters typically mark vertical grid lines (columns)
   - Numbers typically mark horizontal grid lines (rows)

Return both the identifier (null if not found) and whether grid callouts are present."""


class _BlockNameResponse(BaseModel):
    """Response model for block name extraction."""

    name: str | None = None


class _ViewInfoResponse(BaseModel):
    """Response model for view info extraction (identifier + grid callouts)."""

    identifier: str | None = None
    has_grid_callouts: bool = False


def extract_view_info(image: np.ndarray, client: genai.Client) -> _ViewInfoResponse:
    """Extract identifier and grid callout info from a VIEW block image."""
    return _llm_extract(image, VIEW_INFO_PROMPT, client, response_schema=_ViewInfoResponse)  # type: ignore[return-value]


def extract_text_with_ocr(image: np.ndarray, client: genai.Client) -> str:
    """Extract text from image using Gemini Flash OCR."""
    return _llm_extract(image, OCR_PROMPT, client)  # type: ignore[return-value]


def extract_title_block_info(image: np.ndarray, client: genai.Client) -> TitleBlockInfo:
    """Extract structured info from title block using Gemini Flash."""
    return _llm_extract(image, TITLE_BLOCK_PROMPT, client, response_schema=TitleBlockInfo)  # type: ignore[return-value]


def extract_block_name(image: np.ndarray, client: genai.Client) -> str | None:
    """Extract name from a block image using Gemini Flash."""
    result = _llm_extract(image, BLOCK_NAME_PROMPT, client, response_schema=_BlockNameResponse)
    return result.name


# ============== Alignment and Overlay ==============


def align_and_overlay(
    old_block: np.ndarray,
    new_block: np.ndarray,
    output_dir: Path,
    block_name: str,
) -> dict:
    """Align old block to new and generate overlay images.

    Returns dict with paths to generated images.
    """
    # Import alignment functions
    from lib.sift_alignment import (
        _convert_to_grayscale,
        apply_transformation,
        estimate_transformation,
        extract_sift_features,
        match_features,
    )

    print(f"    Aligning {block_name}...")

    sift_scale = 1.0

    # Downsample for SIFT
    old_small = cv2.resize(
        old_block, None, fx=sift_scale, fy=sift_scale, interpolation=cv2.INTER_AREA
    )
    new_small = cv2.resize(
        new_block, None, fx=sift_scale, fy=sift_scale, interpolation=cv2.INTER_AREA
    )

    old_gray = _convert_to_grayscale(old_small)
    new_gray = _convert_to_grayscale(new_small)

    # Extract and match features
    kp1, desc1 = extract_sift_features(old_gray, n_features=20000, exclude_margin=0.1)
    kp2, desc2 = extract_sift_features(new_gray, n_features=20000, exclude_margin=0.1)

    if desc1 is None or desc2 is None or len(kp1) < 10 or len(kp2) < 10:
        print(f"    Warning: Insufficient features for alignment in {block_name}")
        return {}

    matches = match_features(desc1, desc2, ratio_threshold=0.5)

    if len(matches) < 10:
        print(f"    Warning: Insufficient matches for alignment in {block_name}")
        return {}

    # Estimate transformation
    matrix, mask, inlier_count, total_matches = estimate_transformation(
        kp1,
        kp2,
        matches,
        reproj_threshold=15.0,
        max_iters=10000,
        confidence=0.95,
    )

    if matrix is None:
        print(f"    Warning: Failed to estimate transformation for {block_name}")
        return {}

    # Scale matrix back to full resolution
    scale_factor = 1.0 / sift_scale
    matrix[0, 2] *= scale_factor
    matrix[1, 2] *= scale_factor

    # Calculate expanded canvas
    old_h, old_w = old_block.shape[:2]
    new_h, new_w = new_block.shape[:2]

    old_corners = np.array(
        [[0, 0, 1], [old_w, 0, 1], [old_w, old_h, 1], [0, old_h, 1]], dtype=np.float64
    ).T

    transformed_corners = matrix @ old_corners

    old_x_min, old_x_max = np.min(transformed_corners[0]), np.max(transformed_corners[0])
    old_y_min, old_y_max = np.min(transformed_corners[1]), np.max(transformed_corners[1])

    combined_x_min = min(0, old_x_min)
    combined_y_min = min(0, old_y_min)
    combined_x_max = max(new_w, old_x_max)
    combined_y_max = max(new_h, old_y_max)

    offset_x = -combined_x_min if combined_x_min < 0 else 0
    offset_y = -combined_y_min if combined_y_min < 0 else 0

    expanded_w = int(np.ceil(combined_x_max - combined_x_min))
    expanded_h = int(np.ceil(combined_y_max - combined_y_min))

    # Adjust transformation matrix
    adjusted_matrix = matrix.copy()
    adjusted_matrix[0, 2] += offset_x
    adjusted_matrix[1, 2] += offset_y

    # Apply transformation
    aligned_old = apply_transformation(
        old_block, adjusted_matrix, output_shape=(expanded_w, expanded_h)
    )

    # Place new image on expanded canvas
    aligned_new = np.full((expanded_h, expanded_w, 3), 255, dtype=np.uint8)
    new_x_start = int(offset_x)
    new_y_start = int(offset_y)
    aligned_new[new_y_start : new_y_start + new_h, new_x_start : new_x_start + new_w] = new_block

    # Generate overlay
    from scripts.overlay.generate_overlay import generate_overlay

    overlay, deletion, addition = generate_overlay(aligned_old, aligned_new)

    # Save outputs
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "aligned_old": output_dir / f"{block_name}_aligned_old.png",
        "aligned_new": output_dir / f"{block_name}_aligned_new.png",
        "overlay": output_dir / f"{block_name}_overlay.png",
        "deletion": output_dir / f"{block_name}_deletion.png",
        "addition": output_dir / f"{block_name}_addition.png",
    }

    save_image(aligned_old, paths["aligned_old"])
    save_image(aligned_new, paths["aligned_new"])
    save_image(overlay, paths["overlay"])
    save_image(deletion, paths["deletion"])
    save_image(addition, paths["addition"])

    print(f"    Saved alignment outputs for {block_name}")

    return {k: str(v) for k, v in paths.items()}


# ============== Main Processing ==============


def process_single_image(
    image_path: str,
    output_dir: Path,
    client: genai.Client,
) -> SheetMetadata:
    """Process a single image: segment, extract blocks, run OCR on text blocks."""
    print(f"\nProcessing: {image_path}")

    # Load image
    image = load_image(image_path)
    h, w = image.shape[:2]
    print(f"  Image size: {w}x{h}")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Segment image
    segmentation = segment_image(image_path, client)
    print(f"  Found {len(segmentation.blocks)} blocks")

    # Apply 10px padding to all bounding boxes immediately after segmentation
    padded_blocks = pad_blocks(segmentation.blocks, w, h, padding_px=10)

    # Save visualization with padded bounding boxes
    blocks_viz_path = output_dir / "blocks.png"
    draw_blocks_visualization(image, padded_blocks, blocks_viz_path)

    # Create blocks directory for individual crops
    blocks_dir = output_dir / "blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)

    processed_blocks: list[Block] = []
    sheet_number: str | None = None

    for i, block in enumerate(padded_blocks):
        storage_type = get_storage_type(block.block_type)

        print(f"  [{i + 1}/{len(padded_blocks)}] {block.block_type} ({storage_type})")

        # Crop the block (padding already applied to block bbox)
        cropped = crop_block(image, block.bbox)

        # Update block with storage type
        block.storage_type = storage_type

        # Generate unique block name
        block_name = f"{block.block_type}_{i}"

        # Save cropped image for all blocks
        image_path_out = blocks_dir / f"{block_name}.png"
        save_image(cropped, image_path_out)
        block.image_uri = str(image_path_out.relative_to(SCRIPT_DIR))

        # Extract block name for all blocks
        print("    Extracting block name...")
        block.name = extract_block_name(cropped, client)
        if block.name:
            print(f"    Name: {block.name}")

        # Extract identifier and grid callouts for VIEW category blocks
        block_info = BLOCK_TYPE_INFO.get(block.block_type)
        if block_info and block_info.category == BlockCategory.VIEW:
            print("    Extracting view info...")
            view_info = extract_view_info(cropped, client)
            block.identifier = view_info.identifier
            block.has_grid_callouts = view_info.has_grid_callouts
            if block.identifier:
                print(f"    ID: {block.identifier}")
            print(f"    Grid callouts: {block.has_grid_callouts}")

        if storage_type == "text":
            # Run OCR for text blocks
            print("    Running OCR...")
            ocr_text = extract_text_with_ocr(cropped, client)
            block.ocr_text = ocr_text

        # Special handling for title_block
        if block.block_type == BlockType.TITLE_BLOCK:
            print("    Extracting title block info...")
            title_info = extract_title_block_info(cropped, client)
            block.title_block_info = title_info
            if title_info.sheet_number:
                sheet_number = title_info.sheet_number
                print(f"    Sheet number: {sheet_number}")

        processed_blocks.append(block)

    # Convert image path to relative if possible
    try:
        rel_image_path = str(Path(image_path).relative_to(SCRIPT_DIR))
    except ValueError:
        rel_image_path = image_path  # Keep absolute if not under SCRIPT_DIR

    return SheetMetadata(
        image_uri=rel_image_path,
        sheet_number=sheet_number,
        blocks=processed_blocks,
    )


def find_matching_blocks(
    old_metadata: SheetMetadata,
    new_metadata: SheetMetadata,
) -> list[tuple[Block, Block]]:
    """Find matching blocks between old and new sheets for alignment.

    Matching strategy:
    1. First try to match by identifier (if both blocks have identifiers)
    2. If no identifier match, try to match by BlockType only if there's
       exactly one block of that type in both old and new sheets
    """
    matches = []
    matched_old_blocks: set[int] = set()
    matched_new_blocks: set[int] = set()

    # Build index of new blocks by identifier and by type
    new_by_identifier: dict[str, list[tuple[int, Block]]] = {}
    new_by_type: dict[BlockType, list[tuple[int, Block]]] = {}

    for i, block in enumerate(new_metadata.blocks):
        if block.block_type not in ALIGNMENT_BLOCK_TYPES:
            continue
        if block.identifier:
            new_by_identifier.setdefault(block.identifier, []).append((i, block))
        new_by_type.setdefault(block.block_type, []).append((i, block))

    # Pass 1: Match by identifier
    for old_idx, old_block in enumerate(old_metadata.blocks):
        if old_block.block_type not in ALIGNMENT_BLOCK_TYPES:
            continue
        if not old_block.identifier:
            continue

        # Find by identifier
        if old_block.identifier in new_by_identifier:
            candidates = new_by_identifier[old_block.identifier]
            # Use first unmatched candidate
            for new_idx, new_block in candidates:
                if new_idx not in matched_new_blocks:
                    matches.append((old_block, new_block))
                    matched_old_blocks.add(old_idx)
                    matched_new_blocks.add(new_idx)
                    break

    # Pass 2: Match by BlockType (only if unique on both sides)
    old_by_type: dict[BlockType, list[tuple[int, Block]]] = {}
    for i, block in enumerate(old_metadata.blocks):
        if block.block_type not in ALIGNMENT_BLOCK_TYPES:
            continue
        if i in matched_old_blocks:
            continue
        old_by_type.setdefault(block.block_type, []).append((i, block))

    for block_type, old_candidates in old_by_type.items():
        # Skip if not exactly one unmatched old block of this type
        if len(old_candidates) != 1:
            continue

        # Get unmatched new blocks of same type
        new_candidates = [
            (idx, blk)
            for idx, blk in new_by_type.get(block_type, [])
            if idx not in matched_new_blocks
        ]

        # Skip if not exactly one unmatched new block of this type
        if len(new_candidates) != 1:
            continue

        old_idx, old_block = old_candidates[0]
        new_idx, new_block = new_candidates[0]
        matches.append((old_block, new_block))
        matched_old_blocks.add(old_idx)
        matched_new_blocks.add(new_idx)

    return matches


def main():
    parser = argparse.ArgumentParser(
        description="Segment and extract blocks from construction drawings"
    )
    parser.add_argument("--old", default=str(DEFAULT_OLD), help="Path to old image PNG")
    parser.add_argument("--new", default=str(DEFAULT_NEW), help="Path to new image PNG")
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR), help="Output directory")
    parser.add_argument(
        "--overlay", action="store_true", help="Generate alignment and overlay for matching blocks"
    )
    parser.add_argument(
        "--single",
        action="store_true",
        help="Only process the old image (skip new image and overlay)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.old):
        print(f"Error: Old image not found: {args.old}")
        sys.exit(1)
    if not args.single and not os.path.exists(args.new):
        print(f"Error: New image not found: {args.new}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    old_output_dir = output_dir / "old" if not args.single else output_dir
    new_output_dir = output_dir / "new"
    comparison_dir = output_dir / "comparison"

    print("=" * 60)
    print("Construction Drawing Block Segmentation and Extraction")
    print("=" * 60)
    print(f"Old image: {args.old}")
    if not args.single:
        print(f"New image: {args.new}")
    print(f"Output directory: {output_dir}")

    # Initialize Gemini client
    client = genai.Client(api_key=GEMINI_API_KEY)

    # Process old image
    print("\n" + "=" * 60)
    print("Processing OLD image" if not args.single else "Processing image")
    print("=" * 60)
    old_metadata = process_single_image(args.old, old_output_dir, client)
    old_json_path = old_output_dir / "sheet.json"
    with open(old_json_path, "w") as f:
        json.dump(old_metadata.model_dump(), f, indent=2)
    print(f"  Saved: {old_json_path}")

    if not args.single:
        # Process new image
        print("\n" + "=" * 60)
        print("Processing NEW image")
        print("=" * 60)
        new_metadata = process_single_image(args.new, new_output_dir, client)
        new_json_path = new_output_dir / "sheet.json"
        with open(new_json_path, "w") as f:
            json.dump(new_metadata.model_dump(), f, indent=2)
        print(f"  Saved: {new_json_path}")

        # Find matching blocks and perform alignment (only if --overlay flag is set)
        if args.overlay:
            print("\n" + "=" * 60)
            print("Aligning matching blocks")
            print("=" * 60)

            matching_blocks = find_matching_blocks(old_metadata, new_metadata)
            print(f"Found {len(matching_blocks)} matching block pairs for alignment")

            for old_block, new_block in matching_blocks:
                if old_block.image_uri and new_block.image_uri:
                    old_img = load_image(str(SCRIPT_DIR / old_block.image_uri))
                    new_img = load_image(str(SCRIPT_DIR / new_block.image_uri))

                    block_name = old_block.block_type
                    try:
                        align_and_overlay(old_img, new_img, comparison_dir, block_name)
                    except Exception as e:
                        print(f"  Warning: Alignment failed for {block_name}: {e}")

    print("\n" + "=" * 60)
    print("Processing complete!")
    print("=" * 60)
    print("\nOutputs:")
    print(f"  Sheet: {old_json_path}")
    if not args.single:
        print(f"  New sheet: {new_json_path}")
        if args.overlay:
            print(f"  Comparison: {comparison_dir}")

    # Print token usage summary with cost estimates (per 1M tokens)
    model_costs = {
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50, "cached": 0.03},
        "gemini-3-flash-preview": {"input": 0.50, "output": 3.00, "cached": 0.05},
        "gemini-3-pro-preview": {"input": 2.00, "output": 12.00, "cached": 0.20},
    }
    print_token_usage_summary(model_costs)


if __name__ == "__main__":
    main()
