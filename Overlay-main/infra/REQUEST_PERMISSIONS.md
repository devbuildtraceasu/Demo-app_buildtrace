# Requesting Proper GCP Permissions

## Current Problem

You're getting permission errors because your account (`devbt777@gmail.com`) doesn't have the necessary IAM roles:

1. **Service Usage Admin** - To enable/disable APIs
2. **Service Account Admin** - To create service accounts
3. **Owner or Editor** - For full project access (recommended)

## Solution: Request Proper IAM Role

### Option 1: Request Owner/Editor Role (Recommended)

You need someone with Owner role to grant you access:

1. **Check who has Owner role:**
   - Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   - Look for users with "Owner" role

2. **Request access:**
   - Contact the project owner
   - Ask them to grant you **Owner** or **Editor** role

3. **Or if you're the project owner:**
   - Grant yourself the role via console or command line

### Option 2: Grant Yourself Owner Role (If You're Project Owner)

If you created the project, you should be able to grant yourself the role:

```bash
# Check your current role
gcloud projects get-iam-policy buildtrace-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:devbt777@gmail.com" \
  --format="table(bindings.role)"

# Grant yourself Owner role (requires you to be project owner or org admin)
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/owner"
```

### Option 3: Enable APIs Manually First

If you can't get Owner/Editor role right now, you can enable APIs manually, then Terraform can create the rest:

1. **Enable APIs via Console:**
   - Go to: https://console.cloud.google.com/apis/library?project=buildtrace-dev
   - Enable all 8 APIs:
     - Cloud Run API
     - Cloud SQL Admin API
     - Cloud Storage API
     - Pub/Sub API
     - Artifact Registry API
     - Secret Manager API
     - Service Networking API
     - Cloud Resource Manager API
     - Compute Engine API

2. **Create Service Accounts Manually:**
   - Go to: https://console.cloud.google.com/iam-admin/serviceaccounts?project=buildtrace-dev
   - Create service account: `buildtrace-api`
   - Create service account: `buildtrace-worker`

3. **Then modify Terraform to skip these resources:**
   - Comment out the `google_project_service` resources (APIs already enabled)
   - Comment out the `google_service_account` resources (created manually)
   - Run `terraform apply` for the remaining resources

## Required IAM Roles

To run Terraform successfully, you need one of these:

| Role | What It Allows |
|------|----------------|
| **Owner** | Full access to all resources |
| **Editor** | Can create and manage resources |
| **Service Usage Admin** | Can enable/disable APIs |
| **Service Account Admin** | Can create service accounts |

**Recommended:** Request **Owner** or **Editor** role for simplicity.

## Check Your Current Role

1. Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
2. Find your email: `devbt777@gmail.com`
3. Check what role you have

## If You Don't Have Access

If you can't see the IAM page or don't have any role:

1. **Verify you're in the correct project:**
   ```bash
   gcloud config get-value project
   ```
   Should show: `buildtrace-dev`

2. **Check if project exists:**
   ```bash
   gcloud projects describe buildtrace-dev
   ```

3. **Contact the project owner** to grant you access

## After Getting Proper Permissions

Once you have Owner or Editor role:

1. **Re-run Terraform:**
   ```bash
   cd Overlay-main/infra/terraform
   terraform apply
   ```

2. **It should now succeed** in creating all resources

## Alternative: Manual Setup

If you can't get the proper permissions, you can:

1. Enable APIs manually via console
2. Create service accounts manually
3. Create other resources via console
4. Skip Terraform for now

But this defeats the purpose of infrastructure as code. **It's better to get proper IAM permissions.**

## Next Steps

1. **Check your IAM role** in the console
2. **Request Owner/Editor role** from project owner
3. **Or enable APIs manually** and create service accounts manually
4. **Then retry** `terraform apply`
