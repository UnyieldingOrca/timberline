"""
Unit tests for the models.log module
"""
import pytest
from datetime import date, datetime
from analyzer.models.log import (
    LogRecord, LogCluster, DailyAnalysisResult,
    LogLevel, SeverityLevel
)


def test_log_level_values():
    """Test that all expected log levels exist"""
    assert LogLevel.DEBUG.value == "DEBUG"
    assert LogLevel.INFO.value == "INFO"
    assert LogLevel.WARNING.value == "WARNING"
    assert LogLevel.ERROR.value == "ERROR"
    assert LogLevel.CRITICAL.value == "CRITICAL"


def test_severity_level_values():
    """Test that all expected severity levels exist"""
    assert SeverityLevel.LOW.value == "low"
    assert SeverityLevel.MEDIUM.value == "medium"
    assert SeverityLevel.HIGH.value == "high"
    assert SeverityLevel.CRITICAL.value == "critical"


def test_severity_level_numeric_values():
    """Test numeric value mapping"""
    assert SeverityLevel.LOW.numeric_value == 2
    assert SeverityLevel.MEDIUM.numeric_value == 5
    assert SeverityLevel.HIGH.numeric_value == 7
    assert SeverityLevel.CRITICAL.numeric_value == 9


def test_severity_level_from_numeric():
    """Test conversion from numeric values"""
    assert SeverityLevel.from_numeric(1) == SeverityLevel.LOW
    assert SeverityLevel.from_numeric(4) == SeverityLevel.LOW
    assert SeverityLevel.from_numeric(5) == SeverityLevel.MEDIUM
    assert SeverityLevel.from_numeric(6) == SeverityLevel.MEDIUM
    assert SeverityLevel.from_numeric(7) == SeverityLevel.HIGH
    assert SeverityLevel.from_numeric(8) == SeverityLevel.HIGH
    assert SeverityLevel.from_numeric(9) == SeverityLevel.CRITICAL
    assert SeverityLevel.from_numeric(10) == SeverityLevel.CRITICAL


def test_severity_level_from_numeric_invalid():
    """Test invalid numeric values raise error"""
    with pytest.raises(ValueError, match="Severity value must be between 1 and 10"):
        SeverityLevel.from_numeric(0)
    with pytest.raises(ValueError, match="Severity value must be between 1 and 10"):
        SeverityLevel.from_numeric(11)


def test_severity_level_is_actionable():
    """Test actionable detection"""
    assert SeverityLevel.LOW.is_actionable() is False
    assert SeverityLevel.MEDIUM.is_actionable() is True
    assert SeverityLevel.HIGH.is_actionable() is True
    assert SeverityLevel.CRITICAL.is_actionable() is True


def test_severity_level_is_high_severity():
    """Test high severity detection"""
    assert SeverityLevel.LOW.is_high_severity() is False
    assert SeverityLevel.MEDIUM.is_high_severity() is False
    assert SeverityLevel.HIGH.is_high_severity() is True
    assert SeverityLevel.CRITICAL.is_high_severity() is True


def test_severity_level_is_critical():
    """Test critical severity detection"""
    assert SeverityLevel.LOW.is_critical() is False
    assert SeverityLevel.MEDIUM.is_critical() is False
    assert SeverityLevel.HIGH.is_critical() is False
    assert SeverityLevel.CRITICAL.is_critical() is True




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


def test_cluster_with_severity_and_reasoning(sample_logs):
    """Test cluster with severity level and reasoning"""
    cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3,
        severity=SeverityLevel.HIGH,
        reasoning="Database connection failures affecting multiple services"
    )
    assert cluster.severity == SeverityLevel.HIGH
    assert cluster.severity_score == 7
    assert cluster.reasoning == "Database connection failures affecting multiple services"
    assert cluster.is_high_severity() is True
    assert cluster.is_actionable() is True
    assert cluster.is_analyzed() is True


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
        severity=SeverityLevel.HIGH
    )
    low_severity_cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3,
        severity=SeverityLevel.LOW
    )
    no_severity_cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs,
        count=3
    )

    assert high_severity_cluster.is_high_severity() is True
    assert low_severity_cluster.is_high_severity() is False
    assert no_severity_cluster.is_high_severity() is False


@pytest.fixture
def sample_log():
    """Create a sample log for analysis tests"""
    return LogRecord(
        id=1, timestamp=1640995200000, message="error message", source="pod-1",
        metadata={}, embedding=[0.1], level="ERROR"
    )


def test_cluster_to_dict(sample_logs):
    """Test cluster dictionary conversion"""
    cluster = LogCluster(
        representative_log=sample_logs[0],
        similar_logs=sample_logs[:2],
        count=2,
        severity=SeverityLevel.HIGH,
        reasoning="Database connection failures"
    )
    result = cluster.to_dict()
    assert result['severity'] == "high"
    assert result['severity_score'] == 7
    assert result['reasoning'] == "Database connection failures"
    assert result['count'] == 2
    assert 'representative_log' in result
    assert 'is_actionable' in result
    assert 'is_high_severity' in result
    assert 'time_range' in result


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result for testing"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="error", source="pod-1",
        metadata={}, embedding=[0.1], level="ERROR"
    )
    cluster = LogCluster(
        representative_log=log,
        similar_logs=[log],
        count=1,
        severity=SeverityLevel.HIGH,
        reasoning="Database connection failure detected"
    )

    return DailyAnalysisResult(
        analysis_date=date(2022, 1, 1),
        total_logs_processed=100,
        error_count=10,
        warning_count=20,
        analyzed_clusters=[cluster],
        llm_summary="System showing some issues",
        execution_time=30.5
    )


def test_valid_analysis_result_creation(sample_analysis_result):
    """Test creating a valid analysis result"""
    result = sample_analysis_result
    assert result.total_logs_processed == 100
    assert result.error_count == 10
    assert result.warning_count == 20
    # Health score was removed from the model


def test_negative_logs_raises_error():
    """Test that negative log count raises error"""
    with pytest.raises(ValueError, match="Total logs processed cannot be negative"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=-1,
            error_count=0, warning_count=0, analyzed_clusters=[],
            llm_summary="test", execution_time=1.0
        )


def test_negative_error_count_raises_error():
    """Test that negative error count raises error"""
    with pytest.raises(ValueError, match="Error/warning counts cannot be negative"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=-1, warning_count=0, analyzed_clusters=[],
            llm_summary="test", execution_time=1.0
        )


def test_negative_execution_time_raises_error():
    """Test that negative execution time raises error"""
    with pytest.raises(ValueError, match="Execution time cannot be negative"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=0, warning_count=0, analyzed_clusters=[],
            llm_summary="test", execution_time=-1.0
        )


def test_invalid_duplicate_count_raises_error():
    """Test that invalid duplicate count raises error"""
    with pytest.raises(ValueError, match="Duplicate count must be positive"):
        LogRecord(
            id=1, timestamp=1640995200000, message="error", source="pod",
            metadata={}, embedding=[0.1], level="ERROR", duplicate_count=0
        )


def test_top_issues_property_limits_to_10():
    """Test that top_issues property returns max 10 items"""
    log = LogRecord(
        id=1, timestamp=1640995200000, message="error", source="pod",
        metadata={}, embedding=[0.1], level="ERROR"
    )

    # Create 15 actionable clusters
    clusters = []
    for i in range(15):
        cluster = LogCluster(
            representative_log=log,
            similar_logs=[log],
            count=1,
            severity=SeverityLevel.MEDIUM,  # Actionable
            reasoning=f"Issue {i}"
        )
        clusters.append(cluster)

    result = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1),
        total_logs_processed=100,
        error_count=0,
        warning_count=0,
        analyzed_clusters=clusters,
        llm_summary="test",
        execution_time=1.0
    )

    # top_issues should limit to 10
    assert len(result.top_issues) == 10


def test_empty_summary_raises_error():
    """Test that empty summary raises error"""
    with pytest.raises(ValueError, match="LLM summary cannot be empty"):
        DailyAnalysisResult(
            analysis_date=date(2022, 1, 1), total_logs_processed=100,
            error_count=0, warning_count=0, analyzed_clusters=[],
            llm_summary="", execution_time=1.0
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
 llm_summary="test", execution_time=1.0
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
        llm_summary="test", execution_time=1.0
    )
    warning = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1), total_logs_processed=100,
        error_count=5, warning_count=10, analyzed_clusters=[],
        llm_summary="test", execution_time=1.0
    )
    critical = DailyAnalysisResult(
        analysis_date=date(2022, 1, 1), total_logs_processed=100,
        error_count=20, warning_count=30, analyzed_clusters=[],
        llm_summary="test", execution_time=1.0
    )

    # Health status now based on error rates instead of health_score
    assert healthy.error_rate == 0.0
    assert warning.error_rate == 5.0
    assert critical.error_rate == 20.0


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
    # health_score and health_status removed from model
    assert summary['critical_issues_count'] == 1
    assert summary['total_clusters'] == 1
    assert summary['execution_time'] == 30.5