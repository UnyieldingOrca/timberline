"""
Metrics collection endpoint tests.
Tests Prometheus metrics endpoints for all services.
"""

import pytest
import requests


@pytest.mark.parametrize("service_name,url", [
    ("Log Collector", "http://localhost:8020/api/v1/metrics"),
    ("Log Ingestor", "http://localhost:8201/metrics"),
    ("Milvus Health", "http://localhost:8091/healthz")
])
def test_metrics_endpoint_accessibility(service_name, url, http_retry):
    """Test that metrics endpoints are accessible."""
    response = http_retry(url, timeout=10)
    assert response.status_code == 200, f"{service_name} metrics endpoint not accessible"
    assert len(response.text) > 0, f"{service_name} metrics response is empty"


def test_log_collector_metrics_content(http_retry):
    """Test log collector metrics endpoint content."""
    response = http_retry("http://localhost:8020/api/v1/metrics", timeout=10)
    assert response.status_code == 200

    metrics_text = response.text
    assert len(metrics_text) > 0, "Metrics response is empty"

    # Fluent Bit returns JSON metrics, check for expected structure
    import json
    metrics_data = json.loads(metrics_text)
    assert "input" in metrics_data, f"Expected 'input' in metrics data: {metrics_text[:500]}"
    assert "output" in metrics_data, f"Expected 'output' in metrics data: {metrics_text[:500]}"


def test_log_ingestor_metrics_content(http_retry):
    """Test log ingestor metrics endpoint content."""
    response = http_retry("http://localhost:8201/metrics", timeout=10)
    assert response.status_code == 200

    metrics_text = response.text
    assert len(metrics_text) > 0, "Log ingestor metrics response is empty"

    # Look for expected Go/Prometheus metrics
    expected_metrics = ["go_", "promhttp_"]
    found_metrics = [metric for metric in expected_metrics if metric in metrics_text]
    assert len(found_metrics) > 0, f"No expected metrics found in log ingestor. Available: {metrics_text[:500]}"


def test_milvus_health_endpoint(http_retry):
    """Test Milvus health endpoint."""
    response = http_retry("http://localhost:8091/healthz", timeout=10)
    assert response.status_code == 200, "Milvus health endpoint not accessible"


@pytest.mark.parametrize("metric_pattern", [
    "go_goroutines",
    "go_memstats_",
    "promhttp_metric_handler_"
])
def test_standard_go_metrics_present(metric_pattern, http_retry):
    """Test that standard Go metrics are present in service endpoints."""
    endpoints = [
        "http://localhost:8201/metrics"   # Log Ingestor (only test Prometheus-format metrics)
    ]

    for endpoint in endpoints:
        response = http_retry(endpoint, timeout=10)
        assert response.status_code == 200

        metrics_text = response.text
        assert metric_pattern in metrics_text, \
            f"Metric pattern '{metric_pattern}' not found in {endpoint}"


def test_metrics_format_validity(http_retry):
    """Test that metrics are in valid Prometheus format."""
    endpoints = [
        ("Log Ingestor", "http://localhost:8201/metrics")
    ]

    for service_name, endpoint in endpoints:
        response = http_retry(endpoint, timeout=10)
        assert response.status_code == 200

        metrics_text = response.text
        lines = metrics_text.split('\n')

        # Basic format validation
        metric_lines = [line for line in lines if line and not line.startswith('#')]
        assert len(metric_lines) > 0, f"{service_name} has no metric data lines"

        # Check that metric lines have proper format (name value [timestamp])
        for line in metric_lines[:10]:  # Check first 10 metric lines
            if line.strip():
                parts = line.split()
                assert len(parts) >= 2, f"Invalid metric line format in {service_name}: {line}"


def test_metrics_response_time(http_retry):
    """Test that metrics endpoints respond quickly."""
    endpoints = [
        "http://localhost:8020/api/v1/metrics",
        "http://localhost:8201/metrics",
        "http://localhost:8091/healthz"
    ]

    import time
    for endpoint in endpoints:
        start_time = time.time()
        response = http_retry(endpoint, timeout=5)
        end_time = time.time()

        assert response.status_code == 200
        response_time = end_time - start_time
        assert response_time < 5.0, f"Metrics endpoint {endpoint} took too long: {response_time:.2f}s"


def test_metrics_consistency_across_calls(http_retry):
    """Test that metrics endpoints return consistent data structure across multiple calls."""
    endpoint = "http://localhost:8020/api/v1/metrics"

    # Make two calls
    response1 = http_retry(endpoint, timeout=10)
    response2 = http_retry(endpoint, timeout=10)

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Extract metric structure from JSON responses
    import json
    metrics1 = json.loads(response1.text)
    metrics2 = json.loads(response2.text)

    # Core structure should be consistent
    assert "input" in metrics1 and "input" in metrics2, "Input metrics should be present in both calls"
    assert "output" in metrics1 and "output" in metrics2, "Output metrics should be present in both calls"

    # Structure keys should be the same
    keys1 = set(metrics1.keys())
    keys2 = set(metrics2.keys())
    assert keys1 == keys2, f"Metrics structure inconsistent: {keys1} vs {keys2}"


def test_all_metrics_endpoints_simultaneously(metrics_endpoints, http_retry):
    """Test all metrics endpoints simultaneously for load testing."""
    import concurrent.futures
    import threading

    def fetch_metrics(service_name, url):
        try:
            response = http_retry(url, timeout=10)
            return service_name, response.status_code, len(response.text)
        except Exception as e:
            return service_name, None, str(e)

    # Fetch all metrics endpoints concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(metrics_endpoints)) as executor:
        futures = [
            executor.submit(fetch_metrics, service_name, url)
            for service_name, url in metrics_endpoints
        ]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    # All should succeed
    for service_name, status_code, response_size in results:
        assert status_code == 200, f"{service_name} failed with status {status_code}: {response_size}"
        assert isinstance(response_size, int) and response_size > 0, \
            f"{service_name} returned empty response"