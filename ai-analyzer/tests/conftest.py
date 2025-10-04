"""Pytest fixtures for integration tests"""
import os
import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from analyzer.api.main import create_app
from analyzer.db.base import Base, get_db
from analyzer.config.settings import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings with overrides"""
    # Use environment variables or defaults for testing
    return Settings()


@pytest.fixture(scope="function")
def test_db():
    """Create a test database for each test function"""
    # Always use in-memory SQLite for unit tests to ensure isolation
    database_url = "sqlite:///:memory:"

    engine = create_engine(
        database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Create tables
    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    yield TestingSessionLocal

    # Drop tables after test
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_client(test_db, test_settings):
    """Create a FastAPI test client"""
    # Must set TEST_DATABASE_URL before creating app to prevent init_db from using production DB
    import os
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"

    app = create_app()
    app.state.settings = test_settings

    # Override database dependency
    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    # Restore original DATABASE_URL
    if old_db_url:
        os.environ["DATABASE_URL"] = old_db_url
    elif "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


@pytest.fixture
def sample_log_data():
    """Sample log data for testing"""
    return {
        "timestamp": datetime.now().isoformat(),
        "namespace": "default",
        "pod_name": "test-pod",
        "container_name": "test-container",
        "log": "Test log message",
        "severity": "INFO"
    }


@pytest.fixture
def sample_analysis_request():
    """Sample analysis request for testing"""
    return {
        "namespace": "default",
        "time_range_hours": 24,
        "min_cluster_size": 5
    }
