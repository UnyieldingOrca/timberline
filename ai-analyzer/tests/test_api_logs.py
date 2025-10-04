"""Integration tests for Logs API endpoints"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch


class TestLogsAPI:
    """Test cases for /api/v1/logs endpoints"""

    def test_health_endpoint(self, test_client):
        """Test health check endpoint"""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ai-analyzer-api"

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_get_logs_default_params(self, mock_milvus, test_client):
        """Test GET /api/v1/logs with default parameters"""
        # Mock Milvus client
        mock_client = Mock()
        mock_milvus.return_value = mock_client

        # Mock log data
        mock_log = Mock()
        mock_log.id = 1
        mock_log.timestamp = int(datetime.now().timestamp() * 1000)
        mock_log.message = "Test log message"
        mock_log.level = "INFO"
        mock_log.metadata = {
            "kubernetes": {
                "namespace_name": "default",
                "pod_name": "test-pod",
                "container_name": "test-container",
                "host": "node-1",
                "labels": {"app": "test"}
            }
        }

        mock_client.query_time_range.return_value = [mock_log]

        # Make request
        response = test_client.get("/api/v1/logs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["log"] == "Test log message"
        assert data[0]["namespace"] == "default"
        assert data[0]["pod_name"] == "test-pod"
        assert data[0]["severity"] == "INFO"

        # Verify Milvus was called
        mock_client.connect.assert_called_once()
        mock_client.query_time_range.assert_called_once()
        mock_client.disconnect.assert_called_once()

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_get_logs_with_filters(self, mock_milvus, test_client):
        """Test GET /api/v1/logs with namespace and pod filters"""
        mock_client = Mock()
        mock_milvus.return_value = mock_client

        # Create multiple logs
        mock_log1 = Mock()
        mock_log1.id = 1
        mock_log1.timestamp = int(datetime.now().timestamp() * 1000)
        mock_log1.message = "Log from default namespace"
        mock_log1.level = "INFO"
        mock_log1.metadata = {
            "kubernetes": {
                "namespace_name": "default",
                "pod_name": "test-pod-1",
                "container_name": "test-container",
            }
        }

        mock_log2 = Mock()
        mock_log2.id = 2
        mock_log2.timestamp = int(datetime.now().timestamp() * 1000)
        mock_log2.message = "Log from kube-system namespace"
        mock_log2.level = "WARNING"
        mock_log2.metadata = {
            "kubernetes": {
                "namespace_name": "kube-system",
                "pod_name": "test-pod-2",
                "container_name": "test-container",
            }
        }

        mock_client.query_time_range.return_value = [mock_log1, mock_log2]

        # Filter by namespace
        response = test_client.get("/api/v1/logs?namespace=default")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["namespace"] == "default"

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_get_logs_with_time_range(self, mock_milvus, test_client):
        """Test GET /api/v1/logs with custom time range"""
        mock_client = Mock()
        mock_milvus.return_value = mock_client
        mock_client.query_time_range.return_value = []

        start_time = (datetime.now() - timedelta(hours=48)).isoformat()
        end_time = (datetime.now() - timedelta(hours=24)).isoformat()

        response = test_client.get(
            f"/api/v1/logs?start_time={start_time}&end_time={end_time}"
        )

        assert response.status_code == 200
        assert isinstance(response.json(), list)

        # Verify time range was passed correctly
        mock_client.query_time_range.assert_called_once()
        args = mock_client.query_time_range.call_args[0]
        assert isinstance(args[0], datetime)
        assert isinstance(args[1], datetime)

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_get_logs_limit(self, mock_milvus, test_client):
        """Test GET /api/v1/logs respects limit parameter"""
        mock_client = Mock()
        mock_milvus.return_value = mock_client

        # Create many logs
        logs = []
        for i in range(150):
            mock_log = Mock()
            mock_log.id = i
            mock_log.timestamp = int(datetime.now().timestamp() * 1000)
            mock_log.message = f"Log {i}"
            mock_log.level = "INFO"
            mock_log.metadata = {
                "kubernetes": {
                    "namespace_name": "default",
                    "pod_name": f"pod-{i}",
                    "container_name": "container",
                }
            }
            logs.append(mock_log)

        mock_client.query_time_range.return_value = logs

        # Request with limit
        response = test_client.get("/api/v1/logs?limit=50")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 50

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_get_logs_milvus_error(self, mock_milvus, test_client):
        """Test GET /api/v1/logs handles Milvus errors"""
        mock_client = Mock()
        mock_milvus.return_value = mock_client
        mock_client.connect.side_effect = Exception("Milvus connection failed")

        response = test_client.get("/api/v1/logs")

        assert response.status_code == 500
        assert "Milvus connection failed" in response.json()["detail"]

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_search_logs_not_implemented(self, mock_milvus, test_client):
        """Test POST /api/v1/logs/search returns empty list (not implemented)"""
        mock_client = Mock()
        mock_milvus.return_value = mock_client

        search_request = {
            "query": "error in authentication",
            "limit": 50
        }

        response = test_client.post("/api/v1/logs/search", json=search_request)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Currently returns empty as semantic search is not implemented
        assert len(data) == 0

        # Verify Milvus client was connected and disconnected
        mock_client.connect.assert_called_once()
        mock_client.disconnect.assert_called_once()
