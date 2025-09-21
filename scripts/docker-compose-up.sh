#!/bin/bash

# Start Docker Compose services for Timberline
set -e

echo "🐳 Starting Timberline Docker Environment"
echo "========================================"

# Start services using docker compose
echo "🚀 Starting services..."
docker compose up -d --wait --build

echo "✅ Docker environment started successfully!"