# BuildTrace GCP Deployment Guide

This directory contains infrastructure and deployment scripts for deploying BuildTrace to Google Cloud Platform.

## Quick Start

1. **Prerequisites**
   ```bash
   # Ensure you have these installed
   gcloud --version
   terraform --version
   docker --version
   ```

2. **Authenticate with GCP**
   ```bash
   gcloud auth login
   gcloud config set project buildtrace-dev
   ```

3. **Follow Console Steps**
   - See [CONSOLE_STEPS.md](./CONSOLE_STEPS.md) for manual console setup
   - Enable billing
   - Enable required APIs

4. **Configure Terraform**
   ```bash
   cd infra/terraform
   cp terraform.tfvars.example terraform.tfvars
   # Edit terraform.tfvars with your project ID and region
   ```

5. **Deploy Infrastructure**
   ```bash
   cd infra
   ./deploy.sh
   ```

6. **Setup Secrets**
   ```bash
   ./setup-secrets.sh
   ```

7. **Run Migrations**
   ```bash
   ./run-migrations.sh
   ```

8. **Deploy Frontend**
   ```bash
   ./deploy-frontend.sh firebase  # or 'cloudrun'
   ```

## Directory Structure

```
infra/
├── terraform/           # Terraform infrastructure as code
│   ├── main.tf          # Main infrastructure definitions
│   ├── variables.tf     # Variable definitions
│   ├── terraform.tfvars # Your configuration (create from example)
│   └── terraform.tfvars.example
├── cloudbuild.yaml      # Cloud Build CI/CD configuration
├── deploy.sh            # Main deployment script
├── setup-secrets.sh     # Secret Manager setup
├── run-migrations.sh    # Database migration script
├── deploy-frontend.sh   # Frontend deployment script
├── CONSOLE_STEPS.md     # Manual console steps guide
└── README.md           # This file
```

## Scripts

### `deploy.sh`
Main deployment script that:
- Creates Terraform state bucket
- Initializes and applies Terraform
- Builds and pushes Docker images
- Deploys to Cloud Run

### `setup-secrets.sh`
Interactive script to create and configure secrets in Secret Manager:
- OpenAI API key
- Gemini API key
- JWT secret
- Google OAuth credentials

### `run-migrations.sh`
Runs Prisma database migrations on Cloud SQL:
- Connects via Cloud SQL Proxy
- Executes migrations
- Cleans up proxy connection

### `deploy-frontend.sh`
Deploys the React frontend to either:
- Firebase Hosting (recommended for static sites)
- Cloud Run (for more control)

## Terraform Outputs

After running `terraform apply`, you'll get:
- `api_url` - Cloud Run API service URL
- `db_connection_name` - Cloud SQL connection name
- `uploads_bucket` - GCS bucket for uploads
- `overlays_bucket` - GCS bucket for overlays
- `vision_topic` - Pub/Sub topic name
- `artifact_registry` - Artifact Registry repository

## Environment Variables

### API Service
- `DATABASE_URL` - Constructed from Cloud SQL components
- `STORAGE_BACKEND` - Set to `gcs`
- `STORAGE_BUCKET` - GCS bucket name
- `PUBSUB_PROJECT_ID` - GCP project ID
- `VISION_TOPIC` - Pub/Sub topic
- `CORS_ORIGINS` - JSON array of allowed origins
- Secrets: `OPENAI_API_KEY`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`

### Worker Service
- `DB_HOST` - Cloud SQL Unix socket path
- `DB_PORT` - 5432
- `DB_NAME` - Database name
- `DB_USER` - Database user
- `DB_PASSWORD` - From Secret Manager
- `STORAGE_BACKEND` - Set to `gcs`
- `STORAGE_BUCKET` - GCS bucket name
- `PUBSUB_PROJECT_ID` - GCP project ID
- `VISION_TOPIC` - Pub/Sub topic
- `VISION_SUBSCRIPTION` - Pub/Sub subscription
- Secrets: `OPENAI_API_KEY`, `GEMINI_API_KEY`

## Troubleshooting

### Terraform Errors

**Error: Backend initialization required**
```bash
cd infra/terraform
terraform init
```

**Error: API not enabled**
```bash
gcloud services enable <api-name> --project=buildtrace-dev
```

### Cloud Run Deployment Issues

**Service won't start**
- Check logs: `gcloud run services logs read buildtrace-api --region=us-central1`
- Verify secrets are accessible
- Check service account permissions

**Database connection failed**
- Verify Cloud SQL instance is running
- Check connection name is correct
- Ensure service account has `roles/cloudsql.client`

### Secret Manager Issues

**Secret not found**
- Create secret first: `./setup-secrets.sh`
- Verify secret name matches Terraform configuration
- Check service account has `roles/secretmanager.secretAccessor`

## Cost Optimization

- Use `min_instance_count = 0` for Cloud Run (scales to zero)
- Use appropriate database tier for your workload
- Enable Cloud Storage lifecycle policies
- Set up billing alerts

## Security Best Practices

- Never commit secrets to git
- Use Secret Manager for all sensitive data
- Enable VPC for Cloud SQL (private IP)
- Use least-privilege IAM roles
- Enable audit logging
- Regular security updates

## Next Steps

- Set up CI/CD with Cloud Build
- Configure custom domains
- Set up monitoring and alerts
- Implement backup strategies
- Review and optimize costs

## Support

For issues or questions:
1. Check [CONSOLE_STEPS.md](./CONSOLE_STEPS.md) for detailed steps
2. Review Terraform outputs for resource information
3. Check Cloud Run logs for application errors
4. Verify IAM permissions and service account roles
