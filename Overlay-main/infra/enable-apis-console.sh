#!/bin/bash
# Script to open GCP Console pages for enabling APIs
# This is a helper script - you'll need to click "Enable" on each page

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-dev}"

echo "Opening GCP Console pages to enable APIs..."
echo "Project: $PROJECT_ID"
echo ""
echo "You'll need to click 'Enable' on each page that opens."
echo "Press Enter to continue..."
read

# Array of API IDs
APIs=(
    "run.googleapis.com"
    "sqladmin.googleapis.com"
    "storage.googleapis.com"
    "pubsub.googleapis.com"
    "artifactregistry.googleapis.com"
    "secretmanager.googleapis.com"
    "compute.googleapis.com"
    "servicenetworking.googleapis.com"
    "cloudresourcemanager.googleapis.com"
)

# API names for display
declare -A API_NAMES=(
    ["run.googleapis.com"]="Cloud Run API"
    ["sqladmin.googleapis.com"]="Cloud SQL Admin API"
    ["storage.googleapis.com"]="Cloud Storage API"
    ["pubsub.googleapis.com"]="Cloud Pub/Sub API"
    ["artifactregistry.googleapis.com"]="Artifact Registry API"
    ["secretmanager.googleapis.com"]="Secret Manager API"
    ["compute.googleapis.com"]="Compute Engine API"
    ["servicenetworking.googleapis.com"]="Service Networking API"
    ["cloudresourcemanager.googleapis.com"]="Cloud Resource Manager API"
)

# Open each API page
for api_id in "${APIs[@]}"; do
    api_name="${API_NAMES[$api_id]}"
    url="https://console.cloud.google.com/apis/library/${api_id}?project=${PROJECT_ID}"
    
    echo "Opening: ${api_name:-$api_id}"
    open "$url" 2>/dev/null || xdg-open "$url" 2>/dev/null || echo "Please open: $url"
    
    # Wait a bit between opens
    sleep 2
done

echo ""
echo "All API pages should be open in your browser."
echo "Please enable each API by clicking the 'Enable' button."
echo ""
echo "After enabling all APIs, verify with:"
echo "  gcloud services list --enabled --project=$PROJECT_ID"
