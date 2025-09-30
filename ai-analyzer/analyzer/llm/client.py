from typing import List, Dict, Any, Optional
from loguru import logger
import json
import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_openai import ChatOpenAI
from langchain_community.llms import LlamaCpp
from langchain.schema import HumanMessage, SystemMessage
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

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


class ClusterAnalysis(BaseModel):
    """Pydantic model for cluster analysis output"""
    severity: str = Field(description="Severity level: 'low', 'medium', 'high', or 'critical'")
    reasoning: str = Field(description="Detailed reasoning for the severity assessment")
    impact_assessment: str = Field(description="Assessment of potential impact on system")

    def get_severity_enum(self) -> SeverityLevel:
        """Convert severity string to SeverityLevel enum"""
        try:
            return SeverityLevel(self.severity.lower())
        except ValueError:
            # Default to MEDIUM if invalid severity provided
            return SeverityLevel.MEDIUM


class SeverityRanking(BaseModel):
    """Pydantic model for severity ranking output"""
    severity_levels: List[str] = Field(description="List of severity levels: 'low', 'medium', 'high', or 'critical'")

    def get_severity_enums(self) -> List[SeverityLevel]:
        """Convert severity strings to SeverityLevel enums"""
        result = []
        for severity_str in self.severity_levels:
            try:
                result.append(SeverityLevel(severity_str.lower()))
            except ValueError:
                # Default to MEDIUM if invalid severity provided
                result.append(SeverityLevel.MEDIUM)
        return result


class DailySummary(BaseModel):
    """Pydantic model for daily summary output"""
    summary: str = Field(description="Executive summary of the log analysis")
    key_issues: List[str] = Field(description="List of key issues identified")
    recommendations: List[str] = Field(description="List of recommended actions")


class LLMClient:
    """LangChain-based LLM client for log analysis"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.openai_model

        # Initialize LangChain LLM based on provider setting
        if settings.openai_provider == 'llamacpp':
            # Local LLM using llama.cpp
            self.llm = LlamaCpp(
                model_path=settings.openai_model,
                temperature=0.1,
                max_tokens=2000,
                verbose=False,
            )
        elif settings.openai_provider == 'openai':
            # OpenAI-compatible API
            if not settings.openai_api_key:
                raise LLMError("OPENAI_API_KEY is required for OpenAI provider")

            self.llm = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                temperature=0.1,
                max_tokens=2000,
            )
        else:
            raise LLMError(f"Unsupported OpenAI provider: {settings.openai_provider}")

        # Set up output parsers
        self.cluster_parser = PydanticOutputParser(pydantic_object=ClusterAnalysis)
        self.ranking_parser = PydanticOutputParser(pydantic_object=SeverityRanking)
        self.summary_parser = PydanticOutputParser(pydantic_object=DailySummary)

        logger.info(f"Initialized LangChain LLM client with provider: {settings.openai_provider}, model: {settings.openai_model}")

    def call_llm(self, prompt: str, max_tokens: int = 1000) -> LLMResponse:
        """Make a call to the LLM using LangChain"""
        start_time = time.time()

        try:
            logger.debug(f"Calling LLM with model {self.model_name}")

            # Create system and human messages
            messages = [
                SystemMessage(content="You are an expert log analyzer. Provide structured, accurate analysis."),
                HumanMessage(content=prompt)
            ]

            # Call the LLM
            response = self.llm.invoke(messages)
            response_time = time.time() - start_time

            # Extract content based on response type
            if hasattr(response, 'content'):
                content = response.content
            else:
                content = str(response)

            if not content:
                raise LLMResponseError("Empty response from LLM")

            # Extract token usage if available
            tokens_used = 0
            if hasattr(response, 'response_metadata') and 'token_usage' in response.response_metadata:
                tokens_used = response.response_metadata['token_usage'].get('total_tokens', 0)

            return LLMResponse(
                content=content.strip(),
                tokens_used=tokens_used,
                model_name=self.model_name,
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

    def analyze_single_cluster(self, cluster: LogCluster) -> ClusterAnalysis:
        """Analyze a single log cluster using LangChain with structured output"""
        logger.debug(f"Analyzing single cluster with {cluster.count} occurrences")

        # Create the prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            ("human", """Analyze this log cluster and assess its severity, impact, and provide recommendations.

Log Cluster Information:
- Message: {message}
- Level: {level}
- Source: {source}
- Occurrences: {count}
- Affected Sources: {source_count}

Consider:
- Log level and message content
- Frequency of occurrence
- Number of affected sources
- Potential impact on system functionality
- Urgency of required response

{format_instructions}

Assign severity level based on these criteria:
- "low": Informational logs, debugging data, routine operations (not actionable)
- "medium": Warnings, potential issues that might need attention, performance degradation
- "high": Errors requiring attention, service disruptions, failed operations
- "critical": System failures, security incidents, data loss, complete service outages

Choose the most appropriate severity level from: low, medium, high, critical
""")
        ])

        # Format the prompt
        formatted_prompt = prompt_template.format(
            message=cluster.representative_log.message,
            level=cluster.representative_log.level,
            source=cluster.representative_log.source,
            count=cluster.count,
            source_count=len(cluster.sources),
            format_instructions=self.cluster_parser.get_format_instructions()
        )

        try:
            response = self.call_llm(formatted_prompt, max_tokens=1000)
            analysis = self.cluster_parser.parse(response.content)
            return analysis
        except Exception as e:
            logger.error(f"Failed to parse cluster analysis: {e}")
            # Return default analysis
            raise e

    def analyze_clusters(self, clusters: List[LogCluster], max_workers: int = 5) -> None:
        """Analyze log clusters independently using concurrent processing"""
        if not clusters:
            return

        logger.info(f"Analyzing {len(clusters)} clusters independently with {max_workers} workers")

        # Process clusters concurrently
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all cluster analysis tasks
            future_to_cluster = {
                executor.submit(self.analyze_single_cluster, cluster): cluster
                for cluster in clusters
            }

            # Collect results as they complete
            for future in as_completed(future_to_cluster):
                cluster = future_to_cluster[future]
                try:
                    analysis = future.result()

                    # Update cluster with analysis results
                    cluster.severity = analysis.get_severity_enum()
                    cluster.reasoning = analysis.reasoning

                    # Store additional analysis data if the cluster supports it
                    if hasattr(cluster, 'impact_assessment'):
                        cluster.impact_assessment = analysis.impact_assessment
                    if hasattr(cluster, 'recommended_action'):
                        cluster.recommended_action = analysis.recommended_action

                    logger.debug(f"Completed analysis for cluster: {cluster.representative_log.message[:50]}...")

                except Exception as e:
                    logger.error(f"Failed to analyze cluster {cluster.representative_log.message[:50]}: {e}")
                    # Set default values
                    cluster.severity = SeverityLevel.MEDIUM
                    cluster.reasoning = f"Analysis failed: {str(e)}"

        logger.info("Completed independent cluster analysis")

    def rank_severity(self, clusters: List[LogCluster]) -> List[SeverityLevel]:
        """Rank log clusters by severity level using batch processing"""
        if not clusters:
            return []

        logger.info(f"Ranking severity for {len(clusters)} clusters")

        # Create ranking prompt
        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert log analyzer. Assign severity levels to log clusters."),
            ("human", """Assign severity levels to these log clusters.

Clusters:
{cluster_info}

Consider:
- Log level and message content
- Frequency (cluster count)
- Number of affected sources
- Impact on system functionality

{format_instructions}

Assign severity levels based on these criteria:
- "low": Informational logs, debugging data, routine operations (not actionable)
- "medium": Warnings, potential issues that might need attention, performance degradation
- "high": Errors requiring attention, service disruptions, failed operations
- "critical": System failures, security incidents, data loss, complete service outages

Provide exactly {cluster_count} severity levels in the same order as the clusters listed above.
Choose from: low, medium, high, critical
""")
        ])

        # Prepare cluster information
        cluster_info = []
        for i, cluster in enumerate(clusters[:20], 1):  # Limit for prompt size
            rep_log = cluster.representative_log
            cluster_info.append(
                f"{i}. [{rep_log.level}] {rep_log.source}: {rep_log.message[:150]} "
                f"(Count: {cluster.count}, Sources: {len(cluster.sources)})"
            )

        formatted_prompt = prompt_template.format(
            cluster_info="\n".join(cluster_info),
            cluster_count=len(clusters),
            format_instructions=self.ranking_parser.get_format_instructions()
        )

        try:
            response = self.call_llm(formatted_prompt, max_tokens=500)
            ranking = self.ranking_parser.parse(response.content)
            severity_levels = ranking.get_severity_enums()

            if len(severity_levels) != len(clusters):
                raise LLMError(f"LLM returned {len(severity_levels)} severity levels for {len(clusters)} clusters")

            return severity_levels

        except Exception as e:
            logger.error(f"Failed to rank clusters: {e}")
            # Return default rankings
            return [SeverityLevel.MEDIUM for _ in clusters]

    def generate_daily_summary(self, total_logs: int, error_count: int, warning_count: int,
                             top_clusters: List[LogCluster]) -> str:
        """Generate daily summary using LangChain with structured output"""
        logger.info("Generating daily summary with LLM")

        # Calculate rates
        error_rate = (error_count / total_logs * 100) if total_logs > 0 else 0
        warning_rate = (warning_count / total_logs * 100) if total_logs > 0 else 0

        # Prepare top issues information
        issues_info = []
        if top_clusters:
            for i, cluster in enumerate(top_clusters, 1):
                severity_text = cluster.severity.value if cluster.severity else "unknown"
                issues_info.append(
                    f"{i}. [Severity {severity_text}] {cluster.representative_log.message[:100]} "
                    f"(affects {cluster.count} logs)"
                )

        prompt_template = ChatPromptTemplate.from_messages([
            ("system", "You are an expert log analyst generating executive summaries."),
            ("human", """Generate a structured daily log analysis summary.

Statistics:
- Total logs: {total_logs:,}
- Errors: {error_count} ({error_rate:.1f}%)
- Warnings: {warning_count} ({warning_rate:.1f}%)

Top Issues:
{issues_info}

{format_instructions}

Focus on:
1. Overall system health assessment
2. Critical issues requiring immediate attention
3. Actionable recommendations for operations team
""")
        ])

        formatted_prompt = prompt_template.format(
            total_logs=total_logs,
            error_count=error_count,
            error_rate=error_rate,
            warning_count=warning_count,
            warning_rate=warning_rate,
            issues_info="\n".join(issues_info) if issues_info else "No significant issues identified",
            format_instructions=self.summary_parser.get_format_instructions()
        )

        try:
            response = self.call_llm(formatted_prompt, max_tokens=800)
            summary_obj = self.summary_parser.parse(response.content)

            # Format the structured summary into a readable format
            formatted_summary = f"{summary_obj.summary}\n\n"

            if summary_obj.key_issues:
                formatted_summary += "Key Issues:\n"
                for issue in summary_obj.key_issues:
                    formatted_summary += f"- {issue}\n"
                formatted_summary += "\n"

            if summary_obj.recommendations:
                formatted_summary += "Recommendations:\n"
                for rec in summary_obj.recommendations:
                    formatted_summary += f"- {rec}\n"

            return formatted_summary.strip()

        except Exception as e:
            logger.error(f"Failed to generate structured summary: {e}")
            # Fallback to simple summary
            response = self.call_llm(formatted_prompt.replace(
                self.summary_parser.get_format_instructions(),
                "Provide a concise 2-3 sentence summary."
            ), max_tokens=400)

            summary = response.content.strip()
            if len(summary) < 10:
                raise LLMResponseError("Summary response too short")

            return summary