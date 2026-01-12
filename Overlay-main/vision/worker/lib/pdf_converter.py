"""PDF to PNG conversion library supporting multiple rendering engines."""

import io
import os
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF
import pypdfium2 as pdfium
from pydantic import BaseModel, ConfigDict, Field

Engine = Literal["fitz", "pypdfium2"]


class IndexedPage(BaseModel):
    """Represents a single PNG page with its index."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    index: int = Field(..., description="Page number (0-based index)")
    png_bytes: bytes = Field(..., description="PNG image data as bytes")


class IndexedPages(BaseModel):
    """Container for multiple indexed PNG pages."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pages: list[IndexedPage] = Field(default_factory=list, description="List of indexed pages")

    def __len__(self) -> int:
        return len(self.pages)

    def __getitem__(self, index: int) -> bytes:
        for page in self.pages:
            if page.index == index:
                return page.png_bytes
        raise KeyError(f"Page index {index} not found")

    def __contains__(self, index: int) -> bool:
        return any(page.index == index for page in self.pages)

    def keys(self):
        return [page.index for page in self.pages]

    def items(self):
        return [(page.index, page.png_bytes) for page in self.pages]

    def get(self, index: int, default=None) -> bytes:
        try:
            return self[index]
        except KeyError:
            return default

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def indices(self) -> list[int]:
        return sorted(page.index for page in self.pages)

    def get_page(self, index: int) -> IndexedPage:
        for page in self.pages:
            if page.index == index:
                return page
        raise KeyError(f"Page index {index} not found")


def _open_pdf(source, engine: Engine, error_message: str = "Cannot open PDF"):
    """Open a PDF from path or bytes."""
    try:
        if engine == "pypdfium2":
            return pdfium.PdfDocument(source)
        if isinstance(source, bytes):
            return fitz.open(stream=source, filetype="pdf")
        return fitz.open(source)
    except Exception as exc:
        raise ValueError(error_message) from exc


def _render_page(doc, page_num: int, dpi: int, engine: Engine) -> bytes:
    """Render a single page to PNG bytes."""
    scale = dpi / 72.0

    if engine == "pypdfium2":
        page = doc[page_num]
        bitmap = page.render(scale=scale, rotation=0)
        pil_image = bitmap.to_pil()
        buffer = io.BytesIO()
        pil_image.save(buffer, format="PNG")
        return buffer.getvalue()
    else:
        page = doc[page_num]
        mat = fitz.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=mat, annots=True, alpha=False, colorspace=fitz.csRGB)
        return pix.tobytes("png")


def convert_pdf_to_pngs(
    pdf_path: str,
    output_dir: str,
    dpi: int = 300,
    filename_template: str = "page_{index}.png",
    engine: Engine = "pypdfium2",
) -> list[str]:
    """
    Convert all pages of a PDF to individual PNG files.

    Args:
        pdf_path: Path to input PDF file
        output_dir: Directory to save PNG files
        dpi: Resolution in dots per inch (default: 300)
        filename_template: Template for output filenames, {index} replaced with page number
        engine: Rendering engine - "pypdfium2" (recommended) or "fitz"

    Returns:
        List of paths to created PNG files
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not os.access(output_dir, os.W_OK):
        raise OSError(f"Output directory is not writable: {output_dir}")

    doc = _open_pdf(pdf_path, engine)
    png_paths = []

    try:
        for page_num in range(len(doc)):
            png_bytes = _render_page(doc, page_num, dpi, engine)
            output_file = output_path / filename_template.format(index=page_num)

            with open(output_file, "wb") as f:
                f.write(png_bytes)
            png_paths.append(str(output_file))
    finally:
        doc.close()

    return png_paths


def convert_pdf_bytes_to_png_bytes(
    pdf_bytes: bytes,
    dpi: int = 300,
    skip_indices: list[int] = None,
    engine: Engine = "pypdfium2",
) -> IndexedPages:
    """
    Convert PDF bytes to PNG bytes in memory (no disk I/O).

    Args:
        pdf_bytes: PDF file content as bytes
        dpi: Resolution in dots per inch (default: 300)
        skip_indices: List of page indices to skip
        engine: Rendering engine - "pypdfium2" (recommended) or "fitz"

    Returns:
        IndexedPages container with IndexedPage objects
    """
    if not pdf_bytes:
        raise ValueError("Cannot open PDF")

    skip_set = set(skip_indices or [])
    doc = _open_pdf(pdf_bytes, engine, error_message="Cannot open PDF")
    pages_list = []

    try:
        for page_num in range(len(doc)):
            if page_num in skip_set:
                continue

            png_bytes = _render_page(doc, page_num, dpi, engine)
            pages_list.append(IndexedPage(index=page_num, png_bytes=png_bytes))
    finally:
        doc.close()

    return IndexedPages(pages=pages_list)


def get_pdf_page_count(pdf_path: str) -> int:
    """Get the number of pages in a PDF file."""
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    doc = _open_pdf(pdf_path, "pypdfium2", error_message="Cannot read PDF")
    try:
        return len(doc)
    finally:
        doc.close()
