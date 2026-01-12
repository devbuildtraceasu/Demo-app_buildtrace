"""FastAPI orchestrator - Central API layer for BuildTrace.

This module provides the main FastAPI application that:
- Handles file uploads to GCS
- Submits jobs to Pub/Sub
- Provides REST endpoints for CRUD operations
- Offers WebSocket for real-time job status updates
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.routes import alignment, analysis, auth, comparisons, drawings, google_auth, jobs, projects, uploads

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Starting BuildTrace API server...")
    yield
    logger.info("Shutting down BuildTrace API server...")


app = FastAPI(
    title="BuildTrace API",
    description="Central API for construction drawing overlay comparison",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(projects.router, prefix="/api/projects", tags=["Projects"])
app.include_router(drawings.router, prefix="/api/drawings", tags=["Drawings"])
app.include_router(comparisons.router, prefix="/api/comparisons", tags=["Comparisons"])
app.include_router(uploads.router, prefix="/api/uploads", tags=["Uploads"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])
app.include_router(alignment.router, prefix="/api/alignment", tags=["Alignment"])
app.include_router(google_auth.router, prefix="/api/auth", tags=["Google OAuth"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["AI Analysis"])


@app.get("/health")
async def health_check():
    """Health check endpoint for load balancer."""
    return {"status": "healthy", "service": "buildtrace-api"}


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "BuildTrace API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
    )

