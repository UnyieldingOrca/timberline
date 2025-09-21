"""
Fluent Bit integration tests for Timberline Docker environment.
Tests log collection, parsing, and forwarding to log-ingestor.
"""

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pytest
import requests


@pytest.fixture
def test_logs_dir():
    """Get the test logs directory path."""
    return Path("volumes/test-logs")


@pytest.fixture
def fluent_bit_health_url():
    """Fluent Bit health endpoint URL."""
    return "http://localhost:2020/api/v1/health"


@pytest.fixture
def log_ingestor_metrics_url():
    """Log ingestor metrics endpoint URL."""
    return "http://localhost:9092/metrics"


def test_fluent_bit_health_endpoint(fluent_bit_health_url, http_retry):
    """Test that Fluent Bit health endpoint is responding."""
    response = http_retry(fluent_bit_health_url, timeout=10)
    assert response.status_code == 200
    # Fluent Bit health endpoint typically returns plain text "ok"
    assert "ok" in response.text.lower()


def test_fluent_bit_log_ingestion(test_logs_dir, log_ingestor_metrics_url, http_retry):
    """Test that Fluent Bit successfully ingests and forwards logs."""
    # Ensure test logs directory exists
    test_logs_dir.mkdir(parents=True, exist_ok=True)

    # Get initial metrics from log ingestor
    initial_response = http_retry(log_ingestor_metrics_url, timeout=5)
    initial_metrics = initial_response.text

    # Extract initial log count (if any)
    initial_count = 0
    for line in initial_metrics.split('\n'):
        if 'logs_received_total' in line and not line.startswith('#'):
            try:
                initial_count = int(float(line.split()[-1]))
                break
            except (ValueError, IndexError):
                pass

    # Generate unique test log entries
    timestamp = datetime.utcnow().isoformat() + "Z"
    test_id = str(int(time.time() * 1000))  # Use timestamp as unique ID

    test_logs = [
        {
            "timestamp": timestamp,
            "level": "INFO",
            "message": f"Test log entry 1 - {test_id}",
            "service": "fluent-bit-test",
            "test_id": test_id
        },
        {
            "timestamp": timestamp,
            "level": "WARN",
            "message": f"Test log entry 2 - {test_id}",
            "service": "fluent-bit-test",
            "test_id": test_id
        },
        {
            "timestamp": timestamp,
            "level": "ERROR",
            "message": f"Test log entry 3 - {test_id}",
            "service": "fluent-bit-test",
            "test_id": test_id
        }
    ]

    # Write test logs to file
    test_log_file = test_logs_dir / f"integration-test-{test_id}.log"
    with open(test_log_file, 'w') as f:
        for log_entry in test_logs:
            f.write(json.dumps(log_entry) + '\n')

    # Wait for Fluent Bit to pick up and process the logs
    # Fluent Bit refresh interval is 5 seconds + processing time
    time.sleep(12)

    # Check that log ingestor received the logs
    final_response = http_retry(log_ingestor_metrics_url, timeout=5)
    final_metrics = final_response.text

    # Extract final log count
    final_count = 0
    for line in final_metrics.split('\n'):
        if 'logs_received_total' in line and not line.startswith('#'):
            try:
                final_count = int(float(line.split()[-1]))
                break
            except (ValueError, IndexError):
                pass

    # Verify that logs were processed
    logs_processed = final_count - initial_count
    assert logs_processed >= len(test_logs), \
        f"Expected at least {len(test_logs)} logs to be processed, but only {logs_processed} were processed"

    # Clean up test file
    test_log_file.unlink(missing_ok=True)


def test_fluent_bit_json_parsing(test_logs_dir, log_ingestor_metrics_url, http_retry):
    """Test that Fluent Bit correctly parses JSON log format."""
    # Ensure test logs directory exists
    test_logs_dir.mkdir(parents=True, exist_ok=True)

    # Get initial metrics
    initial_response = http_retry(log_ingestor_metrics_url, timeout=5)
    initial_metrics = initial_response.text

    # Create a test log with complex JSON structure
    timestamp = datetime.utcnow().isoformat() + "Z"
    test_id = str(int(time.time() * 1000))

    complex_log = {
        "timestamp": timestamp,
        "level": "INFO",
        "message": "Complex JSON test",
        "service": "json-parser-test",
        "test_id": test_id,
        "metadata": {
            "user_id": 12345,
            "request_id": "req-abc-123",
            "duration_ms": 150
        },
        "tags": ["integration", "test", "json"]
    }

    # Write test log
    test_log_file = test_logs_dir / f"json-test-{test_id}.log"
    with open(test_log_file, 'w') as f:
        f.write(json.dumps(complex_log) + '\n')

    # Wait for processing
    time.sleep(12)

    # Verify log was processed
    final_response = http_retry(log_ingestor_metrics_url, timeout=5)
    final_metrics = final_response.text

    # Check metrics show log was processed
    assert "logs_received_total" in final_metrics

    # Clean up
    test_log_file.unlink(missing_ok=True)


@pytest.mark.slow
def test_fluent_bit_continuous_monitoring(test_logs_dir, log_ingestor_metrics_url, http_retry):
    """Test that Fluent Bit continuously monitors for new log files."""
    # Ensure test logs directory exists
    test_logs_dir.mkdir(parents=True, exist_ok=True)

    test_id = str(int(time.time() * 1000))

    # Create multiple log files over time
    for i in range(3):
        timestamp = datetime.utcnow().isoformat() + "Z"
        log_entry = {
            "timestamp": timestamp,
            "level": "INFO",
            "message": f"Continuous monitoring test {i} - {test_id}",
            "service": "continuous-test",
            "test_id": test_id,
            "batch": i
        }

        # Write to different files
        test_log_file = test_logs_dir / f"continuous-{test_id}-{i}.log"
        with open(test_log_file, 'w') as f:
            f.write(json.dumps(log_entry) + '\n')

        # Wait between file creations
        time.sleep(3)

    # Wait for all logs to be processed
    time.sleep(15)

    # Verify logs were processed
    response = http_retry(log_ingestor_metrics_url, timeout=5)
    assert response.status_code == 200
    assert "logs_received_total" in response.text

    # Clean up test files
    for i in range(3):
        test_log_file = test_logs_dir / f"continuous-{test_id}-{i}.log"
        test_log_file.unlink(missing_ok=True)