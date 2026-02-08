"""Tests for the Loki HTTP client using respx mocking."""

import json

import httpx
import pytest
import respx

from timberline.loki.client import LokiClient


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
