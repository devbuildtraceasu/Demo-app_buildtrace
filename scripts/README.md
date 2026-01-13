# BuildTrace Scripts

Diagnostic and utility scripts for BuildTrace.

## Diagnostic Scripts

- `check-comparison-status.sh` - Check status of a comparison and its job
- `check-job-logs.sh` - Check worker logs for job processing
- `check-worker-logs.sh` - View worker service logs
- `check-frontend-logs.sh` - View frontend service logs
- `diagnose-jobs.sh` - Diagnose job processing issues

## Deployment Scripts

All deployment scripts are in `Overlay-main/infra/`:
- `DEPLOY_FRONTEND.sh` - Deploy frontend to Cloud Run
- `REDEPLOY_API.sh` - Rebuild and redeploy API
- `BUILD_AND_PUSH.sh` - Build and push Docker images
- `setup-google-auth.sh` - Configure Google OAuth
