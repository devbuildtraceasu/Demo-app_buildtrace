# Quick Start Guide - How to Run Overlay

This guide will help you get the Overlay system up and running quickly.

## Prerequisites

Before you begin, ensure you have:

- **Python 3.12+** installed
- **[uv](https://github.com/astral-sh/uv)** package manager installed
  ```bash
  # Install uv (macOS/Linux)
  curl -LsSf https://astral.sh/uv/install.sh | sh
  
  # Or with Homebrew
  brew install uv
  ```
- **Node.js 22+** installed (for Prisma migrations)
- **Docker and Docker Compose** installed
- **API Keys**:
  - Google Gemini API key (for sheet analysis)
  - OpenAI API key (for change detection)

---

## Option 1: Quick Start with Docker (Recommended)

This is the fastest way to get everything running.

### Step 1: Start Infrastructure Services

```bash
# From the project root
docker compose up -d db pubsub-emulator storage
```

This starts:
- **PostgreSQL** database on port `5432`
- **Pub/Sub Emulator** on port `8681`
- **MinIO** (S3-compatible storage) on ports `9000` (API) and `9001` (console)

Wait a few seconds for services to be healthy. Check status:
```bash
docker compose ps
```

### Step 2: Setup Database Schema

```bash
cd web
npm install
npm run migrate
```

This creates all necessary database tables.

### Step 3: Configure Environment Variables

Create a `.env` file in `vision/worker/`:

```bash
cd ../vision/worker
cat > .env << 'EOF'
# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=overlay_dev
DB_USER=overlay
DB_PASSWORD=overlay_dev_password

# Pub/Sub Configuration
PUBSUB_EMULATOR_HOST=localhost:8681
PUBSUB_PROJECT_ID=local-dev
VISION_TOPIC=vision
VISION_SUBSCRIPTION=vision.worker

# Storage Configuration (MinIO for local dev)
STORAGE_BACKEND=s3
STORAGE_ENDPOINT=http://localhost:9000
STORAGE_ACCESS_KEY=minio
STORAGE_SECRET_KEY=minio123
STORAGE_BUCKET=overlay-uploads
STORAGE_REGION=us-east-1

# AI Services (REQUIRED - Add your keys)
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Worker Configuration
WORKER_MAX_CONCURRENT_MESSAGES=3
WORKER_LOG_LEVEL=INFO
EOF
```

**Important**: Replace `your_gemini_api_key_here` and `your_openai_api_key_here` with your actual API keys.

### Step 4: Install Dependencies

```bash
# Still in vision/worker directory
uv sync
```

### Step 5: Run the Worker

```bash
uv run python main.py
```

You should see output like:
```
[worker.starting] Starting vision worker...
[worker.config] db=localhost:5432/overlay_dev storage=s3 pubsub=local-dev/vision.worker
[connection.established] db=localhost:5432/overlay_dev
[connection.established] pubsub=local-dev/vision.worker
[worker.ready] Worker is ready and listening for jobs...
```

The worker is now running and listening for jobs!

---

## Option 2: Run Everything with Docker Compose

If you prefer to run the worker in Docker as well:

### Step 1: Create Environment File

```bash
# From project root
cd vision/worker
cat > .env << 'EOF'
# Database
DB_HOST=db
DB_PORT=5432
DB_NAME=overlay_dev
DB_USER=overlay
DB_PASSWORD=overlay_dev_password

# Pub/Sub
PUBSUB_EMULATOR_HOST=pubsub-emulator:8681
PUBSUB_PROJECT_ID=local-dev
VISION_TOPIC=vision
VISION_SUBSCRIPTION=vision.worker

# Storage
STORAGE_BACKEND=s3
STORAGE_ENDPOINT=http://storage:9000
STORAGE_ACCESS_KEY=minio
STORAGE_SECRET_KEY=minio123
STORAGE_BUCKET=overlay-uploads
STORAGE_REGION=us-east-1

# AI Services (REQUIRED)
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
EOF
```

### Step 2: Start All Services

```bash
# From project root
docker compose up
```

This starts all services including the worker. You'll see logs from all containers.

---

## Option 3: Manual Setup (For Development)

If you want more control over the setup:

### Step 1: Start Infrastructure

```bash
docker compose up -d db pubsub-emulator storage
```

### Step 2: Setup Database

```bash
cd web
npm install

# Create .env file for Prisma
cat > .env << 'EOF'
DATABASE_URL="postgresql://overlay:overlay_dev_password@localhost:5432/overlay_dev"
EOF

npm run migrate
```

### Step 3: Setup Python Environment

```bash
cd ../vision/worker
uv sync
```

### Step 4: Configure Worker

Create `.env` file (see Option 1, Step 3 for contents).

### Step 5: Run Worker

```bash
uv run python main.py
```

---

## Verifying the Setup

### Check Database

```bash
# Connect to PostgreSQL
docker exec -it overlay_postgres psql -U overlay -d overlay_dev

# List tables
\dt

# Exit
\q
```

### Check Pub/Sub

The Pub/Sub emulator should be running on port 8681. You can verify by checking Docker:
```bash
docker compose ps pubsub-emulator
```

### Check Storage (MinIO)

1. Open browser to `http://localhost:9001`
2. Login with:
   - Username: `minio`
   - Password: `minio123`
3. You should see the `overlay-uploads` bucket

### Check Worker Logs

The worker should be logging messages. Look for:
- `[worker.ready]` - Worker is ready
- `[connection.established]` - Connections successful
- No error messages

---

## Testing the System

### Run Unit Tests

```bash
cd vision/worker
uv run pytest tests/unit/ -v
```

### Run Integration Tests

```bash
uv run pytest tests/integration/ -v
```

### Run All Tests

```bash
uv run pytest tests/ -v
```

---

## Sending a Test Job

To test the system, you need to publish a job message to Pub/Sub. Here's a Python script to do that:

```python
# test_job.py
import json
from google.cloud import pubsub_v1

publisher = pubsub_v1.PublisherClient()
project_id = "local-dev"
topic_name = "vision"

topic_path = publisher.topic_path(project_id, topic_name)

# Example: Drawing preprocessing job
message = {
    "type": "vision.drawing.preprocess",
    "jobId": "test-job-123",
    "payload": {
        "drawingId": "your-drawing-id-here"
    }
}

data = json.dumps(message).encode("utf-8")
future = publisher.publish(topic_path, data, type="vision.drawing.preprocess")
print(f"Published message ID: {future.result()}")
```

Run with:
```bash
# Set environment variable for Pub/Sub emulator
export PUBSUB_EMULATOR_HOST=localhost:8681

# Run the script
python test_job.py
```

---

## Troubleshooting

### Database Connection Failed

**Error**: `[db.connection.failed]`

**Solutions**:
1. Check if PostgreSQL is running: `docker compose ps db`
2. Verify connection details in `.env`
3. Check if database exists: `docker exec -it overlay_postgres psql -U overlay -l`

### Pub/Sub Connection Failed

**Error**: `[pubsub.connection.failed]`

**Solutions**:
1. Check if Pub/Sub emulator is running: `docker compose ps pubsub-emulator`
2. Verify `PUBSUB_EMULATOR_HOST` in `.env`
3. Check if topic/subscription exists (they should be auto-created)

### Storage Connection Failed

**Error**: Storage upload/download failures

**Solutions**:
1. Check if MinIO is running: `docker compose ps storage`
2. Verify MinIO credentials in `.env`
3. Check MinIO console at `http://localhost:9001`
4. Verify bucket exists: `overlay-uploads`

### Missing API Keys

**Error**: `GEMINI_API_KEY` or `OPENAI_API_KEY` not set

**Solutions**:
1. Get API keys:
   - Gemini: https://makersuite.google.com/app/apikey
   - OpenAI: https://platform.openai.com/api-keys
2. Add them to `vision/worker/.env`

### Worker Not Receiving Messages

**Solutions**:
1. Check worker logs for subscription errors
2. Verify message format matches expected envelope
3. Check Pub/Sub subscription exists
4. Verify message attributes include `type` field

### Port Already in Use

**Error**: Port 5432, 8681, 9000, or 9001 already in use

**Solutions**:
1. Stop conflicting services
2. Or change ports in `docker-compose.yml`:
   ```yaml
   ports:
     - "5433:5432"  # Change host port
   ```

---

## Next Steps

Once the system is running:

1. **Read the Documentation**: See `Codebase.md` for detailed architecture and code flow
2. **Explore Jobs**: Check `vision/worker/jobs/` to understand job handlers
3. **Review Models**: See `vision/worker/models.py` for data structures
4. **Check Logs**: Monitor worker logs for job processing
5. **Test Workflows**: Create test drawings and process them through the pipeline

---

## Stopping the System

### Stop All Services

```bash
docker compose down
```

### Stop Only Infrastructure (Keep Worker Running)

```bash
docker compose stop db pubsub-emulator storage
```

### Remove All Data (Clean Slate)

```bash
docker compose down -v
```

This removes all volumes (database data, storage data).

---

## Production Deployment

For production, you'll need to:

1. **Use Real Services**:
   - Replace Pub/Sub emulator with Google Cloud Pub/Sub
   - Replace MinIO with Google Cloud Storage or AWS S3
   - Use production PostgreSQL database

2. **Update Configuration**:
   - Set `STORAGE_BACKEND=gcs` for Google Cloud Storage
   - Configure `VERTEX_AI_PROJECT` for Vertex AI
   - Set proper `PUBSUB_PROJECT_ID`

3. **Security**:
   - Use service account credentials
   - Store secrets securely (not in `.env`)
   - Enable authentication/authorization

4. **Scaling**:
   - Run multiple worker instances
   - Adjust `WORKER_MAX_CONCURRENT_MESSAGES`
   - Monitor resource usage

---

## Getting Help

- Check `Codebase.md` for detailed documentation
- Review `vision/worker/docs/overlay-improvements.md` for planned features
- Check worker logs for error messages
- Review test files in `vision/worker/tests/` for usage examples

