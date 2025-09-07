# Timberline Log Analysis Platform
# Top-level Makefile for building and testing the entire project

.PHONY: help build test clean docker-up docker-down docker-test install-deps lint fmt check

# Default target - this ensures help is the default when running 'make' without arguments
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Timberline Log Analysis Platform"
	@echo "================================="
	@echo ""
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Docker management
docker-up: ## Start Docker integration environment
	@echo "🐳 Starting Docker integration environment..."
	./scripts/start-docker-integration-test.sh

docker-down: ## Stop Docker integration environment
	@echo "🐳 Stopping Docker integration environment..."
	docker compose down --volumes --remove-orphans

docker-test: docker-up test-integration ## Start Docker services and run integration tests
	@echo "✅ Docker integration test complete"

docker-logs: ## Show Docker service logs
	@if command -v docker compose &> /dev/null; then \
		docker compose logs; \
	else \
		docker-compose logs; \
	fi

docker-status: ## Show Docker service status
	@if command -v docker compose &> /dev/null; then \
		docker compose ps; \
	else \
		docker-compose ps; \
	fi

test-integration: install-test-deps ## Run Docker integration tests
	@echo "🧪 Running Docker integration tests..."
	./scripts/run-integration-tests.sh

test-integration-parallel: install-test-deps ## Run Docker integration tests in parallel
	@echo "🧪 Running Docker integration tests in parallel..."
	./scripts/run-integration-tests.sh --parallel

test-pipeline: docker-up ## Test complete log pipeline (collector → ingestor → Milvus)
	@echo "🧪 Testing complete log processing pipeline..."
	./scripts/run-integration-tests.sh
	@echo "✅ Pipeline tests complete"


install-test-deps: ## Install Python test dependencies
	@echo "📦 Installing Python test dependencies..."
	pip install -r requirements-test.txt
