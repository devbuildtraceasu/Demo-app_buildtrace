# Debug OAuth Redirect URI Mismatch

## If Redirect URI is Already in Google Console

### Step 1: Verify Exact Match

1. Go to: https://console.cloud.google.com/apis/credentials?project=buildtrace-prod
2. Click on your OAuth client (ID: `926202951836-oc1enmumkl9ejs05hf8dvqvp78thtod3`)
3. Look at **Authorized redirect URIs**
4. **Check for:**
   - ❌ Any spaces before or after the URL
   - ❌ Trailing slash: `/callback/` (should be `/callback`)
   - ❌ Different casing
   - ❌ HTTP instead of HTTPS

5. **It should be EXACTLY:**
   ```
   https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
   ```

### Step 2: Check What API Is Actually Sending

Run this to see what redirect URI the API is sending:

```bash
curl -s "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url" | jq -r '.url' | grep -o 'redirect_uri=[^&]*'
```

Or use the debug script:
```bash
./DEBUG_REDIRECT_URI.sh
```

### Step 3: Check for Multiple OAuth Clients

You might have multiple OAuth clients. Check ALL of them:

1. In Google Console, look at ALL OAuth 2.0 Client IDs
2. Make sure the redirect URI is added to the CORRECT one (the one with your Client ID)
3. The Client ID should be: `926202951836-oc1enmumkl9ejs05hf8dvqvp78thtod3.apps.googleusercontent.com`

### Step 4: Check API Environment Variable

Verify the API has the correct redirect URI set:

```bash
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --format='value(spec.template.spec.containers[0].env)' | \
  grep GOOGLE_REDIRECT_URI
```

If it's wrong or missing, fix it:

```bash
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --update-env-vars="GOOGLE_REDIRECT_URI=https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback"
```

### Step 5: Check API Has Been Redeployed

The API needs the latest code with whitespace stripping. Check if it's been redeployed:

```bash
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --format='value(status.latestReadyRevisionName)'
```

If it's an old revision, redeploy:

```bash
cd Overlay-main/infra
./BUILD_AND_PUSH.sh
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --image=us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest
```

### Step 6: Check API Logs

See what redirect URI the API is actually using:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND jsonPayload.message=~\"redirect\"" \
  --limit=10 \
  --project=buildtrace-prod \
  --format=json | jq -r '.[].jsonPayload.message'
```

### Step 7: Try Deleting and Re-adding in Google Console

Sometimes Google caches the old value:

1. Go to OAuth client settings
2. **Delete** the redirect URI entry
3. **Save**
4. **Add it again** (copy-paste exactly)
5. **Save**
6. Wait 2-3 minutes
7. Try again

### Step 8: Check OAuth Consent Screen

Make sure your OAuth consent screen is configured:

1. Go to: https://console.cloud.google.com/apis/credentials/consent?project=buildtrace-prod
2. Make sure it's published or in testing mode with test users added
3. If it's in testing, add your email as a test user

## Common Issues

### Issue 1: Whitespace in Google Console
- **Fix**: Delete the entry, re-add it (copy-paste, no spaces)

### Issue 2: Wrong OAuth Client
- **Fix**: Make sure you're using the client with ID: `926202951836-oc1enmumkl9ejs05hf8dvqvp78thtod3`

### Issue 3: API Not Redeployed
- **Fix**: Redeploy the API with latest code

### Issue 4: URL Encoding
- **Fix**: Make sure the URL in Google Console is NOT URL-encoded (should be plain text)

### Issue 5: Multiple Projects
- **Fix**: Make sure you're in the `buildtrace-prod` project, not a different project

## Quick Test

After making changes, test the OAuth URL:

```bash
curl "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url" | jq
```

Then manually decode the `redirect_uri` parameter from the `url` field and compare it to what's in Google Console.
