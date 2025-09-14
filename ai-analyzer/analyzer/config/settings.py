import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # Database Connection
    milvus_host: str = os.getenv('MILVUS_HOST', 'milvus')
    milvus_port: int = int(os.getenv('MILVUS_PORT', '19530'))
    milvus_collection: str = os.getenv('MILVUS_COLLECTION', 'timberline_logs')

    # Analysis Settings
    analysis_window_hours: int = int(os.getenv('ANALYSIS_WINDOW_HOURS', '24'))
    max_logs_per_analysis: int = int(os.getenv('MAX_LOGS_PER_ANALYSIS', '10000'))
    cluster_batch_size: int = int(os.getenv('CLUSTER_BATCH_SIZE', '50'))

    # LLM Configuration (Required)
    llm_provider: str = os.getenv('LLM_PROVIDER', 'openai')
    llm_endpoint: Optional[str] = os.getenv('LLM_ENDPOINT')
    llm_model: str = os.getenv('LLM_MODEL', 'gpt-4o-mini')
    llm_api_key: Optional[str] = os.getenv('LLM_API_KEY')

    # Reporting
    report_output_dir: str = os.getenv('REPORT_OUTPUT_DIR', '/app/reports')
    webhook_url: Optional[str] = os.getenv('WEBHOOK_URL')

    @classmethod
    def from_cli_overrides(cls, cli_overrides: Dict[str, Any]) -> 'Settings':
        """Create Settings instance with CLI parameter overrides"""
        # Start with default instance
        settings = cls()

        # Apply CLI overrides
        override_mapping = {
            'milvus-host': 'milvus_host',
            'milvus-port': 'milvus_port',
            'milvus-collection': 'milvus_collection',
            'llm-provider': 'llm_provider',
            'llm-model': 'llm_model',
            'llm-api-key': 'llm_api_key',
            'llm-endpoint': 'llm_endpoint',
            'report-output-dir': 'report_output_dir',
            'max-logs': 'max_logs_per_analysis'
        }

        for cli_key, attr_name in override_mapping.items():
            if cli_key in cli_overrides:
                setattr(settings, attr_name, cli_overrides[cli_key])

        settings.validate()
        return settings

    def validate(self) -> None:
        """Validate required configuration"""
        if self.llm_provider in ['openai', 'anthropic'] and not self.llm_api_key:
            raise ValueError(f"LLM_API_KEY required for provider: {self.llm_provider}")

        if self.llm_provider == 'local' and not self.llm_endpoint:
            raise ValueError("LLM_ENDPOINT required for local provider")