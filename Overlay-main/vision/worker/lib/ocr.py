"""Text extraction from PNG images using PyMuPDF with GPT-5-mini OCR fallback.

This module provides text extraction capabilities from PNG images:
1. Primary: PyMuPDF for embedded text extraction
2. Fallback: GPT-5-mini vision API for image-only pages (OCR)
"""

import base64
import logging
import os
from io import BytesIO

import fitz  # PyMuPDF
from openai import OpenAI
from PIL import Image

from utils.log_utils import log_ocr_completed

logger = logging.getLogger(__name__)


def _resolve_openai_api_key(api_key: str | None) -> str:
    # Resolve lazily so unit tests can import this module without a full worker config.
    if api_key:
        return api_key
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key
    raise ValueError("OPENAI_API_KEY is required for vision OCR (or pass api_key).")


def extract_text_words_from_pdf_page(pdf_bytes: bytes, page_index: int) -> list[dict]:
    """Extract words with coordinates from a specific PDF page using PyMuPDF.

    Args:
        pdf_bytes: Raw PDF file data
        page_index: Zero-based page index

    Returns:
        List of word dictionaries with structure:
        [
            {
                "block_no": int,
                "line_no": int,
                "word_no": int,
                "bbox": {"x0": float, "y0": float, "x1": float, "y1": float},
                "text": str
            },
            ...
        ]
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_index >= len(doc):
            logger.error(
                f"[ocr.error] page index {page_index} out of range (PDF has {len(doc)} pages)"
            )
            doc.close()
            return []

        page = doc[page_index]
        words = page.get_text("words")

        # Convert tuples to dictionaries
        words_data = []
        for word in words:
            x0, y0, x1, y1, text, block_no, line_no, word_no = word
            words_data.append(
                {
                    "block_no": block_no,
                    "line_no": line_no,
                    "word_no": word_no,
                    "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                    "text": text,
                }
            )

        doc.close()
        return words_data
    except Exception as e:
        logger.error(
            f"[ocr.error] PyMuPDF word extraction failed for page {page_index}: {type(e).__name__}"
        )
        return []


def get_page_dimensions(pdf_bytes: bytes, page_index: int) -> dict:
    """Get page dimensions (width and height).

    Args:
        pdf_bytes: Raw PDF file data
        page_index: Zero-based page index

    Returns:
        Dictionary with width and height: {"width": float, "height": float}
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_index >= len(doc):
            doc.close()
            return {"width": 0, "height": 0}

        page = doc[page_index]
        dims = {"width": page.rect.width, "height": page.rect.height}
        doc.close()
        return dims
    except Exception as e:
        logger.error(f"[ocr.error] Failed to get page dimensions: {type(e).__name__}")
        return {"width": 0, "height": 0}


def get_page_text_dict(pdf_bytes: bytes, page_index: int) -> dict:
    """Get detailed text dictionary with font information.

    Args:
        pdf_bytes: Raw PDF file data
        page_index: Zero-based page index

    Returns:
        Dictionary from page.get_text("dict") with blocks, lines, spans
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if page_index >= len(doc):
            doc.close()
            return {}

        page = doc[page_index]
        text_dict = page.get_text("dict")
        doc.close()
        return text_dict
    except Exception as e:
        logger.error(f"[ocr.error] Failed to get text dict: {type(e).__name__}")
        return {}


def extract_drawing_no_with_vllm(
    png_bytes: bytes,
    sheet_id: str | None = None,
    sheet_index: int | None = None,
    api_key: str | None = None,
) -> str | None:
    """Use vision LLM API to extract drawing number from image.

    Args:
        png_bytes: Raw PNG image data
        sheet_id: Sheet UUID (for logging)
        sheet_index: Sheet index (for logging)

    Returns:
        Extracted drawing number as text, or None if OCR fails

    This is the fallback method for image-only pages (scanned PDFs, raster images).
    """
    client = OpenAI(api_key=_resolve_openai_api_key(api_key))
    base64_image = base64.b64encode(png_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract the drawing no. (drawing number) from this architectural drawing as markdown. "
                                "Focus on the title block where drawing numbers are typically found. "
                                "Return the drawing number only, no other text."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{base64_image}"},
                        },
                    ],
                }
            ],
        )
        text = response.choices[0].message.content

        # Log OCR completion with character count
        char_count = len(text) if text else 0
        log_ocr_completed(logger, "vision_api", char_count, sheet_id, sheet_index)

        return text
    except Exception as e:
        logger.error(f"[ocr.error] Vision API failed: {type(e).__name__}: {str(e)}")
        return None


def extract_drawing_no_from_bottom_right_region(
    png_bytes: bytes,
    crop_left: float = 0.70,
    crop_top: float = 0.76,
    sheet_id: str | None = None,
    api_key: str | None = None,
) -> str | None:
    """OCR bottom-right region of image to extract drawing number.

    Args:
        png_bytes: Raw PNG image data
        crop_left: Fraction of width to start crop (0.70 = right 30%)
        crop_top: Fraction of height to start crop (0.76 = bottom 24%)
        sheet_id: Sheet UUID (for logging)

    Returns:
        Extracted drawing number from region or None if OCR fails

    This function crops the title block region (typically bottom-right)
    and uses vision API to extract the drawing number.
    """
    try:
        img = Image.open(BytesIO(png_bytes))
        W, H = img.size

        # Crop bottom-right region
        crop_box = (int(W * crop_left), int(H * crop_top), W, H)
        crop = img.crop(crop_box)

        buffer = BytesIO()
        crop.save(buffer, format="PNG")
        crop_bytes = buffer.getvalue()

        return extract_drawing_no_with_vllm(crop_bytes, sheet_id, api_key=api_key)
    except Exception as e:
        logger.error(f"[ocr.error] Failed to crop and OCR region: {type(e).__name__}")
        return None
