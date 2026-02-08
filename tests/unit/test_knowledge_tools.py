"""Tests for knowledge base tools."""

import json

import pytest

from timberline.knowledge.store import KnowledgeStore
from timberline.tools.knowledge_tools import build_knowledge_tools


@pytest.fixture
def store(tmp_path):
    return KnowledgeStore(tmp_path)


@pytest.fixture
def tools(store):
    return build_knowledge_tools(store)


def _tool_by_name(tools, name):
    return next(t for t in tools if t.__name__ == name)


def test_build_knowledge_tools_count(tools):
    assert len(tools) == 4


@pytest.mark.asyncio
async def test_write_and_read(tools):
    write = _tool_by_name(tools, "write_knowledge")
    read = _tool_by_name(tools, "read_knowledge")

    result = await write(path="test.md", content="hello")
    assert "Wrote" in result

    result = await read(path="test.md")
    assert result == "hello"


@pytest.mark.asyncio
async def test_read_missing(tools):
    read = _tool_by_name(tools, "read_knowledge")
    result = await read(path="nope.md")
    assert result.startswith("Error:")


@pytest.mark.asyncio
async def test_list(tools, store):
    store.write("a.md", "a")
    store.write("b.md", "b")
    list_kb = _tool_by_name(tools, "list_knowledge")
    result = await list_kb()
    assert "a.md" in result


@pytest.mark.asyncio
async def test_search(tools, store):
    store.write("notes.md", "found an error in prod")
    search = _tool_by_name(tools, "search_knowledge")
    result = await search(text="error")
    data = json.loads(result)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_path_traversal(tools):
    read = _tool_by_name(tools, "read_knowledge")
    result = await read(path="../../etc/passwd")
    assert "Error:" in result
    assert "traversal" in result
