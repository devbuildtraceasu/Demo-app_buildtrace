# Google OAuth Setup Guide for BuildTrace

## Step 1: Create Google OAuth Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select your project: **buildtrace-prod**
3. Navigate to **APIs & Services** → **Credentials**
4. Click **+ CREATE CREDENTIALS** → **OAuth client ID**

### OAuth Client Configuration:

**Application type:** Web application

**Name:** BuildTrace Production

**Authorized JavaScript origins:**
```
https://buildtrace-frontend-okidmickfa-uc.a.run.app
```

**Authorized redirect URIs:**
```
https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback
```

5. Click **CREATE**
6. **SAVE** the following credentials:
   - **Client ID** (looks like: xxx.apps.googleusercontent.com)
   - **Client Secret** (keep this secure!)

## Step 2: Configure OAuth Consent Screen

If you haven't already:

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (for testing) or **Internal** (if you have Google Workspace)
3. Fill in the required fields:
   - **App name:** BuildTrace
   - **User support email:** Your email
   - **Developer contact email:** Your email
4. Add scopes:
   - `.../auth/userinfo.email`
   - `.../auth/userinfo.profile`
   - `openid`
5. Add test users (if using External with testing status)
6. Click **SAVE AND CONTINUE**

## Step 3: Set Environment Variables

You'll need to set these secrets in Google Cloud Run:

### For Frontend Service (buildtrace-frontend):

```bash
GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET="your-client-secret"
SESSION_SECRET="generate-a-random-secret-here"
DATABASE_URL="postgresql://user:pass@/cloudsql/project:region:instance/database"
```

### To generate a SESSION_SECRET:
```bash
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"
```

## Step 4: Set Secrets in Cloud Run

```bash
# Set Google OAuth credentials
gcloud run services update buildtrace-frontend \
  --region=us-central1 \
  --project=buildtrace-prod \
  --set-env-vars="GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com" \
  --set-secrets="GOOGLE_CLIENT_SECRET=google-client-secret:latest" \
  --set-secrets="SESSION_SECRET=session-secret:latest"
```

### Creating Secrets First:

```bash
# Create Google Client Secret
echo -n "your-google-client-secret" | gcloud secrets create google-client-secret \
  --data-file=- \
  --project=buildtrace-prod

# Create Session Secret
node -e "console.log(require('crypto').randomBytes(32).toString('hex'))" | \
  gcloud secrets create session-secret \
  --data-file=- \
  --project=buildtrace-prod

# Grant Cloud Run access to secrets
gcloud secrets add-iam-policy-binding google-client-secret \
  --member="serviceAccount:$(gcloud iam service-accounts list --filter='displayName:Compute Engine default service account' --format='value(email)')" \
  --role="roles/secretmanager.secretAccessor" \
  --project=buildtrace-prod

gcloud secrets add-iam-policy-binding session-secret \
  --member="serviceAccount:$(gcloud iam service-accounts list --filter='displayName:Compute Engine default service account' --format='value(email)')" \
  --role="roles/secretmanager.secretAccessor" \
  --project=buildtrace-prod
```

## Step 5: Required Environment Variables Summary

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | xxx.apps.googleusercontent.com |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | Secret string from Google |
| `SESSION_SECRET` | Random secret for session encryption | 64-char hex string |
| `DATABASE_URL` | PostgreSQL connection string | postgresql://... |
| `NODE_ENV` | Environment | production |

## Next Steps

After obtaining your Google OAuth credentials, I will:
1. Update the authentication code to use Google OAuth
2. Replace Replit OIDC with Google OAuth strategy
3. Test the authentication flow
4. Deploy the updated application

## Testing

Once deployed, test the auth flow:
1. Visit https://buildtrace-frontend-okidmickfa-uc.a.run.app
2. Click "Sign in with Google"
3. Authorize the application
4. You should be redirected back and authenticated

## Troubleshooting

### "redirect_uri_mismatch" error
- Verify the redirect URI in Google Console exactly matches: `https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback`
- Check for trailing slashes

### "401 Unauthorized" errors
- Verify environment variables are set correctly
- Check Cloud Run logs: `gcloud logging read "resource.type=cloud_run_revision" --limit=50 --project=buildtrace-prod`

### Session issues
- Verify DATABASE_URL is correct and accessible
- Check that the `sessions` table exists in your database
