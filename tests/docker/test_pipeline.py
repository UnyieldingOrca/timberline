"""
End-to-end pipeline and data persistence tests.
Tests complete data flow from log-collector through log-ingestor to Milvus with embeddings.
"""

import time
import json

from pymilvus import connections, Collection, utility


def test_complete_pipeline_file_to_milvus(test_logs_dir, milvus_host, milvus_port, http_retry):
    """Test complete pipeline: log file -> collector -> ingestor -> Milvus."""
    # Step 1: Create a unique test log file that the collector will monitor
    test_message = f"PIPELINE_TEST_{int(time.time())}: Critical database connection failure"
    log_file = test_logs_dir / f"pipeline-test_{int(time.time())}.log"

    # Write a distinctly identifiable log entry
    current_time = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime())
    log_entry = f"{current_time} ERROR [database-service] {test_message}"

    with open(log_file, 'w') as f:
        f.write(log_entry + '\n')

    # Step 2: Wait for the log collector to pick up and process the log
    time.sleep(10)

    # Step 4: Connect to Milvus and verify the log was stored with embeddings
    connections.connect(alias="pipeline_test", host=milvus_host, port=milvus_port)

    try:
        collections = utility.list_collections(using="pipeline_test")
        target_collection = "timberline_logs"

        collection = Collection(name=target_collection, using="pipeline_test")
        collection.load()

        # Query for recent logs containing our test message
        current_timestamp = int(time.time() * 1000)
        time_range = current_timestamp - (5 * 60 * 1000)  # Last 5 minutes in milliseconds

        # Search for logs with our unique test message
        query_expr = f"timestamp >= {time_range}"
        results = collection.query(
            expr=query_expr,
            output_fields=["timestamp", "message", "source", "metadata"],
            limit=200
        )

        # Verify our test log was processed and stored
        found_test_log = False
        for result in results:
            if result.get('message') and test_message in result['message']:
                found_test_log = True
                # Additional verification: check that metadata was preserved
                metadata = result.get('metadata', {})
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)

                # Verify log collector added proper metadata
                assert 'level' in metadata or 'log_level' in metadata, "Log level metadata missing"
                break

        assert found_test_log, f"Pipeline test log '{test_message}' not found in Milvus. Found {len(results)} total recent logs in collection {target_collection}"


    finally:
        connections.disconnect("pipeline_test")
        # Clean up test file
        if log_file.exists():
            log_file.unlink()


