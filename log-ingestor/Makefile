# Makefile for Timberline Log Ingestor

# Variables
BINARY_NAME = log-ingestor
GO_VERSION = 1.23
DOCKER_IMAGE = timberline/log-ingestor
DOCKER_TAG ?= latest

# Go commands
GOCMD = go
GOBUILD = $(GOCMD) build
GOCLEAN = $(GOCMD) clean
GOTEST = $(GOCMD) test
GOGET = $(GOCMD) get
GOMOD = $(GOCMD) mod
GOLINT = golangci-lint

# Build flags
BUILD_FLAGS = -ldflags='-w -s -extldflags "-static"'
BUILD_DIR = .

.PHONY: help all build test clean deps fmt lint run docker-build docker-push

# Default target
help: ## Show this help message
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build the application
	@echo "Building $(BINARY_NAME)..."
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 $(GOBUILD) $(BUILD_FLAGS) -o $(BINARY_NAME) cmd/main.go
	@echo "Build complete: $(BINARY_NAME)"

test: ## Run tests
	@echo "Running tests..."
	$(GOTEST) -v -race -coverprofile=coverage.out ./...
	@echo "Tests complete"

test-coverage: test ## Run tests with coverage report
	@echo "Generating coverage report..."
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

clean: ## Clean build artifacts
	@echo "Cleaning..."
	$(GOCLEAN)
	rm -f $(BINARY_NAME)
	rm -f coverage.out coverage.html
	@echo "Clean complete"

deps: ## Download dependencies
	@echo "Downloading dependencies..."
	$(GOMOD) download
	$(GOMOD) tidy
	@echo "Dependencies updated"

fmt: ## Format code
	@echo "Formatting code..."
	$(GOCMD) fmt ./...
	@echo "Format complete"

lint: ## Lint code
	@echo "Running linter..."
	@echo "Running go vet..."
	$(GOCMD) vet ./...
	@echo "Running gofmt check..."
	@if [ -n "$$(gofmt -d .)" ]; then \
		echo "Code is not properly formatted. Please run 'make fmt'"; \
		gofmt -d .; \
		exit 1; \
	fi
	@echo "Running go mod tidy check..."
	$(GOCMD) mod tidy
	@if [ -n "$$(git status --porcelain go.mod go.sum)" ]; then \
		echo "go.mod or go.sum is not tidy. Please run 'go mod tidy'"; \
		exit 1; \
	fi
	@echo "Checking for ineffassign (if available)..."
	@if command -v ineffassign >/dev/null 2>&1; then \
		ineffassign ./...; \
	else \
		echo "ineffassign not available, skipping"; \
	fi
	@echo "Lint complete"

run: build ## Run the application locally
	@echo "Running $(BINARY_NAME)..."
	./$(BINARY_NAME)

docker-build: ## Build Docker image
	@echo "Building Docker image $(DOCKER_IMAGE):$(DOCKER_TAG)..."
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .
	@echo "Docker build complete"

docker-push: docker-build ## Push Docker image
	@echo "Pushing Docker image $(DOCKER_IMAGE):$(DOCKER_TAG)..."
	docker push $(DOCKER_IMAGE):$(DOCKER_TAG)
	@echo "Docker push complete"

dev: fmt lint test build ## Quick development cycle (format, lint, test, build)
