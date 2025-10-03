"""
Unit tests for the storage.analysis_results_store module
"""
import pytest
from datetime import date, datetime
from unittest.mock import patch, Mock, MagicMock, call
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from analyzer.storage.analysis_results_store import (
    AnalysisResultsStore, AnalysisResultsStoreError
)
from analyzer.config.settings import Settings
from analyzer.models.log import DailyAnalysisResult, LogCluster, LogRecord, SeverityLevel


@pytest.fixture
def settings():
    """Create test settings"""
    return Settings.from_dict({
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs',
        'database_url': 'postgresql://postgres:postgres@localhost:5432/test_db',
        'max_logs_per_analysis': 1000,
        'openai_api_key': 'test-key',
        'openai_base_url': 'http://localhost:8000'
    })


@pytest.fixture
def results_store(settings):
    """Create AnalysisResultsStore instance"""
    return AnalysisResultsStore(settings)


@pytest.fixture
def sample_analysis_result():
    """Create sample analysis result for testing"""
    # Create sample log records
    log1 = LogRecord(
        id=1,
        timestamp=int(datetime(2025, 9, 30, 10, 0, 0).timestamp() * 1000),
        message="Error in service",
        source="pod-1",
        metadata={"namespace": "default"},
        embedding=[0.1] * 128,
        level="ERROR",
        duplicate_count=5
    )

    log2 = LogRecord(
        id=2,
        timestamp=int(datetime(2025, 9, 30, 10, 5, 0).timestamp() * 1000),
        message="Warning in cache",
        source="pod-2",
        metadata={"namespace": "default"},
        embedding=[0.2] * 128,
        level="WARNING",
        duplicate_count=3
    )

    # Create sample cluster
    cluster = LogCluster(
        representative_log=log1,
        similar_logs=[log1, log2],
        count=2,
        severity=SeverityLevel.HIGH,
        reasoning="Critical service error detected"
    )

    # Create analysis result
    result = DailyAnalysisResult(
        analysis_date=date(2025, 9, 30),
        total_logs_processed=1000,
        error_count=50,
        warning_count=100,
        analyzed_clusters=[cluster],
        llm_summary="System experienced several critical errors in the main service.",
        execution_time=45.5
    )

    return result


@pytest.fixture
def sample_report():
    """Create sample report dictionary"""
    return {
        "analysis_date": "2025-09-30",
        "generated_at": "2025-09-30T12:00:00",
        "execution_time_seconds": 45.5,
        "summary": {
            "total_logs_processed": 1000,
            "error_count": 50,
            "warning_count": 100,
            "error_rate": 5.0,
            "warning_rate": 10.0,
            "clusters_found": 1,
            "top_issues_identified": 1
        },
        "clusters": []
    }


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_connect_success(mock_session_maker, mock_engine, results_store):
    """Test successful connection to database"""
    mock_engine.return_value = Mock()
    mock_session_maker.return_value = Mock()

    result = results_store.connect()

    assert result is True
    assert results_store.is_connected() is True
    mock_engine.assert_called_once_with(results_store.settings.database_url)


@patch('analyzer.storage.analysis_results_store.get_engine')
def test_connect_failure(mock_engine, results_store):
    """Test connection failure"""
    mock_engine.side_effect = SQLAlchemyError("Connection failed")

    with pytest.raises(AnalysisResultsStoreError, match="Failed to connect to database"):
        results_store.connect()


def test_disconnect(results_store):
    """Test disconnection"""
    mock_engine = Mock()
    results_store.engine = mock_engine
    results_store._connected = True

    results_store.disconnect()

    mock_engine.dispose.assert_called_once()
    assert results_store.engine is None
    assert results_store.is_connected() is False


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_store_analysis_result_success(mock_session_maker, mock_engine,
                                       results_store, sample_analysis_result, sample_report):
    """Test successful storage of analysis result"""
    # Setup mocks
    mock_session = Mock()
    mock_session_maker.return_value.return_value = mock_session

    # Mock the result record
    mock_result = Mock()
    mock_result.id = 123
    mock_session.add.return_value = None

    # Make add set the id
    def add_side_effect(obj):
        obj.id = 123
    mock_session.add.side_effect = add_side_effect

    results_store.connect()
    result_id = results_store.store_analysis_result(
        analysis=sample_analysis_result,
        report=sample_report
    )

    assert result_id == 123
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_store_analysis_result_duplicate(mock_session_maker, mock_engine,
                                         results_store, sample_analysis_result, sample_report):
    """Test storing duplicate analysis result"""
    mock_session = Mock()
    mock_session_maker.return_value.return_value = mock_session
    mock_session.add.side_effect = IntegrityError("duplicate", {}, None)

    results_store.connect()

    with pytest.raises(AnalysisResultsStoreError, match="already exists"):
        results_store.store_analysis_result(
            analysis=sample_analysis_result,
            report=sample_report
        )

    mock_session.rollback.assert_called_once()


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_get_analysis_by_date_found(mock_session_maker, mock_engine, results_store):
    """Test retrieving existing analysis result by date"""
    mock_session = Mock()
    mock_session_maker.return_value.return_value = mock_session

    mock_result = Mock()
    mock_result.id = 1
    mock_result.analysis_date = "2025-09-30"
    mock_result.total_logs_processed = 1000
    mock_result.error_count = 50
    mock_result.report_data = {"test": "data"}

    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = mock_result
    mock_session.query.return_value = mock_query

    results_store.connect()
    result = results_store.get_analysis_by_date("2025-09-30")

    assert result is not None
    assert result['id'] == 1
    assert result['analysis_date'] == "2025-09-30"


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_get_analysis_by_date_not_found(mock_session_maker, mock_engine, results_store):
    """Test retrieving non-existent analysis result"""
    mock_session = Mock()
    mock_session_maker.return_value.return_value = mock_session

    mock_query = Mock()
    mock_query.filter.return_value.first.return_value = None
    mock_session.query.return_value = mock_query

    results_store.connect()
    result = results_store.get_analysis_by_date("2025-09-30")

    assert result is None


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_list_recent_analyses(mock_session_maker, mock_engine, results_store):
    """Test listing recent analyses"""
    mock_session = Mock()
    mock_session_maker.return_value.return_value = mock_session

    mock_result1 = Mock()
    mock_result1.id = 1
    mock_result1.analysis_date = "2025-09-30"
    mock_result1.generated_at = datetime(2025, 9, 30, 12, 0, 0)

    mock_result2 = Mock()
    mock_result2.id = 2
    mock_result2.analysis_date = "2025-09-29"
    mock_result2.generated_at = datetime(2025, 9, 29, 12, 0, 0)

    mock_query = Mock()
    mock_query.order_by.return_value.limit.return_value.all.return_value = [mock_result1, mock_result2]
    mock_session.query.return_value = mock_query

    results_store.connect()
    results = results_store.list_recent_analyses(limit=10)

    assert len(results) == 2
    assert results[0]['id'] == 1
    assert results[1]['id'] == 2


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_delete_old_analyses(mock_session_maker, mock_engine, results_store):
    """Test deleting old analyses"""
    mock_session = Mock()
    mock_session_maker.return_value.return_value = mock_session

    mock_query = Mock()
    mock_query.filter.return_value.delete.return_value = 5
    mock_session.query.return_value = mock_query

    results_store.connect()
    deleted_count = results_store.delete_old_analyses(days_to_keep=30)

    assert deleted_count == 5
    mock_session.commit.assert_called_once()


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_health_check_success(mock_session_maker, mock_engine, results_store):
    """Test successful health check"""
    mock_session = Mock()
    mock_session_maker.return_value.return_value = mock_session

    mock_query = Mock()
    mock_query.limit.return_value.all.return_value = []
    mock_session.query.return_value = mock_query

    results_store.connect()
    health = results_store.health_check()

    assert health is True


@patch('analyzer.storage.analysis_results_store.get_engine')
@patch('analyzer.storage.analysis_results_store.get_session_maker')
def test_health_check_failure(mock_session_maker, mock_engine, results_store):
    """Test failed health check"""
    mock_session_maker.return_value.return_value.query.side_effect = SQLAlchemyError("Connection lost")

    results_store.connect()
    health = results_store.health_check()

    assert health is False
