# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timberline is an AI-powered log analysis platform for Kubernetes environments consisting of multiple components:
- **Log Collector** (Go DaemonSet) - Currently implemented
- **Log Ingestor** (Go Service) - Planned
- **Vector Database** (Milvus) - Planned
- **AI Analysis Engine** (Python Service/Job) - Planned
- **Web Dashboard** - Planned

## Architecture

The system follows a pipeline architecture where logs flow from Kubernetes pods → Log Collector → Log Ingestor → Vector Database → AI Analysis Engine. The Log Collector enriches logs with Kubernetes metadata and performs pre-filtering before forwarding to the ingestion pipeline.

## Development Commands

### Top-Level Commands
Use the top-level Makefile for most development tasks:

```bash
# Setup and building
make help           # Show all available commands
make dev-setup      # Set up development environment
make build          # Build all components
make build-docker   # Build Docker images

# Testing
make test           # Run unit tests + integration tests (if Docker up)
make test-unit      # Run unit tests only
make test-integration  # Run Docker integration tests
make quick-test     # Quick unit tests only
make full-test      # Complete cycle: Docker up → test → Docker down

# Docker environment
make docker-up      # Start Docker integration environment
make docker-down    # Stop Docker integration environment
make docker-status  # Show Docker service status
make docker-logs    # Show Docker service logs

# Code quality
make fmt            # Format all code
make lint           # Run linting
make check          # Run linting + unit tests
make dev-test       # Format + lint + test cycle

# Development workflow
make dev-setup      # One-time setup for new developers
make ci             # Run full CI pipeline
make clean          # Clean all build artifacts
make status         # Show project status
```

### Component-Specific Commands
For working directly with the log collector:

```bash
cd log-collector
make build          # Build binary
make test           # Run tests
make fmt            # Format Go code
make lint           # Run golangci-lint
make run            # Run locally
make docker-build   # Build container image
make deploy-all     # Deploy to Kubernetes
make undeploy       # Remove from Kubernetes
```

### Project Structure

```
timberline/
├── log-collector/              # Go-based DaemonSet (implemented)
│   ├── cmd/main.go            # Application entry point
│   ├── internal/              # Core implementation modules
│   │   ├── collector/         # Log collection logic
│   │   ├── config/            # Configuration management
│   │   ├── forwarder/         # HTTP forwarding
│   │   ├── k8s/              # Kubernetes metadata client
│   │   ├── metrics/          # Prometheus metrics
│   │   └── models/           # Data models
│   ├── k8s/                  # Kubernetes manifests
│   ├── Dockerfile            # Container definition
│   ├── Makefile             # Build automation
│   └── go.mod               # Go dependencies
├── SPEC.md                   # Detailed component specifications
└── README.md                # Project overview
```

## Key Technologies

- **Go 1.23+** with modules for the log collector
- **Kubernetes client-go v0.28.0** for cluster integration
- **Prometheus client** for metrics
- **fsnotify** for file watching
- **logrus** for structured logging

## Configuration

The Log Collector uses environment variables for configuration:
- `LOG_PATHS`, `LOG_LEVELS`, `BUFFER_SIZE`, `FLUSH_INTERVAL`
- `INGESTOR_URL`, `BATCH_SIZE`, `RETRY_ATTEMPTS`
- `METRICS_PORT` for Prometheus endpoint

## Testing and Validation

### Unit Tests
Always run unit tests before committing changes:
```bash
cd log-collector && make test
```

### Integration Tests
Comprehensive Docker-based integration tests for the complete pipeline:

```bash
# Test complete pipeline (log-collector → log-ingestor → Milvus)
make test-pipeline

# Run all integration tests
make test-integration

# Run integration tests in parallel
make test-integration-parallel

# Manual test execution
./scripts/run-integration-tests.sh

# Run specific test classes
pytest tests/docker/test_integration.py::TestLogIngestor -v -m docker
pytest tests/docker/test_integration.py::TestDataPersistence -v -m docker

# Run only pipeline tests (slow)
pytest tests/docker/test_integration.py -v -m "docker and slow"
```

The integration tests cover:
- Service health checks (log-collector, log-ingestor, Milvus, llama.cpp, etcd, MinIO)
- Log ingestion API endpoints 
- Complete pipeline data flow from files → collector → ingestor → Milvus
- Embedding generation and semantic search
- Data persistence verification
- Metrics collection endpoints

The collector includes comprehensive metrics and health endpoints for monitoring in production.

## Future Components

Refer to SPEC.md for detailed specifications of planned components:
- Log Ingestor (Go REST API)
- Milvus vector database setup
- Python-based AI Analysis Engine with LLM integration
- Web dashboard for visualization
