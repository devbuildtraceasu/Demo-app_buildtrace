# Fix redirect_uri_mismatch Error

## The Problem

Google OAuth is rejecting the request because the redirect URI configured in Google Console doesn't match what your API is sending.

## Quick Fix

### Step 1: Check What Redirect URI Your API Is Using

The API uses this redirect URI:
```
https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

**Note**: This points to the **API service**, not the frontend!

### Step 2: Update Google OAuth Console

1. Go to [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials?project=buildtrace-prod)

2. Find your OAuth 2.0 Client ID and click **Edit**

3. Under **Authorized redirect URIs**, make sure you have **EXACTLY** this:
   ```
   https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
   ```

4. **Important checks**:
   - ✅ Must be HTTPS (not HTTP)
   - ✅ No trailing slash
   - ✅ Exact match (case-sensitive)
   - ✅ Points to API service, not frontend

5. Under **Authorized JavaScript origins**, add:
   ```
   https://buildtrace-frontend-okidmickfa-uc.a.run.app
   ```

6. Click **SAVE**

### Step 3: Verify API Configuration

Check that your API service has the correct redirect URI set:

```bash
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --format='value(spec.template.spec.containers[0].env)' | grep GOOGLE_REDIRECT_URI
```

It should show:
```
GOOGLE_REDIRECT_URI=https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

If it's different or missing, update it:

```bash
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --update-env-vars="GOOGLE_REDIRECT_URI=https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback"
```

### Step 4: Test Again

1. Wait 1-2 minutes for Google's changes to propagate
2. Visit: https://buildtrace-frontend-okidmickfa-uc.a.run.app
3. Click "Sign in with Google"
4. Should work now!

## Common Mistakes

❌ **Wrong redirect URI in Google Console:**
- `https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback` (points to frontend - WRONG)
- `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback/` (trailing slash - WRONG)
- `http://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback` (HTTP instead of HTTPS - WRONG)

✅ **Correct redirect URI:**
- `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback` (exact match)

## Debug: Check What Redirect URI API Is Actually Sending

You can check the API logs to see what redirect URI it's constructing:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND jsonPayload.message=~\"redirect\"" \
  --limit=10 \
  --project=buildtrace-prod \
  --format=json
```

Or test the endpoint directly:

```bash
curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url
```

This will return a JSON with the `url` field. Decode the URL and check the `redirect_uri` parameter - it should match exactly what's in Google Console.
