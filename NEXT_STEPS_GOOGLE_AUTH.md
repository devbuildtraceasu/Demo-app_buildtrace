# Google OAuth Setup - Next Steps

I've prepared everything needed to add Google OAuth authentication to your BuildTrace application. Here's what to do next:

## ✅ What I've Done

1. ✅ Created Google OAuth authentication module (`Build-TraceFlow/server/auth/googleAuth.ts`)
2. ✅ Updated server routes to use Google OAuth instead of Replit OIDC
3. ✅ Installed required npm packages (`passport-google-oauth20`)
4. ✅ Created deployment script (`deploy-with-google-auth.sh`)
5. ✅ Created comprehensive setup guide (`GOOGLE_AUTH_SETUP.md`)

## 🎯 What You Need To Do

### Step 1: Create Google OAuth Credentials (5 minutes)

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials?project=buildtrace-prod)

2. Click **+ CREATE CREDENTIALS** → **OAuth client ID**

3. Configure:
   - **Application type:** Web application
   - **Name:** BuildTrace Production
   - **Authorized JavaScript origins:**
     ```
     https://buildtrace-frontend-okidmickfa-uc.a.run.app
     ```
   - **Authorized redirect URIs:**
     ```
     https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback
     ```

4. Click **CREATE** and save:
   - ✏️ **Client ID** (looks like: `xxx.apps.googleusercontent.com`)
   - ✏️ **Client Secret** (keep this secure!)

### Step 2: Deploy with Google OAuth (2 minutes)

Run the deployment script I created:

```bash
# Export your Google OAuth credentials
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-client-secret"

# Run deployment
./deploy-with-google-auth.sh
```

The script will:
- ✅ Create secure secrets in Google Secret Manager
- ✅ Grant Cloud Run access to secrets
- ✅ Build and deploy the updated frontend
- ✅ Configure all environment variables

### Step 3: Test Authentication (1 minute)

1. Visit: https://buildtrace-frontend-okidmickfa-uc.a.run.app
2. Click "Sign in with Google" (or navigate to `/api/auth/google`)
3. Authorize the application
4. You should be redirected back and authenticated!

### Step 4: Verify It's Working

Test the API with authentication:

```bash
# Check auth status
curl https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/status

# After logging in via browser, test API
curl https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/projects
# Should return your projects, not "Not authenticated"
```

## 🔧 Manual Deployment (Alternative)

If you prefer to deploy manually:

```bash
cd Build-TraceFlow

# Build
docker build -t gcr.io/buildtrace-prod/buildtrace-frontend:latest .
docker push gcr.io/buildtrace-prod/buildtrace-frontend:latest

# Create secrets
echo -n "YOUR_CLIENT_SECRET" | gcloud secrets create google-client-secret --data-file=- --project=buildtrace-prod
echo -n "$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")" | gcloud secrets create session-secret --data-file=- --project=buildtrace-prod

# Deploy
gcloud run deploy buildtrace-frontend \
  --image=gcr.io/buildtrace-prod/buildtrace-frontend:latest \
  --region=us-central1 \
  --project=buildtrace-prod \
  --set-env-vars="GOOGLE_CLIENT_ID=YOUR_CLIENT_ID" \
  --set-secrets="GOOGLE_CLIENT_SECRET=google-client-secret:latest,SESSION_SECRET=session-secret:latest"
```

## 🐛 Troubleshooting

### "redirect_uri_mismatch" Error
- Double-check the redirect URI in Google Console exactly matches:
  `https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback`
- No trailing slashes
- Exact protocol (https)

### "Not authenticated" Still Showing
- Check Cloud Run logs:
  ```bash
  gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-frontend" --limit=50 --project=buildtrace-prod
  ```
- Verify environment variables are set correctly
- Make sure you're testing with the same browser where you logged in

### Database Connection Issues
- Verify Cloud SQL instance name is correct
- Check that the database exists and is accessible
- Verify the `sessions` table exists

## 📚 Additional Resources

- Full setup guide: `GOOGLE_AUTH_SETUP.md`
- Deployment script: `deploy-with-google-auth.sh`
- Google OAuth module: `Build-TraceFlow/server/auth/googleAuth.ts`

## 🎉 After Authentication Works

Once authentication is working, you can test:
1. ✅ Project creation
2. ✅ File upload and processing
3. ✅ AI analysis features

All the features you wanted to test will be accessible once users are authenticated!

---

**Need Help?**
- Check logs: `gcloud logging read ...`
- Review `GOOGLE_AUTH_SETUP.md` for detailed troubleshooting
- The auth module includes helpful console warnings if credentials are missing
