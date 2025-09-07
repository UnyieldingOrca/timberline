#!/bin/bash

# Generate test logs for integration testing
# This script creates sample log files that simulate various application scenarios

set -e

LOG_DIR="${1:-./test-logs}"
mkdir -p "$LOG_DIR"

echo "Generating test logs in $LOG_DIR..."

# Generate application error logs
cat > "$LOG_DIR/app-errors.log" << 'EOF'
2024-01-15T10:30:45.123Z ERROR [auth-service] Failed to authenticate user: invalid credentials
2024-01-15T10:31:02.456Z WARN [auth-service] Rate limit approaching for IP 192.168.1.100
2024-01-15T10:31:15.789Z FATAL [database] Connection pool exhausted, cannot serve requests
2024-01-15T10:31:30.012Z ERROR [payment-service] Payment processing failed: insufficient funds
2024-01-15T10:32:45.345Z ERROR [order-service] Order validation failed: invalid product ID
2024-01-15T10:33:00.678Z WARN [cache-service] Cache miss rate exceeding threshold: 85%
2024-01-15T10:33:15.901Z ERROR [notification-service] Failed to send email: SMTP timeout
EOF

# Generate JSON structured logs
cat > "$LOG_DIR/structured-logs.log" << 'EOF'
{"timestamp":"2024-01-15T10:30:45Z","level":"ERROR","service":"api-gateway","message":"Request timeout","request_id":"req-123","duration":5000}
{"timestamp":"2024-01-15T10:31:00Z","level":"WARN","service":"user-service","message":"Slow query detected","query_duration":2500,"table":"users"}
{"timestamp":"2024-01-15T10:31:15Z","level":"FATAL","service":"payment-gateway","message":"Circuit breaker opened","error_rate":0.85,"threshold":0.8}
{"timestamp":"2024-01-15T10:31:30Z","level":"ERROR","service":"inventory","message":"Stock level critical","product_id":"prod-456","current_stock":2,"threshold":10}
{"timestamp":"2024-01-15T10:31:45Z","level":"INFO","service":"analytics","message":"Report generated","report_type":"daily_sales","records_processed":15000}
EOF

# Generate Kubernetes-style logs
cat > "$LOG_DIR/k8s-app.log" << 'EOF'
I0115 10:30:45.123456       1 main.go:45] Starting application server on port 8080
E0115 10:31:00.234567       1 handler.go:123] HTTP 500: Internal server error processing request /api/users
W0115 10:31:15.345678       1 metrics.go:67] Metrics endpoint /metrics responding slowly
E0115 10:31:30.456789       1 database.go:234] Database query failed: connection refused
F0115 10:31:45.567890       1 server.go:89] Failed to bind to port 8080: address already in use
EOF

# Generate mixed format logs with various severity levels
cat > "$LOG_DIR/mixed-format.log" << 'EOF'
Jan 15 10:30:45 host01 app[1234]: INFO: Application started successfully
Jan 15 10:31:00 host01 app[1234]: WARN: Configuration file not found, using defaults
Jan 15 10:31:15 host01 app[1234]: ERROR: Failed to connect to external service
Jan 15 10:31:30 host01 app[1234]: DEBUG: Processing request ID: abc123
2024-01-15T10:32:00Z [ERROR] Database connection lost, retrying...
[FATAL] 2024-01-15 10:32:15: Critical system failure detected
ERROR: 2024-01-15T10:32:30.000Z - Memory usage exceeding limits
WARN 10:32:45 - Disk space running low: 5% remaining
EOF

# Generate high-volume logs for performance testing
echo "Generating high-volume test logs..."
for i in {1..1000}; do
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")
    level="ERROR"
    service="load-test-service-$((i % 10))"
    message="Load test message $i with random data: $(openssl rand -hex 16)"
    echo "${timestamp} ${level} [${service}] ${message}" >> "$LOG_DIR/high-volume.log"
done

# Generate logs with various character encodings and special characters
cat > "$LOG_DIR/special-chars.log" << 'EOF'
2024-01-15T10:30:45Z ERROR [api] Invalid JSON payload: {"user": "José María", "email": "jose@example.com"}
2024-01-15T10:31:00Z WARN [parser] Special characters detected: ñáéíóú çüß αβγ 中文 日本語
2024-01-15T10:31:15Z ERROR [validation] SQL injection attempt detected: '; DROP TABLE users; --
2024-01-15T10:31:30Z FATAL [security] XSS attempt: <script>alert('xss')</script>
EOF

echo "Test log generation completed!"
echo "Generated files:"
ls -la "$LOG_DIR"
