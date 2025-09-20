from datetime import date, datetime, timedelta
from typing import List, Optional
from loguru import logger
import time

from ..models.log import DailyAnalysisResult, LogCluster, AnalyzedLog, LogRecord
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

            # Step 4: Calculate statistics
            error_count = len([log for log in logs if log.level in ["ERROR", "CRITICAL"]])
            warning_count = len([log for log in logs if log.level == "WARNING"])

            # Step 5: Generate health score
            logger.info("Step 5: Calculating health score")
            health_score = self.generate_health_score(logs, analyzed_clusters)

            # Step 6: Create top issues list
            top_issues = self.get_top_issues(analyzed_clusters)

            # Step 7: Generate LLM summary
            logger.info("Step 7: Generating LLM summary")
            llm_summary = self._generate_summary(
                len(logs), error_count, warning_count, top_issues
            )

            # Create result
            result = DailyAnalysisResult(
                analysis_date=analysis_date,
                total_logs_processed=len(logs),
                error_count=error_count,
                warning_count=warning_count,
                analyzed_clusters=analyzed_clusters,
                top_issues=top_issues,
                health_score=health_score,
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
                       f"{len(logs)} logs, {len(clusters)} clusters, health: {health_score:.2f}")
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
                         warning_count: int, top_issues: List[AnalyzedLog]) -> str:
        """Generate LLM summary"""
        return self.llm_client.generate_daily_summary(
            total_logs, error_count, warning_count, top_issues
        )


    def _create_empty_result(self, analysis_date: date, execution_time: float) -> DailyAnalysisResult:
        """Create result for when no logs are found"""
        return DailyAnalysisResult(
            analysis_date=analysis_date,
            total_logs_processed=0,
            error_count=0,
            warning_count=0,
            analyzed_clusters=[],
            top_issues=[],
            health_score=1.0,  # Perfect health when no logs
            llm_summary="No logs found in the specified time range.",
            execution_time=execution_time
        )

    def process_log_clusters(self, clusters: List[LogCluster]) -> List[LogCluster]:
        """Process log clusters with LLM analysis"""
        if not clusters:
            logger.info("No clusters to process")
            return []

        logger.info(f"Processing {len(clusters)} log clusters")

        # Rank clusters by severity using LLM
        severity_scores = self.llm_client.rank_severity(clusters)

        # Update clusters with severity scores
        for i, cluster in enumerate(clusters):
            cluster.severity_score = severity_scores[i]

        # Analyze representative logs from high-priority clusters
        high_priority_clusters = [c for c in clusters if getattr(c, 'severity_score', 0) >= 5]

        if high_priority_clusters:
            representative_logs = [c.representative_log for c in high_priority_clusters[:10]]  # Limit for efficiency
            analyzed_logs = self.llm_client.analyze_log_batch(representative_logs)
            # Update with LLM analysis results
            for cluster, analyzed in zip(high_priority_clusters, analyzed_logs):
                cluster.severity_score = max(cluster.severity_score, analyzed.severity)

        logger.info(f"Processed clusters: {len([c for c in clusters if getattr(c, 'severity_score', 0) >= 5])} significant issues found")
        return clusters


    def generate_health_score(self, logs: List[LogRecord], analyzed_clusters: List[LogCluster]) -> float:
        """Generate system health score (0-1 scale)"""
        if not logs:
            return 1.0

        # Calculate basic error/warning ratios
        error_count = len([log for log in logs if log.level in ["ERROR", "CRITICAL"]])
        warning_count = len([log for log in logs if log.level == "WARNING"])
        total_logs = len(logs)

        error_ratio = error_count / total_logs if total_logs > 0 else 0
        warning_ratio = warning_count / total_logs if total_logs > 0 else 0

        # Base health calculation (weighted by severity)
        base_health = 1.0 - (error_ratio * 0.7 + warning_ratio * 0.3)

        # Factor in LLM severity analysis if available
        if analyzed_clusters:
            cluster_scores = [getattr(c, 'severity_score', 5) for c in analyzed_clusters]
            if cluster_scores:
                avg_severity = sum(cluster_scores) / len(cluster_scores)
                # Normalize severity impact (1-10 scale to 0-1)
                severity_impact = (avg_severity - 1) / 9
                # Apply severity impact with diminishing returns
                base_health *= (1 - severity_impact * 0.4)

        # Ensure score is within bounds
        health_score = max(0.0, min(1.0, base_health))

        logger.info(f"Health score calculation: {error_count} errors, {warning_count} warnings, "
                   f"score: {health_score:.3f}")
        return health_score

    def get_top_issues(self, analyzed_clusters: List[LogCluster], max_issues: int = 10) -> List[AnalyzedLog]:
        """Get top issues sorted by severity"""
        if not analyzed_clusters:
            return []

        all_issues = []

        for cluster in analyzed_clusters:
            severity_score = getattr(cluster, 'severity_score', 0)
            if severity_score >= 5:  # Only significant issues
                # Determine category based on severity and log level
                if severity_score >= 8 or cluster.representative_log.level in ["ERROR", "CRITICAL"]:
                    category = "error"
                elif severity_score >= 6 or cluster.representative_log.level == "WARNING":
                    category = "warning"
                else:
                    category = "info"

                analyzed_log = AnalyzedLog(
                    log=cluster.representative_log,
                    severity=severity_score,
                    reasoning=f"Cluster of {cluster.count} similar logs (severity: {severity_score})",
                    category=category
                )
                all_issues.append(analyzed_log)

        # Sort by severity (descending) and return top issues
        all_issues.sort(key=lambda x: x.severity, reverse=True)
        top_issues = all_issues[:max_issues]

        logger.info(f"Identified {len(top_issues)} top issues from {len(analyzed_clusters)} clusters")
        return top_issues