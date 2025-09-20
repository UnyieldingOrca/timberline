# Log Ingestor

The Log Ingestor is a high-performance Go service that receives logs from collectors, validates them, and stores them in a Milvus vector database for AI-powered analysis.

## Features

- **High-Performance REST API**: Accept log streams via HTTP endpoints (JSON Lines format)
- **Streaming Processing**: Efficient streaming with internal batching for optimal database performance
- **Schema Validation**: Validate log structure and required fields
- **Prometheus Metrics**: Comprehensive monitoring and observability
- **Health Checks**: Kubernetes-ready liveness and readiness probes
- **Rate Limiting**: Protection against traffic spikes
- **Graceful Shutdown**: Proper resource cleanup on termination

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/logs/stream` | Streaming log ingestion (JSON Lines format) |
| GET | `/api/v1/health` | Detailed health check |
| GET | `/api/v1/healthz` | Liveness probe |
| GET | `/api/v1/ready` | Readiness probe |
| GET | `/metrics` | Prometheus metrics (port 9090) |

## Configuration

Configure via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_PORT` | `8080` | HTTP server port |
| `LOG_LEVEL` | `info` | Logging level (debug, info, warn, error) |
| `MILVUS_ADDRESS` | `milvus:19530` | Milvus database address |
| `EMBEDDING_ENDPOINT` | `http://embedding-service:8080/embed` | Embedding service endpoint |
| `EMBEDDING_MODEL` | `nomic-embed-text-v1.5` | Embedding model to use |
| `EMBEDDING_DIMENSION` | `768` | Embedding vector dimension |
| `BATCH_SIZE` | `100` | Maximum logs per batch |
| `BATCH_TIMEOUT` | `5s` | Batch processing timeout |
| `MAX_REQUEST_SIZE` | `10485760` | Maximum request size in bytes (10MB) |
| `METRICS_PORT` | `9090` | Prometheus metrics port |
| `READ_TIMEOUT` | `10s` | HTTP read timeout |
| `WRITE_TIMEOUT` | `10s` | HTTP write timeout |
| `RATE_LIMIT_RPS` | `1000` | Rate limit requests per second |

## Development

### Prerequisites

- Go 1.23+
- Docker
- Kubernetes cluster (for deployment)
- golangci-lint (for linting)

### Quick Start

```bash
# Set up development environment
make dev-setup

# Build and test
make all

# Run locally
make run

# Build Docker image
make docker-build

# Deploy to Kubernetes
make deploy-all
```

### Development Commands

```bash
make dev          # Quick development cycle
make test         # Run tests
make test-coverage # Run tests with coverage
make lint         # Run linter
make fmt          # Format code
make clean        # Clean artifacts
```

## Deployment

### Kubernetes

Deploy to Kubernetes cluster:

```bash
# Deploy with default configuration
make deploy

# Or build and deploy in one step
make deploy-all

# Check status
make status

# View logs
make logs

# Port forward for testing
make port-forward
```

### Resource Requirements

- **Requests**: 250m CPU, 512Mi memory
- **Limits**: 500m CPU, 1Gi memory
- **Replicas**: 3 (for high availability)

## Monitoring

The service exposes Prometheus metrics on port 9090:

- Request counts and durations
- Batch sizes and processing times
- Error rates and types
- Storage health status

## API Usage

### Streaming Log Ingestion (JSON Lines)

```bash
curl -X POST http://localhost:8080/api/v1/logs/stream \
  -H "Content-Type: application/x-ndjson" \
  -d '{"timestamp": 1701423600000, "message": "Application started", "source": "app", "metadata": {"level": "INFO", "pod_name": "app-123", "namespace": "production"}}
{"timestamp": 1701423601000, "message": "Request processed", "source": "app", "metadata": {"level": "INFO", "pod_name": "app-123", "namespace": "production"}}
{"timestamp": 1701423602000, "message": "Error occurred", "source": "app", "metadata": {"level": "ERROR", "pod_name": "app-123", "namespace": "production"}}'
```

### Fluent Bit Configuration

```yaml
[OUTPUT]
    Name              http
    Match             *
    Host              log-ingestor
    Port              8080
    URI               /api/v1/logs/stream
    Format            json_lines
    json_date_key     timestamp
    json_date_format  epoch
```

### Health Check

```bash
curl http://localhost:8080/api/v1/health
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Fluent Bit    │───▶│  Log Ingestor   │───▶│  Milvus Vector  │
│   (DaemonSet)   │    │   (Service)     │    │    Database     │
│  JSON Lines     │    │  Stream API     │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │   Prometheus    │
                       │   (Metrics)     │
                       └─────────────────┘
```

## Security

- Runs as non-root user (1001:1001)
- Read-only root filesystem
- No privileged escalation
- Dropped capabilities
- Resource limits enforced

## Performance

- Concurrent request processing
- Efficient batch operations
- Connection pooling to Milvus
- Optimized JSON parsing
- Minimal memory allocations