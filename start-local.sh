#!/bin/bash
# ============================================
# BuildTrace - Local Development Startup Script
# ============================================
# This script starts all services for local development
# NO CLOUD DEPENDENCIES - Everything runs locally

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}  BuildTrace - Local Development Setup${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OVERLAY_DIR="$PROJECT_ROOT/Overlay-main"
FRONTEND_DIR="$PROJECT_ROOT/Build-TraceFlow"

# Parse arguments
MODE="${1:-docker}"

print_usage() {
    echo "Usage: $0 [docker|dev|services]"
    echo ""
    echo "Modes:"
    echo "  docker   - Run everything in Docker (default)"
    echo "  dev      - Run services in Docker, frontend/API locally for hot-reload"
    echo "  services - Only start infrastructure (DB, MinIO, PubSub)"
    echo ""
}

start_infrastructure() {
    echo -e "${YELLOW}Starting infrastructure services...${NC}"
    cd "$OVERLAY_DIR"
    docker-compose up -d db storage pubsub-emulator

    echo -e "${GREEN}Waiting for services to be healthy...${NC}"
    sleep 5

    # Wait for PostgreSQL
    echo -n "Waiting for PostgreSQL..."
    for i in {1..30}; do
        if docker-compose exec -T db pg_isready -U overlay -d overlay_dev > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 1
    done

    # Wait for MinIO
    echo -n "Waiting for MinIO..."
    for i in {1..30}; do
        if curl -sf http://localhost:9000/minio/health/ready > /dev/null 2>&1; then
            echo -e " ${GREEN}Ready!${NC}"
            break
        fi
        echo -n "."
        sleep 1
    done

    echo -e "${GREEN}Infrastructure is ready!${NC}"
}

start_docker_mode() {
    echo -e "${YELLOW}Starting all services in Docker...${NC}"
    cd "$OVERLAY_DIR"
    docker-compose up -d --build

    echo ""
    echo -e "${GREEN}============================================${NC}"
    echo -e "${GREEN}  All Services Started!${NC}"
    echo -e "${GREEN}============================================${NC}"
    echo ""
    echo "Access points:"
    echo -e "  Frontend:     ${BLUE}http://localhost:3000${NC}"
    echo -e "  API:          ${BLUE}http://localhost:8000${NC}"
    echo -e "  MinIO Console: ${BLUE}http://localhost:9001${NC} (minio/minio123)"
    echo ""
    echo "To view logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "To stop:"
    echo "  docker-compose down"
}

start_dev_mode() {
    echo -e "${YELLOW}Starting development mode (hot-reload enabled)...${NC}"

    # Start infrastructure
    start_infrastructure

    echo ""
    echo -e "${GREEN}Infrastructure is running. Now start the API and frontend manually:${NC}"
    echo ""
    echo -e "${YELLOW}Terminal 1 - Start API:${NC}"
    echo "  cd $OVERLAY_DIR"
    echo "  source .env"
    echo "  uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
    echo ""
    echo -e "${YELLOW}Terminal 2 - Start Vision Worker:${NC}"
    echo "  cd $OVERLAY_DIR/vision/worker"
    echo "  source .env"
    echo "  uv run python -m main"
    echo ""
    echo -e "${YELLOW}Terminal 3 - Start Frontend:${NC}"
    echo "  cd $FRONTEND_DIR"
    echo "  npm run dev"
    echo ""
    echo "Access points:"
    echo -e "  Frontend:     ${BLUE}http://localhost:5000${NC}"
    echo -e "  API:          ${BLUE}http://localhost:8000${NC}"
    echo -e "  MinIO Console: ${BLUE}http://localhost:9001${NC} (minio/minio123)"
}

start_services_only() {
    start_infrastructure
    echo ""
    echo "Infrastructure services are running:"
    echo -e "  PostgreSQL:   ${BLUE}localhost:5432${NC}"
    echo -e "  MinIO:        ${BLUE}localhost:9000${NC}"
    echo -e "  Pub/Sub:      ${BLUE}localhost:8681${NC}"
}

case "$MODE" in
    docker)
        start_docker_mode
        ;;
    dev)
        start_dev_mode
        ;;
    services)
        start_services_only
        ;;
    -h|--help|help)
        print_usage
        ;;
    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        print_usage
        exit 1
        ;;
esac
