# Manual IAM Setup for Service Accounts

## Current Situation

✅ Service accounts exist:
- `buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com`
- `buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com`

❌ Terraform can't manage them (permission denied)

## Solution: Grant IAM Roles Manually

Since Terraform can't manage the service accounts, you need to grant IAM roles manually via console.

### Step 1: Grant Roles to API Service Account

Go to: https://console.cloud.google.com/iam-admin/serviceaccounts?project=buildtrace-dev

1. Click on `buildtrace-api` service account
2. Go to "Permissions" tab
3. Click "Grant Access"
4. Add these roles:
   - **Storage Object Admin** (`roles/storage.objectAdmin`)
   - **Cloud SQL Client** (`roles/cloudsql.client`)
   - **Pub/Sub Publisher** (`roles/pubsub.publisher`)
   - **Secret Manager Secret Accessor** (`roles/secretmanager.secretAccessor`)
5. Click "Save"

### Step 2: Grant Roles to Worker Service Account

1. Click on `buildtrace-worker` service account
2. Go to "Permissions" tab
3. Click "Grant Access"
4. Add these roles:
   - **Storage Object Admin** (`roles/storage.objectAdmin`)
   - **Cloud SQL Client** (`roles/cloudsql.client`)
   - **Pub/Sub Subscriber** (`roles/pubsub.subscriber`)
   - **Secret Manager Secret Accessor** (`roles/secretmanager.secretAccessor`)
5. Click "Save"

### Step 3: Grant Access to Database Password Secret

Go to: https://console.cloud.google.com/security/secret-manager?project=buildtrace-dev

1. Click on `buildtrace-db-password` secret (create it if it doesn't exist)
2. Click "Permissions" tab
3. Click "Add Principal"
4. Add `buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com`
   - Role: Secret Manager Secret Accessor
5. Click "Add Principal" again
6. Add `buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com`
   - Role: Secret Manager Secret Accessor
7. Click "Save"

## After Manual IAM Setup

Once IAM roles are granted:

1. **Run Terraform:**
   ```bash
   terraform apply
   ```

2. **Terraform will now:**
   - Use existing service accounts (via data sources)
   - Create remaining resources
   - Skip service account creation (already exist)

## What Terraform Will Create

- VPC network and subnet
- Cloud SQL instance
- Cloud Storage buckets
- Pub/Sub topics and subscriptions
- Artifact Registry
- Secret Manager secrets
- Cloud Run services (using existing service accounts)

## Quick Command Reference

If you prefer command line (requires proper permissions):

```bash
# Grant roles to API service account
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com" \
  --role="roles/pubsub.publisher"

# Grant roles to Worker service account
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com" \
  --role="roles/cloudsql.client"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"
```
