# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /service

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ca-certificates \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install uv (standalone, no pip required)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project configuration and lock file
# To update: run `uv lock --upgrade` then rebuild
COPY pyproject.toml uv.lock ./

# Install dependencies (system-wide, no venv needed in container)
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

CMD ["uv", "run", "--quiet", "python", "-m", "main"]
