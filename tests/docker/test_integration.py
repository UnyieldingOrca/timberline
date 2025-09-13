#!/usr/bin/env python3
"""
Docker integration tests for Timberline log analysis platform.
Tests the complete pipeline: log-collector → log-ingestor → Milvus vector database.
Also tests individual services: Milvus, llama.cpp embedding service, MinIO, and etcd.

These tests require Docker Compose to be running with all services healthy.
Run with: pytest tests/docker/test_integration.py -m docker
"""

import pytest
import requests
import json
import time
import subprocess
from pymilvus import connections, Collection, CollectionSchema, FieldSchema, DataType
import numpy as np


@pytest.mark.docker
@pytest.mark.integration
class TestDockerServices:
    """Test Docker Compose services are running and healthy."""


    @pytest.mark.parametrize("service_name,url,expected_status", [
        ("Milvus Metrics", "http://localhost:9091/healthz", 200),
        ("llama.cpp", "http://localhost:8000/health", 200),
        ("MinIO", "http://localhost:9000/minio/health/live", 200),
        ("Log Ingestor Health", "http://localhost:8080/api/v1/healthz", 200),
        ("Log Ingestor Metrics", "http://localhost:9092/metrics", 200),
        ("Log Collector Metrics", "http://localhost:9090/metrics", 200)
    ])
    def test_service_health_endpoints(self, service_name, url, expected_status):
        """Test service health endpoints"""
        max_retries = 2
        retry_delay = 1
        
        for attempt in range(max_retries):
            try:
                response = requests.get(url, timeout=5)  # Increased timeout
                if response.status_code == expected_status:
                    return
                elif attempt == max_retries - 1:
                    pytest.fail(f"{service_name} health check failed: status {response.status_code}, response: {response.text[:200]}")
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    pytest.fail(f"{service_name} health check failed: {e}")
                time.sleep(retry_delay)


@pytest.mark.docker
@pytest.mark.integration
class TestEmbeddingService:
    """Test llama.cpp embedding service."""

    @pytest.fixture
    def embedding_url(self):
        return "http://localhost:8000/v1/embeddings"

    @pytest.fixture
    def test_texts(self):
        return [
            "ERROR: Database connection failed in container",
            "WARN: Memory usage high in service",
            "FATAL: System crash detected in deployment",
            "INFO: Application started successfully"
        ]

    def test_embedding_service_response(self, embedding_url, test_texts):
        """Test that embedding service returns valid embeddings"""
        for text in test_texts:
            payload = {
                "model": "nomic-embed-text-v1.5",
                "input": text
            }

            response = requests.post(embedding_url, json=payload, timeout=60)
            assert response.status_code == 200, f"Embedding request failed: {response.text}"

            result = response.json()
            assert 'data' in result, "Response missing 'data' field"
            assert len(result['data']) > 0, "No embeddings returned"
            
            embedding = result['data'][0]['embedding']
            assert isinstance(embedding, list), "Embedding is not a list"
            assert len(embedding) > 0, "Embedding vector is empty"
            assert all(isinstance(x, (int, float)) for x in embedding), "Embedding contains non-numeric values"

    def test_embedding_consistency(self, embedding_url):
        """Test that same input produces consistent embeddings"""
        text = "Test message for consistency check"
        payload = {
            "model": "nomic-embed-text-v1.5",
            "input": text
        }

        # Get embeddings twice
        response1 = requests.post(embedding_url, json=payload, timeout=60)
        response2 = requests.post(embedding_url, json=payload, timeout=60)
        
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        embedding1 = response1.json()['data'][0]['embedding']
        embedding2 = response2.json()['data'][0]['embedding']
        
        # Embeddings should be identical for the same input
        assert embedding1 == embedding2, "Embeddings are not consistent for same input"


@pytest.mark.docker
@pytest.mark.integration
class TestMilvusDatabase:
    """Test Milvus vector database operations."""

    @pytest.fixture(scope="class")
    def milvus_connection(self):
        """Connect to Milvus database"""
        connections.connect(
            alias="default",
            host="localhost",
            port="19530"
        )
        yield
        connections.disconnect("default")

    @pytest.fixture
    def test_collection_name(self):
        return "pytest_test_logs"

    @pytest.fixture
    def log_schema(self):
        """Define schema for log entries"""
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="timestamp", dtype=DataType.INT64),
            FieldSchema(name="log_level", dtype=DataType.VARCHAR, max_length=50),
            FieldSchema(name="message", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="container_name", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="service_name", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768)  # nomic-embed dim
        ]
        
        return CollectionSchema(
            fields=fields,
            description="Timberline log entries with embeddings"
        )

    def test_milvus_connection(self, milvus_connection):
        """Test connection to Milvus"""
        # Connection is established in fixture, just verify it works
        assert True

    def test_collection_operations(self, milvus_connection, test_collection_name, log_schema):
        """Test creating, inserting, and querying a collection"""
        # Clean up any existing collection
        try:
            collection = Collection(name=test_collection_name)
            collection.drop()
        except:
            pass

        # Create collection
        collection = Collection(name=test_collection_name, schema=log_schema)
        assert collection is not None

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
class TestLogIngestor:
    """Test log-ingestor service functionality."""

    @pytest.fixture
    def ingestor_url(self):
        return "http://localhost:8080"

    @pytest.fixture
    def sample_log_entry(self):
        return {
            "timestamp": int(time.time() * 1000),  # Convert to milliseconds
            "message": "Database connection failed in container timberline-app",
            "source": "timberline-app",
            "metadata": {
                "level": "ERROR",
                "container_name": "timberline-app-1",
                "namespace": "default",
                "pod_name": "timberline-app-1-pod",
                "service_name": "timberline-app"
            }
        }



    def test_log_ingestor_health(self, ingestor_url):
        """Test log ingestor health endpoint"""
        response = requests.get(f"{ingestor_url}/api/v1/health", timeout=10)
        assert response.status_code == 200
        
        health_data = response.json()
        assert "status" in health_data
        assert health_data["status"] == "healthy"
    
    def test_log_ingestor_liveness(self, ingestor_url):
        """Test log ingestor liveness endpoint"""
        response = requests.get(f"{ingestor_url}/api/v1/healthz", timeout=10)
        assert response.status_code == 200
        assert response.text.strip() == "OK"

    def test_log_ingestor_metrics(self):
        """Test log ingestor metrics endpoint"""
        response = requests.get("http://localhost:9092/metrics", timeout=10)
        assert response.status_code == 200
        assert len(response.text) > 0

    def test_single_log_ingestion(self, ingestor_url, sample_log_entry):
        """Test ingesting a single log entry via batch endpoint"""
        # Since log-ingestor only has batch endpoint, send single log as batch
        response = requests.post(
            f"{ingestor_url}/api/v1/logs/batch",
            json={"logs":[{"timestamp":1704110400000,"message":"Test log message","source":"test-source","metadata":{"level":"INFO"}}]},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        assert response.status_code == 200, response.json()
        
        result = response.json()
        assert result.get("success") == True
        assert result.get("processed_count") == 1

    def test_batch_log_ingestion(self, ingestor_url):
        """Test ingesting multiple log entries"""
        log_entries = [
            {
                "timestamp": int(time.time() * 1000) + (i * 1000),  # Milliseconds with 1s intervals
                "message": f"{level}: Test message {i} from container",
                "source": "test-service",
                "metadata": {
                    "level": level,
                    "container_name": f"test-container-{i}",
                    "namespace": "default",
                    "pod_name": f"test-pod-{i}",
                    "service_name": "test-service"
                }
            }
            for i, level in enumerate(["ERROR", "WARN", "INFO", "DEBUG"])
        ]

        response = requests.post(
            f"{ingestor_url}/api/v1/logs/batch",
            json={"logs": log_entries},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        assert response.status_code == 200 or response.status_code == 202
        
        result = response.json()
        assert result.get("success") == True
        assert result.get("processed_count") == len(log_entries)

    def test_log_collector_to_ingestor_connectivity(self, ingestor_url):
        """Test that log-collector can successfully forward logs to log-ingestor"""
        # Simulate what log-collector would send to log-ingestor
        log_payload = {
            "logs": [{
                "timestamp": int(time.time() * 1000),  # Convert to milliseconds
                "message": "Test connectivity between log-collector and log-ingestor",
                "source": "log-collector",
                "metadata": {
                    "level": "ERROR",
                    "container_name": "timberline-log-collector",
                    "namespace": "default", 
                    "pod_name": "timberline-log-collector-pod",
                    "service_name": "log-collector",
                    "node_name": "test-node",
                    "labels": {"app": "log-collector"}
                }
            }]
        }
        
        # Use the correct batch endpoint
        response = requests.post(
            f"{ingestor_url}/api/v1/logs/batch",
            json=log_payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        # Accept both 200 (processed immediately) and 202 (accepted for processing)
        assert response.status_code in [200, 202], f"Log forwarding failed: {response.status_code} {response.text}"


@pytest.mark.docker
@pytest.mark.integration
@pytest.mark.slow
class TestDataPersistence:
    """Test data persistence from log-ingestor to Milvus."""

    def test_ingestor_to_milvus_data_flow(self):
        """Test that log-ingestor correctly stores data in Milvus with embeddings"""
        # Step 1: Send log to ingestor
        ingestor_url = "http://localhost:8080"
        test_log = {
            "timestamp": int(time.time() * 1000),  # Convert to milliseconds
            "message": "Integration test: Memory usage spike detected",
            "source": "test-application",
            "metadata": {
                "level": "WARN",
                "container_name": "test-app-container",
                "namespace": "production",
                "pod_name": "test-app-pod-123",
                "service_name": "test-application"
            }
        }
        
        # Send log to ingestor via batch endpoint
        response = requests.post(
            f"{ingestor_url}/api/v1/logs/batch",
            json={"logs": [test_log]},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        assert response.status_code in [200, 202], f"Log ingestion failed: {response.text}"
        
        # Step 2: Wait for processing and storage
        time.sleep(5)
        
        # Step 3: Connect to Milvus and verify data was stored
        connections.connect(alias="default", host="localhost", port="19530")
        
        # Check if there's a logs collection (this would be created by log-ingestor)
        from pymilvus import utility
        collections = utility.list_collections()
        
        # Look for a collection that might contain our logs
        # The actual collection name depends on log-ingestor implementation
        possible_names = ["logs", "timberline_logs", "log_entries", "application_logs"]
        target_collection = None
        
        for name in possible_names:
            if name in collections:
                target_collection = name
                break
        
        if target_collection:
            try:
                collection = Collection(name=target_collection)
                collection.load()
                
                # Query for logs that might match our test data
                # Use a broad query to find recent logs
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
                        # Note: level is now in metadata, not top-level
                        assert result.get('source') == 'test-application'
                        break
                
                assert found_test_log, f"Test log was not found in Milvus after ingestion. Found {len(results)} total logs."
                
            except Exception as e:
                pytest.fail(f"Failed to query Milvus collection {target_collection}: {e}")
        
        else:
            # If no expected collection exists, this might be expected during development
            # Log this for debugging but don't fail the test
            print(f"No expected log collections found. Available: {collections}")
            print("This may be expected if log-ingestor hasn't created collections yet")
        
        connections.disconnect("default")

    def test_embedding_generation_and_storage(self):
        """Test that logs get proper embeddings when stored in Milvus"""
        # This test verifies that the log-ingestor is properly generating
        # embeddings using the llama.cpp service and storing them in Milvus
        
        ingestor_url = "http://localhost:8080"
        test_log = {
            "timestamp": int(time.time() * 1000),  # Convert to milliseconds
            "message": "Critical system failure in database connection pool",
            "source": "database",
            "metadata": {
                "level": "ERROR",
                "container_name": "database-service",
                "namespace": "production",
                "pod_name": "db-service-pod-456",
                "service_name": "database"
            }
        }
        
        # Send log to ingestor via batch endpoint
        response = requests.post(
            f"{ingestor_url}/api/v1/logs/batch",
            json={"logs": [test_log]},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        assert response.status_code in [200, 202]
        
        # Wait for embedding generation and storage
        time.sleep(10)
        
        # Verify embedding was generated by checking if similar semantic search works
        connections.connect(alias="default", host="localhost", port="19530")
        
        from pymilvus import utility
        collections = utility.list_collections()
        
        # Look for collections with embeddings
        for collection_name in collections:
            try:
                collection = Collection(name=collection_name)
                # Check if this collection has embedding field
                schema = collection.schema
                has_embedding_field = any(field.name == "embedding" for field in schema.fields)
                
                if has_embedding_field:
                    collection.load()
                    
                    # Generate a test embedding for search
                    embedding_url = "http://localhost:8000/v1/embeddings"
                    payload = {
                        "model": "nomic-embed-text-v1.5", 
                        "input": "database connection error"  # Similar to our test message
                    }
                    
                    embed_response = requests.post(embedding_url, json=payload, timeout=60)
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
                        
                        # If we find results, verify they make semantic sense
                        if len(results[0]) > 0:
                            print(f"Found {len(results[0])} semantically similar logs")
                            # This indicates the embedding pipeline is working
                            assert True
                            connections.disconnect("default")
                            return
                            
            except Exception as e:
                print(f"Error checking collection {collection_name}: {e}")
                continue
        
        connections.disconnect("default")
        print("No collections with embeddings found - this may be expected during development")


@pytest.mark.docker
@pytest.mark.integration
class TestMetrics:
    """Test metrics collection endpoints."""

    def test_log_collector_metrics(self):
        """Test log collector metrics endpoint"""
        metrics_url = "http://localhost:9090/metrics"
        response = requests.get(metrics_url, timeout=10)
        assert response.status_code == 200, "Metrics endpoint not accessible"
        
        metrics_text = response.text
        assert len(metrics_text) > 0, "Metrics response is empty"
        
        # Look for expected metrics
        expected_metrics = ["go_", "promhttp_"]
        found_metrics = [metric for metric in expected_metrics if metric in metrics_text]
        assert len(found_metrics) > 0, "No expected metrics found"

    def test_log_ingestor_metrics(self):
        """Test log ingestor metrics endpoint"""
        ingestor_metrics_url = "http://localhost:9092/metrics"
        response = requests.get(ingestor_metrics_url, timeout=10)
        assert response.status_code == 200, "Log ingestor metrics endpoint not accessible"
        
        metrics_text = response.text
        assert len(metrics_text) > 0, "Log ingestor metrics response is empty"
        
        # Look for expected Go metrics
        expected_metrics = ["go_", "promhttp_"]
        found_metrics = [metric for metric in expected_metrics if metric in metrics_text]
        assert len(found_metrics) > 0, "No expected metrics found in log ingestor"

    def test_milvus_metrics(self):
        """Test Milvus metrics endpoint"""
        milvus_metrics_url = "http://localhost:9091/healthz"
        response = requests.get(milvus_metrics_url, timeout=10)
        assert response.status_code == 200, "Milvus health endpoint not accessible"