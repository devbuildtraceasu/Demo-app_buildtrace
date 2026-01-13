#!/bin/bash
# Check for job processing logs and Gemini block extraction

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"

echo "============================================"
echo "  Checking Job Processing Logs"
echo "============================================"
echo ""

echo "1. Recent job activity (last 2 hours):"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"job\" OR textPayload=~\"sheet\" OR textPayload=~\"block\" OR jsonPayload.message=~\"job\" OR jsonPayload.message=~\"sheet\" OR jsonPayload.message=~\"block\")" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "2. Gemini-related logs:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"Gemini\" OR textPayload=~\"gemini\" OR textPayload=~\"Segment\" OR textPayload=~\"Extract\" OR jsonPayload.message=~\"Gemini\" OR jsonPayload.message=~\"Segment\" OR jsonPayload.message=~\"Extract\")" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "3. Errors and warnings:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (severity>=ERROR OR severity>=WARNING)" \
  --limit=30 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "4. All recent worker logs (last 50 entries):"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h
