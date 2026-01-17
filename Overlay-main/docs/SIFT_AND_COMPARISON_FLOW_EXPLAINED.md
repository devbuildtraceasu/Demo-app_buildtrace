# SIFT Confidence Threshold & Comparison Flow - Detailed Explanation

## 1. SIFT Confidence Threshold (0.3) - Why This Value?

### What is SIFT?
**SIFT (Scale-Invariant Feature Transform)** is a computer vision algorithm used to detect and describe distinctive features in images. In BuildTrace, it's used to align two drawing blocks (old vs new) by finding matching features between them.

### What is Inlier Ratio?
The **inlier ratio** is a measure of how well the SIFT alignment worked:

```
inlier_ratio = inlier_count / total_matches
```

- **Total matches**: Number of SIFT feature matches found between the two images
- **Inliers**: Matches that fit the calculated transformation (after RANSAC filtering)
- **Inlier ratio**: Percentage of matches that are "good" (0.0 to 1.0)

### Why 0.3 (30%)?

The threshold of **0.3** (30%) is set in `block_overlay_generate.py`:

```python
SIFT_CONFIDENCE_THRESHOLD = 0.3
```

**Reasoning:**

1. **Construction drawings are challenging**:
   - Often have repetitive patterns (grid lines, hatches)
   - May have significant changes between versions
   - Can have different scales, rotations, or partial views
   - May include text, annotations, and symbols that don't match

2. **30% is a practical minimum**:
   - **Too high (e.g., 0.7)**: Would reject many valid alignments where drawings have substantial changes
   - **Too low (e.g., 0.1)**: Would accept poor alignments that produce incorrect overlays
   - **0.3 (30%)**: Balances between accepting reasonable alignments while rejecting clearly wrong ones

3. **Fallback strategy**:
   - If SIFT inlier ratio < 0.3, the system tries **Grid alignment** (if grid callouts are available)
   - If Grid also fails, it falls back to the SIFT result anyway (even with low confidence)
   - This ensures we always produce an overlay, even if quality is lower

### How It Works in Code

```python
# Step 1: Try SIFT alignment
aligned_a, aligned_b, stats = sift_align(...)

# Check confidence
if stats.inlier_ratio >= 0.3:  # 30% threshold
    # ✅ Good alignment - use it
    return aligned_a, aligned_b, stats
else:
    # ⚠️ Low confidence - try Grid fallback
    if has_grid_callouts:
        # Try grid-based alignment
        result = align_with_grid(...)
        if result is good:
            return result
    
    # Fallback: Use SIFT result anyway (even with low confidence)
    return aligned_a, aligned_b, stats
```

### Real-World Example

**Scenario**: Comparing two elevation drawings where:
- Old drawing: North elevation with 100 SIFT features
- New drawing: North elevation with 95 SIFT features
- Matches found: 60 feature pairs
- After RANSAC: 25 inliers (matches that fit the transformation)

**Inlier ratio**: 25/60 = **0.42 (42%)**

**Result**: ✅ **PASSES** (0.42 > 0.3) - Alignment is accepted

**If inlier ratio was 0.20 (20%)**:
- ❌ **FAILS** threshold (0.20 < 0.3)
- System tries Grid alignment as fallback
- If Grid fails, uses SIFT result anyway (with warning)

---

## 2. Comparison Flow - Complete Process

The comparison flow is the end-to-end process from user action to displaying the overlay. Here's the detailed breakdown:

### Phase 1: User Initiates Comparison

**Frontend** (`NewOverlay.tsx`):
1. User uploads two drawings (source and target)
2. User selects blocks from each drawing
3. User clicks "Start Comparison"
4. Frontend calls `createComparison.mutateAsync()`

### Phase 2: API Creates Comparison Record

**Backend** (`api/routes/comparisons.py` - `create_comparison()`):

```python
# Step 1: Validate blocks exist
block_a = session.get(Block, block_a_id)  # Source block
block_b = session.get(Block, block_b_id)  # Target block

# Step 2: Create Overlay record in database
overlay = Overlay(
    id=overlay_id,
    block_a_id=block_a_id,
    block_b_id=block_b_id,
)
session.add(overlay)
session.commit()

# Step 3: Create Job record
job = Job(
    id=job_id,
    type="vision.block.overlay.generate",
    status="Queued",
    target_type="overlay",
    target_id=overlay_id,
    payload={"block_a_id": block_a_id, "block_b_id": block_b_id}
)
session.add(job)
session.commit()

# Step 4: Publish job to Pub/Sub
pubsub.publish(topic, job_payload)
```

**Result**: 
- Overlay record created (no URIs yet)
- Job created with status "Queued"
- Job published to Pub/Sub topic

### Phase 3: Vision Worker Picks Up Job

**Worker** (`vision/worker/main.py`):

1. **Message received** from Pub/Sub subscription
2. **Job runner** routes to `run_block_overlay_generate_job()`
3. **Job status** updated: "Queued" → "Started"

### Phase 4: Overlay Generation Process

**Worker** (`vision/worker/jobs/block_overlay_generate.py`):

#### 4.1 Download Block Images
```python
img_a_bytes = download_block_image(block_a.uri)  # Old drawing
img_b_bytes = download_block_image(block_b.uri)  # New drawing
```

#### 4.2 Align Blocks (SIFT + Grid Strategy)

**Step 2a: Try SIFT Alignment**
```python
aligned_a, aligned_b, stats = sift_align(
    img_a, img_b,
    n_features=1000,           # Extract 1000 SIFT features
    ratio_threshold=0.75,      # Lowe's ratio test
    ransac_threshold=15.0,     # 15 pixel reprojection error
    scale_min=0.3, scale_max=3.0,
    rotation_deg_min=-30, rotation_deg_max=30
)

# Check confidence
if stats.inlier_ratio >= 0.3:
    # ✅ Use SIFT result
    alignment_method = "sift"
else:
    # ⚠️ Low confidence - try Grid
```

**Step 2b: Try Grid Alignment (if SIFT confidence < 0.3)**
```python
if has_grid_callouts:
    aligned_a, aligned_b, stats = align_with_grid(
        img_a, img_b,
        path_a, path_b
    )
    # Grid uses Gemini API to detect grid callouts
    # Then matches grid lines between images
    alignment_method = "grid"
```

#### 4.3 Generate Overlay Images

After alignment, generate three output images:

```python
# 1. Overlay: Both images overlaid (old in red, new in green)
overlay_bytes = generate_overlay_image(aligned_a, aligned_b)

# 2. Addition: What's new (only in new drawing)
addition_bytes = generate_addition_image(aligned_a, aligned_b)

# 3. Deletion: What's removed (only in old drawing)
deletion_bytes = generate_deletion_image(aligned_a, aligned_b)

# Calculate quality score
overlay_score = stats.inlier_ratio  # For SIFT
# or grid match quality for Grid
```

#### 4.4 Upload to Storage

```python
overlay_uri = upload_to_storage(overlay_bytes, f"{overlay_id}/overlay.png")
addition_uri = upload_to_storage(addition_bytes, f"{overlay_id}/addition.png")
deletion_uri = upload_to_storage(deletion_bytes, f"{overlay_id}/deletion.png")
```

#### 4.5 Update Database

```python
overlay.uri = overlay_uri
overlay.addition_uri = addition_uri
overlay.deletion_uri = deletion_uri
overlay.score = overlay_score  # Quality score (0.0 to 1.0)
job.status = "Completed"
session.commit()
```

### Phase 5: Frontend Polls for Completion

**Frontend** (`OverlayViewer.tsx`):

```typescript
// Poll comparison status every 2 seconds
const { data: comparison } = useQuery({
  queryKey: ['comparison', comparisonId],
  queryFn: () => api.comparisons.get(comparisonId),
  refetchInterval: 2000  // Poll every 2 seconds
})

// Check if overlay is ready
if (comparison?.uri && comparison?.addition_uri && comparison?.deletion_uri) {
  // ✅ Overlay complete - display it
  showOverlayViewer(comparison)
} else {
  // ⏳ Still processing - show loading spinner
  showProcessingSpinner()
}
```

### Complete Flow Diagram

```
User Action
    ↓
[Frontend] Create Comparison Request
    ↓
[API] POST /api/comparisons
    ├─ Validate blocks exist
    ├─ Create Overlay record (no URIs)
    ├─ Create Job record (status: Queued)
    └─ Publish to Pub/Sub
    ↓
[Pub/Sub] Message in queue
    ↓
[Worker] Receive message
    ├─ Update job status: Queued → Started
    ├─ Download block images
    ├─ Align blocks (SIFT → Grid fallback)
    ├─ Generate overlay images
    ├─ Upload to storage
    └─ Update database (URIs + score)
    ↓
[Database] Overlay record updated
    ├─ overlay.uri = "s3://..."
    ├─ overlay.addition_uri = "s3://..."
    ├─ overlay.deletion_uri = "s3://..."
    └─ overlay.score = 0.42
    ↓
[Frontend] Polls GET /api/comparisons/{id}
    ├─ Checks if URIs exist
    └─ Displays overlay when ready
```

### Key Points

1. **Asynchronous Processing**: Comparison is async - API returns immediately, worker processes in background
2. **Job Tracking**: Job status ("Queued" → "Started" → "Completed") tracks progress
3. **Fallback Strategy**: SIFT → Grid → Low-confidence SIFT ensures we always produce a result
4. **Quality Score**: `overlay.score` (0.0-1.0) indicates alignment quality
5. **Polling**: Frontend polls every 2 seconds until overlay is ready

### Error Handling

- **SIFT fails completely**: Try Grid alignment
- **Grid fails**: Use SIFT result anyway (with low confidence warning)
- **Both fail**: Job status = "Failed", overlay URIs remain null
- **Storage upload fails**: Job status = "Failed", retry possible

---

## Summary

**SIFT Confidence Threshold (0.3)**:
- Measures alignment quality (inlier ratio = good matches / total matches)
- 30% is a practical minimum for construction drawings with changes
- Triggers Grid fallback if below threshold
- Ensures we always produce an overlay, even if quality is lower

**Comparison Flow**:
- User action → API creates records → Pub/Sub → Worker processes → Storage upload → Database update → Frontend displays
- Fully asynchronous with job tracking
- Multiple alignment strategies (SIFT + Grid) for robustness
- Frontend polls until completion
