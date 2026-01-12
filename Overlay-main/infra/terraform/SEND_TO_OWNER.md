# Email Template to Send to Project Owner

Copy and send this email to the project owner:

---

**Subject:** Request IAM Permissions for BuildTrace Terraform Deployment

Hi [Project Owner Name],

I need IAM permissions on the `buildtrace-dev` project to deploy infrastructure via Terraform.

**My email:** `devbt777@gmail.com`

**Required IAM Roles:**
1. Compute Network Admin - To create VPC networks
2. Secret Manager Admin - To create secrets for API keys
3. Storage Admin - To create Cloud Storage buckets
4. Pub/Sub Admin - To create Pub/Sub topics/subscriptions
5. Artifact Registry Admin - To create Docker repositories
6. Project IAM Admin - To grant roles to service accounts

**How to Grant (Choose One):**

### Option 1: Via Console (Easiest)
1. Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
2. Click "Grant Access"
3. Enter: `devbt777@gmail.com`
4. Select all 6 roles listed above
5. Click "Save"

### Option 2: Via CLI
```bash
PROJECT_ID="buildtrace-dev"
USER_EMAIL="devbt777@gmail.com"

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

**Alternative:** If you prefer, I can create the resources manually via the GCP Console instead. Let me know which approach you prefer.

Thanks!

---

## Who is the Project Owner?

To find the project owner:

1. Go to: https://console.cloud.google.com/iam-admin/iam?project=buildtrace-dev
2. Look for users with **Owner** or **Project Owner** role
3. Contact them via email

Or check the project settings:
- Go to: https://console.cloud.google.com/iam-admin/settings?project=buildtrace-dev
- Look for "Project number" and contact info
