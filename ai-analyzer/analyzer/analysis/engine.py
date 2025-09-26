from datetime import date, datetime, timedelta
from typing import List, Optional
from loguru import logger
import time

from ..models.log import DailyAnalysisResult, LogCluster, LogRecord, SeverityLevel
from ..storage.milvus_client import MilvusQueryEngine, MilvusConnectionError
from ..llm.client import LLMClient
from ..reporting.generator import ReportGenerator, ReportGeneratorError
from ..config.settings import Settings


class AnalysisEngineError(Exception):
    """Base exception for analysis engine errors"""
    pass


class AnalysisEngine:
    """Orchestrates the complete daily log analysis pipeline"""

    def __init__(self, settings: Settings):
        self.settings = settings

        try:
            settings.validate()
        except Exception as e:
            raise AnalysisEngineError(f"Invalid settings: {e}")

        # Initialize components
        try:
            self.milvus_client = MilvusQueryEngine(settings)
            self.llm_client = LLMClient(settings)
            self.report_generator = ReportGenerator(settings)
            logger.info("Analysis engine initialized successfully")
        except Exception as e:
            raise AnalysisEngineError(f"Failed to initialize analysis engine: {e}")

    def health_check(self) -> dict:
        """Check health of all components"""
        health_status = {
            "milvus": False,
            "llm": False,
            "report_generator": True,  # No external dependencies
            "overall": False
        }

        try:
            health_status["milvus"] = self.milvus_client.health_check()
        except Exception as e:
            logger.error(f"Milvus health check failed: {e}")

        try:
            health_status["llm"] = self.llm_client.health_check()
        except Exception as e:
            logger.error(f"LLM health check failed: {e}")

        health_status["overall"] = all([
            health_status["milvus"],
            health_status["llm"],
            health_status["report_generator"]
        ])

        logger.info(f"Health check results: {health_status}")
        return health_status

    def analyze_daily_logs(self, analysis_date: date) -> DailyAnalysisResult:
        """Orchestrate the daily analysis pipeline"""
        if not isinstance(analysis_date, date):
            raise AnalysisEngineError("analysis_date must be a date object")

        start_time = time.time()
        logger.info(f"Starting daily analysis for {analysis_date}")

        # Check LLM health before proceeding
        if not self.llm_client.health_check():
            raise AnalysisEngineError("LLM is not available - analysis requires LLM to function")

        # Calculate time range (analysis window ending at the analysis date)
        end_datetime = datetime.combine(analysis_date, datetime.min.time()) + timedelta(days=1)
        start_datetime = end_datetime - timedelta(hours=self.settings.analysis_window_hours)

        logger.info(f"Analysis window: {start_datetime} to {end_datetime}")

        try:
            # Step 1: Query logs from Milvus
            logger.info("Step 1: Querying logs from Milvus")
            logs = self._query_logs_with_retry(start_datetime, end_datetime)

            if not logs:
                logger.warning("No logs found in the specified time range")
                return self._create_empty_result(analysis_date, time.time() - start_time)

            # Step 2: Cluster similar logs
            logger.info(f"Step 2: Clustering {len(logs)} logs")
            clusters = self.milvus_client.cluster_similar_logs(logs)
            logger.info(f"Created {len(clusters)} clusters")

            # Step 3: LLM analysis
            logger.info("Step 3: Running LLM analysis")
            analyzed_clusters = self.process_log_clusters(clusters)

            # Step 4: Calculate statistics (accounting for duplicate counts)
            total_actual_logs = sum(log.duplicate_count for log in logs)
            error_count = sum(log.duplicate_count for log in logs if log.level in ["ERROR", "CRITICAL"])
            warning_count = sum(log.duplicate_count for log in logs if log.level == "WARNING")

            # Step 6: Generate LLM summary
            logger.info("Step 6: Generating LLM summary")
            top_clusters = [c for c in analyzed_clusters if c.is_actionable()][:10]
            llm_summary = self._generate_summary(
                total_actual_logs, error_count, warning_count, top_clusters
            )

            # Create result
            result = DailyAnalysisResult(
                analysis_date=analysis_date,
                total_logs_processed=total_actual_logs,
                error_count=error_count,
                warning_count=warning_count,
                analyzed_clusters=analyzed_clusters,
                llm_summary=llm_summary,
                execution_time=time.time() - start_time
            )

            # Step 8: Generate and save report
            logger.info("Step 8: Generating report")
            try:
                report_path = self.report_generator.generate_and_save_report(result)
                logger.info(f"Report saved to: {report_path}")
            except ReportGeneratorError as e:
                logger.error(f"Report generation failed: {e}")
                # Don't fail the entire analysis for report issues

            logger.info(f"Daily analysis completed in {result.execution_time:.2f}s - "
                       f"{len(logs)} unique logs ({total_actual_logs} total including duplicates), {len(clusters)} clusters")
            return result

        except MilvusConnectionError as e:
            logger.error(f"Milvus connection failed: {e}")
            raise AnalysisEngineError(f"Database connection failed: {e}")
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise AnalysisEngineError(f"Analysis pipeline failed: {e}")

    def _query_logs_with_retry(self, start_datetime: datetime, end_datetime: datetime,
                              max_retries: int = 3) -> List[LogRecord]:
        """Query logs with retry logic"""
        for attempt in range(max_retries):
            try:
                return self.milvus_client.query_time_range(start_datetime, end_datetime)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Log query attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(2 ** attempt)  # Exponential backoff

        return []

    def _generate_summary(self, total_logs: int, error_count: int,
                         warning_count: int, top_clusters: List[LogCluster]) -> str:
        """Generate LLM summary"""
        return self.llm_client.generate_daily_summary(
            total_logs, error_count, warning_count, top_clusters
        )


    def _create_empty_result(self, analysis_date: date, execution_time: float) -> DailyAnalysisResult:
        """Create result for when no logs are found"""
        return DailyAnalysisResult(
            analysis_date=analysis_date,
            total_logs_processed=0,
            error_count=0,
            warning_count=0,
            analyzed_clusters=[],
            llm_summary="No logs found in the specified time range.",
            execution_time=execution_time
        )

    def process_log_clusters(self, clusters: List[LogCluster]) -> List[LogCluster]:
        """Process log clusters with LLM analysis"""
        if not clusters:
            logger.info("No clusters to process")
            return []

        logger.info(f"Processing {len(clusters)} log clusters")

        # Analyze clusters directly using LLM
        self.llm_client.analyze_clusters(clusters)

        # Count actionable clusters
        actionable_clusters = [c for c in clusters if c.is_actionable()]
        logger.info(f"Processed clusters: {len(actionable_clusters)} actionable issues found")
        return clusters


