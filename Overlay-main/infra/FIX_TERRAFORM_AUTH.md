# Fixing Terraform Authentication Issues

## Problem
You're getting OAuth authentication errors when Terraform tries to access the GCS backend:
```
oauth2: cannot fetch token: 400 Bad Request
"error": "invalid_grant"
"error_description": "reauth related error (invalid_rapt)"
```

This means your gcloud authentication has expired or needs re-authentication.

## Solution 1: Re-authenticate with gcloud (Recommended)

### Step 1: Re-authenticate
```bash
gcloud auth login
```

This will open a browser window. Complete the authentication flow.

### Step 2: Set Application Default Credentials
```bash
gcloud auth application-default login
```

This sets up credentials that Terraform can use.

### Step 3: Verify Authentication
```bash
gcloud auth list
```

You should see your account listed as active.

### Step 4: Try Terraform Again
```bash
cd Overlay-main/infra/terraform
terraform init
```

## Solution 2: Use Local State (Temporary Workaround)

If you can't fix authentication right now, you can use local state temporarily:

### Step 1: Comment Out Backend
Edit `main.tf` and comment out the backend block:

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
  }

  # Comment out backend for local state
  # backend "gcs" {
  #   bucket = "buildtrace-terraform-state"
  #   prefix = "terraform/state"
  # }
}
```

### Step 2: Initialize with Local State
```bash
cd Overlay-main/infra/terraform
terraform init
```

### Step 3: Continue with Terraform
```bash
terraform plan
terraform apply
```

⚠️ **Warning**: Local state means:
- State is stored in `terraform.tfstate` file
- Not shared between team members
- Should be committed to git (with caution) or backed up
- Not recommended for production

## Solution 3: Use Service Account (For CI/CD)

If you're setting up for automation, use a service account:

### Step 1: Create Service Account
```bash
gcloud iam service-accounts create terraform-sa \
  --display-name="Terraform Service Account" \
  --project=buildtrace-dev
```

### Step 2: Grant Permissions
```bash
# Grant Storage Admin for state bucket
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:terraform-sa@buildtrace-dev.iam.gserviceaccount.com" \
  --role="roles/storage.admin"

# Grant other necessary roles
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="serviceAccount:terraform-sa@buildtrace-dev.iam.gserviceaccount.com" \
  --role="roles/owner"
```

### Step 3: Create and Download Key
```bash
gcloud iam service-accounts keys create terraform-key.json \
  --iam-account=terraform-sa@buildtrace-dev.iam.gserviceaccount.com
```

### Step 4: Use Service Account
```bash
export GOOGLE_APPLICATION_CREDENTIALS="$(pwd)/terraform-key.json"
terraform init
```

## Quick Fix: Re-authenticate Now

Run these commands:

```bash
# Re-authenticate
gcloud auth login

# Set application default credentials
gcloud auth application-default login

# Verify
gcloud auth list

# Try terraform again
cd Overlay-main/infra/terraform
terraform init
```

## If Re-authentication Doesn't Work

### Check for Organization Policies
If you're in a Google Workspace organization, there might be policies blocking authentication:

1. Check if you need to use a different authentication method
2. Contact your organization admin
3. Try using a service account instead

### Clear Cached Credentials
```bash
# Clear gcloud credentials
gcloud auth revoke --all

# Clear application default credentials
rm -rf ~/.config/gcloud/application_default_credentials.json

# Re-authenticate
gcloud auth login
gcloud auth application-default login
```

## Verify Everything Works

After fixing authentication:

```bash
# Test GCS access
gsutil ls gs://buildtrace-terraform-state

# If that works, try Terraform
cd Overlay-main/infra/terraform
terraform init
```

## Next Steps

Once `terraform init` succeeds:
1. Run `terraform plan` to review changes
2. Run `terraform apply` to create infrastructure
3. Type `yes` when prompted
