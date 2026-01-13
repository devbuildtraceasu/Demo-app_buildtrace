# BuildTrace GCP Deployment - Quick Start

## Prerequisites Check

```bash
# Verify you have these installed
gcloud --version    # Google Cloud SDK
terraform --version # >= 1.5.0
docker --version    # Docker CLI
```

## 5-Minute Setup

### 1. Authenticate & Set Project
```bash
gcloud auth login
gcloud config set project buildtrace-dev
```

### 2. Enable Billing & APIs
Go to [GCP Console](https://console.cloud.google.com):
- Enable billing for `buildtrace-dev` project
- Or run: `gcloud services enable run.googleapis.com sqladmin.googleapis.com storage.googleapis.com pubsub.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com --project=buildtrace-dev`

### 3. Create Terraform State Bucket
```bash
gsutil mb -p buildtrace-dev -l us-central1 gs://buildtrace-terraform-state
gsutil versioning set on gs://buildtrace-terraform-state
```

### 4. Configure Terraform
```bash
cd Overlay-main/infra/terraform
# terraform.tfvars is already created with buildtrace-dev
# Edit if you need to change region or other settings
```

### 5. Deploy Everything
```bash
cd Overlay-main/infra

# Deploy infrastructure and build images
./deploy.sh

# Setup secrets (interactive)
./setup-secrets.sh

# Run database migrations
./run-migrations.sh

# Deploy frontend
./deploy-frontend.sh firebase
```

## What Gets Created

- **Cloud SQL**: PostgreSQL 15 database
- **Cloud Storage**: 2 buckets (uploads, overlays)
- **Pub/Sub**: Topic and subscription for job queue
- **Artifact Registry**: Docker image repository
- **Cloud Run**: 2 services (API, Worker)
- **Service Accounts**: With appropriate permissions
- **Secrets**: For API keys and credentials

## Get Your URLs

After deployment, get your service URLs:

```bash
cd infra/terraform
terraform output api_url
```

Or check Cloud Run console:
- API: https://console.cloud.google.com/run
- Frontend: Check Firebase Hosting or Cloud Run

## Common Commands

```bash
# View API logs
gcloud run services logs read buildtrace-api --region=us-central1 --limit=50

# View worker logs
gcloud run services logs read buildtrace-overlay-worker --region=us-central1 --limit=50

# Update service with new image
gcloud run deploy buildtrace-api --image us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/api:latest --region us-central1

# Connect to database
gcloud sql connect buildtrace-db --user=buildtrace --database=buildtrace
```

## Troubleshooting

**"Permission denied" errors**
- Verify you have Owner or Editor role on the project
- Check service account permissions

**"API not enabled"**
- Enable required APIs (see step 2)
- Wait a few minutes for propagation

**"Image pull failed"**
- Verify image exists: `gcloud artifacts docker images list us-central1-docker.pkg.dev/buildtrace-dev/buildtrace`
- Check service account has Artifact Registry Reader role

**"Database connection failed"**
- Verify Cloud SQL instance is running
- Check connection name in environment variables
- Verify service account has Cloud SQL Client role

## Next Steps

1. Update `GOOGLE_REDIRECT_URI` in API service with production URL
2. Update `CORS_ORIGINS` with your frontend domain
3. Set up monitoring and alerts
4. Configure custom domains (optional)
5. Review costs and optimize

## Need Help?

- Detailed steps: See `CONSOLE_STEPS.md`
- Infrastructure docs: See `README.md`
- Deployment summary: See `DEPLOYMENT_SUMMARY.md`
