# Database Schema Validation Guide

## Overview

This document provides a comprehensive guide to all foreign key relationships in the BuildTrace database schema and the validation logic implemented to prevent foreign key constraint violations.

## Database Schema Relationships

### Entity Relationship Diagram

```
Project (1) ──< (N) Drawing
Drawing (1) ──< (N) Sheet
Sheet (1) ──< (N) Block
Block (1) ──< (2) Overlay (block_a_id, block_b_id)
Overlay (1) ──< (N) Change
Job (N) ──< (1) Job (parent_id, self-referential)
Job (N) ──< (1) Overlay (job_id)
```

### Foreign Key Constraints

| Child Table | Foreign Key Field | Parent Table | Constraint Name |
|------------|------------------|--------------|-----------------|
| `drawings` | `project_id` | `projects` | `drawings_project_id_fkey` |
| `sheets` | `drawing_id` | `drawings` | `sheets_drawing_id_fkey` |
| `blocks` | `sheet_id` | `sheets` | `blocks_sheet_id_fkey` |
| `overlays` | `block_a_id` | `blocks` | `overlays_block_a_id_fkey` |
| `overlays` | `block_b_id` | `blocks` | `overlays_block_b_id_fkey` |
| `overlays` | `job_id` | `jobs` | `overlays_job_id_fkey` |
| `changes` | `overlay_id` | `overlays` | `changes_overlay_id_fkey` |
| `jobs` | `parent_id` | `jobs` | `jobs_parent_id_fkey` (self-referential) |

## Validation Implementation

### API Endpoints

#### 1. Create Drawing (`POST /api/drawings`)

**File**: `Overlay-main/api/routes/drawings.py`

**Validation**:
- ✅ Checks if `project_id` exists in `projects` table
- ✅ Checks if project is not soft-deleted (`deleted_at IS NULL`)

**Code**:
```python
if drawing_data.project_id:
    project = session.get(Project, drawing_data.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project not found: {drawing_data.project_id}")
    if project.deleted_at is not None:
        raise HTTPException(status_code=404, detail=f"Project has been deleted: {drawing_data.project_id}")
```

#### 2. Create Comparison (`POST /api/comparisons`)

**File**: `Overlay-main/api/routes/comparisons.py`

**Validation**:
- ✅ Checks if `project_id` exists and is not deleted
- ✅ Checks if `block_a_id` exists in `blocks` table
- ✅ Checks if `block_b_id` exists in `blocks` table
- ✅ Checks if blocks are not soft-deleted
- ✅ Checks if blocks have `uri` (required for overlay generation)

**Code**:
```python
# Project validation
if comparison_data.project_id:
    project = session.get(Project, comparison_data.project_id)
    if not project or project.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Project not found or deleted")

# Block validation
block_a = session.get(Block, block_a_id)
block_b = session.get(Block, block_b_id)
if not block_a or block_a.deleted_at is not None:
    raise HTTPException(status_code=404, detail=f"Block A not found or deleted: {block_a_id}")
if not block_b or block_b.deleted_at is not None:
    raise HTTPException(status_code=404, detail=f"Block B not found or deleted: {block_b_id}")
if not block_a.uri or not block_b.uri:
    raise HTTPException(status_code=400, detail="Blocks missing image URI")
```

#### 3. Create Change (`POST /api/comparisons/{comparison_id}/changes`)

**File**: `Overlay-main/api/routes/comparisons.py`

**Validation**:
- ✅ Checks if `overlay_id` (comparison_id) exists in `overlays` table
- ✅ Checks if overlay is not soft-deleted

**Code**:
```python
overlay = session.get(Overlay, comparison_id)
if not overlay:
    raise HTTPException(status_code=404, detail=f"Comparison (overlay) not found: {comparison_id}")
if overlay.deleted_at is not None:
    raise HTTPException(status_code=404, detail=f"Comparison (overlay) has been deleted: {comparison_id}")
```

#### 4. Submit Manual Alignment (`POST /api/alignment/manual`)

**File**: `Overlay-main/api/routes/alignment.py`

**Validation**:
- ✅ Checks if `overlay_id` exists in `overlays` table
- ✅ Checks if overlay is not soft-deleted

**Code**:
```python
overlay = session.get(Overlay, request.overlay_id)
if not overlay:
    raise HTTPException(status_code=404, detail=f"Overlay not found: {request.overlay_id}")
if overlay.deleted_at is not None:
    raise HTTPException(status_code=404, detail=f"Overlay has been deleted: {request.overlay_id}")
```

### Worker Jobs

#### 1. Drawing Preprocessing (`vision.drawing.preprocess`)

**File**: `Overlay-main/vision/worker/jobs/drawing_preprocess.py`

**Validation**:
- ✅ Checks if `drawing_id` exists in `drawings` table
- ✅ Checks if drawing is not soft-deleted
- ✅ Checks if drawing has `uri` (required for PDF download)

**Code**:
```python
drawing = session.get(Drawing, payload.drawing_id)
if not drawing:
    raise ValueError(f"Drawing {payload.drawing_id} not found")
if drawing.deleted_at is not None:
    raise ValueError(f"Drawing {payload.drawing_id} has been deleted")
if not drawing.uri:
    raise ValueError(f"Drawing {payload.drawing_id} is missing URI")
```

**Note**: Worker creates `Sheet` records with `drawing_id`. The drawing is validated before sheet creation, so foreign key is guaranteed to be valid.

#### 2. Sheet Preprocessing (`vision.sheet.preprocess`)

**File**: `Overlay-main/vision/worker/jobs/sheet_preprocess.py`

**Validation**:
- ✅ Checks if `sheet_id` exists in `sheets` table
- ✅ Checks if sheet is not soft-deleted
- ✅ Checks if sheet has `uri` (required for image download)

**Code**:
```python
sheet = session.get(Sheet, payload.sheet_id)
if not sheet:
    raise ValueError(f"Sheet {payload.sheet_id} not found")
if sheet.deleted_at is not None:
    raise ValueError(f"Sheet {payload.sheet_id} has been deleted")
if not sheet.uri:
    raise ValueError(f"Sheet {payload.sheet_id} is missing URI")
```

**Note**: Worker creates `Block` records with `sheet_id`. The sheet is validated before block creation, so foreign key is guaranteed to be valid.

#### 3. Block Overlay Generation (`vision.block.overlay.generate`)

**File**: `Overlay-main/vision/worker/jobs/block_overlay_generate.py`

**Validation**:
- ✅ Checks if `block_a_id` exists in `blocks` table
- ✅ Checks if `block_b_id` exists in `blocks` table
- ✅ Checks if blocks are not soft-deleted
- ✅ Checks if blocks have `uri` (required for overlay generation)

**Code**:
```python
block_a = session.get(Block, payload.block_a_id)
block_b = session.get(Block, payload.block_b_id)
if not block_a:
    raise ValueError(f"Block A not found: {payload.block_a_id}")
if not block_b:
    raise ValueError(f"Block B not found: {payload.block_b_id}")
if block_a.deleted_at is not None:
    raise ValueError(f"Block A has been deleted: {payload.block_a_id}")
if block_b.deleted_at is not None:
    raise ValueError(f"Block B has been deleted: {payload.block_b_id}")
if not block_a.uri or not block_b.uri:
    raise ValueError(f"Blocks missing image URI")
```

**Note**: Worker creates `Overlay` records with `block_a_id` and `block_b_id`. Blocks are validated before overlay creation, so foreign keys are guaranteed to be valid.

## Soft Delete Pattern

All tables use soft deletes with a `deleted_at` timestamp field:

- `projects.deleted_at`
- `drawings.deleted_at`
- `sheets.deleted_at`
- `blocks.deleted_at`
- `overlays.deleted_at`
- `changes.deleted_at`

**Validation Rule**: Always check `deleted_at IS NULL` when validating foreign key relationships, as soft-deleted records should be treated as non-existent.

## Error Handling

### API Endpoints

- **404 Not Found**: Parent entity doesn't exist or is soft-deleted
- **400 Bad Request**: Required fields missing (e.g., `uri`)

### Worker Jobs

- **ValueError**: Parent entity doesn't exist, is soft-deleted, or missing required fields
- Worker errors are logged and job status is updated to "Failed"

## Testing Checklist

### API Endpoints

- [ ] Create drawing with invalid `project_id` → 404
- [ ] Create drawing with deleted `project_id` → 404
- [ ] Create comparison with invalid `block_a_id` → 404
- [ ] Create comparison with deleted blocks → 404
- [ ] Create comparison with blocks missing `uri` → 400
- [ ] Create change with invalid `overlay_id` → 404
- [ ] Submit alignment with invalid `overlay_id` → 404

### Worker Jobs

- [ ] Drawing preprocessing with invalid `drawing_id` → ValueError
- [ ] Drawing preprocessing with deleted drawing → ValueError
- [ ] Sheet preprocessing with invalid `sheet_id` → ValueError
- [ ] Sheet preprocessing with deleted sheet → ValueError
- [ ] Block overlay with invalid `block_a_id` → ValueError
- [ ] Block overlay with deleted blocks → ValueError

## Common Issues and Solutions

### Issue: Foreign Key Constraint Violation

**Error**: `sqlalchemy.exc.IntegrityError: (psycopg2.errors.ForeignKeyViolation) insert or update on table "X" violates foreign key constraint "X_Y_fkey"`

**Cause**: Code is trying to insert/update a record with a foreign key that doesn't exist in the parent table.

**Solution**:
1. Check if validation is implemented for the endpoint/job
2. Verify the parent entity exists before creating child
3. Check if parent entity is soft-deleted
4. Ensure validation happens before `session.commit()`

### Issue: Missing URI Validation

**Error**: Worker fails when trying to download image/PDF

**Cause**: Entity exists but `uri` field is NULL or empty.

**Solution**: Add `uri` validation in addition to existence checks.

### Issue: Race Condition

**Error**: Validation passes but foreign key violation occurs

**Cause**: Parent entity deleted between validation and commit.

**Solution**: 
- Use database transactions
- Consider using `SELECT FOR UPDATE` for critical validations
- Add retry logic for transient failures

## Best Practices

1. **Always validate before insert**: Check parent exists and is not deleted
2. **Check required fields**: Validate `uri` and other required fields
3. **Use transactions**: Wrap related operations in database transactions
4. **Clear error messages**: Provide specific error details (entity ID, field name)
5. **Log validation failures**: Log when validation fails for debugging
6. **Test edge cases**: Test with deleted entities, missing fields, invalid IDs

## Migration Notes

When adding new foreign key relationships:

1. Add foreign key constraint in database migration
2. Add validation in API endpoint or worker job
3. Test with invalid/deleted parent entities
4. Update this documentation

## Related Files

- API Models: `Overlay-main/api/routes/*.py`
- Worker Models: `Overlay-main/vision/worker/models.py`
- Worker Jobs: `Overlay-main/vision/worker/jobs/*.py`
- Database Schema: `Overlay-main/web/prisma/schema.prisma`
