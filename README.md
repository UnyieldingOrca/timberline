# Timberline

Agentic log analysis for Loki.

Timberline connects to an existing [Loki](https://grafana.com/oss/loki/) instance and uses a [LangGraph](https://langchain-ai.github.io/langgraph/) ReAct agent to autonomously query logs, find issues, and build a persistent knowledge base over time. No web UI, no database -- just a CLI tool that reasons about your logs.

## How It Works

```
                    ┌──────────────────────┐
                    │     LLM Agent        │
                    │  (Anthropic / OpenAI)│
                    └──────┬───────────────┘
                           │
                    ┌──────▼───────────────┐
                    │    Tool Registry     │
                    │   (10 tools total)   │
                    └──┬───────────────┬───┘
                       │               │
              ┌────────▼──────┐ ┌──────▼────────┐
              │  Loki Tools   │ │  KB Tools     │
              │  (6 tools)    │ │  (4 tools)    │
              └────────┬──────┘ └──────┬────────┘
                       │               │
              ┌────────▼──────┐ ┌──────▼────────┐
              │  Loki API     │ │  Filesystem   │
              │  (httpx)      │ │  Knowledge    │
              └───────────────┘ └───────────────┘
```

The agent:
1. Checks its knowledge base for prior context
2. Surveys the Loki landscape (labels, volumes)
3. Triages errors and warnings across namespaces
4. Deep dives into significant issues
5. Compares against known patterns
6. Writes findings and updates the knowledge base

## Quick Start

```bash
# Install
pip install -e ".[all]"

# Configure
cp .env.example .env
# Edit .env with your Loki URL and API key

# Check connectivity
timberline health

# Run analysis
timberline analyze --since 1h
```

## CLI

```bash
timberline analyze              # Analyze logs from the last 24h
timberline analyze --since 1h   # Last hour
timberline analyze --namespace prod

timberline health               # Check Loki connectivity

timberline kb list              # List knowledge base files
timberline kb view findings/2026-02-07.md
timberline kb clear --confirm   # Clear knowledge base
```

## Configuration

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `TIMBERLINE_LOKI_URL` | `http://localhost:3100` | Loki base URL |
| `TIMBERLINE_LOKI_ORG_ID` | | Multi-tenant org ID |
| `TIMBERLINE_LLM_MODEL` | `anthropic/claude-sonnet-4` | OpenRouter model ID |
| `OPENROUTER_API_KEY` | | OpenRouter API key |
| `TIMBERLINE_KNOWLEDGE_BASE_PATH` | `./knowledge_base` | KB directory |
| `TIMBERLINE_MAX_AGENT_TURNS` | `50` | Max agent loop iterations |

See `.env.example` for the full list.

## Agent Tools

**Loki tools** -- query and explore your log data:
- `query_logs` -- Execute LogQL queries with time range and filters
- `get_labels` -- List available label names
- `get_label_values` -- Get values for a specific label
- `get_series` -- Find active log streams matching selectors
- `get_log_volume` -- Volume statistics over time
- `get_log_stats` -- Index-level statistics (stream count, bytes, entries)

**Knowledge base tools** -- persistent memory across runs:
- `read_knowledge` -- Read a file from the knowledge base
- `write_knowledge` -- Write or append to a knowledge base file
- `list_knowledge` -- List files with glob support
- `search_knowledge` -- Grep the knowledge base for a string

## Knowledge Base

The agent builds a persistent knowledge base on the filesystem:

```
knowledge_base/
├── findings/     # Per-run analysis (2026-02-07.md, etc.)
├── patterns/     # Recurring error patterns and signatures
├── services/     # Per-service learned context
├── config/       # Discovered namespaces, labels, thresholds
└── meta/         # Run metadata (last-run.json)
```

Each run builds on prior knowledge, allowing the agent to track trends and compare against known patterns.

## Development

```bash
pip install -e ".[all]"    # Install with all dependencies

just dev                   # Format + lint + test
just test                  # Run tests only
just lint                  # Run ruff
just fmt                   # Run black + ruff fix
```

### Local Loki Environment

A Kind cluster with Loki and a log generator for local development:

```bash
just kind-up      # Create cluster with Loki + Promtail + log generator
just kind-logs    # Verify Loki has data
just kind-down    # Tear down
```

This deploys Loki (single-binary mode) on port 3100, Promtail for log collection, and a busybox-based log generator that emits structured JSON logs simulating multiple microservices.

### Project Structure

```
timberline/
├── timberline/               # Main package
│   ├── config.py             # Settings (pydantic-settings)
│   ├── cli.py                # Click CLI
│   ├── agent.py              # LangGraph ReAct agent
│   ├── loki/client.py        # Async httpx Loki client
│   ├── tools/                # Tool layer
│   │   ├── base.py           # ToolResult, ToolDefinition, ToolRegistry
│   │   ├── loki_tools.py     # 6 Loki tools
│   │   └── knowledge_tools.py # 4 KB tools
│   ├── knowledge/store.py    # Filesystem knowledge store
│   └── prompts/system.py     # System prompt builder
├── tests/                    # 46 tests
├── dev/                      # Kind + Loki dev environment
└── knowledge_base/           # Default KB directory
```

## License

This project is licensed under the MIT License -- see the [LICENSE](LICENSE) file for details.
