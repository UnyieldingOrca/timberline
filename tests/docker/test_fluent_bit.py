"""
Fluent Bit integration tests for Timberline Docker environment.
Tests log collection, parsing, and forwarding to log-ingestor.
"""

import json
import os
import tempfile
import time
from datetime import datetime, UTC
from pathlib import Path

import pytest
import requests
from pymilvus import connections, Collection


# test_logs_dir fixture is now provided by conftest.py


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
    # Fluent Bit health endpoint returns JSON with version info
    import json
    health_data = json.loads(response.text)
    assert "fluent-bit" in health_data, "Health response should contain fluent-bit info"
    assert "version" in health_data["fluent-bit"], "Health response should contain version"


def test_fluent_bit_log_ingestion(test_logs_dir, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit successfully ingests and forwards logs to Milvus."""
    # Ensure test logs directory exists
    test_logs_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique test log entries
    timestamp = int(time.time() * 1000)  # Unix timestamp in milliseconds
    test_id = str(timestamp)  # Use timestamp as unique ID

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
    time.sleep(3)

    # Connect to Milvus and query for our test logs
    try:
        connections.connect(
            alias="test",
            host="localhost",
            port="19530",
            timeout=5
        )

        collection = Collection("timberline_logs", using="test")
        collection.load()

        # Query for logs with our test timestamp (should be very recent)
        query_expr = f'timestamp >= {timestamp - 1000}'  # Within 1 second of our test timestamp
        results = collection.query(
            expr=query_expr,
            output_fields=["message", "timestamp"],
            limit=20
        )

        print(f"Logs found with our timestamp: {len(results)}")
        if results:
            print("Messages found:", [r["message"] for r in results])

        # Verify that at least some of our test logs were stored
        found_messages = [result["message"] for result in results]
        expected_messages = [log["message"] for log in test_logs]

        matches_found = 0
        for expected_msg in expected_messages:
            if any(expected_msg in found_msg for found_msg in found_messages):
                matches_found += 1

        # We should find at least one of our test logs
        assert matches_found > 0, \
            f"None of our test logs found. Expected: {expected_messages}. Found: {found_messages}"

        print(f"✓ Successfully verified {matches_found}/{len(expected_messages)} test logs stored in Milvus")

    finally:
        try:
            connections.disconnect("test")
        except:
            pass

    # Clean up test file
    test_log_file.unlink(missing_ok=True)


def test_fluent_bit_json_parsing(test_logs_dir, log_ingestor_metrics_url, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit correctly parses JSON log format."""
    # Ensure test logs directory exists
    test_logs_dir.mkdir(parents=True, exist_ok=True)

    # Create a test log with complex JSON structure
    timestamp = int(time.time() * 1000)  # Unix timestamp in milliseconds
    test_id = str(timestamp)

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
    time.sleep(3)

    # Verify log was processed
    # Connect to Milvus and query for our test logs
    try:
        connections.connect(
            alias="test",
            host="localhost",
            port="19530",
            timeout=5
        )

        collection = Collection("timberline_logs", using="test")
        collection.load()

        # Query for logs with our test timestamp (should be very recent)
        query_expr = f'timestamp >= {timestamp - 1000}'  # Within 1 second of our test timestamp
        results = collection.query(
            expr=query_expr,
            output_fields=["message", "timestamp"],
            limit=20
        )

        assert len(results) == 1, f"Expected 1 log entry, found {len(results)}"
        assert results[0]["message"] == "Complex JSON test"
        assert results[0]["timestamp"] == timestamp

    finally:
        try:
            connections.disconnect("test")
        except:
            pass

    # Clean up
    test_log_file.unlink(missing_ok=True)
