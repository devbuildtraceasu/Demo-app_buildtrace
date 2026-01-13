# Complete Authentication Flow Analysis

## Current Flow

### Step 1: Frontend Initiates Login
**File**: `Build-TraceFlow/client/src/pages/auth/AuthPage.tsx`
- User clicks "Sign in with Google" button
- Calls: `api.auth.getGoogleAuthUrl()`
- Which calls: `GET /auth/google/url` (via `api.ts`)

**API Base URL**: 
- From `VITE_API_URL` env var (set at build time)
- Defaults to `/api` if not set
- Final URL: `${VITE_API_URL}/auth/google/url` → `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url`

### Step 2: API Returns Google OAuth URL
**File**: `Overlay-main/api/routes/google_auth.py`
- Route: `@router.get("/google/url")`
- Router prefix: `/api/auth`
- **Full path**: `/api/auth/google/url` ✅
- Returns: `{ "url": "https://accounts.google.com/o/oauth2/v2/auth?..." }`

### Step 3: Frontend Redirects to Google
- `window.location.href = url`
- User authenticates with Google
- Google redirects to: `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback?code=...`

### Step 4: API Callback (THE PROBLEM)
**File**: `Overlay-main/api/routes/google_auth.py`
- Route: `@router.get("/google/callback")`
- Router prefix: `/api/auth`
- **Full path**: `/api/auth/google/callback` ✅
- **Status**: Returns "Not Found" ❌

## The Problem

The callback route exists in code but returns "Not Found". This means:

1. **Either**: The API hasn't been redeployed with the latest code
2. **Or**: There's a routing conflict
3. **Or**: The route isn't being registered properly

## Route Registration Analysis

**File**: `Overlay-main/api/main.py`

```python
# Line 53: google_auth.router registered FIRST
app.include_router(google_auth.router, prefix="/api/auth", tags=["Google OAuth"])

# Line 55: auth.router registered AFTER
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
```

**Routes in google_auth.router**:
- `GET /google/url` → `/api/auth/google/url` ✅
- `GET /google/callback` → `/api/auth/google/callback` ✅
- `GET /google/login` → `/api/auth/google/login` ✅

**Routes in auth.router**:
- `POST /login` → `/api/auth/login` ✅
- `GET /me` → `/api/auth/me` ✅
- `POST /logout` → `/api/auth/logout` ✅
- ~~`GET /google/url`~~ (removed) ✅
- ~~`GET /google/callback`~~ (removed) ✅

**Route Order**: Since `google_auth.router` is registered first, its routes should take precedence. ✅

## Possible Issues

### Issue 1: API Not Redeployed
**Symptom**: Route exists in code but returns 404
**Fix**: Redeploy API with latest code

### Issue 2: Route Conflict
**Symptom**: Different route matching first
**Analysis**: No conflict - `google_auth.router` is first and has the callback route

### Issue 3: Request Base URL Issue
**Symptom**: `request.base_url` might be wrong in Cloud Run
**Check**: The `get_redirect_uri()` function uses `request.base_url` which might be incorrect

### Issue 4: CORS Issue
**Symptom**: Request blocked before reaching route
**Check**: CORS should allow all origins in dev, but check settings

## Debugging Steps

### 1. Check if Route is Registered
Test the endpoint directly:
```bash
curl -v "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback?code=test"
```

Expected:
- If route exists: 400 Bad Request (invalid code) or redirect
- If route doesn't exist: 404 Not Found

### 2. Check API Logs
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
  --limit=50 \
  --project=buildtrace-prod
```

Look for:
- Route registration logs
- Request logs showing the callback endpoint being hit
- Any 404 errors

### 3. Check API Docs
```bash
curl "https://buildtrace-api-okidmickfa-uc.a.run.app/docs"
```

Check if `/api/auth/google/callback` appears in the OpenAPI docs.

### 4. Verify Deployment
```bash
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --format='value(status.latestReadyRevisionName,status.url)'
```

Check when the latest revision was created.

## Most Likely Solution

The API needs to be **redeployed** with the latest code. The route exists in the source but the deployed version doesn't have it.

**Redeploy Command**:
```bash
cd Overlay-main/infra
./REDEPLOY_API.sh
```

Or manually:
```bash
cd Overlay-main
docker build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest \
  -f api/Dockerfile .

docker push us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest

gcloud run services update buildtrace-api \
  --region=us-central1 \
  --project=buildtrace-prod \
  --image=us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest
```

## Flow Diagram

```
User clicks "Sign in with Google"
    ↓
Frontend: GET /api/auth/google/url
    ↓
API: Returns Google OAuth URL
    ↓
Frontend: Redirects to Google
    ↓
Google: User authenticates
    ↓
Google: Redirects to /api/auth/google/callback?code=...
    ↓
API: ❌ Returns 404 Not Found (ROUTE NOT DEPLOYED)
    ↓
Should: Process code, create JWT, redirect to frontend with token
```

## Next Steps

1. **Redeploy API** with latest code
2. **Verify route exists** by checking `/docs` endpoint
3. **Test callback** with a test code
4. **Check logs** for any errors
5. **Verify Google Console** has correct redirect URI
