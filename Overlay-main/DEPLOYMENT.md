# BuildTrace Deployment Guide

This guide covers running BuildTrace locally for development and deploying to Google Cloud Platform for production.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Development](#local-development)
3. [Cloud Deployment (GCP)](#cloud-deployment-gcp)
4. [Environment Variables](#environment-variables)
5. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Software

```bash
# Check versions
node --version      # >= 18.x
python --version    # >= 3.12
docker --version    # >= 24.x
uv --version        # >= 0.1.x (Python package manager)
```

### Install Dependencies

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Node.js (if not installed)
# macOS
brew install node

# Install Docker Desktop
# https://www.docker.com/products/docker-desktop
```

### API Keys (for AI features)

- **OpenAI API Key**: For change detection and cost analysis
- **Google Gemini API Key**: For grid callout detection
- **Google OAuth Credentials**: For Google login (optional)

---

## Local Development

### Option 1: Quick Start with Docker Compose (Recommended)

This starts all services with a single command.

```bash
cd Overlay-main

# Create .env file
cat > .env << 'EOF'
# Database
DB_PASSWORD=buildtrace_dev_password

# Storage (MinIO)
MINIO_ACCESS_KEY=buildtrace
MINIO_SECRET_KEY=buildtrace123

# API Keys (optional - for AI features)
OPENAI_API_KEY=your-openai-key
GEMINI_API_KEY=your-gemini-key

# Auth (optional - for Google OAuth)
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
JWT_SECRET=your-secret-key-change-in-production
EOF

# Start all services
docker compose up -d

# View logs
docker compose logs -f
```

**Services will be available at:**
- Frontend: http://localhost:3000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (login: buildtrace/buildtrace123)

### Option 2: Manual Development Setup

For active development with hot-reload.

#### Step 1: Start Infrastructure Services

```bash
cd Overlay-main

# Start only infrastructure (database, storage, pubsub)
docker compose up -d postgres minio minio-init pubsub
```

#### Step 2: Run the API Server

```bash
cd Overlay-main

# Create Python environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e api/

# Set environment variables
export DATABASE_URL="postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev"
export STORAGE_BACKEND="s3"
export STORAGE_BUCKET="overlay-uploads"
export STORAGE_ENDPOINT="http://localhost:9000"
export STORAGE_ACCESS_KEY="minio"
export STORAGE_SECRET_KEY="minio123"
export PUBSUB_EMULATOR_HOST="localhost:8085"
export PUBSUB_PROJECT_ID="local-dev"

# Run the API (with hot-reload)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

#### Step 3: Run the Vision Worker

```bash
cd Overlay-main/vision/worker

# Create Python environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e .

# Set environment variables
export DATABASE_URL="postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev"
export STORAGE_BACKEND="s3"
export STORAGE_BUCKET="overlay-uploads"
export STORAGE_ENDPOINT="http://localhost:9000"
export STORAGE_ACCESS_KEY="minio"
export STORAGE_SECRET_KEY="minio123"
export PUBSUB_EMULATOR_HOST="localhost:8085"
export PUBSUB_PROJECT_ID="local-dev"
export VISION_SUBSCRIPTION="vision-subscription"

# Optional: AI API keys
export OPENAI_API_KEY="your-openai-key"
export GEMINI_API_KEY="your-gemini-key"

# Run the worker
python main.py
```

#### Step 4: Run the Frontend

```bash
cd Build-TraceFlow

# Install dependencies
npm install

# Set API URL
export VITE_API_URL="http://localhost:8000/api"

# Run development server
npm run dev
```

**Frontend will be available at:** http://localhost:5000

### Option 3: Production-Like Local Environment

Use the production Docker Compose for a more realistic environment:

```bash
cd Overlay-main

# Build and run production configuration
docker compose -f docker-compose.prod.yml up --build
```

---

## Cloud Deployment (GCP)

### Step 1: GCP Project Setup

```bash
# Set your project ID
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"

# Authenticate with GCP
gcloud auth login
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
  run.googleapis.com \
  sqladmin.googleapis.com \
  storage.googleapis.com \
  pubsub.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

### Step 2: Deploy Infrastructure with Terraform

```bash
cd Overlay-main/infra/terraform

# Copy and configure variables
cp terraform.tfvars.example terraform.tfvars

# Edit terraform.tfvars with your values
# - project_id
# - region
# - cors_origins (your frontend domain)

# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Apply infrastructure
terraform apply
```

This creates:
- Cloud SQL PostgreSQL instance
- Cloud Storage buckets (uploads, overlays)
- Pub/Sub topics and subscriptions
- Artifact Registry for Docker images
- Cloud Run services (API, overlay-worker)
- IAM roles and service accounts

### Step 3: Build and Push Docker Images

```bash
cd Overlay-main

# Configure Docker for Artifact Registry
gcloud auth configure-docker ${REGION}-docker.pkg.dev

# Build and push API image
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/api:latest -f api/Dockerfile .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/api:latest

# Build and push worker image
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/overlay-worker:latest -f vision/worker/Dockerfile .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/overlay-worker:latest
```

### Step 4: Deploy to Cloud Run

```bash
# Deploy API
gcloud run deploy buildtrace-api \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/api:latest \
  --region ${REGION} \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "STORAGE_BACKEND=gcs,STORAGE_BUCKET=${PROJECT_ID}-uploads"

# Deploy Overlay Worker
gcloud run deploy buildtrace-overlay-worker \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/overlay-worker:latest \
  --region ${REGION} \
  --platform managed \
  --no-allow-unauthenticated \
  --memory 16Gi \
  --cpu 8 \
  --timeout 900
```

### Step 5: Set Secrets

```bash
# Store API keys in Secret Manager
echo -n "your-openai-key" | gcloud secrets create openai-api-key --data-file=-
echo -n "your-gemini-key" | gcloud secrets create gemini-api-key --data-file=-
echo -n "your-jwt-secret" | gcloud secrets create jwt-secret --data-file=-

# Grant access to Cloud Run service accounts
gcloud secrets add-iam-policy-binding openai-api-key \
  --member="serviceAccount:buildtrace-worker@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Step 6: Deploy Frontend

**Note**: The frontend is a React + Vite application (not Next.js). Replit integration is development-only and not used in production. See `../Build-TraceFlow/ARCHITECTURE.md` for details.

For the frontend, you have several options:

**Option A: Firebase Hosting**
```bash
cd Build-TraceFlow

# Install Firebase CLI
npm install -g firebase-tools

# Initialize Firebase
firebase init hosting

# Build for production
VITE_API_URL="https://buildtrace-api-xxxxx.run.app/api" npm run build

# Deploy
firebase deploy --only hosting
```

**Option B: Cloud Run (Static)**
```bash
cd Build-TraceFlow

# Build the frontend
npm run build

# Create nginx Dockerfile
cat > Dockerfile << 'EOF'
FROM nginx:alpine
COPY dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EOF

# Build and deploy
docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/frontend:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/frontend:latest

gcloud run deploy buildtrace-frontend \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/buildtrace/frontend:latest \
  --region ${REGION} \
  --allow-unauthenticated
```

### Step 7: Configure CI/CD (Optional)

Use Cloud Build for automatic deployments:

```bash
# Connect repository
gcloud builds triggers create github \
  --repo-name="your-repo" \
  --repo-owner="your-org" \
  --branch-pattern="^main$" \
  --build-config="infra/cloudbuild.yaml"
```

---

## Environment Variables

### API Server

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `STORAGE_BACKEND` | `s3` or `gcs` | `s3` |
| `STORAGE_BUCKET` | Storage bucket name | Required |
| `STORAGE_ENDPOINT` | S3 endpoint (for MinIO) | - |
| `STORAGE_ACCESS_KEY` | S3 access key | - |
| `STORAGE_SECRET_KEY` | S3 secret key | - |
| `PUBSUB_PROJECT_ID` | GCP project ID | Required |
| `PUBSUB_EMULATOR_HOST` | Pub/Sub emulator host | - |
| `VISION_TOPIC` | Pub/Sub topic name | `vision` |
| `JWT_SECRET` | Secret for JWT signing | Required |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | - |

### Vision Worker

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `STORAGE_BACKEND` | `s3` or `gcs` | `s3` |
| `STORAGE_BUCKET` | Storage bucket name | Required |
| `VISION_SUBSCRIPTION` | Pub/Sub subscription | Required |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `GEMINI_API_KEY` | Google Gemini API key | - |
| `SIFT_N_FEATURES` | SIFT feature count | `20000` |
| `SIFT_RATIO_THRESHOLD` | SIFT ratio threshold | `0.75` |

### Frontend

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | API base URL | `/api` |

---

## Troubleshooting

### Common Issues

#### Database Connection Failed
```bash
# Check if PostgreSQL is running
docker compose ps postgres

# Check connection
psql postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev
```

#### Storage Upload Failed
```bash
# Check if MinIO is running
docker compose ps minio

# Verify bucket exists
mc alias set local http://localhost:9000 minio minio123
mc ls local/
```

#### Pub/Sub Messages Not Processing
```bash
# Check emulator is running
curl http://localhost:8085

# Check subscription exists
gcloud pubsub subscriptions list --project=local-dev
```

#### AI Analysis Not Working
```bash
# Verify API keys are set
echo $OPENAI_API_KEY
echo $GEMINI_API_KEY

# Check worker logs
docker compose logs overlay-worker
```

### Health Checks

```bash
# API health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

### Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs -f api
docker compose logs -f overlay-worker

# Cloud Run logs
gcloud run services logs read buildtrace-api --region=${REGION}
```

---

## Quick Reference

### Local URLs
- Frontend: http://localhost:3000 (Docker) or http://localhost:5000 (npm)
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001

### Useful Commands

```bash
# Restart all services
docker compose restart

# Rebuild and restart
docker compose up --build -d

# Stop all services
docker compose down

# Remove all data (fresh start)
docker compose down -v

# Run database migrations
cd Overlay-main/web && npx prisma migrate deploy
```

