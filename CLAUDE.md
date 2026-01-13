# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BuildTrace is a full-stack application for architectural drawing comparison and overlay analysis. It processes PDF drawings, extracts individual sheets and blocks, then generates visual overlays to compare different drawing versions.

**Two Main Components:**
- **Build-TraceFlow/** - Frontend (React + Vite + Express)
- **Overlay-main/** - Backend API and vision worker services

## Common Development Commands

### Frontend (Build-TraceFlow/)

```bash
cd Build-TraceFlow
npm install
npm run dev          # Development server (port 5000)
npm run build        # Production build to dist/public/
npm start            # Serve production build
npm run check        # TypeScript type checking
```

### Backend Worker (Overlay-main/vision/worker/)

```bash
cd Overlay-main/vision/worker
uv sync              # Install dependencies with uv package manager
uv run python main.py  # Run the worker

# Testing
uv run pytest tests/ -v                  # All tests
uv run pytest tests/unit/ -v             # Unit tests only
uv run pytest tests/integration/ -v      # Integration tests only
uv run pytest tests/ -v -n auto          # Parallel execution
```

### Database (Overlay-main/web/)

```bash
cd Overlay-main/web
npm install
npm run migrate        # Create/apply Prisma migrations
npm run generate       # Generate Prisma client
npm run studio         # Open Prisma Studio GUI
npm run migrate:deploy # Deploy migrations (production)
npm run reset          # Reset database (development)
```

### Local Infrastructure

```bash
# Start all infrastructure services
docker compose up -d db pubsub-emulator storage

# Start everything including worker
docker compose up

# View logs
docker compose logs -f vision-worker

# Stop services
docker compose down
```

## Architecture Overview

### Frontend Architecture (Build-TraceFlow/)

**Stack**: React 19.2 + Vite 7.1.9 + Express + Wouter routing

**Important**: This is NOT a Next.js application. It's a React SPA with two deployment modes:

1. **Development** (`NODE_ENV !== "production"`):
   - Express server runs Vite dev server in middleware mode
   - HMR enabled
   - Replit plugins loaded only when `REPL_ID` environment variable is set
   - Code: `server/vite.ts` sets up Vite middleware

2. **Production** (`NODE_ENV === "production"`):
   - Static files pre-built to `dist/public/`
   - Served via nginx on Cloud Run (port 8080)
   - No Replit plugins
   - Code: `server/static.ts` serves static files

**Key Files:**
- `vite.config.ts` - Vite configuration, conditionally loads Replit plugins
- `server/index.ts` - Main server entry, routes to dev/prod setup
- `server/vite.ts` - Vite dev server setup (development only)
- `server/static.ts` - Static file serving (production only)

### Backend Architecture (Overlay-main/)

**Async Job Processing Pipeline:**

```
Web App → Pub/Sub Topic → Vision Worker → Database + Storage
```

**Worker Job Types** (in processing order):

1. **DrawingPreprocess** (`vision.drawing.preprocess`)
   - Converts PDF to PNG sheets (300 DPI)
   - Creates Sheet records
   - Spawns SheetPreprocess jobs

2. **SheetPreprocess** (`vision.sheet.preprocess`)
   - Analyzes sheet with Gemini AI
   - Segments into blocks
   - Extracts metadata (title block, sheet number, discipline)
   - Creates Block records

3. **DrawingOverlayGenerate** (`vision.drawing.overlay.generate`)
   - Matches sheets between two drawings
   - Pairing strategies: sheet number → title → discipline + order
   - Spawns SheetOverlayGenerate jobs

4. **SheetOverlayGenerate** (`vision.sheet.overlay.generate`)
   - Matches blocks between two sheets (VIEW blocks only)
   - Pairing strategies: identifier → name → text signature → bounds → order
   - Spawns BlockOverlayGenerate jobs

5. **BlockOverlayGenerate** (`vision.block.overlay.generate`)
   - Aligns blocks (Grid or SIFT method)
   - Generates overlay images (merge, addition, deletion)
   - Creates Overlay records

6. **OverlayChangeDetect** (`vision.overlay.change.detect`)
   - Uses OpenAI GPT-5.1 to analyze changes
   - Extracts structured change data

7. **OverlayClas hDetect** (`vision.overlay.clash.detect`)
   - Detects spatial conflicts

**Key Components:**

- **Job Registry** (`jobs/registry.py`): Maps job types to handlers
- **Job Runner** (`jobs/runner.py`): Executes jobs, handles errors
- **Job Envelope** (`jobs/envelope.py`): Standardized message format
- **Clients** (`clients/`): Database (SQLModel), Pub/Sub, Storage (S3/GCS), Gemini AI
- **Core Libraries** (`lib/`):
  - `pdf_converter.py` - PDF to PNG conversion
  - `sheet_analyzer.py` - Gemini-based sheet analysis
  - `sift_alignment.py` - Feature-based image alignment
  - `grid_alignment.py` - Grid-based alignment (uses Gemini for grid detection)
  - `overlay_render.py` - Overlay image generation
  - `ocr.py` - Text extraction
  - `identifier_extractor.py` - Extract block identifiers

### Data Models (Overlay-main/vision/worker/models.py)

**Entity Relationships:**
```
Project → Drawing (1:N) → Sheet (1:N) → Block (1:N)
                                           ↓
                                        Overlay (compares two blocks)
```

**Key Models:**
- `Drawing` - Uploaded PDF file (`uri` points to storage)
- `Sheet` - Individual page extracted from drawing (`index`, `sheet_number`, `discipline`, `metadata_`)
- `Block` - Segmented region on sheet (`type`, `bounds`, `ocr`, `description`, `metadata_`)
- `Overlay` - Comparison result (`block_a_id`, `block_b_id`, `uri`, `addition_uri`, `deletion_uri`, `score`, `changes`, `clashes`)
- `Job` - Background processing job (`type`, `status`, `target_type`, `target_id`, `payload`, `events`, `parent_id`)

**Block Types Enum:** PLAN, ELEVATION, SECTION, DETAIL, LEGEND, KEYNOTE, SCHEDULE, TITLE_BLOCK, REVISION_HISTORY, etc.

## Development Workflow Patterns

### Worker Job Development Pattern

When creating or modifying job handlers:

1. **Job Definition** - Add to `jobs/registry.py`:
   ```python
   JOB_SPECS = {
       JobType.YOUR_JOB: JobSpec(
           job_type=JobType.YOUR_JOB,
           payload_model=YourPayloadModel,
           handler=handle_your_job,
           log_context=lambda p: {"entity_id": p.entity_id}
       )
   }
   ```

2. **Handler Implementation** - Create in `jobs/your_job.py`:
   - Download resources from storage
   - Process data
   - Upload results to storage
   - Update database records
   - Create child jobs if needed (fanout pattern)
   - Mark job as completed

3. **Child Job Creation** - Always check for duplicates:
   ```python
   existing_job = session.exec(
       select(Job).where(
           Job.type == JobType.CHILD_JOB,
           Job.target_id == target_id,
           Job.status.in_([JobStatus.QUEUED, JobStatus.STARTED])
       )
   ).first()

   if existing_job:
       return  # Skip, job already exists
   ```

4. **Publishing Jobs** - Use Pub/Sub client:
   ```python
   from clients.pubsub import get_pubsub_client

   client = get_pubsub_client()
   client.publish(
       config.VISION_TOPIC,
       message_dict,
       attributes={"type": job_type}
   )
   ```

### Alignment Method Selection

The worker automatically selects alignment method based on block metadata:

- **Grid Alignment**: If `block.metadata_.get("has_grid_callouts") == True`
  - Uses Gemini to detect grid lines
  - Aligns based on grid intersections
  - Falls back to SIFT if insufficient grid lines

- **SIFT Alignment**: Default method
  - Feature detection using SIFT algorithm
  - Feature matching with Lowe's ratio test
  - RANSAC for robust transformation estimation
  - Configurable via environment variables (SIFT_*, RANSAC_*, TRANSFORM_*)

### Error Handling in Jobs

The worker distinguishes between permanent and transient errors:

**Permanent Errors** (ACK message, don't retry):
- Invalid payload format
- Missing required entities in database
- Unsupported job types
- Validation failures

**Transient Errors** (NACK message, retry):
- Network failures
- Temporary service unavailability
- Rate limiting
- Storage timeouts

Job handlers should raise appropriate exceptions; the runner handles ACK/NACK logic.

### Storage Paths Convention

When uploading files to storage, follow these path conventions:

- PDFs: `drawings/{drawing_id}/drawing.pdf`
- Sheets: `sheets/{drawing_id}/sheet_{index}.png`
- Blocks: `blocks/{sheet_id}/block_{index}_{type}.png`
- Overlays: `overlays/{overlay_id}/overlay.png`
- Additions: `overlays/{overlay_id}/addition.png`
- Deletions: `overlays/{overlay_id}/deletion.png`

The storage client automatically handles bucket name and backend (S3/GCS) based on configuration.

## Environment Configuration

### Worker Environment Variables (Overlay-main/vision/worker/.env)

**Required:**
- `GEMINI_API_KEY` - Google Gemini API key (for sheet analysis)
- `OPENAI_API_KEY` - OpenAI API key (for change detection)

**Database:**
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

**Storage:**
- `STORAGE_BACKEND` - "s3" (MinIO/AWS) or "gcs" (Google Cloud)
- `STORAGE_BUCKET` - Bucket name
- For S3: `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_REGION`
- For GCS: `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON)

**Pub/Sub:**
- `PUBSUB_PROJECT_ID` - GCP project ID
- `VISION_TOPIC` - Topic name (default: "vision")
- `VISION_SUBSCRIPTION` - Subscription name (default: "vision.worker")
- `PUBSUB_EMULATOR_HOST` - For local development (e.g., "localhost:8681")

**Processing Configuration:**
- `PDF_CONVERSION_DPI` - DPI for PDF→PNG (default: 300)
- `OVERLAY_OUTPUT_DPI` - DPI for overlay images (default: 100)
- `WORKER_MAX_CONCURRENT_MESSAGES` - Max concurrent jobs (default: 3)

**Alignment Tuning:**
- `SIFT_N_FEATURES` - Max SIFT features (default: 1000)
- `SIFT_RATIO_THRESHOLD` - Lowe's ratio test (default: 0.75)
- `RANSAC_REPROJ_THRESHOLD` - Reprojection threshold in pixels (default: 15.0)
- `TRANSFORM_SCALE_MIN`, `TRANSFORM_SCALE_MAX` - Allowed scale range (default: 0.3-3.0)
- `TRANSFORM_ROTATION_DEG_MIN`, `TRANSFORM_ROTATION_DEG_MAX` - Allowed rotation (default: ±30°)

## Testing Strategy

### Worker Tests (Overlay-main/vision/worker/tests/)

**Structure:**
- `tests/unit/` - Unit tests for individual functions/modules
- `tests/integration/` - Integration tests with external services
- `tests/contract/` - Contract tests for API/message formats
- `conftest.py` - Shared pytest fixtures

**Key Test Fixtures** (from conftest.py):
- `db_session` - Test database session
- `mock_storage_client` - Mock storage client
- `mock_pubsub_client` - Mock Pub/Sub client
- `sample_drawing`, `sample_sheet`, `sample_block` - Sample entities

**Running Specific Tests:**
```bash
# Single test file
uv run pytest tests/unit/test_sift_alignment.py -v

# Single test function
uv run pytest tests/unit/test_sift_alignment.py::test_align_images -v

# Tests matching pattern
uv run pytest tests/ -k "alignment" -v
```

## Deployment

### Local Development Deployment

See `Overlay-main/QUICKSTART.md` for detailed setup instructions.

**Quick Start:**
```bash
# Start infrastructure
docker compose up -d db pubsub-emulator storage

# Setup database
cd Overlay-main/web && npm install && npm run migrate

# Setup and run worker
cd ../vision/worker
cp .env.example .env  # Edit with API keys
uv sync
uv run python main.py

# Run frontend (separate terminal)
cd ../../../Build-TraceFlow
npm install && npm run dev
```

### Production Deployment (Google Cloud)

See `DEPLOYMENT_STATUS.md` and `Overlay-main/infra/DEPLOYMENT_COMPLETE.md` for full details.

**Deployment Scripts** (in `Overlay-main/infra/`):

```bash
# Build and push Docker images
./BUILD_AND_PUSH.sh

# Deploy frontend to Cloud Run
./DEPLOY_FRONTEND.sh

# Run database migrations on Cloud SQL
./run-migrations.sh
```

**Live Services:**
- Frontend: https://buildtrace-frontend-okidmickfa-uc.a.run.app
- API: https://buildtrace-api-okidmickfa-uc.a.run.app
- Worker: Internal Cloud Run service (not publicly accessible)

**View Logs:**
```bash
# API logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-api" --limit=50 --project=buildtrace-prod

# Worker logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=buildtrace-overlay-worker" --limit=50 --project=buildtrace-prod
```

## Key Design Patterns Used

### Singleton Pattern
- Database engine (`clients/db.py`)
- Pub/Sub client (`clients/pubsub.py`)
- Storage client (`clients/storage.py`)

### Registry Pattern
- Job registry (`jobs/registry.py`) maps job types to handlers

### Factory Pattern
- Storage client factory creates S3 or GCS client based on config

### Strategy Pattern
- Alignment methods (Grid vs SIFT)
- Block pairing strategies (identifier → name → text → bounds → order)
- Sheet pairing strategies (number → title → discipline → order)

### Fanout Pattern
- Jobs create child jobs (Drawing → Sheets → Blocks)
- Deduplication prevents duplicate processing on retries

### Retry Pattern
- Connection retries with exponential backoff
- Pub/Sub message retries (NACK on transient errors)

## Important Gotchas

### Frontend Gotchas

1. **Not Next.js**: This is a React SPA with Vite, not Next.js. Don't use Next.js patterns.

2. **Replit Plugins**: Only loaded in development when `REPL_ID` is set. Don't reference them in production code.

3. **API Proxy**: Development uses Vite proxy to localhost:8000. Production uses direct `VITE_API_URL`.

4. **Build Output**: Production build goes to `dist/public/`, not `dist/` directly.

### Worker Gotchas

1. **Job Deduplication**: Always check for existing jobs before creating new ones to prevent duplicate processing.

2. **Storage URIs**: Use storage client methods to get proper URIs. Don't construct URIs manually.

3. **Database Sessions**: Use `with get_session() as session:` context manager. Don't create sessions manually.

4. **Soft Deletes**: Blocks use soft delete (`deleted_at` timestamp). Always filter out soft-deleted records.

5. **Child Job Timing**: Create child jobs AFTER committing parent job data to database to ensure consistency.

6. **Alignment Failures**: Block overlay generation can fail if alignment score is too low. This is expected behavior.

7. **Metadata Field Name**: It's `metadata_` (with underscore) in SQLModel to avoid conflicts with SQLAlchemy.

8. **Connection Pooling**: Database connection pool is limited (10 base, 20 overflow). Don't hold sessions open unnecessarily.

## Additional Documentation

- **Codebase Details**: `Overlay-main/Codebase.md` - Comprehensive architecture documentation
- **Quick Start**: `Overlay-main/QUICKSTART.md` - Step-by-step setup guide
- **Frontend Architecture**: `Build-TraceFlow/ARCHITECTURE.md` - Frontend deployment paths
- **Deployment Guide**: `Overlay-main/infra/DEPLOYMENT_COMPLETE.md` - Production deployment
- **Deployment Status**: `DEPLOYMENT_STATUS.md` - Current deployment state
- **Future Improvements**: `Overlay-main/vision/worker/docs/overlay-improvements.md` - Planned enhancements
