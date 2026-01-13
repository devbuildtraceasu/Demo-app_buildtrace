# Quick Fix Checklist - Try These in Order

## ✅ Step 1: Fresh Login (5 minutes)

1. **Log out of GCP Console:**
   - Go to: https://console.cloud.google.com
   - Click profile icon (top right) → "Sign out"

2. **Clear browser data:**
   - Chrome: Settings → Privacy → Clear browsing data → Cookies and site data
   - Or use Incognito/Private window

3. **Log back in:**
   - Go to: https://console.cloud.google.com
   - Sign in with: `devbt777@gmail.com`
   - Select project: `buildtrace-dev`

4. **Test access:**
   - Try: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   - Can you see the IAM page now? ✅

## ✅ Step 2: Check Billing (2 minutes)

1. **Go to billing:**
   - https://console.cloud.google.com/billing?project=buildtrace-dev

2. **Check:**
   - Do you see a billing account?
   - Who has access to it?
   - That person can grant you permissions

## ✅ Step 3: Try gcloud CLI (3 minutes)

```bash
# Clear old auth
gcloud auth revoke --all

# Fresh login
gcloud auth login

# Set project
gcloud config set project buildtrace-dev

# Test access
gcloud projects describe buildtrace-dev

# If that works, try granting yourself Editor
gcloud projects add-iam-policy-binding buildtrace-dev \
  --member="user:devbt777@gmail.com" \
  --role="roles/editor"
```

## ✅ Step 4: Check Project Settings (2 minutes)

1. **Go to:**
   - https://console.cloud.google.com/iam-admin/settings?project=buildtrace-dev

2. **Look for:**
   - Project number: `484112` (we know this)
   - Any contact info or owner details

## ✅ Step 5: Contact Billing Account Owner

If Steps 1-4 don't work:

1. **Find billing account owner** (from Step 2)
2. **Ask them to grant you Owner role:**
   - Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
   - Click "Grant Access"
   - Enter: `devbt777@gmail.com`
   - Role: **Owner**
   - Click "Save"

## ✅ Step 6: Last Resort - New Project

If nothing works and you have billing access:

```bash
# Create new project
gcloud projects create buildtrace-dev-v2 \
  --name="BuildTrace Dev V2"

# Link billing
gcloud billing projects link buildtrace-dev-v2 \
  --billing-account=YOUR_BILLING_ACCOUNT_ID

# Update terraform.tfvars
# Change: project_id = "buildtrace-dev-v2"
```

---

## What Worked?

After trying these, let me know:
- ✅ Can you access IAM page after fresh login?
- ✅ Can you see billing account?
- ✅ Does `gcloud projects describe` work?
- ✅ Who has access to billing?

This will help determine the next step!
