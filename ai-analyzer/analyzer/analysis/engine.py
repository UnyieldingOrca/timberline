from datetime import date, datetime, timedelta
from typing import List
from loguru import logger
import time

from ..models.log import DailyAnalysisResult, LogCluster, AnalyzedLog
from ..storage.milvus_client import MilvusQueryEngine
from ..llm.client import LLMClient
from ..reporting.generator import ReportGenerator
from ..config.settings import Settings


class AnalysisEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.validate()

        # Initialize components
        self.milvus_client = MilvusQueryEngine(settings)
        self.llm_client = LLMClient(settings)
        self.report_generator = ReportGenerator(settings)

        logger.info("Analysis engine initialized")

    def analyze_daily_logs(self, analysis_date: date) -> DailyAnalysisResult:
        """Orchestrate the daily analysis pipeline"""
        start_time = time.time()
        logger.info(f"Starting daily analysis for {analysis_date}")

        # Calculate time range (24 hours ending at the analysis date)
        end_datetime = datetime.combine(analysis_date, datetime.min.time()) + timedelta(days=1)
        start_datetime = end_datetime - timedelta(hours=self.settings.analysis_window_hours)

        try:
            # Step 1: Query logs from Milvus
            logger.info("Step 1: Querying logs from Milvus")
            logs = self.milvus_client.query_time_range(start_datetime, end_datetime)

            # Step 2: Cluster similar logs
            logger.info("Step 2: Clustering similar logs")
            clusters = self.milvus_client.cluster_similar_logs(logs)

            # Step 3: LLM analysis
            logger.info("Step 3: Running LLM analysis")
            analyzed_clusters = self.process_log_clusters(clusters)

            # Step 4: Generate health score
            logger.info("Step 4: Calculating health score")
            health_score = self.generate_health_score(logs, analyzed_clusters)

            # Step 5: Create top issues list
            top_issues = self.get_top_issues(analyzed_clusters)

            # Step 6: Generate LLM summary
            error_count = len([log for log in logs if log.level == "ERROR"])
            warning_count = len([log for log in logs if log.level == "WARNING"])

            llm_summary = self.llm_client.generate_daily_summary(
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

            # Step 7: Generate and save report
            logger.info("Step 7: Generating report")
            self.report_generator.generate_and_save_report(result)

            logger.info(f"Daily analysis completed in {result.execution_time:.2f}s")
            return result

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise

    def process_log_clusters(self, clusters: List[LogCluster]) -> List[LogCluster]:
        """Process log clusters with LLM analysis"""
        logger.info(f"Processing {len(clusters)} log clusters")

        # Rank clusters by severity
        self.llm_client.rank_severity(clusters)

        # Analyze representative logs from each cluster
        representative_logs = [cluster.representative_log for cluster in clusters]
        analyzed_logs = self.llm_client.analyze_log_batch(representative_logs)

        # Update clusters with analysis results
        for cluster, analyzed in zip(clusters, analyzed_logs):
            cluster.severity_score = analyzed.severity

        return clusters

    def generate_health_score(self, logs: List, analyzed_clusters: List[LogCluster]) -> float:
        """Generate system health score (0-1 scale)"""
        if not logs:
            return 1.0

        error_ratio = len([log for log in logs if log.level == "ERROR"]) / len(logs)
        warning_ratio = len([log for log in logs if log.level == "WARNING"]) / len(logs)

        # Simple health calculation
        health_score = 1.0 - (error_ratio * 0.6 + warning_ratio * 0.3)

        # Factor in LLM severity scores
        if analyzed_clusters:
            avg_severity = sum(c.severity_score or 1 for c in analyzed_clusters) / len(analyzed_clusters)
            severity_impact = (avg_severity - 1) / 9  # Normalize to 0-1
            health_score *= (1 - severity_impact * 0.3)

        return max(0.0, min(1.0, health_score))

    def get_top_issues(self, analyzed_clusters: List[LogCluster]) -> List[AnalyzedLog]:
        """Get top issues sorted by severity"""
        all_issues = []

        for cluster in analyzed_clusters:
            if cluster.severity_score and cluster.severity_score >= 5:  # Only significant issues
                analyzed_log = AnalyzedLog(
                    log=cluster.representative_log,
                    severity=cluster.severity_score,
                    reasoning=f"Cluster of {cluster.count} similar logs with severity {cluster.severity_score}",
                    category="error" if cluster.severity_score >= 7 else "warning"
                )
                all_issues.append(analyzed_log)

        # Sort by severity and return top 10
        all_issues.sort(key=lambda x: x.severity, reverse=True)
        return all_issues[:10]