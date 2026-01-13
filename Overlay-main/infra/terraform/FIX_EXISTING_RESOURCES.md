# Fixing Terraform for Existing Resources

## Current Situation

✅ APIs are enabled manually  
✅ Service accounts exist:
- `buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com`
- `buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com`

❌ Terraform is trying to create them again (causing errors)

## Solution: Import Existing Resources

### Step 1: Import Service Accounts into Terraform State

Run this to tell Terraform the service accounts already exist:

```bash
cd Overlay-main/infra/terraform

# Import API service account
terraform import google_service_account.api projects/buildtrace-dev/serviceAccounts/buildtrace-api@buildtrace-dev-484112.iam.gserviceaccount.com

# Import Worker service account
terraform import google_service_account.worker projects/buildtrace-dev/serviceAccounts/buildtrace-worker@buildtrace-dev-484112.iam.gserviceaccount.com
```

Or use the helper script:

```bash
cd Overlay-main/infra/terraform
./import-existing-resources.sh
```

### Step 2: Verify Imports

Check that they're imported:

```bash
terraform state list | grep service_account
```

You should see:
- `google_service_account.api`
- `google_service_account.worker`

### Step 3: Run Terraform Apply

Now Terraform knows the service accounts exist and won't try to create them:

```bash
terraform apply
```

## What I've Already Done

✅ Commented out the `google_project_service` resources (APIs already enabled)
✅ Created import script for service accounts

## After Import

Terraform should now be able to create:
- VPC network and subnet
- Cloud SQL instance
- Cloud Storage buckets
- Pub/Sub topics and subscriptions
- Artifact Registry
- Secret Manager secrets
- Cloud Run services

## If Import Fails

If you get permission errors during import, you can:

1. **Skip service account creation** by commenting them out in `main.tf`
2. **Manually grant IAM roles** to the existing service accounts
3. **Continue with Terraform** for other resources

But importing is the cleanest solution.
