"""
Milvus vector database tests.
Tests database connection, collection operations, and vector search functionality.
"""

import pytest
import time
import numpy as np
from pymilvus import Collection, utility


@pytest.mark.docker
@pytest.mark.integration
def test_milvus_connection(milvus_connection):
    """Test connection to Milvus database."""
    # Connection is established in fixture, just verify it works
    assert True


@pytest.mark.docker
@pytest.mark.integration
def test_create_collection(milvus_connection, test_collection_name, log_schema):
    """Test creating a collection in Milvus."""
    # Clean up any existing collection
    try:
        collection = Collection(name=test_collection_name)
        collection.drop()
    except:
        pass

    # Create collection
    collection = Collection(name=test_collection_name, schema=log_schema)
    assert collection is not None
    assert collection.name == test_collection_name

    # Cleanup
    collection.drop()


@pytest.mark.docker
@pytest.mark.integration
def test_collection_index_creation(milvus_connection, test_collection_name, log_schema):
    """Test creating an index on collection."""
    # Clean up any existing collection
    try:
        collection = Collection(name=test_collection_name)
        collection.drop()
    except:
        pass

    # Create collection
    collection = Collection(name=test_collection_name, schema=log_schema)

    # Create index
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)

    # Verify index exists
    index_info = collection.index()
    assert index_info is not None

    # Cleanup
    collection.drop()


@pytest.mark.docker
@pytest.mark.integration
def test_insert_and_query_data(milvus_connection, test_collection_name, log_schema):
    """Test inserting and querying data in Milvus."""
    # Clean up any existing collection
    try:
        collection = Collection(name=test_collection_name)
        collection.drop()
    except:
        pass

    # Create collection
    collection = Collection(name=test_collection_name, schema=log_schema)

    # Create index
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)

    # Insert test data
    test_data = [
        [int(time.time())],  # timestamp
        ["ERROR"],  # log_level
        ["Database connection failed in container"],  # message
        ["timberline-log-collector"],  # container_name
        ["log-collector"],  # service_name
        [np.random.random(768).tolist()]  # embedding (nomic-embed dimension)
    ]

    collection.insert(test_data)
    collection.flush()

    # Load collection and verify data
    collection.load()
    count = collection.num_entities
    assert count == 1, f"Expected 1 entity, found {count}"

    # Cleanup
    collection.drop()


@pytest.mark.docker
@pytest.mark.integration
def test_vector_search(milvus_connection, test_collection_name, log_schema):
    """Test vector search functionality."""
    # Clean up any existing collection
    try:
        collection = Collection(name=test_collection_name)
        collection.drop()
    except:
        pass

    # Create collection
    collection = Collection(name=test_collection_name, schema=log_schema)

    # Create index
    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)

    # Insert test data
    test_data = [
        [int(time.time())],  # timestamp
        ["ERROR"],  # log_level
        ["Database connection failed in container"],  # message
        ["timberline-log-collector"],  # container_name
        ["log-collector"],  # service_name
        [np.random.random(768).tolist()]  # embedding
    ]

    collection.insert(test_data)
    collection.flush()
    collection.load()

    # Search test
    search_params = {
        "metric_type": "L2",
        "params": {"nprobe": 10}
    }

    query_vector = np.random.random(768).tolist()
    results = collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=search_params,
        limit=1,
        output_fields=["message", "container_name", "service_name"]
    )

    assert len(results[0]) > 0, "Search returned no results"

    # Cleanup
    collection.drop()


@pytest.mark.docker
@pytest.mark.integration
def test_multiple_collections(milvus_connection, log_schema):
    """Test working with multiple collections."""
    collection_names = ["test_collection_1", "test_collection_2"]

    try:
        # Create multiple collections
        collections = []
        for name in collection_names:
            # Clean up existing
            try:
                old_collection = Collection(name=name)
                old_collection.drop()
            except:
                pass

            collection = Collection(name=name, schema=log_schema)
            collections.append(collection)

        # Verify both collections exist
        all_collections = utility.list_collections()
        for name in collection_names:
            assert name in all_collections

    finally:
        # Cleanup
        for name in collection_names:
            try:
                collection = Collection(name=name)
                collection.drop()
            except:
                pass


@pytest.mark.docker
@pytest.mark.integration
def test_collection_statistics(milvus_connection, test_collection_name, log_schema):
    """Test getting collection statistics."""
    # Clean up any existing collection
    try:
        collection = Collection(name=test_collection_name)
        collection.drop()
    except:
        pass

    # Create collection and insert data
    collection = Collection(name=test_collection_name, schema=log_schema)

    # Insert multiple test records
    timestamps = [int(time.time()) + i for i in range(3)]
    log_levels = ["ERROR", "WARN", "INFO"]
    messages = ["Error message", "Warning message", "Info message"]
    containers = ["container-1", "container-2", "container-3"]
    services = ["service-1", "service-2", "service-3"]
    embeddings = [np.random.random(768).tolist() for _ in range(3)]

    test_data = [timestamps, log_levels, messages, containers, services, embeddings]

    collection.insert(test_data)
    collection.flush()
    collection.load()

    # Check statistics
    count = collection.num_entities
    assert count == 3, f"Expected 3 entities, found {count}"

    # Cleanup
    collection.drop()


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.parametrize("metric_type", ["L2", "IP"])
def test_different_similarity_metrics(milvus_connection, test_collection_name, log_schema, metric_type):
    """Test different similarity metrics for vector search."""
    # Clean up any existing collection
    try:
        collection = Collection(name=test_collection_name)
        collection.drop()
    except:
        pass

    # Create collection
    collection = Collection(name=test_collection_name, schema=log_schema)

    # Create index with specified metric
    index_params = {
        "metric_type": metric_type,
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128}
    }
    collection.create_index(field_name="embedding", index_params=index_params)

    # Insert test data
    test_data = [
        [int(time.time())],
        ["ERROR"],
        ["Test message"],
        ["test-container"],
        ["test-service"],
        [np.random.random(768).tolist()]
    ]

    collection.insert(test_data)
    collection.flush()
    collection.load()

    # Search with the same metric
    search_params = {
        "metric_type": metric_type,
        "params": {"nprobe": 10}
    }

    query_vector = np.random.random(768).tolist()
    results = collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=search_params,
        limit=1
    )

    assert len(results[0]) > 0, f"Search with {metric_type} metric returned no results"

    # Cleanup
    collection.drop()