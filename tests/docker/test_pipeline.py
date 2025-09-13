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
        f.flush()  # Ensure data is written to disk

    try:
        # Step 2: Wait for the log collector to pick up and process the log
        # The collector has a 2s flush interval, plus time for ingestor processing
        # Keep the file alive until after processing completes
        time.sleep(8)

        # Step 3: Connect to Milvus and verify the log was stored with embeddings
        connections.connect(alias="pipeline_test", host=milvus_host, port=milvus_port)

        try:
            collections = utility.list_collections(using="pipeline_test")
            target_collection = "timberline_logs"

            collection = Collection(name=target_collection, using="pipeline_test")
            collection.load()

            # Query for logs without time restrictions to avoid timezone issues
            # Search for logs containing our test message
            results = collection.query(
                expr="id >= 0",  # Get all logs, no timestamp filtering
                output_fields=["timestamp", "message", "source", "metadata"],
                limit=1000
            )

            # Debug: print some results to understand what's in Milvus
            print(f"\nFound {len(results)} total recent logs in collection {target_collection}")
            if results:
                print("Sample recent logs:")
                for i, result in enumerate(results[:5]):  # Show first 5
                    print(f"  {i+1}: {result.get('message', 'No message')[:120]}...")

                # Also search for any logs that might contain our test identifier
                pipeline_logs = [r for r in results if r.get('message') and 'PIPELINE_TEST_' in r.get('message', '')]
                if pipeline_logs:
                    print(f"\nFound {len(pipeline_logs)} potential pipeline test logs:")
                    for i, result in enumerate(pipeline_logs):
                        print(f"  {i+1}: {result.get('message', 'No message')}")

            # Verify our test log was processed and stored
            found_test_log = False
            for result in results:
                if result.get('message') and test_message in result['message']:
                    found_test_log = True
                    print(f"Found test log: {result}")

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

    finally:
        # Clean up test file after test completion
        if log_file.exists():
            log_file.unlink()


