#!/bin/bash
# Import existing service accounts into Terraform state

set -e

PROJECT_ID="buildtrace-dev"

echo "Importing existing service accounts into Terraform state..."

# Import API service account
echo "Importing buildtrace-api service account..."
terraform import google_service_account.api projects/${PROJECT_ID}/serviceAccounts/buildtrace-api@${PROJECT_ID}-484112.iam.gserviceaccount.com

# Import Worker service account  
echo "Importing buildtrace-worker service account..."
terraform import google_service_account.worker projects/${PROJECT_ID}/serviceAccounts/buildtrace-worker@${PROJECT_ID}-484112.iam.gserviceaccount.com

echo ""
echo "✅ Service accounts imported!"
echo ""
echo "Now you can run: terraform apply"
echo ""
echo "Note: If you still get API permission errors, you may need to:"
echo "  1. Comment out the google_project_service resources in main.tf (APIs already enabled)"
echo "  2. Or get proper IAM permissions to list services"
