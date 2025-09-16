import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Literal
from pathlib import Path
from dotenv import load_dotenv


def _get_default_settings() -> Dict[str, Any]:
    """Get default settings from environment variables"""
    load_dotenv()
    return {
        'milvus_host': os.getenv('MILVUS_HOST', 'milvus'),
        'milvus_port': int(os.getenv('MILVUS_PORT', '19530')),
        'milvus_collection': os.getenv('MILVUS_COLLECTION', 'timberline_logs'),
        'analysis_window_hours': int(os.getenv('ANALYSIS_WINDOW_HOURS', '24')),
        'max_logs_per_analysis': int(os.getenv('MAX_LOGS_PER_ANALYSIS', '10000')),
        'cluster_batch_size': int(os.getenv('CLUSTER_BATCH_SIZE', '50')),
        'llm_endpoint': os.getenv('LLM_ENDPOINT'),
        'llm_model': os.getenv('LLM_MODEL', 'gpt-4o-mini'),
        'llm_api_key': os.getenv('LLM_API_KEY'),
        'report_output_dir': os.getenv('REPORT_OUTPUT_DIR', '/app/reports'),
        'webhook_url': os.getenv('WEBHOOK_URL')
    }


@dataclass
class Settings:
    """Configuration settings for the AI Log Analyzer"""

    # Database Connection
    milvus_host: str = field(default_factory=lambda: _get_default_settings()['milvus_host'])
    milvus_port: int = field(default_factory=lambda: _get_default_settings()['milvus_port'])
    milvus_collection: str = field(default_factory=lambda: _get_default_settings()['milvus_collection'])

    # Analysis Settings
    analysis_window_hours: int = field(default_factory=lambda: _get_default_settings()['analysis_window_hours'])
    max_logs_per_analysis: int = field(default_factory=lambda: _get_default_settings()['max_logs_per_analysis'])
    cluster_batch_size: int = field(default_factory=lambda: _get_default_settings()['cluster_batch_size'])

    # LLM Configuration (OpenAI Compatible)
    llm_endpoint: Optional[str] = field(default_factory=lambda: _get_default_settings()['llm_endpoint'])
    llm_model: str = field(default_factory=lambda: _get_default_settings()['llm_model'])
    llm_api_key: Optional[str] = field(default_factory=lambda: _get_default_settings()['llm_api_key'])

    # Reporting
    report_output_dir: str = field(default_factory=lambda: _get_default_settings()['report_output_dir'])
    webhook_url: Optional[str] = field(default_factory=lambda: _get_default_settings()['webhook_url'])

    def __post_init__(self):
        """Validate settings after initialization"""
        self.validate()

    @classmethod
    def from_cli_overrides(cls, cli_overrides: Dict[str, Any]) -> 'Settings':
        """Create Settings instance with CLI parameter overrides"""
        # Start with default instance (validation disabled temporarily)
        settings = cls.__new__(cls)

        # Set defaults first from environment
        defaults = _get_default_settings()
        for key, value in defaults.items():
            setattr(settings, key, value)

        # Apply CLI overrides
        override_mapping = {
            'milvus-host': 'milvus_host',
            'milvus-port': 'milvus_port',
            'milvus-collection': 'milvus_collection',
            'llm-endpoint': 'llm_endpoint',
            'llm-model': 'llm_model',
            'llm-api-key': 'llm_api_key',
            'report-output-dir': 'report_output_dir',
            'max-logs': 'max_logs_per_analysis'
        }

        for cli_key, attr_name in override_mapping.items():
            if cli_key in cli_overrides:
                value = cli_overrides[cli_key]
                # Type conversion for numeric fields
                if attr_name in ['milvus_port', 'max_logs_per_analysis'] and isinstance(value, str):
                    value = int(value)
                setattr(settings, attr_name, value)

        # Validate after applying overrides
        settings.validate()
        return settings

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'Settings':
        """Create Settings from a dictionary"""
        settings = cls.__new__(cls)

        # Set all attributes with defaults
        defaults = _get_default_settings()
        settings.milvus_host = config_dict.get('milvus_host', defaults['milvus_host'])
        settings.milvus_port = config_dict.get('milvus_port', defaults['milvus_port'])
        settings.milvus_collection = config_dict.get('milvus_collection', defaults['milvus_collection'])
        settings.analysis_window_hours = config_dict.get('analysis_window_hours', defaults['analysis_window_hours'])
        settings.max_logs_per_analysis = config_dict.get('max_logs_per_analysis', defaults['max_logs_per_analysis'])
        settings.cluster_batch_size = config_dict.get('cluster_batch_size', defaults['cluster_batch_size'])
        settings.llm_endpoint = config_dict.get('llm_endpoint', defaults['llm_endpoint'])
        settings.llm_model = config_dict.get('llm_model', defaults['llm_model'])
        settings.llm_api_key = config_dict.get('llm_api_key', defaults['llm_api_key'])
        settings.report_output_dir = config_dict.get('report_output_dir', defaults['report_output_dir'])
        settings.webhook_url = config_dict.get('webhook_url', defaults['webhook_url'])

        settings.validate()
        return settings

    def validate(self) -> None:
        """Validate configuration settings"""
        # Validate Milvus settings
        if not self.milvus_host.strip():
            raise ValueError("Milvus host cannot be empty")

        if not (1 <= self.milvus_port <= 65535):
            raise ValueError("Milvus port must be between 1 and 65535")

        if not self.milvus_collection.strip():
            raise ValueError("Milvus collection name cannot be empty")

        # Validate analysis settings
        if self.analysis_window_hours <= 0:
            raise ValueError("Analysis window hours must be positive")

        if self.max_logs_per_analysis <= 0:
            raise ValueError("Max logs per analysis must be positive")

        if self.cluster_batch_size <= 0:
            raise ValueError("Cluster batch size must be positive")

        # Validate LLM settings
        if not self.llm_api_key:
            raise ValueError("LLM_API_KEY is required")

        if not self.llm_model.strip():
            raise ValueError("LLM model cannot be empty")

        # Validate reporting settings
        if not self.report_output_dir.strip():
            raise ValueError("Report output directory cannot be empty")

    @property
    def milvus_connection_string(self) -> str:
        """Get Milvus connection string"""
        return f"{self.milvus_host}:{self.milvus_port}"

    @property
    def report_output_path(self) -> Path:
        """Get report output directory as Path object"""
        return Path(self.report_output_dir)

    def ensure_output_directory(self) -> None:
        """Ensure the output directory exists"""
        self.report_output_path.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary"""
        return {
            'milvus_host': self.milvus_host,
            'milvus_port': self.milvus_port,
            'milvus_collection': self.milvus_collection,
            'analysis_window_hours': self.analysis_window_hours,
            'max_logs_per_analysis': self.max_logs_per_analysis,
            'cluster_batch_size': self.cluster_batch_size,
            'llm_endpoint': self.llm_endpoint,
            'llm_model': self.llm_model,
            'llm_api_key': '***' if self.llm_api_key else None,  # Mask API key
            'report_output_dir': self.report_output_dir,
            'webhook_url': self.webhook_url
        }

    def get_sanitized_dict(self) -> Dict[str, Any]:
        """Get dictionary with sensitive information removed"""
        config = self.to_dict()
        # Remove sensitive fields
        config['llm_api_key'] = None
        return config