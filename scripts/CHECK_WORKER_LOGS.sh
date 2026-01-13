#!/bin/bash
# Check worker logs for Gemini block extraction

echo "============================================"
echo "  Checking Worker Logs for Gemini Block Extraction"
echo "============================================"
echo ""

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"

echo "Fetching recent worker logs..."
echo ""

# Get logs with Gemini-related content
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"Gemini\" OR textPayload=~\"gemini\" OR textPayload=~\"block\" OR textPayload=~\"segment\" OR jsonPayload.message=~\"Gemini\" OR jsonPayload.message=~\"block\")" \
  --limit=100 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=1h

echo ""
echo "============================================"
echo "  Recent Worker Activity (All Logs)"
echo "============================================"
echo ""

# Get all recent logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=1h

echo ""
echo "To see more detailed logs, run:"
echo "  gcloud logging read \"resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker\" --limit=200 --project=$PROJECT_ID --format=json | jq"
