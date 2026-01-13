"""Initialize database tables."""

import logging
import sys
from pathlib import Path

# Add parent directory to path so we can import api
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import SQLModel

from api.dependencies import engine
from api.models import Organization, User

# Import all models that have routes to ensure they're registered
from api.routes.comparisons import Change, Overlay
from api.routes.drawings import Block, Drawing, Sheet
from api.routes.jobs import Job
from api.routes.projects import Project

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Create all database tables."""
    logger.info("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created successfully!")


if __name__ == "__main__":
    init_db()
