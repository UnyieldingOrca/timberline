# AI Log Analyzer - Component Specification

## Overview

The AI Log Analyzer is a Python-based service that performs intelligent analysis of logs stored in the Milvus vector database to identify concerning, anomalous, and actionable log patterns. It runs on a daily cadence to provide proactive insights for system health and operational improvements.

## Architecture

### Component Type
- **Language**: Python 3.11+
- **Deployment**: Kubernetes CronJob (daily scheduled) + Service (on-demand analysis)
- **Dependencies**: Milvus, llama.cpp embedding service, optional LLM endpoint

### Resource Requirements
- **Memory**: 2-4 GiB (depending on analysis window size)
- **CPU**: 1-2 cores
- **Storage**: 1 GiB for temporary analysis data and reports
- **GPU**: Optional (for local LLM inference)

## Core Responsibilities

### 1. Daily Log Analysis Pipeline
- Query last 24 hours of logs from Milvus vector database
- Perform statistical anomaly detection
- Execute semantic similarity analysis for pattern recognition
- Generate severity scores for identified issues
- Create actionable reports with recommendations

### 2. Real-time Analysis API
- On-demand analysis for specific time ranges
- Immediate analysis of critical log patterns
- Health check and metrics endpoints

### 3. Report Generation & Notifications
- Generate structured analysis reports
- Send alerts for critical findings
- Maintain historical analysis trends
- Export reports in multiple formats (JSON, HTML, Slack)

## Data Flow

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Milvus    │───▶│ AI Analyzer  │───▶│ Analysis Reports│
│  (Logs DB)  │    │   Service    │    │ & Notifications │
└─────────────┘    └──────────────┘    └─────────────────┘
                           │
                    ┌──────▼──────┐
                    │ LLM Service │
                    │ (Optional)  │
                    └─────────────┘
```

## Technical Components

### 1. Milvus Query Engine (`analyzer/storage/milvus_client.py`)

**Purpose**: Interface with Milvus for log retrieval and semantic search

**Key Features**:
- Time-range queries for daily analysis windows
- Semantic similarity search for pattern detection
- Anomaly detection using vector distance metrics
- Batch processing for large log volumes

**Core Methods**:
```python
class MilvusQueryEngine:
    def query_time_range(self, start_time: datetime, end_time: datetime) -> List[LogRecord]
    def search_similar_logs(self, query_embedding: List[float], limit: int = 100) -> List[LogRecord]
    def detect_anomalous_patterns(self, time_window: timedelta) -> List[AnomalyResult]
    def get_log_statistics(self, time_range: tuple) -> LogStatistics
```

### 2. Analysis Engine (`analyzer/analysis/engine.py`)

**Purpose**: Core analysis logic for identifying concerning log patterns

**Analysis Capabilities**:
- **Statistical Anomaly Detection**: Identify logs with unusual frequency, timing, or patterns
- **Severity Classification**: Assign criticality scores (1-10) to log entries and patterns
- **Pattern Recognition**: Group similar errors and identify recurring issues
- **Trend Analysis**: Compare current patterns with historical baselines
- **Service Health Assessment**: Per-service and system-wide health scoring

**Analysis Pipeline**:
```python
class AnalysisEngine:
    def analyze_daily_logs(self, analysis_date: date) -> DailyAnalysisResult
    def detect_anomalies(self, logs: List[LogRecord]) -> List[Anomaly]
    def classify_severity(self, logs: List[LogRecord]) -> List[SeverityClassification]
    def identify_actionable_items(self, logs: List[LogRecord]) -> List[ActionableItem]
    def generate_insights(self, analysis_results: AnalysisResult) -> List[Insight]
```

### 3. LLM Integration (`analyzer/llm/client.py`)

**Purpose**: Optional integration with Large Language Models for advanced analysis

**Capabilities**:
- Natural language interpretation of complex error patterns
- Root cause analysis suggestions
- Human-readable report generation
- Contextual recommendations

**Supported LLM Providers**:
- **Local**: llama.cpp, Ollama
- **Cloud**: OpenAI GPT-4, Anthropic Claude, Azure OpenAI
- **Self-hosted**: vLLM, TGI (Text Generation Inference)

**Integration Pattern**:
```python
class LLMClient:
    def analyze_log_pattern(self, pattern: LogPattern) -> AnalysisInsight
    def generate_root_cause_analysis(self, error_cluster: List[LogRecord]) -> RootCauseAnalysis
    def create_human_readable_summary(self, analysis: AnalysisResult) -> str
    def suggest_actions(self, anomalies: List[Anomaly]) -> List[ActionSuggestion]
```

### 4. Report Generator (`analyzer/reporting/generator.py`)

**Purpose**: Generate structured reports and notifications

**Report Types**:
- **Daily Summary**: High-level health overview with key metrics
- **Critical Issues**: Immediate attention items with severity scores
- **Trend Analysis**: Week/month comparisons and patterns
- **Service Health**: Per-service breakdown and recommendations
- **Actionable Items**: Prioritized list with suggested actions

**Output Formats**:
- JSON (structured data for APIs)
- HTML (human-readable dashboards)
- Markdown (documentation integration)
- Slack/Teams (notification integrations)

## Configuration

### Environment Variables

```bash
# Database Connection
MILVUS_HOST=milvus
MILVUS_PORT=19530
MILVUS_COLLECTION=timberline_logs

# Analysis Settings
ANALYSIS_WINDOW_HOURS=24
ANOMALY_THRESHOLD=2.0
SEVERITY_THRESHOLD=7
MAX_LOGS_PER_ANALYSIS=50000

# LLM Configuration (Optional)
LLM_PROVIDER=openai|anthropic|local|none
LLM_ENDPOINT=http://localhost:8000/v1
LLM_MODEL=gpt-4|claude-3|llama-3.1-8b
LLM_API_KEY=secret_key

# Reporting
REPORT_OUTPUT_DIR=/app/reports
NOTIFICATION_WEBHOOK_URL=https://hooks.slack.com/...
SMTP_SERVER=smtp.company.com
ALERT_EMAIL=ops-team@company.com

# Scheduling
CRON_SCHEDULE=0 6 * * *  # Daily at 6 AM
TIMEZONE=UTC
```

## API Endpoints

### REST API Service

```
# Health and Status
GET  /api/v1/health              # Service health check
GET  /api/v1/status              # Analysis status and metrics

# Analysis Operations
POST /api/v1/analyze/on-demand   # Trigger immediate analysis
GET  /api/v1/analyze/latest      # Get latest analysis results
GET  /api/v1/analyze/history     # Get historical analysis results

# Reports
GET  /api/v1/reports/daily/{date}    # Get daily report
GET  /api/v1/reports/summary         # Get current summary
POST /api/v1/reports/export          # Export report in specified format

# Configuration
GET  /api/v1/config              # Get current configuration
PUT  /api/v1/config              # Update configuration

# Metrics
GET  /api/v1/metrics             # Prometheus metrics endpoint
```

### Webhook Notifications

```
# Slack Integration
POST /webhook/slack/critical     # Send critical alerts to Slack
POST /webhook/slack/daily        # Send daily summary to Slack

# Generic Webhooks
POST /webhook/generic/{endpoint} # Send notifications to configured endpoints
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
class Anomaly:
    id: str
    type: str  # 'statistical', 'semantic', 'frequency'
    severity: int  # 1-10 scale
    description: str
    affected_logs: List[int]  # Log IDs
    confidence: float  # 0.0-1.0
    first_seen: datetime
    last_seen: datetime
    similar_patterns: List[str]

@dataclass
class ActionableItem:
    id: str
    title: str
    description: str
    severity: int
    category: str  # 'performance', 'error', 'security', 'infrastructure'
    suggested_actions: List[str]
    affected_services: List[str]
    estimated_impact: str  # 'low', 'medium', 'high', 'critical'
    time_to_resolve: str  # 'immediate', 'hours', 'days'

@dataclass
class DailyAnalysisResult:
    analysis_date: date
    total_logs_processed: int
    anomalies_detected: List[Anomaly]
    actionable_items: List[ActionableItem]
    service_health_scores: Dict[str, float]
    overall_health_score: float
    trends: Dict[str, Any]
    execution_time: float
```

## Analysis Algorithms

### 1. Statistical Anomaly Detection

**Z-Score Analysis**: Identify logs with unusual frequency patterns
```python
def detect_frequency_anomalies(logs: List[LogRecord], window: timedelta) -> List[Anomaly]:
    # Group logs by time buckets and calculate z-scores for frequencies
    # Flag buckets with z-score > threshold as anomalies
```

**Isolation Forest**: Detect outliers in log embedding space
```python
def detect_embedding_anomalies(embeddings: List[List[float]]) -> List[Anomaly]:
    # Use isolation forest to identify logs with unusual embedding patterns
    # Useful for finding completely new types of errors
```

### 2. Semantic Pattern Recognition

**Clustering Analysis**: Group similar error messages
```python
def cluster_similar_logs(logs: List[LogRecord]) -> List[LogCluster]:
    # Use DBSCAN or K-means clustering on embeddings
    # Identify recurring error patterns and their frequencies
```

**Temporal Pattern Analysis**: Identify time-based patterns
```python
def analyze_temporal_patterns(logs: List[LogRecord]) -> List[TemporalPattern]:
    # Find patterns that occur at specific times or intervals
    # Useful for identifying scheduled job failures or peak hour issues
```

### 3. Severity Scoring

**Multi-factor Severity Assessment**:
- **Log Level**: ERROR > WARN > INFO weight
- **Message Content**: Keywords like "critical", "fatal", "timeout"
- **Frequency**: Repeated errors get higher scores
- **Service Impact**: Core services weighted higher
- **Time Context**: Recent errors weighted higher

```python
def calculate_severity_score(log: LogRecord, context: AnalysisContext) -> int:
    score = 0
    score += log_level_weight(log.level)
    score += keyword_analysis(log.message)
    score += frequency_multiplier(log, context)
    score += service_criticality(log.source)
    score += temporal_relevance(log.timestamp)
    return min(10, score)  # Cap at 10
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
            resources:
              requests:
                memory: "2Gi"
                cpu: "1000m"
              limits:
                memory: "4Gi"
                cpu: "2000m"
```

**Service for On-Demand Analysis**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ai-analyzer-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ai-analyzer-service
  template:
    metadata:
      labels:
        app: ai-analyzer-service
    spec:
      containers:
      - name: ai-analyzer
        image: timberline/ai-analyzer:latest
        command: ["python", "-m", "analyzer.server"]
        ports:
        - containerPort: 8080
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

# ML/AI
sentence-transformers>=2.5.0
transformers>=4.30.0
torch>=2.0.0

# API Framework
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0

# Configuration
pyyaml>=6.0
python-dotenv>=1.0.0

# Utilities
loguru>=0.7.0
httpx>=0.24.0
jinja2>=3.1.0

# Optional LLM Integrations
openai>=1.0.0
anthropic>=0.3.0
```

## Monitoring & Observability

### Metrics Exposed
- `analyzer_logs_processed_total`: Total logs analyzed
- `analyzer_anomalies_detected_total`: Anomalies found
- `analyzer_analysis_duration_seconds`: Analysis execution time
- `analyzer_service_health_scores`: Health scores by service
- `analyzer_llm_requests_total`: LLM API requests (if enabled)

### Logging Strategy
- Structured logging with correlation IDs
- Log analysis execution details
- Performance metrics and timing
- Error tracking and debugging information

### Health Checks
- Milvus connectivity
- LLM service availability (if configured)
- Recent analysis execution status
- Resource utilization monitoring

## Security Considerations

### Data Privacy
- No log content stored locally beyond analysis session
- Optional log anonymization before LLM processing
- Configurable PII detection and redaction

### API Security
- JWT authentication for API endpoints
- Rate limiting for on-demand analysis
- RBAC for configuration changes

### LLM Security
- API key management through secrets
- Request sanitization and validation
- Local LLM option for sensitive environments

## Future Enhancements

### Planned Features
1. **Machine Learning Models**: Custom anomaly detection models
2. **Real-time Streaming**: Process logs as they arrive
3. **Dashboard Integration**: Web UI for reports and configuration
4. **Multi-tenant Support**: Analyze logs from multiple clusters
5. **Advanced Alerting**: Smart alert routing and escalation
6. **Historical Trending**: Long-term pattern analysis and predictions

### Integration Opportunities
- **Kubernetes Events**: Correlate log anomalies with K8s events
- **Metrics**: Combine log analysis with Prometheus metrics
- **Tracing**: Integration with distributed tracing systems
- **CI/CD**: Automated analysis in deployment pipelines