# Integration Tests

This directory contains integration tests for the Timberline log analysis platform.

## Test Structure

The tests are organized by component for better maintainability:

- `conftest.py` - pytest configuration and shared fixtures
- `log_generator.py` - log data generation module
- `test_service_health.py` - service health endpoint tests
- `test_embedding_service.py` - llama.cpp embedding service tests
- `test_milvus_database.py` - Milvus vector database tests
- `test_log_ingestor.py` - log ingestor API and functionality tests
- `test_pipeline.py` - end-to-end pipeline and data persistence tests
- `test_metrics.py` - Prometheus metrics endpoint tests

## Test Philosophy

Each test file follows clean pytest patterns:

- **Single-function tests** using fixtures and parameterization
- **Proper fixtures** for setup/teardown and data generation
- **Parameterized tests** for testing multiple scenarios
- **Clear test names** describing what is being tested

Example test structure:
```python
@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.parametrize("input_value,expected", [
    ("test1", "result1"),
    ("test2", "result2")
])
def test_specific_functionality(fixture1, fixture2, input_value, expected):
    """Test specific functionality with parameterized inputs."""
    result = some_function(fixture1, input_value)
    assert result == expected
```

## Log Generation

Log data is generated programmatically within the test suite:

```python
def test_my_feature(log_generator):
    # Generate log entries for API testing
    log_entries = log_generator.generate_log_entries_for_api(count=10)

    # Use the entries in your test
    response = requests.post(api_url, json={"logs": log_entries})
    assert response.status_code == 200
```

## Shared Fixtures

Available fixtures from `conftest.py`:

- `log_generator` - Log data generator instance
- `ingestor_url` - Log ingestor service URL
- `embedding_url` - Embedding service URL
- `milvus_connection` - Milvus database connection
- `sample_log_entry` - Single test log entry
- `http_retry` - HTTP request helper with retry logic

## Running Tests

```bash
# Run all integration tests
make test-integration

# Run tests by component
pytest tests/docker/test_service_health.py -v
pytest tests/docker/test_embedding_service.py -v
pytest tests/docker/test_milvus_database.py -v
pytest tests/docker/test_log_ingestor.py -v
pytest tests/docker/test_pipeline.py -v
pytest tests/docker/test_metrics.py -v

# Run tests in parallel
make test-integration-parallel

# Run only slow pipeline tests
pytest tests/docker/test_pipeline.py -v -m "docker and slow"

# Run specific test with pattern
pytest tests/docker/ -v -k "test_embedding"
```

## Test Markers

- `@pytest.mark.docker` - Requires Docker services to be running
- `@pytest.mark.integration` - Integration test (vs unit test)
- `@pytest.mark.slow` - Slower tests (like full pipeline tests)

## Prerequisites

- Docker and Docker Compose
- Python test dependencies: `pip install -r requirements-test.txt`
- All Docker services healthy (run `make docker-up` first)