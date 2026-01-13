#!/bin/bash
# Debug script to check what redirect URI is being sent

echo "Checking what redirect URI the API is sending..."
echo ""

# Get the OAuth URL and extract redirect_uri
OAUTH_URL=$(curl -s "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url" | jq -r '.url')

if [ -z "$OAUTH_URL" ] || [ "$OAUTH_URL" = "null" ]; then
    echo "❌ Error: Could not get OAuth URL from API"
    echo "Response:"
    curl -s "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url"
    exit 1
fi

echo "Full OAuth URL:"
echo "$OAUTH_URL"
echo ""

# Extract redirect_uri parameter
REDIRECT_URI=$(echo "$OAUTH_URL" | grep -o 'redirect_uri=[^&]*' | cut -d'=' -f2 | sed 's/%2F/\//g' | sed 's/%3A/:/g' | sed 's/%2B/+/g' | sed 's/%20/ /g')

echo "Redirect URI being sent:"
echo "'$REDIRECT_URI'"
echo ""

# Check for whitespace
if [[ "$REDIRECT_URI" =~ [[:space:]] ]]; then
    echo "⚠️  WARNING: Redirect URI contains whitespace!"
    echo "Length: ${#REDIRECT_URI}"
    echo "Hex dump:"
    echo "$REDIRECT_URI" | od -An -tx1
else
    echo "✅ No whitespace detected"
fi

echo ""
echo "Expected redirect URI:"
echo "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback"
echo ""

# Compare
EXPECTED="https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback"
if [ "$REDIRECT_URI" = "$EXPECTED" ]; then
    echo "✅ Redirect URI matches expected value"
else
    echo "❌ Redirect URI does NOT match!"
    echo "Difference:"
    diff <(echo "$REDIRECT_URI") <(echo "$EXPECTED") || true
fi

echo ""
echo "Check API environment variable:"
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --format='value(spec.template.spec.containers[0].env)' 2>/dev/null | \
  grep -o 'GOOGLE_REDIRECT_URI=[^,}]*' | cut -d'=' -f2 || echo "Not found in env vars"
