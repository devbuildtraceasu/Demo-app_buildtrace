# Request IAM Permissions

## Quick Request Template

Send this to your project owner:

---

**Subject:** Request IAM Roles for BuildTrace Terraform Deployment

Hi,

I need the following IAM roles on project `buildtrace-dev` to deploy infrastructure via Terraform:

**Account:** `devbt777@gmail.com`

**Required Roles:**
1. **Compute Network Admin** - Create VPC networks
2. **Secret Manager Admin** - Create and manage secrets
3. **Storage Admin** - Create Cloud Storage buckets
4. **Pub/Sub Admin** - Create topics and subscriptions
5. **Artifact Registry Admin** - Create Docker repositories
6. **Project IAM Admin** - Grant roles to service accounts

**Alternative:** If you prefer, I can create the resources manually via the GCP Console. See `MANUAL_RESOURCE_CREATION.md` for details.

Thanks!

---

## Grant Permissions via Console

1. Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
2. Click **"Grant Access"**
3. Enter: `devbt777@gmail.com`
4. Select these roles:
   - Compute Network Admin
   - Secret Manager Admin
   - Storage Admin
   - Pub/Sub Admin
   - Artifact Registry Admin
   - Project IAM Admin
5. Click **"Save"**

## Grant Permissions via CLI

If you have `gcloud` access with admin permissions:

```bash
PROJECT_ID="buildtrace-dev"
USER_EMAIL="devbt777@gmail.com"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$USER_EMAIL" \
  --role="roles/compute.networkAdmin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$USER_EMAIL" \
  --role="roles/secretmanager.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$USER_EMAIL" \
  --role="roles/storage.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$USER_EMAIL" \
  --role="roles/pubsub.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$USER_EMAIL" \
  --role="roles/artifactregistry.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="user:$USER_EMAIL" \
  --role="roles/resourcemanager.projectIamAdmin"
```

## Verify Permissions

After permissions are granted, verify with:

```bash
gcloud projects get-iam-policy buildtrace-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:devbt777@gmail.com" \
  --format="table(bindings.role)"
```

You should see all the roles listed above.
