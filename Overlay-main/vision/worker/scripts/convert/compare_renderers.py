#!/usr/bin/env python3
"""
Compare PDF rendering between PyMuPDF, pypdfium2, and pdf2image (Poppler).
Tests different rendering engines to find the most accurate for architectural drawings.

Usage: uv run python compare_renderers.py <path_to_pdf>

Engines:
- PyMuPDF (MuPDF): Fast, but may render lines faintly
- pypdfium2 (PDFium/Chrome): Chrome-quality rendering, recommended
- pdf2image (Poppler): Linux standard, proven reliability
"""

import argparse
import os
import sys
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

INTERMEDIATES_DIR = Path(__file__).resolve().parent / "intermediates"


def ensure_output_dir():
    INTERMEDIATES_DIR.mkdir(parents=True, exist_ok=True)
    return INTERMEDIATES_DIR


def render_with_pymupdf(pdf_path: str, page_num: int, pdf_stem: str, dpi: int = 300):
    """Render using PyMuPDF/MuPDF (default, no alpha processing)."""
    output_dir = ensure_output_dir()

    doc = fitz.open(pdf_path)
    page = doc[page_num]

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(matrix=mat, annots=True, alpha=False, colorspace=fitz.csRGB)
    path = output_dir / f"{pdf_stem}_p{page_num}_pymupdf_{dpi}dpi.png"
    pix.save(str(path))
    doc.close()

    print(f"  PyMuPDF (MuPDF): {path}")
    return path


def render_with_pymupdf_alpha_boost(
    pdf_path: str, page_num: int, pdf_stem: str, dpi: int = 300, alpha_power: float = 0.2
):
    """
    Render using PyMuPDF with alpha boost and true color preservation.
    Fixes faded lines by unpremultiplying colors and boosting alpha.
    """
    output_dir = ensure_output_dir()

    doc = fitz.open(pdf_path)
    page = doc[page_num]

    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(matrix=mat, annots=True, alpha=True, colorspace=fitz.csRGB)
    img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    doc.close()

    r, g, b, a = img.split()
    r_arr = np.array(r, dtype=np.float32)
    g_arr = np.array(g, dtype=np.float32)
    b_arr = np.array(b, dtype=np.float32)
    a_arr = np.array(a, dtype=np.float32) / 255.0

    # Unpremultiply to get true colors
    mask = a_arr > 0.01
    r_true = np.where(mask, np.clip(r_arr / np.maximum(a_arr, 0.01), 0, 255), 255.0)
    g_true = np.where(mask, np.clip(g_arr / np.maximum(a_arr, 0.01), 0, 255), 255.0)
    b_true = np.where(mask, np.clip(b_arr / np.maximum(a_arr, 0.01), 0, 255), 255.0)

    # Boost alpha
    a_boosted = np.power(a_arr, alpha_power)

    # Composite onto white
    white = 255.0
    r_result = (r_true * a_boosted + white * (1 - a_boosted)).astype(np.uint8)
    g_result = (g_true * a_boosted + white * (1 - a_boosted)).astype(np.uint8)
    b_result = (b_true * a_boosted + white * (1 - a_boosted)).astype(np.uint8)

    result = Image.merge(
        "RGB", (Image.fromarray(r_result), Image.fromarray(g_result), Image.fromarray(b_result))
    )

    power_str = str(alpha_power).replace(".", "")
    path = output_dir / f"{pdf_stem}_p{page_num}_pymupdf_alphaboost_{power_str}_{dpi}dpi.png"
    result.save(str(path))

    print(f"  PyMuPDF (alpha boost {alpha_power}): {path}")
    return path


def render_with_pypdfium2(pdf_path: str, page_num: int, pdf_stem: str, dpi: int = 300):
    """Render using pypdfium2 (PDFium/Chrome engine)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("  pypdfium2: SKIPPED (not installed, run: uv add pypdfium2)")
        return None

    output_dir = ensure_output_dir()

    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[page_num]

    # Scale factor: 72 DPI is base, so scale = dpi / 72
    scale = dpi / 72.0
    bitmap = page.render(scale=scale, rotation=0)
    pil_image = bitmap.to_pil()

    path = output_dir / f"{pdf_stem}_p{page_num}_pypdfium2_{dpi}dpi.png"
    pil_image.save(str(path))

    print(f"  pypdfium2 (PDFium/Chrome): {path}")
    return path


def render_with_pdf2image(pdf_path: str, page_num: int, pdf_stem: str, dpi: int = 300):
    """Render using pdf2image (Poppler engine)."""
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("  pdf2image: SKIPPED (not installed, run: uv add pdf2image)")
        return None

    output_dir = ensure_output_dir()

    try:
        # Convert single page (first_page and last_page are 1-indexed)
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            first_page=page_num + 1,
            last_page=page_num + 1,
        )

        if images:
            path = output_dir / f"{pdf_stem}_p{page_num}_pdf2image_{dpi}dpi.png"
            images[0].save(str(path), "PNG")
            print(f"  pdf2image (Poppler): {path}")
            return path
        else:
            print("  pdf2image: FAILED (no images returned)")
            return None

    except Exception as e:
        print(f"  pdf2image: FAILED ({e})")
        print("    Note: Requires Poppler installed (brew install poppler)")
        return None


def compare_file_sizes(files: list):
    """Compare file sizes to see content differences."""
    print("\n=== File Size Comparison ===")
    for name, path in files:
        if path and os.path.exists(path):
            size = os.path.getsize(path)
            print(f"  {name}: {size:,} bytes")
        else:
            print(f"  {name}: N/A")


def main():
    parser = argparse.ArgumentParser(
        description="Compare PDF rendering engines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Engines tested:
  PyMuPDF (MuPDF)     - Fast, may render faintly
  PyMuPDF + alpha     - With alpha boost fix
  pypdfium2 (PDFium)  - Chrome-quality, recommended
  pdf2image (Poppler) - Linux standard, reliable

Install dependencies:
  uv add pypdfium2 pdf2image
  brew install poppler  # Required for pdf2image
        """,
    )
    parser.add_argument("pdf_path", help="Path to the input PDF file")
    parser.add_argument("--page", type=int, default=0, help="Page number to render (0-based)")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for rendering")
    parser.add_argument(
        "--alpha-power", type=float, default=0.2, help="Alpha boost power (lower = stronger)"
    )
    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"Error: File not found: {args.pdf_path}")
        sys.exit(1)

    pdf_stem = Path(args.pdf_path).stem
    print(f"\n{'=' * 60}")
    print("Comparing PDF Rendering Engines")
    print(f"{'=' * 60}")
    print(f"Input: {args.pdf_path}")
    print(f"Page: {args.page}, DPI: {args.dpi}")
    print(f"Output: {INTERMEDIATES_DIR}\n")

    files = []

    # PyMuPDF default
    # print("[1/4] PyMuPDF (MuPDF engine)")
    # path = render_with_pymupdf(args.pdf_path, args.page, pdf_stem, args.dpi)
    # files.append(("PyMuPDF (default)", path))

    # # PyMuPDF with alpha boost
    # print(f"\n[2/4] PyMuPDF + Alpha Boost (power={args.alpha_power})")
    # path = render_with_pymupdf_alpha_boost(args.pdf_path, args.page, pdf_stem, args.dpi, args.alpha_power)
    # files.append((f"PyMuPDF (alpha boost)", path))

    # pypdfium2
    print("\n[3/4] pypdfium2 (PDFium/Chrome engine)")
    path = render_with_pypdfium2(args.pdf_path, args.page, pdf_stem, args.dpi)
    files.append(("pypdfium2 (PDFium)", path))

    # pdf2image
    # print("\n[4/4] pdf2image (Poppler engine)")
    # path = render_with_pdf2image(args.pdf_path, args.page, pdf_stem, args.dpi)
    # files.append(("pdf2image (Poppler)", path))

    # Compare
    compare_file_sizes(files)

    print(f"\n{'=' * 60}")
    print("Done! Compare the output images visually.")


if __name__ == "__main__":
    main()
