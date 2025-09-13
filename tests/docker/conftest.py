"""
Pytest configuration and fixtures for Docker integration tests.
"""

import pytest
import os
from pathlib import Path
from .log_generator import LogGenerator


@pytest.fixture(scope="session")
def test_logs_dir():
    """Provide test logs directory path."""
    return Path("test-logs")


@pytest.fixture(scope="session")
def log_generator(test_logs_dir):
    """Create and configure log generator."""
    generator = LogGenerator(output_dir=str(test_logs_dir))
    return generator


@pytest.fixture(scope="session", autouse=True)
def setup_test_logs(log_generator, test_logs_dir):
    """Setup test logs before running tests."""
    # Ensure test logs directory exists
    test_logs_dir.mkdir(exist_ok=True)

    # Generate all test logs
    log_generator.generate_all_test_logs()

    yield

    # Cleanup after tests complete
    # Optionally keep logs for debugging: comment out the cleanup line
    # log_generator.cleanup()


