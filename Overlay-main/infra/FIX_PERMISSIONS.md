# Fixing GCP Permission Issues

## Problem
You're getting "Permission denied" errors when trying to enable APIs. This means your account (`devbt777@gmail.com`) doesn't have the necessary IAM roles on the `buildtrace-dev` project.

## Solution Options

### Option 1: Enable APIs via Console (Easiest)

If you have console access, you can enable APIs through the web interface:

1. **Go to APIs & Services Library**
   - Visit: https://console.cloud.google.com/apis/library?project=buildtrace-dev
   - Or navigate: APIs & Services > Library

2. **Enable each API individually:**
   - Search for and enable:
     - **Cloud Run API** (`run.googleapis.com`)
     - **Cloud SQL Admin API** (`sqladmin.googleapis.com`)
     - **Cloud Storage API** (`storage.googleapis.com`)
     - **Cloud Pub/Sub API** (`pubsub.googleapis.com`)
     - **Artifact Registry API** (`artifactregistry.googleapis.com`)
     - **Secret Manager API** (`secretmanager.googleapis.com`)
     - **Service Networking API** (`servicenetworking.googleapis.com`)
     - **Cloud Resource Manager API** (`cloudresourcemanager.googleapis.com`)

3. **Wait for APIs to enable** (usually takes 1-2 minutes)

### Option 2: Request Proper IAM Role

You need one of these roles to enable APIs:
- **Owner** (full access)
- **Editor** (can manage resources)
- **Service Usage Admin** (can enable/disable APIs)

**To request access:**

1. **Check your current role:**
   - Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   - Look for `devbt777@gmail.com` in the list
   - Note your current role

2. **If you don't have Owner/Editor/Service Usage Admin:**
   - Contact the project owner to grant you one of these roles
   - Or if you're the project owner, you may need to grant yourself the role

3. **Grant yourself Owner role (if you're the project owner):**
   ```bash
   # This requires you to be the project owner or have Organization Admin role
   gcloud projects add-iam-policy-binding buildtrace-dev \
     --member="user:devbt777@gmail.com" \
     --role="roles/owner"
   ```

### Option 3: Use Terraform to Enable APIs

Terraform can enable APIs automatically if you have the right permissions. The Terraform configuration includes API enabling:

```bash
cd Overlay-main/infra/terraform
terraform init
terraform plan  # This will show APIs that need to be enabled
terraform apply  # This will enable APIs automatically
```

**Note:** Terraform still requires you to have `Service Usage Admin` role or higher.

### Option 4: Verify Billing Account

Make sure billing is properly linked:

1. **Go to Billing:**
   - Visit: https://console.cloud.google.com/billing?project=buildtrace-dev

2. **Link billing account:**
   - If no billing account is linked, click "Link a billing account"
   - Select your billing account (the name might be different from "buildtrace-dev")
   - The billing account ID format is usually: `01XXXX-XXXXXX-XXXXXX`

3. **Verify billing is active:**
   - The project should show "Active" status

## Quick Fix: Enable APIs One by One via Console

Since you have console access, the fastest solution is:

1. **Open this link** (replace with your project if different):
   ```
   https://console.cloud.google.com/apis/library?project=buildtrace-dev
   ```

2. **Enable each API:**
   - Click on each API name below
   - Click "Enable" button
   - Wait for confirmation

**Direct links to enable each API:**
- [Cloud Run API](https://console.cloud.google.com/apis/library/run.googleapis.com?project=buildtrace-dev)
- [Cloud SQL Admin API](https://console.cloud.google.com/apis/library/sqladmin.googleapis.com?project=buildtrace-dev)
- [Cloud Storage API](https://console.cloud.google.com/apis/library/storage.googleapis.com?project=buildtrace-dev)
- [Cloud Pub/Sub API](https://console.cloud.google.com/apis/library/pubsub.googleapis.com?project=buildtrace-dev)
- [Artifact Registry API](https://console.cloud.google.com/apis/library/artifactregistry.googleapis.com?project=buildtrace-dev)
- [Secret Manager API](https://console.cloud.google.com/apis/library/secretmanager.googleapis.com?project=buildtrace-dev)
- [Service Networking API](https://console.cloud.google.com/apis/library/servicenetworking.googleapis.com?project=buildtrace-dev)
- [Cloud Resource Manager API](https://console.cloud.google.com/apis/library/cloudresourcemanager.googleapis.com?project=buildtrace-dev)

## Verify APIs Are Enabled

After enabling, verify with:

```bash
gcloud services list --enabled --project=buildtrace-dev
```

Or check in console:
- Go to: https://console.cloud.google.com/apis/dashboard?project=buildtrace-dev

## If You Still Can't Enable APIs

1. **Check if you're the project owner:**
   - Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   - Look for your email and check the role

2. **If you're not the owner:**
   - Contact the project owner to:
     - Grant you "Owner" or "Editor" role, OR
     - Enable the APIs for you

3. **If you ARE the owner but still can't enable:**
   - There might be an organization policy blocking API enablement
   - Check: https://console.cloud.google.com/iam-admin/orgpolicies?project=buildtrace-dev
   - Look for policies related to "Service Usage" or "API Enablement"

## After APIs Are Enabled

Once APIs are enabled, continue with:

```bash
# Create Terraform state bucket
gsutil mb -p buildtrace-dev -l us-central1 gs://buildtrace-terraform-state
gsutil versioning set on gs://buildtrace-terraform-state

# Continue with Terraform
cd Overlay-main/infra/terraform
terraform init
terraform plan
terraform apply
```

## Need Help?

If you continue to have permission issues:
1. Verify you're logged into the correct Google account
2. Check that `buildtrace-dev` is the correct project ID
3. Verify billing is linked and active
4. Contact your GCP organization admin if this is an organization-managed project
