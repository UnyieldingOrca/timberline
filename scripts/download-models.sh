#!/bin/bash

# Download models for Timberline AI analyzer
# This script downloads the required models for Kubernetes deployment
# Models are downloaded to a local cache and loaded into kind nodes

set -e

MODELS_DIR="./volumes/llama-models"
EMBEDDING_MODEL="nomic-embed-text-v1.5.f16.gguf"
CHAT_MODEL="Qwen3-0.6B-Q4_K_M.gguf"

# Create models directory if it doesn't exist
mkdir -p "$MODELS_DIR"

echo "🔍 Checking for required models in $MODELS_DIR..."

# Function to download a model if it doesn't exist
download_model() {
    local model_name="$1"
    local model_url="$2"
    local model_path="$MODELS_DIR/$model_name"

    if [[ -f "$model_path" ]]; then
        echo "✅ $model_name already exists"
    else
        echo "⬇️  Downloading $model_name..."
        echo "   Source: $model_url"
        echo "   Target: $model_path"

        # Use curl with progress bar and resume capability
        curl -L --progress-bar --continue-at - -o "$model_path" "$model_url"

        if [[ -f "$model_path" ]]; then
            echo "✅ Successfully downloaded $model_name"
        else
            echo "❌ Failed to download $model_name"
            exit 1
        fi
    fi
}

echo ""
echo "📦 Downloading Embedding Model..."
download_model "$EMBEDDING_MODEL" \
    "https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.f16.gguf"

echo ""
echo "🧠 Downloading Chat Model (Qwen3 0.6B)..."
download_model "$CHAT_MODEL" \
    "https://huggingface.co/unsloth/Qwen3-0.6B-GGUF/resolve/main/Qwen3-0.6B-Q4_K_M.gguf"

echo ""
echo "🎉 All models downloaded successfully!"
echo ""
echo "📊 Model Information:"
echo "   Embedding Model: $EMBEDDING_MODEL (~274MB) - Used for log vectorization"
echo "   Chat Model: $CHAT_MODEL (~370MB) - Used for AI analysis and reasoning"
echo ""
echo "💡 You can now start the services with: make kind-setup"