"""Database models for analysis results."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Float, Text, JSON, BigInteger
from analyzer.db.base import Base


class AnalysisResult(Base):
    """Analysis result stored in PostgreSQL."""

    __tablename__ = "analysis_results"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    analysis_date = Column(String(10), nullable=False, unique=True, index=True)  # YYYY-MM-DD
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
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
