# BuildTrace Frontend Dockerfile
# Multi-stage build for production-optimized React app

# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY . .

# Build the application
ARG VITE_API_URL=/api
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Stage 2: Production
FROM nginx:alpine

# Copy built assets (build outputs to dist/public)
COPY --from=builder /app/dist/public /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Verify files exist (fail fast if build failed)
RUN test -f /usr/share/nginx/html/index.html || (echo "ERROR: index.html not found in build output" && exit 1) && \
    test -f /etc/nginx/conf.d/default.conf || (echo "ERROR: nginx.conf not found" && exit 1) && \
    nginx -t || (echo "ERROR: nginx configuration test failed" && exit 1)

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost:8080/ || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

