# Check Your Current Permissions

## Why You're Seeing This

Even if you created the project, you might not have **Owner** or **Editor** permissions. GCP projects can have different permission levels.

## Check Your Current Roles

Run this command to see what roles you currently have:

```bash
gcloud projects get-iam-policy buildtrace-dev \
  --flatten="bindings[].members" \
  --filter="bindings.members:devbt777@gmail.com" \
  --format="table(bindings.role)"
```

## Check Who Has Owner Role

To see who can grant you permissions:

```bash
gcloud projects get-iam-policy buildtrace-dev \
  --flatten="bindings[].members" \
  --filter="bindings.role:roles/owner" \
  --format="table(bindings.members)"
```

## If You Are the Owner

If you see your email in the Owner list, you can grant yourself permissions:

### Via Console:
1. Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
2. If you see "You need additional access", try:
   - Click "Request permissions" button
   - Or check if there's another account that's the Owner

### Via CLI (if you have Owner role):
```bash
# First, make sure you're authenticated
gcloud auth login

# Then grant yourself the roles
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/editor"
```

**Note:** If you get permission errors even with `gcloud auth login`, you're not the Owner.

## If You're NOT the Owner

You'll see your email but with limited roles (like "Viewer" or "Browser"). In this case:

1. **Use the "Request permissions" button** in the console
2. **Contact the actual Owner** (from the command above)
3. **Or create resources manually** (see `MANUAL_RESOURCE_CREATION.md`)

## Quick Test

Try this to see if you can read the project:

```bash
gcloud projects describe buildtrace-dev
```

If this works, you have basic access. If it fails, you need more permissions.
