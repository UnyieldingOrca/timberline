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

        base_time = datetime.now(UTC)
        services = ["auth-service", "database", "payment-service", "order-service", "cache-service", "notification-service", "api-gateway", "user-service"]
        levels = ["ERROR", "WARN", "FATAL", "INFO"]

        error_templates = [
            ("ERROR", "auth-service", "Failed to authenticate user: invalid credentials"),
            ("WARN", "auth-service", "Rate limit approaching for IP {ip}"),
            ("FATAL", "database", "Connection pool exhausted, cannot serve requests"),
            ("ERROR", "payment-service", "Payment processing failed: {reason}"),
            ("ERROR", "order-service", "Order validation failed: {reason}"),
            ("WARN", "cache-service", "Cache miss rate exceeding threshold: {percent}%"),
            ("ERROR", "notification-service", "Failed to send email: {reason}"),
            ("ERROR", "api-gateway", "Request timeout after {timeout}ms"),
            ("ERROR", "user-service", "User lookup failed for ID: {user_id}"),
            ("WARN", "database", "Query execution time exceeded {timeout}ms"),
            ("ERROR", "payment-service", "Transaction declined: {reason}"),
            ("ERROR", "auth-service", "Token validation failed: {reason}"),
            ("FATAL", "cache-service", "Redis connection lost: {reason}"),
            ("ERROR", "order-service", "Inventory check failed for product {product_id}"),
            ("ERROR", "notification-service", "Push notification delivery failed: {reason}"),
            ("INFO", "auth-service", "User successfully authenticated"),
            ("INFO", "database", "Database connection established"),
            ("INFO", "payment-service", "Payment processed successfully"),
            ("INFO", "order-service", "Order created successfully"),
            ("INFO", "cache-service", "Cache warmed up successfully"),
            ("INFO", "notification-service", "Email sent successfully"),
            ("INFO", "api-gateway", "Request processed successfully"),
            ("INFO", "user-service", "User profile updated")
        ]

        payment_reasons = ["insufficient funds", "expired card", "invalid CVV", "card declined", "fraud detected"]
        order_reasons = ["invalid product ID", "out of stock", "invalid quantity", "price mismatch"]
        timeout_reasons = ["connection timeout", "read timeout", "gateway timeout", "upstream timeout"]
        auth_reasons = ["expired token", "malformed token", "signature mismatch", "insufficient privileges"]

        timestamp_formats = [
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z",  # ISO with milliseconds
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ"),                 # ISO without milliseconds
            lambda t: t.strftime("%Y-%m-%d %H:%M:%S"),                  # Simple datetime
            lambda t: t.strftime("%b %d %H:%M:%S"),                     # Syslog format
            lambda t: t.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3],          # Slash format with ms
            lambda t: str(int(t.timestamp())),                          # Unix timestamp
            lambda t: str(int(t.timestamp() * 1000)),                   # Unix timestamp ms
            lambda t: t.strftime("%d-%m-%Y %H:%M:%S"),                  # European format
        ]

        # Choose one timestamp format for this entire log file (consistency within stream)
        chosen_timestamp_format = random.choice(timestamp_formats)
        use_timestamps = random.random() > 0.15  # 15% chance this entire file has no timestamps

        logs = []
        for i in range(70):  # 10x the original 7 logs
            timestamp = base_time + timedelta(seconds=random.randint(0, 3600), microseconds=random.randint(0, 999999))

            level, service, template = random.choice(error_templates)

            # Fill in template variables
            message = template.format(
                ip=f"192.168.{random.randint(1,255)}.{random.randint(1,255)}",
                reason=random.choice(payment_reasons + order_reasons + timeout_reasons + auth_reasons),
                percent=random.randint(80, 95),
                timeout=random.randint(1000, 10000),
                user_id=f"usr-{random.randint(1000, 9999)}",
                product_id=f"prod-{random.randint(100, 999)}"
            )

            # Use consistent timestamp format for this file
            if use_timestamps:
                timestamp_str = chosen_timestamp_format(timestamp)
                log_line = f"{timestamp_str} {level} [{service}] {message}"
            else:
                log_line = f"{level} [{service}] {message}"

            logs.append((timestamp, log_line))

        logs.sort()  # Sort by timestamp

        with open(log_file, 'w') as f:
            for _, log_line in logs:
                f.write(log_line + '\n')

        return log_file

    def generate_structured_logs(self) -> Path:
        """Generate JSON structured logs."""
        log_file = self.output_dir / "structured-logs.log"

        base_time = datetime.now(UTC)
        services = ["api-gateway", "user-service", "payment-gateway", "inventory", "analytics", "auth-service", "notification", "order-processing"]
        levels = ["ERROR", "WARN", "FATAL", "INFO", "DEBUG"]
        tables = ["users", "orders", "products", "payments", "sessions", "inventory", "analytics"]
        report_types = ["daily_sales", "weekly_summary", "monthly_report", "user_activity", "inventory_status"]

        timestamp_formats = [
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ"),                 # ISO format
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z",   # ISO with milliseconds
            lambda t: t.isoformat() + "Z",                              # Python isoformat
            lambda t: str(int(t.timestamp())),                          # Unix timestamp
            lambda t: str(int(t.timestamp() * 1000)),                   # Unix timestamp ms
            lambda t: t.strftime("%Y-%m-%d %H:%M:%S"),                  # Simple format
        ]

        # Choose consistent timestamp handling for this entire JSON log file
        timestamp_mode = random.choice(["format", "none", "null"])
        if timestamp_mode == "format":
            chosen_timestamp_format = random.choice(timestamp_formats)

        logs = []
        for i in range(50):  # 10x the original 5 logs
            timestamp = base_time + timedelta(seconds=random.randint(0, 3600), microseconds=random.randint(0, 999999))

            service = random.choice(services)
            level = random.choice(levels)

            log_entry = {
                "level": level,
                "service": service,
                "request_id": f"req-{random.randint(1000, 9999)}-{random.randint(100, 999)}"
            }

            # Apply consistent timestamp handling for entire file
            if timestamp_mode == "format":
                log_entry["timestamp"] = chosen_timestamp_format(timestamp)
            elif timestamp_mode == "null":
                log_entry["timestamp"] = None
            # If "none", don't add timestamp field at all

            # Add service-specific fields based on service type with appropriate levels
            if service == "api-gateway":
                message_options = [
                    ("ERROR", "Request timeout"),
                    ("WARN", "Rate limit exceeded"),
                    ("ERROR", "Invalid route"),
                    ("FATAL", "Upstream service down"),
                    ("INFO", "Request processed successfully"),
                    ("DEBUG", "Route lookup completed")
                ]
                chosen_level, message = random.choice(message_options)
                log_entry["level"] = chosen_level
                log_entry.update({
                    "message": message,
                    "duration": random.randint(100, 10000),
                    "status_code": random.choice([200, 400, 404, 500, 502, 503]),
                    "client_ip": f"192.168.{random.randint(1,255)}.{random.randint(1,255)}"
                })
            elif service == "user-service":
                message_options = [
                    ("WARN", "Slow query detected"),
                    ("ERROR", "User authentication failed"),
                    ("INFO", "Profile update successful"),
                    ("INFO", "Password reset requested"),
                    ("DEBUG", "User session created")
                ]
                chosen_level, message = random.choice(message_options)
                log_entry["level"] = chosen_level
                log_entry.update({
                    "message": message,
                    "query_duration": random.randint(100, 5000),
                    "table": random.choice(tables),
                    "user_id": f"user-{random.randint(1000, 9999)}"
                })
            elif service == "payment-gateway":
                message_options = [
                    ("FATAL", "Circuit breaker opened"),
                    ("INFO", "Payment processed"),
                    ("ERROR", "Transaction failed"),
                    ("ERROR", "Fraud detected"),
                    ("DEBUG", "Payment validation started")
                ]
                chosen_level, message = random.choice(message_options)
                log_entry["level"] = chosen_level
                log_entry.update({
                    "message": message,
                    "error_rate": round(random.uniform(0.1, 0.9), 2),
                    "threshold": round(random.uniform(0.7, 0.9), 2),
                    "transaction_id": f"txn-{random.randint(10000, 99999)}"
                })
            elif service == "inventory":
                message_options = [
                    ("WARN", "Stock level critical"),
                    ("INFO", "Inventory updated"),
                    ("WARN", "Reorder point reached"),
                    ("INFO", "Stock audit completed"),
                    ("DEBUG", "Inventory check initiated")
                ]
                chosen_level, message = random.choice(message_options)
                log_entry["level"] = chosen_level
                log_entry.update({
                    "message": message,
                    "product_id": f"prod-{random.randint(100, 999)}",
                    "current_stock": random.randint(0, 100),
                    "threshold": random.randint(5, 20)
                })
            elif service == "analytics":
                message_options = [
                    ("INFO", "Report generated"),
                    ("INFO", "Data processing completed"),
                    ("INFO", "Export finished"),
                    ("INFO", "Metrics calculated"),
                    ("WARN", "Processing taking longer than expected"),
                    ("DEBUG", "Analytics job started")
                ]
                chosen_level, message = random.choice(message_options)
                log_entry["level"] = chosen_level
                log_entry.update({
                    "message": message,
                    "report_type": random.choice(report_types),
                    "records_processed": random.randint(1000, 50000),
                    "processing_time": random.randint(10, 300)
                })
            else:
                # Generic fields for other services
                message_options = [
                    ("INFO", "Operation completed"),
                    ("ERROR", "Error occurred"),
                    ("WARN", "Warning condition"),
                    ("DEBUG", "Debug info"),
                    ("INFO", "Service started")
                ]
                chosen_level, message = random.choice(message_options)
                log_entry["level"] = chosen_level
                log_entry.update({
                    "message": message,
                    "correlation_id": f"corr-{random.randint(1000, 9999)}",
                    "execution_time": random.randint(10, 1000)
                })

            logs.append((timestamp, log_entry))

        # Sort by timestamp
        logs.sort(key=lambda x: x[0])

        with open(log_file, 'w') as f:
            for _, log_entry in logs:
                f.write(json.dumps(log_entry) + '\n')

        return log_file

    def generate_kubernetes_logs(self) -> Path:
        """Generate Kubernetes-style logs."""
        log_file = self.output_dir / "k8s-app.log"

        base_time = datetime.now(UTC)
        files = ["main.go", "handler.go", "metrics.go", "database.go", "server.go", "auth.go", "cache.go", "queue.go"]
        levels = ["I", "E", "W", "F"]

        message_templates = [
            ("I", "Starting application server on port {port}"),
            ("I", "Successfully connected to database"),
            ("I", "Cache initialized with {size} MB"),
            ("I", "Worker pool started with {workers} workers"),
            ("E", "HTTP {status}: {error} processing request {endpoint}"),
            ("E", "Database query failed: {reason}"),
            ("E", "Authentication failed for user {user_id}"),
            ("E", "Cache operation failed: {reason}"),
            ("W", "Metrics endpoint {endpoint} responding slowly"),
            ("W", "High memory usage detected: {percent}%"),
            ("W", "Connection pool near capacity: {current}/{max}"),
            ("W", "Rate limit approaching for endpoint {endpoint}"),
            ("F", "Failed to bind to port {port}: {reason}"),
            ("F", "Database connection lost: {reason}"),
            ("F", "Critical system error: {reason}"),
            ("I", "Health check passed for service {service}"),
            ("I", "Configuration reloaded successfully"),
            ("E", "Queue processing failed: {reason}"),
            ("W", "Disk space low: {percent}% remaining")
        ]

        logs = []
        for i in range(50):  # 10x the original 5 logs
            timestamp = base_time + timedelta(seconds=random.randint(0, 3600), microseconds=random.randint(0, 999999))
            day_str = timestamp.strftime("%m%d")
            time_str = timestamp.strftime("%H:%M:%S.%f")

            level, template = random.choice(message_templates)
            file_name = random.choice(files)
            line_num = random.randint(10, 500)

            # Fill in template variables
            message = template.format(
                port=random.choice([8080, 8081, 8082, 9000, 9090]),
                status=random.choice([400, 401, 403, 404, 500, 502, 503]),
                error=random.choice(["Internal server error", "Bad request", "Unauthorized", "Not found", "Service unavailable"]),
                endpoint=random.choice(["/api/users", "/api/orders", "/api/health", "/metrics", "/api/auth", "/api/payments"]),
                reason=random.choice(["connection refused", "timeout", "invalid credentials", "resource exhausted", "permission denied"]),
                user_id=f"user-{random.randint(1000, 9999)}",
                percent=random.randint(75, 95),
                size=random.randint(128, 1024),
                workers=random.randint(4, 32),
                current=random.randint(80, 95),
                max=100,
                service=random.choice(["auth", "database", "cache", "queue", "metrics"])
            )

            log_line = f"{level}{day_str} {time_str}       1 {file_name}:{line_num}] {message}"
            logs.append((timestamp, log_line))

        # Sort by timestamp
        logs.sort(key=lambda x: x[0])

        with open(log_file, 'w') as f:
            for _, log_line in logs:
                f.write(log_line + '\n')

        return log_file

    def generate_mixed_format_logs(self) -> Path:
        """Generate mixed format logs with various severity levels."""
        log_file = self.output_dir / "mixed-format.log"

        base_time = datetime.now(UTC)
        hosts = ["host01", "host02", "host03", "web-server", "db-server", "cache-node"]
        apps = ["app", "nginx", "postgres", "redis", "worker", "scheduler"]
        levels = ["INFO", "WARN", "ERROR", "DEBUG", "FATAL"]

        message_templates = [
            ("INFO", "Application started successfully"),
            ("WARN", "Configuration file not found, using defaults"),
            ("ERROR", "Failed to connect to external service"),
            ("DEBUG", "Processing request ID: {request_id}"),
            ("ERROR", "Database connection lost, retrying..."),
            ("FATAL", "Critical system failure detected"),
            ("WARN", "Memory usage exceeding limits: {percent}%"),
            ("WARN", "Disk space running low: {percent}% remaining"),
            ("ERROR", "Authentication token expired"),
            ("ERROR", "Service health check failed"),
            ("WARN", "Queue processing delayed by {delay}ms"),
            ("WARN", "Cache hit ratio dropped to {percent}%"),
            ("ERROR", "Network timeout connecting to {service}"),
            ("WARN", "SSL certificate expires in {days} days"),
            ("WARN", "Load average high: {load}"),
            ("ERROR", "File system error on {partition}"),
            ("INFO", "Backup completed successfully ({size}GB)"),
            ("INFO", "User session expired for {user_id}"),
            ("ERROR", "Rate limit exceeded for {endpoint}")
        ]

        logs = []

        # Choose one consistent format for this entire mixed format log file
        format_choice = random.choice([1, 2, 3, 4, 5, 6])

        # Various timestamp formats - choose one for consistency
        timestamp_formats_mixed = [
            lambda t: t.strftime("%b %d %H:%M:%S"),                         # Syslog
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ"),                     # ISO
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z",       # ISO with ms
            lambda t: t.strftime("%Y/%m/%d %H:%M:%S"),                      # Slash format
            lambda t: t.strftime("%d.%m.%Y %H:%M:%S"),                      # German format
            lambda t: str(int(t.timestamp())),                              # Unix timestamp
            lambda t: t.strftime("%Y-%m-%d %H:%M:%S,%f")[:-3],              # Python logging
            lambda t: t.strftime("%m/%d/%Y %I:%M:%S %p"),                   # US format with AM/PM
        ]

        chosen_timestamp_format_mixed = random.choice(timestamp_formats_mixed)

        for i in range(80):  # 10x the original 8 logs
            timestamp = base_time + timedelta(seconds=random.randint(0, 3600))
            host = random.choice(hosts)
            app = random.choice(apps)
            pid = random.randint(1000, 9999)
            level, message = random.choice(message_templates)

            # Fill in template variables
            message = message.format(
                request_id=''.join(random.choices('0123456789abcdef', k=8)),
                percent=random.randint(5, 95),
                delay=random.randint(100, 5000),
                service=random.choice(["auth-service", "payment-api", "user-db", "cache-cluster"]),
                days=random.randint(1, 90),
                load=f"{random.uniform(1.0, 8.0):.2f}",
                partition=random.choice(["/var/log", "/tmp", "/data", "/home"]),
                size=f"{random.uniform(0.5, 50.0):.1f}",
                user_id=f"usr-{random.randint(1000, 9999)}",
                endpoint=random.choice(["/api/users", "/api/orders", "/health", "/metrics"])
            )

            # Use consistent format for entire file
            if format_choice == 1:  # Syslog format
                time_str = chosen_timestamp_format_mixed(timestamp)
                log_line = f"{time_str} {host} {app}[{pid}]: {level}: {message}"
            elif format_choice == 2:  # ISO timestamp with brackets
                time_str = chosen_timestamp_format_mixed(timestamp)
                log_line = f"{time_str} [{level}] {message}"
            elif format_choice == 3:  # Level first format
                time_str = chosen_timestamp_format_mixed(timestamp)
                log_line = f"[{level}] {time_str}: {message}"
            elif format_choice == 4:  # Simple format
                time_str = chosen_timestamp_format_mixed(timestamp)
                log_line = f"{level}: {time_str} - {message}"
            elif format_choice == 5:  # No timestamp format
                log_line = f"{level} {host} {app}: {message}"
            else:  # Minimal format - just level and message
                log_line = f"[{level}] {message}"

            logs.append((timestamp, log_line))

        # Sort by timestamp
        logs.sort(key=lambda x: x[0])

        with open(log_file, 'w') as f:
            for _, log_line in logs:
                f.write(log_line + '\n')

        return log_file

    def generate_high_volume_logs(self, count: int = 10000) -> Path:
        """Generate high-volume logs for performance testing."""
        log_file = self.output_dir / "high-volume.log"

        levels = ["ERROR", "WARN", "INFO", "DEBUG", "TRACE"]
        services = [f"load-test-service-{i}" for i in range(20)]  # More services
        base_time = datetime.now(UTC)

        message_templates = [
            ("INFO", "Processing request batch {batch_id}"),
            ("DEBUG", "Database query executed in {duration}ms"),
            ("DEBUG", "Cache operation: {operation} for key {key}"),
            ("DEBUG", "Authentication check for user {user_id}"),
            ("TRACE", "Load test message {msg_id} with random data: {data}"),
            ("INFO", "Network request to {endpoint} completed"),
            ("DEBUG", "Memory allocation: {size}MB for operation {op_id}"),
            ("INFO", "Thread pool status: {active}/{total} active"),
            ("INFO", "Queue processing: {processed}/{total} messages"),
            ("DEBUG", "Heartbeat from worker {worker_id}"),
            ("INFO", "Metrics collection interval {interval}s"),
            ("INFO", "Configuration reload triggered"),
            ("DEBUG", "Health check probe: {status}"),
            ("DEBUG", "Session management: {operation} session {session_id}"),
            ("DEBUG", "File I/O operation: {operation} {filename}"),
            ("ERROR", "Request processing failed for batch {batch_id}"),
            ("ERROR", "Database query timeout after {duration}ms"),
            ("WARN", "Cache miss rate high for key {key}"),
            ("ERROR", "Authentication failed for user {user_id}"),
            ("WARN", "Memory usage high: {size}MB allocated")
        ]

        timestamp_formats_high_volume = [
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3] + "Z",   # ISO with ms
            lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ"),                 # ISO
            lambda t: t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],          # Space separated with ms
            lambda t: str(int(t.timestamp() * 1000)),                   # Unix timestamp ms
            lambda t: t.strftime("%Y/%m/%d %H:%M:%S"),                  # Slash format
            lambda t: t.strftime("%b %d %H:%M:%S.%f")[:-3],             # Syslog with ms
        ]

        # Choose consistent timestamp format for entire high-volume log file
        use_timestamps_hv = random.random() > 0.10  # 10% chance entire file has no timestamps
        if use_timestamps_hv:
            chosen_timestamp_format_hv = random.choice(timestamp_formats_high_volume)

        with open(log_file, 'w') as f:
            for i in range(count):
                # Spread timestamps over 1 hour with microsecond precision
                offset_seconds = (i * 3600) // count
                offset_microseconds = random.randint(0, 999999)
                timestamp = base_time + timedelta(seconds=offset_seconds, microseconds=offset_microseconds)

                level, template = random.choice(message_templates)
                service = random.choice(services)

                # Fill in template variables
                message = template.format(
                    batch_id=f"batch-{random.randint(1000, 9999)}",
                    duration=random.randint(10, 2000),
                    operation=random.choice(["GET", "SET", "DEL", "UPDATE"]),
                    key=f"key-{random.randint(1000, 9999)}",
                    user_id=f"usr-{random.randint(1000, 9999)}",
                    msg_id=i+1,
                    data=''.join(random.choices('0123456789abcdef', k=16)),
                    endpoint=f"/api/v{random.randint(1,3)}/{random.choice(['users', 'orders', 'products'])}",
                    size=random.randint(1, 100),
                    op_id=f"op-{random.randint(100, 999)}",
                    active=random.randint(1, 50),
                    total=50,
                    processed=random.randint(0, 1000),
                    worker_id=f"worker-{random.randint(1, 10)}",
                    interval=random.randint(5, 60),
                    status=random.choice(["OK", "WARN", "ERROR"]),
                    session_id=f"sess-{random.randint(10000, 99999)}",
                    filename=f"data-{random.randint(1000, 9999)}.{random.choice(['log', 'tmp', 'dat'])}"
                )

                # Use consistent timestamp handling for entire file
                if use_timestamps_hv:
                    timestamp_str = chosen_timestamp_format_hv(timestamp)
                    log_line = f"{timestamp_str} {level} [{service}] {message}"
                else:
                    log_line = f"{level} [{service}] {message}"

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

    def generate_realistic_error_scenarios(self) -> List[Dict[str, Any]]:
        """Generate realistic error scenarios for AI analysis testing."""
        scenarios = [
            # Database errors
            {
                "level": "ERROR",
                "source": "database-service",
                "message": "Connection pool exhausted: too many open connections (max: 100, current: 100)",
                "severity": 8
            },
            {
                "level": "CRITICAL",
                "source": "database-service",
                "message": "Database server not responding: connection timeout after 30 seconds",
                "severity": 10
            },
            {
                "level": "ERROR",
                "source": "database-service",
                "message": "Deadlock detected in transaction: unable to acquire lock on table 'users'",
                "severity": 7
            },

            # Authentication/Security errors
            {
                "level": "ERROR",
                "source": "auth-service",
                "message": "Authentication failed: invalid JWT token signature",
                "severity": 6
            },
            {
                "level": "WARNING",
                "source": "auth-service",
                "message": "Rate limit exceeded: 1000 requests in 60 seconds from IP 192.168.1.100",
                "severity": 5
            },
            {
                "level": "CRITICAL",
                "source": "security-monitor",
                "message": "Potential SQL injection detected: malicious query blocked from user ID 12345",
                "severity": 9
            },

            # Performance issues
            {
                "level": "WARNING",
                "source": "api-gateway",
                "message": "High response time detected: 95th percentile latency is 2.5 seconds",
                "severity": 6
            },
            {
                "level": "ERROR",
                "source": "memory-monitor",
                "message": "Memory usage critical: 95% of heap space consumed (8.5GB of 9GB)",
                "severity": 8
            },
            {
                "level": "WARNING",
                "source": "disk-monitor",
                "message": "Disk space running low: only 5% available on /var/log partition",
                "severity": 7
            },

            # Network/Service errors
            {
                "level": "ERROR",
                "source": "payment-gateway",
                "message": "External payment service unavailable: HTTP 503 Service Unavailable",
                "severity": 8
            },
            {
                "level": "WARNING",
                "source": "cache-service",
                "message": "Redis connection lost: attempting reconnection (attempt 3/5)",
                "severity": 5
            },
            {
                "level": "ERROR",
                "source": "notification-service",
                "message": "Failed to send email notification: SMTP server timeout",
                "severity": 4
            },

            # Application logic errors
            {
                "level": "ERROR",
                "source": "order-service",
                "message": "Order processing failed: insufficient inventory for product SKU-12345",
                "severity": 6
            },
            {
                "level": "ERROR",
                "source": "user-service",
                "message": "User profile update failed: validation error on email format",
                "severity": 3
            },
            {
                "level": "WARNING",
                "source": "analytics-service",
                "message": "Report generation taking longer than expected: 5 minutes elapsed",
                "severity": 4
            },

            # Infrastructure errors
            {
                "level": "CRITICAL",
                "source": "kubernetes",
                "message": "Pod crash loop detected: api-gateway-pod-xyz restarted 5 times in 10 minutes",
                "severity": 9
            },
            {
                "level": "ERROR",
                "source": "load-balancer",
                "message": "Backend server unhealthy: removed api-server-3 from rotation",
                "severity": 7
            },
            {
                "level": "WARNING",
                "source": "monitoring",
                "message": "Metrics collection delayed: Prometheus scrape timeout on target api-gateway",
                "severity": 4
            }
        ]

        log_entries = []
        base_time = int(time.time() * 1000)

        for i, scenario in enumerate(scenarios):
            log_entry = {
                "timestamp": base_time + (i * 2000),  # 2 second intervals
                "message": scenario["message"],
                "source": scenario["source"],
                "metadata": {
                    "level": scenario["level"],
                    "container_name": f"{scenario['source']}-container-{i}",
                    "namespace": "production",
                    "pod_name": f"{scenario['source']}-pod-{i}",
                    "service_name": scenario["source"],
                    "node_name": f"node-{i % 3 + 1}",
                    "labels": {"app": scenario["source"], "version": "v2.1", "tier": "production"},
                    "expected_severity": scenario["severity"]  # For validation in tests
                }
            }
            log_entries.append(log_entry)

        return log_entries

    def cleanup(self) -> None:
        """Clean up generated test logs."""
        if self.output_dir.exists():
            for log_file in self.output_dir.glob("*.log"):
                log_file.unlink()