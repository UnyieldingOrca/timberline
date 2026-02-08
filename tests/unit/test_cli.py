"""Tests for the CLI."""

import pytest
from click.testing import CliRunner

from timberline.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


def test_help(runner):
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "Timberline" in result.output


def test_analyze_help(runner):
    result = runner.invoke(cli, ["analyze", "--help"])
    assert result.exit_code == 0
    assert "--since" in result.output


def test_health_help(runner):
    result = runner.invoke(cli, ["health", "--help"])
    assert result.exit_code == 0


def test_kb_list_empty(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("TIMBERLINE_KNOWLEDGE_BASE_PATH", str(tmp_path / "kb"))
    result = runner.invoke(cli, ["kb", "list"])
    assert result.exit_code == 0
    assert "empty" in result.output.lower()


def test_kb_view_missing(runner, tmp_path, monkeypatch):
    monkeypatch.setenv("TIMBERLINE_KNOWLEDGE_BASE_PATH", str(tmp_path / "kb"))
    (tmp_path / "kb").mkdir()
    result = runner.invoke(cli, ["kb", "view", "nope.md"])
    assert result.exit_code == 1


def test_kb_clear_no_confirm(runner):
    result = runner.invoke(cli, ["kb", "clear"])
    assert result.exit_code == 0
    assert "--confirm" in result.output
