"""Tests for Loki tools."""

import json

import httpx
import pytest
import respx

from timberline.loki.client import LokiClient
from timberline.tools.loki_tools import build_loki_tools


@pytest.fixture
def loki():
    return LokiClient(base_url="http://loki-test:3100")


@pytest.fixture
def tools(loki):
    return build_loki_tools(loki)


def _tool_by_name(tools, name):
    return next(t for t in tools if t.__name__ == name)


def test_build_loki_tools_count(tools):
    assert len(tools) == 6


def test_tool_names(tools):
    names = {t.__name__ for t in tools}
    assert names == {"query_logs", "get_labels", "get_label_values", "get_series", "get_log_volume", "get_log_stats"}


@respx.mock
@pytest.mark.asyncio
async def test_query_logs(tools):
    payload = {"status": "success", "data": {"result": []}}
    respx.get("http://loki-test:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(200, json=payload)
    )
    query_logs = _tool_by_name(tools, "query_logs")
    result = await query_logs(query='{app="test"}')
    assert "success" in result


@respx.mock
@pytest.mark.asyncio
async def test_query_logs_error(tools):
    respx.get("http://loki-test:3100/loki/api/v1/query_range").mock(
        return_value=httpx.Response(500, text="Internal error")
    )
    query_logs = _tool_by_name(tools, "query_logs")
    with pytest.raises(Exception):
        await query_logs(query='{app="test"}')


@respx.mock
@pytest.mark.asyncio
async def test_get_labels(tools):
    respx.get("http://loki-test:3100/loki/api/v1/labels").mock(
        return_value=httpx.Response(200, json={"data": ["app", "pod"]})
    )
    get_labels = _tool_by_name(tools, "get_labels")
    result = await get_labels()
    data = json.loads(result)
    assert "app" in data
