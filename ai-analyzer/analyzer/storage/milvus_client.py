from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from loguru import logger
import random
# Removed sklearn and numpy imports as we're now using label-based clustering

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
                output_fields=["id", "timestamp", "message", "source", "metadata", "embedding"],
                limit=limit
            )

            # Convert results to LogRecord objects
            logs = []
            for result in results:
                try:
                    # Extract metadata and level
                    metadata = result.get("metadata", {})
                    if isinstance(metadata, str):
                        import json
                        try:
                            metadata = json.loads(metadata)
                        except json.JSONDecodeError:
                            metadata = {}

                    # Extract level from metadata, with fallback logic
                    level = "INFO"  # default
                    if isinstance(metadata, dict):
                        level = metadata.get("level") or metadata.get("log_level") or "INFO"

                    log = LogRecord(
                        id=result.get("id", 0),
                        timestamp=result.get("timestamp", 0),
                        message=result.get("message", ""),
                        source=result.get("source", ""),
                        metadata=metadata,
                        embedding=result.get("embedding", []),
                        level=level
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

    def cluster_similar_logs(self, logs: List[LogRecord]) -> List[LogCluster]:
        """Group logs by Kubernetes label keys and values instead of embeddings"""
        if not logs:
            return []

        logger.info(f"Clustering {len(logs)} logs by Kubernetes labels")

        # Group logs by their label combinations
        label_clusters = {}

        for log in logs:
            # Extract Kubernetes labels from metadata
            labels = self._extract_labels(log)

            # Create a hashable key from sorted label items
            label_key = self._create_label_key(labels)

            if label_key not in label_clusters:
                label_clusters[label_key] = []
            label_clusters[label_key].append(log)

        # Create LogCluster objects
        clusters = []
        for label_key, cluster_logs in label_clusters.items():
            # Choose representative log (prioritize ERROR/CRITICAL, then most recent)
            representative = self._choose_representative_log(cluster_logs)

            clusters.append(LogCluster(
                representative_log=representative,
                similar_logs=cluster_logs,
                count=len(cluster_logs)
            ))

        # Sort clusters by severity and count
        clusters.sort(key=lambda c: (c.representative_log.is_error_or_critical(), c.count), reverse=True)

        logger.info(f"Created {len(clusters)} label-based clusters from {len(logs)} logs")
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
        """Choose a representative log from a group prioritizing errors and most recent"""
        if not logs:
            raise ValueError("Cannot choose representative from empty log list")

        # First priority: ERROR or CRITICAL logs
        error_logs = [log for log in logs if log.is_error_or_critical()]
        if error_logs:
            # Return most recent error log
            return max(error_logs, key=lambda log: log.timestamp)

        # Second priority: WARNING logs
        warning_logs = [log for log in logs if log.level == "WARNING"]
        if warning_logs:
            # Return most recent warning log
            return max(warning_logs, key=lambda log: log.timestamp)

        # Fall back to most recent log of any level
        return max(logs, key=lambda log: log.timestamp)

    def _extract_labels(self, log: LogRecord) -> Dict[str, str]:
        """Extract Kubernetes labels from log metadata"""
        if not isinstance(log.metadata, dict):
            return {}

        # Labels can be stored in different places in metadata
        labels = log.metadata.get("labels", {})

        # Handle case where labels might be stored as kubernetes_labels
        if not labels:
            labels = log.metadata.get("kubernetes_labels", {})

        # Handle case where labels are nested under kubernetes metadata
        if not labels and "kubernetes" in log.metadata:
            k8s_metadata = log.metadata["kubernetes"]
            if isinstance(k8s_metadata, dict):
                labels = k8s_metadata.get("labels", {})

        # Ensure labels is a dict and contains only string values
        if isinstance(labels, dict):
            return {str(k): str(v) for k, v in labels.items()}

        return {}

    def _create_label_key(self, labels: Dict[str, str]) -> str:
        """Create a hashable key from label dictionary"""
        if not labels:
            return "no-labels"

        # Sort labels by key to ensure consistent grouping
        sorted_labels = sorted(labels.items())

        # Create key from label pairs
        label_pairs = [f"{k}={v}" for k, v in sorted_labels]
        return "|".join(label_pairs)

