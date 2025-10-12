"""
Milvus vector database operations tests for Timberline Kind deployment.

Tests that verify Milvus vector database business logic.
"""

import pytest
from pymilvus import (
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility
)


@pytest.mark.connectivity
class TestMilvusOperations:
    """Test Milvus vector database operations."""

    def test_milvus_create_collection(self, milvus_client):
        """Test creating a collection in Milvus."""
        collection_name = "test_create_collection"

        # Clean up if exists
        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.drop()

        # Define schema
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
            FieldSchema(name="message", dtype=DataType.VARCHAR, max_length=65535),
        ]

        schema = CollectionSchema(fields=fields, description="Test collection")

        # Create collection
        collection = Collection(collection_name, schema=schema, using=milvus_client)

        # Verify collection exists
        assert utility.has_collection(collection_name, using=milvus_client)

        # Cleanup
        collection.drop()
        assert not utility.has_collection(collection_name, using=milvus_client)

    def test_milvus_insert_vectors(self, milvus_client):
        """Test inserting vectors into Milvus."""
        collection_name = "test_insert_vectors"

        # Clean up if exists
        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.drop()

        # Create collection
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
            FieldSchema(name="message", dtype=DataType.VARCHAR, max_length=65535),
        ]

        schema = CollectionSchema(fields=fields, description="Test insert collection")
        collection = Collection(collection_name, schema=schema, using=milvus_client)

        # Insert data
        import random
        embeddings = [[random.random() for _ in range(768)] for _ in range(10)]
        messages = [f"Test message {i}" for i in range(10)]

        entities = [embeddings, messages]
        collection.insert(entities)
        collection.flush()

        # Verify count
        assert collection.num_entities == 10

        # Cleanup
        collection.drop()

    def test_milvus_create_index(self, milvus_client):
        """Test creating an index on vectors."""
        collection_name = "test_create_index"

        # Clean up if exists
        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.drop()

        # Create collection
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
            FieldSchema(name="message", dtype=DataType.VARCHAR, max_length=65535),
        ]

        schema = CollectionSchema(fields=fields, description="Test index collection")
        collection = Collection(collection_name, schema=schema, using=milvus_client)

        # Create index
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 128}
        }

        collection.create_index(field_name="embedding", index_params=index_params)

        # Verify index exists
        index_info = collection.index()
        assert index_info is not None

        # Cleanup
        collection.drop()

    def test_milvus_vector_search(self, milvus_client):
        """Test vector similarity search in Milvus."""
        collection_name = "test_vector_search"

        # Clean up if exists
        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.drop()

        # Create collection
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
            FieldSchema(name="message", dtype=DataType.VARCHAR, max_length=65535),
        ]

        schema = CollectionSchema(fields=fields, description="Test search collection")
        collection = Collection(collection_name, schema=schema, using=milvus_client)

        # Insert data
        import random
        random.seed(42)  # For reproducibility
        embeddings = [[random.random() for _ in range(768)] for _ in range(20)]
        messages = [f"Test message {i}" for i in range(20)]

        entities = [embeddings, messages]
        collection.insert(entities)
        collection.flush()

        # Create index for search
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 16}
        }
        collection.create_index(field_name="embedding", index_params=index_params)

        # Load collection
        collection.load()

        # Search
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        query_vector = [[random.random() for _ in range(768)]]

        results = collection.search(
            data=query_vector,
            anns_field="embedding",
            param=search_params,
            limit=5,
            output_fields=["message"]
        )

        # Verify results
        assert len(results) > 0
        assert len(results[0]) <= 5

        # Cleanup
        collection.drop()


@pytest.mark.connectivity
@pytest.mark.slow
class TestMilvusStackIntegration:
    """Test complete Milvus stack integration."""

    def test_milvus_stack_end_to_end(self, milvus_client):
        """
        Test complete Milvus stack workflow.

        This test verifies:
        - Milvus creates collection (metadata in etcd)
        - Milvus inserts data (stored in MinIO)
        - Milvus can search data
        """
        collection_name = "test_stack_integration"

        # Clean up if exists
        if utility.has_collection(collection_name, using=milvus_client):
            collection = Collection(collection_name, using=milvus_client)
            collection.drop()

        # Step 1: Create collection (etcd stores metadata)
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
            FieldSchema(name="message", dtype=DataType.VARCHAR, max_length=65535),
        ]

        schema = CollectionSchema(fields=fields, description="Integration test")
        collection = Collection(collection_name, schema=schema, using=milvus_client)

        # Step 2: Insert data (MinIO stores vectors)
        import random
        random.seed(123)
        embeddings = [[random.random() for _ in range(768)] for _ in range(100)]
        messages = [f"Integration test message {i}" for i in range(100)]

        entities = [embeddings, messages]
        collection.insert(entities)
        collection.flush()

        # Step 3: Create index and search
        index_params = {
            "index_type": "IVF_FLAT",
            "metric_type": "L2",
            "params": {"nlist": 32}
        }
        collection.create_index(field_name="embedding", index_params=index_params)
        collection.load()

        # Search
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
        query_vector = [[random.random() for _ in range(768)]]

        results = collection.search(
            data=query_vector,
            anns_field="embedding",
            param=search_params,
            limit=10,
            output_fields=["message"]
        )

        # Verify
        assert len(results) > 0
        assert collection.num_entities == 100

        # Cleanup
        collection.drop()
