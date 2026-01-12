#!/usr/bin/env python3
"""Test script to publish a job message to the Pub/Sub topic."""

import json
import os
import sys

# Set emulator host before importing google.cloud
os.environ["PUBSUB_EMULATOR_HOST"] = "localhost:8681"

from google.cloud import pubsub_v1

PROJECT_ID = "local-dev"
TOPIC_NAME = "vision"


def publish_drawing_preprocess_job(drawing_id: str, job_id: str = None):
    """Publish a drawing preprocessing job."""
    if job_id is None:
        import uuid
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
    print(f"✅ Published job message!")
    print(f"   Job ID: {job_id}")
    print(f"   Drawing ID: {drawing_id}")
    print(f"   Pub/Sub Message ID: {message_id}")
    print(f"\n📋 Check your worker logs to see it process the job.")
    return message_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_publish_job.py <drawing_id> [job_id]")
        print("\nExample:")
        print("  python test_publish_job.py test-drawing-123")
        print("\nNote: The drawing_id must exist in your database.")
        sys.exit(1)
    
    drawing_id = sys.argv[1]
    job_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        publish_drawing_preprocess_job(drawing_id, job_id)
    except Exception as e:
        print(f"❌ Error publishing job: {e}")
        sys.exit(1)

