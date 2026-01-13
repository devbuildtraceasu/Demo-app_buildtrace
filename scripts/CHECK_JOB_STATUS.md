# Checking Job Status and Gemini Block Extraction

## The Job Flow

When you upload 2 drawings, here's what should happen:

1. **API creates drawing preprocessing jobs** → Publishes to Pub/Sub topic `vision`
2. **Worker receives drawing jobs** → Converts PDF to PNG → Creates sheets → Publishes sheet jobs
3. **Worker receives sheet jobs** → **Gemini block extraction happens here** → Saves blocks to database

## Quick Diagnosis

### 1. Check if Drawing Jobs Were Created

The API should have created drawing preprocessing jobs when you uploaded. Check API logs:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
  --limit=50 \
  --project=buildtrace-prod \
  --format=json \
  --freshness=4h \
  | grep -i "drawing\|publish\|job" | head -20
```

### 2. Check Worker is Receiving Messages

The worker should show it's receiving jobs:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=100 \
  --project=buildtrace-prod \
  --format=json \
  --freshness=2h \
  | jq -r '.[] | "\(.timestamp) [\(.severity)] \(.textPayload // .jsonPayload.message // "")"' | head -50
```

### 3. Check Database for Jobs

If you have database access, check if jobs exist:

```sql
-- Check drawing jobs
SELECT id, type, status, target_id, created_at 
FROM jobs 
WHERE type = 'vision.drawing.preprocess' 
ORDER BY created_at DESC 
LIMIT 10;

-- Check sheet jobs (these trigger Gemini block extraction)
SELECT id, type, status, target_id, created_at 
FROM jobs 
WHERE type = 'vision.sheet.preprocess' 
ORDER BY created_at DESC 
LIMIT 10;

-- Check if blocks were created (Gemini extraction result)
SELECT id, sheet_id, type, created_at 
FROM blocks 
ORDER BY created_at DESC 
LIMIT 20;
```

### 4. Check Pub/Sub Subscription

Verify the worker subscription is active and has messages:

```bash
# Check subscription
gcloud pubsub subscriptions describe vision-worker-subscription \
  --project=buildtrace-prod

# Check for undelivered messages
gcloud pubsub subscriptions pull vision-worker-subscription \
  --project=buildtrace-prod \
  --limit=5
```

## What to Look For in Logs

### Drawing Job Processing (Step 2)
```
[job.received] vision.drawing.preprocess msg-xxxxx
[job.started] Drawing job started: drawing_id=xxx
[INFO] Download PDF
[INFO] Convert PDF to PNG
[INFO] Upload sheets
[INFO] Publish sheet jobs
[job.completed] Drawing job completed
```

### Sheet Job Processing - Gemini Block Extraction (Step 3)
```
[job.received] vision.sheet.preprocess msg-xxxxx
[job.started] Sheet job started: sheet_id=xxx
[INFO] Download sheet image
[INFO] Analyze sheet
  [INFO] Segment blocks          ← Gemini 3 Pro identifies all blocks
  [DEBUG] Block 1/8: floor_plan   ← Individual block extraction
  [DEBUG] Block 2/8: legend
  ...
  [INFO] Segment blocks done (45.2s)
  [INFO] Extract title block     ← Gemini 2.5 Flash for title block
  [INFO] Extract title block done (2.1s)
[INFO] Analyze sheet done
[INFO] Upload blocks
[job.completed] Sheet job completed
```

## If No Logs Appear

1. **Check if drawings were actually uploaded** - Verify in the frontend or database
2. **Check API logs** - See if drawing jobs were created and published
3. **Check Pub/Sub** - Verify messages are in the topic
4. **Check worker service** - Ensure it's running and has proper IAM permissions
5. **Check worker subscription** - Ensure it's configured and active

## Common Issues

### Worker Not Receiving Messages
- Check Pub/Sub subscription exists: `vision-worker-subscription`
- Check worker service account has `pubsub.subscriber` role
- Check subscription is attached to correct topic: `vision`

### Jobs Created But Not Processed
- Check worker is running: `gcloud run services describe buildtrace-overlay-worker --region=us-central1`
- Check worker logs for errors
- Check Pub/Sub subscription has messages waiting

### Gemini Block Extraction Not Working
- Check `GEMINI_API_KEY` secret is set on worker service
- Check worker logs for Gemini API errors
- Check worker has `secretmanager.secretAccessor` role
