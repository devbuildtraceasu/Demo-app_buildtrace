# Set CORS_ORIGINS Manually (When CLI Fails)

## The Problem

`gcloud` CLI has issues with JSON arrays containing brackets. Use Cloud Console instead.

## Quick Fix via Cloud Console

### Step 1: Get Your Frontend URL

```bash
gcloud run services describe buildtrace-frontend \
  --region us-central1 \
  --format='value(status.url)'
```

You should get: `https://buildtrace-frontend-okidmickfa-uc.a.run.app`

### Step 2: Open Cloud Console

1. Go to: https://console.cloud.google.com/run
2. Select your project
3. Click on **buildtrace-api** service
4. Click **EDIT & DEPLOY NEW REVISION**

### Step 3: Set CORS_ORIGINS

1. Go to **Variables & Secrets** tab
2. Scroll to **Environment Variables** section
3. Find **CORS_ORIGINS** (or click **ADD VARIABLE** if missing)
4. Set the value to:

```
["https://buildtrace-frontend-okidmickfa-uc.a.run.app","http://localhost:3000","http://localhost:5000"]
```

**Important**: Copy-paste exactly, including the brackets and quotes.

### Step 4: Deploy

1. Click **DEPLOY** at the bottom
2. Wait for deployment to complete (~30 seconds)

## Verify It Worked

```bash
gcloud run services describe buildtrace-api \
  --region us-central1 \
  --format='value(spec.template.spec.containers[0].env)' | grep CORS
```

You should see the production frontend URL first in the list.

## After Setting CORS_ORIGINS

Redeploy the API with the updated redirect code:

```bash
cd Overlay-main/infra
./REDEPLOY_API.sh
```

This will deploy the code that prefers production URLs over localhost.

## Why This Happens

`gcloud` CLI tries to parse JSON arrays as dictionary arguments, which fails. Cloud Console handles JSON values correctly.
