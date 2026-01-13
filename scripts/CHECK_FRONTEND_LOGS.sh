#!/bin/bash
# Check Cloud Run frontend logs for deployment errors

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"
REVISION="${1:-buildtrace-frontend-00013-9w5}"

echo "============================================"
echo "  Frontend Deployment Error Logs"
echo "============================================"
echo ""

echo "Checking logs for revision: $REVISION"
echo ""

# Get all logs for this revision
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-frontend AND resource.labels.revision_name=$REVISION" \
  --limit=100 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=1h

echo ""
echo "============================================"
echo "  Recent Frontend Service Logs (All Revisions)"
echo "============================================"
echo ""

gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-frontend" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "============================================"
echo "  Errors Only"
echo "============================================"
echo ""

gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-frontend AND severity>=ERROR" \
  --limit=30 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h
