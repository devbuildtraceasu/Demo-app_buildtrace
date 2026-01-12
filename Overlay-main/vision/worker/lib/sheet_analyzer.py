"""Sheet-level block segmentation and metadata extraction using Gemini."""

from __future__ import annotations

import io
import json
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from enum import Enum

from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from PIL import Image
from pydantic import BaseModel, Field

from clients.gemini import GeminiModel
from lib.llm_usage import track_usage
from utils.log_utils import log_phase

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 5
BASE_DELAY = 10.0  # seconds
MAX_DELAY = 120.0  # seconds
JITTER_FACTOR = 0.5  # adds up to 50% random jitter

# Parallelization configuration
MAX_PARALLEL_BLOCKS = 5


class BlockCategory(str, Enum):
    VIEW = "view"
    SYMBOL = "symbol"
    TABULAR = "tabular"
    NOTES = "notes"
    METADATA = "metadata"


class BlockTypeInfo(BaseModel):
    storage_type: str
    category: BlockCategory
    description: str


BLOCK_TYPE_INFO: dict[str, BlockTypeInfo] = {
    # View blocks
    "plan": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Plan view: floor plan, ceiling plan, roof plan, site plan, etc.",
    ),
    "elevation": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Vertical orthographic view of exterior or interior walls",
    ),
    "section": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Vertical cut through building showing internal construction layers",
    ),
    "detail": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.VIEW,
        description="Enlarged view of construction assembly, connection, or component",
    ),
    # Symbol blocks
    "legend": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Key explaining symbols, materials, finishes, flooring, patterns or matching tags",
    ),
    "diagram": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Schematic representation: riser, single-line, or flow diagram",
    ),
    "key_plan": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Reference plan indicating location of the current view",
    ),
    "north_arrow": BlockTypeInfo(
        storage_type="image",
        category=BlockCategory.SYMBOL,
        description="Orientation symbol showing north direction",
    ),
    # Tabular blocks
    "schedule": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.TABULAR,
        description="Tabular schedules (doors, finishes, equipment, etc.)",
    ),
    "revision_history": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.TABULAR,
        description="Revision table / revision history",
    ),
    "project_info": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.TABULAR,
        description="Project information table",
    ),
    # Notes blocks
    "general_notes": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="General notes section",
    ),
    "key_notes": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Key notes or legends keyed to views",
    ),
    "sheet_notes": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Sheet-specific notes",
    ),
    "abbreviations": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Abbreviation list",
    ),
    "code_references": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Code references and compliance notes",
    ),
    "notes": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.NOTES,
        description="Notes or callouts",
    ),
    # Metadata blocks
    "title_block": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.METADATA,
        description="A single unique title block containing the sheet number (drawing number), drawing title (optional), project name (optional), date (optional), revision (optional), and scale (optional), usually located in the bottom right corner of the sheet",
    ),
    "consultants": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.METADATA,
        description="Consultant listings or seals",
    ),
    "seals": BlockTypeInfo(
        storage_type="text",
        category=BlockCategory.METADATA,
        description="Professional seals or stamps",
    ),
}


def _build_block_types_prompt() -> str:
    image_lines: list[str] = []
    text_lines: list[str] = []
    for block_type, info in BLOCK_TYPE_INFO.items():
        line = f"- {block_type}: {info.description}"
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

IMPORTANT INSTRUCTIONS:
1. Return coordinates as xmin, ymin, xmax, ymax normalized to 1000.
2. Be sure to separate blocks that are distinct rectangular regions.
3. Bounding boxes should not fully encompass each other, but they can partially overlap. If boxes are completely enclosed in another box, they should be separated or merged.
4. Bounding boxes should be expanded to include all relevant grid lines and grid reference callouts (grid bubbles or markers containing a letter, number or decimal), titles and labels. Do not cut off any grid line reference callouts.
5. Do not cut off parts of a text, drawing, diagram, plan or any content. Expand the box to fully encompass the unit of content.
"""


OCR_PROMPT = """You are an expert construction drawing analyzer. Extract all text from this image and format as clean Markdown.
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


BLOCK_INFO_PROMPT = """You are an expert construction drawing analyzer. Extract info about this construction drawing block.

1. NAME: The title/label of this block, typically found below the content for views, or above for tables/notes.
   Examples: "FIRST FLOOR PLAN", "DOOR SCHEDULE", "GENERAL NOTES", "EAST ELEVATION"
   Return null if not found.

2. DESCRIPTION: A brief (1 sentence) description of what this block contains.
   Examples: "Floor plan showing room layouts and dimensions", "Table of door specifications"

Return both fields."""


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


class BoundingBox(BaseModel):
    """Bounding box coordinates normalized to 0-1000 scale."""

    xmin: int = Field(description="Left X coordinate (0-1000)")
    ymin: int = Field(description="Top Y coordinate (0-1000)")
    xmax: int = Field(description="Right X coordinate (0-1000)")
    ymax: int = Field(description="Bottom Y coordinate (0-1000)")


class SegmentationBlock(BaseModel):
    """A block/region on a construction drawing sheet."""

    block_type: str = Field(description="Block type")
    bbox: BoundingBox = Field(description="Bounding box coordinates")


class SegmentationResult(BaseModel):
    """Result of block segmentation."""

    blocks: list[SegmentationBlock] = Field(description="List of detected blocks")


class TitleBlockInfo(BaseModel):
    """Extracted title block information."""

    sheet_number: str | None = Field(
        default=None, description="Sheet number (also called drawing number, e.g., A101, S-201)"
    )
    sheet_title: str | None = Field(
        default=None, description="Sheet title (also called drawing title)"
    )
    project_name: str | None = Field(default=None, description="Project name")
    date: str | None = Field(default=None, description="Date on drawing")
    revision: str | None = Field(default=None, description="Current revision")
    scale: str | None = Field(default=None, description="Drawing scale")


class BlockInfoResponse(BaseModel):
    """Response model for block name and description extraction."""

    name: str | None = Field(default=None, description="Block name/title")
    description: str = Field(description="Brief description of block content")


class ViewInfoResponse(BaseModel):
    """Response model for view info extraction (identifier + grid callouts)."""

    identifier: str | None = Field(default=None, description="Block identifier")
    has_grid_callouts: bool = Field(default=False, description="Whether view has grid callouts")


class AnalyzedBlock(BaseModel):
    """A fully analyzed block with extracted metadata."""

    block_type: str
    bbox: BoundingBox
    description: str
    storage_type: str
    name: str | None
    ocr_text: str | None
    crop_bytes: bytes
    identifier: str | None = None
    has_grid_callouts: bool | None = None


class SheetAnalysisResult(BaseModel):
    """Result of full sheet analysis."""

    blocks: list[AnalyzedBlock]
    metadata: dict


def _calculate_backoff(attempt: int) -> float:
    """Calculate exponential backoff delay with jitter."""
    delay = min(BASE_DELAY * (2**attempt), MAX_DELAY)
    jitter = delay * JITTER_FACTOR * random.random()
    return delay + jitter


def _llm_extract(
    image_bytes: bytes,
    prompt: str,
    client: genai.Client,
    response_schema: type[BaseModel] | None = None,
    media_resolution: str = "MEDIA_RESOLUTION_MEDIUM",
    model: str = GeminiModel.GEMINI_2_5_FLASH,
    thinking_level: str | None = None,
    log_response: bool = False,
) -> BaseModel | str:
    config_kwargs: dict[str, object] = {
        "temperature": 0.0,
        "media_resolution": media_resolution,
    }
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema
    if thinking_level is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level=thinking_level)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(mime_type="image/png", data=image_bytes),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(**config_kwargs),
            )

            # Track token usage for cost aggregation
            track_usage(model, response.usage_metadata)

            if log_response:
                logger.debug(f"  LLM response: {response.text}")

            if response_schema is not None:
                result_dict = json.loads(response.text)
                return response_schema(**result_dict)
            return response.text.strip()

        except (genai_errors.ServerError, genai_errors.ClientError) as e:
            last_error = e
            # ServerError (503): model overloaded
            # ClientError (429): rate limit exceeded
            if attempt < MAX_RETRIES - 1:
                delay = _calculate_backoff(attempt)
                logger.warning(
                    f"Gemini API error (attempt {attempt + 1}/{MAX_RETRIES}): {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.error(f"Gemini API error after {MAX_RETRIES} attempts: {e}")
                raise

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in _llm_extract")


def _pad_bbox(bbox: BoundingBox, width: int, height: int, padding_px: int) -> BoundingBox:
    x1 = int(bbox.xmin * width / 1000)
    y1 = int(bbox.ymin * height / 1000)
    x2 = int(bbox.xmax * width / 1000)
    y2 = int(bbox.ymax * height / 1000)

    x1 = max(0, x1 - padding_px)
    y1 = max(0, y1 - padding_px)
    x2 = min(width, x2 + padding_px)
    y2 = min(height, y2 + padding_px)

    return BoundingBox(
        xmin=int(x1 * 1000 / width),
        ymin=int(y1 * 1000 / height),
        xmax=int(x2 * 1000 / width),
        ymax=int(y2 * 1000 / height),
    )


def _crop_bytes(image: Image.Image, bbox: BoundingBox) -> bytes:
    width, height = image.size
    x1 = int(bbox.xmin * width / 1000)
    y1 = int(bbox.ymin * height / 1000)
    x2 = int(bbox.xmax * width / 1000)
    y2 = int(bbox.ymax * height / 1000)
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(width, x2), min(height, y2)
    crop = image.crop((x1, y1, x2, y2))
    buffer = io.BytesIO()
    crop.save(buffer, format="PNG")
    return buffer.getvalue()


def _extract_title_block_info(
    image: Image.Image,
    title_blocks: list[tuple[SegmentationBlock, BoundingBox]],
    client: genai.Client,
    max_canvas_dimension: int = 2000,
) -> TitleBlockInfo | None:
    """Extract title block info from one or more title blocks.

    If multiple title blocks exist:
    - Combines them on a single canvas if combined size <= max_canvas_dimension
    - Otherwise uses the block closest to the bottom-right corner
    """
    if not title_blocks:
        return None

    width, height = image.size

    if len(title_blocks) == 1:
        # Single title block - just use it directly
        _, padded_bbox = title_blocks[0]
        crop_bytes = _crop_bytes(image, padded_bbox)
    else:
        # Multiple title blocks - calculate combined canvas size
        crops_with_positions: list[tuple[Image.Image, int, int, int, int]] = []
        min_x, min_y = float("inf"), float("inf")
        max_x, max_y = 0, 0

        for _, padded_bbox in title_blocks:
            x1 = int(padded_bbox.xmin * width / 1000)
            y1 = int(padded_bbox.ymin * height / 1000)
            x2 = int(padded_bbox.xmax * width / 1000)
            y2 = int(padded_bbox.ymax * height / 1000)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width, x2), min(height, y2)

            min_x, min_y = min(min_x, x1), min(min_y, y1)
            max_x, max_y = max(max_x, x2), max(max_y, y2)

            crop = image.crop((x1, y1, x2, y2))
            crops_with_positions.append((crop, x1, y1, x2, y2))

        combined_width = int(max_x - min_x)
        combined_height = int(max_y - min_y)

        if combined_width > max_canvas_dimension or combined_height > max_canvas_dimension:
            # Canvas too large - use block closest to bottom-right corner
            best_block = None
            best_distance = float("inf")
            for raw_block, padded_bbox in title_blocks:
                # Calculate center of block
                cx = (padded_bbox.xmin + padded_bbox.xmax) / 2
                cy = (padded_bbox.ymin + padded_bbox.ymax) / 2
                # Distance from bottom-right (1000, 1000 in normalized coords)
                distance = ((1000 - cx) ** 2 + (1000 - cy) ** 2) ** 0.5
                if distance < best_distance:
                    best_distance = distance
                    best_block = padded_bbox

            crop_bytes = _crop_bytes(image, best_block)  # type: ignore[arg-type]
        else:
            # Combine all title blocks on a single canvas
            canvas = Image.new("RGB", (combined_width, combined_height), (255, 255, 255))
            for crop, x1, y1, x2, y2 in crops_with_positions:
                paste_x = int(x1 - min_x)
                paste_y = int(y1 - min_y)
                canvas.paste(crop, (paste_x, paste_y))

            buffer = io.BytesIO()
            canvas.save(buffer, format="PNG")
            crop_bytes = buffer.getvalue()

    tb_result = _llm_extract(
        crop_bytes,
        TITLE_BLOCK_PROMPT,
        client,
        response_schema=TitleBlockInfo,
        model=GeminiModel.GEMINI_2_5_FLASH,
    )
    return tb_result if isinstance(tb_result, TitleBlockInfo) else None


def _extract_single_block(
    idx: int,
    raw_block: SegmentationBlock,
    image: Image.Image,
    client: genai.Client,
    padding_px: int,
    block_count: int,
) -> tuple[int, AnalyzedBlock]:
    """Extract data for a single block. Returns (index, block) for ordering."""
    logger.debug(f"  Block {idx + 1}/{block_count}: {raw_block.block_type}")
    width, height = image.size
    padded_bbox = _pad_bbox(raw_block.bbox, width, height, padding_px)
    crop_bytes = _crop_bytes(image, padded_bbox)

    storage_type = BLOCK_TYPE_INFO.get(
        raw_block.block_type,
        BlockTypeInfo(
            storage_type="image",
            category=BlockCategory.VIEW,
            description="",
        ),
    ).storage_type

    name: str | None = None
    description: str = ""
    ocr_text: str | None = None
    identifier: str | None = None
    has_grid_callouts: bool | None = None

    # Extract name and description together
    block_info_result = _llm_extract(
        crop_bytes,
        BLOCK_INFO_PROMPT,
        client,
        response_schema=BlockInfoResponse,
        model=GeminiModel.GEMINI_2_5_FLASH,
    )
    if isinstance(block_info_result, BlockInfoResponse):
        name = block_info_result.name
        description = block_info_result.description

    # Extract identifier and grid callouts for VIEW category blocks
    block_type_info = BLOCK_TYPE_INFO.get(raw_block.block_type)
    if block_type_info and block_type_info.category == BlockCategory.VIEW:
        view_info_result = _llm_extract(
            crop_bytes,
            VIEW_INFO_PROMPT,
            client,
            response_schema=ViewInfoResponse,
            model=GeminiModel.GEMINI_2_5_FLASH,
        )
        if isinstance(view_info_result, ViewInfoResponse):
            identifier = view_info_result.identifier
            has_grid_callouts = view_info_result.has_grid_callouts

    if storage_type == "text":
        ocr_result = _llm_extract(
            crop_bytes,
            OCR_PROMPT,
            client,
            response_schema=None,
            model=GeminiModel.GEMINI_2_5_FLASH,
        )
        if isinstance(ocr_result, str):
            ocr_text = ocr_result.strip()

    return (
        idx,
        AnalyzedBlock(
            block_type=raw_block.block_type,
            bbox=padded_bbox,
            description=description,
            storage_type=storage_type,
            name=name,
            ocr_text=ocr_text,
            crop_bytes=crop_bytes,
            identifier=identifier,
            has_grid_callouts=has_grid_callouts,
        ),
    )


def analyze_sheet(
    png_bytes: bytes,
    client: genai.Client,
    padding_px: int = 10,
) -> SheetAnalysisResult:
    image = Image.open(io.BytesIO(png_bytes)).convert("RGB")
    width, height = image.size

    with log_phase(logger, "Segment blocks"):
        segmentation = _llm_extract(
            png_bytes,
            SEGMENTATION_PROMPT,
            client,
            response_schema=SegmentationResult,
            media_resolution="MEDIA_RESOLUTION_MEDIUM",
            model=GeminiModel.GEMINI_3_PRO,
            thinking_level="low",
        )

    # First pass: collect all title blocks
    title_blocks: list[tuple[SegmentationBlock, BoundingBox]] = []
    for raw_block in segmentation.blocks:  # type: ignore[union-attr]
        if raw_block.block_type == "title_block":
            padded_bbox = _pad_bbox(raw_block.bbox, width, height, padding_px)
            title_blocks.append((raw_block, padded_bbox))

    # Extract title block info from combined/selected title blocks
    title_block_info: TitleBlockInfo | None = None
    if title_blocks:
        with log_phase(logger, "Extract title block"):
            title_block_info = _extract_title_block_info(image, title_blocks, client)

    block_count = len(segmentation.blocks)  # type: ignore[union-attr]

    with log_phase(logger, f"Extract block data ({block_count} blocks, parallel)"):
        indexed_blocks: list[tuple[int, AnalyzedBlock]] = []
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_BLOCKS) as executor:
            futures = {
                executor.submit(
                    _extract_single_block,
                    idx,
                    raw_block,
                    image,
                    client,
                    padding_px,
                    block_count,
                ): idx
                for idx, raw_block in enumerate(segmentation.blocks)  # type: ignore[union-attr]
            }
            for future in as_completed(futures):
                idx, block = future.result()
                indexed_blocks.append((idx, block))

        # Sort by original index to maintain order
        indexed_blocks.sort(key=lambda x: x[0])
        blocks = [block for _, block in indexed_blocks]

    metadata = {
        "block_count": len(blocks),
        "title_block": title_block_info.model_dump() if title_block_info else None,
    }
    return SheetAnalysisResult(blocks=blocks, metadata=metadata)
