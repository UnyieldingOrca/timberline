#!/bin/bash
# Run Timberline integration tests against kind cluster
# This script ensures kind cluster is ready before executing tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CLUSTER_NAME="timberline-test"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}Timberline Kind Integration Test Runner${NC}"
echo "========================================"

# Check if kind cluster exists
if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
    echo -e "${RED}Error: Kind cluster '$CLUSTER_NAME' not found${NC}"
    echo "Please run './scripts/kind-setup.sh' first"
    exit 1
fi

# Check if kubectl context is correct
if ! kubectl config current-context | grep -q "kind-${CLUSTER_NAME}"; then
    echo -e "${YELLOW}Setting kubectl context to kind-${CLUSTER_NAME}${NC}"
    kubectl config use-context kind-${CLUSTER_NAME}
fi

# Check if pytest is available
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest not found. Install test requirements:${NC}"
    echo "pip install -r requirements-test.txt"
    exit 1
fi

# Function to check service health
check_service_health() {
    local url=$1
    local name=$2
    local max_attempts=${3:-30}
    local attempt=1

    echo -e "${YELLOW}Checking $name health...${NC}"

    while [ $attempt -le $max_attempts ]; do
        if curl -sf "$url" > /dev/null 2>&1; then
            echo -e "✓ $name: ${GREEN}healthy${NC}"
            return 0
        else
            echo "Attempt $attempt/$max_attempts: $name not ready, waiting..."
            sleep 2
            ((attempt++))
        fi
    done

    echo -e "✗ $name: ${RED}unhealthy after $max_attempts attempts${NC}"
    return 1
}

# Function to check all critical services
check_all_services() {
    echo -e "${BLUE}Checking service health...${NC}"

    local services=(
        "http://localhost:9091/healthz Milvus"
        "http://localhost:8000/health Embedding_Service"
        "http://localhost:8001/health Chat_Service"
        "http://localhost:9000/minio/health/live MinIO"
        "http://localhost:8080/api/v1/healthz Log_Ingestor"
    )

    local all_healthy=true

    for service in "${services[@]}"; do
        url=$(echo $service | cut -d' ' -f1)
        name=$(echo $service | cut -d' ' -f2)

        if ! check_service_health "$url" "$name" 10; then
            all_healthy=false
        fi
    done

    if [ "$all_healthy" = "true" ]; then
        return 0
    else
        return 1
    fi
}

# Check if services are healthy
if ! check_all_services; then
    echo -e "${RED}Some services are not healthy. Please check the cluster status:${NC}"
    echo "kubectl get pods -n timberline"
    echo "kubectl get services -n timberline"
    exit 1
fi

# Set environment variables for tests
export KIND_CLUSTER=true
export KUBECONFIG_CONTEXT="kind-${CLUSTER_NAME}"

echo -e "${BLUE}Running integration tests against kind cluster...${NC}"

# Test execution options
TEST_ARGS="--tb=short --color=yes -v"

# Add parallel execution if requested
if [ "$1" = "--parallel" ]; then
    echo "Running tests in parallel"
    TEST_ARGS="$TEST_ARGS -n auto"
fi

# Run the integration tests
pytest tests/docker/ \
    --timeout=300 \
    $TEST_ARGS

test_exit_code=$?


# Report results
if [ $test_exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ All kind integration tests passed!${NC}"
    echo ""
    echo "Test environment info:"
    echo "  Cluster: $CLUSTER_NAME"
    echo "  Context: $(kubectl config current-context)"
    echo "  Nodes: $(kubectl get nodes --no-headers | wc -l)"
    echo "  Pods: $(kubectl get pods -n timberline --no-headers | wc -l)"
else
    echo -e "${RED}✗ Some integration tests failed${NC}"

    # Show service logs if tests failed
    if [ "$2" = "--show-logs" ] || [ "$1" = "--show-logs" ]; then
        echo -e "${YELLOW}Showing service logs for debugging:${NC}"
        echo ""
        echo "Log Ingestor logs:"
        kubectl logs -n timberline -l app=log-ingestor --tail=50
        echo ""
        echo "Fluent Bit logs:"
        kubectl logs -n timberline -l app=fluent-bit --tail=50
        echo ""
        echo "Milvus logs:"
        kubectl logs -n timberline -l app=milvus --tail=50
    fi
fi

echo ""
echo "To view cluster status:"
echo "  kubectl get all -n timberline"
echo ""
echo "To access services directly:"
echo "  kubectl port-forward -n timberline svc/log-ingestor 8080:8080"
echo "  kubectl port-forward -n timberline svc/milvus 19530:19530"

exit $test_exit_code