# BuildTrace Authentication Guide

Complete guide for Google OAuth authentication setup and troubleshooting.

## Architecture

BuildTrace uses **Google OAuth 2.0** with a separated frontend and backend:

- **Frontend**: React app (static files on Cloud Run)
- **Backend API**: FastAPI service (handles OAuth)
- **Flow**: Frontend → API → Google → API → Frontend

## Setup

### Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Select project: **buildtrace-prod**
3. Click **+ CREATE CREDENTIALS** → **OAuth client ID**
4. Configure:
   - **Type**: Web application
   - **Name**: BuildTrace Production
   - **Authorized redirect URIs**: 
     ```
     https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
     ```
5. Save **Client ID** and **Client Secret**

### Step 2: Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (or **Internal** if you have Google Workspace)
3. Fill required fields (app name, emails)
4. Add scopes: `email`, `profile`, `openid`
5. Add test users if needed
6. Save

### Step 3: Set Environment Variables

```bash
cd Overlay-main/infra
./setup-google-auth.sh
```

This script:
- Prompts for Google Client ID and Secret
- Creates secrets in Secret Manager
- Sets environment variables on API service

### Step 4: Set CORS_ORIGINS

**Important**: Use Cloud Console (CLI has issues with JSON arrays):

1. Go to Cloud Run → `buildtrace-api` → **EDIT & DEPLOY NEW REVISION**
2. **Variables & Secrets** tab
3. Set `CORS_ORIGINS` to:
   ```json
   ["https://buildtrace-frontend-okidmickfa-uc.a.run.app","http://localhost:3000","http://localhost:5000"]
   ```
4. Click **DEPLOY**

## Authentication Flow

```
User → Frontend → API → Google → API → Frontend → Dashboard
```

1. **User clicks "Sign in with Google"**
   - Frontend calls: `GET /api/auth/google/url`

2. **API returns Google OAuth URL**
   - Includes redirect URI: `https://buildtrace-api-xxx.run.app/api/auth/google/callback`

3. **User authenticates with Google**
   - Google shows consent screen
   - User grants permissions

4. **Google redirects to API callback**
   - URL: `/api/auth/google/callback?code=...`
   - API exchanges code for tokens
   - API gets user info from Google
   - API creates/updates user in database
   - API generates JWT token

5. **API redirects to frontend**
   - URL: `https://buildtrace-frontend-xxx.run.app/dashboard?token=<jwt>`
   - Frontend extracts token from URL
   - Frontend stores token in localStorage
   - Frontend redirects to `/dashboard`

6. **Authenticated requests**
   - Frontend includes: `Authorization: Bearer <token>`
   - API validates token and returns user info

## Troubleshooting

### "Google OAuth is not configured"

**Cause**: `GOOGLE_CLIENT_ID` not set on API service

**Fix**:
```bash
cd Overlay-main/infra
./setup-google-auth.sh
```

### "redirect_uri_mismatch"

**Cause**: Redirect URI in Google Console doesn't match API's redirect URI

**Fix**:
1. Check API's redirect URI:
   ```bash
   gcloud run services describe buildtrace-api \
     --region us-central1 \
     --format='value(spec.template.spec.containers[0].env)' | grep GOOGLE_REDIRECT_URI
   ```

2. Ensure Google Console has **exact** match:
   - Go to [Credentials](https://console.cloud.google.com/apis/credentials)
   - Edit OAuth client
   - Add: `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback`
   - **No trailing slash, no whitespace**

### Redirect Goes to localhost:3000

**Cause**: `CORS_ORIGINS` has localhost first, or not set correctly

**Fix**: Set `CORS_ORIGINS` via Cloud Console (see Step 4 above)

### Frontend Can't Reach API

**Cause**: `VITE_API_URL` not set correctly during build

**Fix**:
```bash
cd Overlay-main/infra
./DEPLOY_FRONTEND.sh
```

This rebuilds frontend with correct API URL.

## Testing

### Test OAuth URL Endpoint

```bash
curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url
```

**Expected**: `{"url": "https://accounts.google.com/..."}`

**If error**: Check `GOOGLE_CLIENT_ID` is set

### Test Full Flow

1. Open frontend: https://buildtrace-frontend-okidmickfa-uc.a.run.app
2. Click "Sign in with Google"
3. Should redirect to Google
4. After authentication, should redirect to `/dashboard`
5. Should see user logged in

## Security Notes

- **JWT tokens** expire after 24 hours (configurable)
- **Secrets** stored in Google Secret Manager
- **HTTPS only** in production
- **CORS** restricted to known origins
- **Redirect URIs** must match exactly (no wildcards)

## Related Files

- API OAuth routes: `Overlay-main/api/routes/google_auth.py`
- Frontend auth: `Build-TraceFlow/client/src/lib/api.ts`
- Setup script: `Overlay-main/infra/setup-google-auth.sh`
