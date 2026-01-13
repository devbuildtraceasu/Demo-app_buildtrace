#!/bin/bash
# Simple fix for CORS_ORIGINS - Use Cloud Console method

set -e

REGION="us-central1"
API_SERVICE="buildtrace-api"
FRONTEND_SERVICE="buildtrace-frontend"

echo "============================================"
echo "  Fix CORS_ORIGINS for OAuth Redirect"
echo "============================================"
echo ""

# Get frontend URL
FRONTEND_URL=$(gcloud run services describe $FRONTEND_SERVICE \
  --region $REGION \
  --format='value(status.url)')

if [ -z "$FRONTEND_URL" ]; then
  echo "ERROR: Could not get frontend URL"
  exit 1
fi

echo "Frontend URL: $FRONTEND_URL"
echo ""

# Construct the JSON value
CORS_VALUE="[\"$FRONTEND_URL\",\"http://localhost:3000\",\"http://localhost:5000\"]"

echo "============================================"
echo "  Use Cloud Console (Easiest Method)"
echo "============================================"
echo ""
echo "1. Open: https://console.cloud.google.com/run?project=$(gcloud config get-value project 2>/dev/null || echo 'YOUR_PROJECT_ID')"
echo ""
echo "2. Click on service: $API_SERVICE"
echo ""
echo "3. Click 'EDIT & DEPLOY NEW REVISION'"
echo ""
echo "4. Go to 'Variables & Secrets' tab"
echo ""
echo "5. Find 'CORS_ORIGINS' or add it if missing"
echo ""
echo "6. Set the value to (copy exactly):"
echo ""
echo "   $CORS_VALUE"
echo ""
echo "7. Click 'DEPLOY'"
echo ""
echo "============================================"
echo "  OR Try CLI with Base64 Encoding"
echo "============================================"
echo ""

# Try base64 encoding approach
CORS_B64=$(echo -n "$CORS_VALUE" | base64)
echo "Attempting base64 method..."
echo ""

# Or try with proper YAML format in file
TEMP_YAML=$(mktemp)
cat > "$TEMP_YAML" << EOF
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: $API_SERVICE
spec:
  template:
    spec:
      containers:
      - env:
        - name: CORS_ORIGINS
          value: '$CORS_VALUE'
EOF

echo "Trying YAML file method..."
gcloud run services replace "$TEMP_YAML" \
  --region $REGION 2>&1 || {
  echo ""
  echo "YAML method failed. Use Cloud Console method above."
  rm "$TEMP_YAML"
  exit 1
}

rm "$TEMP_YAML"

echo ""
echo "✅ Done! CORS_ORIGINS updated."
echo ""
