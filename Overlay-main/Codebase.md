# Overlay Codebase Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Code Flow](#code-flow)
4. [Key Components](#key-components)
5. [Job Types and Pipeline](#job-types-and-pipeline)
6. [Data Models](#data-models)
7. [External Services & Clients](#external-services--clients)
8. [Configuration](#configuration)
9. [Development Setup](#development-setup)

---

## Project Overview

**Overlay** is a vision worker system designed for drawing comparison and overlay generation. It processes architectural/engineering drawings (PDFs), extracts individual sheets, segments them into blocks, and generates visual overlays to compare different versions of drawings.

### Core Functionality
- **PDF Processing**: Converts PDF drawings into individual sheet images
- **Sheet Analysis**: Analyzes sheets using AI (Gemini) to extract blocks, metadata, and text
- **Block Segmentation**: Identifies and extracts different types of blocks (plans, elevations, sections, details, legends, etc.)
- **Overlay Generation**: Creates visual overlays comparing blocks from different drawing versions
- **Change Detection**: Identifies additions, deletions, and modifications between drawing versions
- **Clash Detection**: Detects spatial conflicts in drawings

---

## Architecture

### High-Level Architecture

```
┌─────────────────┐
│   Web App       │  (Creates jobs, manages projects)
└────────┬────────┘
         │
         │ Publishes to Pub/Sub
         ▼
┌─────────────────┐
│  Pub/Sub Topic  │  (vision topic)
└────────┬────────┘
         │
         │ Subscribes
         ▼
┌─────────────────┐
│ Vision Worker   │  (main.py - Job Runner)
│                 │
│  ┌───────────┐  │
│  │ Job       │  │
│  │ Registry  │  │
│  └─────┬─────┘  │
│        │       │
│        ▼       │
│  ┌───────────┐ │
│  │ Job       │ │
│  │ Handlers  │ │
│  └─────┬─────┘ │
│        │       │
└────────┼───────┘
         │
    ┌────┴────┐
    │        │
    ▼         ▼
┌────────┐ ┌──────────┐
│  DB    │ │ Storage  │
│(Postgres)│ │(S3/GCS) │
└────────┘ └──────────┘
```

### Component Structure

```
vision/worker/
├── main.py              # Entry point - Pub/Sub subscriber
├── config.py            # Configuration management
├── models.py            # SQLModel data models
├── jobs/                # Job handlers
│   ├── registry.py     # Job type registry
│   ├── runner.py       # Job execution engine
│   ├── envelope.py     # Job message envelope
│   ├── types.py        # Job type constants
│   ├── job_lifecycle.py # Job status management
│   ├── drawing_preprocess.py
│   ├── sheet_preprocess.py
│   ├── drawing_overlay_generate.py
│   ├── sheet_overlay_generate.py
│   ├── block_overlay_generate.py
│   ├── change_detect.py
│   └── clash_detect.py
├── clients/             # External service clients
│   ├── db.py           # Database connection
│   ├── pubsub.py       # Pub/Sub messaging
│   ├── storage.py      # Cloud storage (S3/GCS)
│   └── gemini.py       # Gemini AI client
├── lib/                # Core libraries
│   ├── pdf_converter.py
│   ├── sheet_analyzer.py
│   ├── sift_alignment.py
│   ├── grid_alignment.py
│   ├── overlay_render.py
│   ├── ocr.py
│   └── identifier_extractor.py
└── utils/              # Utility functions
    ├── job_events.py
    ├── log_utils.py
    └── storage_utils.py
```

---

## Code Flow

### 1. Worker Startup (`main.py`)

**Flow:**
1. **Initialization**
   - Configure logging
   - Register signal handlers (SIGINT, SIGTERM) for graceful shutdown
   - Load configuration from environment variables

2. **Connection Validation**
   - Validate database connectivity (PostgreSQL)
   - Validate Pub/Sub connectivity
   - Retry with exponential backoff on failure

3. **Pub/Sub Subscription**
   - Create `JobRunner` instance
   - Subscribe to `vision.worker` subscription
   - Configure flow control (max concurrent messages, memory limits)
   - Start subscription in background thread

4. **Message Processing**
   - For each message:
     - Extract trace context
     - Parse JSON payload
     - Create `JobEnvelope`
     - Look up job handler in registry
     - Execute handler with database session
     - ACK on success, NACK on transient errors

### 2. Job Processing Pipeline

#### Phase 1: Drawing Preprocessing (`drawing_preprocess.py`)

**Purpose**: Convert PDF drawing into individual sheet images

**Flow:**
```
1. Receive job message with drawing_id
2. Load Drawing from database
3. Download PDF from storage
4. Validate PDF format
5. Convert PDF pages to PNG images (300 DPI)
6. Upload each page as a Sheet image
7. Create Sheet records in database
8. Create Sheet preprocessing jobs
9. Publish sheet jobs to Pub/Sub
10. Mark drawing job as completed
```

**Key Functions:**
- `_download_pdf()`: Downloads PDF from storage
- `_validate_pdf_bytes()`: Validates PDF header
- `convert_pdf_bytes_to_png_bytes()`: Converts PDF to PNG (uses pdf2image)
- `_upsert_sheets()`: Creates/updates Sheet records
- `_create_sheet_jobs()`: Creates child jobs for sheet processing

#### Phase 2: Sheet Preprocessing (`sheet_preprocess.py`)

**Purpose**: Analyze sheet to extract blocks and metadata

**Flow:**
```
1. Receive job message with sheet_id
2. Load Sheet from database
3. Download sheet PNG from storage
4. Analyze sheet using Gemini AI:
   - Segment into blocks
   - Extract metadata (title block, sheet number, discipline)
   - Extract OCR text
   - Identify block types
5. Soft-delete existing blocks for this sheet
6. Upload block images to storage
7. Create Block records in database
8. Update Sheet metadata
9. Mark sheet job as completed
```

**Key Functions:**
- `analyze_sheet()`: Uses Gemini to analyze sheet structure
- `_upload_block_image()`: Uploads cropped block images
- `_map_block_type()`: Maps AI-detected types to BlockType enum
- `_apply_sheet_metadata()`: Updates sheet with extracted metadata

#### Phase 3: Overlay Generation

**Three levels of overlay generation:**

##### 3a. Drawing Overlay (`drawing_overlay_generate.py`)

**Purpose**: Match sheets between two drawings and create sheet overlay jobs

**Flow:**
```
1. Receive job with drawing_a_id and drawing_b_id
2. Load both drawings and their sheets
3. Pair sheets using multiple strategies:
   a. By normalized sheet_number (primary)
   b. By title (fallback)
   c. By discipline + order (fallback)
4. For each matched pair:
   - Check if sheet overlay job already exists
   - Create SheetOverlayGenerate job
   - Publish to Pub/Sub
5. Track pairing statistics
6. Mark job as completed
```

**Pairing Strategies:**
- **Sheet Number**: Normalized (lowercase, stripped) matching
- **Title**: Lowercase title matching
- **Discipline**: Group by discipline, then match by order
- **Order Fallback**: Match by index if no other method works

##### 3b. Sheet Overlay (`sheet_overlay_generate.py`)

**Purpose**: Match blocks between two sheets and create block overlay jobs

**Flow:**
```
1. Receive job with sheet_a_id and sheet_b_id
2. Load both sheets and their blocks
3. Filter to VIEW blocks only (Plan, Elevation, Section, Detail)
4. Pair blocks using multiple strategies:
   a. By identifier (from metadata)
   b. By normalized name (from metadata)
   c. By text signature (OCR/description)
   d. By bounds signature (size/aspect ratio)
   e. By order (fallback)
5. For each matched pair:
   - Check if block overlay job already exists
   - Create BlockOverlayGenerate job
   - Publish to Pub/Sub
6. Track pairing statistics
7. Mark job as completed
```

**Block Pairing Strategies:**
- **Identifier**: Exact match on `metadata.identifier` (e.g., "A1", "101")
- **Name**: Normalized `metadata.name` matching
- **Text Signature**: Normalized OCR/description text
- **Bounds Signature**: Size and aspect ratio compatibility
- **Order Fallback**: Match by spatial position (top-to-bottom, left-to-right)

##### 3c. Block Overlay (`block_overlay_generate.py`)

**Purpose**: Generate visual overlay image comparing two blocks

**Flow:**
```
1. Receive job with block_a_id and block_b_id
2. Load both blocks from database
3. Download block images from storage
4. Select alignment method:
   - Grid-based (if block has grid callouts)
   - SIFT-based (default)
5. Align images:
   - Grid: Extract grid lines using Gemini, align
   - SIFT: Feature detection and matching
6. Generate overlay image (merge mode):
   - Aligned block A (old) in red tint
   - Aligned block B (new) in green tint
   - Overlap shows as yellow
7. Generate addition/deletion images:
   - Addition: Green areas (new content)
   - Deletion: Red areas (removed content)
8. Upload overlay images to storage
9. Calculate alignment score (inlier ratio)
10. Create/update Overlay record
11. Mark job as completed
```

**Alignment Methods:**
- **Grid Alignment**: Uses Gemini to detect grid lines, aligns based on grid intersections
- **SIFT Alignment**: Feature-based alignment using SIFT keypoints and RANSAC

**Overlay Rendering:**
- **Merge Mode**: Red (old) + Green (new) = Yellow (overlap)
- **Addition Image**: Green areas (new content)
- **Deletion Image**: Red areas (removed content)

#### Phase 4: Change Detection (`change_detect.py`)

**Purpose**: Analyze overlay to detect specific changes using LLM

**Flow:**
```
1. Receive job with overlay_id
2. Load Overlay and associated blocks
3. Download overlay images
4. Use OpenAI GPT-5.1 to analyze changes:
   - Identify additions
   - Identify deletions
   - Identify modifications
   - Extract structured change data
5. Update Overlay.changes array
6. Mark job as completed
```

#### Phase 5: Clash Detection (`clash_detect.py`)

**Purpose**: Detect spatial conflicts in drawings

**Flow:**
```
1. Receive job with overlay_id
2. Load Overlay and associated blocks
3. Analyze overlay for clashes
4. Update Overlay.clashes array
5. Mark job as completed
```

---

## Key Components

### Job System

#### Job Registry (`jobs/registry.py`)

Central registry mapping job types to handlers:

```python
JOB_SPECS = {
    JobType.DRAWING_PREPROCESS: JobSpec(...),
    JobType.SHEET_PREPROCESS: JobSpec(...),
    JobType.DRAWING_OVERLAY_GENERATE: JobSpec(...),
    JobType.SHEET_OVERLAY_GENERATE: JobSpec(...),
    JobType.BLOCK_OVERLAY_GENERATE: JobSpec(...),
    JobType.OVERLAY_CHANGE_DETECT: JobSpec(...),
    JobType.OVERLAY_CLASH_DETECT: JobSpec(...),
}
```

Each `JobSpec` contains:
- `job_type`: String identifier
- `payload_model`: Pydantic model for validation
- `handler`: Function to execute
- `log_context`: Function to extract logging context

#### Job Runner (`jobs/runner.py`)

**Responsibilities:**
- Parse incoming Pub/Sub messages
- Create `JobEnvelope` from message data
- Look up job handler in registry
- Validate payload against Pydantic model
- Execute handler with database session
- Handle errors (permanent vs transient)

#### Job Envelope (`jobs/envelope.py`)

Standardized job message format:
```python
{
    "type": "vision.drawing.preprocess",
    "jobId": "clx123...",
    "payload": {
        "drawingId": "clx456..."
    }
}
```

#### Job Lifecycle (`jobs/job_lifecycle.py`)

Manages job status transitions:
- `QUEUED` → `STARTED` → `COMPLETED` / `FAILED`
- Tracks job events (created, started, completed, failed)
- Handles cancellation

### Data Models (`models.py`)

#### Core Entities

**Drawing**
- Represents uploaded PDF file
- Fields: `id`, `project_id`, `filename`, `name`, `uri`, `created_at`, `updated_at`, `deleted_at`

**Sheet**
- Individual page extracted from drawing
- Fields: `id`, `drawing_id`, `index`, `uri`, `title`, `sheet_number`, `discipline`, `metadata_`

**Block**
- Segmented region on a sheet
- Fields: `id`, `sheet_id`, `type` (BlockType enum), `uri`, `bounds`, `ocr`, `description`, `metadata_`

**Overlay**
- Comparison result between two blocks
- Fields: `id`, `block_a_id`, `block_b_id`, `uri`, `addition_uri`, `deletion_uri`, `score`, `summary`, `changes`, `clashes`

**Job**
- Background processing job
- Fields: `id`, `type`, `status`, `target_type`, `target_id`, `payload`, `events`, `parent_id`

#### Block Types

Enum of supported block types:
- `PLAN`, `ELEVATION`, `SECTION`, `DETAIL`
- `LEGEND`, `KEYNOTE`, `SCHEDULE`
- `TITLE_BLOCK`, `REVISION_HISTORY`
- `GENERAL_NOTES`, `KEY_NOTES`, `SHEET_NOTES`
- And more...

### External Service Clients

#### Database Client (`clients/db.py`)

**Features:**
- SQLModel-based ORM
- Connection pooling (10 base, 20 overflow)
- Connection health checks (pool_pre_ping)
- Session management via context manager

**Usage:**
```python
with get_session() as session:
    drawing = session.get(Drawing, drawing_id)
```

#### Pub/Sub Client (`clients/pubsub.py`)

**Features:**
- Publish messages to topics
- Subscribe to subscriptions (streaming pull)
- Flow control (max messages, max bytes)
- Trace context propagation

**Usage:**
```python
client = get_pubsub_client()
client.publish("vision", message_dict, attributes={"type": "job.type"})
```

#### Storage Client (`clients/storage.py`)

**Features:**
- Supports both S3 (MinIO) and GCS
- Upload/download files and bytes
- File existence checks
- Singleton pattern

**Usage:**
```python
client = get_storage_client()
uri = client.upload_from_bytes(png_bytes, "sheets/123/sheet_0.png", "image/png")
data = client.download_to_bytes("sheets/123/sheet_0.png")
```

#### Gemini Client (`clients/gemini.py`)

**Features:**
- Google Gemini API integration
- Vision model for image analysis
- Vertex AI support (production)
- API key support (development)

### Core Libraries

#### PDF Converter (`lib/pdf_converter.py`)

Converts PDF bytes to PNG images:
- Uses `pdf2image` library
- Configurable DPI (default 300)
- Returns indexed pages dictionary

#### Sheet Analyzer (`lib/sheet_analyzer.py`)

Analyzes sheet images using Gemini:
- Segments into blocks
- Extracts metadata (title block, sheet number, discipline)
- Performs OCR
- Identifies block types

#### Alignment Libraries

**SIFT Alignment (`lib/sift_alignment.py`)**
- Feature detection using SIFT
- Feature matching with Lowe's ratio test
- RANSAC for robust transformation estimation
- Configurable parameters (n_features, ratio_threshold, RANSAC params)

**Grid Alignment (`lib/grid_alignment.py`)**
- Uses Gemini to detect grid lines
- Aligns based on grid intersections
- Falls back to SIFT if insufficient grid lines

#### Overlay Renderer (`lib/overlay_render.py`)

Generates overlay images:
- Merge mode: Red (old) + Green (new) = Yellow (overlap)
- Addition image: Green areas (new content)
- Deletion image: Red areas (removed content)
- Configurable DPI (default 100 for overlays)

---

## Job Types and Pipeline

### Job Type Constants (`jobs/types.py`)

```python
class JobType:
    DRAWING_PREPROCESS = "vision.drawing.preprocess"
    SHEET_PREPROCESS = "vision.sheet.preprocess"
    DRAWING_OVERLAY_GENERATE = "vision.drawing.overlay.generate"
    SHEET_OVERLAY_GENERATE = "vision.sheet.overlay.generate"
    BLOCK_OVERLAY_GENERATE = "vision.block.overlay.generate"
    OVERLAY_CHANGE_DETECT = "vision.overlay.change.detect"
    OVERLAY_CLASH_DETECT = "vision.overlay.clash.detect"
```

### Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Drawing Preprocess                                        │
│    PDF → Sheets (PNG images)                                 │
│    Creates: Sheet records + Sheet Preprocess jobs            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Sheet Preprocess (for each sheet)                        │
│    Sheet PNG → Blocks (segmented images)                    │
│    Creates: Block records                                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Drawing Overlay Generate                                  │
│    Match sheets between Drawing A and Drawing B             │
│    Creates: Sheet Overlay Generate jobs                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Sheet Overlay Generate (for each matched sheet pair)    │
│    Match blocks between Sheet A and Sheet B                 │
│    Creates: Block Overlay Generate jobs                    │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Block Overlay Generate (for each matched block pair)   │
│    Align blocks → Generate overlay images                   │
│    Creates: Overlay record                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. Overlay Change Detect (optional)                         │
│    Analyze overlay → Extract structured changes              │
│    Updates: Overlay.changes                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. Overlay Clash Detect (optional)                           │
│    Analyze overlay → Detect spatial conflicts               │
│    Updates: Overlay.clashes                                 │
└─────────────────────────────────────────────────────────────┘
```

### Job Fanout Pattern

Jobs can create child jobs:
- **Drawing Preprocess** → Creates multiple **Sheet Preprocess** jobs
- **Drawing Overlay Generate** → Creates multiple **Sheet Overlay Generate** jobs
- **Sheet Overlay Generate** → Creates multiple **Block Overlay Generate** jobs

**Deduplication:**
- Checks for existing jobs before creating new ones
- Prevents duplicate processing on retries

---

## Data Models

### Entity Relationships

```
Project
  └── Drawing (1:N)
        └── Sheet (1:N)
              └── Block (1:N)
                    ├── Overlay (N:1) ──┐
                    └── Overlay (N:1) ──┘
                          (block_a_id, block_b_id)

Job
  ├── parent_id (self-reference)
  └── target_type/target_id (polymorphic)
```

### Key Fields

**Drawing**
- `uri`: Storage URI of PDF file (s3:// or gs://)

**Sheet**
- `index`: Page number in PDF (0-based)
- `sheet_number`: Extracted sheet number (e.g., "A-101")
- `discipline`: Discipline code (e.g., "A" for Architecture)
- `metadata_`: JSON with title block data

**Block**
- `type`: BlockType enum
- `bounds`: JSON with `{xmin, ymin, xmax, ymax, normalized}`
- `ocr`: Extracted text from block
- `description`: AI-generated description
- `metadata_`: JSON with `{name, identifier, has_grid_callouts, ...}`

**Overlay**
- `uri`: Overlay image (merge mode)
- `addition_uri`: Addition image (green)
- `deletion_uri`: Deletion image (red)
- `score`: Alignment confidence score (0.0-1.0)
- `summary`: JSON with alignment stats
- `changes`: Array of change objects (from change detection)
- `clashes`: Array of clash objects (from clash detection)

**Job**
- `type`: Job type string
- `status`: JobStatus enum (QUEUED, STARTED, COMPLETED, FAILED, CANCELED)
- `target_type`: Entity type ("drawing", "sheet", "block", "overlay")
- `target_id`: Entity ID
- `payload`: JSON payload (job-specific)
- `events`: Array of job event objects
- `parent_id`: Parent job ID (for fanout jobs)

---

## External Services & Clients

### PostgreSQL Database

**Purpose**: Persistent storage for all entities

**Connection:**
- Host, port, database, user, password from config
- Connection pooling (10 base, 20 overflow)
- Health checks enabled

**Schema Management:**
- Managed via Prisma (in `web/prisma/`)
- SQLModel models in `models.py`

### Google Cloud Pub/Sub

**Purpose**: Asynchronous job queue

**Configuration:**
- Project ID
- Topic: `vision`
- Subscription: `vision.worker`

**Flow Control:**
- Max concurrent messages: 3 (default)
- Max memory: 500MB (default)
- Max lease duration: 1800s (30 minutes)

**Local Development:**
- Uses Pub/Sub Emulator (port 8681)
- Configured via `PUBSUB_EMULATOR_HOST`

### Cloud Storage

**Purpose**: Store PDFs, sheet images, block images, overlay images

**Backends:**
- **S3/MinIO**: Local development
  - Endpoint: `http://localhost:9000`
  - Access key/secret key authentication
- **GCS**: Production
  - Uses Google Cloud credentials
  - Service account JSON file

**Storage Paths:**
- PDFs: `drawings/{drawing_id}/drawing.pdf`
- Sheets: `sheets/{drawing_id}/sheet_{index}.png`
- Blocks: `blocks/{sheet_id}/block_{index}_{type}.png`
- Overlays: `overlays/{overlay_id}/overlay.png`

### Google Gemini AI

**Purpose**: Sheet analysis, block segmentation, grid detection

**Models:**
- Gemini Pro Vision (for image analysis)
- Vertex AI (production) or API key (development)

**Usage:**
- Sheet analysis: Segment sheets into blocks
- Grid detection: Extract grid lines for alignment
- OCR: Extract text from blocks

### OpenAI

**Purpose**: Change detection analysis

**Models:**
- GPT-5.1 (default) for change analysis
- GPT-5-mini for OCR and identifier extraction

**Usage:**
- Analyze overlay images to extract structured change data

---

## Configuration

### Configuration File (`config.py`)

Uses Pydantic Settings for environment variable management.

### Key Configuration Options

#### Database
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

#### Storage
- `STORAGE_BACKEND`: `"s3"` or `"gcs"`
- `STORAGE_BUCKET`: Bucket name
- S3: `STORAGE_ENDPOINT`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_REGION`
- GCS: `GOOGLE_APPLICATION_CREDENTIALS` (path to service account JSON)

#### Pub/Sub
- `PUBSUB_PROJECT_ID`: GCP project ID
- `VISION_TOPIC`: Topic name (default: "vision")
- `VISION_SUBSCRIPTION`: Subscription name (default: "vision.worker")
- `PUBSUB_EMULATOR_HOST`: For local development

#### AI Services
- `GEMINI_API_KEY`: Gemini API key (optional, if not using Vertex AI)
- `VERTEX_AI_PROJECT`: GCP project for Vertex AI
- `OPENAI_API_KEY`: OpenAI API key
- `OPENAI_MODEL`: Model name (default: "gpt-5.1")

#### Processing
- `PDF_CONVERSION_DPI`: DPI for PDF→PNG (default: 300)
- `OVERLAY_OUTPUT_DPI`: DPI for overlay images (default: 100)

#### Worker
- `WORKER_MAX_CONCURRENT_MESSAGES`: Max concurrent jobs (default: 3)
- `WORKER_MAX_MEMORY_BYTES`: Max memory for in-flight messages (default: 500MB)
- `WORKER_MAX_LEASE_DURATION_SECONDS`: Max job duration (default: 1800s)
- `WORKER_LOG_LEVEL`: Logging level (default: "INFO")

#### SIFT Alignment
- `SIFT_N_FEATURES`: Max SIFT features (default: 1000)
- `SIFT_EXCLUDE_MARGIN`: Edge exclusion ratio (default: 0.2)
- `SIFT_RATIO_THRESHOLD`: Lowe's ratio test (default: 0.75)

#### RANSAC
- `RANSAC_REPROJ_THRESHOLD`: Reprojection threshold in pixels (default: 15.0)
- `RANSAC_MAX_ITERS`: Max iterations (default: 5000)
- `RANSAC_CONFIDENCE`: Confidence level (default: 0.95)

#### Transform Constraints
- `TRANSFORM_SCALE_MIN/MAX`: Allowed scale range (default: 0.3-3.0)
- `TRANSFORM_ROTATION_DEG_MIN/MAX`: Allowed rotation range (default: ±30°)

#### Overlay Filtering
- `OVERLAY_INTENSITY_THRESHOLD`: Minimum intensity difference for real changes (default: 40)

---

## Development Setup

### Prerequisites
- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Node.js 22+ (for Prisma migrations)
- Docker and Docker Compose

### Local Infrastructure

Start services:
```bash
docker compose up -d db pubsub-emulator storage
```

Services:
- **PostgreSQL**: Port 5432
- **Pub/Sub Emulator**: Port 8681
- **MinIO**: Port 9000 (API), 9001 (Console)

### Database Setup

```bash
cd web
npm install
cp .env.example .env
npm run migrate
```

### Worker Setup

```bash
cd vision/worker
cp .env.example .env
# Edit .env with your API keys
uv sync
```

### Run Worker

```bash
cd vision/worker
uv run python main.py
```

Or with Docker:
```bash
docker compose up vision-worker
```

### Testing

```bash
cd vision/worker
uv run pytest tests/ -v
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
```

---

## Key Design Patterns

### 1. Singleton Pattern
- Database engine (`clients/db.py`)
- Pub/Sub client (`clients/pubsub.py`)
- Storage client (`clients/storage.py`)

### 2. Registry Pattern
- Job registry (`jobs/registry.py`) maps job types to handlers

### 3. Factory Pattern
- Storage client factory (`clients/storage.py`) creates S3 or GCS client based on config

### 4. Strategy Pattern
- Alignment methods (Grid vs SIFT)
- Block pairing strategies (identifier, name, text, bounds, order)
- Sheet pairing strategies (number, title, discipline, order)

### 5. Fanout Pattern
- Jobs create child jobs (drawing → sheets → blocks)

### 6. Retry Pattern
- Connection retries with exponential backoff
- Pub/Sub message retries (NACK on transient errors)

---

## Error Handling

### Job Errors

**Permanent Errors:**
- Invalid payload
- Missing entities
- Unsupported job types
- **Action**: ACK message (don't retry)

**Transient Errors:**
- Network failures
- Temporary service unavailability
- **Action**: NACK message (retry)

**Error Detection:**
- `utils/job_errors.py` contains `is_permanent_job_error()` function

### Job Status Management

- **QUEUED**: Job created, not started
- **STARTED**: Job execution began
- **COMPLETED**: Job finished successfully
- **FAILED**: Job failed (permanent or transient)
- **CANCELED**: Job canceled before/during execution

### Logging

Structured logging with context:
- Job IDs
- Entity IDs (drawing_id, sheet_id, block_id)
- Trace context (for distributed tracing)
- Phase tracking
- Performance metrics (duration, size)

---

## Performance Considerations

### Memory Management
- Flow control limits in-flight messages
- Image processing uses temporary files
- Garbage collection after large operations

### Concurrency
- Default: 3 concurrent messages
- Configurable via `WORKER_MAX_CONCURRENT_MESSAGES`
- Pub/Sub handles message distribution

### Storage Optimization
- Overlay images at lower DPI (100 vs 300 for sheets)
- Temporary files cleaned up after processing

### Database
- Connection pooling (10 base, 20 overflow)
- Health checks prevent stale connections
- Batch operations where possible

---

## Future Improvements

See `vision/worker/docs/overlay-improvements.md` for planned enhancements:
- Fuzzy OCR/description similarity
- Store pairing metadata on Overlay records
- Persist alignment metadata
- Retry alignment with relaxed params
- Add publish batching/limits
- Add maximum overlays per sheet/drawing
- Track parent job completion based on child status
- Add structured metrics for alignment time + memory
- Unit and integration tests

---

## Summary

The Overlay codebase is a sophisticated vision processing pipeline that:

1. **Processes PDFs** into sheets and blocks
2. **Analyzes content** using AI (Gemini, OpenAI)
3. **Matches entities** using multiple strategies (identifier, name, text, bounds, order)
4. **Generates overlays** using advanced alignment (Grid/SIFT)
5. **Detects changes** and clashes using LLM analysis
6. **Manages jobs** asynchronously via Pub/Sub with proper error handling

The architecture is modular, extensible, and designed for scalability with proper separation of concerns between job handlers, clients, and core libraries.

