#!/bin/bash
# Complete deployment script for BuildTrace
# Run this after creating the project and linking billing

set -e

echo "============================================"
echo "  BuildTrace GCP Deployment Script"
echo "============================================"
echo ""

# Check current project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
if [ -z "$PROJECT_ID" ]; then
    echo "ERROR: No project set. Run: gcloud config set project YOUR_PROJECT_ID"
    exit 1
fi

echo "Current project: $PROJECT_ID"
echo ""

# Step 1: Enable APIs
echo "Step 1: Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  pubsub.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  servicenetworking.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=$PROJECT_ID

echo "✅ APIs enabled"
echo ""

# Step 2: Update terraform.tfvars
echo "Step 2: Updating terraform.tfvars..."
cd "$(dirname "$0")/terraform"
sed -i.bak "s/project_id = .*/project_id = \"$PROJECT_ID\"/" terraform.tfvars
echo "✅ terraform.tfvars updated"
echo ""

# Step 3: Initialize Terraform
echo "Step 3: Initializing Terraform..."
terraform init
echo "✅ Terraform initialized"
echo ""

# Step 4: Plan
echo "Step 4: Creating Terraform plan..."
terraform plan -out=tfplan
echo "✅ Plan created"
echo ""

# Step 5: Apply
echo "Step 5: Applying Terraform (this will take 10-15 minutes)..."
read -p "Press Enter to apply, or Ctrl+C to cancel..."
terraform apply tfplan
echo "✅ Infrastructure created!"
echo ""

# Get outputs
echo "============================================"
echo "  Deployment Complete!"
echo "============================================"
echo ""
terraform output

echo ""
echo "Next steps:"
echo "1. Build and push Docker images (see deploy.sh)"
echo "2. Run database migrations"
echo "3. Set up secrets in Secret Manager"
echo "4. Deploy frontend"
