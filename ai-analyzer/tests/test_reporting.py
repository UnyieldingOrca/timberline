"""
Unit tests for the reporting.generator module
"""
import pytest
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, mock_open

from analyzer.reporting.generator import ReportGenerator, ReportGeneratorError
from analyzer.config.settings import Settings
from analyzer.models.log import (
    DailyAnalysisResult, LogRecord, LogCluster, AnalyzedLog
)


@pytest.fixture
def settings(tmp_path):
    """Create test settings with temporary directory"""
    return Settings.from_dict({
        'report_output_dir': str(tmp_path / "reports"),
        'webhook_url': 'https://hooks.slack.com/test',
        'llm_api_key': 'test-key',
        'llm_endpoint': 'http://localhost:8000'
    })


@pytest.fixture
def settings_no_webhook(tmp_path):
    """Create test settings without webhook"""
    return Settings.from_dict({
        'report_output_dir': str(tmp_path / "reports"),
        'webhook_url': None,
        'llm_api_key': 'test-key',
        'llm_endpoint': 'http://localhost:8000'
    })


@pytest.fixture
def sample_logs():
    """Create sample log records"""
    logs = []
    base_time = datetime(2022, 1, 1, 10, 0, 0)

    for i in range(5):
        logs.append(LogRecord(
            id=i + 1,
            timestamp=int((base_time + timedelta(minutes=i)).timestamp() * 1000),
            message=f"Test log message {i + 1}",
            source=f"pod-{(i % 3) + 1}",
            metadata={"namespace": "test", "pod": f"app-{i}"},
            embedding=[0.1 + (i * 0.1)] * 128,
            level=["INFO", "WARNING", "ERROR", "INFO", "CRITICAL"][i]
        ))

    return logs


@pytest.fixture
def sample_clusters(sample_logs):
    """Create sample log clusters"""
    clusters = [
        LogCluster(
            representative_log=sample_logs[0],
            similar_logs=[sample_logs[0], sample_logs[3]],
            count=2
        ),
        LogCluster(
            representative_log=sample_logs[2],
            similar_logs=[sample_logs[2]],
            count=1
        ),
        LogCluster(
            representative_log=sample_logs[4],
            similar_logs=[sample_logs[4]],
            count=1
        )
    ]

    # Add severity scores
    for i, cluster in enumerate(clusters):
        cluster.severity_score = [5, 8, 10][i]

    return clusters


@pytest.fixture
def sample_analyzed_logs(sample_logs):
    """Create sample analyzed logs"""
    return [
        AnalyzedLog(
            log=sample_logs[2],  # ERROR level
            severity=8,
            reasoning="Database connection failure detected",
            category="error"
        ),
        AnalyzedLog(
            log=sample_logs[4],  # CRITICAL level
            severity=10,
            reasoning="Critical system failure",
            category="error"  # Use valid category
        ),
        AnalyzedLog(
            log=sample_logs[1],  # WARNING level
            severity=5,
            reasoning="Performance degradation warning",
            category="warning"
        )
    ]


@pytest.fixture
def sample_analysis(sample_clusters, sample_analyzed_logs):
    """Create sample daily analysis result"""
    return DailyAnalysisResult(
        analysis_date=datetime(2022, 1, 1),
        total_logs_processed=1000,
        error_count=50,
        warning_count=150,
        health_score=0.75,  # Valid health score between 0 and 1
        analyzed_clusters=sample_clusters,
        top_issues=sample_analyzed_logs,
        llm_summary="System showing elevated error rates with database issues.",
        execution_time=45.2
    )


def test_initialization_success(settings):
    """Test successful ReportGenerator initialization"""
    generator = ReportGenerator(settings)

    assert generator.settings == settings
    assert generator.output_dir == Path(settings.report_output_dir)
    assert generator.webhook_url == settings.webhook_url
    assert generator.output_dir.exists()


def test_initialization_invalid_directory():
    """Test initialization with invalid directory"""
    # Try to create directory in non-existent parent
    settings = Settings.from_dict({
        'report_output_dir': '/nonexistent/path/reports',
        'llm_api_key': 'test-key',
        'llm_endpoint': 'http://localhost:8000'
    })

    # Should handle the error gracefully or create the directory
    try:
        generator = ReportGenerator(settings)
        # If successful, the directory should have been created
        assert generator.output_dir.exists()
    except ReportGeneratorError:
        # This is also acceptable behavior
        pass


def test_generate_daily_report_success(settings, sample_analysis):
    """Test successful daily report generation"""
    generator = ReportGenerator(settings)

    report = generator.generate_daily_report(sample_analysis)

    # Verify report structure
    assert isinstance(report, dict)
    assert "analysis_date" in report
    assert "generated_at" in report
    assert "execution_time_seconds" in report
    assert "summary" in report
    assert "clusters" in report
    assert "top_issues" in report
    assert "llm_summary" in report

    # Verify summary content
    summary = report["summary"]
    assert summary["total_logs_processed"] == 1000
    assert summary["error_count"] == 50
    assert summary["warning_count"] == 150
    assert summary["health_score"] == 0.75
    assert summary["clusters_found"] == 3
    assert summary["top_issues_identified"] == 3

    # Verify clusters
    assert len(report["clusters"]) == 3
    cluster = report["clusters"][0]
    assert "id" in cluster
    assert "representative_message" in cluster
    assert "count" in cluster
    assert "severity_score" in cluster
    assert "source" in cluster
    assert "level" in cluster
    assert "timestamp" in cluster

    # Verify top issues
    assert len(report["top_issues"]) == 3
    issue = report["top_issues"][0]
    assert "severity" in issue
    assert "category" in issue
    assert "reasoning" in issue
    assert "message" in issue
    assert "source" in issue
    assert "timestamp" in issue
    assert "level" in issue


def test_generate_daily_report_none_analysis(settings):
    """Test report generation with None analysis"""
    generator = ReportGenerator(settings)

    with pytest.raises(ReportGeneratorError, match="Analysis result cannot be None"):
        generator.generate_daily_report(None)


def test_generate_daily_report_empty_clusters(settings, sample_analysis):
    """Test report generation with empty clusters"""
    generator = ReportGenerator(settings)

    # Modify sample to have empty clusters
    sample_analysis.analyzed_clusters = []
    sample_analysis.top_issues = []
    sample_analysis.llm_summary = None

    report = generator.generate_daily_report(sample_analysis)

    assert len(report["clusters"]) == 0
    assert len(report["top_issues"]) == 0
    assert report["llm_summary"] == "No summary available"
    assert report["summary"]["clusters_found"] == 0
    assert report["summary"]["top_issues_identified"] == 0


def test_truncate_message(settings):
    """Test message truncation"""
    generator = ReportGenerator(settings)

    # Test normal message
    short_message = "Short message"
    assert generator._truncate_message(short_message, 100) == short_message

    # Test long message
    long_message = "A" * 300
    truncated = generator._truncate_message(long_message, 100)
    assert len(truncated) == 100
    assert truncated.endswith("...")

    # Test empty message
    assert generator._truncate_message("", 100) == ""

    # Test None message
    assert generator._truncate_message(None, 100) == ""


def test_save_report_success(settings, sample_analysis):
    """Test successful report saving"""
    generator = ReportGenerator(settings)
    report = generator.generate_daily_report(sample_analysis)

    # Test with explicit filepath
    filepath = str(generator.output_dir / "test_report.json")
    result_path = generator.save_report(report, filepath)

    assert result_path == filepath
    assert Path(filepath).exists()

    # Verify file contents
    with open(filepath, 'r', encoding='utf-8') as f:
        saved_report = json.load(f)

    assert saved_report == report


def test_save_report_auto_filepath(settings, sample_analysis):
    """Test report saving with automatic filepath generation"""
    generator = ReportGenerator(settings)
    report = generator.generate_daily_report(sample_analysis)

    filepath = generator.save_report(report)

    assert Path(filepath).exists()
    assert "daily_analysis_20220101.json" in filepath


def test_save_report_invalid_path(settings, sample_analysis):
    """Test report saving with invalid path"""
    generator = ReportGenerator(settings)
    report = generator.generate_daily_report(sample_analysis)

    # Try to save to invalid path (readonly filesystem simulation)
    with patch('builtins.open', mock_open()) as mock_file:
        mock_file.side_effect = PermissionError("Permission denied")

        with pytest.raises(ReportGeneratorError, match="Failed to save report"):
            generator.save_report(report, "/invalid/path/report.json")


def test_send_webhook_notification_success(settings, sample_analysis):
    """Test successful webhook notification"""
    generator = ReportGenerator(settings)
    report = generator.generate_daily_report(sample_analysis)

    result = generator.send_webhook_notification(report)

    assert result is True


def test_send_webhook_notification_no_url(settings_no_webhook, sample_analysis):
    """Test webhook notification with no URL configured"""
    generator = ReportGenerator(settings_no_webhook)
    report = generator.generate_daily_report(sample_analysis)

    result = generator.send_webhook_notification(report)

    assert result is False


def test_send_webhook_notification_error(settings, sample_analysis):
    """Test webhook notification with error"""
    generator = ReportGenerator(settings)
    report = generator.generate_daily_report(sample_analysis)

    # Mock json.dumps to raise an exception
    with patch('analyzer.reporting.generator.json.dumps') as mock_dumps:
        mock_dumps.side_effect = Exception("JSON serialization error")

        result = generator.send_webhook_notification(report)

        assert result is False


def test_generate_and_save_report_success(settings, sample_analysis):
    """Test complete report generation and saving"""
    generator = ReportGenerator(settings)

    filepath = generator.generate_and_save_report(sample_analysis)

    assert Path(filepath).exists()
    assert "daily_analysis_20220101.json" in filepath

    # Verify file contents
    with open(filepath, 'r', encoding='utf-8') as f:
        saved_report = json.load(f)

    assert saved_report["analysis_date"] == "2022-01-01T00:00:00"
    assert saved_report["summary"]["total_logs_processed"] == 1000


def test_generate_and_save_report_none_analysis(settings):
    """Test complete report generation with None analysis"""
    generator = ReportGenerator(settings)

    with pytest.raises(ReportGeneratorError, match="Analysis result cannot be None"):
        generator.generate_and_save_report(None)


def test_list_reports(settings, sample_analysis):
    """Test listing report files"""
    generator = ReportGenerator(settings)

    # Create some reports
    generator.generate_and_save_report(sample_analysis)

    # Modify date and create another report
    sample_analysis.analysis_date = datetime(2022, 1, 2)
    generator.generate_and_save_report(sample_analysis)

    reports = generator.list_reports()

    assert len(reports) >= 2
    for report_info in reports:
        assert "filepath" in report_info
        assert "filename" in report_info
        assert "size_bytes" in report_info
        assert "modified" in report_info
        assert report_info["filename"].startswith("daily_analysis_")


def test_list_reports_empty_directory(settings):
    """Test listing reports from empty directory"""
    generator = ReportGenerator(settings)

    reports = generator.list_reports()

    assert reports == []


def test_list_reports_with_limit(settings, sample_analysis):
    """Test listing reports with limit"""
    generator = ReportGenerator(settings)

    # Create multiple reports
    for i in range(5):
        sample_analysis.analysis_date = datetime(2022, 1, i + 1)
        generator.generate_and_save_report(sample_analysis)

    reports = generator.list_reports(limit=3)

    assert len(reports) == 3


def test_cleanup_old_reports(settings, sample_analysis):
    """Test cleaning up old report files"""
    generator = ReportGenerator(settings)

    # Create some reports
    filepath1 = generator.generate_and_save_report(sample_analysis)

    # Create an "old" file by modifying its timestamp
    old_time = (datetime.now() - timedelta(days=35)).timestamp()
    import os
    os.utime(filepath1, (old_time, old_time))

    # Create a recent file
    sample_analysis.analysis_date = datetime(2022, 1, 2)
    filepath2 = generator.generate_and_save_report(sample_analysis)

    # Cleanup files older than 30 days
    removed_count = generator.cleanup_old_reports(keep_days=30)

    assert removed_count == 1
    assert not Path(filepath1).exists()
    assert Path(filepath2).exists()


def test_cleanup_old_reports_invalid_days(settings):
    """Test cleanup with invalid days parameter"""
    generator = ReportGenerator(settings)

    with pytest.raises(ValueError, match="keep_days must be positive"):
        generator.cleanup_old_reports(keep_days=0)

    with pytest.raises(ValueError, match="keep_days must be positive"):
        generator.cleanup_old_reports(keep_days=-5)


def test_cleanup_old_reports_no_files(settings):
    """Test cleanup with no files"""
    generator = ReportGenerator(settings)

    removed_count = generator.cleanup_old_reports(keep_days=30)

    assert removed_count == 0


def test_cleanup_old_reports_error_handling(settings, sample_analysis):
    """Test cleanup error handling"""
    generator = ReportGenerator(settings)

    # Create a report
    generator.generate_and_save_report(sample_analysis)

    # Mock Path.glob to raise an exception
    with patch('pathlib.Path.glob') as mock_glob:
        mock_glob.side_effect = Exception("Filesystem error")

        removed_count = generator.cleanup_old_reports(keep_days=30)

        assert removed_count == 0


def test_report_generator_error_inheritance():
    """Test ReportGeneratorError is proper exception"""
    error = ReportGeneratorError("Test error")
    assert isinstance(error, Exception)
    assert str(error) == "Test error"


def test_long_message_truncation_in_report(settings, sample_analysis):
    """Test that long messages are properly truncated in reports"""
    generator = ReportGenerator(settings)

    # Create a log with very long message
    long_message = "A" * 500
    sample_analysis.analyzed_clusters[0].representative_log.message = long_message
    sample_analysis.top_issues[0].log.message = long_message

    report = generator.generate_daily_report(sample_analysis)

    # Check cluster message truncation
    cluster_message = report["clusters"][0]["representative_message"]
    assert len(cluster_message) == 200
    assert cluster_message.endswith("...")

    # Check top issue message truncation
    issue_message = report["top_issues"][0]["message"]
    assert len(issue_message) == 200
    assert issue_message.endswith("...")


def test_webhook_payload_structure(settings, sample_analysis):
    """Test webhook notification payload structure"""
    generator = ReportGenerator(settings)
    report = generator.generate_daily_report(sample_analysis)

    # Capture the logged notification payload
    with patch('analyzer.reporting.generator.logger') as mock_logger:
        generator.send_webhook_notification(report)

        # Check that logger.info was called with webhook payload
        mock_logger.info.assert_called()

        # Find the call with the webhook payload
        payload_call = None
        for call in mock_logger.info.call_args_list:
            if 'Webhook notification payload:' in str(call):
                payload_call = call
                break

        assert payload_call is not None