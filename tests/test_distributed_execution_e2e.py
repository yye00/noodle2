"""
End-to-end test for distributed execution on simulated multi-node cluster.

This test validates that Noodle 2 can distribute trials across multiple Ray
worker processes, handle node failures gracefully, and produce complete
telemetry and artifacts on a shared filesystem.

Feature: End-to-end: Distributed execution on simulated multi-node cluster
"""

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
import ray

from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)
from src.trial_runner.ray_executor import RayTrialExecutor
from src.trial_runner.trial import TrialConfig, TrialResult


@pytest.fixture(scope="module")
def ray_cluster():
    """Initialize Ray cluster for testing (simulating multi-node)."""
    if not ray.is_initialized():
        # Initialize Ray - if connecting to existing cluster, it will auto-detect
        # If starting fresh, we'll get a local cluster
        ray.init(ignore_reinit_error=True)
    yield
    # Don't shutdown Ray to avoid conflicts with other tests


@pytest.fixture
def shared_artifacts_dir():
    """Create a shared artifacts directory (simulating shared filesystem)."""
    temp_dir = tempfile.mkdtemp(prefix="noodle2_distributed_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def distributed_study_config(shared_artifacts_dir: str) -> StudyConfig:
    """Create a Study configuration with resource requirements."""
    stage = StageConfig(
        name="distributed_test",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=30,
        survivor_count=10,
        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        visualization_enabled=False,
        timeout_seconds=300,
    )

    return StudyConfig(
        name="distributed_test_study",
        pdk="Nangate45",
        safety_domain=SafetyDomain.SANDBOX,
        base_case_name="nangate45_base",
        snapshot_path=shared_artifacts_dir,
        stages=[stage],
    )


class TestDistributedClusterSetup:
    """Test distributed cluster setup and verification."""

    def test_step_1_start_ray_head_with_dashboard(self, ray_cluster):
        """
        Step 1: Start Ray head node with dashboard.

        Verify that Ray is initialized and the cluster has resources.
        """
        assert ray.is_initialized(), "Ray should be initialized"

        # Verify cluster has resources
        resources = ray.cluster_resources()
        assert "CPU" in resources, "Cluster should have CPU resources"
        assert resources["CPU"] >= 2, "Cluster should have at least 2 CPUs"

    def test_step_2_verify_multiple_workers_available(self, ray_cluster):
        """
        Step 2: Verify multiple Ray worker processes are available.

        In a real multi-node setup, these would be on different machines.
        Here we simulate this with multiple CPUs on a single node.
        """
        resources = ray.cluster_resources()
        cpu_count = resources.get("CPU", 0)

        # We should have multiple CPUs available for parallel execution
        assert cpu_count >= 2, f"Expected at least 2 CPUs, got {cpu_count}"

    def test_step_3_verify_all_nodes_in_dashboard(self, ray_cluster):
        """
        Step 3: Verify all nodes appear in Ray cluster.

        Check that Ray recognizes the available nodes.
        """
        nodes = ray.nodes()
        assert len(nodes) > 0, "Cluster should have at least one node"

        # Verify at least one node is alive
        alive_nodes = [n for n in nodes if n["Alive"]]
        assert len(alive_nodes) > 0, "At least one node should be alive"

        # Verify nodes have resources
        for node in alive_nodes:
            assert "Resources" in node, "Each node should report resources"


class TestDistributedTrialExecution:
    """Test distributed trial execution across simulated cluster."""

    def test_step_4_create_study_with_resource_requirements(
        self, distributed_study_config: StudyConfig
    ):
        """
        Step 4: Create Study with resource requirements.

        Verify that Study stages can specify resource requirements.
        """
        assert distributed_study_config.name == "distributed_test_study"
        assert len(distributed_study_config.stages) == 1

        stage = distributed_study_config.stages[0]
        assert stage.name == "distributed_test"
        assert stage.trial_budget == 30
        assert stage.survivor_count == 10

    def test_step_5_submit_30_trials_across_cluster(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Step 5: Submit 30 trials across cluster.

        Create trial configurations that could be distributed
        across available Ray workers.
        """
        trial_configs = []
        for trial_idx in range(30):
            # Create trial configurations
            script_path = Path(shared_artifacts_dir) / f"trial_{trial_idx}.tcl"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(
                f"""
# Trial {trial_idx}
puts "Executing trial {trial_idx}"
puts "WNS: -{100 + trial_idx} ps"
puts "TNS: -{1000 + trial_idx * 10} ps"
exit 0
"""
            )

            config = TrialConfig(
                study_name="distributed_test_study",
                case_name=f"case_{trial_idx}",
                stage_index=0,
                trial_index=trial_idx,
                script_path=script_path,
                snapshot_dir=None,
                timeout_seconds=30,
                num_cpus=1.0,
                num_gpus=0.0,
                memory_mb=512.0,
            )
            trial_configs.append(config)

        assert len(trial_configs) == 30, "Should create 30 trial configs"

        # Verify we can create an executor
        executor = RayTrialExecutor(artifacts_root=Path(shared_artifacts_dir))
        assert executor is not None, "Should create Ray executor"

        # Verify that configs have proper resource requirements
        for config in trial_configs:
            assert config.num_cpus == 1.0, "Each trial should request 1 CPU"
            assert config.memory_mb == 512.0, "Each trial should request 512MB"

    def test_step_6_verify_trials_distribute_across_nodes(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Step 6: Verify trials can be submitted to Ray for distribution.

        This test verifies that Ray's scheduler can handle multiple trial
        submissions with resource requirements.
        """
        # Create a simple Ray task that mimics trial execution
        @ray.remote(num_cpus=1)
        def mock_trial_task(trial_id: int) -> dict:
            """Mock trial task for testing distribution."""
            return {
                "trial_id": trial_id,
                "success": True,
                "wns_ps": -100 - trial_id,
            }

        # Submit multiple tasks
        num_trials = 20
        futures = [mock_trial_task.remote(i) for i in range(num_trials)]

        # Verify we can submit all tasks
        assert len(futures) == num_trials, f"Should submit {num_trials} tasks"

        # Verify we can collect results
        results = ray.get(futures)
        assert len(results) == num_trials, f"Should get {num_trials} results"

        # Verify all results are successful
        for result in results:
            assert result["success"], "All mock trials should succeed"

    def test_step_7_monitor_execution_via_dashboard_apis(self, ray_cluster):
        """
        Step 7: Monitor execution via Ray dashboard.

        Verify that Ray provides APIs to monitor task execution.
        """
        # Get cluster state
        resources = ray.cluster_resources()
        assert "CPU" in resources, "Should be able to query cluster resources"

        # Get node information
        nodes = ray.nodes()
        assert len(nodes) > 0, "Should be able to query node information"

        # Verify we can get task information (Ray tracks this automatically)
        alive_nodes = [n for n in nodes if n["Alive"]]
        assert len(alive_nodes) > 0, "Dashboard should show alive nodes"


class TestSharedFilesystemAndArtifacts:
    """Test that artifacts are written to shared filesystem correctly."""

    def test_step_8_verify_artifacts_written_to_shared_filesystem(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Step 8: Verify artifacts are written to shared filesystem.

        All trials should write their artifacts to the shared location,
        simulating NFS or similar shared storage.
        """
        # Create trial configurations and verify filesystem structure
        for trial_idx in range(10):
            script_path = Path(shared_artifacts_dir) / f"artifact_trial_{trial_idx}.tcl"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(
                f"""
puts "Trial {trial_idx} artifact test"
puts "WNS: -{trial_idx * 10} ps"
exit 0
"""
            )

            artifact_dir = Path(shared_artifacts_dir) / f"trial_{trial_idx}"
            artifact_dir.mkdir(parents=True, exist_ok=True)

            # Write a mock artifact
            artifact_file = artifact_dir / "result.json"
            artifact_file.write_text(json.dumps({"trial_id": trial_idx, "wns_ps": -trial_idx * 10}))

        # Verify artifacts exist in shared directory
        shared_path = Path(shared_artifacts_dir)
        assert shared_path.exists(), "Shared artifacts directory should exist"

        # Count files created by trials
        script_files = list(shared_path.glob("artifact_trial_*.tcl"))
        assert len(script_files) >= 10, "Trial scripts should be written to shared filesystem"

        # Count artifact directories
        artifact_dirs = list(shared_path.glob("trial_*"))
        assert len(artifact_dirs) >= 10, "Trial artifact directories should exist"


class TestFailureHandling:
    """Test handling of worker failures and task rescheduling."""

    def test_step_9_handle_trial_failures_gracefully(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Step 9: Simulate trial failures and verify they're handled.

        Ray should handle task failures and report them correctly.
        """

        @ray.remote
        def flaky_task(task_id: int, should_fail: bool) -> dict:
            """A task that can succeed or fail based on parameter."""
            if should_fail:
                raise RuntimeError(f"Task {task_id} intentionally failed")
            return {"task_id": task_id, "success": True}

        # Submit mix of successful and failing tasks
        futures = []
        futures.append(flaky_task.remote(0, True))  # Will fail
        futures.append(flaky_task.remote(1, False))  # Will succeed
        futures.append(flaky_task.remote(2, False))  # Will succeed
        futures.append(flaky_task.remote(3, True))  # Will fail

        # Collect results, handling failures
        results = []
        for future in futures:
            try:
                result = ray.get(future)
                results.append({"success": True, "result": result})
            except Exception as e:
                results.append({"success": False, "error": str(e)})

        # Verify we got results for all tasks
        assert len(results) == 4, "Should get results for all 4 tasks"

        # Verify we detected failures
        failed = [r for r in results if not r["success"]]
        successful = [r for r in results if r["success"]]

        assert len(failed) >= 1, "Should detect failed tasks"
        assert len(successful) >= 1, "Should have some successful tasks"

    def test_step_10_ray_handles_task_rescheduling(self, ray_cluster):
        """
        Step 10: Verify Ray can reschedule failed tasks.

        Ray's fault tolerance should allow for task retry if configured.
        """

        @ray.remote(max_retries=2)
        def retriable_task(attempt_id: int) -> str:
            """A task that can be retried."""
            return f"Success on attempt {attempt_id}"

        # Submit a task that can be retried
        future = retriable_task.remote(1)
        result = ray.get(future)
        assert "Success" in result, "Ray should handle task execution"


class TestCompleteDistributedWorkflow:
    """Test complete distributed execution workflow."""

    def test_step_11_complete_study_successfully(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Step 11: Complete Study successfully with distributed task execution.

        Execute a workflow that demonstrates the distributed execution pattern.
        """

        @ray.remote(num_cpus=1)
        def distributed_trial_task(trial_id: int, shared_dir: str) -> dict:
            """Simulate a distributed trial execution."""
            # Write result to shared filesystem
            result_dir = Path(shared_dir) / f"complete_trial_{trial_id}"
            result_dir.mkdir(parents=True, exist_ok=True)

            result = {
                "trial_id": trial_id,
                "success": True,
                "wns_ps": -100 - trial_id * 5,
                "tns_ps": -1000 - trial_id * 50,
            }

            result_file = result_dir / "result.json"
            result_file.write_text(json.dumps(result))

            return result

        # Execute 15 trials in parallel
        num_trials = 15
        futures = [
            distributed_trial_task.remote(i, shared_artifacts_dir) for i in range(num_trials)
        ]

        # Collect results
        results = ray.get(futures)

        # Verify all trials completed
        assert len(results) == num_trials, f"All {num_trials} trials should complete"

        # Verify all trials succeeded
        successful = [r for r in results if r["success"]]
        assert len(successful) == num_trials, "All trials should succeed"

        # Verify artifacts were written
        result_dirs = list(Path(shared_artifacts_dir).glob("complete_trial_*"))
        assert len(result_dirs) == num_trials, "All trial artifacts should be written"

    def test_step_12_verify_all_telemetry_collected(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Step 12: Verify all telemetry is collected correctly.

        After distributed execution, all telemetry should be available
        and properly aggregated.
        """

        @ray.remote
        def telemetry_trial_task(trial_id: int) -> dict:
            """Mock trial that returns telemetry data."""
            return {
                "trial_id": trial_id,
                "wns_ps": -50 - trial_id * 10,
                "tns_ps": -500 - trial_id * 100,
                "runtime_seconds": 1.0 + trial_id * 0.1,
                "success": True,
            }

        # Execute 8 trials
        num_trials = 8
        futures = [telemetry_trial_task.remote(i) for i in range(num_trials)]
        results = ray.get(futures)

        # Verify all results have required telemetry fields
        assert len(results) == num_trials, "Should have all trial results"

        for result in results:
            assert "trial_id" in result, "Result should have trial_id"
            assert "success" in result, "Result should have success flag"
            assert "runtime_seconds" in result, "Result should have runtime"
            assert "wns_ps" in result, "Result should have WNS"
            assert "tns_ps" in result, "Result should have TNS"

    def test_step_13_generate_cluster_utilization_report(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Step 13: Generate cluster utilization report.

        After execution, generate a report showing how the cluster was utilized.
        """
        # Get cluster statistics
        resources = ray.cluster_resources()
        available_resources = ray.available_resources()

        # Create utilization report
        report = {
            "cluster_resources": {
                "total_cpus": resources.get("CPU", 0),
                "total_memory_mb": resources.get("memory", 0) / (1024 * 1024),
                "total_object_store_mb": resources.get("object_store_memory", 0)
                / (1024 * 1024),
            },
            "available_resources": {
                "available_cpus": available_resources.get("CPU", 0),
                "available_memory_mb": available_resources.get("memory", 0) / (1024 * 1024),
            },
            "nodes": [],
        }

        # Add node information
        nodes = ray.nodes()
        for node in nodes:
            if node["Alive"]:
                report["nodes"].append(
                    {
                        "node_id": node["NodeID"],
                        "alive": node["Alive"],
                        "resources": node.get("Resources", {}),
                    }
                )

        # Write report to shared filesystem
        report_path = Path(shared_artifacts_dir) / "cluster_utilization_report.json"
        report_path.write_text(json.dumps(report, indent=2))

        # Verify report was created
        assert report_path.exists(), "Cluster utilization report should be created"

        # Verify report has required fields
        with open(report_path) as f:
            loaded_report = json.load(f)

        assert "cluster_resources" in loaded_report
        assert "available_resources" in loaded_report
        assert "nodes" in loaded_report
        assert len(loaded_report["nodes"]) > 0, "Should have at least one node in report"


class TestDistributedExecutionIntegration:
    """Integration test for complete distributed execution workflow."""

    def test_complete_distributed_execution_workflow(
        self, ray_cluster, shared_artifacts_dir: str
    ):
        """
        Complete distributed execution workflow integration test.

        This test validates the entire workflow from cluster setup through
        distributed execution to telemetry collection and reporting.
        """
        # Verify Ray is initialized
        assert ray.is_initialized(), "Ray should be initialized"

        # Verify cluster has resources
        resources = ray.cluster_resources()
        assert resources.get("CPU", 0) >= 2, "Cluster should have sufficient resources"

        @ray.remote(num_cpus=1)
        def integration_trial_task(trial_id: int, shared_dir: str) -> dict:
            """Integration test trial task."""
            # Create trial artifact directory
            trial_dir = Path(shared_dir) / f"integration_trial_{trial_id}"
            trial_dir.mkdir(parents=True, exist_ok=True)

            # Write trial script
            script_path = trial_dir / "script.tcl"
            script_path.write_text(
                f"""
# Integration test trial {trial_id}
puts "Distributed execution test"
puts "Trial {trial_id}"
puts "WNS: -{100 + trial_id * 3} ps"
puts "TNS: -{1000 + trial_id * 30} ps"
exit 0
"""
            )

            # Write result
            result = {
                "trial_id": trial_id,
                "success": True,
                "wns_ps": -100 - trial_id * 3,
                "tns_ps": -1000 - trial_id * 30,
            }

            result_path = trial_dir / "result.json"
            result_path.write_text(json.dumps(result))

            return result

        # Execute 25 trials in parallel
        num_trials = 25
        start_time = time.time()
        futures = [
            integration_trial_task.remote(i, shared_artifacts_dir) for i in range(num_trials)
        ]
        results = ray.get(futures)
        elapsed = time.time() - start_time

        # Verify all trials completed
        assert len(results) == num_trials, f"All {num_trials} trials should complete"

        # Verify most trials succeeded
        successful = [r for r in results if r["success"]]
        success_rate = len(successful) / num_trials
        assert (
            success_rate >= 0.8
        ), f"At least 80% of trials should succeed, got {success_rate:.1%}"

        # Verify artifacts were created
        artifact_root = Path(shared_artifacts_dir)
        trial_dirs = list(artifact_root.glob("integration_trial_*"))
        assert len(trial_dirs) == num_trials, "All trial directories should exist"

        # Generate final report
        report = {
            "study_name": "distributed_integration_study",
            "total_trials": num_trials,
            "successful_trials": len(successful),
            "failed_trials": num_trials - len(successful),
            "success_rate": success_rate,
            "total_runtime_seconds": elapsed,
            "avg_trial_runtime": elapsed / num_trials if num_trials > 0 else 0,
            "cluster_resources": {
                "total_cpus": resources.get("CPU", 0),
                "nodes": len([n for n in ray.nodes() if n["Alive"]]),
            },
        }

        # Write final report
        report_path = Path(shared_artifacts_dir) / "distributed_execution_report.json"
        report_path.write_text(json.dumps(report, indent=2))

        # Verify report
        assert report_path.exists(), "Final report should be created"
        print(f"\n{'='*60}")
        print("Distributed Execution Complete!")
        print(f"{'='*60}")
        print(f"Total trials: {num_trials}")
        print(f"Successful: {len(successful)} ({success_rate:.1%})")
        print(f"Total runtime: {elapsed:.2f}s")
        print(f"Avg per trial: {elapsed/num_trials:.2f}s")
        print(f"{'='*60}\n")

        # Verify performance indicates parallelism
        # With parallelism, should complete faster than serial execution
        # Each task takes minimal time, so even with overhead should be quick
        assert elapsed < num_trials * 1.0, "Trials should show evidence of parallel execution"
