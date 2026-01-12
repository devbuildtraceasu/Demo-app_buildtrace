# BuildTrace API Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv for fast dependency installation
RUN pip install uv

# Copy API project files
COPY api/pyproject.toml ./
COPY api/ ./api/

# Install dependencies
RUN uv pip install --system fastapi uvicorn[standard] python-multipart \
    sqlmodel psycopg2-binary google-cloud-storage boto3 google-cloud-pubsub \
    python-jose[cryptography] passlib[bcrypt] pydantic-settings python-dotenv httpx numpy \
    email-validator

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

