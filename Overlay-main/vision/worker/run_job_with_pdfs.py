#!/usr/bin/env python3
"""Run jobs with the actual PDFs uploaded to MinIO.

This script creates test data and publishes jobs to process the uploaded PDFs.
Uses raw SQL to match the actual database schema (Prisma).
"""

import os
import sys
import json
from datetime import UTC, datetime

# Set emulator host before importing google.cloud
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"

from google.cloud import pubsub_v1
from sqlalchemy import text

# Add parent directory to path
sys.path.insert(0, '/Users/ashishrajshekhar/Downloads/Overlay-main/vision/worker')

from clients.db import get_session
from jobs.types import JobType
from jobs.envelope import build_job_envelope
from utils.id_utils import generate_cuid

PROJECT_ID = "local-dev"
TOPIC_NAME = "vision"


def create_all_data():
    """Create project, drawings, and jobs using raw SQL to match actual DB schema."""
    with get_session() as session:
        now = datetime.now(UTC)
        
        # Generate IDs
        project_id = generate_cuid()
        drawing_old_id = generate_cuid()
        drawing_new_id = generate_cuid()
        job_old_id = generate_cuid()
        job_new_id = generate_cuid()
        
        # 1. Create project (matches Prisma schema)
        session.execute(
            text("""
                INSERT INTO projects (id, created_at, updated_at, organization_id, name, deleted_at)
                VALUES (:id, :created_at, :updated_at, :organization_id, :name, :deleted_at)
            """),
            {
                "id": project_id,
                "created_at": now,
                "updated_at": now,
                "organization_id": "test-org-001",
                "name": "Test Project",
                "deleted_at": None,
            }
        )
        
        # 2. Create drawings (matches Prisma schema)
        session.execute(
            text("""
                INSERT INTO drawings (id, created_at, updated_at, project_id, filename, name, uri, deleted_at)
                VALUES (:id, :created_at, :updated_at, :project_id, :filename, :name, :uri, :deleted_at)
            """),
            {
                "id": drawing_old_id,
                "created_at": now,
                "updated_at": now,
                "project_id": project_id,
                "filename": "A-111_old.pdf",
                "name": "A-111 Old",
                "uri": "s3://overlay-uploads/A-111_old.pdf",
                "deleted_at": None,
            }
        )
        
        session.execute(
            text("""
                INSERT INTO drawings (id, created_at, updated_at, project_id, filename, name, uri, deleted_at)
                VALUES (:id, :created_at, :updated_at, :project_id, :filename, :name, :uri, :deleted_at)
            """),
            {
                "id": drawing_new_id,
                "created_at": now,
                "updated_at": now,
                "project_id": project_id,
                "filename": "A-111_new.pdf",
                "name": "A-111 New",
                "uri": "s3://overlay-uploads/A-111_new.pdf",
                "deleted_at": None,
            }
        )
        
        # 3. Create jobs (matches Prisma schema - NO organization_id, NO actor_id)
        job_old_payload = json.dumps({"drawingId": drawing_old_id})
        job_old_events = json.dumps([{
            "id": generate_cuid(),
            "jobType": JobType.DRAWING_PREPROCESS,
            "jobId": job_old_id,
            "status": "Queued",
            "eventType": "created",
            "createdAt": now.isoformat(),
            "drawingId": drawing_old_id,
        }])
        
        session.execute(
            text("""
                INSERT INTO jobs (id, created_at, updated_at, project_id, parent_id, target_type, target_id, type, status, payload, events, organization_id, actor_id)
                VALUES (:id, :created_at, :updated_at, :project_id, :parent_id, :target_type, :target_id, :type, :status, CAST(:payload AS jsonb), CAST(:events AS jsonb), :organization_id, :actor_id)
            """),
            {
                "id": job_old_id,
                "created_at": now,
                "updated_at": now,
                "project_id": project_id,
                "parent_id": None,
                "target_type": "drawing",
                "target_id": drawing_old_id,
                "type": JobType.DRAWING_PREPROCESS,
                "status": "Queued",
                "payload": job_old_payload,
                "events": job_old_events,
                "organization_id": "test-org-001",
                "actor_id": None,
            }
        )
        
        job_new_payload = json.dumps({"drawingId": drawing_new_id})
        job_new_events = json.dumps([{
            "id": generate_cuid(),
            "jobType": JobType.DRAWING_PREPROCESS,
            "jobId": job_new_id,
            "status": "Queued",
            "eventType": "created",
            "createdAt": now.isoformat(),
            "drawingId": drawing_new_id,
        }])
        
        session.execute(
            text("""
                INSERT INTO jobs (id, created_at, updated_at, project_id, parent_id, target_type, target_id, type, status, payload, events, organization_id, actor_id)
                VALUES (:id, :created_at, :updated_at, :project_id, :parent_id, :target_type, :target_id, :type, :status, CAST(:payload AS jsonb), CAST(:events AS jsonb), :organization_id, :actor_id)
            """),
            {
                "id": job_new_id,
                "created_at": now,
                "updated_at": now,
                "project_id": project_id,
                "parent_id": None,
                "target_type": "drawing",
                "target_id": drawing_new_id,
                "type": JobType.DRAWING_PREPROCESS,
                "status": "Queued",
                "payload": job_new_payload,
                "events": job_new_events,
                "organization_id": "test-org-001",
                "actor_id": None,
            }
        )
        
        session.commit()
        
        print(f"✅ Created test data:")
        print(f"   Project ID: {project_id}")
        print(f"   Drawing (Old): {drawing_old_id} - A-111_old.pdf")
        print(f"   Drawing (New): {drawing_new_id} - A-111_new.pdf")
        print(f"   Job (Old): {job_old_id}")
        print(f"   Job (New): {job_new_id}")
        
        return {
            "project_id": project_id,
            "drawing_old_id": drawing_old_id,
            "drawing_new_id": drawing_new_id,
            "job_old_id": job_old_id,
            "job_new_id": job_new_id,
        }


def publish_job(job_id: str, drawing_id: str, drawing_name: str):
    """Publish a drawing preprocessing job message to Pub/Sub."""
    envelope = build_job_envelope(
        job_type=JobType.DRAWING_PREPROCESS,
        job_id=job_id,
        payload={"drawingId": drawing_id},
    )
    
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    
    data = json.dumps(envelope).encode("utf-8")
    future = publisher.publish(
        topic_path, 
        data, 
        type=JobType.DRAWING_PREPROCESS,
        id=job_id
    )
    
    message_id = future.result(timeout=10.0)
    print(f"   ✅ Published job for {drawing_name}")
    print(f"      Job ID: {job_id}")
    print(f"      Pub/Sub Message ID: {message_id}")
    return message_id


if __name__ == "__main__":
    try:
        print("Creating project, drawings, and jobs...")
        data = create_all_data()
        
        print("\n📤 Publishing jobs to Pub/Sub...")
        print("\n1. Processing A-111_old.pdf...")
        publish_job(data["job_old_id"], data["drawing_old_id"], "A-111_old.pdf")
        
        print("\n2. Processing A-111_new.pdf...")
        publish_job(data["job_new_id"], data["drawing_new_id"], "A-111_new.pdf")
        
        print("\n✨ Done! Watch your worker terminal for processing logs.")
        print(f"\n💡 IDs saved:")
        print(f"   Drawing Old: {data['drawing_old_id']}")
        print(f"   Drawing New: {data['drawing_new_id']}")
        print(f"\n   After both drawings are processed, you can create an overlay job")
        print(f"   to compare them.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
