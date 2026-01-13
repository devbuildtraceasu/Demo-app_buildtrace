# BuildTrace GCP Deployment - Complete

## 🎉 Deployment Status: LIVE

All services are deployed and operational on Google Cloud Platform.

## 📍 Service URLs

- **Frontend**: https://buildtrace-frontend-okidmickfa-uc.a.run.app
- **API**: https://buildtrace-api-okidmickfa-uc.a.run.app
- **Worker**: https://buildtrace-overlay-worker-926202951836.us-central1.run.app (internal only)

## 🏗️ Infrastructure Overview

### Project Details
- **Project ID**: `buildtrace-prod`
- **Region**: `us-central1`
- **Environment**: Development

### Resources Created

#### Compute & Networking
- **VPC Network**: `buildtrace-vpc` with subnet `buildtrace-subnet` (10.0.0.0/24)
- **VPC Connector**: `buildtrace-vpc-connector` (for Cloud Run to access private IP Cloud SQL)
- **Private Services Connection**: For Cloud SQL private IP access

#### Database
- **Cloud SQL Instance**: `buildtrace-db`
  - PostgreSQL 15
  - Private IP only (no public IP)
  - Connection: `buildtrace-prod:us-central1:buildtrace-db`
  - Database: `buildtrace`
  - User: `buildtrace`
  - Migrations: ✅ Applied

#### Storage
- **Cloud Storage Buckets**:
  - `buildtrace-prod-uploads` - User file uploads
  - `buildtrace-prod-overlays` - Generated overlay images

#### Messaging
- **Pub/Sub Topics**:
  - `vision` - Main job queue
  - `vision-dlq` - Dead letter queue
- **Pub/Sub Subscriptions**:
  - `vision-worker-subscription` - Worker subscription

#### Container Registry
- **Artifact Registry**: `buildtrace` repository (Docker images)
  - Location: `us-central1`
  - Images:
    - `api:latest`
    - `overlay-worker:latest`
    - `frontend:latest`

#### Secrets
- `buildtrace-db-password` - Database password
- `openai-api-key` - OpenAI API key
- `gemini-api-key` - Google Gemini API key
- `jwt-secret` - JWT signing secret
- `google-client-id` - Google OAuth client ID
- `google-client-secret` - Google OAuth client secret
- `google-redirect-uri` - Google OAuth redirect URI

#### Service Accounts
- `buildtrace-api@buildtrace-prod.iam.gserviceaccount.com`
  - Roles: Storage Object Admin, Cloud SQL Client, Pub/Sub Publisher, Secret Manager Secret Accessor
- `buildtrace-worker@buildtrace-prod.iam.gserviceaccount.com`
  - Roles: Storage Object Admin, Cloud SQL Client, Pub/Sub Subscriber, Secret Manager Secret Accessor

#### Cloud Run Services
- **API Service**: `buildtrace-api`
  - Port: 8000
  - Min instances: 0
  - Max instances: 2
  - CPU: 2
  - Memory: 2Gi
  - Public access: ✅ Enabled

- **Worker Service**: `buildtrace-overlay-worker`
  - Port: 8080 (health check)
  - Min instances: 1 (always running for Pub/Sub)
  - Max instances: 2
  - CPU: 2
  - Memory: 4Gi
  - Public access: ❌ Internal only

- **Frontend Service**: `buildtrace-frontend`
  - Port: 8080
  - Min instances: 0
  - Max instances: 2
  - CPU: 1
  - Memory: 256Mi
  - Public access: ✅ Enabled
  - **Note**: React + Vite application (not Next.js). Serves static files via nginx. Replit integration is development-only.

## 🔧 Configuration

### Environment Variables

#### API Service
- `DB_USER`: `buildtrace`
- `DB_NAME`: `buildtrace`
- `DB_PASSWORD`: From Secret Manager
- `CLOUD_SQL_CONNECTION_NAME`: `buildtrace-prod:us-central1:buildtrace-db`
- `STORAGE_BACKEND`: `gcs`
- `STORAGE_BUCKET`: `buildtrace-prod-uploads`
- `PUBSUB_PROJECT_ID`: `buildtrace-prod`
- `VISION_TOPIC`: `vision`
- `CORS_ORIGINS`: JSON array of allowed origins

#### Worker Service
- `DB_HOST`: `/cloudsql/buildtrace-prod:us-central1:buildtrace-db`
- `DB_PORT`: `5432`
- `DB_NAME`: `buildtrace`
- `DB_USER`: `buildtrace`
- `DB_PASSWORD`: From Secret Manager
- `STORAGE_BACKEND`: `gcs`
- `STORAGE_BUCKET`: `buildtrace-prod-overlays`
- `PUBSUB_PROJECT_ID`: `buildtrace-prod`
- `VISION_TOPIC`: `vision`
- `VISION_SUBSCRIPTION`: `vision-worker-subscription`
- `OPENAI_API_KEY`: From Secret Manager
- `GEMINI_API_KEY`: From Secret Manager

#### Frontend
- `VITE_API_URL`: `https://buildtrace-api-okidmickfa-uc.a.run.app`

## 🚀 Deployment Process

### Initial Setup
1. Created new GCP project: `buildtrace-prod`
2. Enabled required APIs
3. Created service accounts
4. Set up billing

### Infrastructure Deployment
```bash
cd Overlay-main/infra/terraform
terraform init
terraform apply
```

### Database Setup
```bash
# Enable public IP temporarily
gcloud sql instances patch buildtrace-db --assign-ip --project=buildtrace-prod

# Add authorized network
MY_IP=$(curl -s ifconfig.me)
gcloud sql instances patch buildtrace-db --authorized-networks=$MY_IP/32 --project=buildtrace-prod

# Run migrations
cd Overlay-main/web
export DATABASE_URL="postgresql://buildtrace:$(gcloud secrets versions access latest --secret=buildtrace-db-password --project=buildtrace-prod)@$(gcloud sql instances describe buildtrace-db --project=buildtrace-prod --format="get(ipAddresses[0].ipAddress)"):5432/buildtrace"
npx prisma migrate deploy

# Disable public IP
gcloud sql instances patch buildtrace-db --no-assign-ip --project=buildtrace-prod
```

### Application Deployment
```bash
# Build and push images
cd Overlay-main/infra
./BUILD_AND_PUSH.sh

# Deploy frontend
./DEPLOY_FRONTEND.sh
```

## 🔐 Security

- Cloud SQL uses private IP only (no public access)
- VPC connector enables secure private network access
- Secrets stored in Secret Manager
- Service accounts with minimal required permissions
- CORS configured for specific frontend origins

## 📝 Key Fixes Applied

### 1. API CORS Configuration
- Fixed CORS parsing to handle JSON array from environment variable
- Added frontend URLs to allowed origins
- Verified CORS working with OPTIONS requests

### 2. Worker Database Connection
- Added VPC connector for Cloud Run to access private IP Cloud SQL
- Fixed Unix socket path handling in worker code
- Added socket existence verification
- Worker now successfully connects via Unix socket

### 3. Frontend API Path
- Fixed `API_BASE` to include `/api` prefix
- Frontend now correctly calls `/api/projects` instead of `/projects`

### 4. Database Migrations
- Ran Prisma migrations to create all required tables
- Database schema is up to date

## 📊 Monitoring

### View Logs
```bash
# API logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" --limit=50 --project=buildtrace-prod

# Worker logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" --limit=50 --project=buildtrace-prod
```

### Check Service Status
```bash
gcloud run services describe buildtrace-api --region=us-central1 --project=buildtrace-prod
gcloud run services describe buildtrace-overlay-worker --region=us-central1 --project=buildtrace-prod
gcloud run services describe buildtrace-frontend --region=us-central1 --project=buildtrace-prod
```

## 🔄 Update Process

### Update API
```bash
cd Overlay-main/infra
./BUILD_AND_PUSH.sh
gcloud run services update buildtrace-api --region=us-central1 --project=buildtrace-prod --image=us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/api:latest
```

### Update Worker
```bash
cd Overlay-main/infra
./BUILD_AND_PUSH.sh
gcloud run services update buildtrace-overlay-worker --region=us-central1 --project=buildtrace-prod --image=us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/overlay-worker:latest
```

### Update Frontend
```bash
cd Overlay-main/infra
./DEPLOY_FRONTEND.sh
```

## 📚 Documentation Files

- `README.md` - Infrastructure overview
- `QUICKSTART.md` - Quick deployment guide
- `CONSOLE_STEPS.md` - Manual console steps
- `DEPLOYMENT_SUMMARY.md` - Deployment summary
- `MANUAL_IAM_SETUP.md` - IAM configuration guide
- `run-migrations.sh` - Database migration script

## 🐛 Troubleshooting

### Worker Can't Connect to Database
- Verify VPC connector is running: `gcloud compute networks vpc-access connectors describe buildtrace-vpc-connector --region=us-central1 --project=buildtrace-prod`
- Check Cloud SQL instance is running: `gcloud sql instances describe buildtrace-db --project=buildtrace-prod`
- Verify service account has Cloud SQL Client role

### API Returns 404
- Verify endpoint includes `/api` prefix
- Check API logs for routing errors
- Verify CORS configuration

### Frontend Can't Reach API
- Check CORS origins include frontend URL
- Verify API is publicly accessible
- Check browser console for CORS errors

## 📅 Deployment Date
January 12, 2026

## ✅ Verification Checklist

- [x] VPC network and subnet created
- [x] Cloud SQL instance created with private IP
- [x] Database migrations applied
- [x] Storage buckets created
- [x] Pub/Sub topics and subscriptions created
- [x] Artifact Registry repository created
- [x] Secrets created in Secret Manager
- [x] Service accounts created with proper roles
- [x] VPC connector created
- [x] API service deployed and accessible
- [x] Worker service deployed and connected to database
- [x] Frontend deployed and accessible
- [x] CORS configured correctly
- [x] All services healthy

## 🎯 Next Steps

1. Test project creation flow
2. Test file upload and processing
3. Test AI analysis feature
4. Monitor costs and usage
5. Set up Cloud Monitoring alerts
6. Configure custom domain (optional)
7. Set up CI/CD pipeline (optional)
