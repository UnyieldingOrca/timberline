# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timberline is an agentic log analysis tool for Kubernetes environments. It connects to an existing **Loki** instance, uses a Deep Agent (via the `deepagents` SDK) to autonomously query and analyze logs, and builds a persistent filesystem knowledge base over time. CLI-only, no web UI or database.

## Architecture

```
Tools (async functions) → ToolRegistry → Deep Agent (deepagents SDK)
```

- **Tools** are plain `async` functions returning `ToolResult`. Dependencies (LokiClient, KnowledgeStore) are injected via `functools.partial`.
- **ToolRegistry** holds `ToolDefinition` objects with name, description, JSON Schema, and bound function.
- **Agent** (`timberline/agent.py`) converts tools to LangChain `StructuredTool` instances and runs a `create_deep_agent` from the `deepagents` SDK. LLM backend uses OpenRouter via `init_chat_model`.

## Development Commands

```bash
pip install -e ".[all]"     # Install with all dependencies
pip install -e ".[dev]"     # Install with dev dependencies only

just dev                    # Format, lint, test
just test                   # Run pytest
just lint                   # Run ruff
just fmt                    # Run black + ruff fix

timberline analyze --since 1h
timberline health           # Check Loki connectivity
timberline kb list          # List knowledge base files
timberline kb view <path>   # View a knowledge base file
timberline kb clear --confirm
```

### Kind + Loki Dev Environment

```bash
just kind-up    # Create Kind cluster with Loki + Promtail + log generator
just kind-down  # Delete Kind cluster
just kind-logs  # Check Loki has data (curl labels endpoint)
```

Deploys Loki (single-binary, filesystem storage) on port 3100 with Promtail collecting logs from a busybox log generator that emits structured JSON logs simulating multiple services.

## Configuration

Settings loaded from env vars (with `.env` support via `pydantic-settings`):

| Variable | Default | Description |
|----------|---------|-------------|
| `TIMBERLINE_LOKI_URL` | `http://localhost:3100` | Loki base URL |
| `TIMBERLINE_LOKI_ORG_ID` | (none) | Multi-tenant org ID |
| `TIMBERLINE_LLM_MODEL` | `anthropic/claude-sonnet-4` | OpenRouter model ID |
| `OPENROUTER_API_KEY` | (none) | OpenRouter API key |
| `TIMBERLINE_KNOWLEDGE_BASE_PATH` | `./knowledge_base` | KB directory |
| `TIMBERLINE_MAX_AGENT_TURNS` | `50` | Max agent loop iterations |
| `TIMBERLINE_LOG_LEVEL` | `INFO` | Log level |

## Project Structure

```
timberline/
├── pyproject.toml                # Python project config
├── justfile                      # dev, test, lint, fmt, kind-up/down
├── .env.example                  # Environment variable template
│
├── timberline/                   # Main package
│   ├── config.py                 # Settings (pydantic-settings)
│   ├── cli.py                    # Click CLI (analyze, health, kb)
│   ├── agent.py                  # Deep agent (run_agent, AnalysisResult)
│   ├── loki/
│   │   └── client.py             # Async httpx Loki API client
│   ├── tools/
│   │   ├── base.py               # ToolResult, ToolDefinition, ToolRegistry
│   │   ├── loki_tools.py         # 6 Loki tools + register_loki_tools()
│   │   └── knowledge_tools.py    # 4 KB tools + register_knowledge_tools()
│   ├── knowledge/
│   │   └── store.py              # KnowledgeStore (filesystem, path-safe)
│   └── prompts/
│       └── system.py             # System prompt builder
│
├── tests/                        # pytest test suite
│   ├── conftest.py               # Shared fixtures
│   ├── test_config.py
│   ├── test_agent.py             # Mocked deep agent tests
│   ├── test_loki_client.py       # respx-mocked Loki client tests
│   ├── test_loki_tools.py
│   ├── test_knowledge_store.py
│   ├── test_knowledge_tools.py
│   ├── test_tool_registry.py
│   └── test_cli.py
│
├── knowledge_base/               # Default KB directory (gitignored except README)
│   └── README.md
│
└── dev/                          # Kind + Loki dev environment
    ├── kind-cluster.yaml
    ├── loki/                     # Loki deployment manifests
    ├── promtail/                 # Promtail DaemonSet + RBAC
    └── log-generator/            # Busybox log generator deployment
```

## Agent Tools (10 total)

**Loki tools (6):** `query_logs`, `get_labels`, `get_label_values`, `get_series`, `get_log_volume`, `get_log_stats`

**Knowledge base tools (4):** `read_knowledge`, `write_knowledge`, `list_knowledge`, `search_knowledge`

## Key Implementation Details

### Tool Registration Pattern

Tools are registered with `functools.partial` to bind infrastructure dependencies:

```python
register_loki_tools(registry, loki_client)      # binds LokiClient
register_knowledge_tools(registry, kb_store)     # binds KnowledgeStore
```

The LLM-facing function signature only includes parameters the agent controls.

### Knowledge Base

Filesystem directory with path traversal protection (`KnowledgeStore._validate_path()`). Structure:
- `findings/` -- per-run analysis
- `patterns/` -- recurring error signatures
- `services/` -- per-service context
- `config/` -- discovered labels, thresholds
- `meta/` -- run metadata

### Agent

`timberline/agent.py` contains `run_agent()` which:
1. Builds an LLM via `init_chat_model` using OpenRouter's OpenAI-compatible API
2. Converts `ToolDefinition` objects to LangChain `StructuredTool` instances
3. Creates a deep agent via `create_deep_agent` from the `deepagents` SDK
4. Invokes it and returns an `AnalysisResult`

## Testing

```bash
pytest                    # Run all 46 tests
pytest tests/test_loki_client.py -v   # Specific test file
pytest --cov=timberline   # With coverage
```

Tests use:
- `respx` for HTTP mocking (Loki client tests)
- `tmp_path` for filesystem tests (knowledge store)
- `unittest.mock` for LLM/agent mocking (agent tests)
- `click.testing.CliRunner` for CLI tests

## Common Workflows

### Adding a New Tool

1. Add async function in `timberline/tools/loki_tools.py` or `knowledge_tools.py`
2. Register it in the `register_*_tools()` function with a `ToolDefinition`
3. Add tests
4. Run `just dev`
