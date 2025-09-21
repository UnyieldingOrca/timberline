from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Literal
from enum import Enum


class LogLevel(Enum):
    """Enumeration for log levels"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"




@dataclass
class LogRecord:
    """Represents a single log record from the vector database"""
    id: int
    timestamp: int  # Unix timestamp in milliseconds
    message: str
    source: str
    metadata: Dict[str, Any]
    embedding: List[float]
    level: str

    def __post_init__(self):
        """Validate the log record after initialization"""
        if self.timestamp <= 0:
            raise ValueError("Timestamp must be positive")
        if not self.message.strip():
            raise ValueError("Message cannot be empty")
        if not self.source.strip():
            raise ValueError("Source cannot be empty")
        if not self.embedding:
            raise ValueError("Embedding cannot be empty")
        if self.level not in [level.value for level in LogLevel]:
            raise ValueError(f"Invalid log level: {self.level}")

    @property
    def datetime(self) -> datetime:
        """Convert timestamp to datetime object"""
        return datetime.fromtimestamp(self.timestamp / 1000)

    @property
    def log_level_enum(self) -> LogLevel:
        """Get log level as enum"""
        return LogLevel(self.level)

    def is_error_or_critical(self) -> bool:
        """Check if log is error or critical level"""
        return self.log_level_enum in [LogLevel.ERROR, LogLevel.CRITICAL]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'message': self.message,
            'source': self.source,
            'metadata': self.metadata,
            'embedding': self.embedding,
            'level': self.level,
            'datetime_iso': self.datetime.isoformat()
        }


@dataclass
class LogCluster:
    """Represents a cluster of similar logs"""
    representative_log: LogRecord
    similar_logs: List[LogRecord]
    count: int
    severity_score: Optional[int] = None  # 1-10 scale set by LLM

    def __post_init__(self):
        """Validate the cluster after initialization"""
        if self.count <= 0:
            raise ValueError("Count must be positive")
        if self.count != len(self.similar_logs):
            raise ValueError("Count must match number of similar logs")
        if self.representative_log not in self.similar_logs:
            raise ValueError("Representative log must be in similar_logs list")
        if self.severity_score is not None:
            if not (1 <= self.severity_score <= 10):
                raise ValueError("Severity score must be between 1 and 10")

    @property
    def error_count(self) -> int:
        """Count of error/critical logs in cluster"""
        return sum(1 for log in self.similar_logs if log.is_error_or_critical())

    @property
    def sources(self) -> List[str]:
        """Unique sources in this cluster"""
        return list(set(log.source for log in self.similar_logs))

    def get_time_range(self) -> tuple[datetime, datetime]:
        """Get the time range of logs in this cluster"""
        timestamps = [log.datetime for log in self.similar_logs]
        return min(timestamps), max(timestamps)

    def is_high_severity(self) -> bool:
        """Check if cluster has high severity (7+)"""
        return self.severity_score is not None and self.severity_score >= 7


@dataclass
class AnalyzedLog:
    """Represents a log that has been analyzed by LLM"""
    log: LogRecord
    severity: int  # 1-10 scale from LLM
    reasoning: str

    def __post_init__(self):
        """Validate the analyzed log after initialization"""
        if not (1 <= self.severity <= 10):
            raise ValueError("Severity must be between 1 and 10")
        if not self.reasoning.strip():
            raise ValueError("Reasoning cannot be empty")

    def is_actionable(self) -> bool:
        """Check if this analysis indicates actionable issues"""
        return self.severity >= 5

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            'log': self.log.to_dict(),
            'severity': self.severity,
            'reasoning': self.reasoning,
            'is_actionable': self.is_actionable()
        }


@dataclass
class DailyAnalysisResult:
    """Represents the complete result of a daily analysis run"""
    analysis_date: date
    total_logs_processed: int
    error_count: int
    warning_count: int
    analyzed_clusters: List[LogCluster]
    top_issues: List[AnalyzedLog]  # Top 10 by severity
    health_score: float  # 0-1 scale
    llm_summary: str
    execution_time: float

    def __post_init__(self):
        """Validate the analysis result after initialization"""
        if self.total_logs_processed < 0:
            raise ValueError("Total logs processed cannot be negative")
        if self.error_count < 0 or self.warning_count < 0:
            raise ValueError("Error/warning counts cannot be negative")
        if not (0 <= self.health_score <= 1):
            raise ValueError("Health score must be between 0 and 1")
        if self.execution_time < 0:
            raise ValueError("Execution time cannot be negative")
        if len(self.top_issues) > 10:
            raise ValueError("Top issues should not exceed 10 items")
        if not self.llm_summary.strip():
            raise ValueError("LLM summary cannot be empty")

    @property
    def info_count(self) -> int:
        """Calculate info log count"""
        return self.total_logs_processed - self.error_count - self.warning_count

    @property
    def error_rate(self) -> float:
        """Calculate error rate as percentage"""
        if self.total_logs_processed == 0:
            return 0.0
        return (self.error_count / self.total_logs_processed) * 100

    @property
    def warning_rate(self) -> float:
        """Calculate warning rate as percentage"""
        if self.total_logs_processed == 0:
            return 0.0
        return (self.warning_count / self.total_logs_processed) * 100

    def get_critical_issues(self) -> List[AnalyzedLog]:
        """Get issues with severity >= 8"""
        return [issue for issue in self.top_issues if issue.severity >= 8]

    def get_health_status(self) -> Literal["healthy", "warning", "critical"]:
        """Get health status based on health score"""
        if self.health_score >= 0.8:
            return "healthy"
        elif self.health_score >= 0.5:
            return "warning"
        else:
            return "critical"

    def to_summary_dict(self) -> Dict[str, Any]:
        """Convert to summary dictionary for reporting"""
        return {
            'analysis_date': self.analysis_date.isoformat(),
            'total_logs_processed': self.total_logs_processed,
            'error_count': self.error_count,
            'warning_count': self.warning_count,
            'info_count': self.info_count,
            'error_rate': round(self.error_rate, 2),
            'warning_rate': round(self.warning_rate, 2),
            'health_score': round(self.health_score, 3),
            'health_status': self.get_health_status(),
            'critical_issues_count': len(self.get_critical_issues()),
            'total_clusters': len(self.analyzed_clusters),
            'execution_time': round(self.execution_time, 2),
            'llm_summary': self.llm_summary
        }