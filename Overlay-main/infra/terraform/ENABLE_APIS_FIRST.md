# Enable APIs Manually Before Running Terraform

## Current Situation

✅ **Service accounts created** - Good progress!
❌ **APIs not enabled** - Terraform can't enable them due to permissions

## Solution: Enable APIs Manually, Then Run Terraform

### Step 1: Enable All Required APIs

Go to: https://console.cloud.google.com/apis/library?project=buildtrace-dev

Enable these 9 APIs (click on each, then click "Enable"):

1. **Cloud Run API** - `run.googleapis.com`
2. **Cloud SQL Admin API** - `sqladmin.googleapis.com`
3. **Cloud Storage API** - `storage.googleapis.com`
4. **Cloud Pub/Sub API** - `pubsub.googleapis.com`
5. **Artifact Registry API** - `artifactregistry.googleapis.com`
6. **Secret Manager API** - `secretmanager.googleapis.com`
7. **Compute Engine API** - `compute.googleapis.com`
8. **Service Networking API** - `servicenetworking.googleapis.com`
9. **Cloud Resource Manager API** - `cloudresourcemanager.googleapis.com`

**Quick links to enable each:**
- [Cloud Run API](https://console.cloud.google.com/apis/library/run.googleapis.com?project=buildtrace-dev)
- [Cloud SQL Admin API](https://console.cloud.google.com/apis/library/sqladmin.googleapis.com?project=buildtrace-dev)
- [Cloud Storage API](https://console.cloud.google.com/apis/library/storage.googleapis.com?project=buildtrace-dev)
- [Cloud Pub/Sub API](https://console.cloud.google.com/apis/library/pubsub.googleapis.com?project=buildtrace-dev)
- [Artifact Registry API](https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com?project=buildtrace-dev)
- [Secret Manager API](https://console.cloud.google.com/apis/library/secretmanager.googleapis.com?project=buildtrace-dev)
- [Compute Engine API](https://console.cloud.google.com/apis/library/compute.googleapis.com?project=buildtrace-dev)
- [Service Networking API](https://console.cloud.google.com/apis/library/servicenetworking.googleapis.com?project=buildtrace-dev)
- [Cloud Resource Manager API](https://console.cloud.google.com/apis/library/cloudresourcemanager.googleapis.com?project=buildtrace-dev)

### Step 2: Wait for APIs to Enable

After enabling, wait 1-2 minutes for them to propagate.

### Step 3: Verify APIs Are Enabled

Check: https://console.cloud.google.com/apis/dashboard?project=buildtrace-dev

You should see all 9 APIs listed as "Enabled".

### Step 4: Run Terraform Again

Once APIs are enabled:

```bash
cd Overlay-main/infra/terraform
terraform apply
```

Terraform should now be able to:
- ✅ Detect that APIs are enabled (no permission errors)
- ✅ Create VPC network
- ✅ Create Cloud SQL instance
- ✅ Create Cloud Storage buckets
- ✅ Create Pub/Sub topics/subscriptions
- ✅ Create Artifact Registry
- ✅ Create Secret Manager secrets
- ✅ Create Cloud Run services

## What's Already Done

✅ Service accounts created:
- `buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com`
- `buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com`

## What Terraform Will Create Next

After APIs are enabled, Terraform will create:
- VPC network and subnet
- Cloud SQL PostgreSQL instance
- Cloud Storage buckets (uploads, overlays)
- Pub/Sub topics and subscriptions
- Artifact Registry repository
- Secret Manager secrets
- Cloud Run services (API and Worker)

## Alternative: Use Helper Script

You can also use the helper script to open all API pages:

```bash
cd Overlay-main/infra
./enable-apis-console.sh
```

Then enable each API in the browser windows that open.

## After APIs Are Enabled

Once all APIs show as "Enabled" in the console:

1. **Run terraform apply:**
   ```bash
   terraform apply
   ```

2. **It should now succeed** in creating the remaining resources

3. **Get outputs:**
   ```bash
   terraform output
   ```

4. **Continue with deployment:**
   - Build and push Docker images
   - Setup secrets
   - Run migrations
   - Deploy frontend
