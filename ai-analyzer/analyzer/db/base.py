"""SQLAlchemy base configuration."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()

# Global session maker (initialized in application startup)
SessionLocal = None


def get_engine(database_url: str):
    """Create database engine."""
    return create_engine(database_url, pool_pre_ping=True)


def get_session_maker(engine):
    """Create session maker."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db(database_url: str = None):
    """Initialize database connection."""
    global SessionLocal
    if database_url is None:
        database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/timberline")
    engine = get_engine(database_url)
    SessionLocal = get_session_maker(engine)
    return engine


def get_db() -> Session:
    """Dependency for getting database session."""
    if SessionLocal is None:
        init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
