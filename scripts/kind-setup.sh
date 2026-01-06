#!/bin/bash
# Setup kind cluster for Timberline integration testing
# This script creates a kind cluster and deploys all necessary services using Helm

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

CLUSTER_NAME="timberline-test"
NAMESPACE="timberline"
RELEASE_NAME="timberline"
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

# Check if helm is installed
if ! command -v helm &> /dev/null; then
    echo -e "${RED}Error: helm not found. Please install helm: https://helm.sh/docs/intro/install/${NC}"
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

# Create cluster if it doesn't exist
if cluster_exists; then
    echo -e "${YELLOW}Cluster $CLUSTER_NAME already exists. Updating deployments...${NC}"
    # Set kubectl context
    kubectl config use-context kind-$CLUSTER_NAME
else
    echo -e "${BLUE}Creating kind cluster: $CLUSTER_NAME${NC}"
    kind create cluster --name $CLUSTER_NAME --config "$PROJECT_ROOT/kind-cluster.yaml"

    # Set kubectl context
    kubectl cluster-info --context kind-$CLUSTER_NAME
fi

# Build and load Docker images
echo -e "${BLUE}Building and loading Docker images...${NC}"
cd "$PROJECT_ROOT"

# Build log-ingestor image
echo "Building log-ingestor image..."
DOCKER_BUILDKIT=1 docker build -t timberline/log-ingestor:latest ./log-ingestor

# Build ai-analyzer image
echo "Building ai-analyzer image..."
DOCKER_BUILDKIT=1 docker build -t timberline/ai-analyzer:latest ./ai-analyzer

# Build web-ui image
echo "Building web-ui image..."
DOCKER_BUILDKIT=1 docker build -t timberline/web-ui:latest ./web-ui

# Load images into kind cluster
echo "Loading images into kind cluster..."
kind load docker-image timberline/log-ingestor:latest --name $CLUSTER_NAME
kind load docker-image timberline/ai-analyzer:latest --name $CLUSTER_NAME
kind load docker-image timberline/web-ui:latest --name $CLUSTER_NAME

# Deploy Kubernetes resources using Helm
echo -e "${BLUE}Deploying Timberline using Helm...${NC}"

# Create namespace
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# Check if release already exists
if helm list -n $NAMESPACE | grep -q "^${RELEASE_NAME}"; then
    echo "Helm release $RELEASE_NAME already exists. Upgrading..."
    helm upgrade $RELEASE_NAME "$PROJECT_ROOT/helm/timberline" \
        --namespace $NAMESPACE \
        --values "$SCRIPT_DIR/values-kind.yaml" \
        --wait \
        --timeout 15m
else
    echo "Installing Helm chart..."
    helm install $RELEASE_NAME "$PROJECT_ROOT/helm/timberline" \
        --namespace $NAMESPACE \
        --create-namespace \
        --values "$SCRIPT_DIR/values-kind.yaml" \
        --wait \
        --timeout 15m
fi

echo -e "${YELLOW}Waiting for all pods to be ready...${NC}"

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n $NAMESPACE --timeout=600s || true

# Health check all services
echo -e "${BLUE}Running health checks...${NC}"

services=(
    "http://localhost:9091/healthz Milvus_Metrics"
    "http://localhost:9100/health Embedding_Service"
    "http://localhost:9101/health Chat_Service"
    "http://localhost:9900/minio/health/live MinIO"
    "http://localhost:9200/api/v1/healthz Log_Ingestor"
    "http://localhost:9201/metrics Log_Ingestor_Metrics"
    "http://localhost:9020/api/v1/health Fluent_Bit"
    "http://localhost:9300 Attu_UI"
    "http://localhost:9400/health AI_Analyzer_API"
    "http://localhost:9500 Web_UI"
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
echo "  Web UI: http://localhost:9500"
echo "  AI Analyzer API: http://localhost:9400"
echo "  Log Ingestor API: http://localhost:9200"
echo "  Log Ingestor Metrics: http://localhost:9201/metrics"
echo "  Attu UI (Milvus): http://localhost:9300"
echo "  Milvus gRPC: localhost:9530"
echo "  Milvus Metrics: http://localhost:9091/healthz"
echo "  Embedding Service: http://localhost:9100"
echo "  Chat Service: http://localhost:9101"
echo "  MinIO API: http://localhost:9900"
echo "  MinIO Console: http://localhost:9901"
echo "  Fluent Bit Metrics: http://localhost:9020"
echo "  PostgreSQL: localhost:5432"
echo ""
echo "To run integration tests:"
echo "  make test-integration"
echo "  # or: pytest tests/docker/ -v"
echo ""
echo "To delete cluster:"
echo "  make kind-down"
echo "  # or: kind delete cluster --name $CLUSTER_NAME"
echo ""
echo "To upgrade deployment:"
echo "  helm upgrade $RELEASE_NAME helm/timberline -n $NAMESPACE"