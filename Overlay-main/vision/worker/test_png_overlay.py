#!/usr/bin/env python3
"""Test overlay generation with two PNG images directly.

Skips PDF preprocessing - directly uploads PNGs and creates overlay job.
"""

import os
import sys
import json
from datetime import UTC, datetime
from pathlib import Path

os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"

from google.cloud import pubsub_v1
from sqlalchemy import text

sys.path.insert(0, '/Users/ashishrajshekhar/Downloads/Overlay-main/vision/worker')

from clients.db import get_session
from clients.storage import get_storage_client
from jobs.types import JobType
from jobs.envelope import build_job_envelope
from utils.id_utils import generate_cuid

PROJECT_ID = "local-dev"
TOPIC_NAME = "vision"

# Your PNG files
OLD_PNG = "/Users/ashishrajshekhar/Downloads/Overlay-main/my_set/old.png"
NEW_PNG = "/Users/ashishrajshekhar/Downloads/Overlay-main/my_set/new.png"


def upload_png_to_storage(local_path: str, remote_path: str) -> str:
    """Upload a PNG file to MinIO and return the URI."""
    storage = get_storage_client()
    with open(local_path, "rb") as f:
        png_bytes = f.read()
    uri = storage.upload_from_bytes(png_bytes, remote_path, content_type="image/png")
    size_mb = len(png_bytes) / (1024 * 1024)
    print(f"   ✅ Uploaded {Path(local_path).name} ({size_mb:.1f}MB) → {remote_path}")
    return uri


def create_test_data():
    """Create project, drawings, sheets, and blocks for the two PNGs."""
    with get_session() as session:
        now = datetime.now(UTC)
        
        # Generate IDs
        project_id = generate_cuid()
        drawing_old_id = generate_cuid()
        drawing_new_id = generate_cuid()
        sheet_old_id = generate_cuid()
        sheet_new_id = generate_cuid()
        block_old_id = generate_cuid()
        block_new_id = generate_cuid()
        
        # Upload PNGs to storage
        print("\n📤 Uploading PNG files to MinIO...")
        old_uri = upload_png_to_storage(
            OLD_PNG, 
            f"test-overlays/{project_id}/old.png"
        )
        new_uri = upload_png_to_storage(
            NEW_PNG,
            f"test-overlays/{project_id}/new.png"
        )
        
        print("\n📝 Creating database records...")
        
        # Create project
        session.execute(
            text("""
                INSERT INTO projects (id, created_at, updated_at, organization_id, name)
                VALUES (:id, :now, :now, :org_id, :name)
            """),
            {"id": project_id, "now": now, "org_id": "test-org", "name": "PNG Test Project"}
        )
        
        # Create drawings
        for did, name, uri in [(drawing_old_id, "Old Drawing", old_uri), 
                                (drawing_new_id, "New Drawing", new_uri)]:
            session.execute(
                text("""
                    INSERT INTO drawings (id, created_at, updated_at, project_id, filename, name, uri)
                    VALUES (:id, :now, :now, :project_id, :filename, :name, :uri)
                """),
                {"id": did, "now": now, "project_id": project_id, 
                 "filename": f"{name}.png", "name": name, "uri": uri}
            )
        
        # Create sheets
        for sid, did, uri in [(sheet_old_id, drawing_old_id, old_uri),
                              (sheet_new_id, drawing_new_id, new_uri)]:
            session.execute(
                text("""
                    INSERT INTO sheets (id, created_at, updated_at, drawing_id, index, uri)
                    VALUES (:id, :now, :now, :drawing_id, :index, :uri)
                """),
                {"id": sid, "now": now, "drawing_id": did, "index": 0, "uri": uri}
            )
        
        # Create blocks (the actual images to compare)
        for bid, sid, uri, btype in [(block_old_id, sheet_old_id, old_uri, "Plan"),
                                      (block_new_id, sheet_new_id, new_uri, "Plan")]:
            session.execute(
                text("""
                    INSERT INTO blocks (id, created_at, updated_at, sheet_id, type, uri, description)
                    VALUES (:id, :now, :now, :sheet_id, :type, :uri, :description)
                """),
                {"id": bid, "now": now, "sheet_id": sid, "type": btype, 
                 "uri": uri, "description": "Test block from PNG"}
            )
        
        session.commit()
        
        print(f"   ✅ Project: {project_id}")
        print(f"   ✅ Block (old): {block_old_id}")
        print(f"   ✅ Block (new): {block_new_id}")
        
        return {
            "project_id": project_id,
            "block_old_id": block_old_id,
            "block_new_id": block_new_id,
            "sheet_old_id": sheet_old_id,
            "sheet_new_id": sheet_new_id,
            "drawing_old_id": drawing_old_id,
            "drawing_new_id": drawing_new_id,
        }


def create_overlay_job(data: dict):
    """Create overlay record and job."""
    with get_session() as session:
        now = datetime.now(UTC)
        overlay_id = generate_cuid()
        job_id = generate_cuid()
        
        # Create overlay record
        session.execute(
            text("""
                INSERT INTO overlays (id, created_at, updated_at, block_a_id, block_b_id)
                VALUES (:id, :now, :now, :block_a_id, :block_b_id)
            """),
            {
                "id": overlay_id,
                "now": now,
                "block_a_id": data["block_old_id"],
                "block_b_id": data["block_new_id"],
            }
        )
        
        # Create job record
        job_payload = json.dumps({
            "block_a_id": data["block_old_id"],
            "block_b_id": data["block_new_id"],
            "sheet_a_id": data["sheet_old_id"],
            "sheet_b_id": data["sheet_new_id"],
            "drawing_a_id": data["drawing_old_id"],
            "drawing_b_id": data["drawing_new_id"],
        })
        
        session.execute(
            text("""
                INSERT INTO jobs (id, created_at, updated_at, project_id, 
                    target_type, target_id, type, status, payload, organization_id)
                VALUES (:id, :now, :now, :project_id,
                    :target_type, :target_id, :type, :status, CAST(:payload AS jsonb), :org_id)
            """),
            {
                "id": job_id,
                "now": now,
                "project_id": data["project_id"],
                "target_type": "overlay",
                "target_id": overlay_id,
                "type": JobType.BLOCK_OVERLAY_GENERATE,
                "status": "Queued",
                "payload": job_payload,
                "org_id": "test-org",
            }
        )
        
        # Link job to overlay
        session.execute(
            text("UPDATE overlays SET job_id = :job_id WHERE id = :id"),
            {"job_id": job_id, "id": overlay_id}
        )
        
        session.commit()
        
        print(f"\n📋 Created overlay job:")
        print(f"   Overlay ID: {overlay_id}")
        print(f"   Job ID: {job_id}")
        
        return overlay_id, job_id


def publish_job(job_id: str, data: dict):
    """Publish the overlay job to Pub/Sub."""
    envelope = build_job_envelope(
        job_type=JobType.BLOCK_OVERLAY_GENERATE,
        job_id=job_id,
        payload={
            "block_a_id": data["block_old_id"],
            "block_b_id": data["block_new_id"],
            "sheet_a_id": data["sheet_old_id"],
            "sheet_b_id": data["sheet_new_id"],
            "drawing_a_id": data["drawing_old_id"],
            "drawing_b_id": data["drawing_new_id"],
        },
    )
    
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    
    msg_data = json.dumps(envelope).encode("utf-8")
    future = publisher.publish(topic_path, msg_data, type=JobType.BLOCK_OVERLAY_GENERATE, id=job_id)
    msg_id = future.result(timeout=10.0)
    
    print(f"\n📤 Published job to Pub/Sub (msg_id={msg_id})")
    return msg_id


if __name__ == "__main__":
    # Check files exist
    if not os.path.exists(OLD_PNG):
        print(f"❌ File not found: {OLD_PNG}")
        sys.exit(1)
    if not os.path.exists(NEW_PNG):
        print(f"❌ File not found: {NEW_PNG}")
        sys.exit(1)
    
    print("🖼️  Testing overlay with PNG files:")
    print(f"   Old: {OLD_PNG}")
    print(f"   New: {NEW_PNG}")
    
    try:
        # Create test data
        data = create_test_data()
        
        # Create and publish overlay job
        overlay_id, job_id = create_overlay_job(data)
        publish_job(job_id, data)
        
        print("\n✨ Done! Watch your worker terminal for overlay generation.")
        print(f"\n📊 After completion, view results:")
        print(f"   - MinIO: http://localhost:9001 → block-overlays/{overlay_id}.png")
        print(f"   - Prisma: http://localhost:5555 → Overlay table")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

