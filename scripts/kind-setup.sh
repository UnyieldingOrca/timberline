#!/bin/bash
# Setup kind cluster for Timberline integration testing
# This script creates a kind cluster and deploys all necessary services

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

echo -e "${GREEN}Timberline Kind Integration Setup${NC}"
echo "=================================="

# Check if kind is installed
if ! command -v kind &> /dev/null; then
    echo -e "${RED}Error: kind not found. Please install kind: https://kind.sigs.k8s.io/docs/user/quick-start/${NC}"
    exit 1
fi

# Check if kubectl is installed
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}Error: kubectl not found. Please install kubectl${NC}"
    exit 1
fi

# Check if docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker is not running. Please start Docker${NC}"
    exit 1
fi

# Function to check if cluster exists
cluster_exists() {
    kind get clusters | grep -q "^${CLUSTER_NAME}$"
}

# Function to wait for deployment to be ready
wait_for_deployment() {
    local namespace=$1
    local deployment=$2
    local timeout=${3:-300}

    echo -e "${YELLOW}Waiting for $deployment in $namespace to be ready (timeout: ${timeout}s)...${NC}"
    kubectl wait --for=condition=available --timeout=${timeout}s deployment/$deployment -n $namespace
}

# Function to wait for pod to be ready
wait_for_pod() {
    local namespace=$1
    local selector=$2
    local timeout=${3:-300}

    echo -e "${YELLOW}Waiting for pods with selector $selector in $namespace to be ready (timeout: ${timeout}s)...${NC}"
    kubectl wait --for=condition=ready --timeout=${timeout}s pod -l $selector -n $namespace
}

# Create or recreate cluster
if cluster_exists; then
    echo -e "${YELLOW}Cluster $CLUSTER_NAME already exists. Recreating...${NC}"
    kind delete cluster --name $CLUSTER_NAME
fi

echo -e "${BLUE}Creating kind cluster: $CLUSTER_NAME${NC}"
kind create cluster --name $CLUSTER_NAME --config "$PROJECT_ROOT/kind-cluster.yaml"

# Set kubectl context
kubectl cluster-info --context kind-$CLUSTER_NAME

# Build and load Docker images
echo -e "${BLUE}Building and loading Docker images...${NC}"
cd "$PROJECT_ROOT"

# Build log-ingestor image
echo "Building log-ingestor image..."
docker build -t timberline/log-ingestor:latest ./log-ingestor

# Load images into kind cluster
echo "Loading images into kind cluster..."
kind load docker-image timberline/log-ingestor:latest --name $CLUSTER_NAME

# Deploy Kubernetes resources
echo -e "${BLUE}Deploying all Kubernetes resources...${NC}"

# Create namespace first
kubectl apply -f "$PROJECT_ROOT/k8s/namespace.yaml"

# Apply all manifests at once
echo "Applying all Kubernetes manifests..."
kubectl apply -f "$PROJECT_ROOT/k8s/milvus/"
kubectl apply -f "$PROJECT_ROOT/k8s/llm/"
kubectl apply -f "$PROJECT_ROOT/k8s/log-ingestor/"
kubectl apply -f "$PROJECT_ROOT/k8s/fluent-bit/"
kubectl apply -f "$PROJECT_ROOT/k8s/attu/"

echo -e "${YELLOW}Waiting for all deployments to be ready...${NC}"

# Wait for infrastructure services first (they're dependencies)
echo "Waiting for infrastructure services..."
wait_for_deployment timberline etcd 120
wait_for_deployment timberline minio 120

# Wait for Milvus (depends on etcd and minio)
echo "Waiting for Milvus..."
wait_for_deployment timberline milvus 300

# Wait for LLM services (long timeout for model downloads)
echo "Waiting for LLM services (model downloads may take time)..."
wait_for_deployment timberline llama-cpp-embedding 600
wait_for_deployment timberline llama-cpp-chat 600

# Wait for log-ingestor (depends on milvus and embedding service)
echo "Waiting for log-ingestor..."
wait_for_deployment timberline log-ingestor 120

# Wait for Fluent Bit DaemonSet
echo "Waiting for Fluent Bit..."
wait_for_pod timberline "app=fluent-bit" 120

# Wait for Attu (optional UI)
echo "Waiting for Attu..."
wait_for_deployment timberline attu 120

# Health check all services
echo -e "${BLUE}Running health checks...${NC}"

services=(
    "http://localhost:9091/healthz Milvus_Metrics"
    "http://localhost:8000/health Embedding_Service"
    "http://localhost:8001/health Chat_Service"
    "http://localhost:9000/minio/health/live MinIO"
    "http://localhost:8080/api/v1/healthz Log_Ingestor"
    "http://localhost:9092/metrics Log_Ingestor_Metrics"
    "http://localhost:2020/api/v1/health Fluent_Bit"
    "http://localhost:3000 Attu_UI"
)

echo "Checking service health..."
for service in "${services[@]}"; do
    url=$(echo $service | cut -d' ' -f1)
    name=$(echo $service | cut -d' ' -f2)

    if curl -sf "$url" > /dev/null 2>&1; then
        echo -e "✓ $name: ${GREEN}healthy${NC}"
    else
        echo -e "✗ $name: ${RED}unhealthy${NC}"
    fi
done

echo ""
echo -e "${GREEN}✓ Kind cluster setup complete!${NC}"
echo ""
echo "Cluster info:"
echo "  Name: $CLUSTER_NAME"
echo "  Context: kind-$CLUSTER_NAME"
echo ""
echo "Service endpoints:"
echo "  Log Ingestor API: http://localhost:8080"
echo "  Log Ingestor Metrics: http://localhost:9092/metrics"
echo "  Milvus gRPC: localhost:19530"
echo "  Milvus Metrics: http://localhost:9091/healthz"
echo "  Embedding Service: http://localhost:8000"
echo "  Chat Service: http://localhost:8001"
echo "  MinIO Console: http://localhost:9001"
echo "  Attu UI: http://localhost:3000"
echo "  Fluent Bit Metrics: http://localhost:2020"
echo ""
echo "To run integration tests:"
echo "  ./scripts/run-kind-integration-tests.sh"
echo ""
echo "To delete cluster:"
echo "  kind delete cluster --name $CLUSTER_NAME"