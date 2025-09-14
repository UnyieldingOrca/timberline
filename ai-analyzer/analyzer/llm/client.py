from typing import List
from loguru import logger
import random

from ..models.log import LogRecord, LogCluster, AnalyzedLog
from ..config.settings import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key
        self.endpoint = settings.llm_endpoint

    def analyze_log_batch(self, logs: List[LogRecord]) -> List[AnalyzedLog]:
        """Analyze a batch of logs with LLM (STUB)"""
        logger.info(f"Analyzing {len(logs)} logs with LLM")

        analyzed_logs = []
        for log in logs:
            # STUB: Generate fake analysis based on log level
            if log.level == "ERROR":
                severity = random.randint(7, 10)
                reasoning = f"Critical error detected in {log.source}: {log.message[:50]}..."
                category = "error"
            elif log.level == "WARNING":
                severity = random.randint(4, 6)
                reasoning = f"Warning condition in {log.source}: potential issue"
                category = "warning"
            else:
                severity = random.randint(1, 3)
                reasoning = f"Normal operation log from {log.source}"
                category = "info"

            analyzed_logs.append(AnalyzedLog(
                log=log,
                severity=severity,
                reasoning=reasoning,
                category=category
            ))

        logger.info(f"Completed LLM analysis of {len(analyzed_logs)} logs (STUB)")
        return analyzed_logs

    def rank_severity(self, log_clusters: List[LogCluster]) -> List[int]:
        """Rank log clusters by severity (STUB)"""
        logger.info(f"Ranking severity for {len(log_clusters)} clusters")

        severity_scores = []
        for cluster in log_clusters:
            rep_log = cluster.representative_log
            if rep_log.level == "ERROR":
                score = random.randint(8, 10)
            elif rep_log.level == "WARNING":
                score = random.randint(5, 7)
            else:
                score = random.randint(1, 4)

            severity_scores.append(score)
            cluster.severity_score = score

        logger.info(f"Completed severity ranking (STUB)")
        return severity_scores

    def generate_daily_summary(self, total_logs: int, error_count: int, warning_count: int,
                             top_issues: List[AnalyzedLog]) -> str:
        """Generate daily summary with LLM (STUB)"""
        logger.info("Generating daily summary with LLM")

        # STUB: Generate a basic summary
        summary = f"""
Daily Log Analysis Summary:

📊 **Statistics:**
- Total logs processed: {total_logs}
- Errors: {error_count}
- Warnings: {warning_count}

🔍 **Top Issues:**
"""

        for i, issue in enumerate(top_issues[:5], 1):
            summary += f"{i}. {issue.category.upper()}: {issue.reasoning}\n"

        summary += """
🏥 **System Health:** Based on the analysis, the system shows some concerning patterns that require attention.

💡 **Recommendations:**
- Investigate recurring error patterns
- Monitor resource usage
- Review application logs for anomalies
"""

        logger.info("Generated daily summary (STUB)")
        return summary.strip()

    def health_check(self) -> bool:
        """Check LLM service health (STUB)"""
        logger.info(f"Checking {self.provider} LLM service health")
        # STUB: Always return healthy
        return True