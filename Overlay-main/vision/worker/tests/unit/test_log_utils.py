"""Unit tests for logging utilities."""

import logging
from unittest.mock import Mock
from uuid import UUID

import pytest

from utils.log_utils import (
    format_compact_context,
    format_context,
    format_duration,
    format_size,
    get_memory_mb,
    log_coordination_published,
    log_coordination_ready,
    log_identifier_extracted,
    log_job_completed,
    log_job_failed_permanent,
    log_job_failed_transient,
    log_job_received,
    log_job_started,
    log_message_acked,
    log_message_nacked,
    log_ocr_completed,
    log_pdf_converted,
    log_status_updated,
    log_storage_download,
    log_storage_upload,
    log_worker_config,
    log_worker_ready,
    log_worker_shutdown,
    log_worker_starting,
)


class TestFormatSize:
    def test_formats_bytes(self):
        """Format bytes as human-readable string."""
        assert format_size(500) == "500b"
        assert format_size(0) == "0b"

    def test_formats_kilobytes(self):
        """Format kilobytes as human-readable string."""
        assert format_size(1024) == "1.0kb"
        assert format_size(1536) == "1.5kb"
        assert format_size(102400) == "100.0kb"

    def test_formats_megabytes(self):
        """Format megabytes as human-readable string."""
        assert format_size(1048576) == "1.0mb"
        assert format_size(1572864) == "1.5mb"
        assert format_size(104857600) == "100.0mb"


class TestFormatDuration:
    def test_formats_milliseconds(self):
        """Format milliseconds as human-readable string."""
        assert format_duration(500) == "500ms"
        assert format_duration(999) == "999ms"
        assert format_duration(0) == "0ms"

    def test_formats_seconds(self):
        """Format seconds as human-readable string."""
        assert format_duration(1000) == "1.0s"
        assert format_duration(1500) == "1.5s"
        assert format_duration(15000) == "15.0s"


class TestFormatContext:
    def test_formats_drawing_only(self):
        """Format context with drawing ID only."""
        result = format_context(drawing_id="12345678-1234-1234-1234-123456789012")
        assert result == "draw-12345678"

    def test_formats_drawing_and_sheet(self):
        """Format context with drawing and sheet IDs."""
        result = format_context(
            drawing_id="12345678-1234-1234-1234-123456789012",
            sheet_id="87654321-4321-4321-4321-210987654321",
        )
        assert result == "draw-12345678 > sheet-87654321"

    def test_formats_full_hierarchy(self):
        """Format context with all IDs."""
        result = format_context(
            drawing_id="12345678-1234-1234-1234-123456789012",
            sheet_id="87654321-4321-4321-4321-210987654321",
            block_id="abcdefab-abcd-abcd-abcd-abcdefabcdef",
            overlay_id="01234567-89ab-cdef-0123-456789abcdef",
            job_id="fedcba98-7654-3210-fedc-ba9876543210",
        )
        assert (
            result
            == "draw-12345678 > sheet-87654321 > block-abcdefab > ovl-01234567 > job-fedcba98"
        )

    def test_handles_short_ids(self):
        """Format context with short IDs (less than 8 chars)."""
        result = format_context(drawing_id="abc123", sheet_id="def456")
        assert result == "draw-abc123 > sheet-def456"

    def test_handles_none_values(self):
        """Format context with None values."""
        result = format_context(drawing_id=None, sheet_id=None)
        assert result == ""

    def test_handles_uuid_objects(self):
        """Format context with UUID objects instead of strings."""
        drawing_uuid = UUID("12345678-1234-1234-1234-123456789012")
        sheet_uuid = UUID("87654321-4321-4321-4321-210987654321")
        overlay_uuid = UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef")
        job_uuid = UUID("01234567-89ab-cdef-0123-456789abcdef")

        result = format_context(
            drawing_id=drawing_uuid,
            sheet_id=sheet_uuid,
            overlay_id=overlay_uuid,
            job_id=job_uuid,
        )
        assert result == "draw-12345678 > sheet-87654321 > ovl-abcdefab > job-01234567"


class TestFormatCompactContext:
    def test_formats_job_only(self):
        """Format compact context with job ID only."""
        result = format_compact_context(job_id="12345678-1234-1234-1234-123456789012")
        assert result == "job-12345678"

    def test_handles_none_values(self):
        """Format compact context with None values."""
        result = format_compact_context(job_id=None)
        assert result == ""

    def test_handles_uuid_objects(self):
        """Format compact context with UUID objects."""
        job_uuid = UUID("12345678-1234-1234-1234-123456789012")

        result = format_compact_context(job_id=job_uuid)
        assert result == "job-12345678"


class TestGetMemoryMb:
    def test_returns_float_or_none(self):
        """Get memory returns float or None."""
        result = get_memory_mb()
        # Memory should be either a positive float or None (if psutil not available)
        assert result is None or (isinstance(result, float) and result > 0)


class TestLoggingFunctions:
    """Test logging functions don't crash and produce expected output."""

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger."""
        return Mock(spec=logging.Logger)

    def test_log_job_received(self, mock_logger):
        """Test log_job_received function."""
        log_job_received(
            mock_logger,
            "conversion",
            "msg-12345678",
            drawing_id="12345678-1234-1234-1234-123456789012",
            job_id="87654321-4321-4321-4321-210987654321",
        )

        # Verify logger was called
        assert mock_logger.info.call_count >= 1

        # Check first call contains job.received
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[job.received]" in first_call
        assert "conversion" in first_call

    def test_log_job_started(self, mock_logger):
        """Test log_job_started function."""
        start_time = log_job_started(
            mock_logger,
            "conversion",
            "msg-12345678",
            drawing_id="12345678-1234-1234-1234-123456789012",
            job_id="87654321-4321-4321-4321-210987654321",
        )

        # Verify returns a timestamp
        assert isinstance(start_time, float)
        assert start_time > 0

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[job.started]" in first_call

    def test_log_job_completed(self, mock_logger):
        """Test log_job_completed function."""
        log_job_completed(
            mock_logger,
            "conversion",
            "msg-12345678",
            start_time=1000.0,
            drawing_id="12345678-1234-1234-1234-123456789012",
            job_id="87654321-4321-4321-4321-210987654321",
            pages_total=50,
            pages_new=30,
            pages_existing=20,
        )

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[job.completed]" in first_call

    def test_log_status_updated(self, mock_logger):
        """Test log_status_updated function."""
        log_status_updated(
            mock_logger,
            "drawing",
            "draw-12345678",
            old_status="Created",
            new_status="Pages Segmented",
        )

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[status.updated]" in call_text
        assert "Created" in call_text
        assert "Pages Segmented" in call_text

    def test_log_storage_download(self, mock_logger):
        """Test log_storage_download function."""
        log_storage_download(
            mock_logger,
            "pdfs/file.pdf",
            size_bytes=1048576,
            duration_ms=1500,
            drawing_id="12345678-1234-1234-1234-123456789012",
        )

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[storage.download]" in first_call
        assert "file.pdf" in first_call

    def test_log_storage_upload(self, mock_logger):
        """Test log_storage_upload function."""
        log_storage_upload(
            mock_logger,
            "pngs/page_0.png",
            size_bytes=512000,
            duration_ms=800,
        )

        # Verify logger was called (debug level for uploads)
        assert mock_logger.debug.call_count == 1
        call_text = mock_logger.debug.call_args[0][0]
        assert "[storage.upload]" in call_text
        assert "page_0.png" in call_text

    def test_log_pdf_converted(self, mock_logger):
        """Test log_pdf_converted function."""
        log_pdf_converted(
            mock_logger,
            page_count=50,
            duration_ms=15000,
            drawing_id="12345678-1234-1234-1234-123456789012",
        )

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[pdf.converted]" in first_call
        assert "50 pages" in first_call

    def test_log_coordination_published(self, mock_logger):
        """Test log_coordination_published function."""
        log_coordination_published(
            mock_logger,
            "vision",
            50,
            drawing_id="12345678-1234-1234-1234-123456789012",
        )

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[coordination.published]" in first_call
        assert "vision" in first_call
        assert "50" in first_call

    def test_log_coordination_ready(self, mock_logger):
        """Test log_coordination_ready function."""
        log_coordination_ready(mock_logger, "all pages identified", True)

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[coordination.ready]" in call_text

        # Test waiting state
        mock_logger.reset_mock()
        log_coordination_ready(mock_logger, "all pages identified", False)
        call_text = mock_logger.info.call_args[0][0]
        assert "[coordination.waiting]" in call_text

    def test_log_message_acked(self, mock_logger):
        """Test log_message_acked function."""
        log_message_acked(mock_logger, "msg-12345678", "conversion")

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[message.acked]" in call_text

    def test_log_message_nacked(self, mock_logger):
        """Test log_message_nacked function."""
        log_message_nacked(mock_logger, "msg-12345678", "conversion", "transient_error")

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[message.nacked]" in call_text

    def test_log_job_failed_permanent(self, mock_logger):
        """Test log_job_failed_permanent function."""
        error = ValueError("Invalid data")
        log_job_failed_permanent(mock_logger, "conversion", "msg-12345678", error)

        # Verify logger.error was called
        assert mock_logger.error.call_count >= 1
        first_call = mock_logger.error.call_args_list[0][0][0]
        assert "[job.failed.permanent]" in first_call

    def test_log_job_failed_transient(self, mock_logger):
        """Test log_job_failed_transient function."""
        error = ConnectionError("Network timeout")
        log_job_failed_transient(mock_logger, "conversion", "msg-12345678", error)

        # Verify logger.error was called
        assert mock_logger.error.call_count >= 1
        first_call = mock_logger.error.call_args_list[0][0][0]
        assert "[job.failed.transient]" in first_call

    def test_log_ocr_completed(self, mock_logger):
        """Test log_ocr_completed function."""
        log_ocr_completed(
            mock_logger,
            "vision_api",
            1247,
            sheet_id="sheet-123",
            sheet_index=5,
        )

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[ocr.completed]" in first_call
        assert "vision_api" in first_call
        assert "1,247" in first_call

    def test_log_identifier_extracted(self, mock_logger):
        """Test log_identifier_extracted function."""
        log_identifier_extracted(
            mock_logger,
            "A-101",
            sheet_id="sheet-123",
            sheet_index=5,
        )

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[identifier.extracted]" in first_call
        assert "A-101" in first_call

    def test_log_identifier_extracted_none(self, mock_logger):
        """Test log_identifier_extracted with None."""
        log_identifier_extracted(mock_logger, None, sheet_index=5)

        # Verify logger was called
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[identifier.extracted]" in first_call
        assert "none" in first_call

    def test_log_worker_starting(self, mock_logger):
        """Test log_worker_starting function."""
        log_worker_starting(mock_logger)

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[worker.starting]" in call_text

    def test_log_worker_config(self, mock_logger):
        """Test log_worker_config function."""
        log_worker_config(
            mock_logger,
            db_host="localhost",
            db_port=5432,
            db_name="odin",
            storage_backend="gcs",
            storage_bucket="my-bucket",
            pubsub_project="my-project",
            topics=["convert", "extract"],
            subscriptions=["vision.worker"],
            max_concurrent=10,
            max_memory_bytes=1073741824,
            max_lease_seconds=1800,
        )

        # Verify logger was called multiple times
        assert mock_logger.info.call_count >= 4
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[worker.config]" in first_call

    def test_log_worker_ready(self, mock_logger):
        """Test log_worker_ready function."""
        log_worker_ready(mock_logger)

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[worker.ready]" in call_text

    def test_log_worker_shutdown(self, mock_logger):
        """Test log_worker_shutdown function."""
        log_worker_shutdown(mock_logger)

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[worker.shutdown]" in call_text

    def test_log_ocr_completed_with_uuid(self, mock_logger):
        """Test log_ocr_completed with UUID object."""
        sheet_uuid = UUID("abcdefab-abcd-abcd-abcd-abcdefabcdef")

        log_ocr_completed(
            mock_logger,
            "pymupdf",
            5718,
            sheet_id=sheet_uuid,
            sheet_index=0,
        )

        # Verify logger was called and didn't crash
        assert mock_logger.info.call_count >= 1
        first_call = mock_logger.info.call_args_list[0][0][0]
        assert "[ocr.completed]" in first_call

    def test_log_status_updated_with_uuid(self, mock_logger):
        """Test log_status_updated with UUID object."""
        drawing_uuid = UUID("12345678-1234-1234-1234-123456789012")

        log_status_updated(
            mock_logger,
            "drawing",
            drawing_uuid,
            old_status="Created",
            new_status="Pages Segmented",
        )

        # Verify logger was called
        assert mock_logger.info.call_count == 1
        call_text = mock_logger.info.call_args[0][0]
        assert "[status.updated]" in call_text
        assert "12345678" in call_text  # Short ID without prefix
        assert "Created → Pages Segmented" in call_text
