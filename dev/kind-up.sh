#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="timberline"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- Cluster ---
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo "Kind cluster '${CLUSTER_NAME}' already exists, skipping creation."
else
    echo "Creating Kind cluster '${CLUSTER_NAME}'..."
    kind create cluster --config "${SCRIPT_DIR}/kind-cluster.yaml" --name "${CLUSTER_NAME}"
fi

# --- Loki stack ---
echo "Applying Loki stack..."
kubectl apply -f "${SCRIPT_DIR}/loki/namespace.yaml"
kubectl apply -f "${SCRIPT_DIR}/loki/loki-config.yaml"
kubectl apply -f "${SCRIPT_DIR}/loki/loki-deployment.yaml"
kubectl apply -f "${SCRIPT_DIR}/loki/loki-service.yaml"

# --- Promtail ---
echo "Applying Promtail..."
kubectl apply -f "${SCRIPT_DIR}/promtail/"

# --- Log generator ---
echo "Applying log generator..."
kubectl apply -f "${SCRIPT_DIR}/log-generator/"

# --- Wait for readiness (rollout status handles pods not yet existing) ---
echo "Waiting for Loki to be ready..."
kubectl -n monitoring rollout status deployment/loki --timeout=120s

echo "Waiting for log generator pods..."
kubectl -n default rollout status deployment/log-generator --timeout=60s

# Wait for logs only if Loki has no data yet
echo "Checking if Loki already has data..."
if curl -sf 'http://localhost:3100/loki/api/v1/labels' | python3 -c "import sys,json; sys.exit(0 if len(json.load(sys.stdin).get('data',[])) > 0 else 1)" 2>/dev/null; then
    echo "Loki already has log data, skipping ingestion wait."
else
    echo "Waiting for logs to be ingested (30s)..."
    sleep 30
fi

echo "Loki ready at http://localhost:3100"
