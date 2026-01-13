#!/bin/bash
# Enable all required APIs for the new project

set -e

PROJECT_ID=$(gcloud config get-value project)
echo "Enabling APIs for project: $PROJECT_ID"

# Enable all required APIs
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

echo ""
echo "=== All APIs enabled! ==="
echo ""
echo "Next steps:"
echo "1. Update terraform.tfvars with project_id = \"$PROJECT_ID\""
echo "2. Run: terraform init"
echo "3. Run: terraform apply"
