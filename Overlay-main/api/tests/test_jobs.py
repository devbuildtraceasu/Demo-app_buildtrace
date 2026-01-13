"""Tests for jobs API endpoints."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.routes.jobs import Job

client = TestClient(app)


class TestJobsAPI:
    """Test suite for jobs API endpoints."""

    def setup_method(self):
        """Setup test data before each test."""
        # We'll need to create test jobs directly in the database
        # For now, these tests check the endpoint structure
        pass

    def test_list_jobs_success(self):
        """Test listing jobs returns array."""
        # Get a valid token first
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": f"jobs_test_{id(self)}@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Jobs",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        response = client.get(
            "/api/jobs",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_jobs_with_project_filter(self):
        """Test listing jobs with project_id filter."""
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": f"jobs_filter_test_{id(self)}@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Filter",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        response = client.get(
            "/api/jobs?project_id=test-proj-123",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_jobs_with_status_filter(self):
        """Test listing jobs with status filter."""
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": f"jobs_status_test_{id(self)}@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Status",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        response = client.get(
            "/api/jobs?status_filter=Completed",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_list_jobs_with_limit(self):
        """Test listing jobs with limit parameter."""
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": f"jobs_limit_test_{id(self)}@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Limit",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        response = client.get(
            "/api/jobs?limit=10",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        jobs = response.json()
        assert isinstance(jobs, list)
        assert len(jobs) <= 10

    def test_list_jobs_unauthorized(self):
        """Test listing jobs without authentication fails."""
        response = client.get("/api/jobs")
        assert response.status_code == 401

    def test_get_job_not_found(self):
        """Test getting non-existent job returns 404."""
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": f"job_404_test_{id(self)}@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "NotFound",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        response = client.get(
            "/api/jobs/nonexistent-job-id",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_cancel_job_not_found(self):
        """Test canceling non-existent job returns 404."""
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": f"cancel_404_test_{id(self)}@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Cancel",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        response = client.post(
            "/api/jobs/nonexistent-job-id/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404

    def test_jobs_require_authentication(self):
        """Test all job endpoints require authentication."""
        # List jobs
        response = client.get("/api/jobs")
        assert response.status_code == 401

        # Get job
        response = client.get("/api/jobs/some-job-id")
        assert response.status_code == 401

        # Cancel job
        response = client.post("/api/jobs/some-job-id/cancel")
        assert response.status_code == 401

    def test_sse_endpoint_exists(self):
        """Test SSE endpoint is accessible."""
        # SSE endpoint allows unauthenticated access for easier testing
        # But should return error for non-existent job
        response = client.get("/api/jobs/sse/nonexistent-job")
        # SSE returns 200 with streaming response, but will send error event
        assert response.status_code == 200

    def test_list_jobs_combined_filters(self):
        """Test listing jobs with multiple filters."""
        signup_response = client.post(
            "/api/auth/signup",
            json={
                "email": f"jobs_combined_test_{id(self)}@buildtrace.com",
                "password": "TestPassword123",
                "first_name": "Combined",
                "last_name": "Test",
            },
        )
        token = signup_response.json()["access_token"]

        response = client.get(
            "/api/jobs?project_id=proj-123&status_filter=Completed&limit=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        jobs = response.json()
        assert isinstance(jobs, list)
        assert len(jobs) <= 20


class TestJobStatusMapping:
    """Test job status mapping logic."""

    def test_status_mapping_values(self):
        """Test that status mapping returns correct enum values."""
        from api.routes.jobs import _map_status
        from api.schemas.job import JobStatus

        assert _map_status("Queued") == JobStatus.QUEUED
        assert _map_status("Started") == JobStatus.STARTED
        assert _map_status("Completed") == JobStatus.COMPLETED
        assert _map_status("Failed") == JobStatus.FAILED
        assert _map_status("Canceled") == JobStatus.CANCELED
        assert _map_status("Unknown") == JobStatus.QUEUED  # Default


class TestSSEEndpoint:
    """Test Server-Sent Events endpoint."""

    def test_sse_headers(self):
        """Test SSE endpoint returns correct headers."""
        response = client.get("/api/jobs/sse/test-job-id", stream=True)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["connection"] == "keep-alive"

    def test_sse_nonexistent_job(self):
        """Test SSE endpoint handles non-existent job."""
        response = client.get("/api/jobs/sse/nonexistent-job-12345", stream=True)
        assert response.status_code == 200

        # Read the first event (should be an error event)
        content = b""
        for chunk in response.iter_bytes():
            content += chunk
            if b"\n\n" in content:  # End of first event
                break

        text = content.decode('utf-8')
        assert "event: error" in text
        assert "Job not found" in text
