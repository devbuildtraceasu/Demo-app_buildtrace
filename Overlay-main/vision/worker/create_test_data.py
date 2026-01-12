#!/usr/bin/env python3
"""Script to create test data in the database for testing jobs."""

import sys
from datetime import UTC, datetime

# Add parent directory to path to import models
sys.path.insert(0, '/Users/ashishrajshekhar/Downloads/Overlay-main/vision/worker')

from clients.db import get_session
from models import Drawing, Project
from utils.id_utils import generate_cuid


def create_test_project():
    """Create a test project."""
    with get_session() as session:
        project_id = generate_cuid()
        project = Project(
            id=project_id,
            organization_id="test-org-001",
            deleted_at=None,
        )
        session.add(project)
        session.commit()
        session.refresh(project)
        print(f"✅ Created project: {project_id}")
        return project_id


def create_test_drawing(project_id: str, pdf_uri: str = None):
    """Create a test drawing."""
    if pdf_uri is None:
        # Default test PDF URI (you'll need to upload a PDF to MinIO first)
        pdf_uri = "s3://overlay-uploads/test/test.pdf"
    
    with get_session() as session:
        drawing_id = generate_cuid()
        drawing = Drawing(
            id=drawing_id,
            project_id=project_id,
            filename="test.pdf",
            name="Test Drawing",
            uri=pdf_uri,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            deleted_at=None,
        )
        session.add(drawing)
        session.commit()
        session.refresh(drawing)
        print(f"✅ Created drawing: {drawing_id}")
        print(f"   URI: {pdf_uri}")
        return drawing_id


if __name__ == "__main__":
    print("Creating test data...")
    
    # Create project
    project_id = create_test_project()
    
    # Create drawing
    # You can pass a custom URI as second argument
    pdf_uri = sys.argv[1] if len(sys.argv) > 1 else None
    drawing_id = create_test_drawing(project_id, pdf_uri)
    
    print(f"\n📋 Test data created:")
    print(f"   Project ID: {project_id}")
    print(f"   Drawing ID: {drawing_id}")
    print(f"\n💡 Next step: Publish a job using:")
    print(f"   uv run python test_publish_job.py {drawing_id}")

