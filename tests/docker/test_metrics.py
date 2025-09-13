"""
Metrics collection endpoint tests.
Tests Prometheus metrics endpoints for all services.
"""

import pytest
import requests


@pytest.mark.parametrize("service_name,url", [
    ("Log Collector", "http://localhost:9090/metrics"),
    ("Log Ingestor", "http://localhost:9092/metrics"),
    ("Milvus Health", "http://localhost:9091/healthz")
])
def test_metrics_endpoint_accessibility(service_name, url, http_retry):
    """Test that metrics endpoints are accessible."""
    response = http_retry(url, timeout=10)
    assert response.status_code == 200, f"{service_name} metrics endpoint not accessible"
    assert len(response.text) > 0, f"{service_name} metrics response is empty"


def test_log_collector_metrics_content(http_retry):
    """Test log collector metrics endpoint content."""
    response = http_retry("http://localhost:9090/metrics", timeout=10)
    assert response.status_code == 200

    metrics_text = response.text
    assert len(metrics_text) > 0, "Metrics response is empty"

    # Look for expected Prometheus metrics
    expected_metrics = ["go_", "promhttp_"]
    found_metrics = [metric for metric in expected_metrics if metric in metrics_text]
    assert len(found_metrics) > 0, f"No expected metrics found. Available metrics preview: {metrics_text[:500]}"


def test_log_ingestor_metrics_content(http_retry):
    """Test log ingestor metrics endpoint content."""
    response = http_retry("http://localhost:9092/metrics", timeout=10)
    assert response.status_code == 200

    metrics_text = response.text
    assert len(metrics_text) > 0, "Log ingestor metrics response is empty"

    # Look for expected Go/Prometheus metrics
    expected_metrics = ["go_", "promhttp_"]
    found_metrics = [metric for metric in expected_metrics if metric in metrics_text]
    assert len(found_metrics) > 0, f"No expected metrics found in log ingestor. Available: {metrics_text[:500]}"


def test_milvus_health_endpoint(http_retry):
    """Test Milvus health endpoint."""
    response = http_retry("http://localhost:9091/healthz", timeout=10)
    assert response.status_code == 200, "Milvus health endpoint not accessible"


@pytest.mark.parametrize("metric_pattern", [
    "go_goroutines",
    "go_memstats_",
    "promhttp_metric_handler_"
])
def test_standard_go_metrics_present(metric_pattern, http_retry):
    """Test that standard Go metrics are present in service endpoints."""
    endpoints = [
        "http://localhost:9090/metrics",  # Log Collector
        "http://localhost:9092/metrics"   # Log Ingestor
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
        ("Log Collector", "http://localhost:9090/metrics"),
        ("Log Ingestor", "http://localhost:9092/metrics")
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
        "http://localhost:9090/metrics",
        "http://localhost:9092/metrics",
        "http://localhost:9091/healthz"
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
    endpoint = "http://localhost:9090/metrics"

    # Make two calls
    response1 = http_retry(endpoint, timeout=10)
    response2 = http_retry(endpoint, timeout=10)

    assert response1.status_code == 200
    assert response2.status_code == 200

    # Extract metric names from both responses
    def extract_metric_names(text):
        lines = text.split('\n')
        metric_names = set()
        for line in lines:
            if line and not line.startswith('#'):
                parts = line.split()
                if len(parts) >= 2:
                    metric_name = parts[0].split('{')[0]  # Remove labels
                    metric_names.add(metric_name)
        return metric_names

    metrics1 = extract_metric_names(response1.text)
    metrics2 = extract_metric_names(response2.text)

    # Core metrics should be present in both responses
    common_metrics = metrics1.intersection(metrics2)
    assert len(common_metrics) > 0, "No common metrics found between two calls"

    # Most metrics should be consistent (some may vary due to timing)
    consistency_ratio = len(common_metrics) / max(len(metrics1), len(metrics2))
    assert consistency_ratio > 0.8, f"Metrics inconsistent across calls: {consistency_ratio:.2f}"


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