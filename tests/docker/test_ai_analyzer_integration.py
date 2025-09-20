"""
AI Analyzer integration tests with complete pipeline.
Tests end-to-end flow: log generation -> collector -> ingestor -> Milvus -> AI analysis.
"""

import pytest
import time
from datetime import date
import json


@pytest.mark.docker
class TestAIAnalyzerIntegration:
    """Test AI Analyzer integration with the complete log pipeline."""

    def test_complete_pipeline_with_ai_analysis(self, realistic_log_data, http_retry,
                                              ingestor_url, ai_analyzer_engine):
        """Test complete pipeline: logs -> collector -> ingestor -> Milvus -> AI analysis."""

        # Step 1: Ingest realistic log scenarios via the API
        print(f"\n=== Ingesting {len(realistic_log_data)} realistic log scenarios ===")

        batch_size = 5
        total_ingested = 0

        for i in range(0, len(realistic_log_data), batch_size):
            batch = realistic_log_data[i:i + batch_size]
            response = http_retry(
                f"{ingestor_url}/api/v1/logs/batch",
                method="POST",
                json={"logs": batch},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            assert response.status_code == 200, f"Log ingestion failed: {response.text}"

            result = response.json()
            assert result.get("success") == True
            total_ingested += len(batch)
            print(f"Ingested batch {i//batch_size + 1}: {len(batch)} logs")

        print(f"Total logs ingested: {total_ingested}")

        # Step 2: Wait for logs to be processed and indexed in Milvus
        print("=== Waiting for logs to be processed in Milvus ===")
        time.sleep(5)

        # Step 3: Health check
        print("=== Verifying AI Analyzer health ===")
        health_status = ai_analyzer_engine.health_check()
        print(f"Health check results: {health_status}")

        # Milvus must be healthy for integration tests
        assert health_status['milvus'], "Milvus must be healthy for integration tests"

        # Step 4: Run AI analysis (this is where you can set breakpoints for debugging)
        print("=== Running AI analysis (set breakpoints here for debugging) ===")

        analysis_date = date.today()
        result = ai_analyzer_engine.analyze_daily_logs(analysis_date)

        # Step 5: Validate and display results
        self._validate_analysis_result(result, analysis_date)
        self._display_analysis_results(result)

    def _validate_analysis_result(self, result, expected_date):
        """Validate the analysis result structure and content."""
        # Import here to avoid path issues
        from analyzer.models.log import DailyAnalysisResult

        assert isinstance(result, DailyAnalysisResult), "Result should be DailyAnalysisResult"
        assert result.total_logs_processed > 0, f"Should have processed logs, got {result.total_logs_processed}"
        assert result.analysis_date == expected_date, "Analysis date should match"
        assert 0 <= result.health_score <= 1, f"Health score should be 0-1, got {result.health_score}"
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
        print(f"  Health Score: {result.health_score:.3f}")
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
                print(f"  Issue {i+1}: [Severity {issue.severity}] {issue.category}")
                print(f"    Message: {issue.log.message[:100]}...")
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

    def test_ai_analyzer_with_file_logs(self, log_generator, ai_analyzer_engine):
        """Test AI Analyzer with file-based logs (collector pipeline)."""

        # Generate log files that the collector can pick up
        print("=== Generating log files for collector ===")

        # Create a variety of log files
        app_logs = log_generator.generate_application_logs()
        structured_logs = log_generator.generate_structured_logs()
        k8s_logs = log_generator.generate_kubernetes_logs()
        mixed_logs = log_generator.generate_mixed_format_logs()

        print(f"Generated log files:")
        print(f"  - Application logs: {app_logs}")
        print(f"  - Structured logs: {structured_logs}")
        print(f"  - Kubernetes logs: {k8s_logs}")
        print(f"  - Mixed format logs: {mixed_logs}")

        # Wait for collector to process files
        print("=== Waiting for collector to process log files ===")
        time.sleep(8)  # Collector flush interval + processing time

        # Now run AI analysis
        print("=== Running AI analysis on file-based logs ===")
        result = ai_analyzer_engine.analyze_daily_logs(date.today())

        print(f"\n📊 File-based analysis results:")
        print(f"  Logs processed: {result.total_logs_processed}")
        print(f"  Health score: {result.health_score:.3f}")
        print(f"  Clusters: {len(result.analyzed_clusters)}")

        # Should have processed some logs from the files
        assert result.total_logs_processed > 0, "Should have processed logs from files"


@pytest.mark.docker
@pytest.mark.slow
class TestAIAnalyzerPerformance:
    """Test AI Analyzer performance with larger datasets."""

    def test_high_volume_log_analysis(self, log_generator, ingestor_url, http_retry,
                                     ai_analyzer_engine, realistic_log_data):
        """Test AI Analyzer with high volume of logs."""

        print("=== Generating high volume logs ===")
        high_volume_logs = log_generator.generate_log_entries_for_api(count=100)
        all_logs = high_volume_logs + realistic_log_data

        print(f"Generated {len(all_logs)} total logs for high volume test")

        # Ingest all logs
        print("=== Ingesting high volume logs ===")
        batch_size = 20
        for i in range(0, len(all_logs), batch_size):
            batch = all_logs[i:i + batch_size]
            response = http_retry(
                f"{ingestor_url}/api/v1/logs/batch",
                method="POST",
                json={"logs": batch},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            assert response.status_code == 200

        print("Waiting for processing...")
        time.sleep(10)

        # Run analysis and measure performance
        print("=== Running performance analysis ===")
        start_time = time.time()
        result = ai_analyzer_engine.analyze_daily_logs(date.today())
        analysis_duration = time.time() - start_time

        print(f"\n⚡ Performance Results:")
        print(f"  Total analysis time: {analysis_duration:.2f}s")
        print(f"  Logs processed: {result.total_logs_processed}")
        print(f"  Logs per second: {result.total_logs_processed / analysis_duration:.2f}")
        print(f"  Clusters created: {len(result.analyzed_clusters)}")

        # Performance assertions
        assert analysis_duration < 60, f"Analysis should complete within 60s, took {analysis_duration:.2f}s"
        assert result.total_logs_processed > 50, "Should process significant number of logs"