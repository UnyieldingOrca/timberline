# Timberline Kind Integration Tests

Comprehensive integration test suite for Timberline deployed on Kind (Kubernetes in Docker).

## Overview

These tests validate the complete Timberline platform deployed via Helm chart on a Kind cluster. They cover:

- **Deployment Status**: Pods, deployments, StatefulSets, and DaemonSets
- **Service Health**: Health endpoints and metrics for all services
- **Service Connectivity**: Inter-service communication and networking
- **Component-Specific**: Detailed tests for each major component
- **End-to-End Pipeline**: Complete log flow from ingestion to analysis

## Test Structure

```
tests/kind/
├── conftest.py                    # Fixtures and helpers
├── test_deployment_status.py      # Deployment, pod, and service status
├── test_service_health.py         # Health endpoint tests
├── test_service_connectivity.py   # Inter-service communication
├── test_fluent_bit.py            # Fluent Bit DaemonSet tests
├── test_log_ingestor.py          # Log Ingestor service tests
├── test_milvus_stack.py          # Milvus + etcd + MinIO tests
├── test_llm_services.py          # Embedding and chat service tests
├── test_ai_analyzer.py           # AI Analyzer API tests
└── test_e2e_pipeline.py          # End-to-end pipeline tests
```

## Prerequisites

### 1. Install Dependencies

```bash
# Install Python test dependencies
pip install pytest pytest-xdist requests pymilvus psycopg2-binary

# Or use the project Makefile
make install-test-deps
```

### 2. Setup Kind Cluster

```bash
# Setup Kind cluster and deploy Timberline
make kind-setup

# Or manually
./scripts/kind-setup.sh
```

This will:
- Create a Kind cluster
- Install the Timberline Helm chart
- Wait for all pods to be ready
- Download required AI models

## Running Tests

### Quick Health Check (Fast)

Run only health check tests for fast validation:

```bash
pytest tests/kind/ -v -m health
```

### Deployment Tests

Test that all resources are deployed correctly:

```bash
pytest tests/kind/ -v -m deployment
```

### Connectivity Tests

Test inter-service communication:

```bash
pytest tests/kind/ -v -m connectivity
```

### End-to-End Tests

Test complete pipeline workflows:

```bash
pytest tests/kind/ -v -m e2e
```

### All Tests (Excluding Slow)

Run all tests except slow-running ones:

```bash
pytest tests/kind/ -v -m "not slow"
```

### Complete Test Suite

Run all tests including slow-running tests:

```bash
pytest tests/kind/ -v
```

### Parallel Execution

Run tests in parallel for faster execution:

```bash
pytest tests/kind/ -v -n auto
```

### Specific Test File

Run tests from a specific file:

```bash
pytest tests/kind/test_service_health.py -v
pytest tests/kind/test_e2e_pipeline.py -v
```

### Specific Test Class or Function

```bash
# Run specific test class
pytest tests/kind/test_deployment_status.py::TestDeploymentStatus -v

# Run specific test function
pytest tests/kind/test_service_health.py::TestServiceHealthEndpoints::test_fluent_bit_health -v
```

## Test Markers

Tests are organized with markers for selective execution:

- `@pytest.mark.health` - Quick health checks
- `@pytest.mark.deployment` - Deployment status tests
- `@pytest.mark.connectivity` - Service connectivity tests
- `@pytest.mark.persistence` - Data persistence tests
- `@pytest.mark.e2e` - End-to-end pipeline tests
- `@pytest.mark.slow` - Long-running tests

## Environment Variables

You can customize test behavior with environment variables:

```bash
# Set custom namespace (default: default)
export TIMBERLINE_NAMESPACE=timberline

# Set custom helm release name (default: timberline)
export TIMBERLINE_RELEASE=my-release
```

## Test Fixtures

Key fixtures available in `conftest.py`:

### Kubernetes Helpers

- `kubectl` - Execute kubectl commands
- `wait_for_pod_ready` - Wait for pods to become ready
- `get_pod_logs` - Retrieve pod logs
- `create_test_pod` - Create temporary test pods

### Port Forwarding

- `port_forward_manager` - Create port-forwards to services

```python
def test_example(port_forward_manager):
    with port_forward_manager("log-ingestor-service", 8080) as pf:
        url = f"http://localhost:{pf.local_port}/api/v1/healthz"
        # ... make requests to url
```

### Database Connections

- `milvus_client` - Connected Milvus client
- `postgres_conn` - PostgreSQL connection (if enabled)
- `cleanup_milvus_data` - Clean Milvus data before test
- `cleanup_postgres_data` - Clean PostgreSQL data before test

### HTTP Utilities

- `http_retry` - HTTP client with retry logic
- `wait_for_service_ready` - Wait for service health endpoint

### Test Data

- `sample_log_entries` - Sample log data for testing

## Common Test Patterns

### Testing Service Health

```python
def test_service_health(namespace, port_forward_manager, http_retry, wait_for_service_ready):
    with port_forward_manager("my-service", 8080, namespace) as pf:
        url = f"http://localhost:{pf.local_port}/health"
        wait_for_service_ready(url)

        response = http_retry(url)
        assert response.status_code == 200
```

### Testing API Endpoints

```python
def test_api_endpoint(namespace, port_forward_manager, http_retry):
    with port_forward_manager("my-service", 8080, namespace) as pf:
        url = f"http://localhost:{pf.local_port}/api/v1/endpoint"

        response = http_retry(
            url,
            method="POST",
            json={"key": "value"},
            timeout=30
        )

        assert response.status_code == 200
```

### Testing Milvus Operations

```python
def test_milvus_operation(milvus_client, cleanup_milvus_data):
    from pymilvus import Collection, utility

    collection_name = "test_collection"

    # Test operations
    assert utility.has_collection(collection_name, using=milvus_client)

    collection = Collection(collection_name, using=milvus_client)
    # ... perform operations
```

## Troubleshooting

### Tests Timing Out

If tests are timing out:

1. Increase timeout in `conftest.py`:
   ```python
   timeout_config = {
       "pod_ready": 600,  # Increase from 300
       "service_ready": 240,  # Increase from 120
   }
   ```

2. Check if all pods are running:
   ```bash
   kubectl get pods
   ```

3. Check pod logs for errors:
   ```bash
   kubectl logs <pod-name>
   ```

### Port Forward Failures

If port forwarding fails:

1. Check if service exists:
   ```bash
   kubectl get svc
   ```

2. Verify pods are running:
   ```bash
   kubectl get pods -l app=<app-name>
   ```

3. Try manual port-forward:
   ```bash
   kubectl port-forward svc/<service-name> 8080:8080
   ```

### Milvus Connection Issues

If Milvus connection fails:

1. Check Milvus pod status:
   ```bash
   kubectl get pods -l app=milvus
   kubectl logs -l app=milvus
   ```

2. Verify etcd and MinIO are running:
   ```bash
   kubectl get pods -l app=etcd
   kubectl get pods -l app=minio
   ```

3. Check Milvus health:
   ```bash
   kubectl port-forward svc/milvus-metrics 9091:9091
   curl http://localhost:9091/healthz
   ```

### Test Data Cleanup

If you need to manually clean test data:

```bash
# Connect to Milvus and drop collections
kubectl port-forward svc/milvus-service 19530:19530

# In Python
from pymilvus import connections, utility, Collection
connections.connect(host="localhost", port="19530")
utility.drop_collection("timberline_logs")
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Kind Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Kind
        run: make kind-setup

      - name: Run Health Checks
        run: pytest tests/kind/ -v -m health --maxfail=3

      - name: Run Full Test Suite
        run: pytest tests/kind/ -v -m "not slow"

      - name: Cleanup
        if: always()
        run: make kind-down
```

### Test Execution Strategies

**Fast Feedback Loop (CI)**:
```bash
pytest tests/kind/ -v -m "health" --maxfail=3
pytest tests/kind/ -v -m "deployment"
```

**Comprehensive Validation**:
```bash
pytest tests/kind/ -v -m "not slow" -n auto
```

**Full Integration Suite**:
```bash
pytest tests/kind/ -v
```

## Contributing

When adding new tests:

1. **Use appropriate markers**: Mark tests with relevant markers (`health`, `deployment`, etc.)
2. **Clean up resources**: Use fixtures for cleanup or manually delete test resources
3. **Use retry logic**: Network operations should use `http_retry` fixture
4. **Document complex tests**: Add docstrings explaining test purpose and workflow
5. **Parameterize when possible**: Use `@pytest.mark.parametrize` for multiple similar tests

## Additional Resources

- [Kind Documentation](https://kind.sigs.k8s.io/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Timberline SPEC.md](../../SPEC.md)
- [Project README](../../README.md)
