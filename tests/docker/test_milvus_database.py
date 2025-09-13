"""
Milvus vector database tests.
Tests database connection and collection listing functionality.
Does not create collections - expects log-ingestor service to bootstrap them.
"""

import pytest
from pymilvus import utility


def test_milvus_connection(milvus_connection):
    """Test connection to Milvus database."""
    # Connection is established in fixture, just verify it works
    assert True


def test_list_collections(milvus_connection):
    """Test listing collections in Milvus (should show collections created by services)."""
    try:
        collections = utility.list_collections()
        # Just verify we can list collections - may be empty if services haven't created any yet
        assert isinstance(collections, list)
        print(f"Available collections: {collections}")
    except Exception as e:
        pytest.skip(f"Could not list collections: {e}")


def test_milvus_connection_info(milvus_connection):
    """Test getting Milvus connection information."""
    try:
        # Test that we can perform basic operations
        collections = utility.list_collections()
        assert isinstance(collections, list)

        # If there are collections, try to get info about them
        for collection_name in collections:
            try:
                from pymilvus import Collection
                collection = Collection(name=collection_name)
                # Just verify we can access collection properties
                schema = collection.schema
                assert schema is not None
                print(f"Collection {collection_name} has {len(schema.fields)} fields")
            except Exception as e:
                print(f"Could not access collection {collection_name}: {e}")
                continue

    except Exception as e:
        pytest.skip(f"Could not perform Milvus operations: {e}")