"""Analysis API endpoints"""
import uuid
from datetime import datetime, timedelta
from typing import List
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from loguru import logger

from ..schemas import AnalysisResponse, CreateAnalysisRequest, ClusterInfo, AnalysisStatus as APIAnalysisStatus
from ...db.base import get_db
from ...db.models import AnalysisJob, AnalysisStatus as DBAnalysisStatus
from ...storage.milvus_client import MilvusQueryEngine
from ...llm.client import LLMClient

router = APIRouter()


async def run_analysis_task(job_id: str, settings, namespace: str = None, time_range_hours: int = 24, min_cluster_size: int = 5):
    """Background task to run analysis"""
    db: Session = next(get_db())

    try:
        # Update status to running
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = DBAnalysisStatus.RUNNING
        job.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Starting analysis job {job_id}")

        # Initialize Milvus client
        milvus_client = MilvusQueryEngine(settings)
        milvus_client.connect()

        # Query logs
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=time_range_hours)
        logs = milvus_client.query_time_range(start_time, end_time)

        # Filter by namespace if provided
        # The metadata field contains the kubernetes metadata directly (not nested)
        if namespace:
            logs = [
                log for log in logs
                if isinstance(log.metadata, dict) and
                log.metadata.get('namespace_name') == namespace
            ]

        logger.info(f"Retrieved {len(logs)} logs for analysis")

        # Cluster logs
        clusters = milvus_client.cluster_similar_logs(logs)

        # Filter clusters by min size
        clusters = [c for c in clusters if c.count >= min_cluster_size]

        logger.info(f"Found {len(clusters)} clusters")

        # Prepare cluster info for response
        cluster_info = []
        for i, cluster in enumerate(clusters[:20]):  # Limit to top 20 clusters
            sample_logs = [log.message for log in cluster.similar_logs[:3]]
            cluster_info.append({
                "cluster_id": i,
                "label": cluster.representative_log.message[:100],
                "size": cluster.count,
                "sample_logs": sample_logs,
                "severity": cluster.representative_log.level
            })

        # Calculate severity score
        error_count = sum(1 for log in logs if log.is_error_or_critical())
        severity_score = min((error_count / len(logs)) * 10, 10.0) if logs else 0.0

        # Generate summary using LLM
        summary = None
        try:
            llm_client = LLMClient(settings)
            if llm_client.health_check():
                # Create summary from top clusters
                top_clusters_text = "\n".join([
                    f"Cluster {i+1}: {c['label']} ({c['size']} logs, {c['severity']})"
                    for i, c in enumerate(cluster_info[:5])
                ])

                prompt = f"""Analyze these log clusters and provide a brief summary:

{top_clusters_text}

Total logs: {len(logs)}
Error count: {error_count}
Clusters found: {len(clusters)}

Provide a 2-3 sentence summary of the main issues."""

                summary = llm_client.generate_summary(prompt)
        except Exception as e:
            logger.warning(f"Failed to generate LLM summary: {e}")

        # Update job with results
        job.status = DBAnalysisStatus.COMPLETED
        job.cluster_count = len(clusters)
        job.severity_score = severity_score
        job.summary = summary
        job.clusters = cluster_info
        job.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"Analysis job {job_id} completed successfully")

        milvus_client.disconnect()

    except Exception as e:
        logger.error(f"Analysis job {job_id} failed: {e}")

        # Update job with error
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if job:
            job.status = DBAnalysisStatus.FAILED
            job.error = str(e)
            job.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@router.get("/analyses", response_model=List[AnalysisResponse])
async def get_analyses(request: Request, db: Session = Depends(get_db)):
    """Get all analyses"""
    try:
        jobs = db.query(AnalysisJob).order_by(AnalysisJob.created_at.desc()).all()

        response = []
        for job in jobs:
            clusters = None
            if job.clusters:
                clusters = [ClusterInfo(**c) for c in job.clusters]

            response.append(AnalysisResponse(
                id=job.id,
                created_at=job.created_at,
                status=APIAnalysisStatus(job.status.value),
                cluster_count=job.cluster_count,
                severity_score=job.severity_score,
                summary=job.summary,
                clusters=clusters,
                error=job.error
            ))

        return response

    except Exception as e:
        logger.error(f"Error fetching analyses: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analyses/{analysis_id}", response_model=AnalysisResponse)
async def get_analysis(request: Request, analysis_id: str, db: Session = Depends(get_db)):
    """Get specific analysis"""
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == analysis_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Analysis not found")

        clusters = None
        if job.clusters:
            clusters = [ClusterInfo(**c) for c in job.clusters]

        response = AnalysisResponse(
            id=job.id,
            created_at=job.created_at,
            status=APIAnalysisStatus(job.status.value),
            cluster_count=job.cluster_count,
            severity_score=job.severity_score,
            summary=job.summary,
            clusters=clusters,
            error=job.error
        )

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyses", response_model=AnalysisResponse)
async def create_analysis(
    request: Request,
    analysis_request: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create new analysis"""
    try:
        settings = request.app.state.settings

        # Create analysis job
        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            id=job_id,
            namespace=analysis_request.namespace,
            time_range_hours=analysis_request.time_range_hours or 24,
            min_cluster_size=analysis_request.min_cluster_size or 5,
            status=DBAnalysisStatus.PENDING
        )

        db.add(job)
        db.commit()

        # Schedule background task
        background_tasks.add_task(
            run_analysis_task,
            job_id,
            settings,
            analysis_request.namespace,
            analysis_request.time_range_hours or 24,
            analysis_request.min_cluster_size or 5
        )

        response = AnalysisResponse(
            id=job.id,
            created_at=job.created_at,
            status=APIAnalysisStatus(job.status.value),
            cluster_count=None,
            severity_score=None,
            summary=None,
            clusters=None,
            error=None
        )

        return response

    except Exception as e:
        logger.error(f"Error creating analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/analyses/{analysis_id}")
async def delete_analysis(request: Request, analysis_id: str, db: Session = Depends(get_db)):
    """Delete analysis"""
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == analysis_id).first()

        if not job:
            raise HTTPException(status_code=404, detail="Analysis not found")

        db.delete(job)
        db.commit()

        return {"status": "deleted", "id": analysis_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
