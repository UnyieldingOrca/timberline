"""
Log Ingestor API tests for Timberline Kind deployment.

Tests that verify the Log Ingestor REST API business logic.
"""

import pytest
import json
import time


@pytest.mark.connectivity
class TestLogIngestorAPI:
    """Test Log Ingestor API endpoints."""

    def test_log_ingestor_accepts_json_lines(
        self,
        service_urls,
        http_retry,
        sample_log_entries,
        wait_for_service_ready
    ):
        """Test Log Ingestor accepts logs in JSON Lines format."""
        health_url = f"{service_urls['log_ingestor']}/api/v1/healthz"
        wait_for_service_ready(health_url)

        url = f"{service_urls['log_ingestor']}/api/v1/logs/stream"

        # Convert logs to JSON Lines format
        log_lines = "\n".join(json.dumps(log) for log in sample_log_entries)

        response = http_retry(
            url,
            method="POST",
            data=log_lines,
            headers={"Content-Type": "application/x-ndjson"},
            timeout=30
        )

        assert response.status_code in [200, 201, 202], \
            f"Unexpected status: {response.status_code}, response: {response.text}"


    def test_log_ingestor_batch_processing(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test Log Ingestor can handle batch log submissions."""
        health_url = f"{service_urls['log_ingestor']}/api/v1/healthz"
        wait_for_service_ready(health_url)

        url = f"{service_urls['log_ingestor']}/api/v1/logs/stream"

        # Generate a batch of logs
        batch_size = 50
        logs = []
        for i in range(batch_size):
            logs.append({
                "timestamp": int(time.time() * 1000) + i,
                "message": f"Batch test log message {i}",
                "level": "INFO",
                "source": "batch-test"
            })

        log_lines = "\n".join(json.dumps(log) for log in logs)

        response = http_retry(
            url,
            method="POST",
            data=log_lines,
            headers={"Content-Type": "application/x-ndjson"},
            timeout=60
        )

        assert response.status_code in [200, 201, 202]

    def test_log_ingestor_handles_large_messages(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test Log Ingestor can handle large log messages."""
        health_url = f"{service_urls['log_ingestor']}/api/v1/healthz"
        wait_for_service_ready(health_url)

        url = f"{service_urls['log_ingestor']}/api/v1/logs/stream"

        # Create a large log message (but within reasonable limits)
        large_message = "A" * 5000  # 5KB message

        log_entry = {
            "timestamp": int(time.time() * 1000),
            "message": large_message,
            "level": "INFO",
            "source": "large-message-test"
        }

        response = http_retry(
            url,
            method="POST",
            data=json.dumps(log_entry),
            headers={"Content-Type": "application/x-ndjson"},
            timeout=30
        )

        assert response.status_code in [200, 201, 202]
