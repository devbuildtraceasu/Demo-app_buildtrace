"""Shared fixtures for vision worker tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True, scope="session")
def test_env_vars():
    """Provide required config env vars for tests."""
    env_vars = {
        "DB_HOST": "localhost",
        "DB_USER": "test_user",
        "DB_PASSWORD": "test_password",
        "STORAGE_BUCKET": "test-bucket",
        "PUBSUB_PROJECT_ID": "test-project",
        "OPENAI_API_KEY": "test-openai-key",
    }
    original = {k: os.environ.get(k) for k in env_vars}
    os.environ.update(env_vars)
    yield
    # Restore original values
    for k, v in original.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(autouse=True, scope="session")
def ensure_test_assets():
    """Create missing test assets once per session."""
    try:
        import fitz  # PyMuPDF
        from PIL import Image, ImageDraw
    except Exception:
        yield
        return

    assets_dir = Path(__file__).resolve().parent / "assets"
    pdfs_dir = assets_dir / "pdfs"
    pngs_dir = assets_dir / "pngs"
    overlay_dir = assets_dir / "overlay"

    pdfs_dir.mkdir(parents=True, exist_ok=True)
    pngs_dir.mkdir(parents=True, exist_ok=True)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    sample_pdf = pdfs_dir / "pdf_sample_5_pages.pdf"
    if not sample_pdf.exists():
        doc = fitz.open()
        for index in range(5):
            page = doc.new_page(width=612, height=792)
            page.insert_text((72, 72), f"Lorem ipsum page {index}", fontsize=12)
            page.insert_text((72, 96), f"Sample content for page {index}", fontsize=12)
        doc.save(sample_pdf)
        doc.close()

    sample_png = pngs_dir / "page_0.png"
    if not sample_png.exists():
        img = Image.new("RGB", (600, 400), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((20, 20), "Sample PNG", fill=(0, 0, 0))
        draw.rectangle((50, 80, 250, 180), outline=(0, 0, 0), width=3)
        img.save(sample_png)

    def create_overlay_image(path: Path, offset: int) -> None:
        if path.exists():
            return
        img = Image.new("L", (400, 400), color=0)
        draw = ImageDraw.Draw(img)
        for x in range(20 + offset, 400, 40):
            draw.line((x, 0, x, 400), fill=128, width=2)
        for y in range(20 + offset, 400, 40):
            draw.line((0, y, 400, y), fill=128, width=2)
        draw.rectangle(
            (120 + offset, 120 + offset, 220 + offset, 220 + offset), outline=255, width=3
        )
        draw.ellipse((260 - offset, 80 + offset, 320 - offset, 140 + offset), outline=200, width=3)
        img.save(path)

    create_overlay_image(overlay_dir / "test_old.png", offset=0)
    create_overlay_image(overlay_dir / "test_new.png", offset=8)

    yield
