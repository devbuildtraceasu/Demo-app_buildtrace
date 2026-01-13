#!/bin/bash
# Comprehensive log checking with simpler queries

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"

echo "============================================"
echo "  Comprehensive Worker Log Check"
echo "============================================"
echo ""

echo "1. ALL worker logs (any text, last 2 hours):"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=100 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "2. Check Pub/Sub subscription activity:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"subscription\" OR textPayload=~\"pubsub\" OR textPayload=~\"message\" OR textPayload=~\"queue\")" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "3. Check API logs for job publishing:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND (textPayload=~\"publish\" OR textPayload=~\"Pub/Sub\" OR textPayload=~\"job\" OR jsonPayload.message=~\"publish\")" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "4. Check for any errors:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND (resource.labels.service_name=buildtrace-overlay-worker OR resource.labels.service_name=buildtrace-api) AND severity>=ERROR" \
  --limit=30 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h
