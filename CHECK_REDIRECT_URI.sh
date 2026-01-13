#!/bin/bash
# Decode and check the redirect URI

echo "Checking redirect URI from API..."
echo ""

# Get the OAuth URL
OAUTH_URL=$(curl -s "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url" | jq -r '.url')

# Extract and decode redirect_uri
ENCODED_URI=$(echo "$OAUTH_URL" | grep -o 'redirect_uri=[^&]*' | cut -d'=' -f2)
DECODED_URI=$(python3 -c "import urllib.parse; print(urllib.parse.unquote('$ENCODED_URI'))")

echo "Encoded (what's in the URL):"
echo "$ENCODED_URI"
echo ""
echo "Decoded (what Google sees):"
echo "'$DECODED_URI'"
echo ""
echo "Expected (what should be in Google Console):"
echo "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback"
echo ""

# Check for whitespace
if [[ "$DECODED_URI" =~ [[:space:]] ]]; then
    echo "⚠️  PROBLEM FOUND: Redirect URI contains whitespace!"
    echo "Length: ${#DECODED_URI}"
    echo "Character codes:"
    echo "$DECODED_URI" | od -An -tx1c
    echo ""
    echo "This is the problem! The API is sending a redirect URI with whitespace."
    echo "You need to:"
    echo "1. Check the GOOGLE_REDIRECT_URI environment variable in Cloud Run"
    echo "2. Make sure it has NO spaces"
    echo "3. Or redeploy the API with the latest code that strips whitespace"
else
    echo "✅ No whitespace detected in decoded URI"
fi

# Compare
EXPECTED="https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback"
if [ "$DECODED_URI" = "$EXPECTED" ]; then
    echo "✅ Decoded URI matches expected value"
    echo ""
    echo "If Google Console has the same URI and it's still not working:"
    echo "1. Delete the redirect URI in Google Console"
    echo "2. Re-add it (copy-paste exactly)"
    echo "3. Make sure there's NO whitespace before or after"
    echo "4. Wait 2-3 minutes"
else
    echo "❌ Decoded URI does NOT match expected!"
    echo ""
    echo "Difference:"
    diff <(echo "$DECODED_URI") <(echo "$EXPECTED") || true
fi
