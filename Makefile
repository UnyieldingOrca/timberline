# Timberline Log Analysis Platform
# Top-level Makefile for building and testing the entire project

.PHONY: help build test clean kind-setup kind-test kind-down install-deps lint fmt check

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

# Kind (Kubernetes in Docker) management
kind-setup: ## Setup kind cluster for integration testing
	@echo "🚀 Setting up kind cluster for integration testing..."
	./scripts/kind-setup.sh

kind-test: kind-setup test-kind ## Setup kind cluster and run integration tests
	@echo "✅ Kind integration test complete"

test-integration: test-kind ## Run integration tests against kind cluster (alias)

test-kind: ## Run integration tests against kind cluster
	@echo "🧪 Running integration tests against kind cluster..."
	./scripts/run-kind-integration-tests.sh

kind-down: ## Delete kind cluster
	@echo "🗑️ Deleting kind cluster..."
	kind delete cluster --name timberline-test

install-test-deps: ## Install Python test dependencies
	@echo "📦 Installing Python test dependencies..."
	pip install -r requirements-test.txt
