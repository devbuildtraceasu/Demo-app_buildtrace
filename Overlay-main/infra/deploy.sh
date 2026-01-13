#!/bin/bash
# BuildTrace GCP Deployment Script
# This script automates the deployment process to Google Cloud Platform

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-dev}"
REGION="${GCP_REGION:-us-central1}"
TERRAFORM_DIR="infra/terraform"

echo -e "${GREEN}BuildTrace GCP Deployment${NC}"
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo ""

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v terraform &> /dev/null; then
    echo -e "${RED}Error: Terraform not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker not found. Please install it first.${NC}"
    exit 1
fi

# Check if authenticated
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo -e "${YELLOW}Not authenticated with gcloud. Running gcloud auth login...${NC}"
    gcloud auth login
fi

# Set project
echo -e "${YELLOW}Setting GCP project to $PROJECT_ID...${NC}"
gcloud config set project $PROJECT_ID

# Phase 1: Create Terraform state bucket
echo -e "${YELLOW}Phase 1: Creating Terraform state bucket...${NC}"
BUCKET_NAME="buildtrace-terraform-state"
if ! gsutil ls -b "gs://$BUCKET_NAME" &> /dev/null; then
    echo "Creating bucket: gs://$BUCKET_NAME"
    gsutil mb -p $PROJECT_ID -l $REGION "gs://$BUCKET_NAME"
    gsutil versioning set on "gs://$BUCKET_NAME"
else
    echo "Bucket already exists: gs://$BUCKET_NAME"
fi

# Phase 2: Initialize and apply Terraform
echo -e "${YELLOW}Phase 2: Deploying infrastructure with Terraform...${NC}"
cd $TERRAFORM_DIR

if [ ! -f "terraform.tfvars" ]; then
    echo -e "${RED}Error: terraform.tfvars not found. Please create it from terraform.tfvars.example${NC}"
    exit 1
fi

terraform init
terraform plan
echo -e "${YELLOW}Review the plan above. Press Enter to apply, or Ctrl+C to cancel...${NC}"
read

terraform apply

# Get outputs
API_URL=$(terraform output -raw api_url 2>/dev/null || echo "")
ARTIFACT_REGISTRY=$(terraform output -raw artifact_registry 2>/dev/null || echo "")

cd ../..

# Phase 3: Build and push Docker images
echo -e "${YELLOW}Phase 3: Building and pushing Docker images...${NC}"

# Configure Docker for Artifact Registry
echo "Configuring Docker for Artifact Registry..."
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build API image
echo "Building API image..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/api:latest -f api/Dockerfile .

# Build Worker image
echo "Building Worker image..."
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/overlay-worker:latest -f vision/worker/Dockerfile .

# Push images
echo "Pushing API image..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/api:latest

echo "Pushing Worker image..."
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/overlay-worker:latest

echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Configure secrets in Secret Manager:"
echo "   - openai-api-key"
echo "   - gemini-api-key"
echo "   - jwt-secret"
echo "   - google-client-id"
echo "   - google-client-secret"
echo ""
echo "2. Update Cloud Run services with secret references"
echo ""
echo "3. Run database migrations"
echo ""
if [ -n "$API_URL" ]; then
    echo "API URL: $API_URL"
fi
