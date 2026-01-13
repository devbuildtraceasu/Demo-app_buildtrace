# BuildTrace Application

Full-stack application for architectural drawing comparison and overlay analysis.

## Project Structure

- **`Build-TraceFlow/`** - Frontend (React + Vite)
  - See [Build-TraceFlow/README.md](./Build-TraceFlow/README.md) and [Build-TraceFlow/ARCHITECTURE.md](./Build-TraceFlow/ARCHITECTURE.md)
- **`Overlay-main/`** - Backend API and worker services
  - See [Overlay-main/README.md](./Overlay-main/README.md)

## Frontend Architecture

The frontend is a **React + Vite** application (not Next.js) with two deployment paths:

1. **Development**: Vite dev server with optional Replit integration
2. **Production**: Static build served via nginx on Cloud Run

**Important Notes**:
- Replit/Vite integration is **development-only** and not used in production
- Production deployment uses Cloud Run with pre-built static files
- See [Build-TraceFlow/ARCHITECTURE.md](./Build-TraceFlow/ARCHITECTURE.md) for details

## Quick Start

### Frontend Development
```bash
cd Build-TraceFlow
npm install
npm run dev
```

### Backend Development
```bash
cd Overlay-main
# See Overlay-main/README.md for setup instructions
```

## Deployment

See [DEPLOYMENT_STATUS.md](./DEPLOYMENT_STATUS.md) for current deployment status and [Overlay-main/infra/](./Overlay-main/infra/) for deployment scripts.
