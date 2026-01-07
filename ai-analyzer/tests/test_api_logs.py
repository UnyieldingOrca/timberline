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

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_get_logs_with_correct_fluentbit_metadata_structure(self, mock_milvus, test_client):
        """
        Test that logs API correctly handles Fluent Bit metadata structure.

        CRITICAL: This test uses the ACTUAL metadata structure from Fluent Bit,
        where kubernetes fields are stored directly in metadata (NOT nested under 'kubernetes' key).

        This test would have caught the bug where code expected:
          log.metadata.get('kubernetes', {}).get('namespace_name')
        But actual structure is:
          log.metadata.get('namespace_name')
        """
        mock_client = Mock()
        mock_milvus.return_value = mock_client

        # CORRECT metadata structure from Fluent Bit → Log Ingestor → Milvus
        mock_log = Mock()
        mock_log.id = 123
        mock_log.timestamp = int(datetime.now().timestamp() * 1000)
        mock_log.message = "Test application started"
        mock_log.level = "INFO"
        mock_log.metadata = {
            "namespace_name": "timberline",
            "pod_name": "web-app-5f7d9c8b-x9z2l",
            "container_name": "web",
            "host": "node-1",
            "labels": {
                "app": "web-app",
                "version": "v1.2.3"
            }
        }

        mock_client.query_time_range.return_value = [mock_log]

        # Make request
        response = test_client.get("/api/v1/logs")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

        # Verify Kubernetes metadata is correctly extracted
        assert data[0]["namespace"] == "timberline", "namespace should be 'timberline', not 'unknown'"
        assert data[0]["pod_name"] == "web-app-5f7d9c8b-x9z2l", "pod_name should match metadata"
        assert data[0]["container_name"] == "web", "container_name should be 'web', not 'unknown'"
        assert data[0]["node_name"] == "node-1", "node_name should be extracted from host field"
        assert data[0]["labels"]["app"] == "web-app", "labels should be preserved"
        assert data[0]["log"] == "Test application started"
        assert data[0]["severity"] == "INFO"

    @patch("analyzer.api.routes.logs.MilvusQueryEngine")
    def test_get_logs_namespace_filter_with_correct_metadata(self, mock_milvus, test_client):
        """
        Test that namespace filtering works with the correct Fluent Bit metadata structure.

        This test ensures namespace filtering accesses metadata.get('namespace_name') directly,
        not via metadata.get('kubernetes', {}).get('namespace_name').
        """
        mock_client = Mock()
        mock_milvus.return_value = mock_client

        # Create logs from different namespaces with CORRECT metadata structure
        log1 = Mock()
        log1.id = 1
        log1.timestamp = int(datetime.now().timestamp() * 1000)
        log1.message = "Production log"
        log1.level = "INFO"
        log1.metadata = {
            "namespace_name": "production",
            "pod_name": "api-server-abc",
            "container_name": "api"
        }

        log2 = Mock()
        log2.id = 2
        log2.timestamp = int(datetime.now().timestamp() * 1000)
        log2.message = "Staging log"
        log2.level = "INFO"
        log2.metadata = {
            "namespace_name": "staging",
            "pod_name": "api-server-xyz",
            "container_name": "api"
        }

        log3 = Mock()
        log3.id = 3
        log3.timestamp = int(datetime.now().timestamp() * 1000)
        log3.message = "Another production log"
        log3.level = "WARNING"
        log3.metadata = {
            "namespace_name": "production",
            "pod_name": "worker-def",
            "container_name": "worker"
        }

        mock_client.query_time_range.return_value = [log1, log2, log3]

        # Filter by production namespace
        response = test_client.get("/api/v1/logs?namespace=production")

        assert response.status_code == 200
        data = response.json()

        # Should only return logs from production namespace
        assert len(data) == 2, "Should return exactly 2 logs from production namespace"
        assert all(log["namespace"] == "production" for log in data), "All logs should be from production"
        assert data[0]["pod_name"] in ["api-server-abc", "worker-def"]
        assert data[1]["pod_name"] in ["api-server-abc", "worker-def"]

        # Verify staging log was filtered out
        assert not any(log["pod_name"] == "api-server-xyz" for log in data)
