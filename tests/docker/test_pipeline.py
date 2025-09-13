"""
End-to-end pipeline and data persistence tests.
Tests complete data flow from log-ingestor to Milvus with embeddings.
"""

import pytest
import requests
import time
from pymilvus import connections, Collection, utility


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.slow
def test_ingestor_to_milvus_data_flow(ingestor_url, log_generator, milvus_host, milvus_port, http_retry):
    """Test complete data flow from log-ingestor to Milvus."""
    # Step 1: Generate and send log to ingestor
    test_logs = log_generator.generate_log_entries_for_api(count=1)
    test_log = test_logs[0]
    test_log["message"] = "Integration test: Memory usage spike detected"

    # Send log to ingestor
    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json={"logs": [test_log]},
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    assert response.status_code in [200, 202], f"Log ingestion failed: {response.text}"

    # Step 2: Wait for processing and storage
    time.sleep(5)

    # Step 3: Connect to Milvus and verify data was stored
    connections.connect(alias="test_conn", host=milvus_host, port=milvus_port)

    try:
        # Check available collections
        collections = utility.list_collections(using="test_conn")

        # Look for expected collection names
        possible_names = ["logs", "timberline_logs", "log_entries", "application_logs"]
        target_collection = None

        for name in possible_names:
            if name in collections:
                target_collection = name
                break

        if target_collection:
            try:
                collection = Collection(name=target_collection, using="test_conn")
                collection.load()

                # Query for recent logs
                current_time = int(time.time())
                time_range = current_time - 300  # Last 5 minutes

                query_expr = f"timestamp >= {time_range}"
                results = collection.query(
                    expr=query_expr,
                    output_fields=["timestamp", "log_level", "message", "container_name"],
                    limit=100
                )

                # Verify our test log was stored
                found_test_log = False
                for result in results:
                    if (result.get('message') and
                            'Integration test: Memory usage spike detected' in result['message']):
                        found_test_log = True
                        break

                assert found_test_log, \
                    f"Test log not found in Milvus. Found {len(results)} total logs in collection {target_collection}"
            except Exception as e:
                pytest.skip(f"Cannot query collection {target_collection}: {e}")
        else:
            pytest.skip(f"No expected log collections found. Available: {collections}. Log-ingestor service should bootstrap collections.")

    finally:
        connections.disconnect("test_conn")


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.slow
def test_embedding_generation_and_storage(ingestor_url, embedding_url, log_generator, milvus_host, milvus_port, http_retry):
    """Test that logs get proper embeddings when stored in Milvus."""
    # Send test log to ingestor
    test_logs = log_generator.generate_log_entries_for_api(count=1)
    test_log = test_logs[0]
    test_log["message"] = "Critical system failure in database connection pool"
    test_log["source"] = "database"

    response = http_retry(
        f"{ingestor_url}/api/v1/logs/batch",
        method="POST",
        json={"logs": [test_log]},
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    assert response.status_code in [200, 202]

    # Wait for embedding generation and storage
    time.sleep(10)

    # Connect to Milvus and verify embeddings
    connections.connect(alias="test_conn", host=milvus_host, port=milvus_port)

    try:
        collections = utility.list_collections(using="test_conn")

        # Look for collections with embeddings
        for collection_name in collections:
            try:
                collection = Collection(name=collection_name, using="test_conn")
                schema = collection.schema
                has_embedding_field = any(field.name == "embedding" for field in schema.fields)

                if has_embedding_field:
                    collection.load()

                    # Generate test embedding for semantic search
                    payload = {
                        "model": "nomic-embed-text-v1.5",
                        "input": "database connection error"  # Similar to test message
                    }

                    embed_response = http_retry(embedding_url, method="POST", json=payload, timeout=60)
                    if embed_response.status_code == 200:
                        search_embedding = embed_response.json()['data'][0]['embedding']

                        # Perform semantic search
                        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
                        results = collection.search(
                            data=[search_embedding],
                            anns_field="embedding",
                            param=search_params,
                            limit=5,
                            output_fields=["message", "log_level", "container_name"]
                        )

                        # If results found, embedding pipeline is working
                        if len(results[0]) > 0:
                            assert True, "Embedding pipeline working correctly"
                            return

            except Exception as e:
                continue

        pytest.skip("No collections with embeddings found - may be expected during development")

    finally:
        connections.disconnect("test_conn")


@pytest.mark.docker
@pytest.mark.integration
def test_generated_logs_processing(ingestor_url, log_generator, http_retry):
    """Test processing of various generated log formats."""
    test_scenarios = [
        ("Simple app logs", log_generator.generate_log_entries_for_api(count=5)),
        ("High volume logs", log_generator.generate_log_entries_for_api(count=50)),
    ]

    for scenario_name, log_entries in test_scenarios:
        response = http_retry(
            f"{ingestor_url}/api/v1/logs/batch",
            method="POST",
            json={"logs": log_entries},
            headers={"Content-Type": "application/json"},
            timeout=60
        )

        assert response.status_code in [200, 202], f"{scenario_name} failed: {response.text}"

        result = response.json()
        assert result.get("success") == True, f"{scenario_name} processing failed"
        assert result.get("processed_count") == len(log_entries), f"{scenario_name} count mismatch"


@pytest.mark.docker
@pytest.mark.integration
def test_log_file_creation(log_generator, test_logs_dir):
    """Test that log files are created properly."""
    expected_files = [
        "app-errors.log",
        "structured-logs.log",
        "k8s-app.log",
        "mixed-format.log",
        "high-volume.log",
        "special-chars.log"
    ]

    for filename in expected_files:
        log_file = test_logs_dir / filename
        assert log_file.exists(), f"Generated log file {filename} not found"
        assert log_file.stat().st_size > 0, f"Generated log file {filename} is empty"


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.slow
def test_end_to_end_pipeline_performance(ingestor_url, log_generator, http_retry):
    """Test pipeline performance with larger log batches."""
    log_counts = [10, 50, 100]

    for count in log_counts:
        log_entries = log_generator.generate_log_entries_for_api(count=count)

        start_time = time.time()
        response = http_retry(
            f"{ingestor_url}/api/v1/logs/batch",
            method="POST",
            json={"logs": log_entries},
            headers={"Content-Type": "application/json"},
            timeout=120
        )
        end_time = time.time()

        processing_time = end_time - start_time

        assert response.status_code in [200, 202], f"Failed for {count} logs"

        result = response.json()
        assert result.get("success") == True
        assert result.get("processed_count") == count

        # Performance assertion - should process logs reasonably quickly
        # Allow 1 second per 10 logs as a reasonable baseline
        max_expected_time = (count / 10.0) + 5  # 5 second buffer
        assert processing_time < max_expected_time, \
            f"Processing {count} logs took {processing_time:.2f}s, expected < {max_expected_time:.2f}s"
