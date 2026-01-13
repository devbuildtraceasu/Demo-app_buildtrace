#!/bin/bash
# Comprehensive diagnosis of job processing

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"

echo "============================================"
echo "  Job Processing Diagnosis"
echo "============================================"
echo ""

echo "1. Check if drawing jobs were created (API logs):"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND (textPayload=~\"drawing\" OR textPayload=~\"publish\" OR jsonPayload.message=~\"drawing\")" \
  --limit=30 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=4h

echo ""
echo "2. Check worker startup and connection (last 2 hours):"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=100 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h \
  | head -50

echo ""
echo "3. Check for drawing job processing:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"Drawing\" OR textPayload=~\"drawing\" OR textPayload=~\"PDF\" OR textPayload=~\"Convert\")" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=4h

echo ""
echo "4. Check for sheet job processing (Gemini block extraction):"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"Sheet\" OR textPayload=~\"sheet\" OR textPayload=~\"Analyze\" OR textPayload=~\"Segment\" OR textPayload=~\"Block\")" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=4h

echo ""
echo "5. Check Pub/Sub subscription status:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"subscription\" OR textPayload=~\"ready\" OR textPayload=~\"connected\")" \
  --limit=20 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=2h

echo ""
echo "6. Check for ANY errors:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND (resource.labels.service_name=buildtrace-overlay-worker OR resource.labels.service_name=buildtrace-api) AND severity>=ERROR" \
  --limit=30 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=4h

echo ""
echo "============================================"
echo "  Next Steps:"
echo "============================================"
echo "If no logs found:"
echo "  1. Check if drawings were actually uploaded (check API/database)"
echo "  2. Check if drawing preprocessing jobs were created"
echo "  3. Verify Pub/Sub topic and subscription are configured correctly"
echo "  4. Check worker service is running and has proper permissions"
