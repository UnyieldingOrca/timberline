"""Tests for configuration."""

from pathlib import Path

from timberline.config import Settings


def test_defaults():
    s = Settings(loki_url="http://test:3100")
    assert s.loki_url == "http://test:3100"
    assert s.llm_model == "moonshotai/kimi-k2.5"
    assert s.max_agent_turns == 50
    assert s.log_level == "INFO"
    assert isinstance(s.knowledge_base_path, Path)
