# Add Redirect URI to Google OAuth - Step by Step

## The Error

You're seeing:
```
Error 400: redirect_uri_mismatch
redirect_uri=https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

This means the redirect URI is **not registered** in Google Cloud Console.

## Fix: Add Redirect URI to Google Console

### Step 1: Open Google Cloud Console

Go to: **https://console.cloud.google.com/apis/credentials?project=buildtrace-prod**

(Or navigate: APIs & Services → Credentials)

### Step 2: Find Your OAuth Client

1. Look for **OAuth 2.0 Client IDs** section
2. Find your OAuth client (should have your Client ID)
3. Click the **pencil/edit icon** (or click on the client name)

### Step 3: Add Redirect URI

1. Scroll down to **Authorized redirect URIs**
2. Click **+ ADD URI**
3. Enter **EXACTLY** this (copy-paste to avoid typos):
   ```
   https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
   ```
4. **Important checks:**
   - ✅ Must be HTTPS (not HTTP)
   - ✅ No trailing slash
   - ✅ Exact match (case-sensitive)
   - ✅ No extra spaces

### Step 4: Add JavaScript Origin (if not already there)

1. Scroll to **Authorized JavaScript origins**
2. Click **+ ADD URI** if not already present
3. Add:
   ```
   https://buildtrace-frontend-okidmickfa-uc.a.run.app
   ```

### Step 5: Save

1. Click **SAVE** at the bottom
2. Wait 1-2 minutes for changes to propagate

### Step 6: Test Again

1. Visit: https://buildtrace-frontend-okidmickfa-uc.a.run.app
2. Click "Sign in with Google"
3. Should work now!

## Visual Guide

Your OAuth client configuration should look like this:

**Authorized JavaScript origins:**
```
https://buildtrace-frontend-okidmickfa-uc.a.run.app
```

**Authorized redirect URIs:**
```
https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

## Common Mistakes

❌ **Wrong redirect URI:**
- `https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback` (frontend URL - WRONG)
- `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback/` (trailing slash - WRONG)
- `http://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback` (HTTP not HTTPS - WRONG)
- `https://buildtrace-api-okidmickfa-uc.a.run.app/auth/google/callback` (missing /api - WRONG)

✅ **Correct redirect URI:**
- `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback` (exact match)

## Still Not Working?

1. **Double-check the URI** - Copy-paste it exactly
2. **Wait 2-3 minutes** - Google's changes can take time to propagate
3. **Clear browser cache** - Try incognito/private window
4. **Check API logs** to see what redirect URI it's actually using:
   ```bash
   gcloud logging read \
     "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
     --limit=20 \
     --project=buildtrace-prod \
     --format=json | grep -i redirect
   ```
