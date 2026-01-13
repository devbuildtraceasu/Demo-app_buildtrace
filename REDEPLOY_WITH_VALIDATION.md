# Redeploy API with Foreign Key Validation Fixes

## Summary

All foreign key validation fixes have been implemented. The API needs to be redeployed for the fixes to take effect.

## What Was Fixed

### API Endpoints
1. ✅ `POST /api/drawings` - Validates `project_id` exists and not deleted
2. ✅ `POST /api/comparisons` - Validates `project_id`, `block_a_id`, `block_b_id` exist, not deleted, and have URIs
3. ✅ `POST /api/comparisons/{id}/changes` - Validates `overlay_id` exists and not deleted
4. ✅ `POST /api/alignment/manual` - Validates `overlay_id` exists and not deleted

### Worker Jobs
1. ✅ `vision.drawing.preprocess` - Validates `drawing_id` exists, not deleted, and has URI
2. ✅ `vision.sheet.preprocess` - Validates `sheet_id` exists, not deleted, and has URI
3. ✅ `vision.block.overlay.generate` - Validates `block_a_id` and `block_b_id` exist, not deleted, and have URIs

## Deployment Steps

### 1. Redeploy API Service

```bash
cd Overlay-main/infra
./REDEPLOY_API.sh
```

This will:
- Build the API Docker image with validation fixes
- Push to Artifact Registry
- Deploy to Cloud Run

### 2. Redeploy Worker Service (Optional but Recommended)

```bash
cd Overlay-main/infra
./BUILD_AND_PUSH.sh
```

Then update the Cloud Run worker service to use the new image.

## Expected Behavior After Deployment

### Before Fix (Current - from logs):
```
ERROR: sqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) 
insert or update on table "drawings" violates foreign key constraint "drawings_project_id_fkey"
```

### After Fix:
```
HTTP 404: Project not found: {project_id}. Please create the project first.
```

## Testing After Deployment

### Test Case 1: Invalid Project ID
```bash
curl -X POST https://your-api-url/api/drawings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "project_id": "invalid-project-id",
    "filename": "test.pdf",
    "uri": "gs://bucket/test.pdf"
  }'
```

**Expected**: `404 - Project not found: invalid-project-id. Please create the project first.`

### Test Case 2: Valid Project ID
```bash
curl -X POST https://your-api-url/api/drawings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "project_id": "valid-project-id",
    "filename": "test.pdf",
    "uri": "gs://bucket/test.pdf"
  }'
```

**Expected**: `201 Created` with drawing response

### Test Case 3: Missing Project ID
```bash
curl -X POST https://your-api-url/api/drawings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "filename": "test.pdf",
    "uri": "gs://bucket/test.pdf"
  }'
```

**Expected**: `400 - project_id is required`

## Verification

After deployment, check API logs:

```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" \
  --limit=50 \
  --format="table(timestamp,severity,textPayload)" \
  --freshness=1h
```

You should see:
- ✅ Clear 404 errors instead of 500 database errors
- ✅ Helpful error messages with entity IDs
- ✅ No more `ForeignKeyViolation` errors

## Rollback Plan

If issues occur after deployment:

1. **Revert to previous image**:
   ```bash
   gcloud run services update buildtrace-api \
     --region us-central1 \
     --image gcr.io/PROJECT_ID/buildtrace-api:PREVIOUS_TAG
   ```

2. **Or redeploy previous version**:
   ```bash
   git checkout PREVIOUS_COMMIT
   cd Overlay-main/infra
   ./REDEPLOY_API.sh
   ```

## Related Documentation

- `DATABASE_SCHEMA_VALIDATION.md` - Complete validation guide
- `SCHEMA_VALIDATION_SUMMARY.md` - Quick reference
- `FIX_FOREIGN_KEY_ERROR.md` - Original error analysis
