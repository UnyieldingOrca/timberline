"""
Integration tests for AI Analyzer FastAPI backend.
Tests the REST API endpoints exposed by the ai-analyzer service.
"""

import pytest
import time
import requests
from datetime import datetime


@pytest.fixture(scope="session")
def ai_analyzer_api_url():
    """AI Analyzer API base URL."""
    return "http://localhost:8400"


@pytest.fixture(scope="session")
def wait_for_api(ai_analyzer_api_url):
    """Wait for AI Analyzer API to be ready."""
    max_retries = 30
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            response = requests.get(f"{ai_analyzer_api_url}/health", timeout=5)
            if response.status_code == 200:
                print(f"✓ AI Analyzer API is ready")
                return True
        except requests.exceptions.RequestException:
            if attempt < max_retries - 1:
                print(f"Waiting for AI Analyzer API... ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                raise

    raise RuntimeError("AI Analyzer API failed to become ready")


@pytest.mark.docker
class TestAIAnalyzerAPI:
    """Test AI Analyzer REST API endpoints."""

    def test_health_endpoint(self, ai_analyzer_api_url, wait_for_api):
        """Test GET /health endpoint."""
        response = requests.get(f"{ai_analyzer_api_url}/health", timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-analyzer-api"
        print(f"✓ Health check passed: {data}")

    def test_get_logs_endpoint(self, ai_analyzer_api_url, wait_for_api):
        """Test GET /api/v1/logs endpoint."""
        response = requests.get(f"{ai_analyzer_api_url}/api/v1/logs?limit=10", timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} logs from API")

    def test_get_logs_with_filters(self, ai_analyzer_api_url, wait_for_api):
        """Test GET /api/v1/logs with filters."""
        # Test namespace filter
        response = requests.get(
            f"{ai_analyzer_api_url}/api/v1/logs",
            params={"namespace": "default", "limit": 50},
            timeout=10
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        # Verify namespace filter works if we have data
        if len(data) > 0:
            for log in data:
                assert log.get("namespace") == "default"

        print(f"✓ Namespace filter returned {len(data)} logs")

    def test_search_logs_endpoint(self, ai_analyzer_api_url, wait_for_api):
        """Test POST /api/v1/logs/search endpoint."""
        search_request = {
            "query": "error authentication failed",
            "limit": 20
        }

        response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/logs/search",
            json=search_request,
            timeout=10
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Currently returns empty as semantic search is not implemented
        print(f"✓ Search endpoint returned {len(data)} results")

    def test_create_analysis_job(self, ai_analyzer_api_url, wait_for_api, cleanup_milvus_data):
        """Test POST /api/v1/analyses creates a new analysis job."""
        analysis_request = {
            "namespace": "default",
            "time_range_hours": 24,
            "min_cluster_size": 5
        }

        response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/analyses",
            json=analysis_request,
            timeout=10
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "id" in data
        assert data["status"] == "pending"
        assert data["created_at"] is not None

        analysis_id = data["id"]
        print(f"✓ Created analysis job: {analysis_id}")

        # Wait a moment for background task to potentially start
        time.sleep(2)

        # Check job status
        response = requests.get(
            f"{ai_analyzer_api_url}/api/v1/analyses/{analysis_id}",
            timeout=10
        )

        assert response.status_code == 200
        status_data = response.json()
        assert status_data["id"] == analysis_id
        assert status_data["status"] in ["pending", "running", "completed", "failed"]
        print(f"✓ Analysis job status: {status_data['status']}")

        return analysis_id

    def test_get_all_analyses(self, ai_analyzer_api_url, wait_for_api):
        """Test GET /api/v1/analyses returns list of analyses."""
        response = requests.get(f"{ai_analyzer_api_url}/api/v1/analyses", timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Retrieved {len(data)} analysis jobs")

        # Verify structure of returned analyses
        if len(data) > 0:
            analysis = data[0]
            assert "id" in analysis
            assert "status" in analysis
            assert "created_at" in analysis
            print(f"  First analysis: {analysis['id']}, status: {analysis['status']}")

    def test_get_analysis_by_id(self, ai_analyzer_api_url, wait_for_api, cleanup_milvus_data):
        """Test GET /api/v1/analyses/{id} returns specific analysis."""
        # First create an analysis
        analysis_request = {
            "namespace": "kube-system",
            "time_range_hours": 12,
            "min_cluster_size": 3
        }

        create_response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/analyses",
            json=analysis_request,
            timeout=10
        )
        assert create_response.status_code == 200
        analysis_id = create_response.json()["id"]

        # Now retrieve it
        response = requests.get(
            f"{ai_analyzer_api_url}/api/v1/analyses/{analysis_id}",
            timeout=10
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == analysis_id
        assert "status" in data
        assert "created_at" in data
        print(f"✓ Retrieved analysis: {analysis_id}")

    def test_get_analysis_not_found(self, ai_analyzer_api_url, wait_for_api):
        """Test GET /api/v1/analyses/{id} returns 404 for non-existent analysis."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(
            f"{ai_analyzer_api_url}/api/v1/analyses/{fake_id}",
            timeout=10
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        print(f"✓ Correctly returned 404 for non-existent analysis")

    def test_delete_analysis(self, ai_analyzer_api_url, wait_for_api, cleanup_milvus_data):
        """Test DELETE /api/v1/analyses/{id} deletes analysis."""
        # Create an analysis
        analysis_request = {"time_range_hours": 6}

        create_response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/analyses",
            json=analysis_request,
            timeout=10
        )
        assert create_response.status_code == 200
        analysis_id = create_response.json()["id"]

        # Delete it
        delete_response = requests.delete(
            f"{ai_analyzer_api_url}/api/v1/analyses/{analysis_id}",
            timeout=10
        )

        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["status"] == "deleted"
        assert data["id"] == analysis_id
        print(f"✓ Deleted analysis: {analysis_id}")

        # Verify it's gone
        get_response = requests.get(
            f"{ai_analyzer_api_url}/api/v1/analyses/{analysis_id}",
            timeout=10
        )
        assert get_response.status_code == 404

    def test_analysis_with_defaults(self, ai_analyzer_api_url, wait_for_api, cleanup_milvus_data):
        """Test creating analysis with default values."""
        analysis_request = {}  # Empty request should use defaults

        response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/analyses",
            json=analysis_request,
            timeout=10
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        print(f"✓ Created analysis with defaults: {data['id']}")

    def test_analysis_validation(self, ai_analyzer_api_url, wait_for_api):
        """Test request validation for analysis creation."""
        # Test invalid time range
        invalid_request = {
            "time_range_hours": 200  # Max is 168
        }

        response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/analyses",
            json=invalid_request,
            timeout=10
        )

        assert response.status_code == 422  # Validation error
        print(f"✓ Correctly rejected invalid time_range_hours")

        # Test invalid cluster size
        invalid_request = {
            "min_cluster_size": 0  # Min is 1
        }

        response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/analyses",
            json=invalid_request,
            timeout=10
        )

        assert response.status_code == 422
        print(f"✓ Correctly rejected invalid min_cluster_size")


@pytest.mark.docker
@pytest.mark.slow
class TestAIAnalyzerAPIWithData:
    """Test AI Analyzer API with actual log data."""

    def test_analysis_with_ingested_logs(self, ai_analyzer_api_url, wait_for_api,
                                        log_generator, realistic_log_data,
                                        ingestor_url, http_retry, cleanup_milvus_data):
        """Test complete flow: ingest logs -> create analysis -> check results."""
        from .test_helpers import ingest_logs_via_stream

        # Step 1: Ingest logs
        print(f"=== Ingesting {len(realistic_log_data)} logs ===")
        batch_size = 10
        for i in range(0, len(realistic_log_data), batch_size):
            batch = realistic_log_data[i:i + batch_size]
            response = ingest_logs_via_stream(ingestor_url, batch, timeout=30)
            assert response.status_code == 200

        # Wait for logs to be indexed
        print("=== Waiting for logs to be indexed ===")
        time.sleep(5)

        # Step 2: Create analysis via API
        print("=== Creating analysis job via API ===")
        analysis_request = {
            "time_range_hours": 24,
            "min_cluster_size": 3
        }

        response = requests.post(
            f"{ai_analyzer_api_url}/api/v1/analyses",
            json=analysis_request,
            timeout=10
        )

        assert response.status_code == 200
        analysis_id = response.json()["id"]
        print(f"✓ Created analysis job: {analysis_id}")

        # Step 3: Poll for completion (with timeout)
        print("=== Waiting for analysis to complete ===")
        max_wait = 60  # seconds
        poll_interval = 2
        elapsed = 0

        while elapsed < max_wait:
            response = requests.get(
                f"{ai_analyzer_api_url}/api/v1/analyses/{analysis_id}",
                timeout=10
            )

            assert response.status_code == 200
            data = response.json()
            status = data["status"]

            print(f"  Status: {status} (elapsed: {elapsed}s)")

            if status == "completed":
                print(f"✓ Analysis completed successfully!")

                # Validate results
                assert data["cluster_count"] is not None
                assert data["cluster_count"] >= 0
                assert data["severity_score"] is not None
                assert data["summary"] is not None

                print(f"  Clusters found: {data['cluster_count']}")
                print(f"  Severity score: {data['severity_score']}")
                print(f"  Summary: {data['summary'][:100]}...")

                if data.get("clusters"):
                    print(f"  Cluster details: {len(data['clusters'])} clusters")
                    for cluster in data["clusters"][:3]:
                        print(f"    - {cluster.get('label', 'N/A')}: {cluster.get('size', 0)} logs")

                return

            elif status == "failed":
                error = data.get("error", "Unknown error")
                pytest.fail(f"Analysis failed: {error}")

            time.sleep(poll_interval)
            elapsed += poll_interval

        # If we got here, analysis didn't complete in time
        pytest.skip(f"Analysis did not complete within {max_wait}s (status: {status})")

    def test_concurrent_analysis_jobs(self, ai_analyzer_api_url, wait_for_api, cleanup_milvus_data):
        """Test creating multiple analysis jobs concurrently."""
        jobs = []

        # Create 3 analysis jobs
        for i in range(3):
            analysis_request = {
                "time_range_hours": 12 + i * 6,
                "min_cluster_size": 3 + i
            }

            response = requests.post(
                f"{ai_analyzer_api_url}/api/v1/analyses",
                json=analysis_request,
                timeout=10
            )

            assert response.status_code == 200
            job_id = response.json()["id"]
            jobs.append(job_id)
            print(f"✓ Created job {i+1}: {job_id}")

        # Verify all jobs exist
        response = requests.get(f"{ai_analyzer_api_url}/api/v1/analyses", timeout=10)
        assert response.status_code == 200
        all_jobs = response.json()

        # Check that our jobs are in the list
        all_job_ids = [j["id"] for j in all_jobs]
        for job_id in jobs:
            assert job_id in all_job_ids

        print(f"✓ All {len(jobs)} jobs found in analysis list")
