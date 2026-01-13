# Manual GCP Setup (If Terraform Fails)

If you can't get proper IAM permissions for Terraform, you can set up the infrastructure manually via the GCP Console.

## Step 1: Enable APIs

Go to: https://console.cloud.google.com/apis/library?project=buildtrace-dev

Enable these APIs:
- Cloud Run API
- Cloud SQL Admin API
- Cloud Storage API
- Pub/Sub API
- Artifact Registry API
- Secret Manager API
- Service Networking API
- Cloud Resource Manager API
- Compute Engine API

## Step 2: Create Service Accounts

Go to: https://console.cloud.google.com/iam-admin/serviceaccounts?project=buildtrace-dev

### Create `buildtrace-api` service account:
1. Click "Create Service Account"
2. Name: `buildtrace-api`
3. Description: "BuildTrace API Service Account"
4. Click "Create and Continue"
5. Grant roles:
   - Storage Object Admin
   - Cloud SQL Client
   - Pub/Sub Publisher
   - Secret Manager Secret Accessor
6. Click "Done"

### Create `buildtrace-worker` service account:
1. Click "Create Service Account"
2. Name: `buildtrace-worker`
3. Description: "BuildTrace Worker Service Account"
4. Click "Create and Continue"
5. Grant roles:
   - Storage Object Admin
   - Cloud SQL Client
   - Pub/Sub Subscriber
   - Secret Manager Secret Accessor
6. Click "Done"

## Step 3: Create VPC Network

Go to: https://console.cloud.google.com/networking/networks/list?project=buildtrace-dev

1. Click "Create VPC Network"
2. Name: `buildtrace-vpc`
3. Subnet creation mode: "Custom"
4. Click "Add Subnet":
   - Name: `buildtrace-subnet`
   - Region: `us-central1`
   - IP address range: `10.0.0.0/24`
5. Click "Create"

## Step 4: Create Cloud SQL Instance

Go to: https://console.cloud.google.com/sql/instances?project=buildtrace-dev

1. Click "Create Instance"
2. Choose PostgreSQL
3. Instance ID: `buildtrace-db`
4. Password: Generate a strong password (save it!)
5. Region: `us-central1`
6. Database version: PostgreSQL 15
7. Machine type: `db-g1-small`
8. Storage: 20 GB, SSD
9. Under "Connections":
   - Private IP: Enable
   - Network: `buildtrace-vpc`
10. Under "Backups":
    - Enable automated backups
    - Backup window: 2:00 AM
    - Point-in-time recovery: Enable
11. Click "Create" (takes 10-15 minutes)

After creation:
1. Click on the instance
2. Go to "Databases" tab
3. Click "Create Database"
4. Database name: `buildtrace`
5. Click "Create"

6. Go to "Users" tab
7. Click "Add User Account"
8. Username: `buildtrace`
9. Password: Use the password you saved
10. Click "Add"

## Step 5: Create Cloud Storage Buckets

Go to: https://console.cloud.google.com/storage/browser?project=buildtrace-dev

### Create `buildtrace-dev-uploads` bucket:
1. Click "Create Bucket"
2. Name: `buildtrace-dev-uploads`
3. Location: `us-central1`
4. Storage class: Standard
5. Access control: Uniform
6. Enable versioning
7. Lifecycle rule: After 90 days → Nearline
8. CORS: Add origins `http://localhost:3000` and `http://localhost:5000`
9. Click "Create"

### Create `buildtrace-dev-overlays` bucket:
1. Click "Create Bucket"
2. Name: `buildtrace-dev-overlays`
3. Location: `us-central1`
4. Storage class: Standard
5. Access control: Uniform
6. Lifecycle rule: After 180 days → Coldline
7. Click "Create"

## Step 6: Create Pub/Sub Topics and Subscriptions

Go to: https://console.cloud.google.com/cloudpubsub/topic/list?project=buildtrace-dev

### Create `vision` topic:
1. Click "Create Topic"
2. Topic ID: `vision`
3. Message retention: 1 day
4. Click "Create"

### Create `vision-dlq` topic:
1. Click "Create Topic"
2. Topic ID: `vision-dlq`
3. Click "Create"

### Create subscription:
1. Go to Subscriptions: https://console.cloud.google.com/cloudpubsub/subscription/list?project=buildtrace-dev
2. Click "Create Subscription"
3. Subscription ID: `vision-worker-subscription`
4. Topic: `vision`
5. Delivery type: Pull
6. Acknowledgement deadline: 600 seconds
7. Dead letter topic: `vision-dlq`
8. Max delivery attempts: 5
9. Click "Create"

## Step 7: Create Artifact Registry

Go to: https://console.cloud.google.com/artifacts?project=buildtrace-dev

1. Click "Create Repository"
2. Format: Docker
3. Name: `buildtrace`
4. Mode: Standard
5. Location: `us-central1`
6. Click "Create"

## Step 8: Create Secret Manager Secrets

Go to: https://console.cloud.google.com/security/secret-manager?project=buildtrace-dev

### Create `buildtrace-db-password`:
1. Click "Create Secret"
2. Name: `buildtrace-db-password`
3. Secret value: The database password you created
4. Click "Create Secret"

### Create other secrets (for later):
- `openai-api-key`
- `gemini-api-key`
- `jwt-secret`
- `google-client-id`
- `google-client-secret`

## Step 9: Create Cloud Run Services

After all above resources are created, you can create Cloud Run services. However, you'll need Docker images first.

### Build and Push Images:
```bash
# Configure Docker
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build and push API
cd Overlay-main
docker build -t us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/api:latest -f api/Dockerfile .
docker push us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/api:latest

# Build and push Worker
docker build -t us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/overlay-worker:latest -f vision/worker/Dockerfile .
docker push us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/overlay-worker:latest
```

### Deploy API Service:
Go to: https://console.cloud.google.com/run?project=buildtrace-dev

1. Click "Create Service"
2. Service name: `buildtrace-api`
3. Region: `us-central1`
4. Container image: `us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/api:latest`
5. Service account: `buildtrace-api@buildtrace-dev.iam.gserviceaccount.com`
6. Under "Container":
   - CPU: 2
   - Memory: 2 GiB
   - Environment variables:
     - `DB_USER=buildtrace`
     - `DB_NAME=buildtrace`
     - `CLOUD_SQL_CONNECTION_NAME=<from Cloud SQL instance>`
     - `DB_PASSWORD` → Secret: `buildtrace-db-password`
     - `STORAGE_BACKEND=gcs`
     - `STORAGE_BUCKET=buildtrace-dev-uploads`
     - `PUBSUB_PROJECT_ID=buildtrace-dev`
     - `VISION_TOPIC=vision`
     - `CORS_ORIGINS=["http://localhost:3000","http://localhost:5000"]`
7. Under "Connections":
   - Cloud SQL connections: Select `buildtrace-db`
8. Under "Security":
   - Allow unauthenticated invocations: Yes
9. Click "Create"

### Deploy Worker Service:
1. Click "Create Service"
2. Service name: `buildtrace-overlay-worker`
3. Region: `us-central1`
4. Container image: `us-central1-docker.pkg.dev/buildtrace-dev/buildtrace/overlay-worker:latest`
5. Service account: `buildtrace-worker@buildtrace-dev.iam.gserviceaccount.com`
6. Under "Container":
   - CPU: 8
   - Memory: 16 GiB
   - Timeout: 900 seconds
   - Environment variables:
     - `DB_HOST=/cloudsql/<connection-name>`
     - `DB_PORT=5432`
     - `DB_NAME=buildtrace`
     - `DB_USER=buildtrace`
     - `DB_PASSWORD` → Secret: `buildtrace-db-password`
     - `STORAGE_BACKEND=gcs`
     - `STORAGE_BUCKET=buildtrace-dev-overlays`
     - `PUBSUB_PROJECT_ID=buildtrace-dev`
     - `VISION_TOPIC=vision`
     - `VISION_SUBSCRIPTION=vision-worker-subscription`
     - `OPENAI_API_KEY` → Secret: `openai-api-key`
     - `GEMINI_API_KEY` → Secret: `gemini-api-key`
7. Under "Connections":
   - Cloud SQL connections: Select `buildtrace-db`
8. Under "Security":
   - Allow unauthenticated invocations: No (internal only)
9. Click "Create"

## After Manual Setup

Once everything is created manually:

1. **Get the API URL** from Cloud Run
2. **Run database migrations** (see `run-migrations.sh`)
3. **Create remaining secrets** (see `setup-secrets.sh`)
4. **Deploy frontend** (see `deploy-frontend.sh`)

## Note

Manual setup is more time-consuming and error-prone than Terraform. **It's strongly recommended to get proper IAM permissions and use Terraform instead.**
