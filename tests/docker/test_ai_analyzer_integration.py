"""
AI Analyzer integration tests with complete pipeline.
Tests end-to-end flow: log generation -> Fluent Bit -> ingestor -> Milvus -> AI analysis.
"""

import pytest
import time
from datetime import date
import json
import psycopg2
from .test_helpers import ingest_logs_via_stream


@pytest.mark.docker
class TestAIAnalyzerIntegration:
    """Test AI Analyzer integration with the complete log pipeline."""

    def test_complete_ai_analysis_pipeline(self, log_generator, realistic_log_data,
                                         http_retry, ingestor_url, ai_analyzer_engine, cleanup_milvus_data,
                                         milvus_host, milvus_port):
        """Test complete AI analysis pipeline with both file-based and direct ingestion."""

        # Step 1: Health check first
        print("=== Verifying AI Analyzer health ===")
        health_status = ai_analyzer_engine.health_check()
        print(f"Health check results: {health_status}")
        assert health_status['milvus'], "Milvus must be healthy for integration tests"
        assert health_status['results_store'], "Results store must be healthy for integration tests"

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

        # Step 8: Verify results were stored in PostgreSQL
        print("\n=== Verifying analysis results stored in PostgreSQL ===")
        self._verify_postgres_storage(analysis_date, result)

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

    def _verify_postgres_storage(self, analysis_date, result):
        """Verify that analysis results were stored in PostgreSQL."""
        try:
            # Connect to PostgreSQL
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="timberline",
                user="postgres",
                password="postgres"
            )
            cursor = conn.cursor()

            # Query for the analysis result
            analysis_date_str = analysis_date.isoformat()
            cursor.execute(
                """
                SELECT id, analysis_date, total_logs_processed, error_count, clusters_found
                FROM analysis_results
                WHERE analysis_date = %s
                """,
                (analysis_date_str,)
            )

            row = cursor.fetchone()

            # Verify result was stored
            assert row is not None, f"Analysis result for {analysis_date_str} should be stored in PostgreSQL"

            stored_id, stored_date, stored_logs, stored_errors, stored_clusters = row

            # Verify key fields match
            assert stored_logs == result.total_logs_processed
            assert stored_errors == result.error_count
            assert stored_clusters == len(result.analyzed_clusters)

            print(f"✅ Analysis results verified in PostgreSQL (ID: {stored_id})")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def test_ai_analyzer_health_check_only(self, ai_analyzer_engine):
        """Test AI Analyzer health check without full pipeline."""
        health_status = ai_analyzer_engine.health_check()

        print(f"Health check results: {health_status}")

        # Milvus should be healthy in Docker environment
        assert health_status['milvus'], "Milvus should be healthy"
        assert 'llm' in health_status, "LLM health should be checked"
        assert 'overall' in health_status, "Overall health should be reported"

    def test_analysis_results_stored_in_postgres(self, log_generator, realistic_log_data,
                                                  http_retry, ingestor_url, ai_analyzer_engine,
                                                  cleanup_milvus_data):
        """Test that analysis results are properly stored in PostgreSQL."""

        # Step 1: Ingest realistic logs
        print(f"=== Ingesting {len(realistic_log_data)} logs for analysis ===")
        batch_size = 5
        for i in range(0, len(realistic_log_data), batch_size):
            batch = realistic_log_data[i:i + batch_size]
            response = ingest_logs_via_stream(ingestor_url, batch, timeout=30)
            assert response.status_code == 200, f"Log ingestion failed: {response.text}"

        # Wait for logs to be indexed
        time.sleep(5)

        # Step 2: Run analysis
        print("=== Running AI analysis ===")
        analysis_date = date.today()
        result = ai_analyzer_engine.analyze_daily_logs(analysis_date)

        # Validate basic analysis completed
        assert result.total_logs_processed > 0, "Should have processed logs"
        print(f"Analysis completed: {result.total_logs_processed} logs processed")

        # Step 3: Connect to PostgreSQL and verify analysis results are stored
        print("=== Verifying analysis results in PostgreSQL ===")
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(
                host="localhost",
                port=5432,
                database="timberline",
                user="postgres",
                password="postgres"
            )
            cursor = conn.cursor()

            # Query for today's analysis result
            analysis_date_str = analysis_date.isoformat()
            cursor.execute(
                """
                SELECT
                    id, analysis_date, total_logs_processed, error_count, warning_count,
                    error_rate, clusters_found, top_issues_count, report_data, llm_summary
                FROM analysis_results
                WHERE analysis_date = %s
                """,
                (analysis_date_str,)
            )

            row = cursor.fetchone()

            # Verify we found the analysis result
            assert row is not None, f"Should have found analysis result for {analysis_date_str} in PostgreSQL"

            (stored_id, stored_date, stored_logs, stored_errors, stored_warnings,
             stored_error_rate, stored_clusters, stored_issues, stored_report, stored_summary) = row

            print(f"\n📊 Analysis result stored in PostgreSQL:")
            print(f"  Date: {stored_date}")
            print(f"  Logs Processed: {stored_logs}")
            print(f"  Errors: {stored_errors}")
            print(f"  Warnings: {stored_warnings}")
            print(f"  Clusters: {stored_clusters}")
            print(f"  Top Issues: {stored_issues}")

            # Verify the stored data matches the analysis result
            assert stored_date == analysis_date_str
            assert stored_logs == result.total_logs_processed
            assert stored_errors == result.error_count
            assert stored_warnings == result.warning_count
            assert stored_clusters == len(result.analyzed_clusters)
            assert stored_issues == len(result.top_issues)

            # Verify report data is stored
            assert stored_report is not None, "Report data should be stored"
            assert isinstance(stored_report, dict), "Report data should be a dictionary"

            # Verify LLM summary is stored
            assert stored_summary is not None, "LLM summary should be stored"
            assert len(stored_summary) > 0, "LLM summary should not be empty"

            print("\n✅ Analysis results successfully verified in PostgreSQL!")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
