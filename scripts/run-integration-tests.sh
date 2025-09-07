#!/bin/bash
# Run Timberline integration tests with proper setup
# This script ensures Docker services are running before executing tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Timberline Integration Test Runner${NC}"
echo "=================================="

# Check if Docker Compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose not found${NC}"
    exit 1
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found. Install test requirements:${NC}"
    echo "pip install -r requirements-test.txt"
    exit 1
fi

# Function to check if services are healthy
check_services() {
    echo -e "${YELLOW}Checking Docker services health...${NC}"
    
    local services=("milvus" "log-ingestor" "log-collector" "llama-cpp-embedding" "minio" "etcd")
    local healthy=true
    
    for service in "${services[@]}"; do
        if docker-compose ps "$service" | grep -q "healthy"; then
            echo "✓ $service is healthy"
        else
            echo "✗ $service is not healthy"
            healthy=false
        fi
    done
    
    return $healthy
}

# Check if Docker Compose services are running
echo -e "${YELLOW}Checking Docker Compose services...${NC}"
if ! docker-compose ps | grep -q "Up"; then
    echo -e "${YELLOW}Starting Docker Compose services...${NC}"
    docker-compose up -d
    
    # Wait for services to become healthy
    echo "Waiting for services to become healthy..."
    sleep 30
    
    # Check health status
    max_attempts=10
    attempt=1
    while [ $attempt -le $max_attempts ]; do
        if check_services; then
            echo -e "${GREEN}All services are healthy!${NC}"
            break
        else
            echo "Attempt $attempt/$max_attempts: Some services not ready, waiting..."
            sleep 10
            ((attempt++))
        fi
    done
    
    if [ $attempt -gt $max_attempts ]; then
        echo -e "${RED}Services failed to become healthy after $max_attempts attempts${NC}"
        echo "Service status:"
        docker-compose ps
        exit 1
    fi
else
    echo -e "${GREEN}Docker Compose services are already running${NC}"
fi

# Run the integration tests
echo -e "${YELLOW}Running integration tests...${NC}"

# Test execution options
TEST_ARGS=""
if [ "$1" = "--parallel" ]; then
    TEST_ARGS="-n auto"
    echo "Running tests in parallel"
fi

# Run tests with appropriate markers
pytest tests/docker/ \
    -m "docker and integration" \
    --timeout=300 \
    -v \
    --tb=short \
    --color=yes \
    $TEST_ARGS

test_exit_code=$?

# Report results
if [ $test_exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ All integration tests passed!${NC}"
else
    echo -e "${RED}✗ Some integration tests failed${NC}"
fi

# Show service logs if tests failed
if [ $test_exit_code -ne 0 ] && [ "$2" = "--show-logs" ]; then
    echo -e "${YELLOW}Showing service logs for debugging:${NC}"
    docker-compose logs --tail=50
fi

exit $test_exit_code