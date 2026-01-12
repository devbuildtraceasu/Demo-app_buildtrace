"""Drawing identifier extraction using position-based algorithm with regex matching.

This module extracts drawing identifiers from PDF pages using a sophisticated algorithm that:
1. Analyzes word positions and font sizes from PyMuPDF
2. Prioritizes candidates in the bottom-right title block region
3. Scores candidates by font size (larger = more likely) and position
4. Falls back to vision OCR on bottom-right region if no identifier found

Supports various formats: A-101, A2.1, B-S01, A20-01, S-12A, etc.
"""

import logging
import re
from collections import defaultdict

from lib.ocr import extract_drawing_no_from_bottom_right_region, get_page_text_dict

logger = logging.getLogger(__name__)

# Regex to match drawing names like A-101, A 101, A-344-MB, S-12A, A2.1, A1.1, B-S01, A20-01, etc.
# Supports: traditional (A-101), decimal (A2.1), multi-part prefix (B-S01, A20-01), with letters (S-12A)
DRAWING_RE = re.compile(
    r"\b([A-Z]\d*)[-\s]?(\d{1,4}(?:\.\d{1,2})?|[A-Z]\d{1,4}(?:\.\d{1,2})?)([A-Z])?(?:-([A-Z0-9]{1,8}))?\b"
)


def normalize_dwg(text: str, token_match: re.Match) -> str:
    """Preserve original format (A2.1 stays A2.1, A-101 stays A-101, B-S01 stays B-S01).

    Args:
        text: Original text containing the match
        token_match: Regex match object

    Returns:
        Normalized drawing identifier preserving original format
    """
    prefix = token_match.group(1)  # Group 1: A, B, A20, S10
    number = token_match.group(2)  # Group 2: 101, S01, 2.1
    direct_letter = token_match.group(3)  # Group 3: Single letter after number (A in S-12A)
    hyphen_suffix = token_match.group(4)  # Group 4: Suffix after hyphen (-REV, -MB)

    # Find the original separator between prefix and number
    start_pos = token_match.start()
    number_start = token_match.start(2)
    separator = text[start_pos + len(prefix) : number_start]

    # Build the result preserving the original separator
    result = prefix + separator + number

    # Add direct letter if present (like A in S-12A)
    if direct_letter:
        result += direct_letter

    # Add hyphen suffix if present (like REV in A2.1-REV)
    if hyphen_suffix:
        result += "-" + hyphen_suffix

    return result


def words_to_candidates(
    words: list[dict], page_dims: dict, pdf_bytes: bytes = None, page_index: int = 0
) -> list[tuple]:
    """Extract candidate identifiers from words with positions and font sizes.

    Args:
        words: List of word dicts from extract_text_words_from_pdf_page()
        page_dims: Page dimensions dict with "width" and "height"
        pdf_bytes: Optional PDF bytes to extract font size information
        page_index: Page index for font size extraction

    Returns:
        List of (candidate, cx, cy, font_size) tuples
    """
    cands = []

    # Get font size information if PDF bytes provided
    font_sizes = {}
    font_by_y_position = {}  # Store font size by Y-coordinate for same-line lookup

    if pdf_bytes:
        try:
            blocks = get_page_text_dict(pdf_bytes, page_index).get("blocks", [])
            for block in blocks:
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line["spans"]:
                            text = span["text"]
                            size = span["size"]
                            bbox = span["bbox"]
                            cx = 0.5 * (bbox[0] + bbox[2])
                            cy = 0.5 * (bbox[1] + bbox[3])
                            # Store font size keyed by approximate position and text
                            key = (round(cx), round(cy), text.strip())
                            font_sizes[key] = size
                            # Also store by Y-coordinate (±2 pixels) for same-line lookup
                            y_key = round(cy / 2) * 2  # Round to nearest 2 pixels
                            if y_key not in font_by_y_position or size > font_by_y_position[y_key]:
                                font_by_y_position[y_key] = size
        except Exception as e:
            logger.warning(f"[identifier.font_size] Failed to extract font sizes: {e}")

    # Extract candidates from individual words
    for word in words:
        text = word["text"]
        bbox = word["bbox"]
        x0, y0, x1, y1 = bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]

        for m in DRAWING_RE.finditer(text):
            cand = normalize_dwg(text, m)
            cx = 0.5 * (x0 + x1)
            cy = 0.5 * (y0 + y1)

            # Try to find font size
            font_size = 0
            if font_sizes:
                key = (round(cx), round(cy), text.strip())
                font_size = font_sizes.get(key, 0)
                # If not found, try Y-coordinate lookup
                if font_size == 0 and font_by_y_position:
                    y_key = round(cy / 2) * 2
                    font_size = font_by_y_position.get(y_key, 0)

            cands.append((cand, cx, cy, font_size))

    # Also try line-level text (sometimes identifiers are split across words)
    # Build per-line text and re-scan
    lines = defaultdict(list)
    for word in words:
        bbox = word["bbox"]
        block_no = word["block_no"]
        line_no = word["line_no"]
        text = word["text"]
        x0, y0, x1, y1 = bbox["x0"], bbox["y0"], bbox["x1"], bbox["y1"]
        lines[(block_no, line_no)].append((x0, y0, x1, y1, text))

    for (_blk, _ln), items in lines.items():
        items.sort(key=lambda t: t[0])  # Sort by x position
        line_text = " ".join(t[4] for t in items)
        match = DRAWING_RE.search(line_text)
        if match:
            cand = normalize_dwg(line_text, match)
            # Use overall line bbox center
            lx0 = min(t[0] for t in items)
            ly0 = min(t[1] for t in items)
            lx1 = max(t[2] for t in items)
            ly1 = max(t[3] for t in items)
            cx = 0.5 * (lx0 + lx1)
            cy = 0.5 * (ly0 + ly1)

            # Try to find font size for this line
            font_size = 0
            if font_sizes:
                for item in items:
                    text_item = item[4].strip()
                    item_cx = 0.5 * (item[0] + item[2])
                    item_cy = 0.5 * (item[1] + item[3])
                    key = (round(item_cx), round(item_cy), text_item)
                    if key in font_sizes:
                        font_size = max(font_size, font_sizes[key])
                # If still not found, try Y-coordinate lookup
                if font_size == 0 and font_by_y_position:
                    y_key = round(cy / 2) * 2
                    font_size = font_by_y_position.get(y_key, 0)

            cands.append((cand, cx, cy, font_size))

    return cands


def pick_bottom_right(candidates: list[tuple], page_dims: dict) -> str | None:
    """Choose best candidate based on position and font size.

    Drawing numbers in title blocks are typically:
    1. Largest text in the area (high font size)
    2. Located in bottom-right region

    Scoring:
    - Font size weight: 3x (normalized 0-1, then multiplied by 3)
    - Position weight: 1x each for x and y (normalized 0-1)
    - Total score range: 0-5

    Args:
        candidates: List of (candidate, cx, cy, font_size) tuples
        page_dims: Dictionary with "width" and "height"

    Returns:
        Best candidate identifier or None
    """
    if not candidates:
        return None

    w = page_dims.get("width", 1)
    h = page_dims.get("height", 1)

    # Avoid division by zero
    if w == 0:
        w = 1
    if h == 0:
        h = 1

    # Extract font sizes to normalize
    font_sizes = []
    for item in candidates:
        if len(item) >= 4:
            font_sizes.append(item[3])
        else:
            font_sizes.append(0)

    max_font_size = max(font_sizes) if font_sizes else 1
    if max_font_size == 0:
        max_font_size = 1

    best = None
    best_score = -1e9

    for i, item in enumerate(candidates):
        if len(item) >= 4:
            cand, cx, cy, font_size = item[0], item[1], item[2], item[3]
        else:
            cand, cx, cy = item[0], item[1], item[2]
            font_size = 0

        # Normalize font size (0-1 range)
        norm_font_size = font_size / max_font_size if max_font_size > 0 else 0

        # Position score (0-2 range: 0-1 for x, 0-1 for y)
        position_score = (cx / w) + (cy / h)

        # Combined score: font size is weighted heavily (3x) since drawing numbers are largest
        # Font size: 0-3, Position: 0-2, Total: 0-5
        score = (norm_font_size * 3.0) + position_score

        if score > best_score:
            best_score = score
            best = cand

    return best


def extract_identifier_from_words(
    words: list[dict],
    page_dims: dict,
    png_bytes: bytes = None,
    pdf_bytes: bytes = None,
    sheet_index: int = 0,
    sheet_id: str | None = None,
) -> str | None:
    """Extract drawing identifier from words using position-based algorithm.

    Strategy:
    1. Try extracting from words using position + font size scoring
    2. If not found, OCR bottom-right region of PNG

    Args:
        words: List of word dicts from extract_text_words_from_pdf_page()
        page_dims: Page dimensions dict with "width" and "height"
        png_bytes: Optional PNG bytes for OCR fallback
        pdf_bytes: Optional PDF bytes for font size extraction
        sheet_index: Sheet index for font size extraction
        sheet_id: Sheet UUID for logging

    Returns:
        Drawing identifier or None if not found
    """
    # Try extracting from words
    candidates = words_to_candidates(words, page_dims, pdf_bytes, sheet_index)
    identifier = pick_bottom_right(candidates, page_dims)

    if identifier:
        return identifier

    # Fallback: OCR bottom-right region
    if png_bytes:
        ocr_text = extract_drawing_no_from_bottom_right_region(png_bytes, sheet_id=sheet_id)
        if ocr_text:
            return extract_identifier(ocr_text)

    return None


def extract_identifier(text: str) -> str | None:
    """Extracts identifier from plain text.

    This function is kept for backward compatibility but is less accurate than
    the position-based extraction. Use extract_identifier_from_words() instead.

    Args:
        text: Plain text from page

    Returns:
        Drawing identifier or None
    """
    if not text or not text.strip():
        return None

    match = DRAWING_RE.search(text)
    if match:
        return normalize_dwg(text, match)

    return None
