#!/usr/bin/env python3
"""Complete script to create test data and publish a job."""

import os
import sys

# Set emulator host before importing google.cloud
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"

import json
import uuid
from datetime import UTC, datetime

from google.cloud import pubsub_v1

# Add parent directory to path to import models
sys.path.insert(0, '/Users/ashishrajshekhar/Downloads/Overlay-main/vision/worker')

from clients.db import get_session
from models import Drawing, Project
from utils.id_utils import generate_cuid

PROJECT_ID = "local-dev"
TOPIC_NAME = "vision"


def create_test_data(pdf_uri: str = None):
    """Create test project and drawing."""
    if pdf_uri is None:
        pdf_uri = "s3://overlay-uploads/test/test.pdf"
    
    with get_session() as session:
        # Create project
        project_id = generate_cuid()
        project = Project(
            id=project_id,
            organization_id="test-org-001",
            deleted_at=None,
        )
        session.add(project)
        
        # Create drawing
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
        
        print(f"✅ Created test data:")
        print(f"   Project ID: {project_id}")
        print(f"   Drawing ID: {drawing_id}")
        return drawing_id


def publish_job(drawing_id: str):
    """Publish a drawing preprocessing job."""
    job_id = f"test-{uuid.uuid4().hex[:8]}"
    
    message = {
        "type": "vision.drawing.preprocess",
        "jobId": job_id,
        "payload": {
            "drawingId": drawing_id
        }
    }
    
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    
    data = json.dumps(message).encode("utf-8")
    future = publisher.publish(
        topic_path, 
        data, 
        type="vision.drawing.preprocess",
        id=job_id
    )
    
    message_id = future.result(timeout=10.0)
    print(f"\n✅ Published job!")
    print(f"   Job ID: {job_id}")
    print(f"   Drawing ID: {drawing_id}")
    print(f"   Pub/Sub Message ID: {message_id}")
    print(f"\n📋 Check your worker logs to see it process the job.")


if __name__ == "__main__":
    pdf_uri = sys.argv[1] if len(sys.argv) > 1 else None
    
    try:
        print("Creating test data...")
        drawing_id = create_test_data(pdf_uri)
        
        print("\nPublishing job...")
        publish_job(drawing_id)
        
        print("\n✨ Done! Watch your worker terminal for processing logs.")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

