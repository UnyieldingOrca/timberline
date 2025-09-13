"""
Log ingestor service tests.
Tests log ingestion API endpoints, batch processing, and connectivity.
"""

import pytest
import requests
import time


@pytest.mark.docker
@pytest.mark.integration
def test_log_ingestor_health(ingestor_url, http_retry):
    """Test log ingestor health endpoint."""
    response = http_retry(f"{ingestor_url}/api/v1/health", timeout=10)
    assert response.status_code == 200

    health_data = response.json()
    assert "status" in health_data
    assert health_data["status"] == "healthy"


@pytest.mark.docker
@pytest.mark.integration
def test_log_ingestor_liveness(ingestor_url, http_retry):
    """Test log ingestor liveness endpoint."""
    response = http_retry(f"{ingestor_url}/api/v1/healthz", timeout=10)
    assert response.status_code == 200
    assert response.text.strip() == "OK"


@pytest.mark.docker
@pytest.mark.integration
def test_log_ingestor_metrics(http_retry):
    """Test log ingestor metrics endpoint."""
    response = http_retry("http://localhost:9092/metrics", timeout=10)
    assert response.status_code == 200
    assert len(response.text) > 0


@pytest.mark.docker
@pytest.mark.integration
def test_single_log_ingestion(ingestor_url, sample_log_entry, http_retry):
    """Test ingesting a single log entry."""
    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json={"logs": [sample_log_entry]},
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    assert response.status_code == 200, f"Log ingestion failed: {response.text}"

    result = response.json()
    assert result.get("success") == True
    assert result.get("processed_count") == 1


@pytest.mark.docker
@pytest.mark.integration
def test_batch_log_ingestion(ingestor_url, log_generator, http_retry):
    """Test ingesting multiple log entries."""
    log_entries = log_generator.generate_log_entries_for_api(count=4)

    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json={"logs": log_entries},
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    assert response.status_code in [200, 202]

    result = response.json()
    assert result.get("success") == True
    assert result.get("processed_count") == len(log_entries)


@pytest.mark.docker
@pytest.mark.integration
def test_log_collector_connectivity(ingestor_url, http_retry):
    """Test connectivity between log-collector and log-ingestor."""
    log_payload = {
        "logs": [{
            "timestamp": int(time.time() * 1000),
            "message": "Test connectivity between log-collector and log-ingestor",
            "source": "log-collector",
            "metadata": {
                "level": "ERROR",
                "container_name": "timberline-log-collector",
                "namespace": "default",
                "pod_name": "timberline-log-collector-pod",
                "service_name": "log-collector",
                "node_name": "test-node",
                "labels": {"app": "log-collector"}
            }
        }]
    }

    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json=log_payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    assert response.status_code in [200, 202], \
        f"Log forwarding failed: {response.status_code} {response.text}"


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.parametrize("log_count", [1, 5, 25, 100])
def test_variable_batch_sizes(ingestor_url, log_generator, log_count, http_retry):
    """Test ingesting different batch sizes."""
    log_entries = log_generator.generate_log_entries_for_api(count=log_count)

    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json={"logs": log_entries},
        headers={"Content-Type": "application/json"},
        timeout=60
    )

    assert response.status_code in [200, 202], f"Failed for batch size {log_count}"

    result = response.json()
    assert result.get("success") == True
    assert result.get("processed_count") == log_count


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.parametrize("level", ["ERROR", "WARN", "INFO", "DEBUG"])
def test_different_log_levels(ingestor_url, level, http_retry):
    """Test ingesting logs with different severity levels."""
    log_entry = {
        "timestamp": int(time.time() * 1000),
        "message": f"Test {level} message",
        "source": "test-service",
        "metadata": {
            "level": level,
            "container_name": "test-container",
            "namespace": "test-namespace",
            "pod_name": "test-pod",
            "service_name": "test-service"
        }
    }

    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json={"logs": [log_entry]},
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    assert response.status_code in [200, 202], f"Failed for log level {level}"

    result = response.json()
    assert result.get("success") == True
    assert result.get("processed_count") == 1


@pytest.mark.docker
@pytest.mark.integration
def test_empty_batch_handling(ingestor_url, http_retry):
    """Test handling of empty log batches."""
    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json={"logs": []},
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    # Should handle empty batches gracefully
    assert response.status_code in [200, 400], "Empty batch should be handled gracefully"


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.parametrize("invalid_payload", [
    {},  # Missing logs field
    {"logs": "not-a-list"},  # Invalid logs type
    {"logs": [{}]},  # Empty log entry
    {"logs": [{"timestamp": "invalid"}]},  # Invalid timestamp type
])
def test_invalid_payload_handling(ingestor_url, invalid_payload, http_retry):
    """Test handling of invalid payloads."""
    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json=invalid_payload,
        headers={"Content-Type": "application/json"},
        timeout=30
    )

    # Should return error for invalid payloads
    assert response.status_code >= 400, f"Should reject invalid payload: {invalid_payload}"


@pytest.mark.docker
@pytest.mark.integration
def test_concurrent_log_ingestion(ingestor_url, log_generator, http_retry):
    """Test handling concurrent log ingestion requests."""
    import threading
    import concurrent.futures

    def ingest_logs(batch_id):
        log_entries = log_generator.generate_log_entries_for_api(count=10)
        # Add batch ID to distinguish between concurrent requests
        for entry in log_entries:
            entry["message"] = f"Batch {batch_id}: {entry['message']}"

        response = http_retry(
            f"{ingestor_url}/api/v1/logs/batch",
            method="POST",
            json={"logs": log_entries},
            headers={"Content-Type": "application/json"},
            timeout=60
        )
        return response.status_code, len(log_entries)

    # Send 5 concurrent batches
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(ingest_logs, i) for i in range(5)]
        results = [future.result() for future in concurrent.futures.as_completed(futures)]

    # All requests should succeed
    for status_code, log_count in results:
        assert status_code in [200, 202], f"Concurrent request failed with status {status_code}"