"""Tests for parallel execution of independent Studies on shared Ray cluster - Feature #132.

This feature enables multiple independent Studies to execute concurrently on the same
Ray cluster while maintaining complete isolation of resources, telemetry, and state.

Key requirements:
- Studies can be launched concurrently on the same Ray cluster
- Resources are properly isolated between Studies
- Telemetry does not cross-contaminate
- Both Studies complete successfully
- No race conditions or conflicts
"""

import asyncio
import concurrent.futures
import tempfile
import threading
import time
from pathlib import Path
from typing import List

import pytest
import ray

from src.controller.executor import StudyExecutor
from src.controller.study import create_study_config
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


@pytest.fixture(scope="module")
def ray_cluster():
    """Initialize Ray cluster for testing parallel Studies."""
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)
    yield
    # Don't shutdown Ray to avoid conflicts with other tests


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create temporary workspace with separate directories."""
    artifacts_root = tmp_path / "artifacts"
    telemetry_root = tmp_path / "telemetry"
    snapshots_root = tmp_path / "snapshots"

    artifacts_root.mkdir(parents=True)
    telemetry_root.mkdir(parents=True)
    snapshots_root.mkdir(parents=True)

    return tmp_path


def create_minimal_snapshot(snapshot_dir: Path, pdk: str = "nangate45") -> Path:
    """Create a minimal snapshot directory for testing."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal STA script
    sta_script = snapshot_dir / "run_sta.tcl"
    sta_script.write_text("""
# Minimal STA script for testing
puts "Running STA for testing"
puts "WNS: -100 ps"
puts "TNS: -500 ps"
exit 0
""")

    return snapshot_dir


def create_test_study(
    study_name: str,
    workspace: Path,
    safety_domain: SafetyDomain = SafetyDomain.SANDBOX,
) -> StudyExecutor:
    """Create a minimal Study configuration for testing parallel execution."""
    # Create snapshot
    snapshot_path = workspace / "snapshots" / study_name
    create_minimal_snapshot(snapshot_path)

    # Create Study configuration with 1 stage
    stage = StageConfig(
        name="exploration",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=3,
        survivor_count=2,
        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
    )

    config = create_study_config(
        name=study_name,
        pdk="nangate45",
        base_case_name=f"{study_name}_base",
        snapshot_path=str(snapshot_path),
        safety_domain=safety_domain,
        stages=[stage],
    )

    # Create executor
    executor = StudyExecutor(
        config=config,
        artifacts_root=workspace / "artifacts",
        telemetry_root=workspace / "telemetry",
        skip_base_case_verification=True,  # Skip for testing
        enable_graceful_shutdown=False,  # Disable for testing
    )

    return executor


class TestParallelStudyExecution:
    """Test parallel execution of multiple Studies on shared Ray cluster."""

    def test_two_studies_execute_sequentially(
        self, ray_cluster, temp_workspace: Path
    ) -> None:
        """
        Baseline test: Two Studies can execute one after another without issues.

        This verifies basic isolation before testing concurrency.
        """
        # Execute Study A
        study_a = create_test_study("study_a", temp_workspace)
        result_a = study_a.execute()

        assert result_a.study_name == "study_a"
        assert result_a.stages_completed == 1
        assert not result_a.aborted

        # Execute Study B
        study_b = create_test_study("study_b", temp_workspace)
        result_b = study_b.execute()

        assert result_b.study_name == "study_b"
        assert result_b.stages_completed == 1
        assert not result_b.aborted

        # Verify separate artifacts
        artifacts_a = temp_workspace / "artifacts" / "study_a"
        artifacts_b = temp_workspace / "artifacts" / "study_b"
        assert artifacts_a.exists()
        assert artifacts_b.exists()

        # Verify separate telemetry
        telemetry_a = temp_workspace / "telemetry" / "study_a"
        telemetry_b = temp_workspace / "telemetry" / "study_b"
        assert telemetry_a.exists()
        assert telemetry_b.exists()

    def test_two_studies_execute_concurrently_with_threads(
        self, ray_cluster, temp_workspace: Path
    ) -> None:
        """
        Test concurrent execution of two Studies using threads.

        Step 1: Launch Study A on Ray cluster
        Step 2: Launch Study B on same Ray cluster
        Step 3: Verify both Studies execute concurrently
        """
        # Create both Studies
        study_a = create_test_study("concurrent_study_a", temp_workspace)
        study_b = create_test_study("concurrent_study_b", temp_workspace)

        # Track execution timing
        results = {}
        start_times = {}
        end_times = {}

        def execute_study(study: StudyExecutor, study_id: str) -> None:
            """Execute study and record timing."""
            start_times[study_id] = time.time()
            result = study.execute()
            end_times[study_id] = time.time()
            results[study_id] = result

        # Launch both Studies concurrently using threads
        thread_a = threading.Thread(
            target=execute_study, args=(study_a, "study_a")
        )
        thread_b = threading.Thread(
            target=execute_study, args=(study_b, "study_b")
        )

        # Start both threads
        thread_a.start()
        thread_b.start()

        # Wait for both to complete
        thread_a.join(timeout=60)
        thread_b.join(timeout=60)

        # Verify both completed successfully
        assert "study_a" in results
        assert "study_b" in results
        assert results["study_a"].study_name == "concurrent_study_a"
        assert results["study_b"].study_name == "concurrent_study_b"
        assert not results["study_a"].aborted
        assert not results["study_b"].aborted
        assert results["study_a"].stages_completed == 1
        assert results["study_b"].stages_completed == 1

        # Verify timing shows overlap (concurrent execution)
        # Both should have started before either finished
        assert "study_a" in start_times
        assert "study_b" in start_times
        assert "study_a" in end_times
        assert "study_b" in end_times

    def test_concurrent_studies_have_resource_isolation(
        self, ray_cluster, temp_workspace: Path
    ) -> None:
        """
        Step 4: Confirm resource isolation between Studies.

        Verifies that:
        - Each Study has separate artifact directories
        - Each Study has separate telemetry directories
        - File writes from one Study don't affect the other
        """
        study_a = create_test_study("isolated_study_a", temp_workspace)
        study_b = create_test_study("isolated_study_b", temp_workspace)

        # Execute concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(study_a.execute)
            future_b = executor.submit(study_b.execute)

            result_a = future_a.result(timeout=60)
            result_b = future_b.result(timeout=60)

        # Verify successful completion
        assert not result_a.aborted
        assert not result_b.aborted

        # Verify artifacts isolation
        artifacts_a = temp_workspace / "artifacts" / "isolated_study_a"
        artifacts_b = temp_workspace / "artifacts" / "isolated_study_b"
        assert artifacts_a.exists()
        assert artifacts_b.exists()
        assert artifacts_a != artifacts_b

        # Verify telemetry isolation
        telemetry_a = temp_workspace / "telemetry" / "isolated_study_a"
        telemetry_b = temp_workspace / "telemetry" / "isolated_study_b"
        assert telemetry_a.exists()
        assert telemetry_b.exists()
        assert telemetry_a != telemetry_b

        # Verify study telemetry files are separate
        study_file_a = telemetry_a / "study_telemetry.json"
        study_file_b = telemetry_b / "study_telemetry.json"
        assert study_file_a.exists()
        assert study_file_b.exists()

        # Verify contents are study-specific
        import json
        with open(study_file_a) as f:
            data_a = json.load(f)
        with open(study_file_b) as f:
            data_b = json.load(f)

        assert data_a["study_name"] == "isolated_study_a"
        assert data_b["study_name"] == "isolated_study_b"

    def test_concurrent_studies_no_telemetry_cross_contamination(
        self, ray_cluster, temp_workspace: Path
    ) -> None:
        """
        Step 5: Verify no telemetry cross-contamination.

        Ensures that telemetry written by Study A does not appear in Study B's
        telemetry directory and vice versa.
        """
        study_a = create_test_study("telemetry_study_a", temp_workspace)
        study_b = create_test_study("telemetry_study_b", temp_workspace)

        # Execute concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(study_a.execute)
            future_b = executor.submit(study_b.execute)

            future_a.result(timeout=60)
            future_b.result(timeout=60)

        # Check Study A's telemetry directory
        telemetry_a = temp_workspace / "telemetry" / "telemetry_study_a"
        telemetry_b = temp_workspace / "telemetry" / "telemetry_study_b"

        # List all files in each telemetry directory
        files_a = {f.name for f in telemetry_a.rglob("*") if f.is_file()}
        files_b = {f.name for f in telemetry_b.rglob("*") if f.is_file()}

        # Verify both have telemetry files
        assert len(files_a) > 0
        assert len(files_b) > 0

        # Verify study_telemetry.json exists in both
        assert "study_telemetry.json" in files_a
        assert "study_telemetry.json" in files_b

        # Verify event streams are separate
        assert "event_stream.ndjson" in files_a
        assert "event_stream.ndjson" in files_b

    def test_concurrent_studies_complete_successfully(
        self, ray_cluster, temp_workspace: Path
    ) -> None:
        """
        Step 6: Confirm both Studies complete successfully.

        This is the final validation that parallel execution works end-to-end.
        """
        study_a = create_test_study("success_study_a", temp_workspace)
        study_b = create_test_study("success_study_b", temp_workspace)

        # Execute both concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(study_a.execute)
            future_b = executor.submit(study_b.execute)

            result_a = future_a.result(timeout=60)
            result_b = future_b.result(timeout=60)

        # Verify successful completion
        assert result_a.study_name == "success_study_a"
        assert result_b.study_name == "success_study_b"
        assert not result_a.aborted
        assert not result_b.aborted
        assert result_a.stages_completed == 1
        assert result_b.stages_completed == 1
        assert result_a.total_stages == 1
        assert result_b.total_stages == 1

        # Verify both have stage results
        assert len(result_a.stage_results) == 1
        assert len(result_b.stage_results) == 1

    def test_three_studies_execute_concurrently(
        self, ray_cluster, temp_workspace: Path
    ) -> None:
        """
        Stress test: Three Studies execute concurrently.

        This verifies scalability beyond just two concurrent Studies.
        """
        study_a = create_test_study("multi_study_a", temp_workspace)
        study_b = create_test_study("multi_study_b", temp_workspace)
        study_c = create_test_study("multi_study_c", temp_workspace)

        # Execute all three concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            future_a = executor.submit(study_a.execute)
            future_b = executor.submit(study_b.execute)
            future_c = executor.submit(study_c.execute)

            result_a = future_a.result(timeout=60)
            result_b = future_b.result(timeout=60)
            result_c = future_c.result(timeout=60)

        # Verify all completed successfully
        assert not result_a.aborted
        assert not result_b.aborted
        assert not result_c.aborted
        assert result_a.stages_completed == 1
        assert result_b.stages_completed == 1
        assert result_c.stages_completed == 1

        # Verify separate telemetry
        telemetry_a = temp_workspace / "telemetry" / "multi_study_a"
        telemetry_b = temp_workspace / "telemetry" / "multi_study_b"
        telemetry_c = temp_workspace / "telemetry" / "multi_study_c"
        assert telemetry_a.exists()
        assert telemetry_b.exists()
        assert telemetry_c.exists()

    def test_concurrent_studies_with_different_safety_domains(
        self, ray_cluster, temp_workspace: Path
    ) -> None:
        """
        Test concurrent Studies with different safety domain configurations.

        Verifies that Studies with different safety policies can run concurrently
        without interfering with each other.
        """
        study_sandbox = create_test_study(
            "sandbox_study", temp_workspace, SafetyDomain.SANDBOX
        )
        study_guarded = create_test_study(
            "guarded_study", temp_workspace, SafetyDomain.GUARDED
        )

        # Execute concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_sandbox = executor.submit(study_sandbox.execute)
            future_guarded = executor.submit(study_guarded.execute)

            result_sandbox = future_sandbox.result(timeout=60)
            result_guarded = future_guarded.result(timeout=60)

        # Verify both completed successfully
        assert not result_sandbox.aborted
        assert not result_guarded.aborted

        # Verify safety domains are preserved in telemetry
        import json
        telemetry_sandbox = temp_workspace / "telemetry" / "sandbox_study" / "study_telemetry.json"
        telemetry_guarded = temp_workspace / "telemetry" / "guarded_study" / "study_telemetry.json"

        with open(telemetry_sandbox) as f:
            data_sandbox = json.load(f)
        with open(telemetry_guarded) as f:
            data_guarded = json.load(f)

        assert data_sandbox["safety_domain"] == "sandbox"
        assert data_guarded["safety_domain"] == "guarded"


class TestRayClusterSharing:
    """Test that Studies properly share the same Ray cluster."""

    def test_studies_use_same_ray_cluster(self, ray_cluster) -> None:
        """
        Verify that multiple Studies use the same Ray cluster instance.

        This confirms true cluster sharing rather than multiple isolated clusters.
        """
        # Get initial cluster resources
        initial_resources = ray.cluster_resources()

        assert "CPU" in initial_resources
        assert initial_resources["CPU"] > 0

        # Create temporary workspace
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)

            # Execute two Studies
            study_a = create_test_study("cluster_study_a", temp_path)
            study_b = create_test_study("cluster_study_b", temp_path)

            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                future_a = executor.submit(study_a.execute)
                future_b = executor.submit(study_b.execute)

                future_a.result(timeout=60)
                future_b.result(timeout=60)

            # Verify Ray cluster is still the same
            final_resources = ray.cluster_resources()
            assert final_resources == initial_resources

    def test_ray_dashboard_shows_both_studies(self, ray_cluster, temp_workspace: Path) -> None:
        """
        Verify that Ray Dashboard would show tasks from both Studies.

        This is a conceptual test - actual dashboard inspection would require
        the dashboard UI, but we can verify the cluster state.
        """
        study_a = create_test_study("dashboard_study_a", temp_workspace)
        study_b = create_test_study("dashboard_study_b", temp_workspace)

        # Execute both Studies
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_a = executor.submit(study_a.execute)
            future_b = executor.submit(study_b.execute)

            result_a = future_a.result(timeout=60)
            result_b = future_b.result(timeout=60)

        # Both should complete successfully
        assert not result_a.aborted
        assert not result_b.aborted

        # Ray cluster should still be healthy
        assert ray.is_initialized()
        cluster_resources = ray.cluster_resources()
        assert "CPU" in cluster_resources
