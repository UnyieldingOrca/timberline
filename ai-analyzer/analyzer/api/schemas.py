"""Pydantic schemas for API requests and responses"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field


class AnalysisStatus(str, Enum):
    """Analysis status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class LogEntryResponse(BaseModel):
    """Log entry response model"""
    id: str
    timestamp: str
    namespace: str
    pod_name: str
    container_name: str
    log: str
    severity: Optional[str] = None
    node_name: Optional[str] = None
    labels: Optional[Dict[str, str]] = None

    class Config:
        from_attributes = True


class LogSearchRequest(BaseModel):
    """Log search request model"""
    query: str = Field(..., description="Search query for semantic search")
    limit: int = Field(50, ge=1, le=1000, description="Maximum number of results")


class ClusterInfo(BaseModel):
    """Cluster information model"""
    cluster_id: int
    label: str
    size: int
    sample_logs: List[str]
    severity: str


class AnalysisResponse(BaseModel):
    """Analysis response model"""
    id: str
    created_at: datetime
    status: AnalysisStatus
    cluster_count: Optional[int] = None
    severity_score: Optional[float] = None
    summary: Optional[str] = None
    clusters: Optional[List[ClusterInfo]] = None
    error: Optional[str] = None

    class Config:
        from_attributes = True


class CreateAnalysisRequest(BaseModel):
    """Create analysis request model"""
    namespace: Optional[str] = Field(None, description="Namespace to analyze (all if not specified)")
    time_range_hours: Optional[int] = Field(24, ge=1, le=168, description="Hours to look back")
    min_cluster_size: Optional[int] = Field(5, ge=1, le=100, description="Minimum cluster size")
