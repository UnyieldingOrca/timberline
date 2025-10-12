# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timberline is an AI-powered log analysis platform for Kubernetes environments. It collects, processes, and analyzes logs using vector embeddings and LLM-powered insights to detect patterns, identify issues, and generate actionable reports.

## Architecture

Timberline consists of multiple microservices that work together:

**Data Pipeline:**
- **Fluent Bit** - (DaemonSet) - Collects logs from Kubernetes nodes with metadata enrichment
- **Log Ingestor** (Go service) - HTTP endpoint for streaming log ingestion, generates embeddings, stores in Milvus
- **Milvus Stack** - Vector database (Milvus + etcd + MinIO) for log storage and semantic search
- **Embedding Service** - llama.cpp server running nomic-embed-text-v1.5 (768 dimensions)

**Analysis Layer:**
- **AI Analyzer** (Python FastAPI + CLI) - Clusters similar logs, uses LLM for severity scoring, generates daily reports
- **Chat Service** - llama.cpp server for LLM analysis (Qwen3-0.6B-Q4_K_M)
- **PostgreSQL** - Stores analysis results and metadata

**Frontend:**
- **Web UI** (React + TypeScript + Vite) - Dashboard for viewing logs, searches, and analysis reports

**Flow:** Logs → Fluent Bit → Log Ingestor → Milvus (with embeddings) → AI Analyzer queries/clusters → LLM analysis → Reports → Web UI

## Development Commands

### Top-Level (Make)

```bash
# Quick start - Docker Compose environment
make docker-up          # Start all services in Docker Compose
make docker-down        # Stop Docker Compose environment
make docker-test        # Run integration tests against Docker

# Kubernetes (Kind) environment
make kind-up            # Create Kind cluster and deploy via Helm
make kind-down          # Delete Kind cluster
make kind-test          # Run integration tests against Kind cluster

# Testing
make install-test-deps  # Install Python test dependencies
make download-models    # Download AI models (nomic-embed, Qwen3)
```

### Log Ingestor (Go)

```bash
cd log-ingestor

# Development
make dev                # Full dev cycle: fmt + lint + test + build
make build              # Build static binary
make test               # Run tests with race detection
make fmt                # Format code
make lint               # Run golangci-lint
make run                # Build and run locally

# Testing specific packages
go test ./internal/handlers -v
go test ./internal/storage -v -run TestMilvusClient
```

### AI Analyzer (Python)

```bash
cd ai-analyzer

# Testing
pytest                                          # Run all tests
pytest tests/test_analysis.py -v              # Specific test file
pytest --cov=analyzer --cov-report=html       # Coverage report

# Code quality
black analyzer/ tests/                         # Format code
ruff check analyzer/ tests/                    # Lint code

# CLI tool (after pip install -e .)
ai-analyzer analyze-daily                      # Run daily analysis
ai-analyzer analyze-daily --date 2025-10-11   # Specific date
ai-analyzer health-check                       # Check all components
ai-analyzer list-reports --limit 10            # List recent reports

# API server
uvicorn analyzer.api.main:app --reload --host 0.0.0.0 --port 8000

# Database migrations
alembic upgrade head                           # Run migrations
alembic revision --autogenerate -m "desc"     # Create new migration
```

### Web UI (React + TypeScript)

```bash
cd web-ui

npm install             # Install dependencies
npm run dev             # Start dev server (http://localhost:5173)
npm run build           # Type-check and build production
npm run lint            # Lint code
npm run preview         # Preview production build
```

## Testing Strategy

### Unit Tests
- **Log Ingestor**: Go tests with testify/mock for handlers, storage, embedding client
- **AI Analyzer**: Python pytest with mocked dependencies (Milvus, LLM, PostgreSQL)
- **Web UI**: No test suite currently implemented

### Integration Tests (Kind)
Located in `tests/kind/` - comprehensive tests against Helm-deployed services on Kind cluster:

```bash
# Quick health check
pytest tests/kind/ -v -m health

# By category
pytest tests/kind/ -v -m deployment      # Deployment status
pytest tests/kind/ -v -m connectivity    # Service networking
pytest tests/kind/ -v -m e2e             # End-to-end pipeline

# Full suite
pytest tests/kind/ -v                    # All tests including slow
pytest tests/kind/ -v -m "not slow"      # Exclude slow tests
pytest tests/kind/ -v -n auto            # Parallel execution
```

**Test markers**: `health`, `deployment`, `connectivity`, `persistence`, `e2e`, `slow`

See `tests/kind/README.md` for comprehensive integration testing documentation.

### Integration Tests (Docker)
Located in `tests/` - tests against Docker Compose environment (older, less comprehensive than Kind tests)

## Configuration

### Environment Variables

**Docker Compose** (`.env` file):
- `DOCKER_VOLUME_DIRECTORY` - Volume mount directory (default: `.`)
- `OPENAI_API_KEY` - LLM API key (required for OpenAI provider)
- `OPENAI_BASE_URL` - Custom OpenAI-compatible endpoint
- `OPENAI_MODEL` - LLM model name
- `OPENAI_PROVIDER` - `openai` or `llamacpp` (default: openai)
- `STORE_RESULTS_IN_MILVUS` - Store analysis results in Milvus

**Log Ingestor** (Go):
- `SERVER_PORT` (8080), `MILVUS_ADDRESS` (milvus:19530)
- `EMBEDDING_ENDPOINT`, `EMBEDDING_DIMENSION` (768)
- `NUM_WORKERS` (4), `BATCH_SIZE` (100)
- `SIMILARITY_THRESHOLD` (0.95), `RATE_LIMIT_RPS` (1000)

**AI Analyzer** (Python):
- `MILVUS_HOST` (milvus), `MILVUS_PORT` (19530), `MILVUS_COLLECTION` (timberline_logs)
- `DATABASE_URL` - PostgreSQL connection string
- `ANALYSIS_WINDOW_HOURS` (24), `MAX_LOGS_PER_ANALYSIS` (10000)
- `OPENAI_PROVIDER`, `OPENAI_MODEL`, `OPENAI_API_KEY`

**Web UI** (JavaScript):
- `VITE_API_URL` - Backend API URL (default: `http://localhost:8000`)

## Port Mappings

### Docker Compose (8xxx ports)
- 8200/8201: Log Ingestor (API/Metrics)
- 8530/8091: Milvus (DB/Metrics)
- 8100: Embedding Service
- 8101: Chat Service
- 8020/8090: Fluent Bit (HTTP/Metrics)
- 8300: Attu (Milvus UI)
- 8400: AI Analyzer API
- 8500: Web UI
- 8900/8901: MinIO (API/Console)
- 5432: PostgreSQL

### Kind Cluster (9xxx ports)
- 9200/9201: Log Ingestor (API/Metrics)
- 9530/9091: Milvus (DB/Metrics)
- 9100: Embedding Service
- 9101: Chat Service
- 9020: Fluent Bit Metrics
- 9300: Attu (Milvus UI)
- 9400: AI Analyzer API
- 9500: Web UI
- 9900/9901: MinIO (API/Console)

## Deployment

### Docker Compose
```bash
# Setup and start
cp .env.example .env              # Configure environment
make download-models              # Download AI models (first time)
make docker-up                    # Start all services

# Access services
curl http://localhost:8200/api/v1/healthz    # Log Ingestor
curl http://localhost:8400/health            # AI Analyzer
open http://localhost:8500                   # Web UI
open http://localhost:8300                   # Attu (Milvus UI)
```

### Kubernetes (Helm)
```bash
# Deploy on Kind
make kind-up                      # Creates cluster + deploys Helm chart

# Manual Helm operations
helm install timberline helm/timberline -f helm/timberline/values.yaml
helm upgrade timberline helm/timberline
helm uninstall timberline

# Access services (NodePort on Kind)
curl http://localhost:9200/api/v1/healthz    # Log Ingestor
curl http://localhost:9400/health            # AI Analyzer
open http://localhost:9500                   # Web UI
```

The Helm chart is located in `helm/timberline/` with templates for all services. The Kind setup uses `kind-cluster.yaml` for cluster configuration with port mappings.

## Project Structure

```
timberline/
├── log-ingestor/           # Go HTTP service for log ingestion
│   ├── cmd/main.go        # Entry point
│   ├── internal/          # Core implementation
│   │   ├── handlers/      # HTTP handlers (stream endpoint)
│   │   ├── storage/       # Milvus client
│   │   ├── embedding/     # Embedding service client
│   │   ├── config/        # Environment config
│   │   └── metrics/       # Prometheus metrics
│   └── Makefile
├── ai-analyzer/            # Python LLM analysis service
│   ├── analyzer/
│   │   ├── analysis/      # Analysis engine (clustering, LLM)
│   │   ├── api/           # FastAPI routes
│   │   ├── cli/           # CLI tool
│   │   ├── storage/       # Milvus client
│   │   ├── llm/           # LLM client (OpenAI/llama.cpp)
│   │   ├── db/            # PostgreSQL (SQLAlchemy)
│   │   └── config/        # Settings management
│   ├── tests/
│   └── alembic/           # Database migrations
├── web-ui/                 # React + TypeScript frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── lib/api.ts     # API client
│   │   └── App.tsx
│   ├── nginx.conf         # Production nginx config
│   └── Dockerfile
├── tests/
│   ├── kind/              # Kind integration tests (comprehensive)
│   └── *.py               # Docker integration tests (legacy)
├── scripts/
│   ├── kind-setup.sh      # Setup Kind cluster + Helm deploy
│   ├── download-models.sh # Download AI models
│   └── *.sh
├── helm/timberline/        # Kubernetes Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
├── fluent-bit-config/      # Fluent Bit configuration
├── docker-compose.yaml     # Docker Compose stack
├── kind-cluster.yaml       # Kind cluster configuration
├── Makefile                # Top-level build commands
└── pytest.ini              # Pytest configuration
```

## Key Implementation Details

### Log Ingestor Architecture
- **Worker Pool Pattern**: Channel-based queue with configurable worker goroutines (`NUM_WORKERS`)
- **Fluent Bit Compatibility**: Supports both direct LogEntry format and Fluent Bit JSON format
- **Deduplication**: Uses cosine similarity (`SIMILARITY_THRESHOLD`) to detect duplicate logs
- **Streaming**: JSON Lines format for HTTP streaming ingestion
- See `log-ingestor/CLAUDE.md` for detailed implementation notes

### AI Analyzer Pipeline
1. Query logs from Milvus for analysis window (default 24 hours)
2. Cluster similar logs by Kubernetes labels (app, version, tier)
3. Send clusters to LLM for severity scoring (1-10 scale)
4. Calculate system health score (0-1)
5. Generate LLM summary with actionable insights
6. Store results in PostgreSQL and optionally Milvus
7. Send webhook notification if configured
- See `ai-analyzer/CLAUDE.md` for detailed architecture

### Web UI Architecture
- **State Management**: TanStack Query for all server state
- **Routing**: Simple state-based view switching (TanStack Router installed but not used)
- **API Client**: Namespaced methods in `src/lib/api.ts` (logsApi, analysisApi)
- **Production**: Multi-stage Docker build with nginx, API proxy to avoid CORS
- See `web-ui/CLAUDE.md` for detailed implementation notes

## Database Schemas

### Milvus Collections
- **timberline_logs**: Log entries with embeddings (768-dim vectors)
  - Fields: log_id, message, log_level, namespace, pod_name, container_name, timestamp, k8s labels, embedding, duplicate_count
  - Indexes: Vector index (cosine similarity), scalar indexes on timestamp, namespace, pod_name

### PostgreSQL Tables
- **analyses**: Analysis job metadata (id, start_time, end_time, status, namespace, health_score)
- **clusters**: Cluster information per analysis (cluster_id, labels, severity, representative_logs)
- See `ai-analyzer/alembic/versions/` for migration history

## Common Development Workflows

### Adding a New Feature to Log Ingestor
1. Add types to `internal/models/`
2. Implement business logic in appropriate package (`internal/storage/`, `internal/handlers/`)
3. Add tests in `*_test.go` files
4. Run `make dev` (formats, lints, tests, builds)
5. Update `log-ingestor/CLAUDE.md` if architecture changes

### Adding a New Analysis Feature
1. Update models in `analyzer/models/`
2. Implement in `analyzer/analysis/engine.py`
3. Add tests in `tests/test_analysis.py`
4. Create database migration: `alembic revision --autogenerate -m "description"`
5. Run tests: `pytest`
6. Update `ai-analyzer/CLAUDE.md` if architecture changes

### Adding a New UI Component
1. Create component in `web-ui/src/components/`
2. Add API methods to `src/lib/api.ts` if needed
3. Add types to `src/lib/api.ts` type definitions
4. Use TanStack Query for server state
5. Test manually with `npm run dev`

### Running End-to-End Tests
1. Start Kind cluster: `make kind-up` (or `make docker-up` for Docker)
2. Run tests: `pytest tests/kind/ -v` (or `./scripts/run-integration-tests.sh` for Docker)
3. Debug failures by checking pod logs: `kubectl logs <pod-name>`
4. Clean up: `make kind-down` (or `make docker-down`)

## Troubleshooting

### Services Not Starting
- Check health endpoints: `/api/v1/healthz` (Log Ingestor), `/health` (AI Analyzer)
- Review logs: `docker compose logs <service>` or `kubectl logs <pod>`
- Verify dependencies: Milvus depends on etcd+MinIO, AI Analyzer depends on PostgreSQL+Milvus

### Milvus Connection Issues
- Check Milvus health: `curl http://localhost:8091/healthz` (Docker) or port 9091 (Kind)
- Verify etcd and MinIO are healthy
- Check collection exists: Use Attu UI at localhost:8300 (Docker) or 9300 (Kind)

### Embedding Generation Failures
- Check embedding service health: `curl http://localhost:8100/health` (Docker) or 9100 (Kind)
- Models must be downloaded: `make download-models`
- Model location: `volumes/llama-models/` (Docker) or within cluster (Kind)

### Tests Failing
- Increase timeouts in `tests/kind/conftest.py` for slow environments
- Check if all pods are ready: `kubectl get pods`
- View test pod logs: `kubectl logs -l app=<app-name>`
- Clean test data: See `tests/kind/README.md` troubleshooting section

## Additional Resources

- Component-specific documentation: `log-ingestor/CLAUDE.md`, `ai-analyzer/CLAUDE.md`, `web-ui/CLAUDE.md`
- Integration testing guide: `tests/kind/README.md`
- Helm chart values: `helm/timberline/values.yaml`
- Docker Compose configuration: `docker-compose.yaml`
