#!/bin/bash

# Start Docker Compose-based integration testing environment for Timberline
set -e

echo "🐳 Starting Timberline Docker Integration Test Environment"
echo "========================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠️${NC} $1"
}

print_error() {
    echo -e "${RED}❌${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ️${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check if docker is installed and running
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker"
        exit 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker is not running. Please start Docker"
        exit 1
    fi

    # Check if docker-compose is available
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not available. Please install docker-compose or use Docker with Compose plugin"
        exit 1
    fi

    print_status "Prerequisites check passed"
}

# Download embedding model
download_embedding_model() {
    print_info "Downloading embedding model..."

    # Ensure model directory exists
    mkdir -p volumes/llama-models

    # Check if model already exists
    if [ -f "volumes/llama-models/nomic-embed-text-v1.5.f16.gguf" ]; then
        print_status "Embedding model already exists"
        return
    fi

    # Download the nomic embedding model
    print_info "Downloading nomic-embed-text-v1.5.f16.gguf model..."
    if command -v wget &> /dev/null; then
        wget -O volumes/llama-models/nomic-embed-text-v1.5.f16.gguf \
            "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.f16.gguf"
    elif command -v curl &> /dev/null; then
        curl -L -o volumes/llama-models/nomic-embed-text-v1.5.f16.gguf \
            "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.f16.gguf"
    else
        print_error "Neither wget nor curl is available. Please install one of them or manually download the model to volumes/llama-models/nomic-embed-text-v1.5.f16.gguf"
        exit 1
    fi

    if [ $? -eq 0 ]; then
        print_status "Embedding model downloaded successfully"
    else
        print_error "Failed to download embedding model"
        exit 1
    fi
}

# Generate test logs
generate_test_logs() {
    print_info "Generating test logs..."

    # Ensure test logs directory exists
    mkdir -p test-logs

    # Generate logs using the existing script
    if [ -f "./scripts/generate-test-logs.sh" ]; then
        ./scripts/generate-test-logs.sh test-logs
        print_status "Test logs generated"
    else
        print_warning "Test log generation script not found, creating sample logs..."
        # Create some sample logs for testing
        cat > test-logs/application.log << EOF
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z ERROR Database connection failed: timeout after 30s
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z WARN High memory usage detected: 85%
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z INFO Application started successfully
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z ERROR Failed to process user request: invalid token
EOF
        print_status "Sample test logs created"
    fi
}

# Build and start services
start_services() {
    print_info "Building and starting Docker Compose services..."

    # Use docker compose if available, otherwise docker-compose
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Stop any existing services first
    print_info "Stopping any existing services..."
    $COMPOSE_CMD down --remove-orphans || true

    # Build and start services
    print_info "Building log-collector image..."
    $COMPOSE_CMD build log-collector

    print_info "Starting all services..."
    $COMPOSE_CMD up -d

    if [ $? -eq 0 ]; then
        print_status "Services started successfully"
    else
        print_error "Failed to start services"
        exit 1
    fi
}

# Wait for services to be healthy
wait_for_services() {
    print_info "Waiting for services to be healthy..."

    # Use docker compose if available, otherwise docker-compose
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi

    # Wait for critical services to be healthy
    print_info "Waiting for etcd to be healthy..."
    timeout=300
    while [ $timeout -gt 0 ]; do
        if $COMPOSE_CMD ps etcd | grep -q "healthy"; then
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done

    if [ $timeout -le 0 ]; then
        print_error "etcd failed to become healthy"
        exit 1
    fi

    print_info "Waiting for minio to be healthy..."
    timeout=300
    while [ $timeout -gt 0 ]; do
        if $COMPOSE_CMD ps minio | grep -q "healthy"; then
            break
        fi
        sleep 5
        timeout=$((timeout - 5))
    done

    if [ $timeout -le 0 ]; then
        print_error "minio failed to become healthy"
        exit 1
    fi

    print_info "Waiting for milvus to be healthy..."
    timeout=600
    while [ $timeout -gt 0 ]; do
        if $COMPOSE_CMD ps milvus | grep -q "healthy"; then
            break
        fi
        sleep 10
        timeout=$((timeout - 10))
    done

    if [ $timeout -le 0 ]; then
        print_warning "milvus health check timed out, but continuing..."
    fi

    print_info "Waiting for llama.cpp embedding service to be healthy..."
    timeout=300
    while [ $timeout -gt 0 ]; do
        if $COMPOSE_CMD ps llama-cpp-embedding | grep -q "healthy"; then
            break
        fi
        sleep 10
        timeout=$((timeout - 10))
    done

    if [ $timeout -le 0 ]; then
        print_warning "llama.cpp embedding service health check timed out, but continuing..."
    fi

    # Give additional time for services to stabilize
    print_info "Allowing services to stabilize..."
    sleep 10

    print_status "Services are ready (or timed out with warnings)"
}

# Display service information
display_services() {
    echo ""
    echo "🔗 Available services:"
    echo "   • Milvus Vector DB:      http://localhost:19530"
    echo "   • Milvus Metrics:        http://localhost:9091"
    echo "   • MinIO Console:         http://localhost:9001 (admin: minioadmin/minioadmin)"
    echo "   • MinIO API:             http://localhost:9000"
    echo "   • llama.cpp Embedding:   http://localhost:8000"
    echo "   • Log Collector Metrics: http://localhost:9090/metrics"
    echo ""
    echo "📊 Service Status:"
    if docker compose version &> /dev/null; then
        docker compose ps
    else
        docker-compose ps
    fi
}

# Main execution
main() {
    check_prerequisites
    download_embedding_model
    generate_test_logs
    start_services
    wait_for_services

    print_status "Docker integration test environment started successfully!"
    display_services
}

# Execute main function
main "$@"