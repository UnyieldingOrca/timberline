from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from loguru import logger
import numpy as np
import random
from sklearn.cluster import KMeans

from pymilvus import connections, Collection, utility, DataType, CollectionSchema, FieldSchema
from pymilvus.exceptions import MilvusException

from ..models.log import LogRecord, LogCluster, LogLevel
from ..config.settings import Settings


class MilvusConnectionError(Exception):
    """Raised when Milvus connection fails"""
    pass


class MilvusQueryEngine:
    """Real Milvus query engine for log analysis"""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.host = settings.milvus_host
        self.port = settings.milvus_port
        self.collection_name = settings.milvus_collection
        self.connection_string = settings.milvus_connection_string
        self.connection_alias = "default"
        self._collection = None

    def connect(self) -> bool:
        """Connect to Milvus database"""
        try:
            logger.info(f"Connecting to Milvus at {self.connection_string}")

            # Connect to Milvus
            connections.connect(
                alias=self.connection_alias,
                host=self.host,
                port=str(self.port)
            )

            # Check if collection exists
            if not utility.has_collection(self.collection_name):
                logger.error(f"Collection '{self.collection_name}' does not exist")
                return False

            # Load collection
            self._collection = Collection(self.collection_name)
            self._collection.load()

            logger.info(f"Successfully connected to Milvus and loaded collection '{self.collection_name}'")
            return True

        except MilvusException as e:
            logger.error(f"Milvus error during connection: {e}")
            raise MilvusConnectionError(f"Milvus connection failed: {e}")
        except Exception as e:
            logger.error(f"Failed to connect to Milvus: {e}")
            raise MilvusConnectionError(f"Connection failed: {e}")

    def disconnect(self) -> None:
        """Disconnect from Milvus database"""
        try:
            if self._collection:
                self._collection.release()
                self._collection = None

            connections.disconnect(alias=self.connection_alias)
            logger.info("Disconnected from Milvus")
        except Exception as e:
            logger.warning(f"Error during disconnect: {e}")

    def is_connected(self) -> bool:
        """Check if connected to Milvus"""
        try:
            return (self._collection is not None and
                   connections.has_connection(self.connection_alias))
        except Exception:
            return False

    def query_time_range(self, start_time: datetime, end_time: datetime) -> List[LogRecord]:
        """Query logs within a time range"""
        # Validate time range first
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")

        if not self.is_connected():
            self.connect()

        if not self._collection:
            raise MilvusConnectionError("Collection not loaded")

        logger.info(f"Querying logs from {start_time} to {end_time}")

        time_diff = end_time - start_time
        if time_diff > timedelta(days=7):
            logger.warning(f"Large time range requested: {time_diff.days} days")

        # Convert to timestamps (milliseconds)
        start_timestamp = int(start_time.timestamp() * 1000)
        end_timestamp = int(end_time.timestamp() * 1000)

        try:
            # Query Milvus with time range filter
            expr = f"timestamp >= {start_timestamp} and timestamp <= {end_timestamp}"

            # Set limit based on max_logs_per_analysis
            limit = min(self.settings.max_logs_per_analysis, 16384)  # Milvus query limit

            results = self._collection.query(
                expr=expr,
                output_fields=["id", "timestamp", "message", "source", "metadata", "embedding", "level"],
                limit=limit
            )

            # Convert results to LogRecord objects
            logs = []
            for result in results:
                try:
                    log = LogRecord(
                        id=result.get("id", 0),
                        timestamp=result.get("timestamp", 0),
                        message=result.get("message", ""),
                        source=result.get("source", ""),
                        metadata=result.get("metadata", {}),
                        embedding=result.get("embedding", []),
                        level=result.get("level", "INFO")
                    )
                    logs.append(log)
                except Exception as e:
                    logger.warning(f"Failed to parse log record: {e}")
                    continue

            # Sort by timestamp (most recent first) and apply final limit
            logs.sort(key=lambda x: x.timestamp, reverse=True)
            if len(logs) > self.settings.max_logs_per_analysis:
                logs = logs[:self.settings.max_logs_per_analysis]

            logger.info(f"Retrieved {len(logs)} logs from Milvus")
            return logs

        except MilvusException as e:
            logger.error(f"Milvus query failed: {e}")
            raise MilvusConnectionError(f"Query failed: {e}")
        except Exception as e:
            logger.error(f"Error querying logs: {e}")
            raise

    def cluster_similar_logs(self, logs: List[LogRecord], similarity_threshold: float = 0.8) -> List[LogCluster]:
        """Group similar logs using vector similarity clustering"""
        if not logs:
            return []

        logger.info(f"Clustering {len(logs)} logs with similarity threshold {similarity_threshold}")

        # Extract embeddings for clustering
        embeddings = [log.embedding for log in logs]
        embeddings_array = np.array(embeddings)

        # Determine optimal number of clusters (heuristic approach)
        max_clusters = min(len(logs) // 5, 20)  # At least 5 logs per cluster, max 20 clusters
        n_clusters = max(2, max_clusters)

        if len(logs) <= max_clusters or len(logs) < 5:
            # Each log is its own cluster
            clusters = []
            for log in logs:
                clusters.append(LogCluster(
                    representative_log=log,
                    similar_logs=[log],
                    count=1
                ))
            return clusters

        # Perform K-means clustering
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings_array)

        # Group logs by cluster
        cluster_dict = {}
        for i, label in enumerate(cluster_labels):
            if label not in cluster_dict:
                cluster_dict[label] = []
            cluster_dict[label].append(logs[i])

        # Create LogCluster objects
        clusters = []
        for cluster_id, cluster_logs in cluster_dict.items():
            # Choose representative log (first ERROR, then WARNING, then first log)
            representative = self._choose_representative_log(cluster_logs)

            clusters.append(LogCluster(
                representative_log=representative,
                similar_logs=cluster_logs,
                count=len(cluster_logs)
            ))

        # Sort clusters by severity and count
        clusters.sort(key=lambda c: (c.representative_log.is_error_or_critical(), c.count), reverse=True)

        logger.info(f"Created {len(clusters)} log clusters")
        return clusters


    def health_check(self) -> bool:
        """Check Milvus connection health"""
        try:
            logger.info("Performing Milvus health check")

            # Try to connect if not already connected
            if not self.is_connected():
                self.connect()

            if not self._collection:
                logger.error("Milvus health check failed: collection not loaded")
                return False

            # Perform a simple query to verify the collection is accessible
            test_results = self._collection.query(
                expr="id >= 0",
                output_fields=["id"],
                limit=1
            )

            logger.info("Milvus health check passed")
            return True

        except MilvusException as e:
            logger.error(f"Milvus health check failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Milvus health check failed: {e}")
            return False

    def _choose_representative_log(self, logs: List[LogRecord]) -> LogRecord:
        """Choose a representative log from a group by random selection"""
        if not logs:
            raise ValueError("Cannot choose representative from empty log list")

        return random.choice(logs)

