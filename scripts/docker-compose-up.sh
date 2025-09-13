#!/bin/bash

# Start Docker Compose services for Timberline
set -e

echo "🐳 Starting Timberline Docker Environment"
echo "========================================"

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

# Start services using docker compose
echo "🚀 Starting services..."
docker compose up -d --wait --build

echo "✅ Docker environment started successfully!"
