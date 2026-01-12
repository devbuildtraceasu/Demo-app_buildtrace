#!/bin/bash
# Build and push Docker images to Artifact Registry
# Builds for AMD64 (linux/amd64) for GCP Cloud Run

set -e

# Get current project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
REGION="us-central1"
REPO="buildtrace"
PLATFORM="linux/amd64"

echo "============================================"
echo "  Building and Pushing Docker Images"
echo "============================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Repository: $REPO"
echo "Platform: $PLATFORM (for GCP Cloud Run)"
echo ""

# Configure Docker to authenticate with Artifact Registry
echo "Step 1: Configuring Docker authentication..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet

# Go to the Overlay-main directory (parent of infra)
cd "$(dirname "$0")/.."
echo "Working directory: $(pwd)"
echo ""

# Build and push API image
echo "Step 2: Building API image (AMD64)..."
docker build --platform ${PLATFORM} \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest \
  -f api/Dockerfile .

echo ""
echo "Step 3: Pushing API image..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest

# Build and push Worker image
echo ""
echo "Step 4: Building Worker image (AMD64)..."
docker build --platform ${PLATFORM} \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/overlay-worker:latest \
  vision/worker

echo ""
echo "Step 5: Pushing Worker image..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/overlay-worker:latest

echo ""
echo "============================================"
echo "  Images Built and Pushed!"
echo "============================================"
echo ""
echo "API Image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/api:latest"
echo "Worker Image: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/overlay-worker:latest"
echo ""
echo "Now run: cd terraform && terraform apply"
