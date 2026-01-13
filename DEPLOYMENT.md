# BuildTrace Deployment Guide

Complete guide for deploying BuildTrace to Google Cloud Platform.

## 📍 Live Services

- **Frontend**: https://buildtrace-frontend-okidmickfa-uc.a.run.app
- **API**: https://buildtrace-api-okidmickfa-uc.a.run.app
- **Worker**: Internal Cloud Run service (Pub/Sub triggered)

## 🏗️ Architecture

### Services

1. **Frontend** (React + Vite)
   - Static files served via nginx on Cloud Run
   - Port: 8080
   - Environment: `VITE_API_URL` set at build time

2. **API** (FastAPI)
   - Python FastAPI service on Cloud Run
   - Port: 8000
   - Handles authentication, projects, drawings, comparisons

3. **Worker** (Python)
   - Processes drawing preprocessing, sheet analysis, block extraction
   - Triggered via Pub/Sub
   - Uses Gemini AI for block extraction

### Infrastructure

- **Database**: Cloud SQL PostgreSQL (private IP)
- **Storage**: Cloud Storage buckets
- **Messaging**: Pub/Sub topics and subscriptions
- **Networking**: VPC with connector for private Cloud SQL access

## 🚀 Quick Deployment

### Prerequisites

```bash
# Install gcloud CLI
# Authenticate
gcloud auth login
gcloud config set project buildtrace-prod
```

### Deploy All Services

```bash
# 1. Deploy infrastructure (Terraform)
cd Overlay-main/infra/terraform
terraform init
terraform apply

# 2. Build and push Docker images
cd ../..
./BUILD_AND_PUSH.sh

# 3. Deploy API and Worker (via Terraform or manually)
# API and Worker are deployed via Terraform

# 4. Deploy Frontend
./DEPLOY_FRONTEND.sh
```

## 🔐 Authentication Setup

### Google OAuth Configuration

1. **Create OAuth Credentials**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
   - Create OAuth 2.0 Client ID (Web application)
   - **Authorized redirect URI**: `https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/callback`

2. **Set Environment Variables on API Service**:
   ```bash
   cd Overlay-main/infra
   ./setup-google-auth.sh
   ```

3. **Set CORS_ORIGINS** (via Cloud Console - CLI has issues with JSON):
   - Go to Cloud Run → `buildtrace-api` → Edit
   - Variables & Secrets tab
   - Set `CORS_ORIGINS` to:
     ```json
     ["https://buildtrace-frontend-okidmickfa-uc.a.run.app","http://localhost:3000","http://localhost:5000"]
     ```

### Authentication Flow

1. User clicks "Sign in with Google" on frontend
2. Frontend calls `GET /api/auth/google/url`
3. API returns Google OAuth URL
4. User authenticates with Google
5. Google redirects to `/api/auth/google/callback` (on API)
6. API processes callback, creates JWT token
7. API redirects to frontend `/dashboard?token=<jwt>`
8. Frontend stores token and uses for authenticated requests

## 📝 Environment Variables

### API Service

- `GOOGLE_CLIENT_ID` - Google OAuth client ID
- `GOOGLE_CLIENT_SECRET` - From Secret Manager
- `GOOGLE_REDIRECT_URI` - OAuth callback URL
- `CORS_ORIGINS` - JSON array of allowed origins
- `DB_USER`, `DB_NAME`, `DB_PASSWORD` - Database credentials
- `CLOUD_SQL_CONNECTION_NAME` - Cloud SQL connection string
- `STORAGE_BACKEND` - `gcs`
- `STORAGE_BUCKET` - Storage bucket name
- `PUBSUB_PROJECT_ID` - GCP project ID
- `VISION_TOPIC` - Pub/Sub topic name

### Frontend Service

- `VITE_API_URL` - Set at build time (Docker build arg)
- `NODE_ENV` - `production`

### Worker Service

- Database and storage config (same as API)
- `VISION_SUBSCRIPTION` - Pub/Sub subscription name
- `OPENAI_API_KEY`, `GEMINI_API_KEY` - From Secret Manager

## 🔧 Common Operations

### Update API Service

```bash
cd Overlay-main/infra
./REDEPLOY_API.sh
```

### Update Frontend

```bash
cd Overlay-main/infra
./DEPLOY_FRONTEND.sh
```

### Update Worker

```bash
cd Overlay-main/infra
./BUILD_AND_PUSH.sh
# Then update Cloud Run service manually or via Terraform
```

### View Logs

```bash
# API logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
  --limit=50 --format="table(timestamp,severity,textPayload)"

# Worker logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=50 --format="table(timestamp,severity,textPayload)"
```

### Check Service Status

```bash
gcloud run services list --region=us-central1
```

## 🐛 Troubleshooting

### OAuth Redirect Goes to localhost

**Problem**: After login, redirects to `http://localhost:3000/dashboard`

**Solution**: 
1. Set `CORS_ORIGINS` on API service with production frontend URL first
2. Redeploy API with updated redirect logic

See `Overlay-main/infra/SET_CORS_MANUALLY.md` for detailed steps.

### Frontend Can't Connect to API

**Problem**: Frontend shows errors, can't reach API

**Solution**:
1. Check `VITE_API_URL` was set correctly during build
2. Rebuild and redeploy frontend:
   ```bash
   cd Overlay-main/infra
   ./DEPLOY_FRONTEND.sh
   ```

### Foreign Key Constraint Violations

**Problem**: `ForeignKeyViolation` errors when creating drawings/comparisons

**Solution**: 
- API now validates foreign keys before insert
- Redeploy API: `./REDEPLOY_API.sh`
- See `DATABASE_SCHEMA_VALIDATION.md` for details

### Worker Not Processing Jobs

**Problem**: Jobs stuck in "Queued" status

**Solution**:
1. Check worker logs (see above)
2. Verify Pub/Sub subscription exists
3. Check worker service is running
4. Verify database connectivity

## 📚 Additional Documentation

- **Authentication**: [AUTHENTICATION.md](./AUTHENTICATION.md)
- **Database Schema**: [docs/DATABASE_SCHEMA_VALIDATION.md](./docs/DATABASE_SCHEMA_VALIDATION.md)
- **Frontend Architecture**: [Build-TraceFlow/ARCHITECTURE.md](./Build-TraceFlow/ARCHITECTURE.md)
- **Infrastructure**: [Overlay-main/infra/README.md](./Overlay-main/infra/README.md)
- **Diagnostic Scripts**: [scripts/README.md](./scripts/README.md)

## 🔗 Quick Links

- **Cloud Console**: https://console.cloud.google.com/run
- **API Docs**: https://buildtrace-api-okidmickfa-uc.a.run.app/docs
- **Logs**: https://console.cloud.google.com/logs
