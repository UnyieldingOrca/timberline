# Integration Tests

This directory contains integration tests for the Timberline log analysis platform.

## Test Structure

- `conftest.py` - pytest configuration and fixtures, including log generation setup
- `test_integration.py` - main integration test suite
- `log_generator.py` - log data generation module

## Log Generation

Log data is now generated programmatically within the test suite rather than by bash scripts. This provides:

- Better control over test data
- More consistent test environments
- Ability to generate specific test scenarios
- Integration with pytest fixtures

### Using the Log Generator

The log generator is available as a pytest fixture:

```python
def test_my_feature(log_generator):
    # Generate log entries for API testing
    log_entries = log_generator.generate_log_entries_for_api(count=10)

    # Use the entries in your test
    response = requests.post(api_url, json={"logs": log_entries})
    assert response.status_code == 200
```

### Generated Log Types

The system generates these types of test logs:

1. **Application Logs** (`app-errors.log`) - Standard application error messages
2. **Structured Logs** (`structured-logs.log`) - JSON formatted logs
3. **Kubernetes Logs** (`k8s-app.log`) - Kubernetes-style formatted logs
4. **Mixed Format Logs** (`mixed-format.log`) - Various log formats mixed together
5. **High Volume Logs** (`high-volume.log`) - Large number of logs for performance testing
6. **Special Characters Logs** (`special-chars.log`) - Logs with unicode and special characters

## Running Tests

```bash
# Run all integration tests
make test-integration

# Run tests in parallel
make test-integration-parallel

# Run specific test classes
pytest tests/docker/test_integration.py::TestPipelineWithGeneratedLogs -v

# Run only pipeline tests (slower tests)
pytest tests/docker/test_integration.py -v -m "docker and slow"
```

## Test Markers

- `@pytest.mark.docker` - Requires Docker services to be running
- `@pytest.mark.integration` - Integration test (vs unit test)
- `@pytest.mark.slow` - Slower tests (like full pipeline tests)

## Prerequisites

- Docker and Docker Compose
- Python test dependencies: `pip install -r requirements-test.txt`
- All Docker services healthy (run `make docker-up` first)