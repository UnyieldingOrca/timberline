"""Tests for the Loki HTTP client using respx mocking."""

import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from timberline.loki.client import LokiClient, _resolve_time


@pytest.fixture
def loki():
    return LokiClient(base_url="http://loki-test:3100")


@respx.mock
@pytest.mark.asyncio
async def test_ready_ok(loki):
    respx.get("http://loki-test:3100/ready").mock(return_value=httpx.Response(200, text="ready"))
    assert await loki.ready() is True


@respx.mock
@pytest.mark.asyncio
async def test_ready_not_ok(loki):
    respx.get("http://loki-test:3100/ready").mock(return_value=httpx.Response(503))
    assert await loki.ready() is False


@respx.mock
@pytest.mark.asyncio
async def test_query_range(loki):
    payload = {"status": "success", "data": {"result": [{"stream": {}, "values": [["1700000000", "test log"]]}]}}
    respx.get("http://loki-test:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await loki.query_range(query='{app="test"}')
    assert result["status"] == "success"
    assert len(result["data"]["result"]) == 1


@respx.mock
@pytest.mark.asyncio
async def test_labels(loki):
    respx.get("http://loki-test:3100/loki/api/v1/labels").mock(
        return_value=httpx.Response(200, json={"data": ["app", "namespace", "pod"]})
    )
    labels = await loki.labels()
    assert labels == ["app", "namespace", "pod"]


@respx.mock
@pytest.mark.asyncio
async def test_label_values(loki):
    respx.get("http://loki-test:3100/loki/api/v1/label/app/values").mock(
        return_value=httpx.Response(200, json={"data": ["nginx", "redis"]})
    )
    values = await loki.label_values("app")
    assert values == ["nginx", "redis"]


@respx.mock
@pytest.mark.asyncio
async def test_series(loki):
    respx.get("http://loki-test:3100/loki/api/v1/series").mock(
        return_value=httpx.Response(200, json={"data": [{"app": "nginx", "namespace": "prod"}]})
    )
    series = await loki.series(match=['{app="nginx"}'])
    assert series == [{"app": "nginx", "namespace": "prod"}]


@respx.mock
@pytest.mark.asyncio
async def test_volume_range(loki):
    payload = {"status": "success", "data": {"result": []}}
    respx.get("http://loki-test:3100/loki/api/v1/index/volume_range").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await loki.volume_range(query='{app="test"}')
    assert result["status"] == "success"


@respx.mock
@pytest.mark.asyncio
async def test_stats(loki):
    payload = {"streams": 5, "chunks": 100, "bytes": 1024, "entries": 500}
    respx.get("http://loki-test:3100/loki/api/v1/index/stats").mock(
        return_value=httpx.Response(200, json=payload)
    )
    result = await loki.stats(query='{app="test"}')
    assert result["streams"] == 5


@respx.mock
@pytest.mark.asyncio
async def test_org_id_header():
    client = LokiClient(base_url="http://loki-test:3100", org_id="tenant-1")
    route = respx.get("http://loki-test:3100/loki/api/v1/labels").mock(
        return_value=httpx.Response(200, json={"data": []})
    )
    await client.labels()
    assert route.calls[0].request.headers["X-Scope-OrgID"] == "tenant-1"


# -- _resolve_time tests --


class TestResolveTime:
    def test_none_returns_none(self):
        assert _resolve_time(None) is None

    def test_empty_string_returns_none(self):
        assert _resolve_time("") is None

    def test_hours(self):
        before = int((time.time() - 3600) * 1e9)
        result = int(_resolve_time("1h"))
        after = int((time.time() - 3600) * 1e9)
        assert before <= result <= after

    def test_days(self):
        before = int((time.time() - 86400) * 1e9)
        result = int(_resolve_time("1d"))
        after = int((time.time() - 86400) * 1e9)
        assert before <= result <= after

    def test_minutes(self):
        before = int((time.time() - 1800) * 1e9)
        result = int(_resolve_time("30m"))
        after = int((time.time() - 1800) * 1e9)
        assert before <= result <= after

    def test_weeks(self):
        before = int((time.time() - 604800) * 1e9)
        result = int(_resolve_time("1w"))
        after = int((time.time() - 604800) * 1e9)
        assert before <= result <= after

    def test_seconds(self):
        before = int((time.time() - 60) * 1e9)
        result = int(_resolve_time("60s"))
        after = int((time.time() - 60) * 1e9)
        assert before <= result <= after

    def test_rfc3339_passthrough(self):
        ts = "2024-01-01T00:00:00Z"
        assert _resolve_time(ts) == ts

    def test_epoch_passthrough(self):
        ts = "1700000000000000000"
        assert _resolve_time(ts) == ts

    def test_whitespace_stripped(self):
        result = _resolve_time("  1h  ")
        assert result is not None
        int(result)  # should be a valid integer string


# -- Verify relative durations reach Loki as nanosecond timestamps --


@respx.mock
@pytest.mark.asyncio
async def test_query_range_resolves_relative_start(loki):
    payload = {"status": "success", "data": {"result": []}}
    route = respx.get("http://loki-test:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json=payload)
    )
    await loki.query_range(query='{app="test"}', start="24h")
    sent_url = str(route.calls[0].request.url)
    params = parse_qs(urlparse(sent_url).query)
    start_val = params["start"][0]
    # Should be a nanosecond epoch, not "24h"
    assert start_val != "24h"
    int(start_val)  # must be a valid integer


@respx.mock
@pytest.mark.asyncio
async def test_labels_resolves_relative_start(loki):
    route = respx.get("http://loki-test:3100/loki/api/v1/labels").mock(
        return_value=httpx.Response(200, json={"data": ["app"]})
    )
    await loki.labels(start="1h")
    sent_url = str(route.calls[0].request.url)
    params = parse_qs(urlparse(sent_url).query)
    start_val = params["start"][0]
    assert start_val != "1h"
    int(start_val)


@respx.mock
@pytest.mark.asyncio
async def test_label_values_resolves_relative_start(loki):
    route = respx.get("http://loki-test:3100/loki/api/v1/label/app/values").mock(
        return_value=httpx.Response(200, json={"data": ["nginx"]})
    )
    await loki.label_values("app", start="12h")
    sent_url = str(route.calls[0].request.url)
    params = parse_qs(urlparse(sent_url).query)
    assert params["start"][0] != "12h"


@respx.mock
@pytest.mark.asyncio
async def test_stats_resolves_relative_start(loki):
    route = respx.get("http://loki-test:3100/loki/api/v1/index/stats").mock(
        return_value=httpx.Response(200, json={"streams": 1, "bytes": 0, "entries": 0})
    )
    await loki.stats(query='{app="test"}', start="7d")
    sent_url = str(route.calls[0].request.url)
    params = parse_qs(urlparse(sent_url).query)
    assert params["start"][0] != "7d"
