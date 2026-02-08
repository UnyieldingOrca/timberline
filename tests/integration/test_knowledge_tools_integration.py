"""Integration tests for knowledge base tool closures."""

import json

import pytest

from timberline.tools.knowledge_tools import build_knowledge_tools


pytestmark = pytest.mark.integration


@pytest.fixture
def kb_tools(knowledge_store):
    return build_knowledge_tools(knowledge_store)


def _tool_by_name(tools, name):
    return next(t for t in tools if t.__name__ == name)


@pytest.mark.asyncio
async def test_full_workflow(kb_tools):
    """Write findings/patterns/services, read back, list, and search across all."""
    write = _tool_by_name(kb_tools, "write_knowledge")
    read = _tool_by_name(kb_tools, "read_knowledge")
    list_kb = _tool_by_name(kb_tools, "list_knowledge")
    search = _tool_by_name(kb_tools, "search_knowledge")

    await write(path="findings/run1.md", content="Found OOM errors in payment-service")
    await write(path="patterns/oom.md", content="OOM pattern: container memory limit")
    await write(path="services/payment.md", content="payment-service: Java, 512Mi limit")

    assert "OOM" in await read(path="findings/run1.md")
    assert "OOM" in await read(path="patterns/oom.md")
    assert "payment" in await read(path="services/payment.md")

    listing = await list_kb()
    assert "findings/run1.md" in listing
    assert "patterns/oom.md" in listing
    assert "services/payment.md" in listing

    result = await search(text="OOM")
    matches = json.loads(result)
    files = {m["file"] for m in matches}
    assert "findings/run1.md" in files
    assert "patterns/oom.md" in files


@pytest.mark.asyncio
async def test_append(kb_tools):
    write = _tool_by_name(kb_tools, "write_knowledge")
    read = _tool_by_name(kb_tools, "read_knowledge")

    await write(path="log.md", content="line1\n")
    await write(path="log.md", content="line2\n", append=True)

    content = await read(path="log.md")
    assert "line1" in content
    assert "line2" in content


@pytest.mark.asyncio
async def test_list_with_directory_filter(kb_tools):
    write = _tool_by_name(kb_tools, "write_knowledge")
    list_kb = _tool_by_name(kb_tools, "list_knowledge")

    await write(path="findings/a.md", content="a")
    await write(path="patterns/b.md", content="b")

    result = await list_kb(directory="findings")
    assert "a.md" in result
    assert "b.md" not in result


@pytest.mark.asyncio
async def test_search_no_matches(kb_tools):
    write = _tool_by_name(kb_tools, "write_knowledge")
    search = _tool_by_name(kb_tools, "search_knowledge")

    await write(path="test.md", content="hello world")
    result = await search(text="zzz_nonexistent_zzz")
    assert result == "No matches found."


@pytest.mark.asyncio
async def test_read_nonexistent(kb_tools):
    read = _tool_by_name(kb_tools, "read_knowledge")
    result = await read(path="does/not/exist.md")
    assert result.startswith("Error:")


@pytest.mark.asyncio
async def test_path_traversal_blocked(kb_tools):
    read = _tool_by_name(kb_tools, "read_knowledge")
    result = await read(path="../../etc/passwd")
    assert "Error:" in result
    assert "traversal" in result
