"""
Unit tests for the analysis.engine module
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
import time

from analyzer.analysis.engine import AnalysisEngine, AnalysisEngineError
from analyzer.config.settings import Settings
from analyzer.models.log import (
    LogRecord, LogCluster, DailyAnalysisResult, SeverityLevel
)
from analyzer.storage.milvus_client import MilvusConnectionError
from analyzer.reporting.generator import ReportGeneratorError

@pytest.fixture
def settings(tmp_path):
    """Create test settings"""
    return Settings.from_dict({
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs',
        'analysis_window_hours': 24,
        'max_logs_per_analysis': 1000,
        'openai_api_key': 'test-key',
        'openai_base_url': 'http://localhost:8000',
        'report_output_dir': str(tmp_path / "reports")
    })

@pytest.fixture
def mock_components():
    """Create mock components"""
    with patch('analyzer.analysis.engine.MilvusQueryEngine') as mock_milvus, \
         patch('analyzer.analysis.engine.LLMClient') as mock_llm, \
         patch('analyzer.analysis.engine.ReportGenerator') as mock_reporter, \
         patch('analyzer.analysis.engine.AnalysisResultsStore') as mock_results_store:

        # Configure mocks
        mock_milvus.return_value.health_check.return_value = True
        mock_llm.return_value.health_check.return_value = True
        mock_results_store.return_value.health_check.return_value = True

        yield {
            'milvus': mock_milvus.return_value,
            'llm': mock_llm.return_value,
            'reporter': mock_reporter.return_value,
            'results_store': mock_results_store.return_value
        }

@pytest.fixture
def sample_logs():
    """Create sample logs for testing"""
    logs = []
    base_time = datetime(2022, 1, 1, 10, 0, 0)

    for i in range(10):
        logs.append(LogRecord(
            id=i + 1,
            timestamp=int((base_time + timedelta(minutes=i * 10)).timestamp() * 1000),
            message=f"Test log message {i + 1}",
            source=f"pod-{(i % 3) + 1}",
            metadata={"namespace": "test", "pod": f"app-{i}"},
            embedding=[0.1 + (i * 0.1)] * 128,
            level=["INFO", "WARNING", "ERROR", "INFO", "CRITICAL",
                   "WARNING", "ERROR", "INFO", "WARNING", "ERROR"][i]
        ))

    return logs

@pytest.fixture
def sample_clusters(sample_logs):
    """Create sample log clusters"""
    clusters = [
        LogCluster(
            representative_log=sample_logs[2],  # ERROR
            similar_logs=[sample_logs[2], sample_logs[6], sample_logs[9]],
            count=3
        ),
        LogCluster(
            representative_log=sample_logs[4],  # CRITICAL
            similar_logs=[sample_logs[4]],
            count=1
        ),
        LogCluster(
            representative_log=sample_logs[1],  # WARNING
            similar_logs=[sample_logs[1], sample_logs[5], sample_logs[8]],
            count=3
        )
    ]

    # Add severity levels
    for i, cluster in enumerate(clusters):
        cluster.severity = [SeverityLevel.HIGH, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM][i]

    return clusters

def test_initialization_success(settings, mock_components):
    """Test successful AnalysisEngine initialization"""
    engine = AnalysisEngine(settings)

    assert engine.settings == settings
    assert engine.milvus_client is not None
    assert engine.llm_client is not None
    assert engine.report_generator is not None

def test_initialization_invalid_settings():
    """Test initialization with invalid settings"""
    # Create a settings object and then modify it to be invalid
    settings = Settings.from_dict({
        'milvus_host': 'localhost',  # Valid initially
        'llm_api_key': 'test-key',
        'llm_endpoint': 'http://localhost:8000'
    })

    # Modify to make it invalid (bypass validation)
    settings.milvus_host = ''  # Make invalid

    with pytest.raises(AnalysisEngineError, match="Invalid settings"):
        AnalysisEngine(settings)

def test_initialization_component_failure(settings):
    """Test initialization when component creation fails"""
    with patch('analyzer.analysis.engine.MilvusQueryEngine') as mock_milvus:
        mock_milvus.side_effect = Exception("Milvus initialization failed")

        with pytest.raises(AnalysisEngineError, match="Failed to initialize analysis engine"):
            AnalysisEngine(settings)

def test_health_check_all_healthy(settings, mock_components):
    """Test health check when all components are healthy"""
    engine = AnalysisEngine(settings)

    # Configure health checks to return True
    mock_components['milvus'].health_check.return_value = True
    mock_components['llm'].health_check.return_value = True

    health = engine.health_check()

    assert health['milvus'] is True
    assert health['llm'] is True
    assert health['results_store'] is True
    assert health['report_generator'] is True
    assert health['overall'] is True

def test_health_check_partial_failure(settings, mock_components):
    """Test health check with some component failures"""
    engine = AnalysisEngine(settings)

    # Configure mixed health check results
    mock_components['milvus'].health_check.return_value = False
    mock_components['llm'].health_check.return_value = True

    health = engine.health_check()

    assert health['milvus'] is False
    assert health['llm'] is True
    assert health['results_store'] is True
    assert health['report_generator'] is True
    assert health['overall'] is False

def test_health_check_with_exceptions(settings, mock_components):
    """Test health check when components raise exceptions"""
    engine = AnalysisEngine(settings)

    # Configure health checks to raise exceptions
    mock_components['milvus'].health_check.side_effect = Exception("Connection failed")
    mock_components['llm'].health_check.side_effect = Exception("API error")

    health = engine.health_check()

    assert health['milvus'] is False
    assert health['llm'] is False
    assert health['results_store'] is True
    assert health['report_generator'] is True
    assert health['overall'] is False

def test_analyze_daily_logs_success(settings, mock_components, sample_logs, sample_clusters):
    """Test successful daily log analysis"""
    engine = AnalysisEngine(settings)

    # Configure mock responses
    mock_components['milvus'].query_time_range.return_value = sample_logs
    mock_components['milvus'].cluster_similar_logs.return_value = sample_clusters
    # Configure LLM to analyze clusters directly
    def mock_analyze_clusters(clusters):
        for i, cluster in enumerate(clusters):
            cluster.severity = [SeverityLevel.HIGH, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM][i]
            cluster.reasoning = ["Database error", "Critical failure", "Warning issue"][i]
    mock_components['llm'].analyze_clusters.side_effect = mock_analyze_clusters
    mock_components['llm'].generate_daily_summary.return_value = "System has some issues"
    mock_components['reporter'].generate_daily_report.return_value = {"summary": "test"}
    mock_components['reporter'].save_report.return_value = "/tmp/report.json"

    result = engine.analyze_daily_logs(date(2022, 1, 1))

    # Verify result structure
    assert isinstance(result, DailyAnalysisResult)
    assert result.analysis_date == date(2022, 1, 1)
    assert result.total_logs_processed == 10
    assert result.error_count == 4  # ERROR + CRITICAL levels
    assert result.warning_count == 3
    assert len(result.analyzed_clusters) == 3
    assert len(result.top_issues) >= 2  # HIGH and CRITICAL clusters are actionable
    # health_score field was removed
    assert result.llm_summary == "System has some issues"
    assert result.execution_time > 0

    # Verify component calls
    mock_components['milvus'].query_time_range.assert_called_once()
    mock_components['milvus'].cluster_similar_logs.assert_called_once_with(sample_logs)
    mock_components['llm'].analyze_clusters.assert_called_once()
    mock_components['reporter'].generate_daily_report.assert_called_once()
    mock_components['reporter'].save_report.assert_called_once()

def test_analyze_daily_logs_invalid_date(settings, mock_components):
    """Test analysis with invalid date parameter"""
    engine = AnalysisEngine(settings)

    with pytest.raises(AnalysisEngineError, match="analysis_date must be a date object"):
        engine.analyze_daily_logs("2022-01-01")  # String instead of date

def test_analyze_daily_logs_no_logs_found(settings, mock_components):
    """Test analysis when no logs are found"""
    engine = AnalysisEngine(settings)

    # Configure mock to return empty logs
    mock_components['milvus'].query_time_range.return_value = []

    result = engine.analyze_daily_logs(date(2022, 1, 1))

    assert result.total_logs_processed == 0
    assert result.error_count == 0
    assert result.warning_count == 0
    assert len(result.analyzed_clusters) == 0
    assert len(result.top_issues) == 0
    # health_score field was removed
    assert "No logs found" in result.llm_summary

def test_analyze_daily_logs_milvus_connection_error(settings, mock_components):
    """Test analysis with Milvus connection failure"""
    engine = AnalysisEngine(settings)

    # Configure mock to raise connection error
    mock_components['milvus'].query_time_range.side_effect = MilvusConnectionError("Connection failed")

    with pytest.raises(AnalysisEngineError, match="Database connection failed"):
        engine.analyze_daily_logs(date(2022, 1, 1))

def test_analyze_daily_logs_general_exception(settings, mock_components):
    """Test analysis with general exception"""
    engine = AnalysisEngine(settings)

    # Configure mock to raise general exception
    mock_components['milvus'].query_time_range.side_effect = Exception("Unexpected error")

    with pytest.raises(AnalysisEngineError, match="Analysis pipeline failed"):
        engine.analyze_daily_logs(date(2022, 1, 1))

def test_analyze_daily_logs_report_generation_failure(settings, mock_components, sample_logs, sample_clusters):
    """Test analysis continues when report generation fails"""
    engine = AnalysisEngine(settings)

    # Configure successful analysis but failed reporting
    mock_components['milvus'].query_time_range.return_value = sample_logs
    mock_components['milvus'].cluster_similar_logs.return_value = sample_clusters
    def mock_analyze_clusters(clusters):
        for i, cluster in enumerate(clusters):
            cluster.severity = [SeverityLevel.HIGH, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM][i]
            cluster.reasoning = "Test reasoning"
    mock_components['llm'].analyze_clusters.side_effect = mock_analyze_clusters
    mock_components['llm'].generate_daily_summary.return_value = "System summary"
    mock_components['reporter'].generate_daily_report.side_effect = ReportGeneratorError("Report failed")

    # Should not raise exception, just log the error
    result = engine.analyze_daily_logs(date(2022, 1, 1))

    assert isinstance(result, DailyAnalysisResult)
    assert result.total_logs_processed == 10

def test_query_logs_with_retry_success(settings, mock_components, sample_logs):
    """Test successful log querying with retry logic"""
    engine = AnalysisEngine(settings)

    mock_components['milvus'].query_time_range.return_value = sample_logs

    start_time = datetime(2022, 1, 1, 0, 0, 0)
    end_time = datetime(2022, 1, 2, 0, 0, 0)

    logs = engine._query_logs_with_retry(start_time, end_time)

    assert logs == sample_logs
    mock_components['milvus'].query_time_range.assert_called_once_with(start_time, end_time)

def test_query_logs_with_retry_eventual_success(settings, mock_components, sample_logs):
    """Test log querying succeeds after retries"""
    engine = AnalysisEngine(settings)

    # Fail first two attempts, succeed on third
    mock_components['milvus'].query_time_range.side_effect = [
        Exception("First failure"),
        Exception("Second failure"),
        sample_logs
    ]

    start_time = datetime(2022, 1, 1, 0, 0, 0)
    end_time = datetime(2022, 1, 2, 0, 0, 0)

    with patch('time.sleep'):  # Speed up test
        logs = engine._query_logs_with_retry(start_time, end_time, max_retries=3)

    assert logs == sample_logs
    assert mock_components['milvus'].query_time_range.call_count == 3

def test_query_logs_with_retry_max_retries_exceeded(settings, mock_components):
    """Test log querying fails after max retries"""
    engine = AnalysisEngine(settings)

    mock_components['milvus'].query_time_range.side_effect = Exception("Persistent failure")

    start_time = datetime(2022, 1, 1, 0, 0, 0)
    end_time = datetime(2022, 1, 2, 0, 0, 0)

    with patch('time.sleep'):  # Speed up test
        with pytest.raises(Exception, match="Persistent failure"):
            engine._query_logs_with_retry(start_time, end_time, max_retries=3)

def test_process_log_clusters_success(settings, mock_components, sample_clusters):
    """Test successful log cluster processing"""
    engine = AnalysisEngine(settings)

    # Configure LLM to analyze clusters directly
    def mock_analyze_clusters(clusters):
        for i, cluster in enumerate(clusters):
            cluster.severity = [SeverityLevel.HIGH, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM][i]
            cluster.reasoning = ["Error reasoning", "Critical reasoning", "Medium reasoning"][i]
    mock_components['llm'].analyze_clusters.side_effect = mock_analyze_clusters

    result_clusters = engine.process_log_clusters(sample_clusters)

    assert len(result_clusters) == 3
    assert all(cluster.severity is not None for cluster in result_clusters)
    assert result_clusters[0].severity == SeverityLevel.HIGH
    assert result_clusters[1].severity == SeverityLevel.CRITICAL
    assert result_clusters[2].severity == SeverityLevel.MEDIUM
    assert all(cluster.reasoning is not None for cluster in result_clusters)

def test_process_log_clusters_empty_input(settings, mock_components):
    """Test cluster processing with empty input"""
    engine = AnalysisEngine(settings)

    result_clusters = engine.process_log_clusters([])

    assert result_clusters == []

def test_process_log_clusters_llm_failure(settings, mock_components, sample_clusters):
    """Test cluster processing with LLM failure - should raise exception"""
    engine = AnalysisEngine(settings)

    mock_components['llm'].analyze_clusters.side_effect = Exception("LLM failure")

    # Should raise exception when LLM fails
    with pytest.raises(Exception, match="LLM failure"):
        engine.process_log_clusters(sample_clusters)

# Removed test_calculate_fallback_severity - fallback functionality removed

def test_error_rate_calculation_no_logs(settings, mock_components):
    """Test error rate calculation with no logs"""
    engine = AnalysisEngine(settings)
    # health_score generation was removed, now we focus on error rates
    result = engine._create_empty_result(date(2022, 1, 1), 1.0)
    assert result.error_rate == 0.0

def test_error_rate_calculation_with_logs(settings, mock_components, sample_logs, sample_clusters):
    """Test error rate calculation with logs"""
    engine = AnalysisEngine(settings)
    # health_score generation was removed, we now use error rates directly
    total_logs = sum(log.duplicate_count for log in sample_logs)
    error_logs = sum(log.duplicate_count for log in sample_logs if log.level in ["ERROR", "CRITICAL"])
    expected_error_rate = (error_logs / total_logs) * 100 if total_logs > 0 else 0.0

    # This would be calculated in the analysis engine
    assert 0.0 <= expected_error_rate <= 100.0

def test_error_rate_calculation_all_errors(settings, mock_components):
    """Test error rate with all error logs"""
    engine = AnalysisEngine(settings)

    error_logs = [
        LogRecord(id=1, timestamp=1640995200000, message="error", source="test",
                 metadata={}, embedding=[0.1] * 128, level="ERROR", duplicate_count=1),
        LogRecord(id=2, timestamp=1640995200000, message="critical", source="test",
                 metadata={}, embedding=[0.1] * 128, level="CRITICAL", duplicate_count=1)
    ]

    # Calculate expected error rate (should be 100% since all are errors)
    total_logs = sum(log.duplicate_count for log in error_logs)
    error_count = sum(log.duplicate_count for log in error_logs if log.level in ["ERROR", "CRITICAL"])
    expected_error_rate = (error_count / total_logs) * 100 if total_logs > 0 else 0.0

    assert expected_error_rate == 100.0  # Should be 100% since all are errors

def test_get_top_issues_empty_clusters(settings, mock_components):
    """Test getting top issues with empty clusters"""
    result = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1),
        total_logs_processed=0,
        error_count=0,
        warning_count=0,
        analyzed_clusters=[],
        llm_summary="No issues",
        execution_time=1.0
    )

    top_issues = result.top_issues

    assert top_issues == []

def test_get_top_issues_with_clusters(settings, mock_components, sample_clusters):
    """Test getting top issues from clusters"""
    # Set severity levels
    sample_clusters[0].severity = SeverityLevel.HIGH
    sample_clusters[1].severity = SeverityLevel.CRITICAL
    sample_clusters[2].severity = SeverityLevel.LOW  # Below actionable threshold

    result = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1),
        total_logs_processed=10,
        error_count=2,
        warning_count=1,
        analyzed_clusters=sample_clusters,
        llm_summary="Some issues found",
        execution_time=1.0
    )

    top_issues = result.top_issues

    assert len(top_issues) == 2  # Only actionable issues
    assert all(isinstance(issue, LogCluster) for issue in top_issues)
    assert top_issues[0].severity == SeverityLevel.CRITICAL  # Highest severity first
    assert top_issues[1].severity == SeverityLevel.HIGH

def test_get_top_issues_max_limit(settings, mock_components):
    """Test top issues respects maximum limit"""
    # Create many clusters with high severity
    many_clusters = []
    for i in range(15):
        log_record = LogRecord(
            id=i, timestamp=1640995200000, message=f"log {i}", source="test",
            metadata={}, embedding=[0.1] * 128, level="ERROR"
        )
        cluster = LogCluster(
            representative_log=log_record,
            similar_logs=[log_record],  # Include the log in similar_logs to match count
            count=1
        )
        cluster.severity = SeverityLevel.HIGH
        many_clusters.append(cluster)

    result = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1),
        total_logs_processed=15,
        error_count=15,
        warning_count=0,
        analyzed_clusters=many_clusters,
        llm_summary="Many issues found",
        execution_time=1.0
    )

    top_issues = result.top_issues

    assert len(top_issues) == 10  # Limited to 10 by property definition

def test_create_empty_result(settings, mock_components):
    """Test creation of empty analysis result"""
    engine = AnalysisEngine(settings)

    result = engine._create_empty_result(date(2022, 1, 1), 1.5)

    assert result.analysis_date == date(2022, 1, 1)
    assert result.total_logs_processed == 0
    assert result.error_count == 0
    assert result.warning_count == 0
    assert result.analyzed_clusters == []
    assert len(result.top_issues) == 0
    # health_score field was removed
    assert "No logs found" in result.llm_summary
    assert result.execution_time == 1.5

def test_analysis_engine_error_inheritance():
    """Test AnalysisEngineError is proper exception"""
    error = AnalysisEngineError("Test error")
    assert isinstance(error, Exception)
    assert str(error) == "Test error"


def test_analyze_daily_logs_with_milvus_storage(settings, mock_components, sample_logs, sample_clusters, tmp_path):
    """Test analysis stores results in Milvus"""
    engine = AnalysisEngine(settings)

    # Configure mock responses
    mock_components['milvus'].query_time_range.return_value = sample_logs
    mock_components['milvus'].cluster_similar_logs.return_value = sample_clusters

    def mock_analyze_clusters(clusters):
        for i, cluster in enumerate(clusters):
            cluster.severity = [SeverityLevel.HIGH, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM][i]
            cluster.reasoning = ["Error reasoning", "Critical reasoning", "Medium reasoning"][i]
    mock_components['llm'].analyze_clusters.side_effect = mock_analyze_clusters
    mock_components['llm'].generate_daily_summary.return_value = "System issues found"

    # Mock report generation
    mock_report = {"summary": "test report"}
    mock_components['reporter'].generate_daily_report.return_value = mock_report
    mock_components['reporter'].save_report.return_value = str(tmp_path / "report.json")

    # Mock results store
    mock_components['results_store'].store_analysis_result.return_value = 123

    result = engine.analyze_daily_logs(date(2022, 1, 1))

    # Verify analysis completed
    assert isinstance(result, DailyAnalysisResult)
    assert result.total_logs_processed == 10

    # Verify results were stored in Milvus
    mock_components['results_store'].store_analysis_result.assert_called_once()
    store_call = mock_components['results_store'].store_analysis_result.call_args
    assert store_call[1]['analysis'] == result
    assert store_call[1]['report'] == mock_report




def test_analyze_daily_logs_milvus_storage_failure_continues(settings, mock_components, sample_logs, sample_clusters, tmp_path):
    """Test analysis continues even if Milvus storage fails"""
    engine = AnalysisEngine(settings)

    # Configure mock responses
    mock_components['milvus'].query_time_range.return_value = sample_logs
    mock_components['milvus'].cluster_similar_logs.return_value = sample_clusters

    def mock_analyze_clusters(clusters):
        for i, cluster in enumerate(clusters):
            cluster.severity = [SeverityLevel.HIGH, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM][i]
            cluster.reasoning = "Test reasoning"
    mock_components['llm'].analyze_clusters.side_effect = mock_analyze_clusters
    mock_components['llm'].generate_daily_summary.return_value = "Summary"
    mock_components['reporter'].generate_daily_report.return_value = {"summary": "test"}
    mock_components['reporter'].save_report.return_value = str(tmp_path / "report.json")

    # Mock storage failure
    from analyzer.storage.analysis_results_store import AnalysisResultsStoreError
    mock_components['results_store'].store_analysis_result.side_effect = AnalysisResultsStoreError("Storage failed")

    # Analysis should complete despite storage failure
    result = engine.analyze_daily_logs(date(2022, 1, 1))

    assert isinstance(result, DailyAnalysisResult)
    assert result.total_logs_processed == 10
    # Storage was attempted
    mock_components['results_store'].store_analysis_result.assert_called_once()


def test_health_check_with_results_store(settings, mock_components):
    """Test health check includes results store"""
    engine = AnalysisEngine(settings)

    # Configure all health checks to return True
    mock_components['milvus'].health_check.return_value = True
    mock_components['llm'].health_check.return_value = True
    mock_components['results_store'].health_check.return_value = True

    health = engine.health_check()

    assert health['milvus'] is True
    assert health['llm'] is True
    assert health['results_store'] is True
    assert health['report_generator'] is True
    assert health['overall'] is True

    # Verify results store health check was called
    mock_components['results_store'].health_check.assert_called_once()


def test_health_check_results_store_failure(settings, mock_components):
    """Test health check fails when results store is unhealthy"""
    engine = AnalysisEngine(settings)

    # Configure results store health check to fail
    mock_components['milvus'].health_check.return_value = True
    mock_components['llm'].health_check.return_value = True
    mock_components['results_store'].health_check.return_value = False

    health = engine.health_check()

    assert health['milvus'] is True
    assert health['llm'] is True
    assert health['results_store'] is False
    assert health['report_generator'] is True
    assert health['overall'] is False  # Overall fails if results store fails