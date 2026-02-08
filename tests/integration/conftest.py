"""Integration test configuration and fixtures."""

import httpx
import pytest
import pytest_asyncio

from timberline.knowledge.store import KnowledgeStore
from timberline.loki.client import LokiClient

LOKI_URL = "http://localhost:3100"


def _loki_is_reachable() -> bool:
    """Check whether Loki is reachable at the expected URL."""
    try:
        resp = httpx.get(f"{LOKI_URL}/ready", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


_loki_available = _loki_is_reachable()


def pytest_collection_modifyitems(config, items):
    """Skip Loki-dependent tests when Loki is not reachable."""
    if _loki_available:
        return
    skip_loki = pytest.mark.skip(reason="Loki is not reachable")
    for item in items:
        if "loki" in item.nodeid:
            item.add_marker(skip_loki)


@pytest_asyncio.fixture
async def loki_client():
    """Async LokiClient connected to the local Kind cluster."""
    client = LokiClient(base_url=LOKI_URL)
    yield client
    await client.close()


@pytest.fixture
def knowledge_store(tmp_path):
    """KnowledgeStore backed by a temporary directory."""
    return KnowledgeStore(tmp_path)
