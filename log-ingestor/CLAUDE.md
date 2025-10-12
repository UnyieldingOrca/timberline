# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Component Overview

The Log Ingestor is a high-performance Go service that accepts streaming logs via HTTP (JSON Lines format), validates them, generates embeddings, and stores them in Milvus vector database for AI-powered analysis.

## Architecture

**Core Flow**: HTTP endpoint → Stream handler → Channel-based queue → Worker pool → Embedding service → Milvus storage

**Key Components**:
- `cmd/main.go` - Application entry point with graceful shutdown
- `internal/handlers/stream.go` - Streaming log ingestion with Fluent Bit compatibility
- `internal/storage/milvus.go` - Milvus vector database client
- `internal/embedding/service.go` - External embedding service client
- `internal/config/config.go` - Environment-based configuration
- `internal/metrics/server.go` - Prometheus metrics on port 9090
- `internal/models/log.go` - Core data structures

**Worker Pool Pattern**: The service uses a channel-based worker pool (configurable via `NUM_WORKERS`) where the HTTP handler publishes log entries to a buffered channel, and worker goroutines process them asynchronously to avoid blocking the HTTP endpoint.

**Fluent Bit Compatibility**: The stream handler supports both direct LogEntry format and Fluent Bit's standard JSON format with `date`, `log`, and `kubernetes` fields. Timestamps are flexibly parsed (int64, float64, ISO 8601, or various string formats).

## Development Commands

```bash
# Development cycle
make dev              # Quick dev cycle: fmt + lint + test + build

# Individual commands
make build            # Build binary (CGO_ENABLED=0, static linking)
make test             # Run tests with race detection and coverage
make test-coverage    # Generate HTML coverage report
make fmt              # Format code with go fmt
make lint             # Run golangci-lint
make run              # Build and run locally
make deps             # Download and tidy dependencies
make clean            # Clean build artifacts

# Docker
make docker-build     # Build Docker image
make docker-push      # Build and push Docker image

# Run specific tests
go test ./internal/handlers -v -run TestStreamHandler
go test ./internal/storage -v -run TestMilvusClient
```

## Configuration

All configuration is via environment variables (see `internal/config/config.go`):

**Core Settings**:
- `SERVER_PORT` (8080) - Main HTTP server port
- `MILVUS_ADDRESS` (milvus:19530) - Milvus connection
- `EMBEDDING_ENDPOINT` (http://embedding-service:8080/embed) - Embedding service URL
- `EMBEDDING_DIMENSION` (768) - Vector dimension for nomic-embed-text-v1.5
- `NUM_WORKERS` (4) - Number of log processing worker goroutines

**Performance Tuning**:
- `BATCH_SIZE` (100) - Maximum logs per batch (not currently used due to direct storage)
- `RATE_LIMIT_RPS` (1000) - Rate limit for HTTP requests
- `MAX_REQUEST_SIZE` (10485760) - Maximum request size (10MB)

**Deduplication Settings**:
- `SIMILARITY_THRESHOLD` (0.95) - Cosine similarity threshold for duplicate detection
- `MIN_EXAMPLES_BEFORE_EXCLUSION` (3) - Minimum duplicates before excluding from results

## API Endpoints

- `POST /api/v1/logs/stream` - JSON Lines streaming (Fluent Bit compatible)
- `GET /api/v1/health` - Detailed health with storage status
- `GET /api/v1/healthz` - Liveness probe
- `GET /api/v1/ready` - Readiness probe
- `GET /metrics` - Prometheus metrics (port 9090)

## Testing

Unit tests use `testify/assert` and `testify/mock`. Mock implementations exist for storage and embedding services.

```bash
# Run all tests
make test

# Run specific package tests
go test ./internal/handlers -v
go test ./internal/storage -v -run TestMilvusClient

# Run with coverage
make test-coverage
```

## Key Dependencies

- **gorilla/mux** - HTTP routing
- **milvus-io/milvus/client/v2** - Vector database client
- **prometheus/client_golang** - Metrics instrumentation
- **sirupsen/logrus** - Structured logging (JSON format)

## Code Patterns

**Error Handling**: Use logrus with structured fields. Return errors from functions and handle at appropriate level.

**Context Usage**: Always pass context for cancellation. Main service uses separate contexts for storage operations, worker pool, and graceful shutdown.

**Metrics**: All handlers increment Prometheus counters/histograms. Metrics are registered in handler constructors.

**Validation**: Models have `Validate()` methods. Configuration validation happens at startup via `Config.Validate()`.
