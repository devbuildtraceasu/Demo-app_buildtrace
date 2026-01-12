#!/usr/bin/env python3
"""Test script to compare different PyMuPDF text extraction methods.

Saves results to JSON files in output/ directory for easy inspection.

Usage:
    python test_text_extraction.py <path_to_pdf> [page_number]

Example:
    python test_text_extraction.py sample.pdf 0
"""

__test__ = False

import base64
import json
import sys
from pathlib import Path

import fitz  # PyMuPDF


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles bytes and other non-serializable types."""

    def default(self, obj):
        if isinstance(obj, bytes):
            # Convert bytes to base64 string for JSON serialization
            return {
                "__type__": "bytes",
                "base64": base64.b64encode(obj).decode("utf-8"),
                "length": len(obj),
            }
        # Let the base class default method raise the TypeError
        return super().default(obj)


def save_json(data, filename: str, output_dir: Path):
    """Save data to JSON file with pretty printing."""
    output_path = output_dir / filename
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, cls=CustomJSONEncoder)
    print(f"✓ Saved: {output_path.name}")


def test_get_text_default(page, output_dir: Path):
    """Test default get_text() - returns plain text."""
    text = page.get_text()
    result = {
        "method": "page.get_text()",
        "description": "Default plain text extraction",
        "length": len(text),
        "text": text,
    }
    save_json(result, "01_get_text_default.json", output_dir)


def test_get_text_blocks(page, output_dir: Path):
    """Test get_text('blocks') - returns list of text blocks with coordinates."""
    blocks = page.get_text("blocks")

    # Convert tuples to dictionaries for better JSON readability
    blocks_data = []
    for block in blocks:
        x0, y0, x1, y1, text, block_no, block_type = block
        blocks_data.append(
            {
                "block_no": block_no,
                "block_type": block_type,
                "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                "text": text,
            }
        )

    result = {
        "method": "page.get_text('blocks')",
        "description": "Text blocks with coordinates",
        "total_blocks": len(blocks),
        "blocks": blocks_data,
    }
    save_json(result, "02_get_text_blocks.json", output_dir)


def test_get_text_words(page, output_dir: Path):
    """Test get_text('words') - returns list of words with coordinates."""
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

    result = {
        "method": "page.get_text('words')",
        "description": "Individual words with coordinates",
        "total_words": len(words),
        "words": words_data,
    }
    save_json(result, "03_get_text_words.json", output_dir)


def test_get_text_dict(page, output_dir: Path):
    """Test get_text('dict') - returns detailed dictionary structure."""
    text_dict = page.get_text("dict")

    result = {
        "method": "page.get_text('dict')",
        "description": "Dictionary structure with full text details",
        "page_dimensions": {"width": text_dict.get("width"), "height": text_dict.get("height")},
        "total_blocks": len(text_dict.get("blocks", [])),
        "data": text_dict,
    }
    save_json(result, "04_get_text_dict.json", output_dir)


def test_get_text_html(page, output_dir: Path):
    """Test get_text('html') - returns HTML formatted text."""
    html = page.get_text("html")

    result = {
        "method": "page.get_text('html')",
        "description": "HTML formatted text",
        "length": len(html),
        "html": html,
    }
    save_json(result, "05_get_text_html.json", output_dir)


def test_get_text_xhtml(page, output_dir: Path):
    """Test get_text('xhtml') - returns XHTML formatted text."""
    xhtml = page.get_text("xhtml")

    result = {
        "method": "page.get_text('xhtml')",
        "description": "XHTML formatted text",
        "length": len(xhtml),
        "xhtml": xhtml,
    }
    save_json(result, "06_get_text_xhtml.json", output_dir)


def test_get_text_xml(page, output_dir: Path):
    """Test get_text('xml') - returns XML formatted text."""
    xml = page.get_text("xml")

    result = {
        "method": "page.get_text('xml')",
        "description": "XML formatted text",
        "length": len(xml),
        "xml": xml,
    }
    save_json(result, "07_get_text_xml.json", output_dir)


def test_get_text_rawdict(page, output_dir: Path):
    """Test get_text('rawdict') - returns raw dictionary with character details."""
    rawdict = page.get_text("rawdict")

    result = {
        "method": "page.get_text('rawdict')",
        "description": "Raw dictionary with character-level details",
        "page_dimensions": {"width": rawdict.get("width"), "height": rawdict.get("height")},
        "total_blocks": len(rawdict.get("blocks", [])),
        "data": rawdict,
    }
    save_json(result, "08_get_text_rawdict.json", output_dir)


def test_get_text_blocks_method(page, output_dir: Path):
    """Test get_text_blocks() method - different from get_text('blocks')."""
    blocks = page.get_text_blocks()

    # Convert tuples to dictionaries
    blocks_data = []
    for block in blocks:
        x0, y0, x1, y1, text, block_no, block_type = block
        blocks_data.append(
            {
                "block_no": block_no,
                "block_type": block_type,
                "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                "text": text,
            }
        )

    result = {
        "method": "page.get_text_blocks()",
        "description": "Alternative blocks method",
        "total_blocks": len(blocks),
        "blocks": blocks_data,
    }
    save_json(result, "09_get_text_blocks_method.json", output_dir)


def test_get_text_words_method(page, output_dir: Path):
    """Test get_text_words() method - different from get_text('words')."""
    words = page.get_text_words()

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

    result = {
        "method": "page.get_text_words()",
        "description": "Alternative words method",
        "total_words": len(words),
        "words": words_data,
    }
    save_json(result, "10_get_text_words_method.json", output_dir)


def test_text_sort_options(page, output_dir: Path):
    """Test get_text() with different sort options."""

    # Default sort
    text_default = page.get_text()

    # Sort with preserve flags
    text_preserve = page.get_text(
        flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE
    )

    # Sort by reading order
    text_sorted = page.get_text("text", sort=True)

    result = {
        "method": "page.get_text() with various flags",
        "description": "Text extraction with different sort and preserve options",
        "variants": {
            "default": {
                "description": "Default (no flags)",
                "length": len(text_default),
                "text": text_default,
            },
            "preserve_ligatures_whitespace": {
                "description": "TEXT_PRESERVE_LIGATURES | TEXT_PRESERVE_WHITESPACE",
                "length": len(text_preserve),
                "text": text_preserve,
            },
            "sorted": {
                "description": "sort=True (reading order)",
                "length": len(text_sorted),
                "text": text_sorted,
            },
        },
    }
    save_json(result, "11_text_sort_options.json", output_dir)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf_path = Path(sys.argv[1])
    page_num = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    if not pdf_path.exists():
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)

    # Create output directory
    script_dir = Path(__file__).parent
    output_dir = script_dir / "output"
    output_dir.mkdir(exist_ok=True)

    print("\nTesting text extraction methods")
    print(f"PDF: {pdf_path}")
    print(f"Page: {page_num}")
    print(f"Output directory: {output_dir}\n")

    # Open PDF
    doc = fitz.open(pdf_path)

    if page_num >= len(doc):
        print(f"Error: Page {page_num} does not exist. PDF has {len(doc)} pages.")
        doc.close()
        sys.exit(1)

    page = doc[page_num]

    # Run all tests
    print("Running tests...")
    test_get_text_default(page, output_dir)
    test_get_text_blocks(page, output_dir)
    test_get_text_words(page, output_dir)
    test_get_text_dict(page, output_dir)
    test_get_text_html(page, output_dir)
    test_get_text_xhtml(page, output_dir)
    test_get_text_xml(page, output_dir)
    test_get_text_rawdict(page, output_dir)
    test_get_text_blocks_method(page, output_dir)
    test_get_text_words_method(page, output_dir)
    test_text_sort_options(page, output_dir)

    # Cleanup
    doc.close()

    print(f"\n{'=' * 80}")
    print(" Testing complete!")
    print(f"{'=' * 80}")
    print(f"\nAll results saved to: {output_dir}")
    print("\nRecommendations for better text ordering:")
    print("  1. Check '02_get_text_blocks.json' - sort blocks by y0, x0 coordinates")
    print("  2. Check '04_get_text_dict.json' - structured text with reading order")
    print("  3. Check '03_get_text_words.json' - reconstruct text by sorting words")
    print("  4. Check '11_text_sort_options.json' - compare different sort flags")


if __name__ == "__main__":
    main()
