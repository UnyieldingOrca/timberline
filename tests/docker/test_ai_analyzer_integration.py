"""
AI Analyzer integration tests with complete pipeline.
Tests end-to-end flow: log generation -> Fluent Bit -> ingestor -> Milvus -> AI analysis.
"""

import pytest
import time
from datetime import date
import json
from .test_helpers import ingest_logs_via_stream


@pytest.mark.docker
class TestAIAnalyzerIntegration:
    """Test AI Analyzer integration with the complete log pipeline."""

    def test_complete_ai_analysis_pipeline(self, log_generator, realistic_log_data,
                                         http_retry, ingestor_url, ai_analyzer_engine, cleanup_milvus_data):
        """Test complete AI analysis pipeline with both file-based and direct ingestion."""

        # Step 1: Health check first
        print("=== Verifying AI Analyzer health ===")
        health_status = ai_analyzer_engine.health_check()
        print(f"Health check results: {health_status}")
        assert health_status['milvus'], "Milvus must be healthy for integration tests"

        # Step 2: Generate file-based logs for Fluent Bit collector
        print("=== Generating log files for collector ===")
        app_logs = log_generator.generate_application_logs()
        structured_logs = log_generator.generate_structured_logs()
        k8s_logs = log_generator.generate_kubernetes_logs()
        mixed_logs = log_generator.generate_mixed_format_logs()

        print(f"Generated log files:")
        print(f"  - Application logs: {app_logs}")
        print(f"  - Structured logs: {structured_logs}")
        print(f"  - Kubernetes logs: {k8s_logs}")
        print(f"  - Mixed format logs: {mixed_logs}")

        # Step 4: Ingest realistic log scenarios via direct API
        print(f"\n=== Ingesting {len(realistic_log_data)} realistic log scenarios ===")
        batch_size = 5

        for i in range(0, len(realistic_log_data), batch_size):
            batch = realistic_log_data[i:i + batch_size]
            response = ingest_logs_via_stream(ingestor_url, batch, timeout=30)
            assert response.status_code == 200, f"Log ingestion failed: {response.text}"

            result = response.json()
            assert result.get("success") == True
            print(f"Ingested batch {i//batch_size + 1}: {len(batch)} logs")


        # Step 5: Wait for all logs to be processed and indexed in Milvus
        print("=== Waiting for all logs to be processed in Milvus ===")
        time.sleep(5)

        # Step 6: Run AI analysis on all logs (file-based + direct ingestion)
        print("=== Running AI analysis on complete dataset ===")
        analysis_date = date.today()
        result = ai_analyzer_engine.analyze_daily_logs(analysis_date)

        # Step 7: Validate and display results
        self._validate_analysis_result(result, analysis_date, expected_min_logs=100)
        self._display_analysis_results(result)

    def _validate_analysis_result(self, result, expected_date, expected_min_logs=1):
        """Validate the analysis result structure and content."""
        from analyzer.models.log import DailyAnalysisResult

        assert isinstance(result, DailyAnalysisResult), "Result should be DailyAnalysisResult"
        assert result.total_logs_processed >= expected_min_logs, f"Should have processed at least {expected_min_logs} logs, got {result.total_logs_processed}"
        assert result.analysis_date == expected_date, "Analysis date should match"
        assert result.execution_time > 0, "Execution time should be positive"

        # Validate that we found some errors/warnings from our realistic scenarios
        assert result.error_count > 0, "Should have detected errors from realistic scenarios"

        # Validate that clustering worked if we have enough logs
        if result.total_logs_processed >= 5:
            assert len(result.analyzed_clusters) > 0, "Should have created clusters"

        # Validate that severity scoring worked (either from LLM or fallback)
        if result.analyzed_clusters:
            severity_scores = [getattr(c, 'severity_score', 0) for c in result.analyzed_clusters]
            assert any(score > 0 for score in severity_scores), "Should have severity scores"

    def _display_analysis_results(self, result):
        """Display detailed analysis results for debugging."""
        print(f"\n📊 ANALYSIS RESULTS:")
        print(f"  Date: {result.analysis_date}")
        print(f"  Logs Processed: {result.total_logs_processed}")
        print(f"  Errors: {result.error_count}")
        print(f"  Warnings: {result.warning_count}")
        print(f"  Clusters: {len(result.analyzed_clusters)}")
        print(f"  Top Issues: {len(result.top_issues)}")
        print(f"  Execution Time: {result.execution_time:.2f}s")

        if result.analyzed_clusters:
            print(f"\n🔍 CLUSTER ANALYSIS:")
            for i, cluster in enumerate(result.analyzed_clusters[:5]):
                severity = getattr(cluster, 'severity_score', 'N/A')
                print(f"  Cluster {i+1}: {cluster.count} logs, severity: {severity}")
                print(f"    Representative: {cluster.representative_log.message[:100]}...")

        if result.top_issues:
            print(f"\n🚨 TOP ISSUES:")
            for i, issue in enumerate(result.top_issues[:5]):
                print(f"  Issue {i+1}: [Severity {issue.severity}]")
                print(f"    Message: {issue.representative_log.message}...")
                print(f"    Reasoning: {issue.reasoning[:100]}...")

        print(f"\n📝 LLM SUMMARY:")
        print(f"  {result.llm_summary}")
        print(f"\n✅ AI Analysis integration test completed successfully!")

    def test_ai_analyzer_health_check_only(self, ai_analyzer_engine):
        """Test AI Analyzer health check without full pipeline."""
        health_status = ai_analyzer_engine.health_check()

        print(f"Health check results: {health_status}")

        # Milvus should be healthy in Docker environment
        assert health_status['milvus'], "Milvus should be healthy"
        assert 'llm' in health_status, "LLM health should be checked"
        assert 'overall' in health_status, "Overall health should be reported"
