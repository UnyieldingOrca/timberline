# Timberline Log Collector

The Log Collector is a high-performance Go-based DaemonSet that collects logs from Kubernetes containers in real-time and forwards them to the Timberline log ingestion pipeline.

## Overview

The Log Collector runs on every Kubernetes node as a DaemonSet, efficiently collecting container logs while performing pre-filtering and metadata enrichment according to the Timberline specification.

## Features

- **Real-time log tailing** from container log files (`/var/log/containers/*` and `/var/log/pods/*`)
- **Kubernetes metadata enrichment** (pod, namespace, node information)
- **Configurable log level filtering** (ERROR, WARN, FATAL, etc.)
- **Buffering and batching** for efficient processing
- **HTTP forwarding** to the log ingester with retry logic
- **Prometheus metrics** for monitoring
- **Graceful shutdown handling**
- **TLS support** for secure communication
- **Data compression** for efficient transport
- **Pre-filtering** to remove noise (debug logs, info logs, health checks)
- **Log parsing support** for JSON, structured, and unstructured logs

## Configuration

The log collector is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_PATHS` | Comma-separated list of log file patterns | `/var/log/containers/*,/var/log/pods/*` |
| `LOG_LEVELS` | Comma-separated list of log levels to collect | `ERROR,WARN,FATAL` |
| `BUFFER_SIZE` | Internal buffer size for log entries | `1000` |
| `FLUSH_INTERVAL` | Interval to flush buffered logs | `5s` |
| `INGESTOR_URL` | URL of the log ingestor service | `http://log-ingestor:8080` |
| `BATCH_SIZE` | Number of logs per batch | `100` |
| `RETRY_ATTEMPTS` | Number of retry attempts for failed requests | `3` |
| `METRICS_PORT` | Port for Prometheus metrics endpoint | `9090` |

## Resource Requirements

According to the Timberline specification:

- **Memory**: 128Mi - 256Mi
- **CPU**: 100m - 200m
- **Storage**: Optional file-based buffer (1GB)

## Quick Start

### Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Docker (for building images)

### Building from Source

1. **Build the Go binary:**
   ```bash
   make build
   ```

2. **Build Docker image:**
   ```bash
   make docker-build
   ```

3. **Run tests:**
   ```bash
   make test
   ```

### Deployment

1. **Deploy to Kubernetes:**
   ```bash
   make deploy-all
   ```

2. **Verify deployment:**
   ```bash
   kubectl get pods -n timberline -l app=timberline-log-collector
   ```

## Monitoring

### Prometheus Metrics

The log collector exposes metrics on port 9090:

- `timberline_logs_collected_total` - Total logs collected
- `timberline_logs_forwarded_total` - Total logs successfully forwarded
- `timberline_logs_dropped_total` - Total logs dropped due to buffer overflow
- `timberline_forwarding_errors_total` - Total forwarding errors
- `timberline_buffer_size` - Current buffer size
- `timberline_files_watched` - Number of files being watched

### Health Endpoints

- `/health` - Health check endpoint
- `/ready` - Readiness check endpoint


## Security

- Runs with minimal privileges
- Uses read-only access to log directories
- Supports TLS for secure communication
- Follows Kubernetes security best practices
- Non-root container execution

## API Integration

The log collector forwards logs to the Timberline log ingester via the following endpoint:

```
POST /api/v1/logs/batch
```

Logs are batched according to the `BATCH_SIZE` configuration and include enriched Kubernetes metadata as specified in the Timberline architecture.

## Development

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Run tests: `make test`
6. Ensure code follows Go standards
7. Submit a pull request

### Testing

Run the test suite:
```bash
make test
```

### Local Development

For local development and testing:
```bash
# Install dependencies
go mod download

# Run locally (requires proper configuration)
go run cmd/main.go
```

## Troubleshooting

### Common Issues

1. **Logs not being collected**
   - Check that log paths exist and are readable
   - Verify DaemonSet has proper permissions (RBAC)
   - Check pod logs for error messages

2. **High memory usage**
   - Adjust `BUFFER_SIZE` to a lower value
   - Check for log volume spikes
   - Monitor metrics for buffer overflow

3. **Connection errors to ingester**
   - Verify `INGESTOR_URL` is correct
   - Check network connectivity
   - Review retry configuration

### Debug Logging

Enable debug logging by setting the log level in the configuration or environment variables.

## License

This component is part of the Timberline project and follows the same MIT License as the main project.
