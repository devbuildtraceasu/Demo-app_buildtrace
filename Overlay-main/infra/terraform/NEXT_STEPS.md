# Next Steps After Terraform Init

## ✅ Terraform Initialized Successfully!

You're now ready to create the infrastructure. Here's what to do next:

## Step 1: Review the Plan

Run this to see what Terraform will create:

```bash
terraform plan
```

This will show you:
- All resources that will be created
- Any configuration issues
- Estimated costs (if available)

**Review the output carefully** before proceeding.

## Step 2: Apply the Infrastructure

Once you've reviewed the plan and everything looks good:

```bash
terraform apply
```

Terraform will:
1. Show you the plan again
2. Ask for confirmation: `Do you want to perform these actions?`
3. Type `yes` to proceed
4. Create all the resources (this takes 10-15 minutes)

## What Will Be Created

The Terraform configuration will create:

- **VPC Network**: Private network for services
- **Cloud SQL**: PostgreSQL 15 database instance
- **Cloud Storage**: 2 buckets (uploads and overlays)
- **Pub/Sub**: Topic and subscription for job queue
- **Artifact Registry**: Docker image repository
- **Service Accounts**: For API and Worker services
- **IAM Roles**: Permissions for service accounts
- **Cloud Run Services**: API and Worker (initially without images)

## Important Notes

### ⚠️ This Will Create Billable Resources

- Cloud SQL instance: ~$25/month
- Cloud Run: Pay-per-use
- Cloud Storage: ~$5-20/month
- **Total estimated**: ~$60-200/month depending on usage

### ⏱️ Time Required

- `terraform plan`: 1-2 minutes
- `terraform apply`: 10-15 minutes (database creation is slow)

### 🔐 Authentication

Make sure you have:
- ✅ APIs enabled (see `FIX_PERMISSIONS.md`)
- ✅ Billing enabled on the project
- ✅ Proper IAM roles (Owner/Editor)

## Common Issues

### "API not enabled"
- Enable the required APIs via console (see `FIX_PERMISSIONS.md`)
- Or wait a few minutes for Terraform to enable them automatically

### "Permission denied"
- Check your IAM role in the project
- You need Owner or Editor role

### "Billing not enabled"
- Link a billing account to the project
- Go to: https://console.cloud.google.com/billing

## After terraform apply

Once infrastructure is created:

1. **Get the outputs:**
   ```bash
   terraform output
   ```
   This shows:
   - API URL
   - Database connection name
   - Bucket names
   - etc.

2. **Build and push Docker images:**
   ```bash
   cd ../..
   ./infra/deploy.sh
   ```

3. **Setup secrets:**
   ```bash
   ./infra/setup-secrets.sh
   ```

4. **Run migrations:**
   ```bash
   ./infra/run-migrations.sh
   ```

## Rollback (if needed)

If something goes wrong:

```bash
# Destroy all resources (BE CAREFUL!)
terraform destroy
```

⚠️ **Warning**: This will delete everything, including the database and all data!

## Ready to Proceed?

Run:
```bash
terraform plan
```

Then review the output. If everything looks good:
```bash
terraform apply
```
