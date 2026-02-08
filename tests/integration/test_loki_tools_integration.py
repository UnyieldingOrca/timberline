"""Integration tests for Loki tool closures against a real Loki instance."""

import json

import pytest

from timberline.tools.loki_tools import build_loki_tools


pytestmark = pytest.mark.integration


@pytest.fixture
def loki_tools(loki_client):
    return build_loki_tools(loki_client)


def _tool_by_name(tools, name):
    return next(t for t in tools if t.__name__ == name)


@pytest.mark.asyncio
async def test_query_logs_returns_json(loki_tools):
    query_logs = _tool_by_name(loki_tools, "query_logs")
    result = await query_logs(query='{app="log-generator"}', limit=5)
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_query_logs_bad_query(loki_tools):
    query_logs = _tool_by_name(loki_tools, "query_logs")
    result = await query_logs(query="not a valid query{{{")
    assert result.startswith("Error:")


@pytest.mark.asyncio
async def test_get_labels_contains_app(loki_tools):
    get_labels = _tool_by_name(loki_tools, "get_labels")
    result = await get_labels()
    labels = json.loads(result)
    assert "app" in labels


@pytest.mark.asyncio
async def test_get_label_values_app(loki_tools):
    get_label_values = _tool_by_name(loki_tools, "get_label_values")
    result = await get_label_values(label="app")
    values = json.loads(result)
    assert "log-generator" in values


@pytest.mark.asyncio
async def test_get_series(loki_tools):
    get_series = _tool_by_name(loki_tools, "get_series")
    result = await get_series(match=['{app="log-generator"}'])
    series = json.loads(result)
    assert isinstance(series, list)
    assert len(series) > 0


@pytest.mark.asyncio
async def test_get_log_stats(loki_tools):
    get_log_stats = _tool_by_name(loki_tools, "get_log_stats")
    result = await get_log_stats(query='{app="log-generator"}')
    stats = json.loads(result)
    assert "streams" in stats
    assert "bytes" in stats


@pytest.mark.asyncio
async def test_get_log_volume(loki_tools):
    get_log_volume = _tool_by_name(loki_tools, "get_log_volume")
    result = await get_log_volume(query='{app="log-generator"}')
    data = json.loads(result)
    assert data["status"] == "success"


# -- Relative duration tests (verify tools handle "24h" etc. without 400 errors) --


@pytest.mark.asyncio
async def test_query_logs_with_relative_start(loki_tools):
    query_logs = _tool_by_name(loki_tools, "query_logs")
    result = await query_logs(query='{app="log-generator"}', start="1h", limit=5)
    assert not result.startswith("Error:")
    data = json.loads(result)
    assert data["status"] == "success"


@pytest.mark.asyncio
async def test_get_labels_with_relative_start(loki_tools):
    get_labels = _tool_by_name(loki_tools, "get_labels")
    result = await get_labels(start="24h")
    assert not result.startswith("Error:")
    labels = json.loads(result)
    assert isinstance(labels, list)


@pytest.mark.asyncio
async def test_get_label_values_with_relative_start(loki_tools):
    get_label_values = _tool_by_name(loki_tools, "get_label_values")
    result = await get_label_values(label="app", start="24h")
    assert not result.startswith("Error:")


@pytest.mark.asyncio
async def test_get_log_stats_with_relative_start(loki_tools):
    get_log_stats = _tool_by_name(loki_tools, "get_log_stats")
    result = await get_log_stats(query='{app="log-generator"}', start="24h")
    assert not result.startswith("Error:")
    stats = json.loads(result)
    assert "streams" in stats
