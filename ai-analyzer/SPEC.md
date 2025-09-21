# AI Log Analyzer - Component Specification (MVP)

## Overview

The AI Log Analyzer is a Python-based service that performs LLM-powered analysis of logs stored in the Milvus vector database to identify concerning, anomalous, and actionable log patterns. It runs as a daily Kubernetes CronJob to provide proactive insights for system health and operational improvements.

## Architecture

### Component Type
- **Language**: Python 3.11+
- **CronJob**: Kubernetes CronJob (daily scheduled only)
- **Dependencies**: Milvus, LLM endpoint (local llama.cpp or cloud provider)

### Resource Requirements
- **Memory**: 2-4 GiB (for LLM context processing)
- **CPU**: 1-2 cores
- **Storage**: 512 MiB for reports and temporary data
- **GPU**: Optional (recommended for local LLM inference)

## Core Responsibilities

### 1. Daily Log Analysis Pipeline
- Query last 24 hours of logs from Milvus vector database
- Group similar logs using Kubernetes label-based clustering
- Send log samples to LLM for analysis and severity ranking
- Generate structured reports with LLM-powered insights
- Output reports to file system or single webhook endpoint

## Data Flow

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Milvus    │───▶│ AI Analyzer  │───▶│ JSON Reports &  │
│  (Logs DB)  │    │   CronJob    │    │ Notifications   │
└─────────────┘    └──────────────┘    └─────────────────┘
                           │
                    ┌──────▼──────┐
                    │ LLM Service │
                    │ (Required)  │
                    └─────────────┘
```

## Technical Components

### 1. Log Retrieval and Clustering
**Purpose**: Interface with Milvus for log retrieval and intelligent grouping

**Key Features**:
- Time-range queries for daily analysis windows
- Log clustering using Kubernetes labels (app, version, tier, etc.)
- Batch processing for large log volumes

### 2. LLM Integration
**Purpose**: Core LLM integration for log analysis and severity ranking

**Capabilities**:
- Severity scoring (1-10 scale) for log patterns
- Natural language interpretation of error clusters
- Human-readable summaries and insights

**Supported LLM Providers**:
- **Local**: llama.cpp, Ollama
- **Cloud**: OpenAI GPT-4, Anthropic Claude

### 3. Analysis Engine
**Purpose**: Orchestrate the daily analysis pipeline

**Key Functions**:
- Daily log analysis coordination
- Log cluster processing with LLM analysis
- System health score generation

### 4. Report Generator
**Purpose**: Generate JSON reports and send notifications

**Output**:
- JSON structured reports
- Optional webhook notifications

## Configuration

### Environment Variables

**Database Connection**:
- Milvus host, port, and collection configuration

**Analysis Settings**:
- Analysis window duration (default: 24 hours)
- Maximum logs per analysis run
- Batch processing sizes

**LLM Configuration** (Required):
- Provider selection (OpenAI, Anthropic, or local)
- API endpoints and authentication
- Model selection

**Reporting**:
- Output directory for reports
- Optional webhook notifications

## CLI Interface

The AI Analyzer runs as a CronJob and provides a simple CLI interface:

- Daily analysis execution (used in CronJob)
- Manual date-specific analysis
- Health check functionality

## Analysis Pipeline

### 1. Log Clustering
- Groups logs by identical Kubernetes label combinations (app, version, tier, etc.)
- Selects representative log for each cluster (prioritizes ERROR > WARNING > INFO)
- Enables service-specific issue identification

### 2. LLM-Based Analysis
- Sends representative logs to LLM for severity scoring and analysis
- Generates severity scores (1-10 scale) with reasoning
- Categorizes issues by type (error, warning, info, performance)

### 3. Health Score Calculation
- Calculates system health based on error/warning counts and severity scores
- Returns 0-1 score (1 = healthy, 0 = critical issues)
- Factors in LLM analysis results for more accurate assessment

## Deployment

The AI Analyzer is deployed as a Kubernetes CronJob that runs daily at 6 AM to analyze the previous 24 hours of logs.


## Monitoring & Observability

### Basic Metrics
- Total logs processed per analysis run
- Analysis execution time tracking
- System health score monitoring
- LLM API request counting

### Logging Strategy
- Structured logging for analysis execution
- Error tracking and debugging information
- LLM request/response logging (sanitized)

### Health Checks
- Database connectivity verification
- LLM service availability testing
- Resource utilization monitoring

## Security Considerations (MVP Scope)

### Data Privacy
- No log content stored locally beyond analysis session
- LLM requests sanitized to remove obvious PII

### LLM Security
- API key management through Kubernetes secrets
- Request sanitization and validation

## Future Enhancements (Post-MVP)

1. **Real-time Analysis**: Process logs as they arrive
2. **Web Dashboard**: UI for reports and configuration
3. **Advanced PII Detection**: Comprehensive data anonymization
4. **Custom ML Models**: Tailored anomaly detection
5. **Historical Trending**: Long-term pattern analysis