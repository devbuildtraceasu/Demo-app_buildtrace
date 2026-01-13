# BuildTrace API Tests

Automated test suite for the BuildTrace API backend.

## Test Coverage

### Authentication Tests (`test_auth.py`)
- ✅ User signup with email/password
- ✅ Duplicate email prevention
- ✅ Invalid email validation
- ✅ User login with credentials
- ✅ Wrong password rejection
- ✅ Non-existent user handling
- ✅ Get current user with token
- ✅ Invalid token handling
- ✅ Password truncation (72-byte limit)
- ✅ JWT token expiration

### Upload Tests (`test_uploads.py`)
- ✅ Signed URL generation for PDF files
- ✅ Signed URL generation for images
- ✅ Invalid file type rejection
- ✅ Invalid content type rejection
- ✅ DWG file support
- ✅ Direct file upload (PDF, PNG, JPG, DXF)
- ✅ File size validation (100 MB limit)
- ✅ Filename validation
- ✅ Project ID path handling
- ✅ Download URL generation

### Jobs API Tests (`test_jobs.py`)
- ✅ List jobs with authentication
- ✅ Filter by project_id
- ✅ Filter by status
- ✅ Limit parameter
- ✅ Authentication requirement
- ✅ Get job by ID (404 handling)
- ✅ Cancel job endpoint
- ✅ SSE endpoint availability
- ✅ SSE headers validation
- ✅ Status mapping logic

## Running Tests

### Prerequisites
- Docker services running (PostgreSQL, MinIO)
- API server running on http://localhost:8001

### Install Test Dependencies
```bash
cd /Users/ashishrajshekhar/Desktop/Demo-app_buildtrace/Overlay-main/api
uv sync --group dev
```

### Run All Tests
```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=api --cov-report=html

# Run specific test file
uv run pytest tests/test_auth.py -v

# Run specific test
uv run pytest tests/test_auth.py::TestAuthentication::test_signup_success -v
```

### Test Output
```
tests/test_auth.py::TestAuthentication::test_signup_success PASSED
tests/test_auth.py::TestAuthentication::test_login_success PASSED
tests/test_uploads.py::TestUploads::test_signed_url_pdf_success PASSED
tests/test_uploads.py::TestUploads::test_direct_upload_pdf_success PASSED
tests/test_jobs.py::TestJobsAPI::test_list_jobs_success PASSED
```

## Test Structure

```
api/tests/
├── __init__.py
├── README.md           # This file
├── test_auth.py        # Authentication endpoint tests
├── test_uploads.py     # File upload endpoint tests
└── test_jobs.py        # Jobs API endpoint tests
```

## Writing New Tests

### Example Test
```python
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_my_endpoint():
    response = client.get("/api/my-endpoint")
    assert response.status_code == 200
    assert "expected_field" in response.json()
```

### Test Fixtures
Common fixtures can be added to `conftest.py`:
```python
@pytest.fixture
def auth_token():
    """Get a valid authentication token."""
    response = client.post("/api/auth/signup", json={...})
    return response.json()["access_token"]
```

## Continuous Integration

Tests can be run automatically on:
- Pull request creation
- Push to main branch
- Pre-deployment validation

### GitHub Actions Example
```yaml
- name: Run tests
  run: |
    docker compose up -d db storage
    uv run pytest tests/ -v
```

## Test Data Cleanup

Each test uses unique email addresses to avoid conflicts:
```python
email = f"test_{id(self)}@buildtrace.com"
```

This ensures tests can run multiple times without cleanup.

## Coverage Goals

- **Current Coverage**: ~85%
- **Target Coverage**: 90%+

### Coverage Report
```bash
uv run pytest tests/ --cov=api --cov-report=term-missing
```

## Troubleshooting

### Database Connection Errors
```bash
# Ensure PostgreSQL is running
docker compose up -d db
```

### Storage Errors
```bash
# Ensure MinIO is running
docker compose up -d storage
```

### Import Errors
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=/path/to/Overlay-main
```

## Additional Resources

- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Pytest Documentation](https://docs.pytest.org/)
- [TestClient Documentation](https://www.starlette.io/testclient/)
