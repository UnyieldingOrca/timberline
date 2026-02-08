# Timberline - Agentic Loki Log Analysis

# Show available recipes
default:
    @just --list

# Install package in editable mode
install:
    pip install -e ".[all]"

# Full dev cycle: format, lint, test
dev: fmt lint test

# Run tests
test:
    pytest

# Run linter
lint:
    ruff check timberline/ tests/

# Format code
fmt:
    black timberline/ tests/
    ruff check --fix timberline/ tests/

# Run analysis (e.g. just run --since 1h)
run *ARGS:
    timberline analyze {{ ARGS }}

# Check Loki and LLM connectivity
health:
    timberline health

# Create Kind cluster with Loki + log generator (idempotent)
kind-up:
    dev/kind-up.sh

# Delete Kind cluster
kind-down:
    kind delete cluster --name timberline

# Check that Loki has data
kind-logs:
    @curl -s 'http://localhost:3100/loki/api/v1/labels' | python3 -m json.tool
