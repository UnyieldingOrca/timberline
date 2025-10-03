"""
Unit tests for the llm.client module
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from analyzer.llm.client import (
    LLMClient, LLMError, LLMConnectionError, LLMResponseError, LLMResponse,
    ClusterAnalysis, SeverityRanking, DailySummary
)
from analyzer.config.settings import Settings
from analyzer.models.log import LogRecord, LogCluster, SeverityLevel

@pytest.fixture
def llm_settings():
    """Create test settings for LLM"""
    return Settings.from_dict({
        'openai_provider': 'openai',
        'openai_model': 'gpt-4o-mini',
        'openai_api_key': 'test-key-12345',
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })

@pytest.fixture
def custom_endpoint_settings():
    """Create test settings for custom endpoint"""
    return Settings.from_dict({
        'openai_provider': 'openai',
        'openai_model': 'custom-model',
        'openai_api_key': 'test-key-12345',
        'openai_base_url': 'http://localhost:8000',
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })

@pytest.fixture
def local_llm_settings():
    """Create test settings for local LLM"""
    return Settings.from_dict({
        'openai_provider': 'llamacpp',
        'openai_model': '/path/to/model.gguf',
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
            similar_logs=[sample_logs[0]],  # Only one log, so count should be 1
            count=1
        ),
        LogCluster(
            representative_log=sample_logs[2],
            similar_logs=[sample_logs[2]],  # Only one log, so count should be 1
            count=1
        )
    ]

@pytest.fixture
def mock_langchain_response():
    """Create mock LangChain response"""
    mock_response = Mock()
    mock_response.content = "Test response"
    mock_response.response_metadata = {
        'token_usage': {'total_tokens': 100}
    }
    return mock_response

def test_initialization_success(llm_settings):
    """Test successful LLM client initialization with ChatOpenAI"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        client = LLMClient(llm_settings)

        assert client.settings == llm_settings
        assert client.model_name == 'gpt-4o-mini'
        mock_chat_openai.assert_called_once_with(
            model='gpt-4o-mini',
            api_key='test-key-12345',
            base_url='https://openrouter.ai/api/v1',
            temperature=0.1,
            max_tokens=2000
        )

def test_initialization_custom_endpoint(custom_endpoint_settings):
    """Test LLM client initialization with custom endpoint"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        client = LLMClient(custom_endpoint_settings)

        assert client.settings == custom_endpoint_settings
        assert client.model_name == 'custom-model'
        mock_chat_openai.assert_called_once_with(
            model='custom-model',
            api_key='test-key-12345',
            base_url='http://localhost:8000',
            temperature=0.1,
            max_tokens=2000
        )

def test_initialization_local_llm(local_llm_settings):
    """Test LLM client initialization with local LLM (LlamaCpp)"""
    with patch('analyzer.llm.client.LlamaCpp') as mock_llama_cpp:
        client = LLMClient(local_llm_settings)

        assert client.settings == local_llm_settings
        assert client.model_name == '/path/to/model.gguf'
        mock_llama_cpp.assert_called_once_with(
            model_path='/path/to/model.gguf',
            temperature=0.1,
            max_tokens=2000,
            verbose=False
        )

def test_initialization_missing_key():
    """Test OpenAI provider initialization without API key"""
    settings = Settings.from_dict({
        'openai_provider': 'openai',
        'openai_model': 'gpt-4o-mini',
        'openai_api_key': 'temp-key',
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })

    settings.openai_api_key = None

    with pytest.raises(LLMError, match="OPENAI_API_KEY is required for OpenAI provider"):
        LLMClient(settings)

def test_initialization_unsupported_provider():
    """Test LLM initialization with unsupported provider"""
    settings = Settings.from_dict({
        'openai_provider': 'openai',
        'openai_model': 'gpt-4o-mini',
        'openai_api_key': 'test-key',
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })

    settings.openai_provider = 'unsupported'

    with pytest.raises(LLMError, match="Unsupported OpenAI provider: unsupported"):
        LLMClient(settings)

def test_initialization_llamacpp_no_key(local_llm_settings):
    """Test LlamaCpp provider initialization without API key (should work)"""
    with patch('analyzer.llm.client.LlamaCpp') as mock_llama_cpp:
        client = LLMClient(local_llm_settings)

        assert client.settings == local_llm_settings
        assert client.model_name == '/path/to/model.gguf'
        mock_llama_cpp.assert_called_once_with(
            model_path='/path/to/model.gguf',
            temperature=0.1,
            max_tokens=2000,
            verbose=False
        )

def test_call_llm_success(llm_settings, mock_langchain_response):
    """Test successful LLM call"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_llm.invoke.return_value = mock_langchain_response
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        response = client.call_llm("Test prompt")

        assert isinstance(response, LLMResponse)
        assert response.content == "Test response"
        assert response.tokens_used == 100
        assert response.model_name == 'gpt-4o-mini'
        assert response.response_time > 0

        mock_llm.invoke.assert_called_once()

def test_call_llm_empty_response(llm_settings):
    """Test LLM call with empty response"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = None
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)

        with pytest.raises(LLMResponseError, match="Empty response from LLM"):
            client.call_llm("Test prompt")

def test_call_llm_connection_error(llm_settings):
    """Test LLM call with connection error"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("Connection timeout")
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)

        with pytest.raises(LLMConnectionError, match="Failed to connect to LLM"):
            client.call_llm("Test prompt")

def test_call_llm_general_error(llm_settings):
    """Test LLM call with general error"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("API rate limit")
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)

        with pytest.raises(LLMResponseError, match="LLM response error"):
            client.call_llm("Test prompt")

def test_health_check_success(llm_settings, mock_langchain_response):
    """Test successful health check"""
    mock_langchain_response.content = "OK"

    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_llm.invoke.return_value = mock_langchain_response
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        result = client.health_check()

        assert result is True

def test_health_check_failure(llm_settings):
    """Test health check failure"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("Connection failed")
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        result = client.health_check()

        assert result is False

def test_analyze_single_cluster_success(llm_settings, sample_clusters):
    """Test successful single cluster analysis"""
    cluster = sample_clusters[0]

    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()

        # Mock the response content to be valid JSON matching ClusterAnalysis schema
        analysis_json = json.dumps({
            "severity": "high",
            "reasoning": "Database connection failures affecting multiple services",
            "impact_assessment": "High impact on application availability"
        })

        mock_response = Mock()
        mock_response.content = analysis_json
        mock_response.response_metadata = {}
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        analysis = client.analyze_single_cluster(cluster)

        assert isinstance(analysis, ClusterAnalysis)
        assert analysis.severity == "high"
        assert analysis.get_severity_enum() == SeverityLevel.HIGH
        assert analysis.reasoning == "Database connection failures affecting multiple services"
        assert analysis.impact_assessment == "High impact on application availability"

def test_analyze_single_cluster_parse_error(llm_settings, sample_clusters):
    """Test single cluster analysis with parse error"""
    cluster = sample_clusters[0]

    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Invalid JSON{"
        mock_response.response_metadata = {}
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)

        # Should raise an exception on parse error
        with pytest.raises(Exception):
            client.analyze_single_cluster(cluster)

def test_analyze_clusters_concurrent(llm_settings, sample_clusters):
    """Test concurrent cluster analysis"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()

        # Mock successful responses for each cluster
        def mock_invoke(messages):
            mock_response = Mock()
            mock_response.content = json.dumps({
                "severity": "high",
                "reasoning": "Moderate severity issue",
                "impact_assessment": "Medium impact"
            })
            mock_response.response_metadata = {}
            return mock_response

        mock_llm.invoke.side_effect = mock_invoke
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        client.analyze_clusters(sample_clusters, max_workers=2)

        # Check that both clusters were analyzed
        for cluster in sample_clusters:
            assert cluster.severity == SeverityLevel.HIGH
            assert cluster.reasoning == "Moderate severity issue"

def test_analyze_clusters_empty_input(llm_settings):
    """Test cluster analysis with empty input"""
    with patch('analyzer.llm.client.ChatOpenAI'):
        client = LLMClient(llm_settings)
        client.analyze_clusters([])
        # Should complete without error

def test_rank_severity_success(llm_settings, sample_clusters):
    """Test successful severity ranking"""
    ranking_response = {"severity_levels": ["high", "medium"]}

    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps(ranking_response)
        mock_response.response_metadata = {}
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        scores = client.rank_severity(sample_clusters)

        assert scores == [SeverityLevel.HIGH, SeverityLevel.MEDIUM]

def test_rank_severity_insufficient_scores(llm_settings, sample_clusters):
    """Test severity ranking with insufficient scores"""
    ranking_response = {"severity_levels": ["high"]}  # Only one level for two clusters

    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps(ranking_response)
        mock_response.response_metadata = {}
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        # Should return default rankings on error
        scores = client.rank_severity(sample_clusters)
        assert scores == [SeverityLevel.MEDIUM, SeverityLevel.MEDIUM]

def test_rank_severity_empty_input(llm_settings):
    """Test severity ranking with empty input"""
    with patch('analyzer.llm.client.ChatOpenAI'):
        client = LLMClient(llm_settings)
        scores = client.rank_severity([])

        assert scores == []

def test_generate_daily_summary_success(llm_settings, sample_logs):
    """Test successful daily summary generation with structured output"""
    summary_response = {
        "summary": "System experiencing elevated error rates with database connectivity issues as primary concern.",
        "key_issues": ["Database connection failures", "High memory usage in worker services"],
        "recommendations": ["Investigate database connectivity", "Monitor memory usage trends"]
    }

    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = json.dumps(summary_response)
        mock_response.response_metadata = {}
        mock_llm.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm

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
        assert "database connectivity issues" in result.lower()
        assert "Key Issues:" in result
        assert "Recommendations:" in result

def test_generate_daily_summary_parse_error_fallback(llm_settings):
    """Test daily summary with parse error fallback"""
    with patch('analyzer.llm.client.ChatOpenAI') as mock_chat_openai:
        mock_llm = Mock()

        # First call returns invalid JSON, second call should return simple text
        responses = [
            Mock(content="Invalid JSON{", response_metadata={}),
            Mock(content="System is operating normally with minor issues detected.", response_metadata={})
        ]

        mock_llm.invoke.side_effect = responses
        mock_chat_openai.return_value = mock_llm

        client = LLMClient(llm_settings)
        result = client.generate_daily_summary(1000, 50, 100, [])

        assert isinstance(result, str)
        assert len(result) > 10
        assert "operating normally" in result

def test_cluster_analysis_pydantic_model():
    """Test ClusterAnalysis Pydantic model"""
    analysis = ClusterAnalysis(
        severity="high",
        reasoning="Database connection issue",
        impact_assessment="High impact on availability"
    )

    assert analysis.severity == "high"
    assert analysis.get_severity_enum() == SeverityLevel.HIGH
    assert analysis.reasoning == "Database connection issue"
    assert analysis.impact_assessment == "High impact on availability"

def test_severity_ranking_pydantic_model():
    """Test SeverityRanking Pydantic model"""
    ranking = SeverityRanking(severity_levels=["high", "medium", "critical", "low"])

    assert ranking.severity_levels == ["high", "medium", "critical", "low"]
    severity_enums = ranking.get_severity_enums()
    assert severity_enums == [SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.CRITICAL, SeverityLevel.LOW]

def test_severity_enum_conversion_with_invalid_values():
    """Test enum conversion with invalid severity values"""
    # Test ClusterAnalysis with invalid severity
    analysis = ClusterAnalysis(
        severity="invalid",
        reasoning="Test reasoning",
        impact_assessment="Test impact"
    )
    assert analysis.get_severity_enum() == SeverityLevel.MEDIUM  # Should default to MEDIUM

    # Test SeverityRanking with mixed valid/invalid values
    ranking = SeverityRanking(severity_levels=["high", "invalid", "critical", "bad"])
    severity_enums = ranking.get_severity_enums()
    assert severity_enums == [SeverityLevel.HIGH, SeverityLevel.MEDIUM, SeverityLevel.CRITICAL, SeverityLevel.MEDIUM]

def test_daily_summary_pydantic_model():
    """Test DailySummary Pydantic model"""
    summary = DailySummary(
        summary="System is stable",
        key_issues=["Minor database latency"],
        recommendations=["Monitor database performance"]
    )

    assert summary.summary == "System is stable"
    assert summary.key_issues == ["Minor database latency"]
    assert summary.recommendations == ["Monitor database performance"]

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

def test_openai_standard_configuration():
    """Test OpenAI standard configuration"""
    settings = Settings.from_dict({
        'openai_provider': 'openai',
        'openai_model': 'gpt-4-turbo',
        'openai_api_key': 'test-openai-key',
        'openai_base_url': 'https://api.openai.com/v1',
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })

    assert settings.openai_provider == 'openai'
    assert settings.openai_model == 'gpt-4-turbo'
    assert settings.openai_api_key == 'test-openai-key'
    assert settings.openai_base_url == 'https://api.openai.com/v1'

def test_llamacpp_configuration():
    """Test LlamaCpp configuration with OpenAI standard naming"""
    settings = Settings.from_dict({
        'openai_provider': 'llamacpp',
        'openai_model': '/path/to/model.gguf',
        'openai_api_key': None,  # Explicitly set to None for llamacpp
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs'
    })

    assert settings.openai_provider == 'llamacpp'
    assert settings.openai_model == '/path/to/model.gguf'
    assert settings.openai_api_key is None  # Not required for llamacpp