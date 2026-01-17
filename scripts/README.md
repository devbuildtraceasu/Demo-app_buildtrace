# BuildTrace Diagnostic Scripts

Shell scripts for debugging and monitoring BuildTrace services in production.

## Prerequisites

- Google Cloud SDK (`gcloud`) installed and authenticated
- Access to `buildtrace-prod` project

Set your project:
```bash
export GCP_PROJECT_ID=buildtrace-prod
```

## Scripts Overview

| Script | Purpose |
|--------|---------|
| `CHECK_ALL_LOGS.sh` | Comprehensive log check across all services |
| `CHECK_WORKER_LOGS.sh` | Worker service logs and Pub/Sub activity |
| `CHECK_JOB_LOGS.sh` | Job-specific processing logs |
| `CHECK_FRONTEND_LOGS.sh` | Frontend service logs |
| `DIAGNOSE_JOBS.sh` | Full job processing diagnosis |
| `CHECK_COMPARISON_STATUS.sh` | Check status of a specific comparison |
| `CHECK_REDIRECT_URI.sh` | Validate OAuth redirect URI configuration |
| `DEBUG_REDIRECT_URI.sh` | Debug OAuth redirect issues |

## Usage

### Check All Logs

Comprehensive check of API, Worker, and error logs:

```bash
./scripts/CHECK_ALL_LOGS.sh
```

Shows:
- All worker logs (last 2 hours)
- Pub/Sub subscription activity
- API job publishing logs
- All errors across services

### Diagnose Job Processing

Full diagnosis when jobs are stuck or not processing:

```bash
./scripts/DIAGNOSE_JOBS.sh
```

Shows:
- Drawing job creation (API side)
- Worker startup and connection
- Drawing preprocessing logs
- Sheet/Gemini block extraction logs
- Pub/Sub subscription status
- All errors

### Check Worker Logs

Worker-specific logs for processing issues:

```bash
./scripts/CHECK_WORKER_LOGS.sh
```

### Check Comparison Status

Check a specific comparison's status and related jobs:

```bash
./scripts/CHECK_COMPARISON_STATUS.sh <comparison_id>
```

### Debug OAuth

Check OAuth redirect URI configuration:

```bash
./scripts/CHECK_REDIRECT_URI.sh
./scripts/DEBUG_REDIRECT_URI.sh
```

## Documentation Files

| File | Purpose |
|------|---------|
| `CHECK_COMPARISON_DETAILS.md` | How to manually check comparison details |
| `CHECK_GEMINI_BLOCKS.md` | Debugging Gemini block extraction |
| `CHECK_JOB_STATUS.md` | Manual job status checking guide |

## Common Patterns

### Filter by Service

```bash
# API only
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
  --limit=50 --project=buildtrace-prod

# Worker only
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=50 --project=buildtrace-prod
```

### Filter by Severity

```bash
# Errors only
gcloud logging read \
  "severity>=ERROR" \
  --limit=30 --project=buildtrace-prod

# Warnings and above
gcloud logging read \
  "severity>=WARNING" \
  --limit=50 --project=buildtrace-prod
```

### Filter by Time

```bash
# Last hour
gcloud logging read "..." --freshness=1h

# Last 4 hours
gcloud logging read "..." --freshness=4h

# Specific time range
gcloud logging read "..." \
  --format="table(timestamp,severity,textPayload)" \
  --order="asc" \
  --filter='timestamp>="2026-01-17T00:00:00Z" AND timestamp<="2026-01-17T23:59:59Z"'
```

### Search by Content

```bash
# Search for specific text
gcloud logging read \
  "resource.type=cloud_run_revision AND textPayload=~\"error\"" \
  --limit=30 --project=buildtrace-prod

# Search for specific ID
gcloud logging read \
  "resource.type=cloud_run_revision AND textPayload=~\"<comparison_id>\"" \
  --limit=30 --project=buildtrace-prod
```

## Related Documentation

- [../DEBUGGING.md](../DEBUGGING.md) - Comprehensive debugging guide
- [../DEPLOYMENT.md](../DEPLOYMENT.md) - Deployment and service management
- [../AUTHENTICATION.md](../AUTHENTICATION.md) - OAuth troubleshooting
