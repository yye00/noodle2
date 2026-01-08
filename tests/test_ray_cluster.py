"""Tests for Ray cluster initialization and management."""

import pytest
import ray
import requests


def test_ray_cluster_initialized() -> None:
    """
    Feature #1: Initialize Ray cluster in single-node mode and verify dashboard starts on port 8265.

    Steps:
        1. Execute 'ray start --head --dashboard-host=0.0.0.0'  (done by init.sh)
        2. Verify Ray dashboard is accessible at http://localhost:8265
        3. Verify Ray status shows cluster is running
        4. Check that dashboard displays node information
    """
    # Ray should already be initialized by init.sh
    # Try to connect to existing cluster or initialize if needed
    if not ray.is_initialized():
        ray.init(address="auto")

    # Verify Ray is initialized
    assert ray.is_initialized(), "Ray cluster should be initialized"

    # Verify dashboard is accessible at port 8265
    try:
        response = requests.get("http://localhost:8265", timeout=5)
        assert response.status_code == 200, "Ray dashboard should be accessible"
    except requests.exceptions.RequestException as e:
        pytest.fail(f"Ray dashboard not accessible at http://localhost:8265: {e}")

    # Verify cluster status
    cluster_resources = ray.cluster_resources()
    assert "CPU" in cluster_resources, "Cluster should have CPU resources"
    assert cluster_resources["CPU"] > 0, "Cluster should have available CPUs"

    # Verify node information
    nodes = ray.nodes()
    assert len(nodes) > 0, "Cluster should have at least one node"
    assert any(node["Alive"] for node in nodes), "At least one node should be alive"


def test_ray_simple_task() -> None:
    """Verify Ray can execute a simple task."""
    if not ray.is_initialized():
        ray.init(address="auto")

    @ray.remote
    def simple_task(x: int) -> int:
        return x * 2

    # Execute task
    result = ray.get(simple_task.remote(21))
    assert result == 42, "Ray task should execute correctly"
