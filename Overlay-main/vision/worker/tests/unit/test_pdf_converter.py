"""Unit tests for PDF to PNG conversion library."""

from pathlib import Path

import pytest
from PIL import Image

from lib.pdf_converter import (
    IndexedPage,
    IndexedPages,
    convert_pdf_bytes_to_png_bytes,
    get_pdf_page_count,
)

# Path to test assets
ASSETS_DIR = Path(__file__).parent.parent / "assets"
PDFS_DIR = ASSETS_DIR / "pdfs"
SAMPLE_PDF = PDFS_DIR / "pdf_sample_5_pages.pdf"


@pytest.fixture
def sample_pdf_bytes():
    """Load sample PDF as bytes."""
    with open(SAMPLE_PDF, "rb") as f:
        return f.read()


class TestGetPdfPageCount:
    """Tests for get_pdf_page_count function."""

    def test_returns_correct_page_count(self):
        """Should return 5 for the sample 5-page PDF."""
        page_count = get_pdf_page_count(str(SAMPLE_PDF))
        assert page_count == 5

    def test_raises_file_not_found_for_missing_file(self):
        """Should raise FileNotFoundError for non-existent PDF."""
        with pytest.raises(FileNotFoundError) as exc_info:
            get_pdf_page_count("/nonexistent/path/file.pdf")
        assert "PDF file not found" in str(exc_info.value)

    def test_raises_value_error_for_corrupted_pdf(self, tmp_path):
        """Should raise ValueError for corrupted/invalid PDF."""
        corrupted_pdf = tmp_path / "corrupted.pdf"
        corrupted_pdf.write_text("This is not a valid PDF file")

        with pytest.raises(ValueError) as exc_info:
            get_pdf_page_count(str(corrupted_pdf))
        assert "Cannot read PDF" in str(exc_info.value)

    def test_raises_error_for_empty_file(self, tmp_path):
        """Should raise ValueError for empty files."""
        empty_file = tmp_path / "empty.pdf"
        empty_file.write_bytes(b"")

        with pytest.raises(ValueError) as exc_info:
            get_pdf_page_count(str(empty_file))
        assert "Cannot read PDF" in str(exc_info.value)


class TestIndexedPage:
    """Tests for IndexedPage model."""

    def test_creates_indexed_page_with_valid_data(self):
        """Should create IndexedPage with index and png_bytes."""
        png_bytes = b"\x89PNG\r\n\x1a\n"  # PNG header
        page = IndexedPage(index=0, png_bytes=png_bytes)

        assert page.index == 0
        assert page.png_bytes == png_bytes

    def test_validates_required_fields(self):
        """Should require both index and png_bytes fields."""
        with pytest.raises(Exception):  # Pydantic ValidationError
            IndexedPage(index=0)  # Missing png_bytes

        with pytest.raises(Exception):  # Pydantic ValidationError
            IndexedPage(png_bytes=b"data")  # Missing index


class TestIndexedPages:
    """Tests for IndexedPages container."""

    def test_creates_empty_container(self):
        """Should create empty IndexedPages container."""
        container = IndexedPages()
        assert len(container) == 0
        assert container.page_count == 0
        assert container.indices == []

    def test_creates_container_with_pages(self):
        """Should create IndexedPages with list of pages."""
        pages = [
            IndexedPage(index=0, png_bytes=b"page0"),
            IndexedPage(index=1, png_bytes=b"page1"),
            IndexedPage(index=2, png_bytes=b"page2"),
        ]
        container = IndexedPages(pages=pages)

        assert len(container) == 3
        assert container.page_count == 3
        assert container.indices == [0, 1, 2]

    def test_getitem_returns_png_bytes(self):
        """Should return PNG bytes for given index."""
        pages = [
            IndexedPage(index=0, png_bytes=b"page0"),
            IndexedPage(index=2, png_bytes=b"page2"),
        ]
        container = IndexedPages(pages=pages)

        assert container[0] == b"page0"
        assert container[2] == b"page2"

    def test_getitem_raises_key_error_for_missing_index(self):
        """Should raise KeyError for non-existent index."""
        pages = [IndexedPage(index=0, png_bytes=b"page0")]
        container = IndexedPages(pages=pages)

        with pytest.raises(KeyError):
            _ = container[1]

    def test_contains_checks_index_existence(self):
        """Should check if index exists in container."""
        pages = [
            IndexedPage(index=0, png_bytes=b"page0"),
            IndexedPage(index=2, png_bytes=b"page2"),
        ]
        container = IndexedPages(pages=pages)

        assert 0 in container
        assert 2 in container
        assert 1 not in container

    def test_keys_returns_all_indices(self):
        """Should return list of all page indices."""
        pages = [
            IndexedPage(index=0, png_bytes=b"page0"),
            IndexedPage(index=2, png_bytes=b"page2"),
            IndexedPage(index=1, png_bytes=b"page1"),
        ]
        container = IndexedPages(pages=pages)

        keys = container.keys()
        assert set(keys) == {0, 1, 2}

    def test_items_returns_index_bytes_pairs(self):
        """Should return (index, png_bytes) pairs."""
        pages = [
            IndexedPage(index=0, png_bytes=b"page0"),
            IndexedPage(index=1, png_bytes=b"page1"),
        ]
        container = IndexedPages(pages=pages)

        items = container.items()
        assert (0, b"page0") in items
        assert (1, b"page1") in items

    def test_get_with_default(self):
        """Should return PNG bytes or default value."""
        pages = [IndexedPage(index=0, png_bytes=b"page0")]
        container = IndexedPages(pages=pages)

        assert container.get(0) == b"page0"
        assert container.get(1) is None
        assert container.get(1, b"default") == b"default"

    def test_indices_returns_sorted_list(self):
        """Should return sorted list of indices."""
        pages = [
            IndexedPage(index=2, png_bytes=b"page2"),
            IndexedPage(index=0, png_bytes=b"page0"),
            IndexedPage(index=1, png_bytes=b"page1"),
        ]
        container = IndexedPages(pages=pages)

        assert container.indices == [0, 1, 2]

    def test_get_page_returns_indexed_page_object(self):
        """Should return IndexedPage object by index."""
        page0 = IndexedPage(index=0, png_bytes=b"page0")
        page1 = IndexedPage(index=1, png_bytes=b"page1")
        container = IndexedPages(pages=[page0, page1])

        retrieved_page = container.get_page(0)
        assert retrieved_page.index == 0
        assert retrieved_page.png_bytes == b"page0"

    def test_get_page_raises_key_error_for_missing_index(self):
        """Should raise KeyError for non-existent index."""
        container = IndexedPages(pages=[IndexedPage(index=0, png_bytes=b"page0")])

        with pytest.raises(KeyError):
            container.get_page(1)


class TestConvertPdfBytesToPngBytes:
    """Tests for convert_pdf_bytes_to_png_bytes function."""

    def test_converts_all_pages_successfully(self, sample_pdf_bytes):
        """Should convert all 5 pages of sample PDF to PNG bytes."""
        indexed_pages = convert_pdf_bytes_to_png_bytes(sample_pdf_bytes, dpi=100)

        # Should return 5 pages
        assert indexed_pages.page_count == 5
        assert len(indexed_pages) == 5

        # All pages should be indexed 0-4
        assert indexed_pages.indices == [0, 1, 2, 3, 4]

        # Each page should have PNG bytes
        for i in range(5):
            assert i in indexed_pages
            png_bytes = indexed_pages[i]
            assert isinstance(png_bytes, bytes)
            assert len(png_bytes) > 0
            # PNG files start with specific magic bytes
            assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    def test_default_dpi_is_300(self, sample_pdf_bytes):
        """Should use 300 DPI as default when dpi parameter is omitted."""
        indexed_pages = convert_pdf_bytes_to_png_bytes(sample_pdf_bytes)

        assert indexed_pages.page_count == 5
        # PNG should be reasonably sized for 300 DPI
        assert len(indexed_pages[0]) > 10000  # At least 10KB

    def test_lower_dpi_produces_smaller_files(self, sample_pdf_bytes):
        """Should produce smaller PNG bytes with lower DPI."""
        pages_300dpi = convert_pdf_bytes_to_png_bytes(sample_pdf_bytes, dpi=300)
        pages_72dpi = convert_pdf_bytes_to_png_bytes(sample_pdf_bytes, dpi=72)

        # 72 DPI should produce smaller files than 300 DPI
        assert len(pages_72dpi[0]) < len(pages_300dpi[0])

    def test_raises_value_error_for_corrupted_pdf(self):
        """Should raise ValueError for corrupted/invalid PDF bytes."""
        corrupted_bytes = b"This is not a valid PDF file"

        with pytest.raises(ValueError) as exc_info:
            convert_pdf_bytes_to_png_bytes(corrupted_bytes)
        assert "Cannot open PDF" in str(exc_info.value)

    def test_raises_value_error_for_empty_bytes(self):
        """Should raise ValueError for empty bytes."""
        with pytest.raises(ValueError) as exc_info:
            convert_pdf_bytes_to_png_bytes(b"")
        assert "Cannot open PDF" in str(exc_info.value)

    def test_png_bytes_are_valid_images(self, sample_pdf_bytes):
        """Should produce valid PNG bytes that can be opened by PIL."""
        from io import BytesIO

        indexed_pages = convert_pdf_bytes_to_png_bytes(sample_pdf_bytes, dpi=100)

        # All PNG bytes should be valid and openable
        for i in range(indexed_pages.page_count):
            png_bytes = indexed_pages[i]
            img = Image.open(BytesIO(png_bytes))
            assert img.format == "PNG"
            assert img.width > 0
            assert img.height > 0
            img.close()

    def test_skip_indices_skips_specified_pages(self, sample_pdf_bytes):
        """Should skip conversion for specified page indices."""
        # Skip pages 1 and 3
        indexed_pages = convert_pdf_bytes_to_png_bytes(
            sample_pdf_bytes, dpi=100, skip_indices=[1, 3]
        )

        # Should only return 3 pages (0, 2, 4)
        assert indexed_pages.page_count == 3
        assert indexed_pages.indices == [0, 2, 4]

        # Skipped pages should not be in container
        assert 1 not in indexed_pages
        assert 3 not in indexed_pages

        # Non-skipped pages should be present
        assert 0 in indexed_pages
        assert 2 in indexed_pages
        assert 4 in indexed_pages

    def test_skip_indices_with_empty_list(self, sample_pdf_bytes):
        """Should convert all pages when skip_indices is empty list."""
        indexed_pages = convert_pdf_bytes_to_png_bytes(sample_pdf_bytes, dpi=100, skip_indices=[])

        assert indexed_pages.page_count == 5
        assert indexed_pages.indices == [0, 1, 2, 3, 4]

    def test_skip_indices_with_none(self, sample_pdf_bytes):
        """Should convert all pages when skip_indices is None."""
        indexed_pages = convert_pdf_bytes_to_png_bytes(sample_pdf_bytes, dpi=100, skip_indices=None)

        assert indexed_pages.page_count == 5
        assert indexed_pages.indices == [0, 1, 2, 3, 4]

    def test_skip_all_pages(self, sample_pdf_bytes):
        """Should return empty container when all pages are skipped."""
        indexed_pages = convert_pdf_bytes_to_png_bytes(
            sample_pdf_bytes, dpi=100, skip_indices=[0, 1, 2, 3, 4]
        )

        assert indexed_pages.page_count == 0
        assert indexed_pages.indices == []

    def test_skip_indices_out_of_range(self, sample_pdf_bytes):
        """Should ignore skip indices that are out of range."""
        # PDF has 5 pages (0-4), try to skip page 10
        indexed_pages = convert_pdf_bytes_to_png_bytes(
            sample_pdf_bytes, dpi=100, skip_indices=[1, 10, 20]
        )

        # Should skip page 1, ignore 10 and 20
        assert indexed_pages.page_count == 4
        assert indexed_pages.indices == [0, 2, 3, 4]
        assert 1 not in indexed_pages

    def test_skip_indices_with_duplicates(self, sample_pdf_bytes):
        """Should handle duplicate indices in skip list."""
        indexed_pages = convert_pdf_bytes_to_png_bytes(
            sample_pdf_bytes, dpi=100, skip_indices=[1, 1, 1, 3, 3]
        )

        # Should skip pages 1 and 3 (duplicates ignored)
        assert indexed_pages.page_count == 3
        assert indexed_pages.indices == [0, 2, 4]
