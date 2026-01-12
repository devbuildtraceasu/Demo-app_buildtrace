"""Database engine and connection management using SQLModel."""

from sqlalchemy.engine import URL
from sqlmodel import Session, create_engine

from config import config

# Module-level engine instance
_engine = None


def get_engine():
    """
    Get or create the database engine with connection pooling.

    Returns:
        Engine: SQLModel database engine instance
    """
    global _engine

    if _engine is None:
        connection_string = URL.create(
            "postgresql+psycopg2",
            username=config.db_user,
            password=config.db_password,
            host=config.db_host,
            port=config.db_port,
            database=config.db_name,
        )

        _engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,  # Verify connections before using
            echo=False,  # Set to True for SQL logging
        )

    return _engine


def get_session() -> Session:
    """
    Create a new database session.

    Returns:
        Session: SQLModel session for database operations

    Example:
        with get_session() as session:
            statement = select(DrawingRevision).where(DrawingRevision.id == "r123")
            revision = session.exec(statement).first()
    """
    engine = get_engine()
    return Session(engine)


def close_engine():
    """Close the database engine and all connections."""
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
