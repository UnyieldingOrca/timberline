"""SQLAlchemy base configuration."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()


def get_engine(database_url: str):
    """Create database engine."""
    return create_engine(database_url, pool_pre_ping=True)


def get_session_maker(engine):
    """Create session maker."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
