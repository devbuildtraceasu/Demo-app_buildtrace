# How to Grant Access to devbt777@gmail.com

## For Project Owner/Admin

You need to grant IAM roles to `devbt777@gmail.com` so they can deploy infrastructure via Terraform.

## Method 1: Via GCP Console (Easiest)

1. **Go to IAM & Admin:**
   - Direct link: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   - Or navigate: IAM & Admin > IAM

2. **Click "Grant Access"** (top of the page)

3. **Enter the email:**
   - Principal: `devbt777@gmail.com`

4. **Select these roles:**
   - ✅ **Compute Network Admin** (`roles/compute.networkAdmin`)
   - ✅ **Secret Manager Admin** (`roles/secretmanager.admin`)
   - ✅ **Storage Admin** (`roles/storage.admin`)
   - ✅ **Pub/Sub Admin** (`roles/pubsub.admin`)
   - ✅ **Artifact Registry Admin** (`roles/artifactregistry.admin`)
   - ✅ **Project IAM Admin** (`roles/resourcemanager.projectIamAdmin`)

5. **Click "Save"**

That's it! The user can now run `terraform apply`.

## Method 2: Via gcloud CLI

If you have `gcloud` CLI installed and are authenticated as a project owner:

```bash
PROJECT_ID="buildtrace-dev"
USER_EMAIL="devbt777@gmail.com"

# Grant all required roles
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

After granting, verify the user has the roles:

```bash
gcloud projects get-iam-policy buildtrace-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:devbt777@gmail.com" \
  --format="table(bindings.role)"
```

## What Each Role Does

- **Compute Network Admin**: Create/manage VPC networks and subnets
- **Secret Manager Admin**: Create/manage secrets (API keys, passwords)
- **Storage Admin**: Create/manage Cloud Storage buckets
- **Pub/Sub Admin**: Create/manage Pub/Sub topics and subscriptions
- **Artifact Registry Admin**: Create/manage Docker image repositories
- **Project IAM Admin**: Grant IAM roles to service accounts (needed for Cloud Run)

## Alternative: Grant Editor Role (Less Secure)

If you want to grant broader permissions (not recommended for production):

```bash
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/editor"
```

**Note:** Editor role grants almost all permissions. Use specific roles above for better security.
