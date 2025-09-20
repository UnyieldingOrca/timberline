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


@pytest.fixture
def log_generator(test_logs_dir, request):
    """Create and configure log generator for each test function.

    Each test gets its own log generator instance with a unique subdirectory
    to avoid conflicts between parallel tests.
    """
    # Create unique subdirectory for this test
    test_name = request.node.name
    unique_dir = test_logs_dir / f"test_{test_name}_{int(time.time() * 1000)}"
    unique_dir.mkdir(parents=True, exist_ok=True)

    generator = LogGenerator(output_dir=str(unique_dir))

    yield generator

    # Optional cleanup - uncomment to remove test logs after each test
    # generator.cleanup()


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
        ("llama.cpp Embedding", "http://localhost:8000/health", 200),
        ("llama.cpp Chat", "http://localhost:8001/health", 200),
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


# AI Analyzer fixtures
@pytest.fixture(scope="session")
def ai_analyzer_path():
    """Path to AI Analyzer package."""
    return Path(__file__).parents[2] / "ai-analyzer"


@pytest.fixture(scope="session")
def ai_analyzer_settings(milvus_host, milvus_port):
    """AI Analyzer configuration settings for testing."""
    return {
        'milvus_host': milvus_host,
        'milvus_port': int(milvus_port),
        'milvus_collection': 'timberline_logs',
        'analysis_window_hours': 24,  # Full day for testing to catch all logs
        'max_logs_per_analysis': 1000,
        'cluster_batch_size': 10,
        'llm_endpoint': 'http://localhost:8001/v1',  # New chat service
        'llm_model': 'llama-3.2-3b-instruct',
        'llm_api_key': 'test-key',
        'report_output_dir': '/tmp/test-reports',
        'webhook_url': None
    }


@pytest.fixture
def ai_analyzer_engine(ai_analyzer_path, ai_analyzer_settings):
    """AI Analyzer engine instance for testing."""
    import sys

    # Add ai-analyzer to path
    sys.path.insert(0, str(ai_analyzer_path))

    # Import after adding to path
    from analyzer.config.settings import Settings
    from analyzer.analysis.engine import AnalysisEngine

    settings = Settings.from_dict(ai_analyzer_settings)
    engine = AnalysisEngine(settings)

    yield engine

    # Cleanup: remove from path
    if str(ai_analyzer_path) in sys.path:
        sys.path.remove(str(ai_analyzer_path))


@pytest.fixture
def realistic_log_data(log_generator):
    """Generate realistic log scenarios for AI analysis testing."""
    return log_generator.generate_realistic_error_scenarios()

