#!/bin/bash
# Fix authentication issues before terraform apply

set -e

echo "Fixing authentication for Terraform..."

# Step 1: Clear existing application default credentials
echo "Step 1: Clearing old credentials..."
rm -f ~/.config/gcloud/application_default_credentials.json

# Step 2: Re-authenticate with application default credentials
echo "Step 2: Re-authenticating (this will open a browser)..."
gcloud auth application-default login

# Step 3: Verify authentication
echo "Step 3: Verifying authentication..."
gcloud auth list

echo ""
echo "✅ Authentication fixed!"
echo ""
echo "Now try running terraform apply again:"
echo "  terraform apply"
