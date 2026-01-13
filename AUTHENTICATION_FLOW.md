# BuildTrace Authentication Flow

## Architecture Overview

BuildTrace uses a **separated frontend and backend** architecture:

- **Frontend**: Static React app served via nginx on Cloud Run
- **Backend API**: Python FastAPI service on Cloud Run
- **Authentication**: Google OAuth handled by the **API service**

## The Problem You Encountered

The error "Google Login Unavailable" occurs because:

1. The frontend (static React app) calls the API: `GET /api/auth/google/url`
2. The API service checks for `GOOGLE_CLIENT_ID` environment variable
3. If not set, it returns HTTP 501: "Google OAuth is not configured"
4. The frontend catches this error and shows the toast message

**Root Cause**: The `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` environment variables were not set on the **API service** (buildtrace-api).

## Authentication Flow

```
┌─────────────┐
│   Browser   │
│  (Frontend) │
└──────┬──────┘
       │
       │ 1. User clicks "Sign in with Google"
       │
       ▼
┌─────────────────────────────────────┐
│  Frontend calls:                    │
│  GET /api/auth/google/url           │
│  → https://buildtrace-api-.../api/  │
└──────┬──────────────────────────────┘
       │
       │ 2. API returns Google OAuth URL
       │
       ▼
┌─────────────────────────────────────┐
│  Redirect to Google OAuth          │
│  https://accounts.google.com/...    │
└──────┬──────────────────────────────┘
       │
       │ 3. User authenticates with Google
       │
       ▼
┌─────────────────────────────────────┐
│  Google redirects to:               │
│  /api/auth/google/callback          │
│  (on API service)                   │
└──────┬──────────────────────────────┘
       │
       │ 4. API processes callback
       │    - Exchanges code for tokens
       │    - Gets user info from Google
       │    - Creates/updates user in DB
       │    - Generates JWT token
       │
       ▼
┌─────────────────────────────────────┐
│  API redirects to frontend:        │
│  /auth?token=<jwt_token>            │
└──────┬──────────────────────────────┘
       │
       │ 5. Frontend reads token from URL
       │    - Stores token in localStorage
       │    - Redirects to /dashboard
       │
       ▼
┌─────────────────────────────────────┐
│  Authenticated!                     │
│  All API calls include:             │
│  Authorization: Bearer <token>       │
└─────────────────────────────────────┘
```

## Configuration Requirements

### API Service (buildtrace-api)

**Required Environment Variables:**
- `GOOGLE_CLIENT_ID` - Your Google OAuth Client ID
- `GOOGLE_CLIENT_SECRET` - From Secret Manager
- `GOOGLE_REDIRECT_URI` - `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback`
- `CORS_ORIGINS` - JSON array including frontend URL

**Note**: These must be set on the **API service**, not the frontend!

### Frontend Service (buildtrace-frontend)

**Required Environment Variables:**
- `VITE_API_URL` - Set at build time: `https://buildtrace-api-okidmickfa-uc.a.run.app`
- `NODE_ENV=production`

**Note**: The frontend is static - it doesn't need Google Auth env vars!

### Google OAuth Console Configuration

In [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

**Authorized JavaScript origins:**
```
https://buildtrace-frontend-okidmickfa-uc.a.run.app
```

**Authorized redirect URIs:**
```
https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

⚠️ **Important**: The redirect URI points to the **API service**, not the frontend!

## Quick Fix

Run the setup script:

```bash
cd Overlay-main/infra
./setup-google-auth.sh
```

This will:
1. Prompt for Google Client ID and Secret
2. Create/update secrets in Secret Manager
3. Configure the API service with Google Auth
4. Set the correct redirect URI

## Verification

After setup, test the flow:

1. Visit: https://buildtrace-frontend-okidmickfa-uc.a.run.app
2. Click "Sign in with Google"
3. Should redirect to Google (not show error)

If you still see the error:

```bash
# Check API service env vars
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --format='value(spec.template.spec.containers[0].env)'

# Check API logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
  --limit=50 \
  --project=buildtrace-prod

# Test endpoint directly
curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url
```

## Common Mistakes

1. ❌ Setting Google Auth env vars on the **frontend service** (it's static, doesn't need them)
2. ❌ Setting redirect URI to frontend URL (should be API URL)
3. ❌ Not including frontend URL in CORS_ORIGINS
4. ❌ Mismatch between redirect URI in Google Console and API configuration

## Summary

- **Frontend**: Static React app, calls API for auth
- **API Service**: Handles all Google OAuth logic
- **Redirect URI**: Points to API service, not frontend
- **Env Vars**: Set on API service, not frontend

See `GOOGLE_AUTH_FIX.md` for detailed setup instructions.
