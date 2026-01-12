#!/usr/bin/env python3
"""
This script loads a PDF and applies a uniform transparency to all its content.
"""

import argparse
import re
from pathlib import Path

import pymupdf


def get_page_content_streams(page: pymupdf.Page) -> list[int]:
    """Return list of xrefs of the page's content streams."""
    key = page.parent.xref_get_key(page.xref, "Contents")
    if not key:
        return []
    if key[0] == "xref":
        return [int(str(key[1]).split()[0])]
    if key[0] == "array":
        arr = key[1]
        return [int(m.group(1)) for m in re.finditer(r"(\d+)\s+0\s+R", arr)]
    return []


def apply_transparency_to_page(page: pymupdf.Page, alpha: float):
    """
    Applies transparency to a single page by adding a graphics state
    and prepending the content stream with a command to use it.
    """
    doc = page.parent

    # 1. Create the ExtGState object for transparency
    gstate_xref = doc.get_new_xref()
    gstate_dict = f"<< /Type /ExtGState /ca {alpha} /CA {alpha} >>"
    doc.update_object(gstate_xref, gstate_dict)

    # 2. Add the new graphics state to the page's resources
    # Get the page's resource dictionary
    res_key = doc.xref_get_key(page.xref, "Resources")
    if not res_key:  # Should not happen for a normal page
        return

    res_xref = int(res_key[1].split()[0])

    # Get the ExtGState dictionary from the resources
    extgstate_key = doc.xref_get_key(res_xref, "ExtGState")

    if not extgstate_key[1]:
        # No ExtGState dict in resources, add one.
        doc.xref_set_key(res_xref, "ExtGState", f"<< /gsT {gstate_xref} 0 R >>")
    else:
        # ExtGState dict exists. Add our new state.
        extgstate_xref = int(extgstate_key[1].split()[0])
        doc.xref_set_key(extgstate_xref, "gsT", f"{gstate_xref} 0 R")

    # 3. Prepend the content stream(s) with the command to use the graphics state
    stream_xrefs = get_page_content_streams(page)
    for stream_xref in stream_xrefs:
        original_bytes = doc.xref_stream(stream_xref) or b""
        # Prepend the command to use our new graphics state
        new_bytes = b"/gsT gs\n" + original_bytes
        doc.update_stream(stream_xref, new_bytes)


def process_pdf(input_path: str, output_path: str, alpha: float):
    """
    Loads a PDF, applies transparency to all pages, and saves it.
    """
    doc = pymupdf.open(input_path)
    print(f"Processing {input_path}...")

    for page in doc:
        apply_transparency_to_page(page, alpha)

    doc.save(output_path, garbage=4, deflate=True, clean=True)
    print(f"Saved transparent PDF to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Apply transparency to a PDF file.")
    parser.add_argument("input_path", type=str, help="Path to the input PDF file.")
    parser.add_argument("output_path", type=str, help="Path to save the output PDF file.")
    parser.add_argument("--alpha", type=float, default=0.5, help="Transparency value (0.0 to 1.0).")
    args = parser.parse_args()

    input_file = Path(args.input_path)
    if not input_file.exists():
        print(f"Error: Input file not found at {args.input_path}")
        return

    process_pdf(args.input_path, args.output_path, args.alpha)


if __name__ == "__main__":
    main()
