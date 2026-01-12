#!/bin/bash
# Fix authentication and initialize Terraform with local state

set -e

echo "Step 1: Setting up Application Default Credentials..."
echo "This will open a browser window for authentication."
gcloud auth application-default login

echo ""
echo "Step 2: Clearing any cached Terraform backend configuration..."
rm -rf .terraform
rm -f .terraform.lock.hcl

echo ""
echo "Step 3: Initializing Terraform with local state..."
terraform init

echo ""
echo "✅ Terraform initialized successfully!"
echo ""
echo "Next steps:"
echo "  terraform plan    # Review what will be created"
echo "  terraform apply   # Create the infrastructure"
