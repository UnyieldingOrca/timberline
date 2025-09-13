"""
Pytest configuration and fixtures for Docker integration tests.
"""

import pytest
import requests
import time
from pathlib import Path
from pymilvus import connections
from .log_generator import LogGenerator


@pytest.fixture(scope="session")
def test_logs_dir():
    """Provide test logs directory path."""
    return Path(__file__).parents[2] / "volumes" / "test-logs"


@pytest.fixture(scope="session")
def log_generator(test_logs_dir):
    """Create and configure log generator."""
    generator = LogGenerator(output_dir=str(test_logs_dir))
    return generator


@pytest.fixture(scope="session", autouse=True)
def setup_test_logs(log_generator, test_logs_dir):
    """Setup test logs before running tests."""
    # Ensure test logs directory exists
    test_logs_dir.mkdir(exist_ok=True)

    # Generate all test logs
    log_generator.generate_all_test_logs()

    yield

    # Cleanup after tests complete
    # Optionally keep logs for debugging: comment out the cleanup line
    # log_generator.cleanup()


# Service URL fixtures
@pytest.fixture(scope="session")
def ingestor_url():
    """Log ingestor service URL."""
    return "http://localhost:8080"


@pytest.fixture(scope="session")
def embedding_url():
    """Embedding service URL."""
    return "http://localhost:8000/v1/embeddings"


@pytest.fixture(scope="session")
def milvus_host():
    """Milvus database host."""
    return "localhost"


@pytest.fixture(scope="session")
def milvus_port():
    """Milvus database port."""
    return "19530"


# Service health check fixtures
@pytest.fixture(scope="session")
def service_endpoints():
    """Service health endpoint configurations."""
    return [
        ("Milvus Metrics", "http://localhost:9091/healthz", 200),
        ("llama.cpp", "http://localhost:8000/health", 200),
        ("MinIO", "http://localhost:9000/minio/health/live", 200),
        ("Log Ingestor Health", "http://localhost:8080/api/v1/healthz", 200),
        ("Log Ingestor Metrics", "http://localhost:9092/metrics", 200),
        ("Log Collector Metrics", "http://localhost:9090/metrics", 200)
    ]


@pytest.fixture(scope="session")
def metrics_endpoints():
    """Metrics endpoint configurations."""
    return [
        ("Log Collector", "http://localhost:9090/metrics"),
        ("Log Ingestor", "http://localhost:9092/metrics"),
        ("Milvus Health", "http://localhost:9091/healthz")
    ]


# Test data fixtures
@pytest.fixture
def sample_log_entry():
    """Single log entry for testing."""
    return {
        "timestamp": int(time.time() * 1000),
        "message": "Test log message for integration testing",
        "source": "test-source",
        "metadata": {
            "level": "INFO",
            "container_name": "test-container",
            "namespace": "test-namespace",
            "pod_name": "test-pod",
            "service_name": "test-service"
        }
    }


@pytest.fixture
def embedding_test_texts():
    """Sample texts for embedding testing."""
    return [
        "ERROR: Database connection failed in container",
        "WARN: Memory usage high in service",
        "FATAL: System crash detected in deployment",
        "INFO: Application started successfully"
    ]


# Milvus fixtures
@pytest.fixture(scope="session")
def milvus_connection(milvus_host, milvus_port):
    """Milvus database connection."""
    connections.connect(
        alias="default",
        host=milvus_host,
        port=milvus_port
    )
    yield
    connections.disconnect("default")




# Helper fixtures
@pytest.fixture
def retry_config():
    """Retry configuration for flaky network calls."""
    return {
        "max_retries": 3,
        "retry_delay": 1,
        "timeout": 10
    }


def make_request_with_retry(url, method="GET", max_retries=3, retry_delay=1, timeout=10, **kwargs):
    """Helper function to make HTTP requests with retry logic."""
    for attempt in range(max_retries):
        try:
            if method.upper() == "GET":
                response = requests.get(url, timeout=timeout, **kwargs)
            elif method.upper() == "POST":
                response = requests.post(url, timeout=timeout, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            return response
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(retry_delay)


@pytest.fixture
def http_retry():
    """HTTP request helper with retry logic."""
    return make_request_with_retry


