# GCP Console Setup Steps

This document outlines the manual steps you need to perform in the Google Cloud Console to complete the deployment.

## Prerequisites

- GCP Project: `buildtrace-dev`
- Billing account linked to the project
- Owner or Editor role on the project

## Step 1: Enable Billing

1. Go to [Google Cloud Console Billing](https://console.cloud.google.com/billing)
2. Select your billing account
3. Click "Link a project"
4. Select `buildtrace-dev` project
5. Click "Set Account"

## Step 2: Enable Required APIs

The Terraform script will automatically enable most APIs, but you can also enable them manually:

1. Go to [APIs & Services > Library](https://console.cloud.google.com/apis/library)
2. Enable the following APIs:
   - **Cloud Run API** (`run.googleapis.com`)
   - **Cloud SQL Admin API** (`sqladmin.googleapis.com`)
   - **Cloud Storage API** (`storage.googleapis.com`)
   - **Cloud Pub/Sub API** (`pubsub.googleapis.com`)
   - **Artifact Registry API** (`artifactregistry.googleapis.com`)
   - **Secret Manager API** (`secretmanager.googleapis.com`)
   - **Service Networking API** (`servicenetworking.googleapis.com`)
   - **Cloud Resource Manager API** (`cloudresourcemanager.googleapis.com`)

Or use the command line:
```bash
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  pubsub.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  servicenetworking.googleapis.com \
  cloudresourcemanager.googleapis.com \
  --project=buildtrace-dev
```

## Step 3: Create Terraform State Bucket

1. Go to [Cloud Storage](https://console.cloud.google.com/storage)
2. Click "Create Bucket"
3. Name: `buildtrace-terraform-state`
4. Location: `us-central1` (or your preferred region)
5. Storage class: Standard
6. Access control: Uniform
7. Click "Create"
8. Enable versioning:
   - Click on the bucket
   - Go to "Configuration" tab
   - Enable "Object versioning"

Or use the command line:
```bash
gsutil mb -p buildtrace-dev -l us-central1 gs://buildtrace-terraform-state
gsutil versioning set on gs://buildtrace-terraform-state
```

## Step 4: Verify Terraform Configuration

1. Navigate to `Overlay-main/infra/terraform/`
2. Ensure `terraform.tfvars` exists and is configured with:
   - `project_id = "buildtrace-dev"`
   - `region = "us-central1"` (or your preferred region)
   - `cors_origins` with your frontend URLs

## Step 5: Run Terraform

```bash
cd Overlay-main/infra/terraform
terraform init
terraform plan
terraform apply
```

This will create:
- VPC network and subnet
- Cloud SQL PostgreSQL instance
- Cloud Storage buckets
- Pub/Sub topics and subscriptions
- Artifact Registry repository
- Service accounts and IAM bindings
- Cloud Run services (initially without images)

## Step 6: Configure Secrets

Run the setup script:
```bash
cd Overlay-main/infra
chmod +x setup-secrets.sh
./setup-secrets.sh
```

Or manually create secrets in [Secret Manager](https://console.cloud.google.com/security/secret-manager):
- `openai-api-key`
- `gemini-api-key` (optional)
- `jwt-secret`
- `google-client-id`
- `google-client-secret`

## Step 7: Build and Push Docker Images

```bash
cd Overlay-main/infra
chmod +x deploy.sh
./deploy.sh
```

Or manually:
```bash
# Configure Docker
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push API
docker build -t us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/api:latest -f api/Dockerfile .
docker push us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/api:latest

# Build and push Worker
docker build -t us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/overlay-worker:latest -f vision/worker/Dockerfile .
docker push us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/overlay-worker:latest
```

## Step 8: Update Cloud Run Services with Secrets

After pushing images, update Cloud Run services to use secrets:

### API Service

1. Go to [Cloud Run](https://console.cloud.google.com/run)
2. Click on `buildtrace-api` service
3. Click "Edit & Deploy New Revision"
4. Under "Variables & Secrets", add:
   - `OPENAI_API_KEY` → Secret: `openai-api-key`
   - `GEMINI_API_KEY` → Secret: `gemini-api-key` (if using)
   - `JWT_SECRET` → Secret: `jwt-secret`
   - `GOOGLE_CLIENT_ID` → Secret: `google-client-id`
   - `GOOGLE_CLIENT_SECRET` → Secret: `google-client-secret`
5. Update `GOOGLE_REDIRECT_URI` to your production API URL
6. Update `CORS_ORIGINS` to include your frontend URL
7. Click "Deploy"

### Worker Service

1. Click on `buildtrace-overlay-worker` service
2. Click "Edit & Deploy New Revision"
3. Under "Variables & Secrets", add:
   - `OPENAI_API_KEY` → Secret: `openai-api-key`
   - `GEMINI_API_KEY` → Secret: `gemini-api-key` (if using)
4. Click "Deploy"

## Step 9: Run Database Migrations

```bash
cd Overlay-main/infra
chmod +x run-migrations.sh
./run-migrations.sh
```

Or manually:
1. Install Cloud SQL Proxy
2. Connect to the database
3. Run Prisma migrations:
   ```bash
   cd Overlay-main/web
   export DATABASE_URL="postgresql://buildtrace:PASSWORD@localhost:5432/buildtrace"
   npx prisma migrate deploy
   ```

## Step 10: Enable pgvector Extension (Optional)

If you need vector search capabilities:

1. Connect to Cloud SQL using Cloud SQL Proxy
2. Run:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

## Step 11: Deploy Frontend

### Option A: Firebase Hosting

1. Install Firebase CLI: `npm install -g firebase-tools`
2. Initialize Firebase in `Build-TraceFlow`:
   ```bash
   cd Build-TraceFlow
   firebase init hosting
   ```
3. Build with production API URL:
   ```bash
   VITE_API_URL="https://buildtrace-api-XXXXX.run.app/api" npm run build
   ```
4. Deploy:
   ```bash
   firebase deploy --only hosting
   ```

### Option B: Cloud Run (Static)

1. Build the frontend:
   ```bash
   cd Build-TraceFlow
   VITE_API_URL="https://buildtrace-api-XXXXX.run.app/api" npm run build
   ```
2. Create Dockerfile for static hosting:
   ```dockerfile
   FROM nginx:alpine
   COPY dist/public /usr/share/nginx/html
   COPY nginx.conf /etc/nginx/conf.d/default.conf
   ```
3. Build and push:
   ```bash
   docker build -t us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/frontend:latest .
   docker push us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/frontend:latest
   ```
4. Deploy to Cloud Run:
   ```bash
   gcloud run deploy buildtrace-frontend \
     --image us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/frontend:latest \
     --region us-central1 \
     --allow-unauthenticated \
     --port 80
   ```

## Step 12: Set Up Monitoring

1. Go to [Cloud Monitoring](https://console.cloud.google.com/monitoring)
2. Create dashboards for:
   - Cloud Run service metrics (requests, latency, errors)
   - Cloud SQL metrics (CPU, memory, connections)
   - Pub/Sub metrics (message count, backlog)
3. Set up billing alerts:
   - Go to [Billing > Budgets & Alerts](https://console.cloud.google.com/billing/budgets)
   - Create a budget with alerts at 50%, 90%, and 100% of your monthly limit

## Step 13: Verify Deployment

1. Test API health:
   ```bash
   curl https://buildtrace-api-XXXXX.run.app/health
   ```
2. Test database connectivity (check Cloud Run logs)
3. Test file upload to GCS
4. Test Pub/Sub message publishing
5. Test worker job processing
6. Test frontend connectivity to API

## Troubleshooting

### Cloud Run Service Won't Start

- Check logs: `gcloud run services logs read buildtrace-api --region=us-central1`
- Verify secrets are accessible by service account
- Check Cloud SQL connection name is correct

### Database Connection Failed

- Verify Cloud SQL instance is running
- Check service account has `roles/cloudsql.client` role
- Verify Cloud SQL connection name in environment variables

### Storage Upload Failed

- Verify service account has `roles/storage.objectAdmin` role
- Check bucket name is correct
- Verify GCS client library is installed

### Pub/Sub Messages Not Processing

- Check subscription exists
- Verify service account has `roles/pubsub.subscriber` role
- Check worker service is running and connected

## Next Steps

- Set up CI/CD with Cloud Build
- Configure custom domain for API and frontend
- Set up monitoring alerts
- Configure backup schedules
- Review and optimize costs
