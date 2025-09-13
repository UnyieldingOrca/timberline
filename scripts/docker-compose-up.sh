#!/bin/bash

# Start Docker Compose services for Timberline
set -e

echo "🐳 Starting Timberline Docker Environment"
echo "========================================"

# Check if docker compose is available
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ Docker Compose not available. Please install docker-compose or use Docker with Compose plugin"
    exit 1
fi

# Download embedding model if needed
echo "📦 Ensuring embedding model is available..."
mkdir -p volumes/llama-models
if [ ! -f "volumes/llama-models/nomic-embed-text-v1.5.f16.gguf" ]; then
    echo "⬇️ Downloading embedding model..."
    if command -v curl &> /dev/null; then
        curl -L -o volumes/llama-models/nomic-embed-text-v1.5.f16.gguf \
            "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.f16.gguf"
    elif command -v wget &> /dev/null; then
        wget -O volumes/llama-models/nomic-embed-text-v1.5.f16.gguf \
            "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.f16.gguf"
    else
        echo "❌ Neither curl nor wget available for downloading model"
        exit 1
    fi
fi

# Generate test logs if needed
echo "📝 Ensuring test logs are available..."
mkdir -p test-logs
if [ ! -f "test-logs/application.log" ]; then
    if [ -f "./scripts/generate-test-logs.sh" ]; then
        ./scripts/generate-test-logs.sh test-logs
    else
        # Create sample logs
        cat > test-logs/application.log << EOF
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z ERROR Database connection failed: timeout after 30s
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z WARN High memory usage detected: 85%
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z INFO Application started successfully
2024-$(date +%m-%d)T$(date +%H:%M:%S)Z ERROR Failed to process user request: invalid token
EOF
    fi
fi

# Start services using docker compose
echo "🚀 Starting services..."
$COMPOSE_CMD up -d --wait --build

echo "✅ Docker environment started successfully!"
