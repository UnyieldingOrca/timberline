from typing import List, Dict, Any, Optional
from loguru import logger
import json
import time
from dataclasses import dataclass

from openai import OpenAI

from ..models.log import LogRecord, LogCluster, AnalyzedLog, LogCategory
from ..config.settings import Settings


class LLMError(Exception):
    """Base exception for LLM-related errors"""
    pass


class LLMConnectionError(LLMError):
    """Raised when LLM connection fails"""
    pass


class LLMResponseError(LLMError):
    """Raised when LLM returns invalid response"""
    pass


@dataclass
class LLMResponse:
    """Structured LLM response"""
    content: str
    tokens_used: int = 0
    model_name: str = ""
    response_time: float = 0.0


class LLMClient:
    """OpenAI-compatible LLM client for log analysis"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.llm_model

        if not settings.llm_api_key:
            raise LLMError("LLM API key is required")

        # Initialize OpenAI client (supports custom endpoints)
        client_kwargs = {"api_key": settings.llm_api_key}
        if settings.llm_endpoint:
            client_kwargs["base_url"] = settings.llm_endpoint

        self.client = OpenAI(**client_kwargs)
        logger.info(f"Initialized LLM client with model: {settings.llm_model}")

    def call_llm(self, prompt: str, max_tokens: int = 1000) -> LLMResponse:
        """Make a call to the LLM using OpenAI client"""
        start_time = time.time()

        try:
            logger.debug(f"Calling LLM with model {self.model}")

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert log analyzer. Provide structured, accurate analysis."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=0.1  # Low temperature for consistent analysis
            )

            response_time = time.time() - start_time

            content = response.choices[0].message.content
            if not content:
                raise LLMResponseError("Empty response from LLM")

            tokens_used = getattr(response.usage, 'total_tokens', 0) if response.usage else 0

            return LLMResponse(
                content=content.strip(),
                tokens_used=tokens_used,
                model_name=self.model,
                response_time=response_time
            )

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"LLM call failed after {response_time:.1f}s: {e}")

            if "connection" in str(e).lower() or "timeout" in str(e).lower():
                raise LLMConnectionError(f"Failed to connect to LLM: {e}")
            else:
                raise LLMResponseError(f"LLM response error: {e}")

    def health_check(self) -> bool:
        """Check LLM service health"""
        try:
            logger.info("Performing LLM health check")

            # Simple test prompt
            test_prompt = "Respond with 'OK' if you can process this message."
            response = self.call_llm(test_prompt, max_tokens=10)

            if response.content and len(response.content.strip()) > 0:
                logger.info("LLM health check passed")
                return True
            else:
                logger.error("LLM health check failed: empty response")
                return False

        except Exception as e:
            logger.error(f"LLM health check failed: {e}")
            return False

    def analyze_log_batch(self, logs: List[LogRecord]) -> List[AnalyzedLog]:
        """Analyze a batch of logs and return severity assessments"""
        if not logs:
            return []

        logger.info(f"Analyzing batch of {len(logs)} logs")

        try:
            # Create analysis prompt
            prompt = self._create_analysis_prompt(logs)
            response = self.call_llm(prompt, max_tokens=2000)

            # Parse JSON response
            try:
                analysis_data = json.loads(response.content)
                return self._parse_analysis_response(logs, analysis_data)
            except json.JSONDecodeError:
                logger.warning("Failed to parse JSON response, using fallback analysis")
                return self._fallback_log_analysis(logs)

        except Exception as e:
            logger.warning(f"LLM batch analysis failed: {e}, using fallback")
            return self._fallback_log_analysis(logs)

    def rank_severity(self, clusters: List[LogCluster]) -> List[int]:
        """Rank log clusters by severity (1-10 scale)"""
        if not clusters:
            return []

        logger.info(f"Ranking severity for {len(clusters)} clusters")

        try:
            prompt = self._create_ranking_prompt(clusters)
            response = self.call_llm(prompt, max_tokens=500)

            # Parse JSON response
            try:
                ranking_data = json.loads(response.content)
                scores = ranking_data.get("severity_scores", [])

                # Ensure we have scores for all clusters
                while len(scores) < len(clusters):
                    scores.append(self._calculate_fallback_severity(clusters[len(scores)]))

                return scores[:len(clusters)]

            except (json.JSONDecodeError, KeyError):
                logger.warning("Failed to parse ranking response, using fallback")
                return self._fallback_cluster_ranking(clusters)

        except Exception as e:
            logger.warning(f"LLM ranking failed: {e}, using fallback")
            return self._fallback_cluster_ranking(clusters)

    def generate_daily_summary(self, total_logs: int, error_count: int, warning_count: int,
                             top_issues: List[AnalyzedLog]) -> str:
        """Generate daily summary using LLM"""
        logger.info("Generating daily summary with LLM")

        prompt = self._create_summary_prompt(total_logs, error_count, warning_count, top_issues)
        response = self.call_llm(prompt, max_tokens=800)

        summary = response.content.strip()
        if len(summary) < 10:  # Basic validation
            raise LLMResponseError("Summary response too short")

        return summary

    def _create_analysis_prompt(self, logs: List[LogRecord]) -> str:
        """Create prompt for log analysis"""
        log_samples = []
        for i, log in enumerate(logs[:10]):  # Limit to first 10 for prompt size
            log_samples.append(f"{i+1}. [{log.level}] {log.source}: {log.message[:200]}")

        prompt = f"""Analyze these {len(logs)} log entries and assess their severity and category.

Log entries:
{chr(10).join(log_samples)}

Respond with JSON in this exact format:
{{
  "analyses": [
    {{
      "index": 1,
      "severity": 8,
      "category": "error",
      "reasoning": "Database connection failure indicates system instability"
    }}
  ]
}}

Severity scale: 1-10 (1=debug info, 5=warning, 8=error, 10=critical)
Categories: {[cat.value for cat in LogCategory]}
Provide analysis for ALL {len(logs)} logs."""

        return prompt

    def _create_ranking_prompt(self, clusters: List[LogCluster]) -> str:
        """Create prompt for cluster ranking"""
        cluster_info = []
        for i, cluster in enumerate(clusters[:20]):  # Limit for prompt size
            rep_log = cluster.representative_log
            cluster_info.append(f"{i+1}. [{rep_log.level}] {rep_log.source}: {rep_log.message[:150]} (Count: {cluster.count})")

        prompt = f"""Rank these {len(clusters)} log clusters by severity on a 1-10 scale.

Clusters:
{chr(10).join(cluster_info)}

Consider:
- Log level (CRITICAL=10, ERROR=8, WARNING=5, INFO=2, DEBUG=1)
- Message content indicating system issues
- Frequency (cluster count)

Respond with JSON:
{{
  "severity_scores": [8, 10, 5, ...]
}}

Provide exactly {len(clusters)} scores in order."""

        return prompt

    def _create_summary_prompt(self, total_logs: int, error_count: int, warning_count: int,
                             top_issues: List[AnalyzedLog]) -> str:
        """Create prompt for daily summary"""
        error_rate = (error_count / total_logs * 100) if total_logs > 0 else 0
        warning_rate = (warning_count / total_logs * 100) if total_logs > 0 else 0

        issues_text = ""
        if top_issues:
            issues_text = "Top issues:\n"
            for i, issue in enumerate(top_issues[:5], 1):
                issues_text += f"{i}. [Severity {issue.severity}] {issue.log.message[:100]}\n"

        prompt = f"""Generate a concise daily log analysis summary.

Statistics:
- Total logs: {total_logs:,}
- Errors: {error_count} ({error_rate:.1f}%)
- Warnings: {warning_count} ({warning_rate:.1f}%)

{issues_text}

Provide a 2-3 sentence executive summary focusing on:
1. Overall system health
2. Key issues requiring attention
3. Recommended actions if any

Be concise and actionable."""

        return prompt

    def _parse_analysis_response(self, logs: List[LogRecord], analysis_data: Dict) -> List[AnalyzedLog]:
        """Parse LLM analysis response into AnalyzedLog objects"""
        analyzed_logs = []
        analyses = analysis_data.get("analyses", [])

        for log in logs:
            # Find matching analysis by index
            analysis = None
            for a in analyses:
                if a.get("index", 0) == len(analyzed_logs) + 1:
                    analysis = a
                    break

            if analysis:
                severity = max(1, min(10, analysis.get("severity", 5)))
                category = analysis.get("category", "info")
                reasoning = analysis.get("reasoning", "No specific reasoning provided")
            else:
                # Fallback analysis
                severity = self._calculate_fallback_severity_from_log(log)
                category = self._determine_category_from_level(log.level)
                reasoning = f"Fallback analysis based on log level: {log.level}"

            analyzed_logs.append(AnalyzedLog(
                log=log,
                severity=severity,
                reasoning=reasoning,
                category=category
            ))

        return analyzed_logs

    def _fallback_log_analysis(self, logs: List[LogRecord]) -> List[AnalyzedLog]:
        """Fallback analysis when LLM is unavailable"""
        analyzed_logs = []

        for log in logs:
            severity = self._calculate_fallback_severity_from_log(log)
            category = self._determine_category_from_level(log.level)
            reasoning = f"Rule-based analysis: {log.level} level log from {log.source}"

            analyzed_logs.append(AnalyzedLog(
                log=log,
                severity=severity,
                reasoning=reasoning,
                category=category
            ))

        return analyzed_logs

    def _fallback_cluster_ranking(self, clusters: List[LogCluster]) -> List[int]:
        """Fallback severity ranking when LLM is unavailable"""
        return [self._calculate_fallback_severity(cluster) for cluster in clusters]

    def _calculate_fallback_severity(self, cluster: LogCluster) -> int:
        """Calculate fallback severity for a cluster"""
        return self._calculate_fallback_severity_from_log(cluster.representative_log)

    def _calculate_fallback_severity_from_log(self, log: LogRecord) -> int:
        """Calculate fallback severity from log level"""
        severity_map = {
            "CRITICAL": 10,
            "ERROR": 8,
            "WARNING": 5,
            "INFO": 2,
            "DEBUG": 1
        }

        base_severity = severity_map.get(log.level, 3)

        # Boost severity for certain keywords
        message_lower = log.message.lower()
        if any(keyword in message_lower for keyword in ["crash", "panic", "fatal", "failed to start"]):
            base_severity = min(10, base_severity + 2)
        elif any(keyword in message_lower for keyword in ["timeout", "connection", "unavailable"]):
            base_severity = min(10, base_severity + 1)

        return base_severity

    def _determine_category_from_level(self, level: str) -> str:
        """Determine category from log level"""
        if level in ["CRITICAL", "ERROR"]:
            return "error"
        elif level == "WARNING":
            return "warning"
        else:
            return "info"

