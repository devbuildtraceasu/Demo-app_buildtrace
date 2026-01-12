"""Unit tests for text extraction from PDF pages and PNG images."""

from pathlib import Path
from unittest.mock import Mock, patch

from lib.ocr import (
    extract_drawing_no_from_bottom_right_region,
    extract_drawing_no_with_vllm,
    extract_text_words_from_pdf_page,
    get_page_dimensions,
    get_page_text_dict,
)

# Test file paths
TEST_DIR = Path(__file__).parent.parent / "assets"
TEST_PDF = TEST_DIR / "pdfs" / "pdf_sample_5_pages.pdf"
TEST_PNG = TEST_DIR / "pngs" / "page_0.png"


class TestExtractTextWordsFromPdfPage:
    def test_extracts_words_from_valid_pdf_page(self):
        """Extract words with coordinates from valid PDF page using real file."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        # Extract words from first page
        words = extract_text_words_from_pdf_page(pdf_bytes, 0)

        # Verify extracted words structure
        assert isinstance(words, list)
        assert len(words) > 0

        # Check first word structure
        first_word = words[0]
        assert "block_no" in first_word
        assert "line_no" in first_word
        assert "word_no" in first_word
        assert "bbox" in first_word
        assert "text" in first_word

        # Check bbox structure
        bbox = first_word["bbox"]
        assert "x0" in bbox
        assert "y0" in bbox
        assert "x1" in bbox
        assert "y1" in bbox
        assert isinstance(bbox["x0"], int | float)
        assert isinstance(bbox["y0"], int | float)

        # Verify some expected words exist
        word_texts = [w["text"] for w in words]
        assert any("Lorem" in text for text in word_texts)
        assert any("ipsum" in text for text in word_texts)

    def test_extracts_words_from_different_pages(self):
        """Extract words from different pages of the same PDF."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        # Extract from multiple pages
        words_page_0 = extract_text_words_from_pdf_page(pdf_bytes, 0)
        words_page_1 = extract_text_words_from_pdf_page(pdf_bytes, 1)

        assert isinstance(words_page_0, list)
        assert isinstance(words_page_1, list)
        assert len(words_page_0) > 0
        assert len(words_page_1) > 0

        # Pages should have different content
        text_0 = " ".join(w["text"] for w in words_page_0)
        text_1 = " ".join(w["text"] for w in words_page_1)
        assert text_0 != text_1

    def test_returns_empty_list_for_page_out_of_range(self):
        """Return empty list when page index exceeds PDF page count."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        # PDF has 5 pages (0-4), request page 10
        words = extract_text_words_from_pdf_page(pdf_bytes, 10)

        assert words == []

    def test_returns_empty_list_on_invalid_pdf(self):
        """Return empty list when PDF is invalid."""
        invalid_pdf_bytes = b"not a valid pdf"
        words = extract_text_words_from_pdf_page(invalid_pdf_bytes, 0)

        assert words == []

    def test_word_coordinates_are_valid(self):
        """Verify word coordinates are logical (x0 < x1, y0 < y1)."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        words = extract_text_words_from_pdf_page(pdf_bytes, 0)

        for word in words[:10]:  # Check first 10 words
            bbox = word["bbox"]
            assert bbox["x0"] <= bbox["x1"], f"Invalid x coordinates for word: {word['text']}"
            assert bbox["y0"] <= bbox["y1"], f"Invalid y coordinates for word: {word['text']}"


class TestGetPageDimensions:
    def test_gets_dimensions_from_valid_pdf(self):
        """Get page dimensions from valid PDF."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        dims = get_page_dimensions(pdf_bytes, 0)

        assert isinstance(dims, dict)
        assert "width" in dims
        assert "height" in dims
        assert dims["width"] > 0
        assert dims["height"] > 0

    def test_returns_zero_dimensions_for_invalid_page(self):
        """Return zero dimensions for page out of range."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        dims = get_page_dimensions(pdf_bytes, 100)

        assert dims == {"width": 0, "height": 0}

    def test_returns_zero_dimensions_on_invalid_pdf(self):
        """Return zero dimensions when PDF is invalid."""
        invalid_pdf_bytes = b"not a valid pdf"
        dims = get_page_dimensions(invalid_pdf_bytes, 0)

        assert dims == {"width": 0, "height": 0}


class TestGetPageTextDict:
    def test_gets_text_dict_from_valid_pdf(self):
        """Get text dictionary with font information from valid PDF."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        text_dict = get_page_text_dict(pdf_bytes, 0)

        assert isinstance(text_dict, dict)
        assert "blocks" in text_dict
        assert isinstance(text_dict["blocks"], list)

        # Check if blocks contain expected structure
        if text_dict["blocks"]:
            block = text_dict["blocks"][0]
            assert "type" in block

    def test_returns_empty_dict_for_invalid_page(self):
        """Return empty dict for page out of range."""
        with open(TEST_PDF, "rb") as f:
            pdf_bytes = f.read()

        text_dict = get_page_text_dict(pdf_bytes, 100)

        assert text_dict == {}

    def test_returns_empty_dict_on_invalid_pdf(self):
        """Return empty dict when PDF is invalid."""
        invalid_pdf_bytes = b"not a valid pdf"
        text_dict = get_page_text_dict(invalid_pdf_bytes, 0)

        assert text_dict == {}


class TestExtractDrawingNoWithVllm:
    @patch("lib.ocr.OpenAI")
    def test_extracts_drawing_no_via_vision_api(self, mock_openai):
        """Extract drawing number using vision API."""
        # Mock OpenAI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "A-101"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        png_bytes = b"mock_png_bytes"
        text = extract_drawing_no_with_vllm(png_bytes, api_key="test-key")

        assert text == "A-101"
        mock_client.chat.completions.create.assert_called_once()

        # Verify the prompt focuses on drawing number
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert any("drawing no" in str(msg).lower() for msg in messages)

    @patch("lib.ocr.OpenAI")
    def test_returns_none_on_api_failure(self, mock_openai):
        """Return None when vision API fails."""
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API error")
        mock_openai.return_value = mock_client

        png_bytes = b"mock_png_bytes"
        text = extract_drawing_no_with_vllm(png_bytes, api_key="test-key")

        assert text is None

    @patch("lib.ocr.OpenAI")
    def test_includes_sheet_id_in_logging(self, mock_openai):
        """Include sheet_id parameter for logging."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "B-201"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        png_bytes = b"mock_png_bytes"
        text = extract_drawing_no_with_vllm(png_bytes, sheet_id="test-sheet-id", api_key="test-key")

        assert text == "B-201"


class TestExtractDrawingNoFromBottomRightRegion:
    @patch("lib.ocr.extract_drawing_no_with_vllm")
    @patch("lib.ocr.Image")
    def test_crops_and_ocrs_bottom_right_region(self, mock_image_class, mock_extract_vllm):
        """Crop bottom-right region and OCR it."""
        # Mock PIL Image
        mock_img = Mock()
        mock_img.size = (1000, 800)
        mock_cropped = Mock()

        mock_img.crop.return_value = mock_cropped
        mock_image_class.open.return_value = mock_img

        # Mock OCR result
        mock_extract_vllm.return_value = "A-101"

        png_bytes = b"mock_png_bytes"
        result = extract_drawing_no_from_bottom_right_region(png_bytes)

        assert result == "A-101"

        # Verify crop box (default: 70% left, 76% top)
        expected_crop_box = (700, 608, 1000, 800)
        mock_img.crop.assert_called_once_with(expected_crop_box)

        # Verify OCR was called with cropped bytes
        mock_extract_vllm.assert_called_once()

    @patch("lib.ocr.extract_drawing_no_with_vllm")
    @patch("lib.ocr.Image")
    def test_uses_custom_crop_parameters(self, mock_image_class, mock_extract_vllm):
        """Use custom crop parameters."""
        mock_img = Mock()
        mock_img.size = (1000, 800)
        mock_cropped = Mock()

        mock_img.crop.return_value = mock_cropped
        mock_image_class.open.return_value = mock_img

        mock_extract_vllm.return_value = "B-201"

        png_bytes = b"mock_png_bytes"
        result = extract_drawing_no_from_bottom_right_region(
            png_bytes, crop_left=0.60, crop_top=0.80
        )

        # Verify custom crop box (60% left, 80% top)
        expected_crop_box = (600, 640, 1000, 800)
        mock_img.crop.assert_called_once_with(expected_crop_box)

    @patch("lib.ocr.Image")
    def test_returns_none_on_crop_failure(self, mock_image_class):
        """Return None when image cropping fails."""
        mock_image_class.open.side_effect = Exception("Invalid image")

        png_bytes = b"invalid_png_bytes"
        result = extract_drawing_no_from_bottom_right_region(png_bytes)

        assert result is None
