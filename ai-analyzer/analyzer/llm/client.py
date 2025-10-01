from typing import List, Dict, Any, Optional
from loguru import logger
import json
import time
from dataclasses import dataclass

from openai import OpenAI

from ..models.log import LogRecord, LogCluster, SeverityLevel
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

    def analyze_clusters(self, clusters: List[LogCluster]) -> None:
        """Analyze log clusters and update them with severity and reasoning"""
        if not clusters:
            return

        logger.info(f"Analyzing {len(clusters)} clusters")

        # Create cluster analysis prompt
        prompt = self._create_cluster_analysis_prompt(clusters)
        response = self.call_llm(prompt, max_tokens=2000)

        # Parse JSON response and update clusters
        analysis_data = json.loads(response.content)
        self._update_clusters_with_analysis(clusters, analysis_data)

    def rank_severity(self, clusters: List[LogCluster]) -> List[SeverityLevel]:
        """Rank log clusters by severity level"""
        if not clusters:
            return []

        logger.info(f"Ranking severity for {len(clusters)} clusters")

        prompt = self._create_ranking_prompt(clusters)
        response = self.call_llm(prompt, max_tokens=500)

        # Parse JSON response
        ranking_data = json.loads(response.content)
        scores = ranking_data.get("severity_scores", [])

        if len(scores) != len(clusters):
            raise LLMError(f"LLM returned {len(scores)} scores for {len(clusters)} clusters")

        # Convert numeric scores to SeverityLevel enums
        severity_levels = []
        for score in scores:
            try:
                severity_levels.append(SeverityLevel.from_numeric(score))
            except ValueError as e:
                logger.warning(f"Invalid severity score {score}, defaulting to LOW: {e}")
                severity_levels.append(SeverityLevel.LOW)

        return severity_levels

    def generate_daily_summary(self, total_logs: int, error_count: int, warning_count: int,
                             top_clusters: List[LogCluster]) -> str:
        """Generate daily summary using LLM"""
        logger.info("Generating daily summary with LLM")

        prompt = self._create_summary_prompt(total_logs, error_count, warning_count, top_clusters)
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

        prompt = f"""Analyze these {len(logs)} log entries and assess their severity.

Log entries:
{chr(10).join(log_samples)}

Respond with JSON in this exact format:
{{
  "analyses": [
    {{
      "index": 1,
      "severity": 8,
      "reasoning": "Database connection failure indicates system instability"
    }}
  ]
}}

Severity scale: 1-10 (1=debug info, 5=warning, 8=error, 10=critical)
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
                             top_clusters: List[LogCluster]) -> str:
        """Create prompt for daily summary"""
        error_rate = (error_count / total_logs * 100) if total_logs > 0 else 0
        warning_rate = (warning_count / total_logs * 100) if total_logs > 0 else 0

        issues_text = ""
        if top_clusters:
            issues_text = "Top issues:\n"
            for i, cluster in enumerate(top_clusters[:5], 1):
                severity_text = cluster.severity.value if cluster.severity else "unknown"
                issues_text += f"{i}. [Severity {severity_text}] {cluster.representative_log.message[:100]} (affects {cluster.count} logs)\n"

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

    def _create_cluster_analysis_prompt(self, clusters: List[LogCluster]) -> str:
        """Create prompt for analyzing log clusters"""
        cluster_samples = []
        for i, cluster in enumerate(clusters, 1):
            cluster_samples.append(
                f"{i}. [{cluster.representative_log.level}] {cluster.representative_log.message} "
                f"(occurs {cluster.count} times from {len(cluster.sources)} sources)"
            )

        prompt = f"""Analyze these {len(clusters)} log clusters and assess their severity and provide reasoning.

Log clusters:
{chr(10).join(cluster_samples)}

Respond with JSON in this exact format:
{{
  "analyses": [
    {{
      "index": 1,
      "severity": 8,
      "reasoning": "Database connection failure indicates system instability affecting multiple services"
    }}
  ]
}}

Severity scale: 1-10 (1=debug info, 5=warning, 8=error, 10=critical)
Consider:
- Log level and message content
- Number of occurrences (frequency)
- Number of affected sources
- Impact on system functionality

Provide analysis for ALL {len(clusters)} clusters."""

        return prompt

    def _update_clusters_with_analysis(self, clusters: List[LogCluster], analysis_data: Dict) -> None:
        """Update clusters with LLM analysis results"""
        analyses = analysis_data.get("analyses", [])

        for cluster in clusters:
            # Find matching analysis by index
            analysis = None
            cluster_index = clusters.index(cluster) + 1
            for a in analyses:
                if a.get("index", 0) == cluster_index:
                    analysis = a
                    break

            if not analysis:
                logger.warning(f"Missing analysis for cluster {cluster_index}, using defaults")
                cluster.severity = SeverityLevel.MEDIUM
                cluster.reasoning = "Analysis not available from LLM"
                continue

            # Extract and validate severity
            severity_score = max(1, min(10, analysis.get("severity", 5)))
            reasoning = analysis.get("reasoning", "No specific reasoning provided")

            # Convert numeric severity to SeverityLevel enum
            try:
                cluster.severity = SeverityLevel.from_numeric(severity_score)
            except ValueError:
                logger.warning(f"Invalid severity score {severity_score}, defaulting to MEDIUM")
                cluster.severity = SeverityLevel.MEDIUM

            cluster.reasoning = reasoning


