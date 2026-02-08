"""Tests for the KnowledgeStore."""

import pytest

from timberline.knowledge.store import KnowledgeStore


@pytest.fixture
def store(tmp_path):
    return KnowledgeStore(tmp_path)


def test_write_and_read(store, tmp_path):
    store.write("test.md", "hello world")
    assert store.read("test.md") == "hello world"


def test_write_creates_dirs(store, tmp_path):
    store.write("a/b/c.md", "nested")
    assert store.read("a/b/c.md") == "nested"


def test_append(store):
    store.write("log.txt", "line1\n")
    store.write("log.txt", "line2\n", append=True)
    assert store.read("log.txt") == "line1\nline2\n"


def test_read_not_found(store):
    with pytest.raises(FileNotFoundError):
        store.read("missing.txt")


def test_path_traversal_blocked(store):
    with pytest.raises(ValueError, match="traversal"):
        store.read("../../etc/passwd")


def test_path_traversal_write_blocked(store):
    with pytest.raises(ValueError, match="traversal"):
        store.write("../../evil.txt", "pwned")


def test_list_files(store):
    store.write("a/x.md", "x")
    store.write("a/y.txt", "y")
    store.write("b/z.md", "z")
    files = store.list_files()
    assert len(files) == 3
    assert "a/x.md" in files


def test_list_files_pattern(store):
    store.write("a.md", "a")
    store.write("b.txt", "b")
    files = store.list_files(pattern="*.md")
    assert files == ["a.md"]


def test_search(store):
    store.write("notes.md", "The error code was 500\nAll clear now")
    store.write("other.md", "No errors here")
    matches = store.search("error")
    assert len(matches) == 2
    assert matches[0]["file"] == "notes.md"
    assert matches[0]["line"] == 1


def test_search_case_insensitive(store):
    store.write("file.md", "ERROR occurred")
    matches = store.search("error")
    assert len(matches) == 1


def test_exists(store):
    store.write("exists.md", "yes")
    assert store.exists("exists.md") is True
    assert store.exists("nope.md") is False
    assert store.exists("../../etc/passwd") is False
