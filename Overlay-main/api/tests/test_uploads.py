"""Tests for file upload endpoints."""

import io

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


class TestUploads:
    """Test suite for file upload endpoints."""

    def test_signed_url_pdf_success(self):
        """Test generating signed URL for PDF file."""
        response = client.post(
            "/api/uploads/signed-url",
            json={
                "filename": "test-drawing.pdf",
                "content_type": "application/pdf",
                "project_id": "test-proj-123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "upload_url" in data
        assert "remote_path" in data
        assert "expires_in" in data
        assert data["expires_in"] == 3600
        assert "projects/test-proj-123/uploads/" in data["remote_path"]
        assert data["remote_path"].endswith(".pdf")

    def test_signed_url_image_success(self):
        """Test generating signed URL for image file."""
        response = client.post(
            "/api/uploads/signed-url",
            json={
                "filename": "test-image.png",
                "content_type": "image/png",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["remote_path"].endswith(".png")
        assert "uploads/" in data["remote_path"]

    def test_signed_url_invalid_file_type(self):
        """Test signed URL generation fails for invalid file type."""
        response = client.post(
            "/api/uploads/signed-url",
            json={
                "filename": "test.txt",
                "content_type": "text/plain",
            },
        )
        assert response.status_code == 400
        assert "File type not allowed" in response.json()["detail"]

    def test_signed_url_invalid_content_type(self):
        """Test signed URL generation fails for invalid content type."""
        response = client.post(
            "/api/uploads/signed-url",
            json={
                "filename": "test.pdf",
                "content_type": "application/xml",
            },
        )
        assert response.status_code == 400
        assert "Content type" in response.json()["detail"]

    def test_signed_url_dwg_file(self):
        """Test generating signed URL for DWG file."""
        response = client.post(
            "/api/uploads/signed-url",
            json={
                "filename": "drawing.dwg",
                "content_type": "application/x-dwg",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["remote_path"].endswith(".dwg")

    def test_direct_upload_pdf_success(self):
        """Test direct file upload with PDF."""
        pdf_content = b"Mock PDF file content for testing"
        files = {
            "file": ("test.pdf", io.BytesIO(pdf_content), "application/pdf")
        }
        data = {"project_id": "test-proj-456"}

        response = client.post(
            "/api/uploads/direct",
            files=files,
            data=data,
        )
        assert response.status_code == 200
        result = response.json()
        assert "uri" in result
        assert "remote_path" in result
        assert "filename" in result
        assert "size" in result
        assert result["filename"] == "test.pdf"
        assert result["size"] == len(pdf_content)

    def test_direct_upload_image_success(self):
        """Test direct file upload with image."""
        image_content = b"Mock PNG image content"
        files = {
            "file": ("test-image.png", io.BytesIO(image_content), "image/png")
        }

        response = client.post(
            "/api/uploads/direct",
            files=files,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["filename"] == "test-image.png"
        assert result["content_type"] == "image/png"

    def test_direct_upload_invalid_file_type(self):
        """Test direct upload fails for invalid file type."""
        files = {
            "file": ("test.txt", io.BytesIO(b"text content"), "text/plain")
        }

        response = client.post(
            "/api/uploads/direct",
            files=files,
        )
        assert response.status_code == 400
        assert "File type not allowed" in response.json()["detail"]

    def test_direct_upload_no_filename(self):
        """Test direct upload fails without filename."""
        files = {
            "file": (None, io.BytesIO(b"content"), "application/pdf")
        }

        response = client.post(
            "/api/uploads/direct",
            files=files,
        )
        assert response.status_code == 400
        assert "Filename is required" in response.json()["detail"]

    def test_direct_upload_file_too_large(self):
        """Test direct upload fails for oversized file."""
        # Create a file larger than 100 MB (100 * 1024 * 1024 bytes)
        large_content = b"x" * (101 * 1024 * 1024)  # 101 MB
        files = {
            "file": ("large.pdf", io.BytesIO(large_content), "application/pdf")
        }

        response = client.post(
            "/api/uploads/direct",
            files=files,
        )
        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]
        assert "100 MB" in response.json()["detail"]

    def test_direct_upload_jpg_success(self):
        """Test direct upload with JPG image."""
        files = {
            "file": ("photo.jpg", io.BytesIO(b"JPG content"), "image/jpeg")
        }

        response = client.post(
            "/api/uploads/direct",
            files=files,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["filename"] == "photo.jpg"

    def test_direct_upload_dxf_success(self):
        """Test direct upload with DXF file."""
        files = {
            "file": ("drawing.dxf", io.BytesIO(b"DXF content"), "application/dxf")
        }

        response = client.post(
            "/api/uploads/direct",
            files=files,
        )
        assert response.status_code == 200
        result = response.json()
        assert result["filename"] == "drawing.dxf"

    def test_signed_url_with_project_id(self):
        """Test signed URL with project ID creates correct path."""
        response = client.post(
            "/api/uploads/signed-url",
            json={
                "filename": "drawing.pdf",
                "content_type": "application/pdf",
                "project_id": "proj-abc-123",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "projects/proj-abc-123/uploads/" in data["remote_path"]

    def test_signed_url_without_project_id(self):
        """Test signed URL without project ID creates generic path."""
        response = client.post(
            "/api/uploads/signed-url",
            json={
                "filename": "drawing.pdf",
                "content_type": "application/pdf",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["remote_path"].startswith("uploads/")
        assert "projects/" not in data["remote_path"]

    def test_download_url_generation(self):
        """Test download URL generation."""
        # First upload a file
        files = {
            "file": ("test.pdf", io.BytesIO(b"PDF content"), "application/pdf")
        }
        upload_response = client.post(
            "/api/uploads/direct",
            files=files,
        )
        assert upload_response.status_code == 200
        remote_path = upload_response.json()["remote_path"]

        # Now get download URL
        response = client.get(f"/api/uploads/download-url/{remote_path}")
        assert response.status_code == 200
        data = response.json()
        assert "download_url" in data
        assert "remote_path" in data
        assert "expires_in" in data
        assert data["remote_path"] == remote_path
