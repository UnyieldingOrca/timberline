"""
Unit tests for the llm.client module
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from analyzer.llm.client import (
    LLMClient, LLMError, LLMConnectionError, LLMResponseError, LLMResponse
)
from analyzer.config.settings import Settings
from analyzer.models.log import LogRecord, LogCluster, AnalyzedLog


@pytest.fixture
def llm_settings():
    """Create test settings for LLM"""
    return Settings.from_dict({
        'llm_model': 'gpt-4o-mini',
        'llm_api_key': 'test-key-12345',
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })


@pytest.fixture
def custom_endpoint_settings():
    """Create test settings for custom endpoint"""
    return Settings.from_dict({
        'llm_model': 'custom-model',
        'llm_api_key': 'test-key-12345',
        'llm_endpoint': 'http://localhost:8000',
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })


@pytest.fixture
def sample_logs():
    """Create sample logs for testing"""
    return [
        LogRecord(
            id=1, timestamp=1640995200000, message='Database connection failed',
            source='api-server', metadata={}, embedding=[0.1] * 128, level='ERROR'
        ),
        LogRecord(
            id=2, timestamp=1640995200000, message='Request processed successfully',
            source='api-server', metadata={}, embedding=[0.2] * 128, level='INFO'
        ),
        LogRecord(
            id=3, timestamp=1640995200000, message='Memory usage high',
            source='worker', metadata={}, embedding=[0.3] * 128, level='WARNING'
        )
    ]


@pytest.fixture
def sample_clusters(sample_logs):
    """Create sample log clusters"""
    return [
        LogCluster(
            representative_log=sample_logs[0],
            similar_logs=[sample_logs[0]],
            count=1
        ),
        LogCluster(
            representative_log=sample_logs[2],
            similar_logs=[sample_logs[2]],
            count=1
        )
    ]


@pytest.fixture
def mock_openai_response():
    """Create mock OpenAI response"""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.usage = Mock()
    mock_response.usage.total_tokens = 100
    return mock_response


def test_initialization_success(llm_settings):
    """Test successful LLM client initialization"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        client = LLMClient(llm_settings)

        assert client.settings == llm_settings
        assert client.model == 'gpt-4o-mini'
        mock_openai.assert_called_once_with(api_key='test-key-12345')


def test_initialization_custom_endpoint(custom_endpoint_settings):
    """Test LLM client initialization with custom endpoint"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        client = LLMClient(custom_endpoint_settings)

        assert client.settings == custom_endpoint_settings
        assert client.model == 'custom-model'
        mock_openai.assert_called_once_with(
            api_key='test-key-12345',
            base_url='http://localhost:8000'
        )


def test_initialization_missing_key():
    """Test LLM initialization without API key"""
    # Create valid settings first, then modify to test LLM client validation
    settings = Settings.from_dict({
        'llm_model': 'gpt-4o-mini',
        'llm_api_key': 'temp-key',  # Valid initially
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })

    # Modify to remove API key after validation
    settings.llm_api_key = None

    with pytest.raises(LLMError, match="LLM API key is required"):
        LLMClient(settings)


def test_call_llm_success(llm_settings, mock_openai_response):
    """Test successful LLM call"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)
        response = client.call_llm("Test prompt")

        assert isinstance(response, LLMResponse)
        assert response.content == "Test response"
        assert response.tokens_used == 100
        assert response.model_name == 'gpt-4o-mini'
        assert response.response_time > 0

        mock_client.chat.completions.create.assert_called_once()


def test_call_llm_empty_response(llm_settings):
    """Test LLM call with empty response"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)

        with pytest.raises(LLMResponseError, match="Empty response from LLM"):
            client.call_llm("Test prompt")


def test_call_llm_connection_error(llm_settings):
    """Test LLM call with connection error"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("Connection timeout")
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)

        with pytest.raises(LLMConnectionError, match="Failed to connect to LLM"):
            client.call_llm("Test prompt")


def test_call_llm_general_error(llm_settings):
    """Test LLM call with general error"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit")
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)

        with pytest.raises(LLMResponseError, match="LLM response error"):
            client.call_llm("Test prompt")


def test_health_check_success(llm_settings, mock_openai_response):
    """Test successful health check"""
    mock_openai_response.choices[0].message.content = "OK"

    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_openai_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)
        result = client.health_check()

        assert result is True


def test_health_check_failure(llm_settings):
    """Test health check failure"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("Connection failed")
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)
        result = client.health_check()

        assert result is False


def test_analyze_log_batch_success(llm_settings, sample_logs):
    """Test successful log batch analysis"""
    analysis_response = {
        "analyses": [
            {"index": 1, "severity": 8, "category": "error", "reasoning": "Database failure"},
            {"index": 2, "severity": 2, "category": "info", "reasoning": "Normal operation"},
            {"index": 3, "severity": 5, "category": "warning", "reasoning": "High memory"}
        ]
    }

    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(analysis_response)
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 200
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)
        results = client.analyze_log_batch(sample_logs)

        assert len(results) == 3
        assert all(isinstance(r, AnalyzedLog) for r in results)
        assert results[0].severity == 8
        assert results[0].category == "error"
        assert results[1].severity == 2


def test_analyze_log_batch_json_parse_error(llm_settings, sample_logs):
    """Test log batch analysis with JSON parse error"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON"
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 50
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)
        results = client.analyze_log_batch(sample_logs)

        # Should fall back to rule-based analysis
        assert len(results) == 3
        assert all(isinstance(r, AnalyzedLog) for r in results)


def test_analyze_log_batch_empty_input(llm_settings):
    """Test log batch analysis with empty input"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)
        results = client.analyze_log_batch([])

        assert results == []


def test_rank_severity_success(llm_settings, sample_clusters):
    """Test successful severity ranking"""
    ranking_response = {"severity_scores": [8, 5]}

    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(ranking_response)
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)
        scores = client.rank_severity(sample_clusters)

        assert scores == [8, 5]


def test_rank_severity_insufficient_scores(llm_settings, sample_clusters):
    """Test severity ranking with insufficient scores"""
    ranking_response = {"severity_scores": [8]}  # Only one score for two clusters

    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(ranking_response)
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 100
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)
        scores = client.rank_severity(sample_clusters)

        assert len(scores) == 2
        assert scores[0] == 8
        assert scores[1] == 5  # Fallback score for WARNING level


def test_rank_severity_empty_input(llm_settings):
    """Test severity ranking with empty input"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)
        scores = client.rank_severity([])

        assert scores == []


def test_generate_daily_summary_success(llm_settings, sample_logs):
    """Test successful daily summary generation"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "System experiencing elevated error rates with database connectivity issues as primary concern."
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 150
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        # Create some analyzed logs
        top_issues = [
            AnalyzedLog(
                log=sample_logs[0],
                severity=8,
                reasoning="Critical database error",
                category="error"
            )
        ]

        client = LLMClient(llm_settings)
        result = client.generate_daily_summary(1000, 50, 100, top_issues)

        assert isinstance(result, str)
        assert len(result) > 50
        assert "database" in result.lower()


def test_generate_daily_summary_too_short(llm_settings):
    """Test daily summary with too short response"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "OK"  # Too short
        mock_response.usage = Mock()
        mock_response.usage.total_tokens = 10
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)

        with pytest.raises(LLMResponseError, match="Summary response too short"):
            client.generate_daily_summary(1000, 50, 100, [])


def test_generate_daily_summary_llm_failure(llm_settings):
    """Test daily summary with LLM failure"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("LLM failed")
        mock_openai.return_value = mock_client

        client = LLMClient(llm_settings)

        with pytest.raises(Exception, match="LLM failed"):
            client.generate_daily_summary(1000, 50, 100, [])


def test_fallback_severity_calculation(llm_settings, sample_logs):
    """Test fallback severity calculation"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        # Test different log levels - sample_logs[0] has "connection" in message, so gets +1 boost
        assert client._calculate_fallback_severity_from_log(sample_logs[0]) == 9  # ERROR (8) + connection boost (1)
        assert client._calculate_fallback_severity_from_log(sample_logs[2]) == 5  # WARNING

        # Test keyword boosting
        crash_log = LogRecord(
            id=99, timestamp=1640995200000, message='System crash detected',
            source='system', metadata={}, embedding=[0.1] * 128, level='ERROR'
        )
        assert client._calculate_fallback_severity_from_log(crash_log) == 10  # 8 + 2

        # Test basic ERROR level without keywords
        basic_error_log = LogRecord(
            id=100, timestamp=1640995200000, message='Something went wrong',
            source='system', metadata={}, embedding=[0.1] * 128, level='ERROR'
        )
        assert client._calculate_fallback_severity_from_log(basic_error_log) == 8  # Just ERROR level


def test_determine_category_from_level(llm_settings):
    """Test category determination from log level"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        assert client._determine_category_from_level("ERROR") == "error"
        assert client._determine_category_from_level("CRITICAL") == "error"
        assert client._determine_category_from_level("WARNING") == "warning"
        assert client._determine_category_from_level("INFO") == "info"
        assert client._determine_category_from_level("DEBUG") == "info"


def test_create_analysis_prompt(llm_settings, sample_logs):
    """Test analysis prompt creation"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        prompt = client._create_analysis_prompt(sample_logs)

        assert "Analyze these 3 log entries" in prompt
        assert "ERROR" in prompt
        assert "Database connection failed" in prompt
        assert "JSON" in prompt
        assert str(len(sample_logs)) in prompt


def test_create_ranking_prompt(llm_settings, sample_clusters):
    """Test ranking prompt creation"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        prompt = client._create_ranking_prompt(sample_clusters)

        assert "Rank these 2 log clusters" in prompt
        assert "severity_scores" in prompt
        assert "JSON" in prompt


def test_create_summary_prompt(llm_settings, sample_logs):
    """Test summary prompt creation"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        top_issues = [
            AnalyzedLog(
                log=sample_logs[0],
                severity=8,
                reasoning="Database error",
                category="error"
            )
        ]

        prompt = client._create_summary_prompt(1000, 50, 100, top_issues)

        assert "1,000" in prompt
        assert "5.0%" in prompt  # error rate
        assert "10.0%" in prompt  # warning rate
        assert "Top issues:" in prompt
        assert "Database connection failed" in prompt


def test_parse_analysis_response_success(llm_settings, sample_logs):
    """Test successful analysis response parsing"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        analysis_data = {
            "analyses": [
                {"index": 1, "severity": 9, "category": "error", "reasoning": "Critical database failure"},
                {"index": 2, "severity": 3, "category": "info", "reasoning": "Normal processing"},
                {"index": 3, "severity": 6, "category": "warning", "reasoning": "Memory usage elevated"}
            ]
        }

        results = client._parse_analysis_response(sample_logs, analysis_data)

        assert len(results) == 3
        assert results[0].severity == 9
        assert results[0].category == "error"
        assert results[1].severity == 3
        assert results[2].category == "warning"


def test_parse_analysis_response_missing_analyses(llm_settings, sample_logs):
    """Test analysis response parsing with missing analyses"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        analysis_data = {
            "analyses": [
                {"index": 1, "severity": 9, "category": "error", "reasoning": "Database failure"}
                # Missing analyses for logs 2 and 3
            ]
        }

        results = client._parse_analysis_response(sample_logs, analysis_data)

        assert len(results) == 3
        assert results[0].severity == 9  # From LLM
        assert results[1].severity == 2   # Fallback for INFO level
        assert results[2].severity == 5   # Fallback for WARNING level


def test_llm_response_dataclass():
    """Test LLMResponse dataclass"""
    response = LLMResponse(
        content="test content",
        tokens_used=100,
        model_name="gpt-4",
        response_time=1.5
    )

    assert response.content == "test content"
    assert response.tokens_used == 100
    assert response.model_name == "gpt-4"
    assert response.response_time == 1.5


def test_llm_error_inheritance():
    """Test LLM error classes"""
    base_error = LLMError("Base error")
    conn_error = LLMConnectionError("Connection error")
    resp_error = LLMResponseError("Response error")

    assert isinstance(base_error, Exception)
    assert isinstance(conn_error, LLMError)
    assert isinstance(resp_error, LLMError)

    assert str(base_error) == "Base error"
    assert str(conn_error) == "Connection error"
    assert str(resp_error) == "Response error"