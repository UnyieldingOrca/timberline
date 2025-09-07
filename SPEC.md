# Timberline - AI-Powered Log Analysis Platform

## Project Overview

Timberline is a scalable, AI-powered log analysis platform designed for Kubernetes environments. It provides intelligent log ingestion, processing, and actionable reporting to help organizations identify and respond to critical system events proactively.


## Component Specifications

### 1. Log Collector (Go DaemonSet)

**Purpose**: Efficiently collect, pre-filter, and forward logs from all Kubernetes nodes.

#### Responsibilities
- Tail log files from `/var/log/containers/*` and `/var/log/pods/*`
- Perform real-time log filtering and enrichment
- Buffer and batch logs for efficient transmission
- Handle backpressure and implement retry logic
- Enrich logs with Kubernetes metadata

#### Technical Requirements
- **Language**: Go
- **Deployment**: Kubernetes DaemonSet
- **Resource Limits**:
  - Memory: 128Mi - 256Mi
  - CPU: 100m - 200m
- **Storage**: Optional file-based buffer (1GB)

#### Key Features
- **Pre-filtering**: Configurable rules to filter noise (debug logs, info logs, health checks)
- **Log Parsing**: Support for JSON, structured, and unstructured logs
- **Metadata Enrichment**: Add pod name, namespace, node, labels
- **Compression**: Gzip compression for network efficiency
- **Security**: Optional TLS encryption for log transmission

#### Configuration
Configuration will be handled via environment variables:
- Log levels to capture (ERROR, WARN)
- Buffer size and flush interval
- Ingestor endpoint URL
- Authentication tokens (if needed)

### 2. Log Ingester (Go Service)

**Purpose**: Receive logs from collectors, validate, enrich, and store in vector database.

#### Responsibilities
- Receive and validate incoming log streams
- Extract features and store in vector database
- Provide health endpoints and metrics
- Handle deduplication and rate limiting

#### Technical Requirements
- **Language**: Go
- **Deployment**: Kubernetes Deployment (3+ replicas)
- **Resource Limits**:
  - Memory: 1Gi - 2Gi
  - CPU: 500m - 1000m

#### Key Features
- **HTTP**: Accept logs via REST API
- **Batch Processing**: Efficient batching for Milvus insertions
- **Monitoring**: Prometheus metrics and health checks
- **Schema Validation**: Validate log structure and required fields

#### API Endpoints
```
POST /api/v1/logs/batch     - Batch log ingestion
GET  /api/v1/health         - Health check
GET  /api/v1/metrics        - Prometheus metrics
```

### 3. Vector Database (Milvus)

**Purpose**: Store log vectors, and provide similarity search capabilities.

#### Schema Design
```yaml
Collections:
  logs:
    fields:
      - id: int64 (primary key)
      - timestamp: int64
      - log_level: varchar(10)
      - message: varchar(65535)
      - source_pod: varchar(255)
      - namespace: varchar(255)
      - node: varchar(255)
      - embedding: float_vector(384)  # sentence-transformer dimension
    indexes:
      - field: embedding
        type: IVF_FLAT
        metric: L2
```

#### Requirements
- **Version**: Milvus 2.6+
- **Storage**: Persistent volumes (100GB+)
- **Memory**: 4Gi+

#### Vector Operations
- **Similarity Search**: Find similar log patterns
- **Anomaly Detection**: Identify outlier log entries
- **Clustering**: Group similar logs for analysis
- **Time-based Queries**: Search within time ranges

### 4. AI Analysis Engine (Python Service/Job)

**Purpose**: Perform AI-powered analysis and generate actionable reports.

#### Responsibilities
- Daily analysis of ingested logs
- Anomaly detection and pattern recognition
- Generate summary reports with actionable insights
- Send notifications for critical findings
- Maintain analysis history and trends

#### Technical Requirements
- **Language**: Python 3.11+
- **Deployment**: Kubernetes CronJob (daily) + Service (on-demand)
- **Resource Limits**:
  - Memory: 2Gi - 4Gi
  - CPU: 1000m - 2000m
- **GPU**: Optional (for large language models)

#### AI Capabilities
- **Large Language Models**: GPT-4/Claude for log interpretation
- **Anomaly Detection**: Statistical and ML-based anomaly detection
- **Pattern Recognition**: Identify recurring issues and trends
- **Severity Scoring**: Assign criticality scores to findings
- **Natural Language Reports**: Generate human-readable summaries

#### Key Features
```
# Analysis Pipeline
1. Data Retrieval    # Query last 24h of logs from Milvus
2. Preprocessing     # Clean and normalize log data
3. Anomaly Detection # Identify unusual patterns
4. LLM Analysis      # Generate insights using LLM
5. Report Generation # Create structured reports
6. Notification      # Send alerts via configured channels
```

## Data Flow

```
1. Log Generation
   └── Application pods generate logs

2. Collection Phase
   └── DaemonSet collectors tail log files
   └── Pre-filtering removes noise
   └── Metadata enrichment adds context

3. Ingestion Phase
   └── Collectors send batched logs to ingester
   └── Ingester validates and processes logs
   └── Extract embeddings using an AI model
   └── Write to Milvus

4. Storage Phase
   └── Logs stored in milvus with embeddings
   └── Indexed for efficient retrieval

5. Analysis Phase (Daily)
   └── AI engine queries recent logs
   └── Performs anomaly detection
   └── Generates insights and reports
   └── Sends notifications
```
