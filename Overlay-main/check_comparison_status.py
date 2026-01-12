#!/usr/bin/env python3
"""Quick script to check the status of recent comparisons and jobs."""

import os
import sys
from datetime import datetime, timezone

# Add the API directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "api"))

from sqlmodel import Session, create_engine, select
from api.config import settings

# Create database engine
engine = create_engine(settings.database_url, echo=False)

print("=" * 80)
print("COMPARISON STATUS CHECK")
print("=" * 80)
print()

with Session(engine) as session:
    # Import models
    from api.routes.comparisons import Overlay
    from api.routes.jobs import Job
    
    # Get most recent overlays
    print("📊 RECENT COMPARISONS (Last 5):")
    print("-" * 80)
    statement = select(Overlay).where(Overlay.deleted_at.is_(None)).order_by(Overlay.created_at.desc()).limit(5)
    overlays = session.exec(statement).all()
    
    if not overlays:
        print("No comparisons found.")
    else:
        for overlay in overlays:
            print(f"\n🔹 Overlay ID: {overlay.id}")
            print(f"   Block A: {overlay.block_a_id}")
            print(f"   Block B: {overlay.block_b_id}")
            print(f"   Job ID: {overlay.job_id or 'None'}")
            print(f"   URI: {overlay.uri or 'None (not completed)'}")
            print(f"   Created: {overlay.created_at}")
            
            # Check associated job
            if overlay.job_id:
                job = session.get(Job, overlay.job_id)
                if job:
                    print(f"   Job Status: {job.status}")
                    print(f"   Job Type: {job.type}")
                    print(f"   Job Updated: {job.updated_at}")
                    
                    # Check for errors in events
                    if job.events:
                        failed_events = [e for e in job.events if e.get("event_type") == "failed" or e.get("status") == "Failed"]
                        if failed_events:
                            print(f"   ⚠️  FAILED EVENTS:")
                            for event in failed_events:
                                metadata = event.get("metadata", {})
                                error = metadata.get("error") or metadata.get("errorMessage", "Unknown error")
                                print(f"      - {error}")
                else:
                    print(f"   ⚠️  Job {overlay.job_id} not found in database!")
            else:
                print(f"   ⚠️  No job ID assigned!")
    
    print()
    print("=" * 80)
    print("📋 RECENT JOBS (Last 5):")
    print("-" * 80)
    
    statement = select(Job).where(Job.type == "vision.block.overlay.generate").order_by(Job.created_at.desc()).limit(5)
    jobs = session.exec(statement).all()
    
    if not jobs:
        print("No overlay generation jobs found.")
    else:
        for job in jobs:
            print(f"\n🔹 Job ID: {job.id}")
            print(f"   Status: {job.status}")
            print(f"   Target: {job.target_type} / {job.target_id}")
            print(f"   Created: {job.created_at}")
            print(f"   Updated: {job.updated_at}")
            
            if job.payload:
                block_a = job.payload.get("block_a_id", "N/A")
                block_b = job.payload.get("block_b_id", "N/A")
                print(f"   Blocks: {block_a} → {block_b}")
            
            # Check events for errors
            if job.events:
                print(f"   Events: {len(job.events)}")
                failed_events = [e for e in job.events if e.get("event_type") == "failed" or e.get("status") == "Failed"]
                if failed_events:
                    print(f"   ⚠️  FAILURES:")
                    for event in failed_events:
                        metadata = event.get("metadata", {})
                        error = metadata.get("error") or metadata.get("errorMessage", "Unknown error")
                        error_type = metadata.get("errorType", "Unknown")
                        print(f"      - [{error_type}] {error}")

print()
print("=" * 80)
print("💡 TIP: Check API logs for 'Publishing job' or 'Failed to publish' messages")
print("=" * 80)

