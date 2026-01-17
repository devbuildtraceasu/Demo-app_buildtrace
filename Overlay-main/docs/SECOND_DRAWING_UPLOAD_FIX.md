# Second Drawing Upload Fix

## Problem
When two drawings are uploaded on the comparison screen, the base (first) drawing progresses well, but the second drawing never processes or shows blocks.

## Root Causes Identified

1. **Shared Mutation Instance**: Both source and target uploads were using the same `createDrawingWithUpload` mutation hook, causing race conditions when both are uploaded quickly.

2. **Query Cache Issues**: The query invalidation might not have been triggering correctly for the second drawing, preventing status polling from starting.

3. **Missing Query Refetch**: The status polling query might not have been starting immediately after the second drawing ID was set.

## Fixes Applied

### 1. Separate Mutation Instances (Frontend)
**File**: `Build-TraceFlow/client/src/pages/project/NewOverlay.tsx`

- Created separate mutation instances for source and target uploads:
  ```typescript
  const createSourceDrawingWithUpload = useCreateDrawingWithUpload();
  const createTargetDrawingWithUpload = useCreateDrawingWithUpload();
  ```

- Updated `handleFileUpload` to use the appropriate mutation based on type:
  ```typescript
  const mutation = type === 'source' ? createSourceDrawingWithUpload : createTargetDrawingWithUpload;
  ```

- Fixed UI loading states to use the correct mutation instance:
  - Source upload: `createSourceDrawingWithUpload.isPending`
  - Target upload: `createTargetDrawingWithUpload.isPending`

### 2. Enhanced Query Invalidation (Frontend)
**File**: `Build-TraceFlow/client/src/pages/project/NewOverlay.tsx`

- Added immediate query invalidation after setting drawing ID
- Added delayed refetch (500ms) to ensure polling starts:
  ```typescript
  queryClient.invalidateQueries({ queryKey: ['drawing', drawing.id, 'status'] });
  setTimeout(() => {
    queryClient.invalidateQueries({ queryKey: ['drawing', drawing.id, 'status'] });
  }, 500);
  ```

### 3. Improved Status Polling (Frontend)
**File**: `Build-TraceFlow/client/src/hooks/use-drawings.ts`

- Added `refetchOnMount: true` to ensure fresh data when component mounts
- Added `refetchOnWindowFocus: true` to refetch when window regains focus
- Added console logging for debugging:
  ```typescript
  queryFn: () => {
    console.log(`[useDrawingStatus] Fetching status for drawing: ${drawingId}`);
    return api.drawings.getStatus(drawingId!);
  }
  ```

### 4. Enhanced Error Handling & Logging (Frontend)
**File**: `Build-TraceFlow/client/src/pages/project/NewOverlay.tsx`

- Added comprehensive logging throughout the upload process:
  ```typescript
  console.log(`[NewOverlay] Starting ${drawingType} drawing upload: ${file.name}`);
  console.log(`[NewOverlay] ${drawingType} drawing created:`, drawing.id);
  console.log(`[NewOverlay] ${drawingType} drawing upload complete, job_id:`, drawing.job_id);
  ```

- Improved error messages to distinguish between source and target upload failures

### 5. Backend Job Refresh (Backend)
**File**: `Overlay-main/api/routes/drawings.py`

- Added `session.refresh(job)` after commit to ensure job is fully loaded before publishing:
  ```python
  session.add(job)
  session.commit()
  session.refresh(job)  # Ensure job is fully loaded before publishing
  ```

## Testing Checklist

- [ ] Upload source drawing - should process and show blocks
- [ ] Upload target drawing immediately after source - should process and show blocks
- [ ] Upload both drawings simultaneously - both should process independently
- [ ] Check browser console for logging messages
- [ ] Verify both drawings show processing status correctly
- [ ] Verify both drawings show blocks when complete

## Expected Behavior After Fix

1. **Source Drawing Upload**:
   - Upload starts → `createSourceDrawingWithUpload.isPending` = true
   - Drawing created → Status polling starts immediately
   - Processing status updates every 2 seconds
   - Blocks appear when complete

2. **Target Drawing Upload**:
   - Upload starts → `createTargetDrawingWithUpload.isPending` = true
   - Drawing created → Status polling starts immediately (independent of source)
   - Processing status updates every 2 seconds
   - Blocks appear when complete

3. **Both Uploads**:
   - Can be uploaded simultaneously without interference
   - Each has its own mutation instance and status polling
   - Both process independently in the background

## Debugging

If the second drawing still doesn't process:

1. **Check Browser Console**:
   - Look for `[NewOverlay]` and `[useDrawingStatus]` log messages
   - Verify both drawing IDs are being set correctly
   - Check for any error messages

2. **Check Network Tab**:
   - Verify both `/api/drawings` POST requests succeed
   - Verify both `/api/drawings/{id}/status` GET requests are being made
   - Check response status codes

3. **Check Backend Logs**:
   - Look for "Publishing preprocessing job" messages for both drawings
   - Verify both jobs are created in the database
   - Check Pub/Sub message IDs

4. **Check Database**:
   ```sql
   SELECT d.id, d.filename, j.id as job_id, j.status, j.type
   FROM drawings d
   LEFT JOIN jobs j ON j.target_id = d.id AND j.type = 'vision.drawing.preprocess'
   ORDER BY d.created_at DESC
   LIMIT 5;
   ```

## Related Files

- `Build-TraceFlow/client/src/pages/project/NewOverlay.tsx` - Main comparison screen
- `Build-TraceFlow/client/src/hooks/use-drawings.ts` - Status polling hook
- `Build-TraceFlow/client/src/hooks/use-upload.ts` - Upload mutation hook
- `Overlay-main/api/routes/drawings.py` - Drawing creation endpoint
