# Timberline Log Analysis Platform
# Top-level Makefile for building and testing the entire project

.PHONY: help build test clean docker-up docker-down docker-test kind-setup kind-test test-integration test-kind kind-down install-deps lint fmt check

# Default target - this ensures help is the default when running 'make' without arguments
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Timberline Log Analysis Platform"
	@echo "================================="
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

download-models: ## Download required AI models
	@echo "📦 Downloading AI models..."
	./scripts/download-models.sh

# Docker Compose management
docker-up: download-models ## Start Docker integration environment
	@echo "🐳 Starting Docker integration environment..."
	./scripts/docker-compose-up.sh

docker-down: ## Stop Docker integration environment
	@echo "🐳 Stopping Docker integration environment..."
	docker compose down

docker-test: ## Run Docker integration tests
	@echo "🧪 Running Docker integration tests..."
	./scripts/run-integration-tests.sh

# Kind (Kubernetes in Docker) management
kind-up: ## Setup kind cluster for integration testing
	@echo "🚀 Setting up kind cluster for integration testing..."
	./scripts/kind-setup.sh

kind-down: ## Delete kind cluster
	@echo "🗑️ Deleting kind cluster..."
	kind delete cluster --name timberline-test

install-test-deps: ## Install Python test dependencies
	@echo "📦 Installing Python test dependencies..."
	pip install -r requirements-test.txt

kind-setup: kind-up download-models ## Setup kind cluster for integration testing (alias for kind-up)

kind-test: kind-setup test-integration ## Setup kind cluster and run integration tests

test-integration: ## Run integration tests against existing kind cluster
	@echo "🧪 Running integration tests against kind cluster..."
	pytest tests/kind/ -v

test-kind: test-integration ## Run integration tests against existing kind cluster (alias)
