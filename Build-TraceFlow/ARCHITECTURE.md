# BuildTrace Frontend Architecture

## Overview

The BuildTrace frontend is a **React + Vite** application (not Next.js) that supports multiple deployment paths:

- **Development**: Vite dev server with Replit integration (optional)
- **Production**: Static build served via nginx on Cloud Run

## Frontend Stack

- **Framework**: React 19.2.0
- **Build Tool**: Vite 7.1.9
- **Routing**: Wouter (lightweight React router)
- **UI Components**: Radix UI + Tailwind CSS
- **State Management**: TanStack Query (React Query)
- **Forms**: React Hook Form + Zod validation

## Deployment Paths

### 1. Development Mode (Local/Replit)

**When**: `NODE_ENV !== "production"`

**How it works**:
- Express server runs Vite dev server in middleware mode
- Hot Module Replacement (HMR) enabled
- Replit plugins loaded only when `REPL_ID` environment variable is set

**Replit Integration** (Development Only):
- `@replit/vite-plugin-cartographer` - Development tooling
- `@replit/vite-plugin-dev-banner` - Development banner
- `@replit/vite-plugin-runtime-error-modal` - Error overlay
- These plugins are **NOT** included in production builds

**Code Reference**:
```typescript
// vite.config.ts
...(process.env.NODE_ENV !== "production" &&
process.env.REPL_ID !== undefined
  ? [
      await import("@replit/vite-plugin-cartographer").then((m) =>
        m.cartographer(),
      ),
      await import("@replit/vite-plugin-dev-banner").then((m) =>
        m.devBanner(),
      ),
    ]
  : []),
```

```typescript
// server/index.ts
if (process.env.NODE_ENV === "production") {
  serveStatic(app);
} else {
  const { setupVite } = await import("./vite");
  await setupVite(httpServer, app);
}
```

### 2. Production Mode (Cloud Run)

**When**: `NODE_ENV === "production"`

**How it works**:
1. Build step: `npm run build` creates static files in `dist/public`
2. Docker build: Multi-stage build creates nginx image
3. Deployment: Cloud Run serves static files via nginx

**Build Process**:
```bash
npm run build  # Runs tsx script/build.ts
# Output: dist/public/ (static assets)
```

**Dockerfile**:
- Stage 1: Build React app with Vite
- Stage 2: Copy static files to nginx image
- Serves on port 8080 (Cloud Run default)

**Deployment**:
```bash
# From Overlay-main/infra/
./DEPLOY_FRONTEND.sh
```

## Replit Configuration (Legacy/Development)

The `.replit` file configures Replit-specific deployment:

```toml
[deployment]
deploymentTarget = "autoscale"
build = ["npm", "run", "build"]
publicDir = "dist/public"
run = ["node", "./dist/index.cjs"]
```

**Note**: This is for Replit platform deployment (development/testing). Production uses Cloud Run.

## Environment Variables

### Development
- `NODE_ENV=development` - Enables Vite dev server
- `REPL_ID` - Optional, enables Replit plugins
- `PORT=5000` - Server port (default)

### Production
- `NODE_ENV=production` - Serves static files
- `VITE_API_URL` - API endpoint URL (build-time)
- `PORT=8080` - Cloud Run port

## API Integration

The frontend communicates with the backend API:

- **Development**: Proxy to `http://localhost:8000/api` (via Vite proxy)
- **Production**: Configured via `VITE_API_URL` build arg

```typescript
// vite.config.ts
proxy: {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
}
```

## Authentication

Uses Replit Auth integration for development:
- `server/replit_integrations/auth/` - Replit OIDC authentication
- Production may use different auth (Google OAuth, etc.)

## File Structure

```
Build-TraceFlow/
├── client/              # React frontend source
│   ├── src/
│   │   ├── components/  # UI components
│   │   ├── pages/       # Page components
│   │   └── main.tsx     # Entry point
│   └── index.html       # HTML template
├── server/              # Express backend
│   ├── index.ts         # Main server (routes dev/prod)
│   ├── vite.ts          # Vite dev server setup
│   └── static.ts        # Static file serving (prod)
├── dist/                # Build output
│   └── public/          # Static assets (production)
├── vite.config.ts       # Vite configuration
├── Dockerfile           # Production Docker image
└── .replit              # Replit configuration (dev)
```

## Key Differences: Development vs Production

| Aspect | Development | Production |
|--------|------------|------------|
| Server | Express + Vite dev server | Express + Static files |
| Build | On-demand (Vite HMR) | Pre-built (`dist/public`) |
| Replit Plugins | Enabled (if `REPL_ID` set) | Disabled |
| Port | 5000 (default) | 8080 (Cloud Run) |
| API Proxy | Vite proxy to localhost:8000 | Direct to `VITE_API_URL` |

## Common Tasks

### Local Development
```bash
npm run dev  # Starts Express + Vite dev server
```

### Production Build
```bash
npm run build  # Creates dist/public/
npm start      # Serves static files (production mode)
```

### Deploy to Cloud Run
```bash
cd Overlay-main/infra
./DEPLOY_FRONTEND.sh
```

## Notes

- **Not Next.js**: This is a React SPA, not a Next.js application
- **Replit is Optional**: Replit integration is for development/testing only
- **Production is Static**: Production serves pre-built static files, not SSR
- **Vite Only in Dev**: Vite dev server only runs in development mode
