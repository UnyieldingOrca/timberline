# Timberline AI-Powered Log Analysis Platform

Timberline is an AI-powered log analysis platform for Kubernetes environments with Go log-ingestor, Python AI analyzer, Fluent Bit log collection, and comprehensive Docker/Kind-based testing.

**ALWAYS reference these instructions first. Only use additional search or bash commands when you encounter unexpected information that contradicts what is documented here.**

## Working Effectively

### Bootstrap and Build the Repository

1. **Install system dependencies and tools:**
   ```bash
   # Go 1.23+ is required (verified: 1.24.7 available)
   go version  # Should show 1.23+
   
   # Install golangci-lint for Go linting (30 seconds)
   curl -sSfL https://raw.githubusercontent.com/golangci/golangci-lint/master/install.sh | sh -s -- -b $(go env GOPATH)/bin v1.55.2
   export PATH=$PATH:$(go env GOPATH)/bin
   
   # Verify Python 3.11+ (verified: 3.12.3 available)
   python3 --version  # Should show 3.11+
   
   # Docker and Kubernetes tools (all verified available)
   docker --version   # For integration testing
   kind version      # For Kubernetes testing
   kubectl version   # For cluster management
   ```

2. **Install Python test dependencies (18 seconds):**
   ```bash
   pip3 install -r requirements-test.txt
   ```

3. **Download AI models (network dependent - may fail in restricted environments):**
   ```bash
   make download-models  # Downloads ~644MB of AI models
   # NOTE: This command may fail with "Could not resolve host: huggingface.co" in restricted environments
   # If it fails, document this limitation and continue - models are only needed for full integration testing
   ```

### Build the Go Log-Ingestor Component

Navigate to the log-ingestor directory for all Go component work:

```bash
cd log-ingestor

# Download Go dependencies (25 seconds first time, cached after)
make deps

# Format Go code (<1 second)
make fmt

# Build the log-ingestor (22 seconds first build, <1 second subsequent builds)
make build

# Run tests (31 seconds - comprehensive test suite with race detection)
# NEVER CANCEL: Test suite takes 31 seconds. Set timeout to 60+ seconds.
make test

# Run linting (14 seconds - expects some test mock issues, this is normal)
# NEVER CANCEL: Linter takes 14 seconds. Set timeout to 30+ seconds.
make lint

# Quick development cycle: format + lint + test + build (fails on lint issues - use individual commands)
make dev

# Run the service locally (requires Milvus and embedding service dependencies)
make run
```

### Available Log-Ingestor Make Targets

```bash
make help           # Show all available targets
make build          # Build binary (22s first, <1s subsequent)
make test           # Run tests with race detection (31s)
make test-coverage  # Generate HTML coverage report
make clean          # Clean build artifacts (<1s)
make deps           # Download and tidy Go dependencies (25s)
make fmt            # Format Go code (<1s)
make lint           # Run golangci-lint (14s, expect test mock issues)
make run            # Build and run locally (needs dependencies)
make docker-build   # Build Docker image
make dev            # Quick dev cycle (fails on lint - use individual commands)
```

### Python AI Analyzer Component

```bash
cd ai-analyzer

# Install in development mode (may fail in restricted network environments)
pip3 install -e .
# NOTE: May fail with "The read operation timed out" in restricted environments
# This is expected and documented limitation

# The component uses pyproject.toml for configuration and has these key dependencies:
# - pandas>=2.0.0, numpy>=1.24.0, scikit-learn>=1.3.0
# - pymilvus>=2.6.0, openai>=1.0.0, anthropic>=0.3.0
# - python-dotenv>=1.0.0, loguru>=0.7.0, httpx>=0.24.0, click>=8.0.0
```

### Docker Integration Testing

**NEVER CANCEL builds or long-running tests - they may take significant time.**

```bash
# Start Docker compose environment (time varies based on image downloads)
# NEVER CANCEL: Initial startup may take 10+ minutes downloading images. Set timeout to 20+ minutes.
make docker-up

# Run Docker integration tests (60 comprehensive tests)
# NEVER CANCEL: Integration tests take 5-10 minutes. Set timeout to 15+ minutes.
make test-docker

# Start services and run tests in one command
# NEVER CANCEL: Full Docker test cycle takes 15-25 minutes. Set timeout to 30+ minutes.
make docker-test

# Stop Docker environment
make docker-down
```

### Kind (Kubernetes in Docker) Testing

**NEVER CANCEL cluster setup or integration tests - they require significant time for downloads and initialization.**

```bash
# Setup Kind cluster for integration testing
# NEVER CANCEL: Cluster setup takes 15-30 minutes for downloads and pod initialization. Set timeout to 45+ minutes.
make kind-setup

# Run integration tests against existing Kind cluster
# NEVER CANCEL: Integration tests take 10-15 minutes. Set timeout to 20+ minutes.
make test-kind

# Setup cluster and run tests in one command
# NEVER CANCEL: Full Kind test cycle takes 30-45 minutes. Set timeout to 60+ minutes.
make kind-test

# Delete Kind cluster
make kind-down
```

## Validation

### Code Quality Validation
Always run these commands before completing changes:
```bash
cd log-ingestor
export PATH=$PATH:$(go env GOPATH)/bin
make fmt && make build && make test
# Note: make lint has known test mock issues - this is expected
```

### Integration Testing Validation
Choose one of these comprehensive validation approaches:

1. **Docker-based validation (recommended for development):**
   ```bash
   make docker-test  # Full Docker environment testing (15-25 minutes)
   ```

2. **Kind-based validation (recommended for Kubernetes features):**
   ```bash
   make kind-test    # Full Kubernetes environment testing (30-45 minutes)
   ```

### Functional Validation Scenarios

After making changes, ALWAYS test these scenarios:

1. **Log-ingestor functional test:**
   ```bash
   cd log-ingestor && make build && timeout 5s ./log-ingestor
   # Expected: Service starts, shows "Starting log ingestor service", then warns about missing dependencies
   # This confirms the service builds and initializes correctly
   ```

2. **API endpoint validation (requires Docker environment):**
   ```bash
   # With Docker environment running:
   curl http://localhost:8080/api/v1/healthz     # Should return 200 OK
   curl http://localhost:9092/metrics            # Should return Prometheus metrics
   ```

3. **Integration test sample:**
   ```bash
   # Run specific test categories
   pytest tests/docker/test_log_ingestor.py -v    # Log ingestion tests
   pytest tests/docker/test_service_health.py -v  # Health check tests
   pytest tests/docker/ -m "not slow" -v          # Fast tests only
   ```

## Common Issues and Solutions

### Network Connectivity Issues
- **Model downloads fail:** Expected in restricted environments. Document the limitation and continue.
- **Python package installation timeouts:** Use existing packages from requirements-test.txt when possible.
- **Docker image pulls slow:** Allow extra time (20+ minutes) for initial setup.

### Build Issues
- **golangci-lint not found:** Run the install command from Bootstrap section.
- **Go dependencies timeout:** Increase timeout to 300+ seconds for first-time downloads.
- **Test mock errors in linting:** Expected issue with test files. Main code should lint cleanly.

### Docker/Kind Issues
- **Services not ready:** Wait for health checks. Kind setup includes automatic health validation.
- **Port conflicts:** Ensure no other services are using ports 8080, 8000, 8001, 9091, 9092, 19530.
- **Storage permissions:** Docker volumes are created automatically in ./volumes/

## Performance Expectations

### Build Times (with dependencies cached)
- Go dependencies download: 25 seconds (first time)
- Go build: <1 second (after first build of 22 seconds)
- Go tests: 31 seconds (comprehensive test suite)
- Go formatting: <1 second
- Go linting: 14 seconds
- Python test deps: 18 seconds

### Integration Test Times
- Docker compose startup: 10-15 minutes (with image downloads)
- Docker integration tests: 5-10 minutes (60 tests)
- Kind cluster setup: 15-30 minutes (with image downloads)
- Kind integration tests: 10-15 minutes
- Model downloads: 5-10 minutes (when network allows)

## Repository Structure

```
timberline/
├── log-ingestor/           # Go REST API service (primary component)
│   ├── cmd/main.go        # Application entry point
│   ├── internal/          # Core implementation modules
│   ├── Makefile           # Build automation (primary build commands)
│   └── go.mod             # Go dependencies
├── ai-analyzer/            # Python analysis engine
│   ├── analyzer/          # Core analysis modules
│   ├── pyproject.toml     # Python project configuration
│   └── tests/             # Python unit tests
├── tests/docker/           # Integration test suite (60 tests)
├── scripts/               # Automation scripts (docker-compose-up.sh, kind-setup.sh, etc.)
├── k8s/                   # Kubernetes manifests
├── fluent-bit/            # Log collection configuration
├── docker-compose.yaml    # Development environment definition
├── Makefile               # Top-level orchestration (primary entry point)
└── requirements-test.txt  # Python test dependencies
```

## Key Service Endpoints (when running)

- **Log Ingestor API:** http://localhost:8080
- **Log Ingestor Health:** http://localhost:8080/api/v1/healthz
- **Log Ingestor Metrics:** http://localhost:9092/metrics
- **Milvus Database:** localhost:19530 (gRPC), http://localhost:9091/healthz (health)
- **Embedding Service:** http://localhost:8000
- **Chat Service:** http://localhost:8001
- **Attu UI (Milvus admin):** http://localhost:3000
- **MinIO Console:** http://localhost:9001

## Top-Level Commands Reference

```bash
make help              # Show all available commands
make download-models   # Download AI models (may fail in restricted networks)
make docker-up         # Start Docker integration environment
make docker-test       # Full Docker testing cycle (15-25 min)
make kind-setup        # Setup Kind cluster (15-30 min)
make kind-test         # Full Kind testing cycle (30-45 min)
make install-test-deps # Install Python test dependencies
```

**Remember: NEVER CANCEL long-running builds or tests. Always use appropriate timeouts (30+ minutes for full test cycles).**