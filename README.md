# BuildTrace

Full-stack application for architectural drawing comparison and overlay analysis using AI.

## 🏗️ Architecture

### Frontend (`Build-TraceFlow/`)
- **Framework**: React + Vite
- **Deployment**: Static files served via nginx on Cloud Run
- **Development**: Vite dev server with hot-reload
- See [Build-TraceFlow/ARCHITECTURE.md](./Build-TraceFlow/ARCHITECTURE.md) for details

### Backend (`Overlay-main/`)
- **API**: FastAPI (Python) on Cloud Run
- **Worker**: Python service for drawing processing and AI analysis
- **Database**: Cloud SQL PostgreSQL
- **Storage**: Google Cloud Storage
- **Messaging**: Google Pub/Sub

## 🚀 Quick Start

### Development

```bash
# Frontend
cd Build-TraceFlow
npm install
npm run dev
# Frontend: http://localhost:5000

# Backend API
cd Overlay-main
# See Overlay-main/README.md for setup
```

### Production Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for complete deployment guide.

**Quick deploy**:
```bash
cd Overlay-main/infra
terraform apply  # Infrastructure
./BUILD_AND_PUSH.sh  # Build images
./DEPLOY_FRONTEND.sh  # Deploy frontend
```

## 📚 Documentation

- **[DEPLOYMENT.md](./DEPLOYMENT.md)** - Complete deployment guide
- **[AUTHENTICATION.md](./AUTHENTICATION.md)** - Google OAuth setup and troubleshooting
- **[docs/DATABASE_SCHEMA_VALIDATION.md](./docs/DATABASE_SCHEMA_VALIDATION.md)** - Database schema and validation
- **[Build-TraceFlow/ARCHITECTURE.md](./Build-TraceFlow/ARCHITECTURE.md)** - Frontend architecture details
- **[Overlay-main/README.md](./Overlay-main/README.md)** - Backend API documentation
- **[scripts/README.md](./scripts/README.md)** - Diagnostic and utility scripts

## 🔗 Live Services

- **Frontend**: https://buildtrace-frontend-okidmickfa-uc.a.run.app
- **API**: https://buildtrace-api-okidmickfa-uc.a.run.app
- **API Docs**: https://buildtrace-api-okidmickfa-uc.a.run.app/docs

## 🛠️ Key Features

- **Drawing Upload**: Upload PDF drawings to projects
- **Sheet Extraction**: Automatic sheet detection and extraction
- **Block Analysis**: AI-powered block extraction using Gemini
- **Comparison**: Compare drawings and detect changes
- **Overlay Generation**: Visual overlay of differences
- **Authentication**: Google OAuth 2.0

## 📁 Project Structure

```
.
├── Build-TraceFlow/          # Frontend (React + Vite)
│   ├── client/               # React application
│   ├── server/               # Express server (dev only)
│   └── dist/                 # Build output
│
├── Overlay-main/             # Backend
│   ├── api/                  # FastAPI application
│   ├── vision/worker/        # Worker service
│   └── infra/                # Infrastructure & deployment
│       ├── terraform/        # Infrastructure as code
│       └── *.sh              # Deployment scripts
│
└── docs/                     # Documentation (if organized)
```

## 🔧 Development

### Prerequisites

- Node.js 20+
- Python 3.12+
- Docker
- Google Cloud SDK
- Terraform (for infrastructure)

### Environment Setup

See individual README files:
- Frontend: `Build-TraceFlow/README.md`
- Backend: `Overlay-main/README.md`
- Infrastructure: `Overlay-main/infra/README.md`

## 🐛 Troubleshooting

Common issues and solutions:

- **Authentication**: See [AUTHENTICATION.md](./AUTHENTICATION.md)
- **Deployment**: See [DEPLOYMENT.md](./DEPLOYMENT.md)
- **Database**: See [DATABASE_SCHEMA_VALIDATION.md](./DATABASE_SCHEMA_VALIDATION.md)

## 📝 License

[Add your license here]
