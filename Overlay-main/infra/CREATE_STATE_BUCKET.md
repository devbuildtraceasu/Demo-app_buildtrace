# Creating Terraform State Bucket

## Problem
You're getting "Permission denied" when trying to create the storage bucket via command line.

## Solution: Create Bucket via Console

### Step 1: Open Cloud Storage Console
1. Go to: https://console.cloud.google.com/storage/create-bucket?project=buildtrace-dev
2. Or navigate: Cloud Storage > Buckets > Create Bucket

### Step 2: Configure the Bucket
Fill in the following settings:

- **Name**: `buildtrace-terraform-state`
  - Must be globally unique (add a suffix if needed, like `buildtrace-terraform-state-12345`)
  
- **Location type**: `Region`
  
- **Location**: `us-central1` (or your preferred region)
  
- **Storage class**: `Standard`
  
- **Access control**: `Uniform` (bucket-level access)
  
- **Protection tools**: 
  - Enable **Object versioning** (important!)
  - You can skip other protection tools for now

### Step 3: Create the Bucket
Click "Create"

### Step 4: Enable Versioning
After the bucket is created:

1. Click on the bucket name: `buildtrace-terraform-state`
2. Go to the "Configuration" tab
3. Scroll to "Object versioning"
4. Click "Edit"
5. Select "Enable"
6. Click "Save"

### Step 5: Update Terraform Configuration (if bucket name differs)

If you had to use a different bucket name (because the name was taken), update Terraform:

1. Edit `Overlay-main/infra/terraform/main.tf`
2. Find the `backend "gcs"` block (around line 18-21)
3. Update the bucket name:

```hcl
backend "gcs" {
  bucket = "buildtrace-terraform-state-12345"  # Your actual bucket name
  prefix = "terraform/state"
}
```

## Alternative: Use Local State (Not Recommended for Production)

If you can't create the bucket and want to proceed for testing:

1. **Comment out the backend block** in `main.tf`:
   ```hcl
   # backend "gcs" {
   #   bucket = "buildtrace-terraform-state"
   #   prefix = "terraform/state"
   # }
   ```

2. **Use local state** (stored in `terraform.tfstate` file)
   - ⚠️ **Warning**: This is not recommended for production
   - State file should be committed to git (with caution) or stored securely
   - Multiple team members cannot share state

3. **Initialize Terraform**:
   ```bash
   cd Overlay-main/infra/terraform
   terraform init
   ```

## Verify Bucket Creation

After creating via console, verify with:

```bash
gsutil ls gs://buildtrace-terraform-state
```

Or check in console:
- Go to: https://console.cloud.google.com/storage/browser?project=buildtrace-dev

## Request Proper Permissions (Long-term Solution)

To avoid these permission issues, you need one of these roles:

- **Storage Admin** (`roles/storage.admin`) - Can create and manage buckets
- **Owner** (`roles/owner`) - Full access
- **Editor** (`roles/editor`) - Can manage resources

**To request access:**
1. Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
2. If you're the project owner, you can grant yourself the role
3. Or contact the project owner to grant you the necessary role

## After Bucket is Created

Once the bucket exists and versioning is enabled, continue with:

```bash
cd Overlay-main/infra/terraform
terraform init
terraform plan
terraform apply
```

## Troubleshooting

### "Bucket name already taken"
- The bucket name must be globally unique across all GCP projects
- Try adding a suffix: `buildtrace-terraform-state-<random-number>`
- Or use your project ID: `buildtrace-dev-terraform-state`

### "Permission denied" even in console
- You need Storage Admin role or higher
- Check your IAM role: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
- Request the role from project owner

### Can't find the bucket after creation
- Make sure you're looking in the correct project
- Check the bucket list: https://console.cloud.google.com/storage/browser?project=buildtrace-dev
