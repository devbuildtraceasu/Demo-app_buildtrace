# Fix Whitespace in Redirect URI

## The Problem

The redirect URI has whitespace, causing a mismatch with Google OAuth.

## Quick Fix

### Step 1: Check Current Environment Variable

```bash
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --format='value(spec.template.spec.containers[0].env)' | \
  grep GOOGLE_REDIRECT_URI
```

If you see any spaces or extra characters, that's the problem.

### Step 2: Fix the Environment Variable

Set it again with NO whitespace:

```bash
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --update-env-vars="GOOGLE_REDIRECT_URI=https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback"
```

**Important**: Copy-paste the URL exactly - no spaces before or after.

### Step 3: Check Google Console

1. Go to: https://console.cloud.google.com/apis/credentials?project=buildtrace-prod
2. Edit your OAuth client
3. Check **Authorized redirect URIs**
4. Make sure there's NO whitespace before or after:
   ```
   https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
   ```
5. If there's whitespace, delete the entry and add it again (copy-paste exactly)

### Step 4: Redeploy API (Code Fix)

The code now strips whitespace automatically, but you need to redeploy:

```bash
cd Overlay-main/infra
./BUILD_AND_PUSH.sh
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --image=us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest
```

## Verification

After fixing, test the redirect URI:

```bash
curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url | jq -r '.url' | grep -o 'redirect_uri=[^&]*'
```

This should show the redirect_uri parameter with NO whitespace.
