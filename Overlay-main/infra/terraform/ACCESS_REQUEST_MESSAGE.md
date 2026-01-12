# Access Request Message

Use this message in the access request form:

---

**Subject/Message:**

I need IAM permissions to deploy infrastructure for BuildTrace via Terraform. 

**Required roles:**
- Compute Network Admin (to create VPC networks)
- Secret Manager Admin (to create secrets for API keys)
- Storage Admin (to create Cloud Storage buckets)
- Pub/Sub Admin (to create Pub/Sub topics/subscriptions)
- Artifact Registry Admin (to create Docker repositories)
- Project IAM Admin (to grant roles to service accounts)

**Purpose:** Deploying BuildTrace application infrastructure including Cloud SQL, Cloud Run, Storage, Pub/Sub, and Artifact Registry.

**Alternative:** If you prefer, I can create resources manually via the GCP Console instead.

Thank you!

---

## Better: Request Specific Roles

Instead of just "give permission", request these specific roles:

1. **Editor** role (gives most permissions needed)
   - OR request these individual roles:
2. Compute Network Admin
3. Secret Manager Admin
4. Storage Admin
5. Pub/Sub Admin
6. Artifact Registry Admin
7. Project IAM Admin

## After Submitting

1. **Wait for approval** - The project owner/admin will receive an email
2. **Check email** - You'll get notified when approved/denied
3. **Or proceed manually** - While waiting, you can create resources manually (see `MANUAL_RESOURCE_CREATION.md`)
