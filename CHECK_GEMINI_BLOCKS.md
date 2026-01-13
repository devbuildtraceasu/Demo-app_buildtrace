# Check Gemini Block Extraction in Worker Logs

## Quick Command

Run this to check worker logs:

```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" \
  --limit=100 \
  --project=buildtrace-prod \
  --format="table(timestamp,severity,textPayload,jsonPayload.message)" \
  --freshness=1h
```

Or use the script:
```bash
chmod +x CHECK_WORKER_LOGS.sh
./CHECK_WORKER_LOGS.sh
```

## What to Look For

### ✅ Successful Gemini Block Extraction

Look for these log messages:

1. **Job Started**:
   ```
   Sheet job started: sheet_id=...
   ```

2. **Block Segmentation** (Gemini 3 Pro):
   ```
   Segment blocks
   Segment blocks done
   ```
   - Uses: `gemini-3-pro-preview`
   - Purpose: Identifies all blocks on the drawing

3. **Title Block Extraction**:
   ```
   Extract title block
   Extract title block done
   ```
   - Uses: `gemini-2.5-flash`
   - Purpose: Extracts sheet number and metadata

4. **Block Extraction** (for each block):
   ```
   Block 1/5: floor_plan
   Block 2/5: legend
   ...
   ```
   - Uses: `gemini-2.5-flash` for each block
   - Purpose: Extracts name, description, identifier, OCR text

5. **Job Completed**:
   ```
   Sheet job completed: sheet_id=...
   ```

### ❌ Error Indicators

Look for these error messages:

1. **Gemini API Errors**:
   ```
   Gemini API error
   GEMINI_API_KEY not found
   ```

2. **Retry Messages**:
   ```
   Gemini API error (attempt 1/5): ...
   Retrying in ...
   ```

3. **Block Extraction Failures**:
   ```
   Failed to extract block
   Error extracting block
   ```

## Gemini Block Extraction Flow

Based on the code in `lib/sheet_analyzer.py`:

### Step 1: Segmentation (Gemini 3 Pro)
- **Model**: `gemini-3-pro-preview`
- **Input**: Full sheet image
- **Output**: List of blocks with bounding boxes
- **Log**: `Segment blocks` phase

### Step 2: Title Block Extraction (Gemini 2.5 Flash)
- **Model**: `gemini-2.5-flash`
- **Input**: Title block crop
- **Output**: Sheet number, project info
- **Log**: `Extract title block` phase

### Step 3: Block-by-Block Extraction (Gemini 2.5 Flash)
For each block:
- **Model**: `gemini-2.5-flash`
- **Input**: Cropped block image
- **Output**: 
  - Name
  - Description
  - Identifier (for VIEW blocks)
  - OCR text (for text blocks)
  - Grid callouts info
- **Log**: `Block X/Y: <block_type>`

### Step 4: Parallel Processing
- Blocks are processed in parallel (max 5 at a time)
- Uses `ThreadPoolExecutor`

## Expected Log Pattern

For 2 drawings uploaded, you should see:

```
[INFO] Sheet job started: sheet_id=xxx, drawing_id=yyy
[INFO] Segment blocks
[DEBUG] Block 1/8: floor_plan
[DEBUG] Block 2/8: legend
[DEBUG] Block 3/8: general_notes
...
[INFO] Segment blocks done (45.2s)
[INFO] Extract title block
[INFO] Extract title block done (2.1s)
[INFO] Sheet job completed: sheet_id=xxx
```

## Check Token Usage

Gemini API usage is tracked. Look for:
- Token usage logs
- Cost tracking
- Model names: `gemini-3-pro-preview`, `gemini-2.5-flash`

## Verify Blocks Were Created

Check the database to see if blocks were created:

```bash
# Connect to database
gcloud sql connect buildtrace-db \
  --user=buildtrace \
  --database=buildtrace \
  --project=buildtrace-prod

# Then in psql:
SELECT COUNT(*) FROM blocks WHERE sheet_id IN (
  SELECT id FROM sheets WHERE drawing_id IN (
    SELECT id FROM drawings ORDER BY created_at DESC LIMIT 2
  )
);
```

## Troubleshooting

### No Gemini Logs
- Check if `GEMINI_API_KEY` is set in Cloud Run service
- Verify secret exists: `gcloud secrets describe gemini-api-key --project=buildtrace-prod`

### Gemini API Errors
- Check API key is valid
- Check quota/rate limits
- Check logs for specific error messages

### Blocks Not Extracted
- Check if segmentation completed
- Check if blocks were saved to database
- Check storage for block images
