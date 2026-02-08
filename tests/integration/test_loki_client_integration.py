"""Integration tests for LokiClient against a real Loki instance."""

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_ready(loki_client):
    assert await loki_client.ready() is True


@pytest.mark.asyncio
async def test_labels_contain_app(loki_client):
    labels = await loki_client.labels()
    assert isinstance(labels, list)
    assert "app" in labels


@pytest.mark.asyncio
async def test_labels_contain_namespace(loki_client):
    labels = await loki_client.labels()
    assert "namespace" in labels


@pytest.mark.asyncio
async def test_label_values_app(loki_client):
    values = await loki_client.label_values("app")
    assert "log-generator" in values


@pytest.mark.asyncio
async def test_query_range_returns_results(loki_client):
    result = await loki_client.query_range('{app="log-generator"}', limit=5)
    assert result["status"] == "success"
    assert len(result["data"]["result"]) > 0


@pytest.mark.asyncio
async def test_query_range_log_lines_are_json(loki_client):
    result = await loki_client.query_range('{app="log-generator"}', limit=5)
    stream = result["data"]["result"][0]
    # Each value entry is [timestamp, log_line]
    log_line = stream["values"][0][1]
    import json
    parsed = json.loads(log_line)
    assert "level" in parsed
    assert "service" in parsed


@pytest.mark.asyncio
async def test_query_range_with_filter(loki_client):
    # Should not error even if no ERROR lines exist
    result = await loki_client.query_range('{app="log-generator"} |= "ERROR"', limit=5)
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_series(loki_client):
    series = await loki_client.series(match=['{app="log-generator"}'])
    assert isinstance(series, list)
    assert len(series) > 0
    assert "app" in series[0]


@pytest.mark.asyncio
async def test_stats(loki_client):
    stats = await loki_client.stats(query='{app="log-generator"}')
    # Stats endpoint returns stream/byte/entry counts; just verify the shape
    assert "streams" in stats
    assert "bytes" in stats
    assert "entries" in stats


@pytest.mark.asyncio
async def test_volume_range(loki_client):
    volume = await loki_client.volume_range(query='{app="log-generator"}')
    assert volume["status"] == "success"


# -- Relative duration tests (the core bug fix) --


@pytest.mark.asyncio
async def test_labels_with_relative_start(loki_client):
    labels = await loki_client.labels(start="24h")
    assert isinstance(labels, list)
    assert len(labels) > 0


@pytest.mark.asyncio
async def test_label_values_with_relative_start(loki_client):
    values = await loki_client.label_values("app", start="24h")
    assert isinstance(values, list)


@pytest.mark.asyncio
async def test_query_range_with_relative_start(loki_client):
    result = await loki_client.query_range('{app="log-generator"}', start="1h", limit=5)
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_stats_with_relative_start(loki_client):
    stats = await loki_client.stats(query='{app="log-generator"}', start="24h")
    assert "streams" in stats


@pytest.mark.asyncio
async def test_series_with_relative_start(loki_client):
    series = await loki_client.series(match=['{app="log-generator"}'], start="24h")
    assert isinstance(series, list)
