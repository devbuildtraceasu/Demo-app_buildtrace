# Manual Resource Creation Guide

Your account (`devbt777@gmail.com`) doesn't have permissions to create resources via Terraform. You have two options:

## Option 1: Request IAM Roles (Recommended)

Ask the project owner to grant you these roles:

### Required IAM Roles:
- **Compute Network Admin** (`roles/compute.networkAdmin`) - Create VPC networks
- **Secret Manager Admin** (`roles/secretmanager.admin`) - Create secrets
- **Storage Admin** (`roles/storage.admin`) - Create buckets
- **Pub/Sub Admin** (`roles/pubsub.admin`) - Create topics/subscriptions
- **Artifact Registry Admin** (`roles/artifactregistry.admin`) - Create repositories
- **Service Account User** (`roles/iam.serviceAccountUser`) - Use service accounts
- **Project IAM Admin** (`roles/resourcemanager.projectIamAdmin`) - Grant IAM roles to service accounts

### Grant via Console:
1. Go to [IAM & Admin > IAM](https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev)
2. Click "Grant Access"
3. Enter: `devbt777@gmail.com`
4. Select all the roles above
5. Click "Save"

### Grant via CLI (if you have access):
```bash
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/compute.networkAdmin"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/secretmanager.admin"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/pubsub.admin"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/resourcemanager.projectIamAdmin"
```

## Option 2: Create Resources Manually

If you can't get permissions, create these resources manually:

### 1. VPC Network

**Console:** [VPC Networks](https://console.cloud.google.com/networking/vpc/networks?project=buildtrace-dev)

1. Click "Create VPC Network"
2. Name: `buildtrace-vpc`
3. Subnet mode: **Custom**
4. Click "Add Subnet":
   - Name: `buildtrace-subnet`
   - Region: `us-central1`
   - IP address range: `10.0.0.0/24`
5. Click "Create"

### 2. Secret Manager Secrets

**Console:** [Secret Manager](https://console.cloud.google.com/security/secret-manager?project=buildtrace-dev)

Create these secrets (values will be set later):

1. **`db-password`**
   - Click "Create Secret"
   - Name: `db-password`
   - Secret value: (leave empty for now, or generate a random password)
   - Click "Create Secret"

2. **`openai-api-key`**
   - Name: `openai-api-key`
   - Secret value: (your OpenAI API key)

3. **`gemini-api-key`**
   - Name: `gemini-api-key`
   - Secret value: (your Gemini API key)

4. **`jwt-secret`**
   - Name: `jwt-secret`
   - Secret value: (generate a random string)

5. **`google-client-id`**
   - Name: `google-client-id`
   - Secret value: `YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com` (replace with your actual client ID)

6. **`google-client-secret`**
   - Name: `google-client-secret`
   - Secret value: `YOUR_GOOGLE_CLIENT_SECRET` (replace with your actual client secret)

7. **`google-redirect-uri`**
   - Name: `google-redirect-uri`
   - Secret value: `http://localhost:5001/api/v1/auth/google/callback`

### 3. Cloud Storage Buckets

**Console:** [Cloud Storage](https://console.cloud.google.com/storage/browser?project=buildtrace-dev)

1. **`buildtrace-uploads-484112`**
   - Click "Create Bucket"
   - Name: `buildtrace-uploads-484112`
   - Location: `us-central1`
   - Storage class: `Standard`
   - Access control: `Uniform`
   - Click "Create"

2. **`buildtrace-overlays-484112`**
   - Name: `buildtrace-overlays-484112`
   - Same settings as above

### 4. Pub/Sub Topics

**Console:** [Pub/Sub Topics](https://console.cloud.google.com/cloudpubsub/topic/list?project=buildtrace-dev)

1. **`vision`**
   - Click "Create Topic"
   - Topic ID: `vision`
   - Click "Create"

2. **`vision-dlq`**
   - Topic ID: `vision-dlq`
   - Click "Create"

### 5. Pub/Sub Subscriptions

**Console:** [Pub/Sub Subscriptions](https://console.cloud.google.com/cloudpubsub/subscription/list?project=buildtrace-dev)

1. **`vision-worker-subscription`**
   - Click "Create Subscription"
   - Subscription ID: `vision-worker-subscription`
   - Topic: `vision`
   - Delivery type: `Pull`
   - Click "Create"

### 6. Artifact Registry Repository

**Console:** [Artifact Registry](https://console.cloud.google.com/artifacts?project=buildtrace-dev)

1. Click "Create Repository"
2. Name: `buildtrace-images`
3. Format: `Docker`
4. Mode: `Standard`
5. Region: `us-central1`
6. Click "Create"

### 7. Grant IAM Roles to Service Accounts

**Console:** [IAM & Admin > IAM](https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev)

For **`buildtrace-api@484112.iam.gserviceaccount.com`**:
- Click "Grant Access"
- Principal: `buildtrace-api@484112.iam.gserviceaccount.com`
- Roles:
  - `Storage Object Admin`
  - `Cloud SQL Client`
  - `Pub/Sub Publisher`
  - `Secret Manager Secret Accessor`

For **`buildtrace-worker@484112.iam.gserviceaccount.com`**:
- Click "Grant Access"
- Principal: `buildtrace-worker@484112.iam.gserviceaccount.com`
- Roles:
  - `Storage Object Admin`
  - `Cloud SQL Client`
  - `Pub/Sub Subscriber`
  - `Secret Manager Secret Accessor`

## After Manual Creation

Once resources are created manually, you can:

1. **Import them into Terraform state** (optional):
   ```bash
   terraform import google_compute_network.main projects/buildtrace-dev/global/networks/buildtrace-vpc
   terraform import google_storage_bucket.uploads buildtrace-uploads-484112
   terraform import google_storage_bucket.overlays buildtrace-overlays-484112
   terraform import google_pubsub_topic.vision projects/buildtrace-dev/topics/vision
   terraform import google_pubsub_topic.vision_dlq projects/buildtrace-dev/topics/vision-dlq
   terraform import google_pubsub_subscription.vision_worker projects/buildtrace-dev/subscriptions/vision-worker-subscription
   terraform import google_artifact_registry_repository.main projects/buildtrace-dev/locations/us-central1/repositories/buildtrace-images
   ```

2. **Or comment out these resources in `main.tf`** and let Terraform only manage Cloud SQL and Cloud Run.

## Next Steps

After resources are created (either via permissions or manually), run:

```bash
cd Overlay-main/infra/terraform
terraform apply
```

Terraform will then create:
- Cloud SQL instance
- Cloud Run services (API and Worker)
