#!/bin/bash
# Run database migrations using Cloud Run Job
# This creates a one-time Cloud Run job to run migrations

set -e

PROJECT_ID="${GCP_PROJECT_ID:-buildtrace-prod}"
REGION="${GCP_REGION:-us-central1}"
INSTANCE_NAME="buildtrace-db"
DATABASE_NAME="buildtrace"
JOB_NAME="buildtrace-migrations"

echo "============================================"
echo "  Running Database Migrations via Cloud Run"
echo "============================================"
echo "Project: $PROJECT_ID"
echo "Instance: $INSTANCE_NAME"
echo ""

# Get connection name
CONNECTION_NAME=$(gcloud sql instances describe $INSTANCE_NAME --project=$PROJECT_ID --format="value(connectionName)")

# Get database password
DB_PASSWORD=$(gcloud secrets versions access latest --secret=buildtrace-db-password --project=$PROJECT_ID)

# Create a temporary migration script
cat > /tmp/migrate.sh << 'MIGRATE_SCRIPT'
#!/bin/bash
set -e
cd /app/web
export DATABASE_URL="postgresql://buildtrace:${DB_PASSWORD}@/buildtrace?host=/cloudsql/${CONNECTION_NAME}"
npx prisma migrate deploy
MIGRATE_SCRIPT

echo "To run migrations, you have two options:"
echo ""
echo "Option 1: Use Cloud SQL Auth Proxy (if you have network access)"
echo "  gcloud sql connect $INSTANCE_NAME --user=buildtrace --database=$DATABASE_NAME --project=$PROJECT_ID"
echo "  Then run: npx prisma migrate deploy"
echo ""
echo "Option 2: Temporarily enable public IP, run migrations, then disable"
echo "  See: https://cloud.google.com/sql/docs/postgres/connect-run#public-ip"
echo ""
echo "Option 3: Create a Cloud Run job (recommended for production)"
echo "  This requires building a migration container image"
