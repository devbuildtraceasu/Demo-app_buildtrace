# BuildTrace Debugging Guide

Comprehensive guide for debugging and analyzing BuildTrace in development and production.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Local Development Debugging](#local-development-debugging)
3. [Production Debugging](#production-debugging)
4. [Common Issues and Solutions](#common-issues-and-solutions)
5. [Database Debugging](#database-debugging)
6. [Job Processing Debugging](#job-processing-debugging)
7. [Authentication Debugging](#authentication-debugging)

---

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   API Service   │────▶│   PostgreSQL    │
│  (React/Vite)   │     │   (FastAPI)     │     │   (Cloud SQL)   │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 │ Pub/Sub
                                 ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │  Vision Worker  │────▶│  Cloud Storage  │
                        │   (Python)      │     │  (GCS/MinIO)    │
                        └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼
                        ┌─────────────────┐
                        │   Gemini AI     │
                        │ (Block Extract) │
                        └─────────────────┘
```

### Service URLs

| Service | Production | Local |
|---------|-----------|-------|
| Frontend | https://buildtrace-frontend-okidmickfa-uc.a.run.app | http://localhost:5000 |
| API | https://buildtrace-api-okidmickfa-uc.a.run.app | http://localhost:8000 |
| API Docs | https://buildtrace-api-okidmickfa-uc.a.run.app/docs | http://localhost:8000/docs |
| MinIO Console | - | http://localhost:9001 |

---

## Local Development Debugging

### Starting Local Services

```bash
# Option 1: All services in Docker
./start-local.sh docker

# Option 2: Infrastructure only (for hot-reload development)
./start-local.sh services

# Option 3: Development mode with instructions
./start-local.sh dev
```

### Checking Service Status

```bash
# Check Docker containers
cd Overlay-main
docker-compose ps

# Check API health
curl http://localhost:8000/health

# Check database connection
docker-compose exec db pg_isready -U overlay -d overlay_dev

# Check MinIO health
curl http://localhost:9000/minio/health/ready
```

### Viewing Local Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f worker
docker-compose logs -f db

# API with uvicorn (dev mode)
cd Overlay-main
PYTHONPATH=$(pwd) uv run uvicorn api.main:app --reload --log-level debug

# Worker (dev mode)
cd Overlay-main/vision/worker
uv run python -m main
```

### Local Database Access

```bash
# Connect to PostgreSQL
docker-compose exec db psql -U overlay -d overlay_dev

# Or directly
psql postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev
```

### Local Storage Access

MinIO Console: http://localhost:9001
- Username: `minio`
- Password: `minio123`

---

## Production Debugging

### Viewing Production Logs

```bash
# Set project
export GCP_PROJECT_ID=buildtrace-prod

# API logs (last 50 entries)
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
  --limit=50 --project=$GCP_PROJECT_ID \
  --format="table(timestamp,severity,textPayload)"

# Worker logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=50 --project=$GCP_PROJECT_ID \
  --format="table(timestamp,severity,textPayload)"

# Frontend logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-frontend" \
  --limit=50 --project=$GCP_PROJECT_ID \
  --format="table(timestamp,severity,textPayload)"

# Errors only (all services)
gcloud logging read \
  "resource.type=cloud_run_revision AND severity>=ERROR" \
  --limit=30 --project=$GCP_PROJECT_ID \
  --format="table(timestamp,resource.labels.service_name,severity,textPayload)"
```

### Using Diagnostic Scripts

```bash
# All logs check
./scripts/CHECK_ALL_LOGS.sh

# Worker-specific logs
./scripts/CHECK_WORKER_LOGS.sh

# Job processing diagnosis
./scripts/DIAGNOSE_JOBS.sh

# Comparison status
./scripts/CHECK_COMPARISON_STATUS.sh <comparison_id>
```

### Check Service Status

```bash
# List all Cloud Run services
gcloud run services list --region=us-central1

# Describe specific service
gcloud run services describe buildtrace-api --region=us-central1

# Check environment variables
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)'
```

---

## Common Issues and Solutions

### 1. Frontend Cannot Connect to API

**Symptoms**: Network errors, CORS errors, API calls failing

**Diagnosis**:
```bash
# Check VITE_API_URL was set during build
# In browser console:
console.log(import.meta.env.VITE_API_URL)

# Check CORS_ORIGINS on API
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)' | grep CORS
```

**Solution**:
```bash
# Rebuild frontend with correct API URL
cd Overlay-main/infra
./DEPLOY_FRONTEND.sh

# Or update CORS via Cloud Console
# Cloud Run > buildtrace-api > Edit > Variables > CORS_ORIGINS
```

### 2. OAuth Redirect Issues

**Symptoms**: "redirect_uri_mismatch", redirects to localhost

**Diagnosis**:
```bash
# Check configured redirect URI
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)' | grep GOOGLE_REDIRECT_URI

# Verify in Google Console
# APIs & Services > Credentials > OAuth Client > Authorized redirect URIs
```

**Solution**: See [AUTHENTICATION.md](./AUTHENTICATION.md) for detailed OAuth troubleshooting.

### 3. Foreign Key Constraint Violations

**Symptoms**: `ForeignKeyViolation` errors when creating drawings/comparisons

**Diagnosis**:
```bash
# Check if parent entity exists
# In psql:
SELECT * FROM projects WHERE id = '<project_id>';
SELECT * FROM blocks WHERE id = '<block_id>';
```

**Solution**: See [docs/DATABASE_SCHEMA_VALIDATION.md](./docs/DATABASE_SCHEMA_VALIDATION.md) for validation details.

### 4. Jobs Stuck in "Queued" Status

**Symptoms**: Uploaded drawings never process, jobs stay "Queued"

**Diagnosis**:
```bash
# Check if jobs are being published
./scripts/DIAGNOSE_JOBS.sh

# Check Pub/Sub subscription
gcloud pubsub subscriptions list --project=buildtrace-prod

# Check worker is receiving messages
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND textPayload=~\"received\"" \
  --limit=20 --project=buildtrace-prod
```

**Solution**:
1. Verify Pub/Sub topic and subscription exist
2. Check worker has correct subscription name
3. Verify worker service is running
4. Check worker has database connectivity

### 5. File Upload Failures

**Symptoms**: Upload errors, files not appearing in storage

**Diagnosis**:
```bash
# Check API logs for upload errors
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND textPayload=~\"upload\"" \
  --limit=30 --project=buildtrace-prod

# Check storage bucket permissions
gsutil ls gs://buildtrace-uploads/
```

**Solution**:
1. Verify file type is allowed (PDF, PNG, JPG, DWG, DXF)
2. Check file size < 100MB
3. Verify storage bucket permissions

---

## Database Debugging

### Connecting to Production Database

```bash
# Via Cloud SQL Proxy
cloud_sql_proxy -instances=buildtrace-prod:us-central1:buildtrace-db=tcp:5433

# Then connect
psql -h localhost -p 5433 -U overlay -d overlay_prod
```

### Useful Queries

```sql
-- Check recent jobs
SELECT id, type, status, created_at, updated_at
FROM jobs
ORDER BY created_at DESC
LIMIT 20;

-- Check job with events
SELECT j.id, j.status, e.message, e.created_at
FROM jobs j
LEFT JOIN job_events e ON j.id = e.job_id
WHERE j.id = '<job_id>'
ORDER BY e.created_at;

-- Check drawings for a project
SELECT id, name, status, uri, created_at
FROM drawings
WHERE project_id = '<project_id>'
ORDER BY created_at DESC;

-- Check sheets for a drawing
SELECT id, name, page_number, uri, created_at
FROM sheets
WHERE drawing_id = '<drawing_id>'
ORDER BY page_number;

-- Check blocks for a sheet
SELECT id, name, uri, bounds, created_at
FROM blocks
WHERE sheet_id = '<sheet_id>';

-- Check comparison/overlay status
SELECT o.id, o.status, o.block_a_id, o.block_b_id,
       j.status as job_status, j.type as job_type
FROM overlays o
LEFT JOIN jobs j ON o.job_id = j.id
WHERE o.id = '<overlay_id>';
```

### Schema Reference

See [docs/DATABASE_SCHEMA_VALIDATION.md](./docs/DATABASE_SCHEMA_VALIDATION.md) for complete schema documentation.

---

## Job Processing Debugging

### Job Flow

```
Drawing Upload → Drawing Preprocess Job → Sheet Records Created
                         ↓
              For each sheet: Sheet Preprocess Job → Block Records Created
                         ↓
              Comparison Request → Block Overlay Generate Job → Overlay Created
```

### Job Types

| Type | Purpose | Input | Output |
|------|---------|-------|--------|
| `vision.drawing.preprocess` | Extract sheets from PDF | Drawing ID | Sheet records |
| `vision.sheet.preprocess` | Extract blocks using Gemini | Sheet ID | Block records |
| `vision.block.overlay.generate` | Generate overlay comparison | Block A/B IDs | Overlay image |

### Checking Job Progress

```sql
-- All jobs for a drawing
SELECT j.id, j.type, j.status, j.progress, j.created_at
FROM jobs j
JOIN drawings d ON j.payload->>'drawing_id' = d.id
WHERE d.id = '<drawing_id>'
ORDER BY j.created_at;

-- Job events (progress messages)
SELECT message, created_at
FROM job_events
WHERE job_id = '<job_id>'
ORDER BY created_at;
```

### Worker Processing Logs

```bash
# Check drawing preprocessing
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND textPayload=~\"Drawing\"" \
  --limit=30 --project=buildtrace-prod

# Check Gemini block extraction
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND textPayload=~\"Gemini\"" \
  --limit=30 --project=buildtrace-prod

# Check overlay generation
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker AND textPayload=~\"overlay\"" \
  --limit=30 --project=buildtrace-prod
```

---

## Authentication Debugging

### Check OAuth Configuration

```bash
# Verify Google Client ID is set
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)' | grep GOOGLE_CLIENT_ID

# Check redirect URI
gcloud run services describe buildtrace-api \
  --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)' | grep GOOGLE_REDIRECT_URI
```

### Test OAuth Flow

```bash
# Test OAuth URL endpoint
curl https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/google/url

# Expected: {"url": "https://accounts.google.com/o/oauth2/auth?..."}
```

### JWT Token Debugging

```bash
# Decode JWT token (replace <token>)
echo "<token>" | cut -d'.' -f2 | base64 -d 2>/dev/null | jq

# Test /me endpoint
curl -H "Authorization: Bearer <token>" \
  https://buildtrace-api-okidmickfa-uc.a.run.app/api/auth/me
```

---

## Additional Resources

- [AUTHENTICATION.md](./AUTHENTICATION.md) - OAuth setup and troubleshooting
- [DEPLOYMENT.md](./DEPLOYMENT.md) - Production deployment guide
- [docs/DATABASE_SCHEMA_VALIDATION.md](./docs/DATABASE_SCHEMA_VALIDATION.md) - Database schema details
- [scripts/README.md](./scripts/README.md) - Diagnostic scripts reference
