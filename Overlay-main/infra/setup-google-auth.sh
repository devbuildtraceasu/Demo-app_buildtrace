#!/bin/bash
# Setup Google OAuth for BuildTrace API service
# This script configures Google Auth environment variables on the Cloud Run API service

set -e

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"
REGION="us-central1"
API_SERVICE="buildtrace-api"
FRONTEND_URL="https://buildtrace-frontend-okidmickfa-uc.a.run.app"
API_URL="https://buildtrace-api-okidmickfa-uc.a.run.app"

echo "============================================"
echo "  Google OAuth Setup for BuildTrace API"
echo "============================================"
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "API Service: $API_SERVICE"
echo "Frontend URL: $FRONTEND_URL"
echo "API URL: $API_URL"
echo ""

# Check if credentials are provided
if [ -z "$GOOGLE_CLIENT_ID" ]; then
    echo "⚠️  GOOGLE_CLIENT_ID not set in environment"
    echo ""
    echo "Please provide your Google OAuth credentials:"
    read -p "Enter Google Client ID: " GOOGLE_CLIENT_ID
fi

if [ -z "$GOOGLE_CLIENT_SECRET" ]; then
    echo ""
    echo "⚠️  GOOGLE_CLIENT_SECRET not set in environment"
    read -sp "Enter Google Client Secret: " GOOGLE_CLIENT_SECRET
    echo ""
fi

if [ -z "$GOOGLE_CLIENT_ID" ] || [ -z "$GOOGLE_CLIENT_SECRET" ]; then
    echo "❌ Error: Both GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are required"
    exit 1
fi

# Create or update secrets in Secret Manager
echo ""
echo "Step 1: Creating/updating secrets in Secret Manager..."

# Check if secret exists, create if not
if ! gcloud secrets describe google-client-secret --project=$PROJECT_ID &>/dev/null; then
    echo "Creating google-client-secret..."
    echo -n "$GOOGLE_CLIENT_SECRET" | gcloud secrets create google-client-secret \
        --data-file=- \
        --project=$PROJECT_ID \
        --replication-policy="automatic"
else
    echo "Updating google-client-secret..."
    echo -n "$GOOGLE_CLIENT_SECRET" | gcloud secrets versions add google-client-secret \
        --data-file=- \
        --project=$PROJECT_ID
fi

# Get service account email for API service
SERVICE_ACCOUNT=$(gcloud run services describe $API_SERVICE \
    --region=$REGION \
    --project=$PROJECT_ID \
    --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || echo "")

if [ -z "$SERVICE_ACCOUNT" ]; then
    # Use default compute service account
    SERVICE_ACCOUNT="${PROJECT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
    echo "Using default service account: $SERVICE_ACCOUNT"
else
    echo "Using service account: $SERVICE_ACCOUNT"
fi

# Grant access to secret
echo ""
echo "Step 2: Granting service account access to secret..."
gcloud secrets add-iam-policy-binding google-client-secret \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID \
    --quiet || echo "Policy binding may already exist"

# Set redirect URI (should point to API callback)
# Strip any whitespace to ensure exact match
REDIRECT_URI=$(echo "${API_URL}/api/auth/google/callback" | tr -d '[:space:]')

echo ""
echo "Step 3: Updating Cloud Run API service with Google Auth configuration..."

# Update the API service with Google Auth env vars
echo "Setting Google Auth environment variables..."
gcloud run services update $API_SERVICE \
    --region=$REGION \
    --project=$PROJECT_ID \
    --update-env-vars="GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID},GOOGLE_REDIRECT_URI=${REDIRECT_URI}" \
    --set-secrets="GOOGLE_CLIENT_SECRET=google-client-secret:latest" \
    --quiet

echo ""
echo "Note: CORS_ORIGINS can be set manually if needed. The API has default CORS settings."
echo "To set CORS_ORIGINS manually, use Cloud Console or run:"
echo "  gcloud run services update $API_SERVICE --region=$REGION --project=$PROJECT_ID \\"
echo "    --update-env-vars='CORS_ORIGINS=${FRONTEND_URL},http://localhost:3000,http://localhost:5000'"

echo ""
echo "============================================"
echo "  ✅ Google OAuth Configured!"
echo "============================================"
echo ""
echo "Configuration:"
echo "  Client ID: ${GOOGLE_CLIENT_ID}"
echo "  Redirect URI: ${REDIRECT_URI}"
echo "  Frontend URL: ${FRONTEND_URL}"
echo ""
echo "⚠️  IMPORTANT: Make sure your Google OAuth credentials are configured with:"
echo ""
echo "   Authorized JavaScript origins:"
echo "     ${FRONTEND_URL}"
echo ""
echo "   Authorized redirect URIs:"
echo "     ${REDIRECT_URI}"
echo ""
echo "📝 To verify in Google Cloud Console:"
echo "   1. Go to: https://console.cloud.google.com/apis/credentials?project=${PROJECT_ID}"
echo "   2. Find your OAuth 2.0 Client ID"
echo "   3. Verify the redirect URI matches: ${REDIRECT_URI}"
echo ""
echo "🧪 Test the authentication:"
echo "   1. Visit: ${FRONTEND_URL}"
echo "   2. Click 'Sign in with Google'"
echo "   3. You should be redirected to Google for authentication"
echo ""
