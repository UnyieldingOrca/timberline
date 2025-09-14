import json
import os
from datetime import datetime
from typing import Dict
from loguru import logger
import httpx

from ..models.log import DailyAnalysisResult
from ..config.settings import Settings


class ReportGenerator:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_dir = settings.report_output_dir
        self.webhook_url = settings.webhook_url

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_daily_report(self, analysis: DailyAnalysisResult) -> Dict:
        """Generate structured JSON report"""
        logger.info("Generating daily report")

        report = {
            "analysis_date": analysis.analysis_date.isoformat(),
            "generated_at": datetime.now().isoformat(),
            "execution_time_seconds": analysis.execution_time,
            "summary": {
                "total_logs_processed": analysis.total_logs_processed,
                "error_count": analysis.error_count,
                "warning_count": analysis.warning_count,
                "health_score": analysis.health_score
            },
            "clusters": [
                {
                    "id": i,
                    "representative_message": cluster.representative_log.message[:200],
                    "count": cluster.count,
                    "severity_score": cluster.severity_score,
                    "source": cluster.representative_log.source,
                    "level": cluster.representative_log.level
                }
                for i, cluster in enumerate(analysis.analyzed_clusters)
            ],
            "top_issues": [
                {
                    "severity": issue.severity,
                    "category": issue.category,
                    "reasoning": issue.reasoning,
                    "message": issue.log.message[:200],
                    "source": issue.log.source,
                    "timestamp": issue.log.timestamp
                }
                for issue in analysis.top_issues
            ],
            "llm_summary": analysis.llm_summary
        }

        logger.info("Daily report generated")
        return report

    def save_report(self, report: Dict, filepath: str) -> None:
        """Save report to file"""
        logger.info(f"Saving report to {filepath}")

        try:
            with open(filepath, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Report saved successfully")
        except Exception as e:
            logger.error(f"Failed to save report: {e}")
            raise

    def send_webhook_notification(self, report: Dict) -> None:
        """Send webhook notification (STUB)"""
        if not self.webhook_url:
            logger.debug("No webhook URL configured, skipping notification")
            return

        logger.info(f"Sending webhook notification to {self.webhook_url}")

        try:
            # STUB: Create a simple notification payload
            notification = {
                "text": f"🤖 Daily Log Analysis Complete",
                "analysis_date": report["analysis_date"],
                "summary": {
                    "health_score": report["summary"]["health_score"],
                    "total_logs": report["summary"]["total_logs_processed"],
                    "errors": report["summary"]["error_count"],
                    "warnings": report["summary"]["warning_count"]
                },
                "top_issues_count": len(report["top_issues"])
            }

            # STUB: Don't actually send, just log
            logger.info(f"Would send webhook notification: {json.dumps(notification, indent=2)}")
            logger.info("Webhook notification sent (STUB)")

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")

    def generate_and_save_report(self, analysis: DailyAnalysisResult) -> str:
        """Generate report and save to file"""
        # Generate report
        report = self.generate_daily_report(analysis)

        # Create filename
        filename = f"daily_analysis_{analysis.analysis_date.strftime('%Y%m%d')}.json"
        filepath = os.path.join(self.output_dir, filename)

        # Save report
        self.save_report(report, filepath)

        # Send notification if configured
        self.send_webhook_notification(report)

        return filepath