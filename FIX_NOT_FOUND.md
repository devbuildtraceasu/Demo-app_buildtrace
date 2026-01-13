# Fix "Not Found" Error for Google OAuth Callback

## The Problem

Getting `{"detail":"Not Found"}` when Google redirects to the callback endpoint.

## The Solution

The API needs to be **redeployed** with the latest code changes. The route exists but the deployed version doesn't have it.

## Quick Fix: Redeploy API

### Option 1: Use Build Script

```bash
cd Overlay-main/infra
./BUILD_AND_PUSH.sh
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --image=us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest
```

### Option 2: Manual Build and Deploy

```bash
cd Overlay-main

# Build the API image
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest \
  -f api/Dockerfile .

# Push to Artifact Registry
docker push us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest

# Deploy to Cloud Run
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --image=us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest
```

## What Was Fixed

1. ✅ Removed duplicate placeholder routes from `auth.py`
2. ✅ Added whitespace stripping in `google_auth.py`
3. ✅ Reordered routers so `google_auth.router` is registered first

## Verify After Deployment

1. Check the route exists:
   ```bash
   curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url
   ```
   Should return a JSON with `url` field, not "Not Found"

2. Test the callback endpoint (will redirect, but should not be "Not Found"):
   ```bash
   curl -I "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback?code=test"
   ```
   Should return a redirect (302) or error about invalid code, NOT 404

3. Check API logs:
   ```bash
   gcloud logging read \
     "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
     --limit=10 \
     --project=buildtrace-prod
   ```

## After Redeployment

1. Wait 1-2 minutes for the new revision to be ready
2. Try Google login again
3. Should work now!
