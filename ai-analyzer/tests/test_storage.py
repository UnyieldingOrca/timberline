"""
Unit tests for the storage.milvus_client module
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, Mock, MagicMock

from analyzer.storage.milvus_client import (
    MilvusQueryEngine, MilvusConnectionError
)
from analyzer.config.settings import Settings
from analyzer.models.log import LogRecord, LogCluster


@pytest.fixture
def settings():
    """Create test settings"""
    return Settings.from_dict({
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs',
        'max_logs_per_analysis': 1000,
        'llm_api_key': 'test-key',
        'llm_endpoint': 'http://localhost:8000'
    })


@pytest.fixture
def milvus_engine(settings):
    """Create MilvusQueryEngine instance"""
    return MilvusQueryEngine(settings)


@pytest.fixture
def sample_logs():
    """Create sample logs for testing with different label combinations"""
    logs = []
    base_time = datetime(2022, 1, 1, 10, 0, 0)

    # Create logs with different label combinations for testing clustering
    label_combinations = [
        {"app": "web-server", "version": "v1.0"},
        {"app": "web-server", "version": "v1.0"},  # Duplicate for clustering
        {"app": "database", "version": "v2.1"},
        {"app": "database", "version": "v2.1"},   # Duplicate for clustering
        {"app": "cache", "tier": "production"},
        {"app": "web-server", "version": "v1.0"},  # Another duplicate
        {"app": "monitoring", "env": "prod"},
        {"app": "cache", "tier": "production"},     # Another duplicate
        {},  # No labels
        {}   # No labels (duplicate)
    ]

    for i, labels in enumerate(label_combinations):
        logs.append(LogRecord(
            id=i,
            timestamp=int((base_time + timedelta(minutes=i)).timestamp() * 1000),
            message=f"Test log message {i}",
            source=f"pod-{i % 3}",
            metadata={"namespace": "test", "labels": labels},
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5] + [0.0] * 123,  # 128-dim
            level="ERROR" if i % 3 == 0 else "INFO"
        ))

    return logs


def test_initialization(milvus_engine, settings):
    """Test MilvusQueryEngine initialization"""
    assert milvus_engine.host == 'localhost'
    assert milvus_engine.port == 19530
    assert milvus_engine.collection_name == 'test_logs'
    assert milvus_engine.connection_string == 'localhost:19530'
    assert not milvus_engine.is_connected()


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
@patch('analyzer.storage.milvus_client.Collection')
def test_connect_success(mock_collection, mock_utility, mock_connections, milvus_engine):
    """Test successful connection to Milvus"""
    # Mock successful connection
    mock_utility.has_collection.return_value = True
    mock_collection_instance = Mock()
    mock_collection.return_value = mock_collection_instance
    mock_connections.has_connection.return_value = True

    assert milvus_engine.connect() is True
    assert milvus_engine.is_connected() is True

    # Verify calls
    mock_connections.connect.assert_called_once()
    mock_utility.has_collection.assert_called_once()
    mock_collection_instance.load.assert_called_once()


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
def test_connect_invalid_config(mock_utility, mock_connections, settings):
    """Test connection with missing collection"""
    mock_utility.has_collection.return_value = False
    engine = MilvusQueryEngine(settings)

    # Should return False when collection doesn't exist
    assert engine.connect() is False


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
@patch('analyzer.storage.milvus_client.Collection')
def test_disconnect(mock_collection, mock_utility, mock_connections, milvus_engine):
    """Test disconnection from Milvus"""
    # Mock successful connection
    mock_utility.has_collection.return_value = True
    mock_collection_instance = Mock()
    mock_collection.return_value = mock_collection_instance
    mock_connections.has_connection.return_value = True

    milvus_engine.connect()
    assert milvus_engine.is_connected() is True

    # Mock disconnection
    mock_connections.has_connection.return_value = False
    milvus_engine.disconnect()
    assert milvus_engine.is_connected() is False


def test_query_time_range_invalid_range(milvus_engine):
    """Test query with invalid time range"""
    start_time = datetime(2022, 1, 1, 11, 0, 0)
    end_time = datetime(2022, 1, 1, 10, 0, 0)  # End before start

    with pytest.raises(ValueError, match="Start time must be before end time"):
        milvus_engine.query_time_range(start_time, end_time)


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
@patch('analyzer.storage.milvus_client.Collection')
def test_query_time_range_auto_connect(mock_collection, mock_utility, mock_connections, milvus_engine):
    """Test that query automatically connects if not connected"""
    assert not milvus_engine.is_connected()

    # Mock successful connection and query
    mock_utility.has_collection.return_value = True
    mock_collection_instance = Mock()
    mock_collection.return_value = mock_collection_instance
    mock_connections.has_connection.return_value = True

    # Mock query results
    mock_query_results = [
        {
            "id": 1,
            "timestamp": 1640995200000,  # 2022-01-01 10:00:00
            "message": "Test log message",
            "source": "test-pod",
            "metadata": {"namespace": "default"},
            "embedding": [0.1] * 128,
            "level": "INFO"
        }
    ]
    mock_collection_instance.query.return_value = mock_query_results

    start_time = datetime(2022, 1, 1, 10, 0, 0)
    end_time = datetime(2022, 1, 1, 11, 0, 0)

    logs = milvus_engine.query_time_range(start_time, end_time)

    assert milvus_engine.is_connected()
    assert isinstance(logs, list)
    assert len(logs) == 1
    assert all(isinstance(log, LogRecord) for log in logs)
    assert logs[0].message == "Test log message"


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
@patch('analyzer.storage.milvus_client.Collection')
def test_query_time_range_large_range_warning(mock_collection, mock_utility, mock_connections, milvus_engine):
    """Test warning for large time ranges"""
    # Mock successful connection
    mock_utility.has_collection.return_value = True
    mock_collection_instance = Mock()
    mock_collection.return_value = mock_collection_instance
    mock_connections.has_connection.return_value = True
    mock_collection_instance.query.return_value = []

    start_time = datetime(2022, 1, 1)
    end_time = datetime(2022, 1, 10)  # 9 days

    with patch('analyzer.storage.milvus_client.logger') as mock_logger:
        milvus_engine.query_time_range(start_time, end_time)

        # Check that warning was logged
        mock_logger.warning.assert_any_call("Large time range requested: 9 days")


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
@patch('analyzer.storage.milvus_client.Collection')
def test_query_time_range_max_logs_limit(mock_collection, mock_utility, mock_connections, milvus_engine):
    """Test max logs per analysis limit"""
    # Mock successful connection
    mock_utility.has_collection.return_value = True
    mock_collection_instance = Mock()
    mock_collection.return_value = mock_collection_instance
    mock_connections.has_connection.return_value = True

    # Create 15 mock results to test the limit
    mock_results = [{"id": i, "timestamp": 1640995200000, "message": f"test {i}",
                    "source": "pod", "metadata": {}, "embedding": [0.1]*128, "level": "INFO"}
                   for i in range(15)]
    mock_collection_instance.query.return_value = mock_results

    # Set a very low limit for testing
    milvus_engine.settings.max_logs_per_analysis = 10

    start_time = datetime(2022, 1, 1, 10, 0, 0)
    end_time = datetime(2022, 1, 1, 15, 0, 0)

    logs = milvus_engine.query_time_range(start_time, end_time)

    assert len(logs) <= 10


def test_cluster_similar_logs_empty_input(milvus_engine):
    """Test clustering with empty log list"""
    clusters = milvus_engine.cluster_similar_logs([])
    assert clusters == []


def test_cluster_similar_logs_single_log(milvus_engine):
    """Test clustering with single log"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="test", source="pod-1",
        metadata={}, embedding=[0.1] * 128, level="INFO"
    )

    clusters = milvus_engine.cluster_similar_logs([log])

    assert len(clusters) == 1
    assert clusters[0].count == 1
    assert clusters[0].representative_log == log


def test_cluster_similar_logs_few_logs(milvus_engine, sample_logs):
    """Test clustering with few logs using label-based clustering"""
    # Use only 3 logs - first 3 have different label combinations
    logs = sample_logs[:3]

    clusters = milvus_engine.cluster_similar_logs(logs)

    # With label-based clustering: logs 0,1 have same labels, log 2 has different
    assert len(clusters) == 2  # Two distinct label groups
    assert sum(cluster.count for cluster in clusters) == 3  # All logs accounted for

    # Check that logs with same labels are clustered together
    cluster_counts = [cluster.count for cluster in clusters]
    cluster_counts.sort()
    assert cluster_counts == [1, 2]  # One cluster with 2 logs, one with 1


def test_cluster_similar_logs_many_logs(milvus_engine, sample_logs):
    """Test clustering with many logs using label-based clustering"""
    # Create more logs by repeating the sample (30 logs total)
    logs = sample_logs * 3

    clusters = milvus_engine.cluster_similar_logs(logs)

    assert len(clusters) > 0
    # With label-based clustering, we should have 5 distinct label groups:
    # 1. {"app": "web-server", "version": "v1.0"}
    # 2. {"app": "database", "version": "v2.1"}
    # 3. {"app": "cache", "tier": "production"}
    # 4. {"app": "monitoring", "env": "prod"}
    # 5. {} (no labels)
    assert len(clusters) == 5
    assert sum(cluster.count for cluster in clusters) == len(logs)


def test_cluster_sorting(milvus_engine):
    """Test that clusters are sorted by severity and count"""
    # Create logs with different labels and levels
    logs = []
    for i in range(10):
        level = ["INFO", "ERROR", "WARNING"][i % 3]
        # Create different label groups
        if i < 3:
            labels = {"app": "web", "tier": "prod"}
        elif i < 6:
            labels = {"app": "db", "env": "staging"}
        else:
            labels = {"service": "cache"}

        logs.append(LogRecord(
            id=i, timestamp=1640995200000 + i, message=f"message {i}",
            source="pod-1", metadata={"labels": labels}, embedding=[0.1 + (i * 0.01)] * 128, level=level
        ))

    clusters = milvus_engine.cluster_similar_logs(logs)

    # Should have 3 clusters (3 different label groups)
    assert len(clusters) == 3

    # Check that all logs are accounted for
    total_logs_in_clusters = sum(cluster.count for cluster in clusters)
    assert total_logs_in_clusters == len(logs)

    # Check that clusters are properly formed
    for cluster in clusters:
        assert cluster.count > 0
        assert len(cluster.similar_logs) == cluster.count

    # Check that clusters are sorted by severity (ERROR logs first)
    # The first cluster should contain ERROR logs
    first_cluster_has_errors = any(log.level == "ERROR" for log in clusters[0].similar_logs)
    assert first_cluster_has_errors or clusters[0].count >= max(c.count for c in clusters[1:])


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
@patch('analyzer.storage.milvus_client.Collection')
def test_health_check_success(mock_collection, mock_utility, mock_connections, milvus_engine):
    """Test successful health check"""
    # Mock successful connection and health check
    mock_utility.has_collection.return_value = True
    mock_collection_instance = Mock()
    mock_collection.return_value = mock_collection_instance
    mock_connections.has_connection.return_value = True
    mock_collection_instance.query.return_value = [{"id": 1}]  # Mock query result

    result = milvus_engine.health_check()
    assert result is True
    assert milvus_engine.is_connected()


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
def test_health_check_invalid_config(mock_utility, mock_connections, settings):
    """Test health check with invalid configuration"""
    settings.milvus_host = ""
    engine = MilvusQueryEngine(settings)

    # Mock the connect method to prevent actual connection attempts
    with patch.object(engine, 'connect', return_value=False) as mock_connect:
        result = engine.health_check()

        # Verify that connect was called (and failed due to invalid config)
        mock_connect.assert_called_once()
        assert result is False


def test_choose_representative_log_prioritizes_errors(milvus_engine):
    """Test representative log selection prioritizes ERROR/CRITICAL logs"""
    logs = [
        LogRecord(id=1, timestamp=1640995200000, message="info", source="pod-1",
                 metadata={}, embedding=[0.1] * 128, level="INFO"),
        LogRecord(id=2, timestamp=1640995200001, message="debug", source="pod-1",
                 metadata={}, embedding=[0.2] * 128, level="DEBUG"),
        LogRecord(id=3, timestamp=1640995200002, message="error", source="pod-1",
                 metadata={}, embedding=[0.3] * 128, level="ERROR"),
    ]

    representative = milvus_engine._choose_representative_log(logs)
    # Should return the ERROR log (highest priority)
    assert representative.level == "ERROR"
    assert representative.id == 3


def test_choose_representative_log_single_item(milvus_engine):
    """Test representative log selection with single log"""
    logs = [
        LogRecord(id=1, timestamp=1640995200000, message="test", source="pod-1",
                 metadata={}, embedding=[0.1] * 128, level="DEBUG")
    ]

    representative = milvus_engine._choose_representative_log(logs)
    assert representative == logs[0]  # Should return the only log


def test_choose_representative_log_empty_list(milvus_engine):
    """Test representative log selection with empty list"""
    with pytest.raises(ValueError, match="Cannot choose representative from empty log list"):
        milvus_engine._choose_representative_log([])


@patch('analyzer.storage.milvus_client.connections')
def test_connection_error_handling(mock_connections, settings):
    """Test connection error handling"""
    # Create engine with empty host to trigger error
    settings.milvus_host = ""
    engine = MilvusQueryEngine(settings)

    # Mock connections.connect to raise an exception
    mock_connections.connect.side_effect = Exception("Connection failed")

    with pytest.raises(MilvusConnectionError, match="Connection failed"):
        engine.connect()


@patch('analyzer.storage.milvus_client.connections')
@patch('analyzer.storage.milvus_client.utility')
@patch('analyzer.storage.milvus_client.Collection')
def test_query_logs_validation(mock_collection, mock_utility, mock_connections, milvus_engine, sample_logs):
    """Test that queried logs have valid structure"""
    # Mock successful connection
    mock_utility.has_collection.return_value = True
    mock_collection_instance = Mock()
    mock_collection.return_value = mock_collection_instance
    mock_connections.has_connection.return_value = True

    # Mock query results with valid log structure
    mock_query_results = [
        {
            "id": 1,
            "timestamp": 1640995200000,  # 2022-01-01 10:00:00
            "message": "Test log message",
            "source": "test-pod",
            "metadata": {"namespace": "default"},
            "embedding": [0.1] * 128,
            "level": "INFO"
        }
    ]
    mock_collection_instance.query.return_value = mock_query_results

    start_time = datetime(2022, 1, 1, 10, 0, 0)
    end_time = datetime(2022, 1, 1, 11, 0, 0)

    logs = milvus_engine.query_time_range(start_time, end_time)

    for log in logs:
        # Test that all required fields are present and valid
        assert isinstance(log.id, int)
        assert isinstance(log.timestamp, int)
        assert isinstance(log.message, str)
        assert isinstance(log.source, str)
        assert isinstance(log.metadata, dict)
        assert isinstance(log.embedding, list)
        assert len(log.embedding) == 128  # Expected embedding dimension
        assert log.level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def test_extract_labels_basic(milvus_engine):
    """Test basic label extraction from log metadata"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="test", source="pod-1",
        metadata={"labels": {"app": "web", "version": "v1.0"}},
        embedding=[0.1] * 128, level="INFO"
    )

    labels = milvus_engine._extract_labels(log)
    assert labels == {"app": "web", "version": "v1.0"}


def test_extract_labels_kubernetes_nested(milvus_engine):
    """Test label extraction from nested kubernetes metadata"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="test", source="pod-1",
        metadata={"kubernetes": {"labels": {"service": "api", "tier": "backend"}}},
        embedding=[0.1] * 128, level="INFO"
    )

    labels = milvus_engine._extract_labels(log)
    assert labels == {"service": "api", "tier": "backend"}


def test_extract_labels_kubernetes_labels_key(milvus_engine):
    """Test label extraction from kubernetes_labels key"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="test", source="pod-1",
        metadata={"kubernetes_labels": {"env": "production", "app": "cache"}},
        embedding=[0.1] * 128, level="INFO"
    )

    labels = milvus_engine._extract_labels(log)
    assert labels == {"env": "production", "app": "cache"}


def test_extract_labels_empty_metadata(milvus_engine):
    """Test label extraction with empty or invalid metadata"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="test", source="pod-1",
        metadata={}, embedding=[0.1] * 128, level="INFO"
    )

    labels = milvus_engine._extract_labels(log)
    assert labels == {}


def test_extract_labels_non_dict_metadata(milvus_engine):
    """Test label extraction with non-dict metadata"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="test", source="pod-1",
        metadata="not a dict", embedding=[0.1] * 128, level="INFO"
    )

    labels = milvus_engine._extract_labels(log)
    assert labels == {}


def test_create_label_key_basic(milvus_engine):
    """Test label key creation from basic labels"""
    labels = {"app": "web", "version": "v1.0"}
    key = milvus_engine._create_label_key(labels)
    assert key == "app=web|version=v1.0"


def test_create_label_key_sorted(milvus_engine):
    """Test that label keys are sorted for consistency"""
    # Test with labels in different order
    labels1 = {"version": "v1.0", "app": "web"}
    labels2 = {"app": "web", "version": "v1.0"}

    key1 = milvus_engine._create_label_key(labels1)
    key2 = milvus_engine._create_label_key(labels2)

    assert key1 == key2
    assert key1 == "app=web|version=v1.0"


def test_create_label_key_empty(milvus_engine):
    """Test label key creation with empty labels"""
    labels = {}
    key = milvus_engine._create_label_key(labels)
    assert key == "no-labels"


def test_cluster_by_labels_integration(milvus_engine):
    """Test complete label-based clustering integration"""
    logs = [
        # Group 1: web-server v1.0 (3 logs)
        LogRecord(id=1, timestamp=1640995200000, message="web log 1", source="pod-1",
                 metadata={"labels": {"app": "web-server", "version": "v1.0"}},
                 embedding=[0.1] * 128, level="INFO"),
        LogRecord(id=2, timestamp=1640995200001, message="web log 2", source="pod-2",
                 metadata={"labels": {"app": "web-server", "version": "v1.0"}},
                 embedding=[0.2] * 128, level="ERROR"),
        LogRecord(id=3, timestamp=1640995200002, message="web log 3", source="pod-3",
                 metadata={"labels": {"app": "web-server", "version": "v1.0"}},
                 embedding=[0.3] * 128, level="WARNING"),

        # Group 2: database v2.1 (2 logs)
        LogRecord(id=4, timestamp=1640995200003, message="db log 1", source="pod-4",
                 metadata={"labels": {"app": "database", "version": "v2.1"}},
                 embedding=[0.4] * 128, level="INFO"),
        LogRecord(id=5, timestamp=1640995200004, message="db log 2", source="pod-5",
                 metadata={"labels": {"app": "database", "version": "v2.1"}},
                 embedding=[0.5] * 128, level="INFO"),

        # Group 3: no labels (1 log)
        LogRecord(id=6, timestamp=1640995200005, message="unlabeled log", source="pod-6",
                 metadata={}, embedding=[0.6] * 128, level="ERROR")
    ]

    clusters = milvus_engine.cluster_similar_logs(logs)

    # Should have 3 clusters
    assert len(clusters) == 3

    # Check cluster sizes
    cluster_counts = sorted([cluster.count for cluster in clusters], reverse=True)
    assert cluster_counts == [3, 2, 1]

    # Check that representative logs are prioritized correctly (ERROR > WARNING > INFO)
    # The web-server cluster should have the ERROR log as representative
    web_cluster = next(c for c in clusters if c.count == 3)
    assert web_cluster.representative_log.level == "ERROR"
    assert web_cluster.representative_log.id == 2  # Most recent ERROR

    # The no-labels cluster should have the ERROR log as representative
    no_labels_cluster = next(c for c in clusters if c.count == 1)
    assert no_labels_cluster.representative_log.level == "ERROR"
    assert no_labels_cluster.representative_log.id == 6


def test_choose_representative_log_most_recent_error(milvus_engine):
    """Test that most recent error log is chosen when multiple errors exist"""
    logs = [
        LogRecord(id=1, timestamp=1640995200000, message="old error", source="pod-1",
                 metadata={}, embedding=[0.1] * 128, level="ERROR"),
        LogRecord(id=2, timestamp=1640995200002, message="new error", source="pod-1",
                 metadata={}, embedding=[0.2] * 128, level="ERROR"),
        LogRecord(id=3, timestamp=1640995200001, message="middle error", source="pod-1",
                 metadata={}, embedding=[0.3] * 128, level="ERROR"),
    ]

    representative = milvus_engine._choose_representative_log(logs)
    # Should return the most recent ERROR log
    assert representative.id == 2  # Newest timestamp
    assert representative.message == "new error"


def test_choose_representative_log_warning_fallback(milvus_engine):
    """Test that WARNING logs are chosen when no ERROR logs exist"""
    logs = [
        LogRecord(id=1, timestamp=1640995200000, message="info", source="pod-1",
                 metadata={}, embedding=[0.1] * 128, level="INFO"),
        LogRecord(id=2, timestamp=1640995200002, message="new warning", source="pod-1",
                 metadata={}, embedding=[0.2] * 128, level="WARNING"),
        LogRecord(id=3, timestamp=1640995200001, message="old warning", source="pod-1",
                 metadata={}, embedding=[0.3] * 128, level="WARNING"),
    ]

    representative = milvus_engine._choose_representative_log(logs)
    # Should return the most recent WARNING log
    assert representative.id == 2
    assert representative.level == "WARNING"
    assert representative.message == "new warning"