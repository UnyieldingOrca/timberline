"""
Helper functions for integration tests to support streaming log ingestion.
"""

import json
import requests
from typing import List, Dict, Any


def ingest_logs_via_stream(ingestor_url: str, log_entries: List[Dict[str, Any]], timeout: int = 30) -> requests.Response:
    """
    Send log entries to the streaming endpoint using JSON Lines format.

    Args:
        ingestor_url: Base URL of the log ingestor service
        log_entries: List of log entry dictionaries
        timeout: Request timeout in seconds

    Returns:
        requests.Response object
    """
    # Convert log entries to JSON Lines format
    json_lines = []
    for entry in log_entries:
        json_lines.append(json.dumps(entry))

    # Join with newlines to create JSON Lines format
    data = '\n'.join(json_lines)

    # Send to streaming endpoint
    headers = {
        'Content-Type': 'application/x-ndjson'
    }

    response = requests.post(
        f"{ingestor_url}/api/v1/logs/stream",
        data=data,
        headers=headers,
        timeout=timeout
    )

    return response


def ingest_single_log_via_stream(ingestor_url: str, log_entry: Dict[str, Any], timeout: int = 30) -> requests.Response:
    """
    Send a single log entry to the streaming endpoint.

    Args:
        ingestor_url: Base URL of the log ingestor service
        log_entry: Single log entry dictionary
        timeout: Request timeout in seconds

    Returns:
        requests.Response object
    """
    return ingest_logs_via_stream(ingestor_url, [log_entry], timeout)


def convert_batch_to_stream_format(batch_payload: Dict[str, Any]) -> str:
    """
    Convert old batch format to streaming JSON Lines format.

    Args:
        batch_payload: Dictionary with 'logs' key containing list of log entries

    Returns:
        String in JSON Lines format
    """
    if 'logs' not in batch_payload:
        return ""

    json_lines = []
    for entry in batch_payload['logs']:
        json_lines.append(json.dumps(entry))

    return '\n'.join(json_lines)