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
from analyzer.models.log import LogRecord, LogCluster, SeverityLevel

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

def test_analyze_clusters_success(llm_settings, sample_clusters):
    """Test successful cluster analysis"""
    analysis_response = {
        "analyses": [
            {"index": 1, "severity": 8, "reasoning": "Database connection failures affecting multiple services"},
            {"index": 2, "severity": 3, "reasoning": "Normal informational messages"}
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
        client.analyze_clusters(sample_clusters)

        assert sample_clusters[0].severity == SeverityLevel.HIGH
        assert sample_clusters[0].reasoning == "Database connection failures affecting multiple services"
        assert sample_clusters[1].severity == SeverityLevel.LOW
        assert sample_clusters[1].reasoning == "Normal informational messages"

def test_analyze_clusters_json_parse_error(llm_settings, sample_clusters):
    """Test analyze_clusters with JSON parse error - should raise exception"""
    with patch('analyzer.llm.client.OpenAI') as mock_openai:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content='Invalid JSON{'))]
        mock_openai.return_value.chat.completions.create.return_value = mock_response

        client = LLMClient(llm_settings)

        # Should raise JSONDecodeError when LLM returns invalid JSON
        with pytest.raises(json.JSONDecodeError):
            client.analyze_clusters(sample_clusters[:1])

def test_analyze_clusters_empty_input(llm_settings):
    """Test cluster analysis with empty input"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)
        client.analyze_clusters([])
        # Empty input should complete without error, no return value to check

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

        assert scores == [SeverityLevel.HIGH, SeverityLevel.MEDIUM]

def test_rank_severity_insufficient_scores(llm_settings, sample_clusters):
    """Test severity ranking with insufficient scores - should raise exception"""
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
        from analyzer.llm.client import LLMError
        with pytest.raises(LLMError, match="returned 1 scores for 2 clusters"):
            client.rank_severity(sample_clusters)

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

        # Create some top issue clusters
        cluster = LogCluster(
            representative_log=sample_logs[0],
            similar_logs=[sample_logs[0]],
            count=1
        )
        cluster.severity = SeverityLevel.HIGH
        cluster.reasoning = "Critical database error"
        top_issues = [cluster]

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

def test_create_cluster_analysis_prompt(llm_settings, sample_clusters):
    """Test cluster analysis prompt creation"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        prompt = client._create_cluster_analysis_prompt(sample_clusters)

        assert "Analyze these 2 log clusters" in prompt
        assert "ERROR" in prompt
        assert "Database connection failed" in prompt
        assert "JSON" in prompt
        assert str(len(sample_clusters)) in prompt

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

        cluster = LogCluster(
            representative_log=sample_logs[0],
            similar_logs=[sample_logs[0]],
            count=1
        )
        cluster.severity = SeverityLevel.HIGH
        cluster.reasoning = "Database error"
        top_issues = [cluster]

        prompt = client._create_summary_prompt(1000, 50, 100, top_issues)

        assert "1,000" in prompt
        assert "5.0%" in prompt  # error rate
        assert "10.0%" in prompt  # warning rate
        assert "Top issues:" in prompt
        assert "Database connection failed" in prompt

def test_update_clusters_with_analysis_success(llm_settings, sample_clusters):
    """Test successful cluster analysis update"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        analysis_data = {
            "analyses": [
                {"index": 1, "severity": 9, "reasoning": "Critical database failure"},
                {"index": 2, "severity": 2, "reasoning": "Normal processing"}
            ]
        }

        client._update_clusters_with_analysis(sample_clusters, analysis_data)

        assert len(sample_clusters) == 2
        assert sample_clusters[0].severity == SeverityLevel.CRITICAL
        assert sample_clusters[0].reasoning == "Critical database failure"
        assert sample_clusters[1].severity == SeverityLevel.LOW
        assert sample_clusters[1].reasoning == "Normal processing"

def test_update_clusters_with_analysis_missing_analyses(llm_settings, sample_clusters):
    """Test cluster analysis update with missing analyses - should use defaults"""
    with patch('analyzer.llm.client.OpenAI'):
        client = LLMClient(llm_settings)

        analysis_data = {
            "analyses": [
                {"index": 1, "severity": 9, "reasoning": "Database failure"}
                # Missing analyses for cluster 2
            ]
        }

        # Should handle missing analysis gracefully by using defaults
        client._update_clusters_with_analysis(sample_clusters, analysis_data)

        # First cluster should have the provided analysis
        assert sample_clusters[0].severity == SeverityLevel.CRITICAL
        assert sample_clusters[0].reasoning == "Database failure"

        # Second cluster should have default values
        assert sample_clusters[1].severity == SeverityLevel.MEDIUM
        assert sample_clusters[1].reasoning == "Analysis not available from LLM"

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