# BuildTrace

Full-stack AI-powered application for architectural drawing comparison and overlay analysis.

## Overview

BuildTrace enables construction professionals to upload architectural drawings, automatically extract sheets and blocks using AI (Google Gemini), and visually compare different versions to identify changes.

## Architecture

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

### Components

| Component | Location | Technology | Description |
|-----------|----------|------------|-------------|
| Frontend | `Build-TraceFlow/` | React, Vite, TypeScript, Tailwind | User interface for uploads, comparisons, and visualization |
| API | `Overlay-main/api/` | FastAPI, SQLModel, Python | REST API for authentication, projects, drawings, comparisons |
| Worker | `Overlay-main/vision/worker/` | Python, Gemini AI | Async processing: PDF extraction, block detection, overlay generation |
| Database | Cloud SQL | PostgreSQL, Prisma | Data storage and schema management |
| Storage | Cloud Storage | GCS (prod), MinIO (local) | File storage for drawings and processed images |

## Quick Start

### Local Development

```bash
# Clone and navigate to project
cd Demo-app_buildtrace

# Start all services with Docker
./start-local.sh docker

# Or start infrastructure only (for hot-reload development)
./start-local.sh dev
```

**Access Points (Local)**:
- Frontend: http://localhost:5000
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- MinIO Console: http://localhost:9001 (minio/minio123)

### Production Services

- Frontend: https://buildtrace-frontend-okidmickfa-uc.a.run.app
- API: https://buildtrace-api-okidmickfa-uc.a.run.app
- API Docs: https://buildtrace-api-okidmickfa-uc.a.run.app/docs

## Project Structure

```
.
├── Build-TraceFlow/              # Frontend application
│   ├── client/src/               # React source code
│   │   ├── components/           # UI components
│   │   ├── pages/                # Page components
│   │   ├── hooks/                # Custom React hooks
│   │   └── lib/                  # Utilities and API client
│   ├── Dockerfile                # Production container
│   └── nginx.conf                # Web server config
│
├── Overlay-main/                 # Backend services
│   ├── api/                      # FastAPI application
│   │   ├── routes/               # API endpoints
│   │   ├── models.py             # Database models
│   │   └── tests/                # API tests
│   ├── vision/worker/            # Processing worker
│   │   ├── jobs/                 # Job handlers
│   │   └── lib/                  # Processing utilities
│   ├── web/prisma/               # Database schema
│   ├── infra/                    # Deployment scripts
│   │   ├── terraform/            # Infrastructure as code
│   │   └── *.sh                  # Deployment scripts
│   └── docker-compose.yml        # Local development
│
├── docs/                         # Additional documentation
├── scripts/                      # Diagnostic scripts
├── start-local.sh                # Local startup script
└── [Documentation files]
```

## Documentation

| Document | Purpose |
|----------|---------|
| [AUTHENTICATION.md](./AUTHENTICATION.md) | Google OAuth setup and troubleshooting |
| [DEPLOYMENT.md](./DEPLOYMENT.md) | Production deployment to GCP |
| [DEBUGGING.md](./DEBUGGING.md) | Comprehensive debugging and analysis guide |
| [docs/DATABASE_SCHEMA_VALIDATION.md](./docs/DATABASE_SCHEMA_VALIDATION.md) | Database schema and foreign key validation |
| [scripts/README.md](./scripts/README.md) | Diagnostic scripts reference |
| [Build-TraceFlow/README.md](./Build-TraceFlow/README.md) | Frontend development guide |
| [Overlay-main/README.md](./Overlay-main/README.md) | Backend development guide |

## Key Features

- **Drawing Upload**: Upload PDF architectural drawings to projects
- **Automatic Sheet Extraction**: Detects and extracts individual sheets from multi-page PDFs
- **AI Block Detection**: Uses Google Gemini to identify and extract drawing blocks
- **Version Comparison**: Compare blocks between drawing versions
- **Visual Overlay**: Generate visual overlays highlighting differences
- **Real-time Updates**: Server-Sent Events for job progress tracking
- **Google OAuth**: Secure authentication with Google accounts

## Development

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker and Docker Compose
- Google Cloud SDK (for deployment)
- Terraform (for infrastructure)

### Running Tests

```bash
# Backend API tests
cd Overlay-main/api
uv run pytest tests/ -v

# Frontend tests
cd Build-TraceFlow
npm test
```

### Environment Variables

**Backend** (see `Overlay-main/.env.example`):
```bash
DATABASE_URL=postgresql://overlay:password@localhost:5432/overlay_dev
STORAGE_BACKEND=s3  # or 'gcs' for production
STORAGE_BUCKET=overlay-uploads
JWT_SECRET=your-secret-key
GEMINI_API_KEY=your-gemini-key
```

**Frontend** (see `Build-TraceFlow/.env.development`):
```bash
VITE_API_URL=http://localhost:8000
```

## Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for complete deployment instructions.

**Quick Deploy**:
```bash
cd Overlay-main/infra

# Deploy infrastructure
cd terraform && terraform apply

# Build and push images
./BUILD_AND_PUSH.sh

# Deploy frontend
./DEPLOY_FRONTEND.sh

# Redeploy API
./REDEPLOY_API.sh
```

## Troubleshooting

See [DEBUGGING.md](./DEBUGGING.md) for comprehensive debugging guide covering:
- Local and production log analysis
- Common issues and solutions
- Database debugging
- Job processing debugging
- Authentication troubleshooting

**Quick Diagnostics**:
```bash
# Check all production logs
./scripts/CHECK_ALL_LOGS.sh

# Diagnose job processing
./scripts/DIAGNOSE_JOBS.sh

# Check worker logs
./scripts/CHECK_WORKER_LOGS.sh
```

## Tech Stack

**Frontend**:
- React 19.2
- Vite 7.1
- TypeScript 5.6
- Tailwind CSS 4.1
- Radix UI Components
- React Query

**Backend**:
- FastAPI
- SQLModel / SQLAlchemy
- PostgreSQL
- Prisma (schema management)
- Google Cloud Pub/Sub
- Google Gemini AI

**Infrastructure**:
- Google Cloud Run
- Google Cloud SQL
- Google Cloud Storage
- Terraform
