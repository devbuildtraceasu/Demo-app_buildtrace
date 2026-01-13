#!/bin/bash
# Quick script to rebuild and redeploy just the API service

set -e

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"
REGION="us-central1"
REPO="buildtrace"
SERVICE_NAME="buildtrace-api"

echo "============================================"
echo "  Rebuilding and Redeploying API"
echo "============================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Go to Overlay-main directory
cd "$(dirname "$0")/.."
echo "Working directory: $(pwd)"
echo ""

# Configure Docker
echo "Step 1: Configuring Docker authentication..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Build API image
echo ""
echo "Step 2: Building API image..."
docker build --platform linux/amd64 \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest \
  -f api/Dockerfile .

# Push image
echo ""
echo "Step 3: Pushing to Artifact Registry..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest

# Deploy to Cloud Run
echo ""
echo "Step 4: Deploying to Cloud Run..."
gcloud run services update ${SERVICE_NAME} \
  --region=${REGION} \
  --project=${PROJECT_ID} \
  --image=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest

echo ""
echo "============================================"
echo "  ✅ API Redeployed!"
echo "============================================"
echo ""
echo "Wait 1-2 minutes for the new revision to be ready, then test:"
echo "  curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url"
echo ""
