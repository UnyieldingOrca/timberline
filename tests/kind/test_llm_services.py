"""
LLM services functional tests for Timberline Kind deployment.

Tests that verify llama.cpp embedding and chat services business logic.
"""

import pytest


@pytest.mark.health
class TestEmbeddingServiceAPI:
    """Test Embedding Service API functionality."""

    def test_embedding_service_generate_embeddings(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test Embedding Service can generate embeddings."""
        health_url = f"{service_urls['embedding_service']}/health"
        wait_for_service_ready(health_url)

        # Send embedding request
        url = f"{service_urls['embedding_service']}/v1/embeddings"
        payload = {
            "input": "This is a test log message for embedding generation",
            "model": "nomic-embed-text-v1.5"
        }

        response = http_retry(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )

        assert response.status_code == 200

        data = response.json()

        # Verify response structure
        assert "data" in data
        assert len(data["data"]) > 0
        assert "embedding" in data["data"][0]

        # Verify embedding dimension (nomic-embed is 768-dimensional)
        embedding = data["data"][0]["embedding"]
        assert len(embedding) == 384

        # Verify embeddings are normalized floats
        assert all(isinstance(val, (int, float)) for val in embedding)

    def test_embedding_service_batch_embeddings(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test Embedding Service can generate batch embeddings."""
        health_url = f"{service_urls['embedding_service']}/health"
        wait_for_service_ready(health_url)

        # Send batch embedding request
        url = f"{service_urls['embedding_service']}/v1/embeddings"
        payload = {
            "input": [
                "First test message",
                "Second test message",
                "Third test message"
            ],
            "model": "nomic-embed-text-v1.5"
        }

        response = http_retry(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        assert response.status_code == 200

        data = response.json()

        # Should have 3 embeddings
        assert "data" in data
        assert len(data["data"]) == 3

        # Each should have 768-dimensional embedding
        for item in data["data"]:
            assert "embedding" in item
            assert len(item["embedding"]) == 384


@pytest.mark.health
class TestLLMChatServiceAPI:
    """Test LLM Chat Service API functionality."""

    def test_llm_chat_service_generate_completion(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test LLM Chat Service can generate completions."""
        health_url = f"{service_urls['llm_chat']}/health"
        wait_for_service_ready(health_url)

        # Send chat completion request
        url = f"{service_urls['llm_chat']}/v1/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say 'test successful' and nothing else."}
            ],
            "max_tokens": 200,
            "temperature": 0.1,
        }

        response = http_retry(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=90  # LLM inference can take longer
        )

        assert response.status_code == 200

        data = response.json()

        # Verify response structure
        assert "choices" in data
        assert len(data["choices"]) > 0
        assert "message" in data["choices"][0]
        assert "content" in data["choices"][0]["message"]

        # Should have generated some text
        content = data["choices"][0]["message"]["content"]
        assert len(content) > 0

    def test_llm_chat_service_with_system_prompt(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test LLM Chat Service with system prompt."""
        health_url = f"{service_urls['llm_chat']}/health"
        wait_for_service_ready(health_url)

        url = f"{service_urls['llm_chat']}/v1/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": "You are a helpful log analysis assistant."},
                {"role": "user", "content": "What is your purpose?"}
            ],
            "max_tokens": 50,
            "temperature": 0.7
        }

        response = http_retry(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=90
        )

        assert response.status_code == 200

        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
