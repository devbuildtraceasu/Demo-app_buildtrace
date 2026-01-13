# Checking Your IAM Role

## What You're Seeing

You're looking at the **Service Accounts** page, which shows service accounts (not your user permissions).

## Check Your User IAM Role Instead

To see what permissions YOU have, go to the **IAM** page:

1. **Go to IAM & Admin:**
   ```
   https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   ```

2. **Look for your email:** `devbt777@gmail.com`

3. **Check your role:**
   - **Owner** ✅ - Can do everything (what you need)
   - **Editor** ✅ - Can create resources (what you need)
   - **Viewer** ❌ - Read-only (not enough)
   - **No role** ❌ - No access (need to request)

## What Terraform Needs to Create

Terraform will create these service accounts (they don't exist yet):
- `buildtrace-api@buildtrace-dev.iam.gserviceaccount.com`
- `buildtrace-worker@buildtrace-dev.iam.gserviceaccount.com`

The default compute service account you see is different - that's for Compute Engine, not what we need.

## If You Don't Have Owner/Editor Role

You need to:

1. **Request access from project owner:**
   - Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   - See who has "Owner" role
   - Contact them to grant you Owner or Editor role

2. **Or if you're the project owner:**
   - Grant yourself Owner role (see REQUEST_PERMISSIONS.md)

## Quick Check Command

You can also check your role via command line:

```bash
gcloud projects get-iam-policy buildtrace-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:devbt777@gmail.com" \
  --format="table(bindings.role)"
```

This will show what role(s) you have on the project.

## Next Steps

1. **Check your IAM role** (not service accounts)
2. **If you have Owner/Editor:** Terraform should work
3. **If you don't:** Request proper role or enable APIs manually
