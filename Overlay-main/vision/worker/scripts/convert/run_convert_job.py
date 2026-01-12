#!/usr/bin/env python3
"""
Script to run PDF to PNG conversion job manually.
Usage: uv run python run_convert_job.py <path_to_pdf>
"""

import argparse
import os
import sys
from pathlib import Path

# Add worker root to sys.path to allow imports
current_dir = Path(__file__).resolve().parent
worker_root = current_dir.parent.parent  # scripts/convert -> scripts -> worker
sys.path.append(str(worker_root))

try:
    from lib.pdf_converter import convert_pdf_to_pngs
except ImportError as e:
    print(f"Error importing modules: {e}")
    print(f"sys.path: {sys.path}")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Convert PDF to PNG images.")
    parser.add_argument("pdf_path", help="Path to the input PDF file")
    args = parser.parse_args()

    pdf_path = args.pdf_path
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    # Output directory relative to this script
    output_dir = current_dir / "output"

    # Create filename template using the PDF stem
    pdf_stem = Path(pdf_path).stem
    filename_template = f"{pdf_stem}_page_{{index}}.png"

    print(f"Converting {pdf_path}...")
    print(f"Output directory: {output_dir}")
    print(f"Filename template: {filename_template}")

    try:
        png_paths = convert_pdf_to_pngs(
            pdf_path=pdf_path,
            output_dir=str(output_dir),
            dpi=300,
            filename_template=filename_template,
            engine="pypdfium2",
        )

        print(f"Successfully created {len(png_paths)} PNGs:")
        for path in png_paths:
            print(f"  - {path}")

    except Exception as e:
        print(f"Conversion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
