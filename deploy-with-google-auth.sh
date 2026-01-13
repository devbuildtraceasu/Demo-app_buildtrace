#!/bin/bash

#######################################################
# Deploy BuildTrace with Google OAuth Authentication
#######################################################

set -e

PROJECT_ID="buildtrace-prod"
REGION="us-central1"
FRONTEND_SERVICE="buildtrace-frontend"

echo "🚀 BuildTrace - Google OAuth Deployment"
echo "========================================"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ gcloud CLI not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if logged in
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | grep -q .; then
    echo "❌ Not logged into gcloud. Please run: gcloud auth login"
    exit 1
fi

# Set project
echo "📝 Setting project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# Check for required environment variables
echo ""
echo "🔐 Checking Google OAuth Configuration..."
echo ""

if [ -z "$GOOGLE_CLIENT_ID" ]; then
    echo "⚠️  GOOGLE_CLIENT_ID not set!"
    echo ""
    read -p "Enter your Google OAuth Client ID: " GOOGLE_CLIENT_ID
fi

if [ -z "$GOOGLE_CLIENT_SECRET" ]; then
    echo "⚠️  GOOGLE_CLIENT_SECRET not set!"
    echo ""
    read -sp "Enter your Google OAuth Client Secret: " GOOGLE_CLIENT_SECRET
    echo ""
fi

if [ -z "$SESSION_SECRET" ]; then
    echo "⚠️  SESSION_SECRET not set! Generating one..."
    SESSION_SECRET=$(node -e "console.log(require('crypto').randomBytes(32).toString('hex'))")
    echo "✅ Generated SESSION_SECRET"
fi

echo ""
echo "✅ OAuth credentials configured"

# Create secrets if they don't exist
echo ""
echo "📦 Creating/Updating secrets..."

# Google Client Secret
echo -n "$GOOGLE_CLIENT_SECRET" | gcloud secrets create google-client-secret \
    --data-file=- \
    --project=$PROJECT_ID 2>/dev/null || \
echo -n "$GOOGLE_CLIENT_SECRET" | gcloud secrets versions add google-client-secret \
    --data-file=- \
    --project=$PROJECT_ID

echo "✅ Created/Updated google-client-secret"

# Session Secret
echo -n "$SESSION_SECRET" | gcloud secrets create session-secret \
    --data-file=- \
    --project=$PROJECT_ID 2>/dev/null || \
echo -n "$SESSION_SECRET" | gcloud secrets versions add session-secret \
    --data-file=- \
    --project=$PROJECT_ID

echo "✅ Created/Updated session-secret"

# Grant access to secrets
echo ""
echo "🔒 Granting Cloud Run access to secrets..."

SERVICE_ACCOUNT=$(gcloud iam service-accounts list \
    --filter="displayName:'Compute Engine default service account'" \
    --format="value(email)" \
    --project=$PROJECT_ID)

gcloud secrets add-iam-policy-binding google-client-secret \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID >/dev/null

gcloud secrets add-iam-policy-binding session-secret \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID >/dev/null

echo "✅ Secrets access configured"

# Build and deploy frontend
echo ""
echo "🏗️  Building and deploying frontend..."
echo ""

cd Build-TraceFlow

# Build the Docker image
echo "📦 Building Docker image..."
docker build -t gcr.io/$PROJECT_ID/$FRONTEND_SERVICE:latest .

echo "📤 Pushing to Google Container Registry..."
docker push gcr.io/$PROJECT_ID/$FRONTEND_SERVICE:latest

# Deploy to Cloud Run
echo ""
echo "🚀 Deploying to Cloud Run..."

gcloud run deploy $FRONTEND_SERVICE \
    --image=gcr.io/$PROJECT_ID/$FRONTEND_SERVICE:latest \
    --region=$REGION \
    --project=$PROJECT_ID \
    --platform=managed \
    --allow-unauthenticated \
    --set-env-vars="NODE_ENV=production,GOOGLE_CLIENT_ID=$GOOGLE_CLIENT_ID,GOOGLE_CALLBACK_URL=https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback" \
    --set-secrets="GOOGLE_CLIENT_SECRET=google-client-secret:latest,SESSION_SECRET=session-secret:latest" \
    --set-cloudsql-instances="$PROJECT_ID:$REGION:buildtrace-db" \
    --update-env-vars="DATABASE_URL=postgresql://overlay:overlay_dev_password@localhost/overlay_dev?host=/cloudsql/$PROJECT_ID:$REGION:buildtrace-db"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your application is available at:"
echo "   https://buildtrace-frontend-okidmickfa-uc.a.run.app"
echo ""
echo "🔐 Google OAuth Configuration:"
echo "   Client ID: $GOOGLE_CLIENT_ID"
echo "   Callback URL: https://buildtrace-frontend-okidmickfa-uc.a.run.app/api/auth/google/callback"
echo ""
echo "⚠️  Make sure the callback URL is added to your Google OAuth credentials!"
echo ""
echo "📝 Test authentication:"
echo "   1. Visit https://buildtrace-frontend-okidmickfa-uc.a.run.app"
echo "   2. Click 'Sign in with Google'"
echo "   3. Authorize the application"
echo ""
