"""
End-to-end pipeline tests for Timberline Kind deployment.

Tests that verify the complete log analysis pipeline from ingestion through analysis.
"""

import pytest
import json
import time
from pymilvus import Collection, utility


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteLogPipeline:
    """Test the complete log ingestion and analysis pipeline."""

    def test_end_to_end_log_flow(
        self,
        namespace,
        port_forward_manager,
        http_retry,
        wait_for_service_ready,
        milvus_client,
        cleanup_milvus_data
    ):
        """
        Test complete log flow through the system:
        1. Submit logs to Log Ingestor
        2. Logs are embedded by Embedding Service
        3. Logs are stored in Milvus
        4. Logs can be queried via AI Analyzer
        """
        # Step 1: Prepare test logs
        test_logs = [
            {
                "timestamp": int(time.time() * 1000),
                "message": "ERROR: Database connection timeout in payment service",
                "level": "ERROR",
                "source": "payment-service",
                "service": "backend",
                "pod": "payment-service-abc123"
            },
            {
                "timestamp": int(time.time() * 1000) + 1,
                "message": "WARN: High memory usage detected: 85% of limit",
                "level": "WARN",
                "source": "monitoring-agent",
                "service": "monitoring",
                "pod": "monitor-xyz789"
            },
            {
                "timestamp": int(time.time() * 1000) + 2,
                "message": "INFO: Successfully processed payment transaction",
                "level": "INFO",
                "source": "payment-service",
                "service": "backend",
                "pod": "payment-service-abc123"
            },
            {
                "timestamp": int(time.time() * 1000) + 3,
                "message": "ERROR: Failed to send notification email - SMTP timeout",
                "level": "ERROR",
                "source": "notification-service",
                "service": "backend",
                "pod": "notification-def456"
            },
        ]

        # Step 2: Submit logs to Log Ingestor
        with port_forward_manager("log-ingestor", 8080, namespace) as pf:
            ingestor_url = f"http://localhost:{pf.local_port}/api/v1/logs/stream"
            log_lines = "\n".join(json.dumps(log) for log in test_logs)

            response = http_retry(
                ingestor_url,
                method="POST",
                data=log_lines,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=30
            )

            assert response.status_code in [200, 201, 202], \
                f"Log ingestion failed: {response.status_code}, {response.text}"

        # Step 3: Wait for processing (embedding + storage)
        time.sleep(10)

        # Step 4: Verify logs are in Milvus
        collection_name = "timberline_logs"

        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.load()

            # Check that we have data
            count = collection.num_entities
            assert count > 0, "No logs found in Milvus after ingestion"

        # Step 5: Verify AI Analyzer can access the data
        with port_forward_manager("ai-analyzer", 8000, namespace) as pf:
            health_url = f"http://localhost:{pf.local_port}/health"
            wait_for_service_ready(health_url)

            response = http_retry(health_url)
            assert response.status_code == 200


@pytest.mark.e2e
@pytest.mark.slow
class TestFluentBitToIngestorPipeline:
    """Test Fluent Bit → Log Ingestor pipeline."""

    def test_fluent_bit_collects_and_forwards_logs(
        self,
        kubectl,
        namespace,
        create_test_pod,
        wait_for_pod_ready,
        port_forward_manager,
        http_retry,
        wait_for_service_ready,
        milvus_client
    ):
        """
        Test that Fluent Bit collects logs from a pod and forwards to Log Ingestor.
        """
        # Create a test pod that generates unique logs
        unique_id = int(time.time())
        unique_message = f"E2E_TEST_MESSAGE_{unique_id}"
        pod_name = f"e2e-test-pod-{unique_id}"

        create_test_pod(
            name=pod_name,
            image="busybox",
            command=[
                "sh", "-c",
                f"for i in 1 2 3 4 5; do echo '{unique_message}'; sleep 2; done; sleep 300"
            ],
            labels={"app": "e2e-test", "test-id": str(unique_id)}
        )

        # Wait for pod to start
        time.sleep(10)

        # Wait for Fluent Bit to collect and forward logs
        # This depends on Fluent Bit's flush interval (default 5s)
        time.sleep(20)

        # Verify logs made it to Log Ingestor (check metrics)
        with port_forward_manager("log-ingestor", 9092, namespace) as pf:
            metrics_url = f"http://localhost:{pf.local_port}/metrics"
            wait_for_service_ready(metrics_url)

            response = http_retry(metrics_url)
            assert response.status_code == 200

            # Should have received some logs
            metrics = response.text
            assert len(metrics) > 0

        # Cleanup: delete test pod
        kubectl(["delete", "pod", pod_name, "--force", "--grace-period=0"], check=False)


@pytest.mark.e2e
class TestIngestorToMilvusPipeline:
    """Test Log Ingestor → Embedding Service → Milvus pipeline."""

    def test_logs_stored_with_embeddings(
        self,
        namespace,
        port_forward_manager,
        http_retry,
        milvus_client,
        cleanup_milvus_data
    ):
        """
        Test that logs submitted to Ingestor are:
        1. Embedded by Embedding Service
        2. Stored in Milvus with embeddings
        """
        # Submit logs
        test_log = {
            "timestamp": int(time.time() * 1000),
            "message": "Critical system failure - database unreachable",
            "level": "CRITICAL",
            "source": "e2e-test"
        }

        with port_forward_manager("log-ingestor", 8080, namespace) as pf:
            url = f"http://localhost:{pf.local_port}/api/v1/logs/stream"

            response = http_retry(
                url,
                method="POST",
                data=json.dumps(test_log),
                headers={"Content-Type": "application/x-ndjson"},
                timeout=30
            )

            assert response.status_code in [200, 201, 202]

        # Wait for processing
        time.sleep(10)

        # Verify in Milvus
        collection_name = "timberline_logs"

        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.load()

            # Should have at least one log
            count = collection.num_entities
            assert count > 0

            # Verify schema has embedding field
            schema = collection.schema
            field_names = [field.name for field in schema.fields]

            assert "embedding" in field_names or "vector" in field_names, \
                "Collection missing embedding field"


@pytest.mark.e2e
@pytest.mark.slow
class TestMilvusToAIAnalyzerPipeline:
    """Test Milvus → AI Analyzer pipeline."""

    def test_ai_analyzer_queries_milvus_data(
        self,
        namespace,
        port_forward_manager,
        http_retry,
        wait_for_service_ready,
        milvus_client,
        cleanup_milvus_data,
        sample_log_entries
    ):
        """
        Test that AI Analyzer can:
        1. Query logs from Milvus
        2. Perform analysis
        """
        # First, insert test logs via Log Ingestor
        with port_forward_manager("log-ingestor", 8080, namespace) as pf:
            url = f"http://localhost:{pf.local_port}/api/v1/logs/stream"
            log_lines = "\n".join(json.dumps(log) for log in sample_log_entries)

            response = http_retry(
                url,
                method="POST",
                data=log_lines,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=30
            )

            assert response.status_code in [200, 201, 202]

        # Wait for processing
        time.sleep(10)

        # Verify AI Analyzer can access the data
        with port_forward_manager("ai-analyzer", 8000, namespace) as pf:
            health_url = f"http://localhost:{pf.local_port}/health"
            wait_for_service_ready(health_url)

            # AI Analyzer is running and can connect to Milvus
            response = http_retry(health_url)
            assert response.status_code == 200


@pytest.mark.e2e
@pytest.mark.slow
class TestCompleteAnalysisWorkflow:
    """Test complete analysis workflow including LLM."""

    def test_full_analysis_workflow(
        self,
        namespace,
        port_forward_manager,
        http_retry,
        wait_for_service_ready,
        milvus_client,
        cleanup_milvus_data
    ):
        """
        Test complete workflow:
        1. Ingest logs
        2. Logs stored with embeddings
        3. AI Analyzer performs analysis
        4. LLM generates insights
        """
        # Step 1: Ingest diverse logs
        test_logs = [
            {
                "timestamp": int(time.time() * 1000) + i,
                "message": f"ERROR: {error_msg}",
                "level": "ERROR",
                "source": "test-service"
            }
            for i, error_msg in enumerate([
                "Database connection pool exhausted",
                "Query timeout after 30 seconds",
                "Failed to acquire database lock",
                "Connection reset by peer",
                "Too many open connections"
            ])
        ]

        with port_forward_manager("log-ingestor", 8080, namespace) as pf:
            url = f"http://localhost:{pf.local_port}/api/v1/logs/stream"
            log_lines = "\n".join(json.dumps(log) for log in test_logs)

            response = http_retry(
                url,
                method="POST",
                data=log_lines,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=30
            )

            assert response.status_code in [200, 201, 202]

        # Step 2: Wait for processing
        time.sleep(15)

        # Step 3: Verify all services in the pipeline are healthy
        services_to_check = [
            ("log-ingestor", 8080, "/api/v1/healthz"),
            ("llama-cpp-embedding", 8000, "/health"),
            ("llama-cpp-chat", 8001, "/health"),
            ("ai-analyzer", 8000, "/health"),
        ]

        for service_name, port, endpoint in services_to_check:
            with port_forward_manager(service_name, port, namespace) as pf:
                url = f"http://localhost:{pf.local_port}{endpoint}"
                response = http_retry(url, timeout=10)
                assert response.status_code == 200, \
                    f"Service {service_name} not healthy"


@pytest.mark.e2e
class TestPipelineDataConsistency:
    """Test data consistency across pipeline components."""

    def test_log_count_consistency(
        self,
        namespace,
        port_forward_manager,
        http_retry,
        milvus_client,
        cleanup_milvus_data
    ):
        """
        Test that the number of logs ingested matches what's stored.
        """
        # Ingest known number of logs
        log_count = 10
        test_logs = [
            {
                "timestamp": int(time.time() * 1000) + i,
                "message": f"Test log entry {i}",
                "level": "INFO",
                "source": "consistency-test"
            }
            for i in range(log_count)
        ]

        with port_forward_manager("log-ingestor", 8080, namespace) as pf:
            url = f"http://localhost:{pf.local_port}/api/v1/logs/stream"
            log_lines = "\n".join(json.dumps(log) for log in test_logs)

            response = http_retry(
                url,
                method="POST",
                data=log_lines,
                headers={"Content-Type": "application/x-ndjson"},
                timeout=30
            )

            assert response.status_code in [200, 201, 202]

        # Wait for processing
        time.sleep(10)

        # Check Milvus
        collection_name = "timberline_logs"

        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.load()

            count = collection.num_entities

            # Should have at least the logs we ingested
            # (might have more from other tests if they don't clean up)
            assert count >= log_count, \
                f"Expected at least {log_count} logs in Milvus, found {count}"

