# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timberline is an AI-powered log analysis platform for Kubernetes environments consisting of multiple components:
- **Log Collector** (Fluent Bit DaemonSet) - Industry-standard log collection
- **Log Ingestor** (Go Service) - Currently implemented
- **Vector Database** (Milvus) - Integrated via Docker
- **AI Analysis Engine** (Python Service/Job) - Currently implemented
- **Web Dashboard** - Planned

## Architecture

The system follows a pipeline architecture where logs flow from Kubernetes pods → Fluent Bit Collector → Log Ingestor → Vector Database → AI Analysis Engine. Fluent Bit enriches logs with Kubernetes metadata and performs pre-filtering before streaming to the ingestion pipeline via JSON Lines format.

## Development Commands

### Top-Level Commands
Use the top-level Makefile for Kubernetes integration testing:

```bash
make help             # Show all available commands

# Kind-based testing (Kubernetes in Docker)
make kind-setup       # Setup kind cluster for integration testing
make kind-test        # Setup kind cluster and run integration tests
make test-integration # Run integration tests against kind cluster
make test-kind        # Run integration tests against kind cluster
make kind-down        # Delete kind cluster

# Dependencies
make download-models  # Download required AI models
make install-test-deps # Install Python test dependencies
```

### Component-Specific Commands
The Go log-ingestor component has these Makefile targets:

```bash
cd log-ingestor
make help           # Show available targets
make build          # Build binary
make test           # Run tests with race detection
make test-coverage  # Run tests with coverage report
make clean          # Clean build artifacts
make deps           # Download and tidy dependencies
make fmt            # Format Go code
make lint           # Run golangci-lint
make run            # Build and run locally
make docker-build   # Build Docker image
make docker-push    # Build and push Docker image
make dev            # Quick dev cycle: fmt + lint + test + build
```

### Project Structure

```
timberline/
├── fluent-bit/                 # Fluent Bit configuration and manifests
│   ├── configmap.yaml         # Fluent Bit configuration
│   ├── daemonset.yaml         # Kubernetes DaemonSet manifest
│   └── rbac.yaml              # Service account and RBAC
├── log-ingestor/               # Go-based REST API service (implemented)
│   ├── cmd/main.go            # Application entry point
│   ├── internal/              # Core implementation modules
│   ├── Dockerfile             # Container definition
│   ├── Makefile               # Build automation
│   └── go.mod                 # Go dependencies
├── tests/                      # Integration test suite
├── scripts/                    # Build and test automation scripts
├── k8s/                        # Kubernetes manifests for all services
├── SPEC.md                     # Detailed component specifications
└── README.md                  # Project overview
```

## Key Technologies

- **Fluent Bit** (CNCF graduated) for log collection and streaming
- **Go 1.23+** with modules for log ingestor
- **JSON Lines** format for efficient log streaming
- **Milvus** vector database for embedding storage
- **Kind** (Kubernetes in Docker) for testing environment
- **Python/pytest** for integration testing

## Configuration

Fluent Bit is configured via ConfigMap with industry-standard patterns:
- Log path filtering for Kubernetes containers and pods
- Kubernetes metadata enrichment (pod, namespace, node, labels)
- JSON Lines output format to log-ingestor `/api/v1/logs/stream` endpoint
- Built-in buffering and retry mechanisms

## Testing and Validation

### Unit Tests
Run unit tests for the log ingestor:
```bash
cd log-ingestor && make test     # Test log ingestor
```

### Integration Tests
Comprehensive Kubernetes-based integration tests for the complete pipeline using kind:

```bash
# Setup kind cluster and run integration tests
make kind-test

# Run integration tests against existing kind cluster
make test-integration

# Setup kind cluster manually
make kind-setup

# Delete kind cluster
make kind-down

# Install Python test dependencies
make install-test-deps

# Manual test execution against kind
./scripts/run-kind-integration-tests.sh --show-logs

# Run specific test classes
pytest tests/docker/test_log_ingestor.py -v
pytest tests/docker/test_embedding_service.py -v
pytest tests/docker/test_ai_analyzer_integration.py -v

# Run tests with specific markers
pytest tests/docker/ -v -m "not slow"
```

The integration tests cover:
- Service health checks (fluent-bit, log-ingestor, Milvus, llama.cpp, etcd, MinIO)
- Log ingestion API endpoints (JSON Lines streaming format)
- Complete pipeline data flow from files → Fluent Bit → ingestor → Milvus
- Embedding generation and semantic search
- Data persistence verification
- Metrics collection endpoints
- AI analysis engine integration and log clustering
- LLM-based severity scoring and report generation

Fluent Bit provides built-in metrics and health endpoints for monitoring in production.

## Future Components

Refer to SPEC.md for detailed specifications of planned components:
- Web dashboard for visualization
- Integration tests should go in our top level tests folder.
- do not generate alembic migration scripts manually