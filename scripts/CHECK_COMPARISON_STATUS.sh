#!/bin/bash
# Check comparison status and job processing

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"
COMPARISON_ID="${1:-c19bb85e051927b3e0711094e}"

echo "============================================"
echo "  Checking Comparison Status"
echo "============================================"
echo ""
echo "Comparison ID: $COMPARISON_ID"
echo ""

# Check API logs for comparison creation
echo "1. Checking API logs for comparison creation:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND (textPayload=~\"$COMPARISON_ID\" OR textPayload=~\"COMPARISON\" OR jsonPayload.message=~\"$COMPARISON_ID\")" \
  --limit=30 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=24h

echo ""
echo "2. Checking if job was published to Pub/Sub:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND (textPayload=~\"Publishing job\" OR textPayload=~\"Successfully published\" OR jsonPayload.message=~\"publish\")" \
  --limit=20 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=24h

echo ""
echo "3. Checking worker logs for job processing:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND (textPayload=~\"overlay\" OR textPayload=~\"block\" OR textPayload=~\"job\" OR jsonPayload.message=~\"overlay\")" \
  --limit=50 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=24h

echo ""
echo "4. Checking for errors:"
echo "----------------------------------------"
gcloud logging read \
  "resource.type=cloud_run_revision AND (resource.labels.service_name=buildtrace-api OR resource.labels.service_name=buildtrace-overlay-worker) AND severity>=ERROR" \
  --limit=30 \
  --project=$PROJECT_ID \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=24h

echo ""
echo "============================================"
echo "  Next Steps:"
echo "============================================"
echo "1. Check if comparison exists in database"
echo "2. Check if job was created and published"
echo "3. Check if worker received the job"
echo "4. Check job status in database"
