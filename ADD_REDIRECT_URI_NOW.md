# ADD REDIRECT URI TO GOOGLE CONSOLE - DO THIS NOW

## The Error

Google is rejecting the request because this redirect URI is **NOT registered**:
```
https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

## Step-by-Step Fix (5 minutes)

### Step 1: Open Google Cloud Console

**Click this link:**
https://console.cloud.google.com/apis/credentials?project=buildtrace-prod

### Step 2: Find Your OAuth Client

1. Look for **OAuth 2.0 Client IDs** section
2. Find the client with ID: `926202951836-oc1enmumkl9ejs05hf8dvqvp78thtod3.apps.googleusercontent.com`
3. Click the **pencil/edit icon** (or click on the client name)

### Step 3: Add Redirect URI

1. Scroll down to **Authorized redirect URIs**
2. Click **+ ADD URI** button
3. **Copy and paste EXACTLY this** (no spaces, no trailing slash):
   ```
   https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
   ```
4. Click **SAVE** at the bottom

### Step 4: Add JavaScript Origin (if not there)

1. Scroll to **Authorized JavaScript origins**
2. If it's empty or doesn't have the frontend URL, click **+ ADD URI**
3. Add:
   ```
   https://buildtrace-frontend-okidmickfa-uc.a.run.app
   ```
4. Click **SAVE**

### Step 5: Wait and Test

1. **Wait 1-2 minutes** for Google's changes to propagate
2. Go to: https://buildtrace-frontend-okidmickfa-uc.a.run.app
3. Click "Sign in with Google"
4. Should work now!

## Visual Checklist

Your OAuth client should have:

✅ **Authorized JavaScript origins:**
```
https://buildtrace-frontend-okidmickfa-uc.a.run.app
```

✅ **Authorized redirect URIs:**
```
https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback
```

## Common Mistakes to Avoid

❌ **DON'T add:**
- `https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback` (wrong - frontend URL)
- `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback/` (trailing slash)
- `http://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback` (HTTP not HTTPS)
- Any spaces before or after the URL

✅ **DO add:**
- `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback` (exact match)

## Still Not Working?

1. **Double-check** you copied the URL exactly (no typos)
2. **Wait 2-3 minutes** - Google can be slow
3. **Try incognito/private window** - clear browser cache
4. **Verify in console** - go back to credentials and make sure the URI is there

## Quick Command to Verify

After adding, you can verify the redirect URI is being sent correctly:

```bash
curl "https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url" | jq -r '.url' | grep -o 'redirect_uri=[^&]*'
```

This should show: `redirect_uri=https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback`
