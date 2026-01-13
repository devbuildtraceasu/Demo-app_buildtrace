#!/bin/bash
# Fix CORS_ORIGINS to use production frontend URL first

set -e

REGION="us-central1"
API_SERVICE="buildtrace-api"
FRONTEND_SERVICE="buildtrace-frontend"

echo "============================================"
echo "  Fixing CORS_ORIGINS for OAuth Redirect"
echo "============================================"
echo ""

# Get frontend URL
echo "Step 1: Getting frontend URL..."
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE \
  --region $REGION \
  --format='value(status.url)')

if [ -z "$FRONTEND_URL" ]; then
  echo "ERROR: Could not get frontend URL. Is the frontend service deployed?"
  exit 1
fi

echo "Frontend URL: $FRONTEND_URL"
echo ""

# Construct CORS_ORIGINS JSON
CORS_ORIGINS_JSON="[\"$FRONTEND_URL\",\"http://localhost:3000\",\"http://localhost:5000\"]"

echo "Step 2: Updating CORS_ORIGINS on API service..."
echo "CORS_ORIGINS: $CORS_ORIGINS_JSON"
echo ""

# Method 1: Use --env-vars-file to avoid shell escaping issues
echo "Creating temporary env vars file..."
TEMP_FILE=$(mktemp)
cat > "$TEMP_FILE" << EOF
CORS_ORIGINS=["$FRONTEND_URL","http://localhost:3000","http://localhost:5000"]
EOF

echo "Setting CORS_ORIGINS via env-vars-file..."
gcloud run services update $API_SERVICE \
  --region $REGION \
  --env-vars-file "$TEMP_FILE"

# Clean up
rm "$TEMP_FILE"

if [ $? -eq 0 ]; then
  echo ""
  echo "============================================"
  echo "  ✅ CORS_ORIGINS Updated!"
  echo "============================================"
  exit 0
fi

# Method 2: Manual instructions if CLI fails
echo ""
echo "⚠️  gcloud CLI had issues with JSON array. Use Cloud Console instead:"
echo ""
echo "1. Go to: https://console.cloud.google.com/run?project=$(gcloud config get-value project)"
echo "2. Click on service: $API_SERVICE"
echo "3. Click 'EDIT & DEPLOY NEW REVISION'"
echo "4. Go to 'Variables & Secrets' tab"
echo "5. Find 'CORS_ORIGINS' environment variable"
echo "6. Set value to: $CORS_ORIGINS_JSON"
echo "7. Click 'DEPLOY'"
echo ""
echo "Or run this command manually (may need to escape brackets):"
echo "  gcloud run services update $API_SERVICE --region $REGION \\"
echo "    --set-env-vars 'CORS_ORIGINS=$CORS_ORIGINS_JSON'"
echo ""
