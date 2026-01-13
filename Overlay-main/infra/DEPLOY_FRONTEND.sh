#!/bin/bash
# Deploy BuildTrace Frontend to Cloud Run

set -e

# Configuration
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
REPO="buildtrace"
SERVICE_NAME="buildtrace-frontend"
API_URL="https://buildtrace-api-okidmickfa-uc.a.run.app"

echo "============================================"
echo "  Deploying BuildTrace Frontend"
echo "============================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "API URL: $API_URL"
echo ""

# Go to frontend directory (Build-TraceFlow root)
cd "$(dirname "$0")/../../Build-TraceFlow"
echo "Working directory: $(pwd)"

# Generate unique tag with timestamp
TAG="v$(date +%Y%m%d%H%M%S)"
IMAGE_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend:${TAG}"
LATEST_TAG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/frontend:latest"

# Build Docker image with API URL as build arg (no cache to ensure fresh build)
# Ensure API URL includes /api suffix for proper routing
API_URL_WITH_SUFFIX="${API_URL%/}/api"
echo ""
echo "Step 1: Building Docker image (AMD64) with tag ${TAG}..."
echo "Using API URL: $API_URL_WITH_SUFFIX"
docker build --platform linux/amd64 --no-cache \
  --build-arg VITE_API_URL=$API_URL_WITH_SUFFIX \
  -t $IMAGE_TAG \
  -t $LATEST_TAG \
  .

# Push to Artifact Registry
echo ""
echo "Step 2: Pushing to Artifact Registry..."
docker push $IMAGE_TAG
docker push $LATEST_TAG

# Deploy to Cloud Run using the unique tag
echo ""
echo "Step 3: Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_TAG \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --set-env-vars="NODE_ENV=production"

# Get the URL
echo ""
echo "============================================"
echo "  Frontend Deployed!"
echo "============================================"
FRONTEND_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format='value(status.url)')
echo ""
echo "Frontend URL: $FRONTEND_URL"
echo ""
echo "Your app is now live!"
