"""Database models for analysis results."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, JSON, BigInteger, Enum
import enum
from analyzer.db.base import Base


def utcnow():
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class AnalysisStatus(enum.Enum):
    """Analysis job status enum."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisJob(Base):
    """Analysis job tracking table."""

    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True)  # UUID
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    status = Column(Enum(AnalysisStatus), nullable=False, default=AnalysisStatus.PENDING, index=True)
    namespace = Column(String(255), nullable=True)
    time_range_hours = Column(Integer, nullable=False, default=24)
    min_cluster_size = Column(Integer, nullable=False, default=5)
    cluster_count = Column(Integer, nullable=True)
    severity_score = Column(Float, nullable=True)
    summary = Column(Text, nullable=True)
    clusters = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    def __repr__(self):
        return f"<AnalysisJob(id={self.id}, status={self.status.value})>"


class AnalysisResult(Base):
    """Analysis result stored in PostgreSQL."""

    __tablename__ = "analysis_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    analysis_date = Column(String(10), nullable=False, unique=True, index=True)  # YYYY-MM-DD
    generated_at = Column(DateTime, nullable=False, default=utcnow)
    total_logs_processed = Column(Integer, nullable=False)
    error_count = Column(Integer, nullable=False, default=0)
    warning_count = Column(Integer, nullable=False, default=0)
    error_rate = Column(Float, nullable=False, default=0.0)
    warning_rate = Column(Float, nullable=False, default=0.0)
    execution_time = Column(Float, nullable=False)
    clusters_found = Column(Integer, nullable=False, default=0)
    top_issues_count = Column(Integer, nullable=False, default=0)
    report_data = Column(JSON, nullable=False)
    llm_summary = Column(Text, nullable=True)

    def __repr__(self):
        return f"<AnalysisResult(date={self.analysis_date}, logs={self.total_logs_processed})>"
