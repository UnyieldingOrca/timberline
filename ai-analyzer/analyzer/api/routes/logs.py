"""Logs API endpoints"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Query, Request, HTTPException
from loguru import logger

from ..schemas import LogEntryResponse, LogSearchRequest
from ...storage.milvus_client import MilvusQueryEngine

router = APIRouter()


@router.get("/logs", response_model=List[LogEntryResponse])
async def get_logs(
    request: Request,
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    pod_name: Optional[str] = Query(None, description="Filter by pod name"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of logs"),
    start_time: Optional[str] = Query(None, description="Start time (ISO 8601)"),
    end_time: Optional[str] = Query(None, description="End time (ISO 8601)"),
):
    """Get logs with optional filters"""
    try:
        settings = request.app.state.settings
        milvus_client = MilvusQueryEngine(settings)
        milvus_client.connect()

        # Determine time range
        if end_time:
            end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        else:
            end_dt = datetime.now()

        if start_time:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        else:
            start_dt = end_dt - timedelta(hours=24)

        # Query logs
        logs = milvus_client.query_time_range(start_dt, end_dt)

        # Filter by namespace and pod_name if provided
        # The metadata field contains the kubernetes metadata directly (not nested)
        if namespace:
            logs = [
                log for log in logs
                if isinstance(log.metadata, dict) and
                log.metadata.get('namespace_name') == namespace
            ]

        if pod_name:
            logs = [
                log for log in logs
                if isinstance(log.metadata, dict) and
                log.metadata.get('pod_name') == pod_name
            ]

        # Limit results
        logs = logs[:limit]

        # Convert to response model
        response = []
        for log in logs:
            # The metadata field contains the kubernetes metadata directly (not nested under 'kubernetes' key)
            # because the log-ingestor extracts it from Fluent Bit's kubernetes field
            k8s_metadata = log.metadata if isinstance(log.metadata, dict) else {}

            response.append(LogEntryResponse(
                id=str(log.id),
                timestamp=datetime.fromtimestamp(log.timestamp / 1000).isoformat(),
                namespace=k8s_metadata.get('namespace_name', 'unknown'),
                pod_name=k8s_metadata.get('pod_name', 'unknown'),
                container_name=k8s_metadata.get('container_name', 'unknown'),
                log=log.message,
                severity=log.level,
                node_name=k8s_metadata.get('host'),
                labels=k8s_metadata.get('labels', {})
            ))

        milvus_client.disconnect()
        return response

    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logs/search", response_model=List[LogEntryResponse])
async def search_logs(request: Request, search_request: LogSearchRequest):
    """Semantic search for logs using embeddings"""
    try:
        settings = request.app.state.settings
        milvus_client = MilvusQueryEngine(settings)
        milvus_client.connect()

        # TODO: Implement semantic search
        # For now, return empty list as placeholder
        # This would require:
        # 1. Generate embedding for search query
        # 2. Perform vector similarity search in Milvus
        # 3. Return top matching logs

        logger.warning("Semantic search not yet implemented")
        milvus_client.disconnect()
        return []

    except Exception as e:
        logger.error(f"Error searching logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
