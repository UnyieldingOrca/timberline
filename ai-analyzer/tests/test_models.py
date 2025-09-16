"""
Unit tests for the models.log module
"""
import pytest
from datetime import date, datetime
from analyzer.models.log import (
    LogRecord, LogCluster, AnalyzedLog, DailyAnalysisResult,
    LogLevel, LogCategory
)


def test_log_level_values():
    """Test that all expected log levels exist"""
    assert LogLevel.DEBUG.value == "DEBUG"
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.WARNING.value == "WARNING"
    assert LogLevel.ERROR.value == "ERROR"
    assert LogLevel.CRITICAL.value == "CRITICAL"


def test_log_category_values():
    """Test that all expected categories exist"""
    assert LogCategory.ERROR.value == "error"
    assert LogCategory.WARNING.value == "warning"
    assert LogCategory.INFO.value == "info"
    assert LogCategory.PERFORMANCE.value == "performance"


@pytest.fixture
def valid_log_record():
    """Create a valid log record for testing"""
    return LogRecord(
        id=1,
        timestamp=1640995200000,  # 2022-01-01 00:00:00 UTC
        message="Test log message",
        source="test-pod",
        metadata={"namespace": "default"},
        embedding=[0.1, 0.2, 0.3],
        level="INFO"
    )


def test_valid_log_record_creation(valid_log_record):
    """Test creating a valid log record"""
    assert valid_log_record.id == 1
    assert valid_log_record.message == "Test log message"
    assert valid_log_record.source == "test-pod"
    assert valid_log_record.level == "INFO"


def test_invalid_timestamp_raises_error():
    """Test that negative timestamp raises error"""
    with pytest.raises(ValueError, match="Timestamp must be positive"):
        LogRecord(
            id=1, timestamp=-1, message="test", source="test",
            metadata={}, embedding=[0.1], level="INFO"
        )


def test_empty_message_raises_error():
    """Test that empty message raises error"""
    with pytest.raises(ValueError, match="Message cannot be empty"):
        LogRecord(
            id=1, timestamp=1640995200000, message="", source="test",
            metadata={}, embedding=[0.1], level="INFO"
        )


def test_empty_source_raises_error():
    """Test that empty source raises error"""
    with pytest.raises(ValueError, match="Source cannot be empty"):
        LogRecord(
            id=1, timestamp=1640995200000, message="test", source="",
            metadata={}, embedding=[0.1], level="INFO"
        )


def test_empty_embedding_raises_error():
    """Test that empty embedding raises error"""
    with pytest.raises(ValueError, match="Embedding cannot be empty"):
        LogRecord(
            id=1, timestamp=1640995200000, message="test", source="test",
            metadata={}, embedding=[], level="INFO"
        )


def test_invalid_log_level_raises_error():
    """Test that invalid log level raises error"""
    with pytest.raises(ValueError, match="Invalid log level"):
        LogRecord(
            id=1, timestamp=1640995200000, message="test", source="test",
            metadata={}, embedding=[0.1], level="INVALID"
        )


def test_datetime_property(valid_log_record):
    """Test datetime property conversion"""
    dt = valid_log_record.datetime
    assert isinstance(dt, datetime)
    # Using a more recent timestamp that doesn't have timezone conversion issues
    # The timestamp 1640995200000 is 2022-01-01 00:00:00 UTC but may be different in local time
    expected_timestamp = 1640995200000 / 1000  # Convert to seconds
    expected_dt = datetime.fromtimestamp(expected_timestamp)
    assert dt == expected_dt


def test_log_level_enum_property(valid_log_record):
    """Test log level enum property"""
    assert valid_log_record.log_level_enum == LogLevel.INFO


def test_is_error_or_critical():
    """Test error/critical detection"""
    error_log = LogRecord(
        id=1, timestamp=1640995200000, message="error", source="test",
        metadata={}, embedding=[0.1], level="ERROR"
    )
    info_log = LogRecord(
        id=2, timestamp=1640995200000, message="info", source="test",
        metadata={}, embedding=[0.1], level="INFO"
    )

    assert error_log.is_error_or_critical() is True
    assert info_log.is_error_or_critical() is False


def test_to_dict(valid_log_record):
    """Test dictionary conversion"""
    result = valid_log_record.to_dict()
    assert result['id'] == 1
    assert result['message'] == "Test log message"
    assert result['source'] == "test-pod"
    assert result['level'] == "INFO"
    assert 'datetime_iso' in result


@pytest.fixture
def sample_logs():
    """Create sample logs for clustering tests"""
    return [
        LogRecord(
            id=1, timestamp=1640995200000, message="error 1", source="pod-1",
            metadata={}, embedding=[0.1], level="ERROR"
        ),
        LogRecord(
            id=2, timestamp=1640995260000, message="error 2", source="pod-2",
            metadata={}, embedding=[0.2], level="ERROR"
        ),
        LogRecord(
            id=3, timestamp=1640995320000, message="error 3", source="pod-1",
            metadata={}, embedding=[0.3], level="INFO"
        )
    ]


def test_valid_cluster_creation(sample_logs):
    """Test creating a valid log cluster"""
    cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3
    )
    assert cluster.count == 3
    assert len(cluster.similar_logs) == 3
    assert cluster.representative_log == sample_logs[0]


def test_invalid_count_raises_error(sample_logs):
    """Test that invalid count raises error"""
    with pytest.raises(ValueError, match="Count must be positive"):
        LogCluster(
            representative_log=sample_logs[0],
            similar_logs=sample_logs,
            count=0
        )


def test_count_mismatch_raises_error(sample_logs):
    """Test that count mismatch raises error"""
    with pytest.raises(ValueError, match="Count must match number of similar logs"):
        LogCluster(
            representative_log=sample_logs[0],
            similar_logs=sample_logs,
            count=5  # Wrong count
        )


def test_representative_not_in_logs_raises_error(sample_logs):
    """Test that representative log not in similar_logs raises error"""
    other_log = LogRecord(
        id=99, timestamp=1640995200000, message="other", source="other",
        metadata={}, embedding=[0.9], level="INFO"
    )
    with pytest.raises(ValueError, match="Representative log must be in similar_logs list"):
        LogCluster(
            representative_log=other_log,
            similar_logs=sample_logs,
            count=3
        )


def test_invalid_severity_score_raises_error(sample_logs):
    """Test that invalid severity score raises error"""
    with pytest.raises(ValueError, match="Severity score must be between 1 and 10"):
        LogCluster(
            representative_log=sample_logs[0],
            similar_logs=sample_logs,
            count=3,
            severity_score=15  # Invalid score
        )


def test_error_count_property(sample_logs):
    """Test error count property"""
    cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3
    )
    assert cluster.error_count == 2  # Two ERROR level logs


def test_sources_property(sample_logs):
    """Test sources property"""
    cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3
    )
    sources = cluster.sources
    assert len(sources) == 2  # pod-1 and pod-2
    assert "pod-1" in sources
    assert "pod-2" in sources


def test_get_time_range(sample_logs):
    """Test time range calculation"""
    cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3
    )
    start_time, end_time = cluster.get_time_range()
    assert isinstance(start_time, datetime)
    assert isinstance(end_time, datetime)
    assert start_time <= end_time


def test_is_high_severity(sample_logs):
    """Test high severity detection"""
    high_severity_cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3,
        severity_score=8
    )
    low_severity_cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3,
        severity_score=3
    )
    no_score_cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3
    )

    assert high_severity_cluster.is_high_severity() is True
    assert low_severity_cluster.is_high_severity() is False
    assert no_score_cluster.is_high_severity() is False


@pytest.fixture
def sample_log():
    """Create a sample log for analysis tests"""
    return LogRecord(
        id=1, timestamp=1640995200000, message="error message", source="pod-1",
        metadata={}, embedding=[0.1], level="ERROR"
    )


def test_valid_analyzed_log_creation(sample_log):
    """Test creating a valid analyzed log"""
    analyzed = AnalyzedLog(
        log=sample_log,
        severity=8,
        reasoning="Critical database connection error",
        category="error"
    )
    assert analyzed.severity == 8
    assert analyzed.reasoning == "Critical database connection error"
    assert analyzed.category == "error"


def test_invalid_severity_raises_error(sample_log):
    """Test that invalid severity raises error"""
    with pytest.raises(ValueError, match="Severity must be between 1 and 10"):
        AnalyzedLog(
            log=sample_log, severity=15, reasoning="test", category="error"
        )


def test_empty_reasoning_raises_error(sample_log):
    """Test that empty reasoning raises error"""
    with pytest.raises(ValueError, match="Reasoning cannot be empty"):
        AnalyzedLog(
            log=sample_log, severity=5, reasoning="", category="error"
        )


def test_invalid_category_raises_error(sample_log):
    """Test that invalid category raises error"""
    with pytest.raises(ValueError, match="Invalid category"):
        AnalyzedLog(
            log=sample_log, severity=5, reasoning="test", category="invalid"
        )


def test_category_enum_property(sample_log):
    """Test category enum property"""
    analyzed = AnalyzedLog(
        log=sample_log, severity=8, reasoning="test", category="error"
    )
    assert analyzed.category_enum == LogCategory.ERROR


def test_is_actionable(sample_log):
    """Test actionable detection"""
    actionable = AnalyzedLog(
        log=sample_log, severity=7, reasoning="test", category="error"
    )
    not_actionable = AnalyzedLog(
        log=sample_log, severity=3, reasoning="test", category="info"
    )

    assert actionable.is_actionable() is True
    assert not_actionable.is_actionable() is False


def test_analyzed_log_to_dict(sample_log):
    """Test dictionary conversion"""
    analyzed = AnalyzedLog(
        log=sample_log, severity=8, reasoning="test", category="error"
    )
    result = analyzed.to_dict()
    assert result['severity'] == 8
    assert result['reasoning'] == "test"
    assert result['category'] == "error"
    assert 'log' in result
    assert 'is_actionable' in result


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result for testing"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="error", source="pod-1",
        metadata={}, embedding=[0.1], level="ERROR"
    )
    cluster = LogCluster(
        representative_log=log, similar_logs=[log], count=1
    )
    analyzed_log = AnalyzedLog(
        log=log, severity=8, reasoning="test", category="error"
    )

    return DailyAnalysisResult(
        analysis_date=date(2022, 1, 1),
        total_logs_processed=100,
        error_count=10,
        warning_count=20,
        analyzed_clusters=[cluster],
        top_issues=[analyzed_log],
        health_score=0.7,
        llm_summary="System showing some issues",
        execution_time=30.5
    )


def test_valid_analysis_result_creation(sample_analysis_result):
    """Test creating a valid analysis result"""
    result = sample_analysis_result
    assert result.total_logs_processed == 100
    assert result.error_count == 10
    assert result.warning_count == 20
    assert result.health_score == 0.7


def test_negative_logs_raises_error():
    """Test that negative log count raises error"""
    with pytest.raises(ValueError, match="Total logs processed cannot be negative"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=-1,
            error_count=0, warning_count=0, analyzed_clusters=[],
            top_issues=[], health_score=0.5, llm_summary="test", execution_time=1.0
        )


def test_negative_error_count_raises_error():
    """Test that negative error count raises error"""
    with pytest.raises(ValueError, match="Error/warning counts cannot be negative"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=-1, warning_count=0, analyzed_clusters=[],
            top_issues=[], health_score=0.5, llm_summary="test", execution_time=1.0
        )


def test_negative_execution_time_raises_error():
    """Test that negative execution time raises error"""
    with pytest.raises(ValueError, match="Execution time cannot be negative"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=0, warning_count=0, analyzed_clusters=[],
            top_issues=[], health_score=0.5, llm_summary="test", execution_time=-1.0
        )


def test_invalid_health_score_raises_error():
    """Test that invalid health score raises error"""
    with pytest.raises(ValueError, match="Health score must be between 0 and 1"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=0, warning_count=0, analyzed_clusters=[],
            top_issues=[], health_score=1.5, llm_summary="test", execution_time=1.0
        )


def test_too_many_top_issues_raises_error():
    """Test that too many top issues raises error"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="error", source="pod",
        metadata={}, embedding=[0.1], level="ERROR"
    )
    issues = [AnalyzedLog(log=log, severity=5, reasoning="test", category="error")
              for _ in range(15)]  # Too many

    with pytest.raises(ValueError, match="Top issues should not exceed 10 items"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=0, warning_count=0, analyzed_clusters=[],
            top_issues=issues, health_score=0.5, llm_summary="test", execution_time=1.0
        )


def test_empty_summary_raises_error():
    """Test that empty summary raises error"""
    with pytest.raises(ValueError, match="LLM summary cannot be empty"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=0, warning_count=0, analyzed_clusters=[],
            top_issues=[], health_score=0.5, llm_summary="", execution_time=1.0
        )


def test_info_count_property(sample_analysis_result):
    """Test info count calculation"""
    result = sample_analysis_result
    assert result.info_count == 70  # 100 - 10 - 20


def test_error_rate_property(sample_analysis_result):
    """Test error rate calculation"""
    result = sample_analysis_result
    assert result.error_rate == 10.0  # 10/100 * 100


def test_warning_rate_property(sample_analysis_result):
    """Test warning rate calculation"""
    result = sample_analysis_result
    assert result.warning_rate == 20.0  # 20/100 * 100


def test_zero_logs_rates():
    """Test rate calculation with zero logs"""
    result = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1), total_logs_processed=0,
        error_count=0, warning_count=0, analyzed_clusters=[],
        top_issues=[], health_score=1.0, llm_summary="test", execution_time=1.0
    )
    assert result.error_rate == 0.0
    assert result.warning_rate == 0.0


def test_get_critical_issues(sample_analysis_result):
    """Test critical issues filtering"""
    result = sample_analysis_result
    critical_issues = result.get_critical_issues()
    assert len(critical_issues) == 1  # One issue with severity 8


def test_get_health_status():
    """Test health status calculation"""
    healthy = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1), total_logs_processed=100,
        error_count=0, warning_count=0, analyzed_clusters=[],
        top_issues=[], health_score=0.9, llm_summary="test", execution_time=1.0
    )
    warning = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1), total_logs_processed=100,
        error_count=0, warning_count=0, analyzed_clusters=[],
        top_issues=[], health_score=0.6, llm_summary="test", execution_time=1.0
    )
    critical = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1), total_logs_processed=100,
        error_count=0, warning_count=0, analyzed_clusters=[],
        top_issues=[], health_score=0.3, llm_summary="test", execution_time=1.0
    )

    assert healthy.get_health_status() == "healthy"
    assert warning.get_health_status() == "warning"
    assert critical.get_health_status() == "critical"


def test_to_summary_dict(sample_analysis_result):
    """Test summary dictionary conversion"""
    result = sample_analysis_result
    summary = result.to_summary_dict()

    assert summary['analysis_date'] == "2022-01-01"
    assert summary['total_logs_processed'] == 100
    assert summary['error_count'] == 10
    assert summary['warning_count'] == 20
    assert summary['info_count'] == 70
    assert summary['error_rate'] == 10.0
    assert summary['warning_rate'] == 20.0
    assert summary['health_score'] == 0.7
    assert summary['health_status'] == "warning"
    assert summary['critical_issues_count'] == 1
    assert summary['total_clusters'] == 1
    assert summary['execution_time'] == 30.5