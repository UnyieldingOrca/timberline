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
- Group similar logs using vector clustering
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

### 1. Milvus Query Engine (`analyzer/storage/milvus_client.py`)

**Purpose**: Interface with Milvus for log retrieval and clustering

**Key Features**:
- Time-range queries for daily analysis windows
- Log clustering using vector similarity
- Batch processing for large log volumes

**Core Methods**:
```python
class MilvusQueryEngine:
    def query_time_range(self, start_time: datetime, end_time: datetime) -> List[LogRecord]
    def cluster_similar_logs(self, logs: List[LogRecord]) -> List[LogCluster]
    def get_log_statistics(self, time_range: tuple) -> LogStatistics
```

### 2. LLM Integration (`analyzer/llm/client.py`)

**Purpose**: Core LLM integration for log analysis and severity ranking

**Capabilities**:
- Severity scoring (1-10 scale) for log patterns
- Natural language interpretation of error clusters
- Human-readable summaries and insights

**Supported LLM Providers**:
- **Local**: llama.cpp, Ollama
- **Cloud**: OpenAI GPT-4, Anthropic Claude

**Integration Pattern**:
```python
class LLMClient:
    def analyze_log_batch(self, logs: List[LogRecord]) -> List[AnalyzedLog]
    def rank_severity(self, log_clusters: List[LogCluster]) -> List[SeverityScore]
    def generate_daily_summary(self, analysis: AnalysisResult) -> str
```

### 3. Analysis Engine (`analyzer/analysis/engine.py`)

**Purpose**: Orchestrate the daily analysis pipeline

**Analysis Pipeline**:
```python
class AnalysisEngine:
    def analyze_daily_logs(self, analysis_date: date) -> DailyAnalysisResult
    def process_log_clusters(self, clusters: List[LogCluster]) -> List[AnalyzedCluster]
    def generate_health_score(self, analysis: AnalysisResult) -> float
```

### 4. Report Generator (`analyzer/reporting/generator.py`)

**Purpose**: Generate JSON reports and send notifications

**Output**:
- JSON structured reports
- Optional webhook notifications

**Core Methods**:
```python
class ReportGenerator:
    def generate_daily_report(self, analysis: DailyAnalysisResult) -> Dict
    def save_report(self, report: Dict, filepath: str) -> None
    def send_webhook_notification(self, report: Dict, webhook_url: str) -> None
```

## Configuration

### Environment Variables

```bash
# Database Connection
MILVUS_HOST=milvus
MILVUS_PORT=19530
MILVUS_COLLECTION=timberline_logs

# Analysis Settings
ANALYSIS_WINDOW_HOURS=24
MAX_LOGS_PER_ANALYSIS=10000
CLUSTER_BATCH_SIZE=50

# LLM Configuration (Required)
LLM_PROVIDER=openai|anthropic|local
LLM_ENDPOINT=http://localhost:8000/v1
LLM_MODEL=gpt-4o-mini|claude-3-haiku|llama-3.1-8b
LLM_API_KEY=secret_key

# Reporting
REPORT_OUTPUT_DIR=/app/reports
WEBHOOK_URL=https://hooks.slack.com/...
```

## CLI Interface

The AI Analyzer runs as a CronJob and provides a simple CLI interface:

```bash
# Main analysis command (used in CronJob)
python -m analyzer.cli analyze-daily

# Optional manual execution
python -m analyzer.cli analyze-date --date=2024-01-15
python -m analyzer.cli health-check
```

## Data Models

### Core Data Structures

```python
@dataclass
class LogRecord:
    id: int
    timestamp: int  # Unix timestamp in milliseconds
    message: str
    source: str
    metadata: Dict[str, Any]
    embedding: List[float]
    level: str

@dataclass
class LogCluster:
    representative_log: LogRecord
    similar_logs: List[LogRecord]
    count: int
    severity_score: Optional[int] = None  # Set by LLM

@dataclass
class AnalyzedLog:
    log: LogRecord
    severity: int  # 1-10 scale from LLM
    reasoning: str
    category: str  # 'error', 'warning', 'info', 'performance'

@dataclass
class DailyAnalysisResult:
    analysis_date: date
    total_logs_processed: int
    error_count: int
    warning_count: int
    analyzed_clusters: List[LogCluster]
    top_issues: List[AnalyzedLog]  # Top 10 by severity
    health_score: float  # 0-1 scale
    llm_summary: str
    execution_time: float
```

## Analysis Pipeline

### 1. Log Clustering
```python
def cluster_similar_logs(logs: List[LogRecord]) -> List[LogCluster]:
    # Use vector similarity clustering on embeddings
    # Group similar log messages together
    # Select representative log for each cluster
```

### 2. LLM-Based Analysis
```python
def analyze_with_llm(clusters: List[LogCluster]) -> List[AnalyzedLog]:
    # Send representative logs to LLM for analysis
    # Get severity scores (1-10) and reasoning
    # Categorize issues by type
```

### 3. Health Score Calculation
```python
def calculate_health_score(analysis: DailyAnalysisResult) -> float:
    # Simple formula based on error/warning counts and severity scores
    # Returns 0-1 score (1 = healthy, 0 = critical issues)
```

## Deployment

### Kubernetes Manifests

**CronJob for Daily Analysis**:
```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: ai-analyzer-daily
spec:
  schedule: "0 6 * * *"  # Daily at 6 AM
  jobTemplate:
    spec:
      template:
        spec:
          containers:
          - name: ai-analyzer
            image: timberline/ai-analyzer:latest
            command: ["python", "-m", "analyzer.cli", "analyze-daily"]
            env:
            - name: MILVUS_HOST
              value: "milvus"
            - name: LLM_PROVIDER
              value: "openai"
            - name: LLM_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llm-credentials
                  key: api-key
            resources:
              requests:
                memory: "1Gi"
                cpu: "500m"
              limits:
                memory: "2Gi"
                cpu: "1000m"
```

### Docker Configuration

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY analyzer/ ./analyzer/
COPY config/ ./config/

# Create non-root user
RUN useradd -m -u 1000 analyzer
USER analyzer

EXPOSE 8080

CMD ["python", "-m", "analyzer.server"]
```

## Dependencies

### Core Python Packages

```text
# Data Processing
pandas>=2.0.0
numpy>=1.24.0
scikit-learn>=1.3.0

# Vector Database
pymilvus>=2.6.0

# LLM Integrations
openai>=1.0.0
anthropic>=0.3.0

# Configuration
python-dotenv>=1.0.0

# Utilities
loguru>=0.7.0
httpx>=0.24.0
click>=8.0.0  # CLI framework
```

## Monitoring & Observability

### Basic Metrics
- `analyzer_logs_processed_total`: Total logs analyzed
- `analyzer_analysis_duration_seconds`: Analysis execution time
- `analyzer_health_score`: Latest calculated health score
- `analyzer_llm_requests_total`: LLM API requests

### Logging Strategy
- Structured logging for analysis execution
- Error tracking and debugging information
- LLM request/response logging (without sensitive data)

### Health Checks
- Milvus connectivity test
- LLM service availability test
- Basic resource utilization check

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