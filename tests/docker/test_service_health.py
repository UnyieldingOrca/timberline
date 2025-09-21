"""
Service health endpoint tests for Timberline Docker services.
Tests that all Docker Compose services are running and healthy.
"""

import pytest
import requests


@pytest.mark.parametrize("service_name,url,expected_status", [
    ("Milvus Metrics", "http://localhost:9091/healthz", 200),
    ("llama.cpp Embedding", "http://localhost:8000/health", 200),
    ("llama.cpp Chat", "http://localhost:8001/health", 200),
    ("MinIO", "http://localhost:9000/minio/health/live", 200),
    ("Log Ingestor Health", "http://localhost:8080/api/v1/healthz", 200),
    ("Log Ingestor Metrics", "http://localhost:9092/metrics", 200),
    ("Fluent Bit Health", "http://localhost:2020/api/v1/health", 200)
])
def test_service_health_endpoint(service_name, url, expected_status, http_retry):
    """Test individual service health endpoints."""
    response = http_retry(url, timeout=5)
    assert response.status_code == expected_status, \
        f"{service_name} health check failed: status {response.status_code}, response: {response.text[:200]}"


def test_all_services_healthy(service_endpoints, http_retry):
    """Test that all services are healthy simultaneously."""
    failed_services = []

    for service_name, url, expected_status in service_endpoints:
        try:
            response = http_retry(url, timeout=5)
            if response.status_code != expected_status:
                failed_services.append((service_name, response.status_code))
        except requests.exceptions.RequestException as e:
            failed_services.append((service_name, str(e)))

    assert not failed_services, f"Failed services: {failed_services}"