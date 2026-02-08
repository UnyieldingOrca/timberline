"""Settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "TIMBERLINE_", "env_file": ".env", "extra": "ignore"}

    # Loki
    loki_url: str = "http://localhost:3100"
    loki_org_id: str | None = None

    # LLM (via OpenRouter)
    llm_model: str = "moonshotai/kimi-k2.5"

    # Knowledge base
    knowledge_base_path: Path = Path("./knowledge_base")

    # Agent
    max_agent_turns: int = 50
    log_level: str = "INFO"
