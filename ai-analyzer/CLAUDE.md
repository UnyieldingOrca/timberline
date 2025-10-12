# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the **AI Analyzer** component of Timberline - a Python-based service that performs LLM-powered analysis of Kubernetes logs stored in Milvus. It runs as both a CLI tool and a FastAPI service to provide daily analysis reports with actionable insights.

## Architecture

The AI Analyzer follows a pipeline architecture with several core components:

- **Analysis Engine** (`analyzer/analysis/engine.py`) - Orchestrates the daily analysis pipeline: queries logs from Milvus, clusters similar logs, sends clusters to LLM for analysis, calculates health scores, and generates reports
- **Storage Layer** (`analyzer/storage/`) - Interfaces with Milvus for log retrieval and analysis result storage
- **LLM Integration** (`analyzer/llm/client.py`) - Abstracts OpenAI-compatible LLM providers (OpenAI, local llama.cpp) for severity scoring and summarization
- **Report Generator** (`analyzer/reporting/generator.py`) - Creates JSON reports and sends webhook notifications
- **FastAPI Service** (`analyzer/api/`) - REST API with endpoints for log analysis and retrieving stored results
- **CLI Interface** (`analyzer/cli/main.py`) - Command-line tool for daily analysis, health checks, and report management
- **PostgreSQL Storage** (`analyzer/db/`) - Stores analysis results using SQLAlchemy with Alembic migrations

## Development Commands

### Running Tests
```bash
# Run all tests with coverage
pytest

# Run specific test file
pytest tests/test_analysis.py -v

# Run specific test function
pytest tests/test_analysis.py::test_analyze_daily_logs -v

# Run with verbose output and coverage report
pytest -v --cov=analyzer --cov-report=term-missing

# Generate HTML coverage report (outputs to htmlcov/)
pytest --cov=analyzer --cov-report=html
```

### Code Quality
```bash
# Format code with Black (line length: 100)
black analyzer/ tests/

# Lint with Ruff
ruff check analyzer/ tests/
```

### Running the Application

#### CLI Tool
```bash
# Install in development mode
pip install -e .

# Run daily analysis for yesterday
ai-analyzer analyze-daily

# Run analysis for specific date
ai-analyzer analyze-daily --date 2025-10-11

# Dry run to validate configuration
ai-analyzer analyze-daily --dry-run

# Health check all components
ai-analyzer health-check

# List recent reports
ai-analyzer list-reports --limit 10

# List stored analysis results from Milvus
ai-analyzer list-stored-results --limit 10

# Get specific analysis result by date
ai-analyzer get-stored-result 2025-10-11

# Clean up old reports
ai-analyzer cleanup-reports --days 30 --dry-run

# Show version
ai-analyzer version
```

#### FastAPI Service
```bash
# Run the API server
uvicorn analyzer.api.main:app --reload --host 0.0.0.0 --port 8000

# Or use the start script
./start-api.sh

# Access API docs at http://localhost:8000/docs
```

### Database Migrations
```bash
# Run migrations to upgrade database
alembic upgrade head

# Create a new migration (auto-generate from models)
alembic revision --autogenerate -m "description"

# Downgrade one version
alembic downgrade -1

# View migration history
alembic history
```

### Docker
```bash
# Build Docker image
docker build -t ai-analyzer:latest .

# Run as API service
docker run -p 8000:8000 ai-analyzer:latest

# Run CLI command
docker run ai-analyzer:latest ai-analyzer --help
```

## Configuration

Configuration is managed through environment variables and CLI overrides:

**Database Connection:**
- `MILVUS_HOST` - Milvus server host (default: milvus)
- `MILVUS_PORT` - Milvus server port (default: 19530)
- `MILVUS_COLLECTION` - Collection name (default: timberline_logs)
- `DATABASE_URL` - PostgreSQL connection string (default: postgresql://postgres:postgres@localhost:5432/timberline)

**Analysis Settings:**
- `ANALYSIS_WINDOW_HOURS` - Analysis time window (default: 24)
- `MAX_LOGS_PER_ANALYSIS` - Maximum logs to process (default: 10000)
- `CLUSTER_BATCH_SIZE` - Clustering batch size (default: 50)

**LLM Configuration (Required):**
- `OPENAI_PROVIDER` - Provider type: 'openai' or 'llamacpp' (default: openai)
- `OPENAI_BASE_URL` - Custom OpenAI-compatible endpoint (optional)
- `OPENAI_MODEL` - Model name (default: gpt-4o-mini)
- `OPENAI_API_KEY` - API key (required for OpenAI provider)

**Reporting:**
- `REPORT_OUTPUT_DIR` - Report output directory (default: /app/reports)
- `WEBHOOK_URL` - Optional webhook for notifications

CLI flags can override environment variables (e.g., `--milvus-host`, `--llm-model`, `--report-output-dir`).

## Key Design Patterns

### Settings Management
The `Settings` class supports three initialization methods:
- Default constructor (loads from environment)
- `from_cli_overrides()` - Merges environment with CLI flags
- `from_dict()` - Creates from configuration dictionary

### Analysis Pipeline
The daily analysis follows these steps:
1. Query logs from Milvus for the analysis window
2. Cluster similar logs by Kubernetes labels (app, version, tier)
3. Send representative logs to LLM for severity scoring (1-10 scale)
4. Calculate system health score (0-1 scale)
5. Generate LLM summary with actionable insights
6. Create JSON report and save to filesystem
7. Store results in both PostgreSQL and Milvus
8. Send webhook notification if configured

### Error Handling
- Custom exceptions: `AnalysisEngineError`, `MilvusConnectionError`, `ReportGeneratorError`, `AnalysisResultsStoreError`
- Retry logic for Milvus queries with exponential backoff
- Graceful degradation: report generation/storage failures don't fail the entire analysis

## Important Notes

- Do not generate Alembic migration scripts manually - use `alembic revision --autogenerate`
- The analysis engine modifies cluster objects in-place during LLM analysis
- Log records track `duplicate_count` for accurate statistics while reducing storage
- Health scores consider both error/warning counts and LLM severity assessments
- All timestamps are stored as Unix milliseconds in Milvus
- Reports are stored both as files (JSON) and in PostgreSQL/Milvus for querying

## Testing Strategy

All tests are unit tests using pytest with mocked dependencies. Tests are organized by component:
- `test_analysis.py` - Analysis engine and pipeline tests
- `test_storage.py` - Milvus client and query tests
- `test_llm.py` - LLM client integration tests
- `test_reporting.py` - Report generation tests
- `test_models.py` - Data model tests
- `test_config.py` - Settings and configuration tests
- `test_api_*.py` - FastAPI endpoint tests
- `test_analysis_results_store.py` - PostgreSQL storage tests

Use `conftest.py` fixtures for test setup (mock settings, clients, database sessions). Coverage reports are generated automatically and stored in `htmlcov/`.
