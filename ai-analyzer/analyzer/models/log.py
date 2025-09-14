from dataclasses import dataclass
from datetime import date
from typing import List, Dict, Any, Optional


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