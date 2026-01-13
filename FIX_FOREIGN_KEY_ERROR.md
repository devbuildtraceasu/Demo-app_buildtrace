# Fix: Foreign Key Constraint Violation

## Problem

**Error**: `sqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) insert or update on table "drawings" violates foreign key constraint "drawings_project_id_fkey"`

**Location**: `/app/api/routes/drawings.py`, line 125 in `create_drawing`

**Cause**: The API is trying to create a drawing with a `project_id` that doesn't exist in the `projects` table.

## Root Cause

The `create_drawing` endpoint was not validating that the project exists before attempting to create a drawing. When the frontend sends a `project_id` that:
- Doesn't exist in the database
- Was deleted (soft delete)
- Is invalid

The database foreign key constraint prevents the insert, causing a 500 error instead of a clear 404 error.

## Fix Applied

### 1. Added Project Validation in `create_drawing`

**File**: `Overlay-main/api/routes/drawings.py`

**Changes**:
- Added validation to check if project exists before creating drawing
- Returns clear 404 error with helpful message if project not found
- Checks for soft-deleted projects

```python
# Validate that project exists before creating drawing
if drawing_data.project_id:
    project = session.get(Project, drawing_data.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found: {drawing_data.project_id}. Please create the project first.",
        )
    if project.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project has been deleted: {drawing_data.project_id}",
        )
```

### 2. Added Project Validation in `create_comparison`

**File**: `Overlay-main/api/routes/comparisons.py`

**Changes**:
- Added same validation for comparison creation
- Prevents foreign key violations when creating comparisons

## Impact

### Before Fix:
- ❌ Database constraint violation → 500 Internal Server Error
- ❌ Unclear error message
- ❌ Frontend can't handle gracefully

### After Fix:
- ✅ Clear 404 error with helpful message
- ✅ Frontend can show user-friendly error
- ✅ Prevents invalid data from being inserted

## Why This Happens

This error typically occurs when:

1. **Frontend sends wrong project_id**:
   - Project was deleted
   - Project ID is from a different organization
   - Project ID is malformed

2. **Race condition**:
   - Project deleted between frontend load and drawing creation
   - Project creation failed but frontend didn't detect it

3. **Data inconsistency**:
   - Project exists in frontend cache but not in database
   - Database was reset but frontend still has old IDs

## Testing

### Test Case 1: Valid Project
```bash
# Should succeed
POST /api/drawings
{
  "project_id": "valid-project-id",
  "filename": "test.pdf",
  "uri": "gs://bucket/test.pdf"
}
```

### Test Case 2: Invalid Project ID
```bash
# Should return 404
POST /api/drawings
{
  "project_id": "non-existent-id",
  "filename": "test.pdf",
  "uri": "gs://bucket/test.pdf"
}
# Response: 404 - "Project not found: non-existent-id. Please create the project first."
```

### Test Case 3: Deleted Project
```bash
# Should return 404
POST /api/drawings
{
  "project_id": "deleted-project-id",
  "filename": "test.pdf",
  "uri": "gs://bucket/test.pdf"
}
# Response: 404 - "Project has been deleted: deleted-project-id"
```

## Frontend Impact

The frontend should now receive clear error messages instead of generic 500 errors. Update frontend error handling to:

1. **Check for 404 errors** on drawing creation
2. **Show user-friendly message**: "Project not found. Please select a valid project."
3. **Redirect to project selection** if project is invalid

## Next Steps

1. **Redeploy API** with the fix:
   ```bash
   cd Overlay-main/infra
   ./REDEPLOY_API.sh
   ```

2. **Test drawing creation** with:
   - Valid project ID
   - Invalid project ID
   - Deleted project ID

3. **Update frontend** (if needed) to handle 404 errors gracefully

4. **Check existing data**:
   - Verify all drawings have valid project_ids
   - Check for orphaned drawings (drawings with non-existent projects)

## Related Issues

This same pattern should be applied to other endpoints that reference foreign keys:
- ✅ `create_drawing` - Fixed
- ✅ `create_comparison` - Fixed
- ⚠️ Other endpoints may need similar validation

## Files Changed

1. `Overlay-main/api/routes/drawings.py` - Added project validation
2. `Overlay-main/api/routes/comparisons.py` - Added project validation
