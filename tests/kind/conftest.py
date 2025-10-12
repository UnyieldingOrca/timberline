"""
Pytest configuration and fixtures for Kind (Kubernetes in Docker) integration tests.

This module provides fixtures for testing the Timberline log analysis platform
in a Kind Kubernetes cluster environment. Uses NodePort services for direct access.

Key Features:
- Kubernetes resource helpers (kubectl commands)
- Direct NodePort URL access (no port forwarding needed)
- Automatic cleanup of test data
- Milvus and PostgreSQL database fixtures
- Service health check utilities
- Test data generation
"""

import pytest
import requests
import subprocess
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from pymilvus import connections, Collection, utility


# ==============================================================================
# Configuration Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def namespace():
    """Kubernetes namespace where Timberline is deployed."""
    return "timberline"


@pytest.fixture(scope="session")
def helm_release_name():
    """Helm release name for Timberline."""
    return "timberline"


@pytest.fixture(scope="session")
def kind_host():
    """Host for Kind cluster NodePort services."""
    return "localhost"


@pytest.fixture(scope="session")
def timeout_config():
    """Timeout configuration for various operations."""
    return {
        "pod_ready": 300,      # 5 minutes for pods to become ready
        "service_ready": 120,  # 2 minutes for services to respond
        "http_request": 30,    # 30 seconds for HTTP requests
    }


# ==============================================================================
# Service URL Fixtures (using NodePort)
# ==============================================================================

@pytest.fixture(scope="session")
def service_urls(kind_host):
    """Service URLs accessible via Kind port mappings (NodePort → hostPort)."""
    return {
        "fluent_bit": f"http://{kind_host}:9020",           # NodePort 30020 → hostPort 9020
        "log_ingestor": f"http://{kind_host}:9200",         # NodePort 30200 → hostPort 9200
        "log_ingestor_metrics": f"http://{kind_host}:9201", # NodePort 30201 → hostPort 9201
        "milvus_grpc": f"{kind_host}:9530",                 # NodePort 30530 → hostPort 9530
        "milvus_metrics": f"http://{kind_host}:9091",       # NodePort 30091 → hostPort 9091
        "minio": f"http://{kind_host}:9900",                # NodePort 30900 → hostPort 9900
        "minio_console": f"http://{kind_host}:9901",        # NodePort 30901 → hostPort 9901
        "embedding_service": f"http://{kind_host}:9100",    # NodePort 30100 → hostPort 9100
        "llm_chat": f"http://{kind_host}:9101",             # NodePort 30101 → hostPort 9101
        "ai_analyzer": f"http://{kind_host}:9400",          # NodePort 30400 → hostPort 9400
        "web_ui": f"http://{kind_host}:9500",               # NodePort 30500 → hostPort 9500
        "attu": f"http://{kind_host}:9300",                 # NodePort 30300 → hostPort 9300
    }


# ==============================================================================
# Kubernetes Helper Functions
# ==============================================================================

def kubectl_exec(command: List[str], namespace: str = "timberline", check: bool = True) -> subprocess.CompletedProcess:
    """
    Execute kubectl command.

    Args:
        command: kubectl command arguments (without 'kubectl')
        namespace: Kubernetes namespace
        check: Raise exception on non-zero exit code

    Returns:
        CompletedProcess with stdout, stderr, and return code
    """
    cmd = ["kubectl", "-n", namespace] + command
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check
    )
    return result


def wait_for_condition(
    check_func,
    timeout: int = 60,
    interval: int = 2,
    error_message: str = "Condition not met within timeout"
) -> bool:
    """
    Wait for a condition to become true.

    Args:
        check_func: Function that returns True when condition is met
        timeout: Maximum time to wait in seconds
        interval: Time between checks in seconds
        error_message: Error message if timeout is reached

    Returns:
        True if condition met, raises TimeoutError otherwise
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            if check_func():
                return True
        except Exception as e:
            # Log but don't fail on temporary errors
            pass
        time.sleep(interval)

    raise TimeoutError(f"{error_message} (waited {timeout}s)")


# ==============================================================================
# Kubernetes Resource Fixtures
# ==============================================================================

@pytest.fixture
def kubectl(namespace):
    """Kubectl command executor fixture."""
    def _kubectl(command: List[str], check: bool = True) -> subprocess.CompletedProcess:
        return kubectl_exec(command, namespace, check)
    return _kubectl


@pytest.fixture
def wait_for_pod_ready(kubectl, timeout_config):
    """
    Wait for a pod to be ready.

    Returns a function that takes pod_name and optional timeout.
    """
    def _wait(pod_selector: str, timeout: Optional[int] = None) -> bool:
        timeout = timeout or timeout_config["pod_ready"]

        def check_ready():
            result = kubectl([
                "get", "pods",
                "-l", pod_selector,
                "-o", "jsonpath={.items[*].status.conditions[?(@.type=='Ready')].status}"
            ], check=False)

            if result.returncode != 0:
                return False

            statuses = result.stdout.strip().split()
            return all(status == "True" for status in statuses) and len(statuses) > 0

        return wait_for_condition(
            check_ready,
            timeout=timeout,
            error_message=f"Pod with selector '{pod_selector}' not ready"
        )

    return _wait


@pytest.fixture
def get_pod_logs(kubectl):
    """Get logs from a pod."""
    def _get_logs(
        pod_name: str,
        container: Optional[str] = None,
        tail: int = 100
    ) -> str:
        cmd = ["logs", pod_name, f"--tail={tail}"]
        if container:
            cmd.extend(["-c", container])

        result = kubectl(cmd, check=False)
        return result.stdout

    return _get_logs


# ==============================================================================
# HTTP and Service Testing Fixtures
# ==============================================================================

@pytest.fixture
def http_retry():
    """HTTP request helper with retry logic."""
    def _request(
        url: str,
        method: str = "GET",
        max_retries: int = 3,
        retry_delay: int = 2,
        timeout: int = 30,
        **kwargs
    ) -> requests.Response:
        for attempt in range(max_retries):
            try:
                if method.upper() == "GET":
                    response = requests.get(url, timeout=timeout, **kwargs)
                elif method.upper() == "POST":
                    response = requests.post(url, timeout=timeout, **kwargs)
                elif method.upper() == "PUT":
                    response = requests.put(url, timeout=timeout, **kwargs)
                elif method.upper() == "DELETE":
                    response = requests.delete(url, timeout=timeout, **kwargs)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                return response
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise e
                time.sleep(retry_delay)

    return _request


@pytest.fixture
def wait_for_service_ready(http_retry, timeout_config):
    """Wait for a service to respond to health checks."""
    def _wait(url: str, expected_status: int = 200, timeout: Optional[int] = None) -> bool:
        timeout = timeout or timeout_config["service_ready"]

        def check_ready():
            try:
                response = http_retry(url, timeout=10, max_retries=1)
                return response.status_code == expected_status
            except:
                return False

        return wait_for_condition(
            check_ready,
            timeout=timeout,
            error_message=f"Service at {url} not ready"
        )

    return _wait


# ==============================================================================
# Database Fixtures
# ==============================================================================

@pytest.fixture(scope="session")
def milvus_connection_params(kind_host):
    """Milvus connection parameters using Kind port mapping."""
    return {
        "host": kind_host,
        "port": 9530,  # NodePort 30530 mapped to hostPort 9530
        "alias": "kind_test"
    }


@pytest.fixture
def milvus_client(milvus_connection_params):
    """Milvus database client."""
    alias = milvus_connection_params["alias"]

    # Connect to Milvus
    connections.connect(
        alias=alias,
        host=milvus_connection_params["host"],
        port=milvus_connection_params["port"],
        timeout=30
    )

    yield alias

    # Disconnect
    try:
        connections.disconnect(alias)
    except:
        pass


@pytest.fixture
def cleanup_milvus_data(milvus_client):
    """Clean Milvus collection data before each test."""
    collection_name = "timberline_logs"

    def _cleanup():
        try:
            if utility.has_collection(collection_name, using=milvus_client):
                collection = Collection(collection_name, using=milvus_client)
                collection.load()
                # Delete all entities
                expr = "id >= 0"
                collection.delete(expr=expr)
                collection.flush()
                print(f"✓ Cleared Milvus collection '{collection_name}'")
        except Exception as e:
            print(f"⚠ Could not clean Milvus collection: {e}")

    # Cleanup before test
    _cleanup()

    yield

    # Optional: cleanup after test
    # _cleanup()


@pytest.fixture
def postgres_conn():
    """PostgreSQL database connection (via kubectl port-forward if needed)."""
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed")

    # PostgreSQL is ClusterIP only, need to use kubectl exec or port-forward
    # For now, skip tests that need PostgreSQL
    pytest.skip("PostgreSQL requires port-forward (ClusterIP service)")


@pytest.fixture
def cleanup_postgres_data(postgres_conn):
    """Clean PostgreSQL data before each test."""
    def _cleanup():
        try:
            cursor = postgres_conn.cursor()
            cursor.execute("DELETE FROM analysis_jobs")
            cursor.execute("DELETE FROM analysis_results")
            postgres_conn.commit()
            cursor.close()
            print("✓ Cleared PostgreSQL tables")
        except Exception as e:
            print(f"⚠ Could not clean PostgreSQL: {e}")

    _cleanup()

    yield

    # Optional: cleanup after test
    # _cleanup()


# ==============================================================================
# Test Data Fixtures
# ==============================================================================

@pytest.fixture
def create_test_pod(kubectl, namespace):
    """
    Create a temporary test pod for generating logs.

    Returns a function that creates a pod and returns its name.
    """
    created_pods = []

    def _create(
        name: str,
        image: str = "busybox",
        command: Optional[List[str]] = None,
        labels: Optional[Dict[str, str]] = None
    ) -> str:
        pod_manifest = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {
                "name": name,
                "labels": labels or {"app": "test-log-generator"}
            },
            "spec": {
                "containers": [{
                    "name": "main",
                    "image": image,
                    "command": command or ["sh", "-c", "while true; do echo 'Test log message'; sleep 5; done"]
                }],
                "restartPolicy": "Never"
            }
        }

        # Create pod
        result = subprocess.run(
            ["kubectl", "-n", namespace, "apply", "-f", "-"],
            input=json.dumps(pod_manifest),
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            created_pods.append(name)

        return name

    yield _create

    # Cleanup: delete created pods
    for pod_name in created_pods:
        try:
            kubectl(["delete", "pod", pod_name, "--force", "--grace-period=0"], check=False)
        except:
            pass


@pytest.fixture
def sample_log_entries():
    """Sample log entries for testing."""
    return [
        {
            "timestamp": int(time.time() * 1000),
            "message": "ERROR: Database connection timeout after 30s",
            "level": "ERROR",
            "source": "app-backend",
        },
        {
            "timestamp": int(time.time() * 1000),
            "message": "WARN: High memory usage detected: 85%",
            "level": "WARN",
            "source": "monitoring-agent",
        },
        {
            "timestamp": int(time.time() * 1000),
            "message": "INFO: Request processed successfully in 125ms",
            "level": "INFO",
            "source": "api-gateway",
        },
    ]


# ==============================================================================
# Port Forward Manager Fixture
# ==============================================================================

@pytest.fixture
def port_forward_manager(kubectl, namespace):
    """
    Context manager for kubectl port-forward operations.

    Returns a function that creates a context manager for port forwarding.
    """
    import contextlib
    import socket
    import threading

    @contextlib.contextmanager
    def _port_forward(service_name, remote_port, ns=None):
        """
        Context manager for port forwarding to a Kubernetes service.

        Args:
            service_name: Name of the service
            remote_port: Remote port on the service
            ns: Namespace (defaults to fixture namespace)

        Yields:
            Object with local_port attribute
        """
        ns = ns or namespace

        # Find an available local port
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            local_port = s.getsockname()[1]

        # Start port-forward in background
        cmd = [
            "kubectl", "-n", ns, "port-forward",
            f"service/{service_name}",
            f"{local_port}:{remote_port}"
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for port-forward to be ready
        time.sleep(2)

        class PortForward:
            def __init__(self, port):
                self.local_port = port

        pf = PortForward(local_port)

        try:
            yield pf
        finally:
            # Clean up port-forward process
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    return _port_forward


# ==============================================================================
# Test Markers and Configuration
# ==============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "health: Quick health check tests")
    config.addinivalue_line("markers", "deployment: Deployment status tests")
    config.addinivalue_line("markers", "connectivity: Service connectivity tests")
    config.addinivalue_line("markers", "persistence: Data persistence tests")
    config.addinivalue_line("markers", "e2e: End-to-end pipeline tests")
    config.addinivalue_line("markers", "slow: Slow-running tests")
