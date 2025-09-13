"""
Embedding service tests for llama.cpp embedding service.
Tests embedding generation, consistency, and API functionality.
"""

import pytest
import requests


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.parametrize("text", [
    "ERROR: Database connection failed in container",
    "WARN: Memory usage high in service",
    "FATAL: System crash detected in deployment",
    "INFO: Application started successfully"
])
def test_embedding_service_response(embedding_url, text, http_retry):
    """Test that embedding service returns valid embeddings for different text inputs."""
    payload = {
        "model": "nomic-embed-text-v1.5",
        "input": text
    }

    response = http_retry(embedding_url, method="POST", json=payload, timeout=60)
    assert response.status_code == 200, f"Embedding request failed: {response.text}"

    result = response.json()
    assert 'data' in result, "Response missing 'data' field"
    assert len(result['data']) > 0, "No embeddings returned"

    embedding = result['data'][0]['embedding']
    assert isinstance(embedding, list), "Embedding is not a list"
    assert len(embedding) > 0, "Embedding vector is empty"
    assert all(isinstance(x, (int, float)) for x in embedding), "Embedding contains non-numeric values"


@pytest.mark.docker
@pytest.mark.integration
def test_embedding_consistency(embedding_url, http_retry):
    """Test that same input produces consistent embeddings."""
    text = "Test message for consistency check"
    payload = {
        "model": "nomic-embed-text-v1.5",
        "input": text
    }

    # Get embeddings twice
    response1 = http_retry(embedding_url, method="POST", json=payload, timeout=60)
    response2 = http_retry(embedding_url, method="POST", json=payload, timeout=60)

    assert response1.status_code == 200
    assert response2.status_code == 200

    embedding1 = response1.json()['data'][0]['embedding']
    embedding2 = response2.json()['data'][0]['embedding']

    # Embeddings should be identical for the same input
    assert embedding1 == embedding2, "Embeddings are not consistent for same input"


@pytest.mark.docker
@pytest.mark.integration
def test_embedding_vector_dimensions(embedding_url, http_retry):
    """Test that embedding vectors have correct dimensions."""
    text = "Test message for dimension check"
    payload = {
        "model": "nomic-embed-text-v1.5",
        "input": text
    }

    response = http_retry(embedding_url, method="POST", json=payload, timeout=60)
    assert response.status_code == 200

    embedding = response.json()['data'][0]['embedding']
    # nomic-embed-text-v1.5 should produce 768-dimensional vectors
    assert len(embedding) == 768, f"Expected 768 dimensions, got {len(embedding)}"


@pytest.mark.docker
@pytest.mark.integration
def test_embedding_service_health(http_retry):
    """Test embedding service health endpoint."""
    response = http_retry("http://localhost:8000/health", timeout=10)
    assert response.status_code == 200, "Embedding service health check failed"


@pytest.mark.docker
@pytest.mark.integration
def test_batch_embedding_requests(embedding_url, embedding_test_texts, http_retry):
    """Test processing multiple embedding requests."""
    results = []

    for text in embedding_test_texts:
        payload = {
            "model": "nomic-embed-text-v1.5",
            "input": text
        }

        response = http_retry(embedding_url, method="POST", json=payload, timeout=60)
        assert response.status_code == 200, f"Failed for text: {text}"

        result = response.json()
        embedding = result['data'][0]['embedding']
        results.append(embedding)

    # All embeddings should be different (not identical vectors)
    assert len(set(tuple(emb) for emb in results)) == len(results), \
        "All embeddings are identical, expected different vectors for different texts"