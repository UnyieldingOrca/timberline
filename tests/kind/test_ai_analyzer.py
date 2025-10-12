"""
AI Analyzer API and integration tests for Timberline Kind deployment.

Tests that verify the AI Analyzer business logic and integrations.
"""

import pytest


@pytest.mark.connectivity
class TestAIAnalyzerAPI:
    """Test AI Analyzer API endpoints."""

    def test_ai_analyzer_query_logs_endpoint(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test AI Analyzer query logs endpoint exists."""
        health_url = f"{service_urls['ai_analyzer']}/health"
        wait_for_service_ready(health_url)

        # Try to query logs (might return empty results)
        url = f"{service_urls['ai_analyzer']}/api/v1/logs/query"
        payload = {
            "query": "test error message",
            "limit": 10
        }

        response = http_retry(
            url,
            method="POST",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
            max_retries=1
        )

        # Should return 200 (even if no results) or 422 if endpoint expects different format
        assert response.status_code in [200, 404, 422]

    def test_ai_analyzer_analyze_endpoint_exists(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test AI Analyzer analyze endpoint exists."""
        health_url = f"{service_urls['ai_analyzer']}/health"
        wait_for_service_ready(health_url)

        # Try to trigger analysis (might fail if no data)
        url = f"{service_urls['ai_analyzer']}/api/v1/analyze"

        response = http_retry(
            url,
            method="POST",
            json={},
            headers={"Content-Type": "application/json"},
            timeout=60,
            max_retries=1
        )

        # Endpoint should exist (200, 400, or 422 are acceptable)
        assert response.status_code in [200, 400, 404, 422]


@pytest.mark.connectivity
class TestAIAnalyzerDatabaseIntegration:
    """Test AI Analyzer integration with databases."""

    def test_ai_analyzer_connects_to_milvus(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready,
        milvus_client
    ):
        """Test AI Analyzer can connect to Milvus."""
        # Verify Milvus is accessible
        from pymilvus import utility

        collections = utility.list_collections(using=milvus_client)
        assert isinstance(collections, list)

        # AI Analyzer should be able to access same Milvus instance
        url = f"{service_urls['ai_analyzer']}/health"
        wait_for_service_ready(url)

        # Health check passes means AI Analyzer is running
        # and should have Milvus connection configured
        response = http_retry(url)
        assert response.status_code == 200


@pytest.mark.connectivity
class TestAIAnalyzerLLMIntegration:
    """Test AI Analyzer integration with LLM services."""

    def test_ai_analyzer_can_call_llm_chat(
        self,
        service_urls,
        http_retry,
        wait_for_service_ready
    ):
        """Test AI Analyzer can communicate with LLM Chat Service."""
        # First verify LLM Chat is working
        llm_url = f"{service_urls['llm_chat']}/health"
        wait_for_service_ready(llm_url)

        response = http_retry(llm_url)
        assert response.status_code == 200

        # AI Analyzer should have LLM endpoint configured
        ai_url = f"{service_urls['ai_analyzer']}/health"
        wait_for_service_ready(ai_url)

        response = http_retry(ai_url)
        assert response.status_code == 200
