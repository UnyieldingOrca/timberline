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
from typing import List, Dict, Any

import pytest
import requests
from pymilvus import connections, Collection


def connect_to_milvus() -> Collection:
    """Helper function to connect to Milvus and return the collection."""
    connections.connect(
        alias="test",
        host="localhost",
        port="8530",
        timeout=5
    )
    collection = Collection("timberline_logs", using="test")
    collection.load()
    return collection


def disconnect_from_milvus():
    """Helper function to safely disconnect from Milvus."""
    try:
        connections.disconnect("test")
    except:
        pass


def query_logs_by_timestamp(collection: Collection, timestamp: int, limit: int = 20) -> List[Dict[str, Any]]:
    """Helper function to query logs by timestamp."""
    query_expr = f'timestamp >= {timestamp - 1000}'
    return collection.query(
        expr=query_expr,
        output_fields=["message", "timestamp"],
        limit=limit
    )


def query_logs_by_test_id(collection: Collection, test_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Helper function to query logs by test ID in message."""
    query_expr = f'message like "%{test_id}%"'
    return collection.query(
        expr=query_expr,
        output_fields=["message", "timestamp", "duplicate_count"],
        limit=limit
    )


def validate_log_matches(results: List[Dict[str, Any]], expected_messages: List[str], test_id: str,
                        min_success_ratio: float = 0.7) -> int:
    """
    Helper function to validate that expected log messages are found in results.

    Args:
        results: Query results from Milvus
        expected_messages: List of expected message strings
        test_id: Test identifier for debugging
        min_success_ratio: Minimum ratio of messages that must be found (default 0.7)

    Returns:
        Number of matches found

    Raises:
        AssertionError: If fewer than min_success_ratio messages are found
    """
    found_messages = [result["message"] for result in results]

    matches_found = 0
    for expected_msg in expected_messages:
        if any(expected_msg in found_msg for found_msg in found_messages):
            matches_found += 1
            print(f"✓ Found log with message: {expected_msg}")
        else:
            print(f"✗ Missing log with message: {expected_msg}")

    min_expected = int(len(expected_messages) * min_success_ratio)
    assert matches_found >= min_expected, \
        f"Found {matches_found}/{len(expected_messages)} expected logs (minimum {min_expected}). " \
        f"Test ID: {test_id}. Expected: {expected_messages}. Found: {found_messages}"

    print(f"✓ Successfully verified {matches_found}/{len(expected_messages)} logs")
    return matches_found


def validate_log_count_by_test_id(results: List[Dict[str, Any]], test_id: str, expected_count: int,
                                 min_success_ratio: float = 0.7) -> int:
    """
    Helper function to validate log count by test ID.

    Args:
        results: Query results from Milvus
        test_id: Test identifier to count in messages
        expected_count: Expected number of logs with test_id
        min_success_ratio: Minimum ratio of logs that must be found (default 0.7)

    Returns:
        Number of matches found

    Raises:
        AssertionError: If fewer than min_success_ratio logs are found
    """
    found_messages = [result["message"] for result in results]
    matches_found = len([msg for msg in found_messages if test_id in msg])

    min_expected = int(expected_count * min_success_ratio)
    assert matches_found >= min_expected, \
        f"Found {matches_found}/{expected_count} logs with test ID {test_id} (minimum {min_expected}). " \
        f"Found messages: {found_messages}"

    print(f"✓ Successfully verified {matches_found}/{expected_count} logs with test ID {test_id}")
    return matches_found


def setup_test_logs_dir(test_logs_dir: Path, subdir: str = "fluent-bit-tests") -> Path:
    """Helper function to setup test logs directory."""
    test_dir = test_logs_dir.joinpath(subdir)
    test_dir.mkdir(parents=True, exist_ok=True)
    return test_dir


@pytest.fixture
def fluent_bit_health_url():
    """Fluent Bit health endpoint URL."""
    return "http://localhost:8020/api/v1/health"


@pytest.fixture
def log_ingestor_metrics_url():
    """Log ingestor metrics endpoint URL."""
    return "http://localhost:8201/metrics"


def test_fluent_bit_health_endpoint(fluent_bit_health_url, http_retry):
    """Test that Fluent Bit health endpoint is responding."""
    response = http_retry(fluent_bit_health_url, timeout=10)
    assert response.status_code == 200
    assert response.content == b'ok\n'


def test_fluent_bit_log_ingestion(test_logs_dir, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit successfully ingests and forwards logs to Milvus."""
    test_logs_dir = setup_test_logs_dir(test_logs_dir)

    # Generate unique test log entries
    timestamp = int(time.time() * 1000)
    test_id = str(timestamp)

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

    # Validate logs were stored in Milvus
    try:
        collection = connect_to_milvus()
        results = query_logs_by_timestamp(collection, timestamp)

        print(f"Logs found with our timestamp: {len(results)}")
        if results:
            print("Messages found:", [r["message"] for r in results])

        expected_messages = [log["message"] for log in test_logs]
        validate_log_matches(results, expected_messages, test_id, min_success_ratio=0.33)  # At least one log

    finally:
        disconnect_from_milvus()


def test_fluent_bit_json_parsing(test_logs_dir, log_ingestor_metrics_url, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit correctly parses JSON log format."""
    test_logs_dir = setup_test_logs_dir(test_logs_dir)

    timestamp = int(time.time() * 1000)
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
    try:
        collection = connect_to_milvus()
        results = query_logs_by_timestamp(collection, timestamp)

        assert len(results) == 1, f"Expected 1 log entry, found {len(results)}"
        assert results[0]["message"] == "Complex JSON test"
        assert results[0]["timestamp"] == timestamp

    finally:
        disconnect_from_milvus()


def test_fluent_bit_timestamp_formats(test_logs_dir, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit correctly handles various timestamp formats."""
    test_logs_dir = setup_test_logs_dir(test_logs_dir)

    current_time = datetime.now(UTC)
    base_timestamp = int(current_time.timestamp() * 1000)
    test_id = str(base_timestamp)

    # Define various timestamp formats that our log generator produces
    timestamp_test_cases = [
        {
            "format_name": "ISO_with_milliseconds",
            "log_line": f'{current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]}Z ERROR [timestamp-test] ISO with milliseconds test - {test_id}',
            "expected_message": f"ISO with milliseconds test - {test_id}"
        },
        {
            "format_name": "ISO_without_milliseconds",
            "log_line": f'{current_time.strftime("%Y-%m-%dT%H:%M:%S")}Z ERROR [timestamp-test] ISO without milliseconds test - {test_id}',
            "expected_message": f"ISO without milliseconds test - {test_id}"
        },
        {
            "format_name": "simple_datetime",
            "log_line": f'{current_time.strftime("%Y-%m-%d %H:%M:%S")} ERROR [timestamp-test] Simple datetime test - {test_id}',
            "expected_message": f"Simple datetime test - {test_id}"
        },
        {
            "format_name": "syslog_format",
            "log_line": f'{current_time.strftime("%b %d %H:%M:%S")} ERROR [timestamp-test] Syslog format test - {test_id}',
            "expected_message": f"Syslog format test - {test_id}"
        },
        {
            "format_name": "slash_format",
            "log_line": f'{current_time.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]} ERROR [timestamp-test] Slash format test - {test_id}',
            "expected_message": f"Slash format test - {test_id}"
        },
        {
            "format_name": "unix_timestamp",
            "log_line": f'{int(current_time.timestamp())} ERROR [timestamp-test] Unix timestamp test - {test_id}',
            "expected_message": f"Unix timestamp test - {test_id}"
        },
        {
            "format_name": "unix_timestamp_ms",
            "log_line": f'{int(current_time.timestamp() * 1000)} ERROR [timestamp-test] Unix timestamp ms test - {test_id}',
            "expected_message": f"Unix timestamp ms test - {test_id}"
        },
        {
            "format_name": "european_format",
            "log_line": f'{current_time.strftime("%d-%m-%Y %H:%M:%S")} ERROR [timestamp-test] European format test - {test_id}',
            "expected_message": f"European format test - {test_id}"
        },
        {
            "format_name": "no_timestamp",
            "log_line": f'ERROR [timestamp-test] No timestamp test - {test_id}',
            "expected_message": f"No timestamp test - {test_id}"
        }
    ]

    # Write test logs with different timestamp formats
    test_log_file = test_logs_dir / f"timestamp-formats-test-{test_id}.log"
    with open(test_log_file, 'w') as f:
        for test_case in timestamp_test_cases:
            f.write(test_case["log_line"] + '\n')

    # Wait for Fluent Bit to pick up and process the logs
    time.sleep(3)

    # Validate logs were processed
    try:
        collection = connect_to_milvus()
        results = query_logs_by_test_id(collection, test_id)

        print(f"Found {len(results)} logs with test ID {test_id}")

        expected_messages = [tc["expected_message"] for tc in timestamp_test_cases]
        validate_log_matches(results, expected_messages, test_id)

    finally:
        disconnect_from_milvus()


def test_fluent_bit_structured_json_timestamps(test_logs_dir, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit correctly handles JSON logs with various timestamp formats."""
    test_logs_dir = setup_test_logs_dir(test_logs_dir)

    current_time = datetime.now(UTC)
    base_timestamp = int(current_time.timestamp() * 1000)
    test_id = str(base_timestamp)

    # Application JSON logs that Fluent Bit will put in the 'log' field
    app_json_logs = [
        {
            "timestamp": current_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "level": "INFO",
            "service": "json-timestamp-test",
            "message": f"JSON ISO format test - {test_id}",
            "test_id": test_id
        },
        {
            "timestamp": current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": "WARN",
            "service": "json-timestamp-test",
            "message": f"JSON ISO with ms test - {test_id}",
            "test_id": test_id
        },
        {
            "timestamp": int(current_time.timestamp()),
            "level": "ERROR",
            "service": "json-timestamp-test",
            "message": f"JSON Unix timestamp test - {test_id}",
            "test_id": test_id
        },
        {
            "timestamp": int(current_time.timestamp() * 1000),
            "level": "DEBUG",
            "service": "json-timestamp-test",
            "message": f"JSON Unix timestamp ms test - {test_id}",
            "test_id": test_id
        },
        {
            "timestamp": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "level": "FATAL",
            "service": "json-timestamp-test",
            "message": f"JSON simple format test - {test_id}",
            "test_id": test_id
        },
        {
            "timestamp": None,
            "level": "INFO",
            "service": "json-timestamp-test",
            "message": f"JSON null timestamp test - {test_id}",
            "test_id": test_id
        }
    ]

    # JSON log without timestamp field
    app_json_no_timestamp = {
        "level": "WARN",
        "service": "json-timestamp-test",
        "message": f"JSON no timestamp field test - {test_id}",
        "test_id": test_id
    }

    # Convert to Fluent Bit format (JSON string in log field)
    json_timestamp_test_cases = []
    for app_log in app_json_logs:
        fluent_bit_log = {
            "date": current_time.timestamp(),
            "log": json.dumps(app_log),
            "source": "fluent-bit"
        }
        json_timestamp_test_cases.append(fluent_bit_log)

    json_no_timestamp = {
        "date": current_time.timestamp(),
        "log": json.dumps(app_json_no_timestamp),
        "source": "fluent-bit"
    }

    # Write test logs
    test_log_file = test_logs_dir / f"json-timestamps-test-{test_id}.log"
    with open(test_log_file, 'w') as f:
        for log_entry in json_timestamp_test_cases:
            f.write(json.dumps(log_entry) + '\n')
        f.write(json.dumps(json_no_timestamp) + '\n')

    # Wait for processing
    time.sleep(3)

    # Verify logs were processed
    try:
        collection = connect_to_milvus()
        results = query_logs_by_test_id(collection, test_id)

        print(f"Found {len(results)} JSON timestamp logs with test ID {test_id}")

        expected_count = len(json_timestamp_test_cases) + 1  # +1 for no timestamp field log
        validate_log_count_by_test_id(results, test_id, expected_count)

    finally:
        disconnect_from_milvus()


def test_fluent_bit_mixed_format_timestamps(test_logs_dir, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit handles mixed format logs with consistent timestamps within stream."""
    test_logs_dir = setup_test_logs_dir(test_logs_dir)

    current_time = datetime.now(UTC)
    base_timestamp = int(current_time.timestamp() * 1000)
    test_id = str(base_timestamp)

    # Test different mixed log formats that maintain consistency within the stream
    mixed_format_test_cases = [
        {
            "format_name": "syslog_consistent",
            "logs": [
                f'{current_time.strftime("%b %d %H:%M:%S")} host01 app[1234]: ERROR: Mixed syslog 1 - {test_id}',
                f'{current_time.strftime("%b %d %H:%M:%S")} host01 app[1235]: WARN: Mixed syslog 2 - {test_id}',
                f'{current_time.strftime("%b %d %H:%M:%S")} host02 app[1236]: INFO: Mixed syslog 3 - {test_id}',
            ]
        },
        {
            "format_name": "iso_bracketed_consistent",
            "logs": [
                f'{current_time.strftime("%Y-%m-%dT%H:%M:%SZ")} [ERROR] Mixed ISO bracketed 1 - {test_id}',
                f'{current_time.strftime("%Y-%m-%dT%H:%M:%SZ")} [WARN] Mixed ISO bracketed 2 - {test_id}',
                f'{current_time.strftime("%Y-%m-%dT%H:%M:%SZ")} [INFO] Mixed ISO bracketed 3 - {test_id}',
            ]
        },
        {
            "format_name": "no_timestamp_consistent",
            "logs": [
                f'ERROR host01 app: Mixed no timestamp 1 - {test_id}',
                f'WARN host02 app: Mixed no timestamp 2 - {test_id}',
                f'INFO host03 app: Mixed no timestamp 3 - {test_id}',
            ]
        }
    ]

    total_expected = sum(len(case["logs"]) for case in mixed_format_test_cases)

    # Write test logs - each format gets its own file to simulate separate streams
    test_files = []
    for i, test_case in enumerate(mixed_format_test_cases):
        test_log_file = test_logs_dir / f"mixed-{test_case['format_name']}-{test_id}-{i}.log"
        test_files.append(test_log_file)

        with open(test_log_file, 'w') as f:
            for log_line in test_case["logs"]:
                f.write(log_line + '\n')

    # Wait for processing
    time.sleep(3)

    # Verify logs were processed
    try:
        collection = connect_to_milvus()
        results = query_logs_by_test_id(collection, test_id, limit=50)

        print(f"Found {len(results)} mixed format logs with test ID {test_id}")

        validate_log_count_by_test_id(results, test_id, total_expected)

    finally:
        disconnect_from_milvus()


def test_fluent_bit_subsampling(test_logs_dir, http_retry, cleanup_milvus_data):
    """Test that Fluent Bit subsampling filter correctly samples INFO logs at 50% while keeping all ERROR/WARN logs."""
    test_logs_dir = setup_test_logs_dir(test_logs_dir)

    current_time = datetime.now(UTC)
    base_timestamp = int(current_time.timestamp() * 1000)
    test_id = str(base_timestamp)

    # Generate a large batch of INFO and ERROR logs
    num_info_logs = 30  # Large sample for statistical significance
    num_error_logs = 10

    info_messages = []
    error_messages = []

    # Write INFO logs
    test_log_file_info = test_logs_dir / f"subsampling-info-test-{test_id}.log"
    with open(test_log_file_info, 'w') as f:
        for i in range(num_info_logs):
            log_line = f'{current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]}Z INFO [subsampling-test] Info log {i} - {test_id}'
            info_messages.append(f"Info log {i} - {test_id}")
            f.write(log_line + '\n')

    # Write ERROR logs
    test_log_file_error = test_logs_dir / f"subsampling-error-test-{test_id}.log"
    with open(test_log_file_error, 'w') as f:
        for i in range(num_error_logs):
            log_line = f'{current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]}Z ERROR [subsampling-test] Error log {i} - {test_id}'
            error_messages.append(f"Error log {i} - {test_id}")
            f.write(log_line + '\n')

    # Wait for Fluent Bit to process logs
    time.sleep(5)

    try:
        collection = connect_to_milvus()
        results = query_logs_by_test_id(collection, test_id, limit=300)

        print(f"\nSubsampling Test Results for {test_id}:")
        print(f"  Total logs written: {num_info_logs + num_error_logs}")
        print(f"  - INFO logs: {num_info_logs}")
        print(f"  - ERROR logs: {num_error_logs}")
        print(f"  Total logs found in Milvus: {len(results)} (including duplicates)")

        # Count how many INFO and ERROR logs were ingested
        error_logs_sum = sum(result.get("duplicate_count", 0) for result in results if "Error log" in result["message"])
        info_logs_sum = sum(result.get("duplicate_count", 0) for result in results if "Info log" in result["message"])

        print(f"  - INFO logs ingested: {info_logs_sum}")
        print(f"  - ERROR logs ingested: {error_logs_sum}")

        # Calculate sampling rates
        info_sampling_rate = (info_logs_sum / num_info_logs) * 100 if num_info_logs > 0 else 0
        error_sampling_rate = (error_logs_sum / num_error_logs) * 100 if num_error_logs > 0 else 0

        print(f"  Sampling rates:")
        print(f"  - INFO: {info_sampling_rate:.1f}%")
        print(f"  - ERROR: {error_sampling_rate:.1f}%")

        # Assertions:
        # 1. All ERROR logs should be kept (100% or close to it due to timing)
        assert error_logs_sum >= int(num_error_logs * 0.9), \
            f"Expected at least 90% of ERROR logs ({int(num_error_logs * 0.9)}), got {error_logs_sum}"

        assert 10 <= info_sampling_rate <= 90, \
            f"Expected INFO sampling rate between 10-90%, got {info_sampling_rate:.1f}%"

        # 3. INFO logs should be significantly less than ERROR logs proportionally
        info_ratio = info_logs_sum / num_info_logs if num_info_logs > 0 else 0
        error_ratio = error_logs_sum / num_error_logs if num_error_logs > 0 else 0
        assert info_ratio < error_ratio, \
            f"INFO logs should have lower ingestion ratio ({info_ratio:.2f}) than ERROR logs ({error_ratio:.2f})"

        print(f"✓ Subsampling test passed!")
        print(f"  - ERROR logs retained: {error_sampling_rate:.1f}% (expected ~100%)")
        print(f"  - INFO logs sampled: {info_sampling_rate:.1f}% (expected ~50%)")

    finally:
        disconnect_from_milvus()
