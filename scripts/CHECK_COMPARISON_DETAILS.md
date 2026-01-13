# Checking Comparison Status

## Analysis

**URL**: `http://localhost:3000/project/c19bb85dbb0bdc45f441c5147/overlay?comparison=c19bb85e051927b3e0711094e`

**Answer**: **NO, the URL does NOT affect job processing.**

### How It Works

1. **Job Processing is Independent**:
   - Jobs are processed by the **worker service** via **Pub/Sub**
   - The frontend URL is just for **displaying status**
   - Jobs run in the background regardless of what page you're on

2. **The Flow**:
   ```
   Frontend → API → Pub/Sub → Worker → Database
                    ↓
              (Job processing happens here)
                    ↓
   Frontend ← API ← Database
   (Polls status every 2 seconds)
   ```

3. **Frontend Polling**:
   - The `OverlayViewer` component polls the comparison status every 2 seconds
   - It checks: `comparison?.status === 'processing'`
   - When status changes to `'completed'` or `'failed'`, polling stops

## What to Check

### 1. **Check if Job Was Created**
The comparison ID `c19bb85e051927b3e0711094e` should have:
- An overlay record in the database
- A job record with type `vision.block.overlay.generate`
- Status should be: `Queued`, `Started`, `Completed`, or `Failed`

### 2. **Check if Job Was Published to Pub/Sub**
Look for API logs showing:
- `"Publishing job {job_id} to Pub/Sub..."`
- `"Successfully published job {job_id}, message_id={message_id}"`

### 3. **Check if Worker Received the Job**
Look for worker logs showing:
- `"[job.received] vision.block.overlay.generate"`
- `"[job.started] Overlay job started"`
- Processing logs for overlay generation

### 4. **Check Current Status**
The comparison status can be:
- `processing` - Job is being processed
- `completed` - Job finished successfully
- `failed` - Job failed
- `queued` - Job waiting to be picked up

## Common Issues

### Issue 1: Job Not Published
**Symptoms**: No "Successfully published" log in API
**Cause**: Pub/Sub publish failed
**Fix**: Check API logs for publish errors

### Issue 2: Worker Not Receiving Jobs
**Symptoms**: No "[job.received]" logs in worker
**Cause**: 
- Worker subscription not active
- Pub/Sub topic/subscription misconfigured
- Worker service not running
**Fix**: Check worker service status and Pub/Sub subscription

### Issue 3: Job Stuck in "Processing"
**Symptoms**: Status stays "processing" indefinitely
**Cause**:
- Worker crashed during processing
- Job timed out
- Worker not processing jobs
**Fix**: Check worker logs for errors, check job timeout settings

### Issue 4: Frontend Not Updating
**Symptoms**: Status doesn't update even though job completed
**Cause**:
- API not returning updated status
- Frontend polling stopped
- Caching issues
**Fix**: Check API response, clear browser cache, check React Query cache

## Diagnostic Commands

Run the diagnostic script:
```bash
chmod +x CHECK_COMPARISON_STATUS.sh
./CHECK_COMPARISON_STATUS.sh c19bb85e051927b3e0711094e
```

Or check manually:
```bash
# Check API logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api AND textPayload=~\"c19bb85e051927b3e0711094e\"" \
  --limit=50 \
  --project=buildtrace-prod

# Check worker logs
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=100 \
  --project=buildtrace-prod
```

## What the Frontend Does

The `OverlayViewer` component:
1. Extracts `comparison` ID from URL query params
2. Calls `useComparison(comparisonId)` hook
3. Hook polls API every 2 seconds when status is "processing"
4. Displays status: "Processing Comparison" or completed overlay

**The URL is just for navigation - it doesn't control job processing.**
