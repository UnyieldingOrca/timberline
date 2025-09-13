"""
Log data generator for integration tests.
Generates various types of log data for testing the complete pipeline.
"""

import json
import os
import time
import random
from datetime import datetime, timedelta, UTC
from typing import List, Dict, Any
from pathlib import Path


class LogGenerator:
    """Generates test log data in various formats for integration testing."""

    def __init__(self, output_dir: str = "test-logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate_all_test_logs(self) -> None:
        """Generate all types of test logs."""
        self.generate_application_logs()
        self.generate_structured_logs()
        self.generate_kubernetes_logs()
        self.generate_mixed_format_logs()
        self.generate_high_volume_logs()
        self.generate_special_characters_logs()

    def generate_application_logs(self) -> Path:
        """Generate application error logs."""
        log_file = self.output_dir / "app-errors.log"

        logs = [
            "2024-01-15T10:30:45.123Z ERROR [auth-service] Failed to authenticate user: invalid credentials",
            "2024-01-15T10:31:02.456Z WARN [auth-service] Rate limit approaching for IP 192.168.1.100",
            "2024-01-15T10:31:15.789Z FATAL [database] Connection pool exhausted, cannot serve requests",
            "2024-01-15T10:31:30.012Z ERROR [payment-service] Payment processing failed: insufficient funds",
            "2024-01-15T10:32:45.345Z ERROR [order-service] Order validation failed: invalid product ID",
            "2024-01-15T10:33:00.678Z WARN [cache-service] Cache miss rate exceeding threshold: 85%",
            "2024-01-15T10:33:15.901Z ERROR [notification-service] Failed to send email: SMTP timeout"
        ]

        with open(log_file, 'w') as f:
            f.write('\n'.join(logs) + '\n')

        return log_file

    def generate_structured_logs(self) -> Path:
        """Generate JSON structured logs."""
        log_file = self.output_dir / "structured-logs.log"

        logs = [
            {
                "timestamp": "2024-01-15T10:30:45Z",
                "level": "ERROR",
                "service": "api-gateway",
                "message": "Request timeout",
                "request_id": "req-123",
                "duration": 5000
            },
            {
                "timestamp": "2024-01-15T10:31:00Z",
                "level": "WARN",
                "service": "user-service",
                "message": "Slow query detected",
                "query_duration": 2500,
                "table": "users"
            },
            {
                "timestamp": "2024-01-15T10:31:15Z",
                "level": "FATAL",
                "service": "payment-gateway",
                "message": "Circuit breaker opened",
                "error_rate": 0.85,
                "threshold": 0.8
            },
            {
                "timestamp": "2024-01-15T10:31:30Z",
                "level": "ERROR",
                "service": "inventory",
                "message": "Stock level critical",
                "product_id": "prod-456",
                "current_stock": 2,
                "threshold": 10
            },
            {
                "timestamp": "2024-01-15T10:31:45Z",
                "level": "INFO",
                "service": "analytics",
                "message": "Report generated",
                "report_type": "daily_sales",
                "records_processed": 15000
            }
        ]

        with open(log_file, 'w') as f:
            for log in logs:
                f.write(json.dumps(log) + '\n')

        return log_file

    def generate_kubernetes_logs(self) -> Path:
        """Generate Kubernetes-style logs."""
        log_file = self.output_dir / "k8s-app.log"

        logs = [
            "I0115 10:30:45.123456       1 main.go:45] Starting application server on port 8080",
            "E0115 10:31:00.234567       1 handler.go:123] HTTP 500: Internal server error processing request /api/users",
            "W0115 10:31:15.345678       1 metrics.go:67] Metrics endpoint /metrics responding slowly",
            "E0115 10:31:30.456789       1 database.go:234] Database query failed: connection refused",
            "F0115 10:31:45.567890       1 server.go:89] Failed to bind to port 8080: address already in use"
        ]

        with open(log_file, 'w') as f:
            f.write('\n'.join(logs) + '\n')

        return log_file

    def generate_mixed_format_logs(self) -> Path:
        """Generate mixed format logs with various severity levels."""
        log_file = self.output_dir / "mixed-format.log"

        logs = [
            "Jan 15 10:30:45 host01 app[1234]: INFO: Application started successfully",
            "Jan 15 10:31:00 host01 app[1234]: WARN: Configuration file not found, using defaults",
            "Jan 15 10:31:15 host01 app[1234]: ERROR: Failed to connect to external service",
            "Jan 15 10:31:30 host01 app[1234]: DEBUG: Processing request ID: abc123",
            "2024-01-15T10:32:00Z [ERROR] Database connection lost, retrying...",
            "[FATAL] 2024-01-15 10:32:15: Critical system failure detected",
            "ERROR: 2024-01-15T10:32:30.000Z - Memory usage exceeding limits",
            "WARN 10:32:45 - Disk space running low: 5% remaining"
        ]

        with open(log_file, 'w') as f:
            f.write('\n'.join(logs) + '\n')

        return log_file

    def generate_high_volume_logs(self, count: int = 1000) -> Path:
        """Generate high-volume logs for performance testing."""
        log_file = self.output_dir / "high-volume.log"

        levels = ["ERROR", "WARN", "INFO", "DEBUG"]
        services = [f"load-test-service-{i}" for i in range(10)]

        with open(log_file, 'w') as f:
            for i in range(count):
                timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z"
                level = random.choice(levels)
                service = random.choice(services)
                random_data = ''.join(random.choices('0123456789abcdef', k=32))
                message = f"Load test message {i+1} with random data: {random_data}"

                log_line = f"{timestamp} {level} [{service}] {message}"
                f.write(log_line + '\n')

        return log_file

    def generate_special_characters_logs(self) -> Path:
        """Generate logs with various character encodings and special characters."""
        log_file = self.output_dir / "special-chars.log"

        logs = [
            '2024-01-15T10:30:45Z ERROR [api] Invalid JSON payload: {"user": "José María", "email": "jose@example.com"}',
            "2024-01-15T10:31:00Z WARN [parser] Special characters detected: ñáéíóú çüß αβγ 中文 日本語",
            "2024-01-15T10:31:15Z ERROR [validation] SQL injection attempt detected: '; DROP TABLE users; --",
            "2024-01-15T10:31:30Z FATAL [security] XSS attempt: <script>alert('xss')</script>"
        ]

        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(logs) + '\n')

        return log_file

    def generate_simple_test_log(self) -> Path:
        """Generate a simple test log for basic testing."""
        log_file = self.output_dir / "application.log"
        current_time = datetime.now(UTC).strftime("%Y-%m-%d")
        current_timestamp = datetime.now(UTC).strftime("%H:%M:%S")

        logs = [
            f"2024-{current_time}T{current_timestamp}Z ERROR Database connection failed: timeout after 30s",
            f"2024-{current_time}T{current_timestamp}Z WARN High memory usage detected: 85%",
            f"2024-{current_time}T{current_timestamp}Z INFO Application started successfully",
            f"2024-{current_time}T{current_timestamp}Z ERROR Failed to process user request: invalid token"
        ]

        with open(log_file, 'w') as f:
            f.write('\n'.join(logs) + '\n')

        return log_file

    def generate_log_entries_for_api(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate log entries for direct API testing."""
        levels = ["ERROR", "WARN", "INFO", "DEBUG"]
        services = ["api-gateway", "user-service", "payment-service", "database", "cache"]

        log_entries = []
        base_time = int(time.time() * 1000)  # Current time in milliseconds

        for i in range(count):
            log_entry = {
                "timestamp": base_time + (i * 1000),  # 1 second intervals
                "message": f"Test log message {i+1}: {random.choice(['Connection failed', 'Processing request', 'Cache miss', 'Authentication error', 'Query timeout'])}",
                "source": random.choice(services),
                "metadata": {
                    "level": random.choice(levels),
                    "container_name": f"test-container-{i}",
                    "namespace": "test-namespace",
                    "pod_name": f"test-pod-{i}",
                    "service_name": random.choice(services),
                    "node_name": "test-node",
                    "labels": {"app": "test-app", "version": "v1.0"}
                }
            }
            log_entries.append(log_entry)

        return log_entries

    def cleanup(self) -> None:
        """Clean up generated test logs."""
        if self.output_dir.exists():
            for log_file in self.output_dir.glob("*.log"):
                log_file.unlink()