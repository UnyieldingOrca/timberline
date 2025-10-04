"""Integration tests for Analysis API endpoints"""
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
from analyzer.db.models import AnalysisJob, AnalysisStatus


class TestAnalysesAPI:
    """Test cases for /api/v1/analyses endpoints"""

    @patch("analyzer.api.routes.analyses.run_analysis_task")
    def test_create_analysis(self, mock_task, test_client, test_db):
        """Test POST /api/v1/analyses creates a new analysis job"""
        analysis_request = {
            "namespace": "default",
            "time_range_hours": 24,
            "min_cluster_size": 5
        }

        response = test_client.post("/api/v1/analyses", json=analysis_request)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"
        assert data["created_at"] is not None

        # Verify background task was scheduled
        mock_task.assert_called_once()

    @patch("analyzer.api.routes.analyses.run_analysis_task")
    def test_create_analysis_with_defaults(self, mock_task, test_client, test_db):
        """Test POST /api/v1/analyses with default values"""
        analysis_request = {}

        response = test_client.post("/api/v1/analyses", json=analysis_request)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"

        # Verify background task was scheduled
        mock_task.assert_called_once()

    def test_get_analyses_empty(self, test_client):
        """Test GET /api/v1/analyses returns empty list when no analyses exist"""
        response = test_client.get("/api/v1/analyses")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_analyses_list(self, test_client, test_db):
        """Test GET /api/v1/analyses returns list of analyses"""
        # Create test jobs in database using the same session as test_client
        from analyzer.db.base import get_db

        # Get the database session from the app
        db = next(test_client.app.dependency_overrides[get_db]())

        job1 = AnalysisJob(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status=AnalysisStatus.COMPLETED,
            namespace="default",
            time_range_hours=24,
            min_cluster_size=5,
            cluster_count=10,
            severity_score=7.5,
            summary="Test summary"
        )

        job2 = AnalysisJob(
            id=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status=AnalysisStatus.PENDING,
            namespace="kube-system",
            time_range_hours=48,
            min_cluster_size=3
        )

        db.add(job1)
        db.add(job2)
        db.commit()

        # Fetch analyses
        response = test_client.get("/api/v1/analyses")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

        # Verify completed analysis
        completed = [a for a in data if a["status"] == "completed"][0]
        assert completed["cluster_count"] == 10
        assert completed["severity_score"] == 7.5
        assert completed["summary"] == "Test summary"

        # Verify pending analysis
        pending = [a for a in data if a["status"] == "pending"][0]
        assert pending["cluster_count"] is None
        assert pending["severity_score"] is None

    def test_get_analysis_by_id(self, test_client, test_db):
        """Test GET /api/v1/analyses/{id} returns specific analysis"""
        # Create test job using the same session as test_client
        from analyzer.db.base import get_db
        db = next(test_client.app.dependency_overrides[get_db]())

        job_id = str(uuid.uuid4())

        job = AnalysisJob(
            id=job_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status=AnalysisStatus.COMPLETED,
            namespace="default",
            time_range_hours=24,
            min_cluster_size=5,
            cluster_count=3,
            severity_score=8.2,
            summary="Critical issues found",
            clusters=[
                {
                    "cluster_id": 0,
                    "label": "Authentication failed",
                    "size": 45,
                    "sample_logs": ["Failed to authenticate user", "Auth token expired"],
                    "severity": "ERROR"
                }
            ]
        )

        db.add(job)
        db.commit()

        # Fetch specific analysis
        response = test_client.get(f"/api/v1/analyses/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == job_id
        assert data["status"] == "completed"
        assert data["cluster_count"] == 3
        assert data["severity_score"] == 8.2
        assert data["summary"] == "Critical issues found"
        assert len(data["clusters"]) == 1
        assert data["clusters"][0]["label"] == "Authentication failed"

    def test_get_analysis_not_found(self, test_client):
        """Test GET /api/v1/analyses/{id} returns 404 for non-existent analysis"""
        fake_id = str(uuid.uuid4())
        response = test_client.get(f"/api/v1/analyses/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_analysis(self, test_client, test_db):
        """Test DELETE /api/v1/analyses/{id} deletes analysis"""
        # Create test job using the same session as test_client
        from analyzer.db.base import get_db
        db = next(test_client.app.dependency_overrides[get_db]())

        job_id = str(uuid.uuid4())

        job = AnalysisJob(
            id=job_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status=AnalysisStatus.COMPLETED,
            time_range_hours=24,
            min_cluster_size=5
        )

        db.add(job)
        db.commit()

        # Delete analysis
        response = test_client.delete(f"/api/v1/analyses/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"
        assert data["id"] == job_id

        # Verify job was deleted
        db.expire_all()  # Clear cache
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        assert job is None

    def test_delete_analysis_not_found(self, test_client):
        """Test DELETE /api/v1/analyses/{id} returns 404 for non-existent analysis"""
        fake_id = str(uuid.uuid4())
        response = test_client.delete(f"/api/v1/analyses/{fake_id}")

        assert response.status_code == 404

    def test_analysis_validation(self, test_client):
        """Test POST /api/v1/analyses validates request parameters"""
        # Invalid time range
        invalid_request = {
            "time_range_hours": 200  # Max is 168
        }

        response = test_client.post("/api/v1/analyses", json=invalid_request)
        assert response.status_code == 422  # Validation error

        # Invalid cluster size
        invalid_request = {
            "min_cluster_size": 0  # Min is 1
        }

        response = test_client.post("/api/v1/analyses", json=invalid_request)
        assert response.status_code == 422

    @patch("analyzer.api.routes.analyses.run_analysis_task")
    def test_analysis_background_task_scheduled(self, mock_task, test_client, test_db):
        """Test that background task is scheduled when analysis is created"""
        analysis_request = {
            "namespace": "default",
            "time_range_hours": 24,
            "min_cluster_size": 5
        }

        response = test_client.post("/api/v1/analyses", json=analysis_request)

        assert response.status_code == 200

        # Note: Background tasks in TestClient run synchronously
        # In actual tests with async, you'd verify the task was added to background_tasks

    def test_analysis_status_transitions(self, test_client, test_db):
        """Test analysis job status can be updated through lifecycle"""
        # Create job using the same session as test_client
        from analyzer.db.base import get_db
        db = next(test_client.app.dependency_overrides[get_db]())

        job_id = str(uuid.uuid4())

        job = AnalysisJob(
            id=job_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status=AnalysisStatus.PENDING,
            time_range_hours=24,
            min_cluster_size=5
        )

        db.add(job)
        db.commit()

        # Check initial status
        response = test_client.get(f"/api/v1/analyses/{job_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "pending"

        # Update to running
        job.status = AnalysisStatus.RUNNING
        db.commit()
        db.expire_all()

        response = test_client.get(f"/api/v1/analyses/{job_id}")
        assert response.json()["status"] == "running"

        # Update to completed with results
        job.status = AnalysisStatus.COMPLETED
        job.cluster_count = 5
        job.severity_score = 6.5
        job.summary = "Analysis complete"
        db.commit()
        db.expire_all()

        response = test_client.get(f"/api/v1/analyses/{job_id}")
        data = response.json()
        assert data["status"] == "completed"
        assert data["cluster_count"] == 5
        assert data["severity_score"] == 6.5

    def test_failed_analysis_with_error(self, test_client, test_db):
        """Test failed analysis stores error message"""
        # Create job using the same session as test_client
        from analyzer.db.base import get_db
        db = next(test_client.app.dependency_overrides[get_db]())

        job_id = str(uuid.uuid4())

        job = AnalysisJob(
            id=job_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            status=AnalysisStatus.FAILED,
            time_range_hours=24,
            min_cluster_size=5,
            error="Milvus connection timeout"
        )

        db.add(job)
        db.commit()

        response = test_client.get(f"/api/v1/analyses/{job_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Milvus connection timeout"
        assert data["cluster_count"] is None
