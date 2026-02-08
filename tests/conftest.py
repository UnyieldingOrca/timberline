"""Shared test fixtures."""

import pytest

from timberline.config import Settings


@pytest.fixture
def settings(tmp_path):
    """Settings with a temporary knowledge base path."""
    return Settings(
        loki_url="http://localhost:3100",
        knowledge_base_path=tmp_path / "kb",
        llm_model="test-model",
    )
