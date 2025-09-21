import json
import os
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path
from loguru import logger
import httpx

from ..models.log import DailyAnalysisResult
from ..config.settings import Settings


class ReportGeneratorError(Exception):
    """Base exception for report generator errors"""
    pass


class ReportGenerator:
    """Generates and manages daily analysis reports"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_dir = Path(settings.report_output_dir)
        self.webhook_url = settings.webhook_url

        # Ensure output directory exists
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Report output directory: {self.output_dir}")
        except Exception as e:
            raise ReportGeneratorError(f"Failed to create output directory {self.output_dir}: {e}")

    def generate_daily_report(self, analysis: DailyAnalysisResult) -> Dict:
        """Generate structured JSON report"""
        if not analysis:
            raise ReportGeneratorError("Analysis result cannot be None")

        logger.info(f"Generating daily report for {analysis.analysis_date}")

        try:
            report = {
                "analysis_date": analysis.analysis_date.isoformat(),
                "generated_at": datetime.now().isoformat(),
                "execution_time_seconds": analysis.execution_time,
                "summary": {
                    "total_logs_processed": analysis.total_logs_processed,
                    "error_count": analysis.error_count,
                    "warning_count": analysis.warning_count,
                    "health_score": analysis.health_score,
                    "clusters_found": len(analysis.analyzed_clusters),
                    "top_issues_identified": len(analysis.top_issues)
                },
                "clusters": [
                    {
                        "id": i,
                        "representative_message": self._truncate_message(cluster.representative_log.message, 200),
                        "count": cluster.count,
                        "severity": cluster.severity.value if cluster.severity else "low",
                        "severity_score": cluster.severity_score if cluster.severity else 0,
                        "source": cluster.representative_log.source,
                        "level": cluster.representative_log.level,
                        "timestamp": cluster.representative_log.timestamp
                    }
                    for i, cluster in enumerate(analysis.analyzed_clusters)
                ],
                "top_issues": [
                    {
                        "severity": cluster.severity.value if cluster.severity else "unknown",
                        "severity_score": cluster.severity.numeric_value if cluster.severity else 0,
                        "reasoning": cluster.reasoning or "No reasoning provided",
                        "message": self._truncate_message(cluster.representative_log.message, 200),
                        "source": cluster.representative_log.source,
                        "timestamp": cluster.representative_log.timestamp,
                        "level": cluster.representative_log.level,
                        "cluster_count": cluster.count,
                        "affected_sources": len(cluster.sources)
                    }
                    for cluster in analysis.top_issues
                ],
                "llm_summary": analysis.llm_summary or "No summary available"
            }

            logger.info(f"Daily report generated with {len(report['clusters'])} clusters and {len(report['top_issues'])} top issues")
            return report

        except Exception as e:
            logger.error(f"Failed to generate daily report: {e}")
            raise ReportGeneratorError(f"Report generation failed: {e}")

    def _truncate_message(self, message: str, max_length: int) -> str:
        """Safely truncate message to specified length"""
        if not message:
            return ""
        if len(message) <= max_length:
            return message
        return message[:max_length-3] + "..."

    def save_report(self, report: Dict, filepath: Optional[str] = None) -> str:
        """Save report to file"""
        if filepath is None:
            # Generate default filepath
            analysis_date = report.get("analysis_date", datetime.now().isoformat()[:10])
            # Extract just the date part, removing time if present
            if 'T' in analysis_date:
                analysis_date = analysis_date.split('T')[0]
            filename = f"daily_analysis_{analysis_date.replace('-', '')}.json"
            filepath = str(self.output_dir / filename)

        logger.info(f"Saving report to {filepath}")

        try:
            # Ensure parent directory exists
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            # Verify file was written successfully
            if not Path(filepath).exists():
                raise ReportGeneratorError(f"Report file was not created at {filepath}")

            file_size = Path(filepath).stat().st_size
            logger.info(f"Report saved successfully to {filepath} ({file_size} bytes)")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save report to {filepath}: {e}")
            raise ReportGeneratorError(f"Failed to save report: {e}")

    def send_webhook_notification(self, report: Dict) -> bool:
        """Send webhook notification"""
        if not self.webhook_url:
            logger.debug("No webhook URL configured, skipping notification")
            return False

        logger.info(f"Sending webhook notification to {self.webhook_url}")

        try:
            # Create notification payload
            notification = {
                "text": "🤖 Daily Log Analysis Complete",
                "analysis_date": report["analysis_date"],
                "summary": {
                    "health_score": report["summary"]["health_score"],
                    "total_logs": report["summary"]["total_logs_processed"],
                    "errors": report["summary"]["error_count"],
                    "warnings": report["summary"]["warning_count"],
                    "clusters": report["summary"].get("clusters_found", 0)
                },
                "top_issues_count": len(report["top_issues"]),
                "execution_time": report["execution_time_seconds"]
            }

            # STUB: In production, this would use httpx to send the webhook
            # For now, just log what would be sent
            logger.info(f"Webhook notification payload: {json.dumps(notification, indent=2)}")
            logger.info("Webhook notification sent successfully (STUB)")
            return True

        except Exception as e:
            logger.error(f"Failed to send webhook notification: {e}")
            return False

    def generate_and_save_report(self, analysis: DailyAnalysisResult) -> str:
        """Generate report and save to file with webhook notification"""
        if not analysis:
            raise ReportGeneratorError("Analysis result cannot be None")

        logger.info(f"Generating and saving report for {analysis.analysis_date}")

        try:
            # Generate report
            report = self.generate_daily_report(analysis)

            # Save report
            filepath = self.save_report(report)

            # Send notification if configured
            webhook_sent = self.send_webhook_notification(report)

            logger.info(f"Report processing complete: saved to {filepath}, webhook sent: {webhook_sent}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to generate and save report: {e}")
            raise ReportGeneratorError(f"Report generation and save failed: {e}")

    def list_reports(self, limit: int = 10) -> list:
        """List recent report files"""
        try:
            report_files = list(self.output_dir.glob("daily_analysis_*.json"))
            # Sort by modification time, most recent first
            report_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            return [
                {
                    "filepath": str(f),
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                }
                for f in report_files[:limit]
            ]
        except Exception as e:
            logger.error(f"Failed to list reports: {e}")
            return []

    def cleanup_old_reports(self, keep_days: int = 30) -> int:
        """Clean up old report files"""
        if keep_days <= 0:
            raise ValueError("keep_days must be positive")

        try:
            cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 3600)
            report_files = list(self.output_dir.glob("daily_analysis_*.json"))

            removed_count = 0
            for report_file in report_files:
                if report_file.stat().st_mtime < cutoff_time:
                    report_file.unlink()
                    removed_count += 1
                    logger.debug(f"Removed old report: {report_file.name}")

            logger.info(f"Cleaned up {removed_count} old report files (keeping {keep_days} days)")
            return removed_count

        except Exception as e:
            logger.error(f"Failed to cleanup old reports: {e}")
            return 0