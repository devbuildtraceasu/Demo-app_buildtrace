#!/bin/bash
# Run database migrations on Cloud SQL
# Usage: ./run-migrations.sh

set -e

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"
REGION="${GCP_REGION:-us-central1}"
INSTANCE_NAME="buildtrace-db"
DATABASE_NAME="buildtrace"

echo "============================================"
echo "  Running Database Migrations"
echo "============================================"
echo "Project: $PROJECT_ID"
echo "Instance: $INSTANCE_NAME"
echo "Database: $DATABASE_NAME"
echo ""

# Get connection name
CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --project=$PROJECT_ID --format="value(connectionName)")

if [ -z "$CONNECTION_NAME" ]; then
    echo "Error: Could not find Cloud SQL instance: $INSTANCE_NAME"
    exit 1
fi

echo "Connection name: $CONNECTION_NAME"
echo ""

# Get database password from Secret Manager
echo "Retrieving database password from Secret Manager..."
DB_PASSWORD=$(gcloud secrets versions access latest --secret=buildtrace-db-password --project=$PROJECT_ID)

if [ -z "$DB_PASSWORD" ]; then
    echo "Error: Could not retrieve database password from Secret Manager"
    exit 1
fi

echo "Password retrieved successfully"
echo ""

# Check if Cloud SQL Proxy is installed
if ! command -v cloud-sql-proxy &> /dev/null; then
    echo "Installing Cloud SQL Proxy..."
    ARCH=$(uname -m)
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    
    if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
        ARCH="arm64"
    else
        ARCH="amd64"
    fi
    
    curl -o cloud-sql-proxy "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.${OS}.${ARCH}"
    chmod +x cloud-sql-proxy
    export PATH="$PWD:$PATH"
    echo "Cloud SQL Proxy installed"
fi

# Start Cloud SQL Proxy in background
echo ""
echo "Starting Cloud SQL Proxy..."
cloud-sql-proxy "$CONNECTION_NAME" --port=5432 > /tmp/cloud-sql-proxy.log 2>&1 &
PROXY_PID=$!

# Wait for proxy to be ready
echo "Waiting for proxy to initialize..."
sleep 5

# Verify proxy is running
if ! ps -p $PROXY_PID > /dev/null; then
    echo "Error: Cloud SQL Proxy failed to start"
    cat /tmp/cloud-sql-proxy.log
    exit 1
fi

echo "Cloud SQL Proxy is running (PID: $PROXY_PID)"
echo ""

# Run migrations using Prisma
echo "Running Prisma migrations..."
cd "$(dirname "$0")/../web"

# Set DATABASE_URL for local connection through proxy
export DATABASE_URL="postgresql://buildtrace:${DB_PASSWORD}@localhost:5432/${DATABASE_NAME}"

echo "Database URL configured"
echo ""

# Run migrations
npx prisma migrate deploy

# Stop proxy
echo ""
echo "Stopping Cloud SQL Proxy..."
kill $PROXY_PID
wait $PROXY_PID 2>/dev/null || true

echo ""
echo "============================================"
echo "  Migrations Complete!"
echo "============================================"
