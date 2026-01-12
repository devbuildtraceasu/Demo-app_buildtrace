"""Unit tests for drawing identifier extraction using position-based algorithm."""

from unittest.mock import patch

from lib.identifier_extractor import (
    DRAWING_RE,
    extract_identifier,
    extract_identifier_from_words,
    normalize_dwg,
    pick_bottom_right,
    words_to_candidates,
)


class TestNormalizeDwg:
    def test_preserves_hyphen_format(self):
        """Preserve A-101 format (with hyphen)."""
        text = "DRAWING A-101 SHEET"
        match = DRAWING_RE.search(text)
        identifier = normalize_dwg(text, match)
        assert identifier == "A-101"

    def test_preserves_space_format(self):
        """Preserve A 101 format (with space)."""
        text = "DRAWING A 101 SHEET"
        match = DRAWING_RE.search(text)
        identifier = normalize_dwg(text, match)
        assert identifier == "A 101"

    def test_preserves_decimal_format(self):
        """Preserve A2.1 format (decimal notation)."""
        text = "SHEET A2.1 DETAIL"
        match = DRAWING_RE.search(text)
        identifier = normalize_dwg(text, match)
        assert identifier == "A2.1"

    def test_preserves_multi_part_prefix(self):
        """Preserve B-S01 format (multi-part prefix)."""
        text = "STRUCTURAL B-S01"
        match = DRAWING_RE.search(text)
        identifier = normalize_dwg(text, match)
        assert identifier == "B-S01"

    def test_preserves_suffix_letter(self):
        """Preserve S-12A format (letter suffix)."""
        text = "SHEET S-12A REVISION"
        match = DRAWING_RE.search(text)
        identifier = normalize_dwg(text, match)
        assert identifier == "S-12A"

    def test_preserves_hyphen_suffix(self):
        """Preserve A2.1-REV format (hyphen suffix)."""
        text = "DRAWING A2.1-REV"
        match = DRAWING_RE.search(text)
        identifier = normalize_dwg(text, match)
        assert identifier == "A2.1-REV"


class TestWordsToCandidates:
    def test_extracts_candidates_from_words(self):
        """Extract candidates from word list."""
        words = [
            {
                "text": "A-101",
                "bbox": {"x0": 100, "y0": 200, "x1": 150, "y1": 220},
                "block_no": 0,
                "line_no": 0,
                "word_no": 0,
            },
            {
                "text": "SCALE",
                "bbox": {"x0": 200, "y0": 200, "x1": 250, "y1": 220},
                "block_no": 0,
                "line_no": 0,
                "word_no": 1,
            },
        ]
        page_dims = {"width": 612, "height": 792}

        candidates = words_to_candidates(words, page_dims)

        # Should find A-101
        assert len(candidates) > 0
        assert any(cand[0] == "A-101" for cand in candidates)

        # Check candidate structure: (identifier, cx, cy, font_size)
        first_cand = candidates[0]
        assert isinstance(first_cand[0], str)  # identifier
        assert isinstance(first_cand[1], int | float)  # cx
        assert isinstance(first_cand[2], int | float)  # cy

    def test_extracts_candidates_from_line_concatenation(self):
        """Extract candidates from concatenated line text (split identifiers)."""
        words = [
            {
                "text": "SHEET",
                "bbox": {"x0": 100, "y0": 200, "x1": 150, "y1": 220},
                "block_no": 0,
                "line_no": 0,
                "word_no": 0,
            },
            {
                "text": "B-S01",
                "bbox": {"x0": 160, "y0": 200, "x1": 210, "y1": 220},
                "block_no": 0,
                "line_no": 0,
                "word_no": 1,
            },
        ]
        page_dims = {"width": 612, "height": 792}

        candidates = words_to_candidates(words, page_dims)

        # Should find B-S01 from line concatenation
        assert any(cand[0] == "B-S01" for cand in candidates)

    @patch("lib.ocr.get_page_text_dict")
    def test_includes_font_sizes_when_pdf_bytes_provided(self, mock_get_text_dict):
        """Include font sizes in candidates when PDF bytes provided."""
        # Mock font size data
        mock_get_text_dict.return_value = {
            "blocks": [
                {
                    "lines": [
                        {
                            "spans": [
                                {
                                    "text": "A-101",
                                    "size": 24.0,
                                    "bbox": [100, 200, 150, 220],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        words = [
            {
                "text": "A-101",
                "bbox": {"x0": 100, "y0": 200, "x1": 150, "y1": 220},
                "block_no": 0,
                "line_no": 0,
                "word_no": 0,
            }
        ]
        page_dims = {"width": 612, "height": 792}
        pdf_bytes = b"mock_pdf_bytes"

        candidates = words_to_candidates(words, page_dims, pdf_bytes, 0)

        # Should include font size
        assert len(candidates) > 0
        # Candidate format: (identifier, cx, cy, font_size)
        assert len(candidates[0]) == 4


class TestPickBottomRight:
    def test_picks_bottom_right_candidate(self):
        """Pick candidate nearest to bottom-right corner."""
        candidates = [
            ("A-101", 100, 100, 12),  # top-left, small font
            ("B-201", 500, 700, 12),  # bottom-right, small font
            ("C-301", 300, 400, 12),  # center, small font
        ]
        page_dims = {"width": 612, "height": 792}

        identifier = pick_bottom_right(candidates, page_dims)

        # Should pick B-201 (bottom-right)
        assert identifier == "B-201"

    def test_picks_largest_font_size(self):
        """Pick candidate with largest font size."""
        candidates = [
            ("A-101", 500, 700, 12),  # bottom-right, small font
            ("B-201", 500, 700, 24),  # bottom-right, large font
            ("C-301", 500, 700, 18),  # bottom-right, medium font
        ]
        page_dims = {"width": 612, "height": 792}

        identifier = pick_bottom_right(candidates, page_dims)

        # Should pick B-201 (largest font)
        assert identifier == "B-201"

    def test_balances_position_and_font_size(self):
        """Balance position (bottom-right) and font size in scoring."""
        candidates = [
            ("A-101", 100, 100, 24),  # top-left, large font
            ("B-201", 500, 700, 18),  # bottom-right, medium font
        ]
        page_dims = {"width": 612, "height": 792}

        identifier = pick_bottom_right(candidates, page_dims)

        # Should pick B-201 (better position outweighs slightly smaller font)
        assert identifier == "B-201"

    def test_returns_none_for_empty_candidates(self):
        """Return None when no candidates."""
        candidates = []
        page_dims = {"width": 612, "height": 792}

        identifier = pick_bottom_right(candidates, page_dims)

        assert identifier is None

    def test_handles_zero_dimensions(self):
        """Handle zero page dimensions gracefully."""
        candidates = [("A-101", 100, 100, 12)]
        page_dims = {"width": 0, "height": 0}

        identifier = pick_bottom_right(candidates, page_dims)

        # Should not crash, should return a result
        assert identifier is not None


class TestExtractIdentifierFromWords:
    @patch("lib.identifier_extractor.words_to_candidates")
    @patch("lib.identifier_extractor.pick_bottom_right")
    def test_extracts_identifier_from_words(self, mock_pick, mock_words_to_cands):
        """Extract identifier from words using position-based algorithm."""
        mock_words_to_cands.return_value = [("A-101", 500, 700, 24)]
        mock_pick.return_value = "A-101"

        words = [
            {
                "text": "A-101",
                "bbox": {"x0": 500, "y0": 700, "x1": 550, "y1": 720},
                "block_no": 0,
                "line_no": 0,
                "word_no": 0,
            }
        ]
        page_dims = {"width": 612, "height": 792}

        identifier = extract_identifier_from_words(words, page_dims)

        assert identifier == "A-101"
        mock_words_to_cands.assert_called_once()
        mock_pick.assert_called_once()

    @patch("lib.identifier_extractor.words_to_candidates")
    @patch("lib.identifier_extractor.pick_bottom_right")
    @patch("lib.identifier_extractor.extract_drawing_no_from_bottom_right_region")
    def test_falls_back_to_ocr_when_no_words_match(
        self, mock_ocr_region, mock_pick, mock_words_to_cands
    ):
        """Fall back to OCR on bottom-right region when no identifier found in words."""
        # No candidates from words
        mock_words_to_cands.return_value = []
        mock_pick.return_value = None

        # OCR returns text with identifier
        mock_ocr_region.return_value = "DRAWING NO: B-201"

        words = []
        page_dims = {"width": 612, "height": 792}
        png_bytes = b"mock_png_bytes"

        identifier = extract_identifier_from_words(words, page_dims, png_bytes=png_bytes)

        assert identifier == "B-201"
        mock_ocr_region.assert_called_once_with(png_bytes, sheet_id=None)

    @patch("lib.identifier_extractor.words_to_candidates")
    @patch("lib.identifier_extractor.pick_bottom_right")
    def test_returns_none_when_no_identifier_found(self, mock_pick, mock_words_to_cands):
        """Return None when no identifier found in words or OCR."""
        mock_words_to_cands.return_value = []
        mock_pick.return_value = None

        words = []
        page_dims = {"width": 612, "height": 792}

        identifier = extract_identifier_from_words(words, page_dims)

        assert identifier is None


class TestExtractIdentifierLegacy:
    """Tests for legacy extract_identifier function (backward compatibility)."""

    def test_extract_standard_format_with_hyphen(self):
        """Extract A-101 format identifier (UDS standard with hyphen)."""
        text = "DRAWING NO: A-101 SHEET 1 OF 5"
        identifier = extract_identifier(text)
        assert identifier == "A-101"

    def test_extract_decimal_format(self):
        """Extract A2.1 format identifier (decimal notation)."""
        text = "SHEET A2.1 DETAIL"
        identifier = extract_identifier(text)
        assert identifier == "A2.1"

    def test_extract_multi_part_prefix(self):
        """Extract B-S01 format identifier (multi-part prefix)."""
        text = "STRUCTURAL SHEET B-S01"
        identifier = extract_identifier(text)
        assert identifier == "B-S01"

    def test_extract_with_letter_suffix(self):
        """Extract S-12A format identifier (letter suffix)."""
        text = "SHEET S-12A REVISION"
        identifier = extract_identifier(text)
        assert identifier == "S-12A"

    def test_no_identifier_found(self):
        """Return None when no identifier found."""
        text = "COVER PAGE - NO DRAWING NUMBER"
        identifier = extract_identifier(text)
        assert identifier is None

    def test_extract_from_empty_string(self):
        """Return None for empty string."""
        text = ""
        identifier = extract_identifier(text)
        assert identifier is None

    def test_extract_from_whitespace_only(self):
        """Return None for whitespace-only string."""
        text = "   \n  \t  "
        identifier = extract_identifier(text)
        assert identifier is None
