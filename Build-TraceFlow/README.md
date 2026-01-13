# BuildTrace Frontend

React + Vite frontend application for BuildTrace.

## Quick Start

### Development

```bash
npm install
npm run dev
```

Starts the Express server with Vite dev server on port 5000.

### Production Build

```bash
npm run build
npm start
```

Builds static files to `dist/public/` and serves them.

## Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed information about:
- Development vs Production deployment paths
- Replit integration (development only)
- Cloud Run production deployment
- Frontend stack and structure

## Key Points

- **Framework**: React 19 + Vite (not Next.js)
- **Development**: Vite dev server with optional Replit plugins
- **Production**: Static build served via nginx on Cloud Run
- **Replit**: Development/testing only, not used in production

## Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm start` - Start production server
- `npm run check` - Type check

## Deployment

See `../Overlay-main/infra/DEPLOY_FRONTEND.sh` for Cloud Run deployment.
