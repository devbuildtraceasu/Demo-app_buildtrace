#!/usr/bin/env python3
"""Generate overlay comparing blocks from A-111_old vs A-111_new."""

import os
import sys
import json
from datetime import UTC, datetime

os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"

from google.cloud import pubsub_v1
from sqlalchemy import text

sys.path.insert(0, '/Users/ashishrajshekhar/Downloads/Overlay-main/vision/worker')

from clients.db import get_session
from jobs.types import JobType
from jobs.envelope import build_job_envelope
from utils.id_utils import generate_cuid

PROJECT_ID = "local-dev"
TOPIC_NAME = "vision"


def get_blocks_for_drawings():
    """Get blocks for the two most recent drawings, grouped by drawing."""
    with get_session() as session:
        result = session.execute(
            text("""
                SELECT d.id as drawing_id, d.name as drawing_name,
                       s.id as sheet_id, s.index as sheet_index,
                       b.id as block_id, b.type as block_type, b.description, b.uri
                FROM drawings d
                JOIN sheets s ON s.drawing_id = d.id AND s.deleted_at IS NULL
                JOIN blocks b ON b.sheet_id = s.id AND b.deleted_at IS NULL
                WHERE d.deleted_at IS NULL
                ORDER BY d.created_at DESC, s.index, b.type
            """)
        )
        rows = result.fetchall()
        
        # Group by drawing
        drawings = {}
        for row in rows:
            did = row[0]
            if did not in drawings:
                drawings[did] = {"name": row[1], "sheets": {}, "blocks": []}
            drawings[did]["blocks"].append({
                "block_id": row[4],
                "sheet_id": row[2],
                "type": row[5],
                "description": row[6],
                "uri": row[7],
            })
        
        return drawings


def find_matching_blocks(drawings: dict):
    """Find matching blocks between the two most recent drawings."""
    drawing_ids = list(drawings.keys())
    if len(drawing_ids) < 2:
        raise ValueError("Need at least 2 drawings with blocks")
    
    new_drawing_id = drawing_ids[0]  # Most recent
    old_drawing_id = drawing_ids[1]  # Second most recent
    
    new_blocks = drawings[new_drawing_id]["blocks"]
    old_blocks = drawings[old_drawing_id]["blocks"]
    
    print(f"\n📊 Block counts:")
    print(f"   Old drawing ({drawings[old_drawing_id]['name']}): {len(old_blocks)} blocks")
    print(f"   New drawing ({drawings[new_drawing_id]['name']}): {len(new_blocks)} blocks")
    
    # Match blocks by type (for simplicity, match same type blocks)
    matches = []
    for old_block in old_blocks:
        for new_block in new_blocks:
            # Match by type - for architectural drawings, compare same block types
            if old_block["type"] == new_block["type"] and old_block["uri"] and new_block["uri"]:
                matches.append({
                    "block_a_id": old_block["block_id"],
                    "block_b_id": new_block["block_id"],
                    "type": old_block["type"],
                    "sheet_a_id": old_block["sheet_id"],
                    "sheet_b_id": new_block["sheet_id"],
                    "drawing_a_id": old_drawing_id,
                    "drawing_b_id": new_drawing_id,
                })
                break  # One match per old block
    
    return matches, old_drawing_id, new_drawing_id


def create_overlay_job(match: dict):
    """Create an overlay record and job for a block pair."""
    with get_session() as session:
        now = datetime.now(UTC)
        overlay_id = generate_cuid()
        job_id = generate_cuid()
        
        # Get project_id from one of the blocks
        result = session.execute(
            text("""
                SELECT s.drawing_id, d.project_id 
                FROM blocks b
                JOIN sheets s ON s.id = b.sheet_id
                JOIN drawings d ON d.id = s.drawing_id
                WHERE b.id = :id
            """),
            {"id": match["block_a_id"]}
        )
        row = result.fetchone()
        project_id = row[1] if row else None
        
        # Create overlay record (links two blocks)
        session.execute(
            text("""
                INSERT INTO overlays (id, created_at, updated_at, block_a_id, block_b_id)
                VALUES (:id, :created_at, :updated_at, :block_a_id, :block_b_id)
            """),
            {
                "id": overlay_id,
                "created_at": now,
                "updated_at": now,
                "block_a_id": match["block_a_id"],
                "block_b_id": match["block_b_id"],
            }
        )
        
        # Create job record
        job_payload = json.dumps({
            "block_a_id": match["block_a_id"],
            "block_b_id": match["block_b_id"],
            "sheet_a_id": match["sheet_a_id"],
            "sheet_b_id": match["sheet_b_id"],
            "drawing_a_id": match["drawing_a_id"],
            "drawing_b_id": match["drawing_b_id"],
        })
        
        session.execute(
            text("""
                INSERT INTO jobs (id, created_at, updated_at, project_id, 
                    target_type, target_id, type, status, payload, organization_id)
                VALUES (:id, :created_at, :updated_at, :project_id,
                    :target_type, :target_id, :type, :status, CAST(:payload AS jsonb), :organization_id)
            """),
            {
                "id": job_id,
                "created_at": now,
                "updated_at": now,
                "project_id": project_id,
                "target_type": "overlay",
                "target_id": overlay_id,
                "type": JobType.BLOCK_OVERLAY_GENERATE,
                "status": "Queued",
                "payload": job_payload,
                "organization_id": "test-org-001",
            }
        )
        
        # Update overlay with job_id
        session.execute(
            text("UPDATE overlays SET job_id = :job_id WHERE id = :id"),
            {"job_id": job_id, "id": overlay_id}
        )
        
        session.commit()
        return overlay_id, job_id


def publish_overlay_job(job_id: str, match: dict):
    """Publish the overlay generation job."""
    envelope = build_job_envelope(
        job_type=JobType.BLOCK_OVERLAY_GENERATE,
        job_id=job_id,
        payload={
            "block_a_id": match["block_a_id"],
            "block_b_id": match["block_b_id"],
            "sheet_a_id": match["sheet_a_id"],
            "sheet_b_id": match["sheet_b_id"],
            "drawing_a_id": match["drawing_a_id"],
            "drawing_b_id": match["drawing_b_id"],
        },
    )
    
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_NAME)
    
    data = json.dumps(envelope).encode("utf-8")
    future = publisher.publish(topic_path, data, type=JobType.BLOCK_OVERLAY_GENERATE, id=job_id)
    return future.result(timeout=10.0)


if __name__ == "__main__":
    print("🔍 Finding blocks from drawings...")
    drawings = get_blocks_for_drawings()
    
    if len(drawings) < 2:
        print("❌ Need at least 2 drawings with blocks to compare")
        sys.exit(1)
    
    print(f"   Found {len(drawings)} drawings with blocks")
    
    matches, old_id, new_id = find_matching_blocks(drawings)
    
    if not matches:
        print("❌ No matching blocks found between drawings")
        print("\n💡 Blocks may have different types. Showing available blocks:")
        for did, dinfo in drawings.items():
            print(f"\n   {dinfo['name']}:")
            for b in dinfo['blocks'][:5]:
                print(f"      - {b['type']}: {b['description'][:50] if b['description'] else 'no description'}...")
        sys.exit(1)
    
    print(f"\n✅ Found {len(matches)} matching block pairs to compare:")
    for m in matches[:5]:  # Show first 5
        print(f"   - {m['type']}")
    if len(matches) > 5:
        print(f"   ... and {len(matches) - 5} more")
    
    print("\n📝 Creating overlay records and jobs...")
    created_jobs = []
    for match in matches:
        overlay_id, job_id = create_overlay_job(match)
        created_jobs.append((job_id, overlay_id, match))
        print(f"   ✓ {match['type']}: overlay={overlay_id[:12]}...")
    
    print("\n📤 Publishing overlay jobs...")
    for job_id, overlay_id, match in created_jobs:
        msg_id = publish_overlay_job(job_id, match)
        print(f"   ✓ Published job {job_id[:12]}... (msg={msg_id})")
    
    print(f"\n✨ Done! Published {len(created_jobs)} overlay jobs.")
    print("   Watch your worker terminal for overlay generation.")
    print("\n   Results will be stored in:")
    print("   - Database: overlays table (uri, addition_uri, deletion_uri)")
    print("   - MinIO: block-overlays/, block-additions/, block-deletions/")
