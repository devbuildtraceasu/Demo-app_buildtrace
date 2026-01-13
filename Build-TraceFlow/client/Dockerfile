# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files from parent directory
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy all source code
COPY . .

# Build the app (builds client)
RUN npm run build

# Production stage - serve with nginx
FROM nginx:alpine

# Copy built assets (dist folder contains client build)
COPY --from=builder /app/dist/public /usr/share/nginx/html

# Copy nginx config from client folder
COPY client/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
