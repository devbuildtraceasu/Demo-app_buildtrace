# Overlay

Drawing comparison and overlay generation pipeline.

## Project Structure

```
overlay/
├── vision/
│   └── worker/
│       ├── main.py             # Worker entrypoint
│       ├── config.py           # Configuration
│       ├── models.py           # SQLModel data models
│       ├── jobs/               # Job handlers
│       ├── clients/            # External service clients
│       ├── lib/                # Core libraries
│       ├── utils/              # Utility functions
│       └── tests/              # Test suites
├── web/
│   ├── prisma/
│   │   └── schema.prisma       # Database schema
│   ├── package.json            # Prisma dependencies
│   └── prisma.config.ts        # Prisma configuration
└── docker-compose.yml          # Local development services
```

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager
- Node.js 22+ (for Prisma migrations)
- Docker and Docker Compose

## Local Development Setup

### 1. Start Infrastructure Services

```bash
docker compose up -d db pubsub-emulator storage
```

This starts:
- **PostgreSQL** on port 5432
- **Pub/Sub Emulator** on port 8681
- **MinIO** (S3-compatible storage) on ports 9000 (API) and 9001 (console)

### 2. Setup Database Schema

```bash
cd web
npm install
cp .env.example .env
npm run migrate
```

### 3. Configure Worker Environment

```bash
cd vision/worker
cp .env.example .env
# Edit .env with your API keys (GEMINI_API_KEY)
```

### 4. Install Worker Dependencies

```bash
cd vision/worker
uv sync
```

### 5. Run the Worker

```bash
cd vision/worker
uv run python main.py
```

Or run everything with Docker:

```bash
docker compose up
```

## Running Tests

```bash
cd vision/worker

# Run all tests
uv run pytest tests/ -v

# Run tests in parallel
uv run pytest tests/ -v -n auto

# Run specific test suite
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v
```

## Database

The database schema is managed with Prisma in `web/prisma/schema.prisma`.

**Models:**
- `Project` - Drawing projects
- `Drawing` - Uploaded PDF drawings
- `Sheet` - Individual sheets extracted from drawings
- `Block` - Segmented blocks on sheets
- `Overlay` - Block-to-block comparison results
- `Job` - Background processing jobs

**Commands:**
```bash
cd web
npm run migrate        # Create/apply migrations
npm run generate       # Generate Prisma client
npm run studio         # Open Prisma Studio GUI
```

## Environment Variables

See `vision/worker/.env.example` for all configuration options.

| Variable | Description |
|----------|-------------|
| `DB_HOST`, `DB_PORT`, etc. | PostgreSQL connection |
| `STORAGE_BACKEND` | `s3` (MinIO/AWS) or `gcs` (Google Cloud) |
| `PUBSUB_EMULATOR_HOST` | Pub/Sub emulator address (local dev) |
| `GEMINI_API_KEY` | Google Gemini API key |
# Demo-app_buildtrace
