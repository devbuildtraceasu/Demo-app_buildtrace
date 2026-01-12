#!/bin/bash
# Create a new GCP project where YOU are the Owner
# This bypasses all permission issues

set -e

echo "=== Creating New GCP Project ==="
echo ""

# New project ID (must be globally unique)
NEW_PROJECT_ID="buildtrace-app-$(date +%s)"
echo "New Project ID: $NEW_PROJECT_ID"

# Create the project
echo ""
echo "Step 1: Creating project..."
gcloud projects create $NEW_PROJECT_ID --name="BuildTrace App"

# Set as current project
echo ""
echo "Step 2: Setting as current project..."
gcloud config set project $NEW_PROJECT_ID

# Check if user has billing accounts
echo ""
echo "Step 3: Checking billing accounts..."
gcloud billing accounts list

echo ""
echo "=== IMPORTANT ==="
echo "Copy one of the ACCOUNT_ID values above and run:"
echo ""
echo "gcloud billing projects link $NEW_PROJECT_ID --billing-account=YOUR_ACCOUNT_ID"
echo ""
echo "Then run the next script: ./enable-apis-new-project.sh"
