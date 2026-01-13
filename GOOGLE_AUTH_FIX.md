# Google Auth Fix - Quick Guide

## The Problem

The frontend shows "Google Login Unavailable" because the **API service** (Python FastAPI) doesn't have `GOOGLE_CLIENT_ID` configured.

**Important**: The frontend is static and doesn't need Google Auth env vars. The **API service** needs them.

## Quick Fix

### Step 1: Run the Setup Script

```bash
cd Overlay-main/infra
./setup-google-auth.sh
```

The script will:
- Prompt for your Google Client ID and Secret
- Create/update secrets in Secret Manager
- Configure the API service with Google Auth env vars
- Set the correct redirect URI

### Step 2: Verify Google OAuth Configuration

In [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

1. Go to **APIs & Services** → **Credentials**
2. Find your OAuth 2.0 Client ID
3. Verify these settings:

**Authorized JavaScript origins:**
```
https://buildtrace-frontend-okidmickfa-uc.a.run.app
```

**Authorized redirect URIs:**
```
https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

⚠️ **Note**: The redirect URI points to the **API service**, not the frontend!

## How Authentication Works

1. User clicks "Sign in with Google" on frontend
2. Frontend calls: `GET /api/auth/google/url` → API returns Google OAuth URL
3. User is redirected to Google for authentication
4. Google redirects to: `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback`
5. API processes callback, creates JWT token
6. API redirects to frontend: `https://buildtrace-frontend-okidmickfa-uc.a.run.app/auth?token=...`
7. Frontend reads token from URL and stores it

## Manual Setup (if script doesn't work)

```bash
# Set environment variables
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"

# Create secret
echo -n "$GOOGLE_CLIENT_SECRET" | gcloud secrets create google-client-secret \
  --data-file=- \
  --project=buildtrace-prod

# Update API service
gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --set-env-vars="GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID},GOOGLE_REDIRECT_URI=https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback" \
  --set-secrets="GOOGLE_CLIENT_SECRET=google-client-secret:latest"
```

## Verify It's Working

1. Visit: https://buildtrace-frontend-okidmickfa-uc.a.run.app
2. Click "Sign in with Google"
3. You should be redirected to Google (not see the error)

## Troubleshooting

### Still seeing "Google Login Unavailable"

1. Check API service has the env var:
   ```bash
   gcloud run services describe buildtrace-api \
     --region=us-central1 \
     --project=buildtrace-prod \
     --format='value(spec.template.spec.containers[0].env)'
   ```

2. Check API logs:
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
     --limit=50 \
     --project=buildtrace-prod
   ```

3. Test the endpoint directly:
   ```bash
   curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url
   ```
   Should return `{"url": "https://accounts.google.com/..."}` not an error.

### "redirect_uri_mismatch" error

- Verify redirect URI in Google Console exactly matches: `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback`
- No trailing slashes
- Must be HTTPS (not HTTP)

### CORS errors

- Make sure `CORS_ORIGINS` includes the frontend URL
- Check API service CORS configuration
