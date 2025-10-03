"""
Unit tests for the config.settings module
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from analyzer.config.settings import Settings


@pytest.fixture
def valid_settings_dict():
    """Create valid settings dictionary for testing"""
    return {
        'milvus_host': 'localhost',
        'milvus_port': 19530,
        'milvus_collection': 'test_logs',
        'analysis_window_hours': 12,
        'max_logs_per_analysis': 5000,
        'cluster_batch_size': 25,
        'openai_model': 'gpt-4',
        'openai_api_key': 'test-key',
        'llm_endpoint': None,
        'report_output_dir': '/tmp/reports',
        'webhook_url': 'https://hooks.example.com/webhook'
    }


def test_settings_from_environment():
    """Test settings loaded from environment variables"""
    env_vars = {
        'MILVUS_HOST': 'test-milvus',
        'MILVUS_PORT': '9999',
        'OPENAI_API_KEY': 'test-api-key'
    }
    with patch.dict(os.environ, env_vars, clear=True):
        settings = Settings()
        assert settings.milvus_host == 'test-milvus'
        assert settings.milvus_port == 9999
        assert settings.openai_api_key == 'test-api-key'


def test_settings_defaults():
    """Test settings with default values"""
    # Clear environment and set only what's needed to avoid picking up .env file
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_MODEL': 'gpt-4o-mini',  # Explicitly set to avoid .env override
        'OPENAI_PROVIDER': 'openai'
    }, clear=True):
        settings = Settings()
        assert settings.milvus_host == 'milvus'
        assert settings.milvus_port == 19530
        assert settings.milvus_collection == 'timberline_logs'
        assert settings.analysis_window_hours == 24
        assert settings.max_logs_per_analysis == 10000
        assert settings.cluster_batch_size == 50
        assert settings.openai_model == 'gpt-4o-mini'
        assert settings.report_output_dir == '/app/reports'


def test_from_dict_creation(valid_settings_dict):
    """Test creating settings from dictionary"""
    settings = Settings.from_dict(valid_settings_dict)
    assert settings.milvus_host == 'localhost'
    assert settings.milvus_port == 19530
    assert settings.openai_api_key == 'test-key'


def test_from_cli_overrides():
    """Test creating settings with CLI overrides"""
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'env-key'}, clear=True):
        cli_overrides = {
            'milvus-host': 'cli-host',
            'milvus-port': 9999,
            'openai-model': 'gpt-4'
        }
        settings = Settings.from_cli_overrides(cli_overrides)
        assert settings.milvus_host == 'cli-host'
        assert settings.milvus_port == 9999
        assert settings.openai_model == 'gpt-4'
        assert settings.openai_api_key == 'env-key'  # From environment


def test_validation_empty_milvus_host():
    """Test validation fails for empty Milvus host"""
    config = {'milvus_host': '', 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Milvus host cannot be empty"):
        Settings.from_dict(config)


def test_validation_invalid_milvus_port():
    """Test validation fails for invalid Milvus port"""
    config = {'milvus_port': 0, 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Milvus port must be between 1 and 65535"):
        Settings.from_dict(config)

    config = {'milvus_port': 70000, 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Milvus port must be between 1 and 65535"):
        Settings.from_dict(config)


def test_validation_empty_milvus_collection():
    """Test validation fails for empty Milvus collection"""
    config = {'milvus_collection': '', 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Milvus collection name cannot be empty"):
        Settings.from_dict(config)


def test_validation_negative_analysis_window():
    """Test validation fails for negative analysis window"""
    config = {'analysis_window_hours': -1, 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Analysis window hours must be positive"):
        Settings.from_dict(config)


def test_validation_negative_max_logs():
    """Test validation fails for negative max logs"""
    config = {'max_logs_per_analysis': -1, 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Max logs per analysis must be positive"):
        Settings.from_dict(config)


def test_validation_negative_cluster_batch_size():
    """Test validation fails for negative cluster batch size"""
    config = {'cluster_batch_size': -1, 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Cluster batch size must be positive"):
        Settings.from_dict(config)


def test_validation_missing_api_key():
    """Test validation fails for missing API key"""
    config = {'openai_api_key': None}
    with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
        Settings.from_dict(config)


def test_validation_empty_openai_model():
    """Test validation fails for empty OpenAI model"""
    config = {'openai_model': '', 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="OpenAI model cannot be empty"):
        Settings.from_dict(config)


def test_validation_empty_report_dir():
    """Test validation fails for empty report directory"""
    config = {'report_output_dir': '', 'openai_api_key': 'test-key'}
    with pytest.raises(ValueError, match="Report output directory cannot be empty"):
        Settings.from_dict(config)


def test_milvus_connection_string_property(valid_settings_dict):
    """Test Milvus connection string property"""
    settings = Settings.from_dict(valid_settings_dict)
    assert settings.milvus_connection_string == "localhost:19530"


def test_report_output_path_property(valid_settings_dict):
    """Test report output path property"""
    settings = Settings.from_dict(valid_settings_dict)
    assert settings.report_output_path == Path('/tmp/reports')


def test_ensure_output_directory():
    """Test output directory creation"""
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / 'test_reports'
        settings = Settings.from_dict({
            'report_output_dir': str(output_dir),
            'openai_api_key': 'test-key'
        })

        # Directory shouldn't exist initially
        assert not output_dir.exists()

        # Ensure directory creation
        settings.ensure_output_directory()
        assert output_dir.exists()
        assert output_dir.is_dir()


def test_to_dict(valid_settings_dict):
    """Test converting settings to dictionary"""
    settings = Settings.from_dict(valid_settings_dict)
    result = settings.to_dict()

    assert result['milvus_host'] == 'localhost'
    assert result['milvus_port'] == 19530
    assert result['openai_api_key'] == '***'  # Should be masked


def test_get_sanitized_dict(valid_settings_dict):
    """Test getting sanitized dictionary"""
    settings = Settings.from_dict(valid_settings_dict)
    result = settings.get_sanitized_dict()

    assert result['milvus_host'] == 'localhost'
    assert result['openai_api_key'] is None  # Should be None


def test_cli_overrides_type_conversion():
    """Test CLI overrides with type conversion"""
    with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}, clear=True):
        cli_overrides = {
            'milvus-port': '9999',  # String that should be converted to int
            'max-logs': '5000'      # String that should be converted to int
        }
        settings = Settings.from_cli_overrides(cli_overrides)
        assert settings.milvus_port == 9999  # Should be converted to int
        assert settings.max_logs_per_analysis == 5000  # Should be converted to int


def test_post_init_validation():
    """Test that __post_init__ calls validation"""
    with patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'OPENAI_PROVIDER': 'openai'
    }, clear=True):
        # This should work fine
        settings = Settings()
        assert settings.openai_api_key == 'test-key'

    # This should fail validation - empty API key for OpenAI provider
    with patch.dict(os.environ, {'OPENAI_PROVIDER': 'openai', 'OPENAI_API_KEY': ''}, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            Settings()