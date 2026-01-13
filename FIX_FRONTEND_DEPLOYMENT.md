# Fix Frontend Deployment - Container Failed to Start

## Problem
Cloud Run reports: "The user-provided container failed to start and listen on the port defined provided by the PORT=8080 environment variable"

## Root Cause Analysis

The Dockerfile uses nginx to serve static files on port 8080. The issue could be:

1. **nginx.conf syntax error** - nginx fails to start
2. **Missing build output** - `dist/public` is empty or missing
3. **nginx not listening on correct port** - Configuration mismatch

## Solution

### Step 1: Verify nginx.conf Syntax

The nginx.conf should be valid. Check it:

```bash
cd Build-TraceFlow
# If nginx is installed locally:
nginx -t -c nginx.conf

# Or check manually - the file should have:
# listen 0.0.0.0:8080;
```

### Step 2: Test Docker Build Locally

Build and test the Docker image locally:

```bash
cd Build-TraceFlow

# Build the image
docker build --platform linux/amd64 \
  --build-arg VITE_API_URL=https://buildtrace-api-okidmickfa-uc.a.run.app/api \
  -t buildtrace-frontend-test \
  .

# Test run the container
docker run -p 8080:8080 buildtrace-frontend-test

# In another terminal, test it:
curl http://localhost:8080/health
curl http://localhost:8080/
```

### Step 3: Check Build Output

Verify the build creates `dist/public` with files:

```bash
cd Build-TraceFlow
npm run build
ls -la dist/public/
# Should see: index.html, assets/, favicon.png, etc.
```

### Step 4: Check Cloud Run Logs

Get detailed error logs:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-frontend AND resource.labels.revision_name=buildtrace-frontend-00013-9w5" \
  --limit=50 \
  --project=buildtrace-prod \
  --format=json
```

Look for:
- nginx startup errors
- File not found errors
- Port binding errors

### Step 5: Fix Common Issues

#### Issue: nginx.conf not found
**Fix**: Ensure `nginx.conf` is in the `Build-TraceFlow/` root directory (same level as Dockerfile)

#### Issue: dist/public is empty
**Fix**: The build must run successfully. Check:
```bash
cd Build-TraceFlow
npm run build
# Verify dist/public/index.html exists
```

#### Issue: nginx syntax error
**Fix**: The nginx.conf should be:
```nginx
server {
    listen 0.0.0.0:8080;  # Must listen on 8080
    # ... rest of config
}
```

#### Issue: Missing index.html
**Fix**: The build script should create `dist/public/index.html`. Check `script/build.ts` runs `viteBuild()` successfully.

### Step 6: Redeploy

Once fixed, redeploy:

```bash
cd Overlay-main/infra
./DEPLOY_FRONTEND.sh
```

## Alternative: Use Express Server Instead of nginx

If nginx continues to fail, you can modify the Dockerfile to use the Express server:

```dockerfile
# Stage 1: Build (same as before)
FROM node:20-alpine AS builder
# ... build steps ...

# Stage 2: Production with Express
FROM node:20-alpine

WORKDIR /app

# Copy built files
COPY --from=builder /app/dist/public ./public
COPY --from=builder /app/dist/index.cjs ./
COPY --from=builder /app/package*.json ./

# Install only production dependencies
RUN npm ci --production

# Set environment
ENV NODE_ENV=production
ENV PORT=8080

# Expose port
EXPOSE 8080

# Start Express server
CMD ["node", "index.cjs"]
```

But this requires the Express server to serve static files correctly (which it should via `serveStatic`).

## Quick Fix Script

```bash
#!/bin/bash
# Quick fix: Rebuild and redeploy frontend

cd Build-TraceFlow

# Clean and rebuild
rm -rf dist
npm run build

# Verify build output
if [ ! -f "dist/public/index.html" ]; then
    echo "ERROR: Build failed - index.html not found"
    exit 1
fi

# Build Docker image
docker build --platform linux/amd64 \
  --build-arg VITE_API_URL=https://buildtrace-api-okidmickfa-uc.a.run.app/api \
  -t us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/frontend:latest \
  .

# Test locally first
echo "Testing container locally..."
docker run -d -p 8080:8080 --name frontend-test us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/frontend:latest
sleep 5
curl http://localhost:8080/health || echo "Container failed to start"
docker stop frontend-test
docker rm frontend-test

# If test passes, push and deploy
echo "Pushing to registry..."
docker push us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/frontend:latest

echo "Deploying to Cloud Run..."
gcloud run deploy buildtrace-frontend \
  --image us-central1-docker.pkg.dev/buildtrace-prod/buildtrace/frontend:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 3 \
  --set-env-vars="NODE_ENV=production"
```
