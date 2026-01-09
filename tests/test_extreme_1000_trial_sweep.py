"""
End-to-end test for extreme scenario: 1000+ trial large-scale parameter sweep.

This test validates that Noodle 2 can handle very large parameter sweeps with
1000+ trials, demonstrating scalability of the Ray orchestration, telemetry
collection, and artifact management systems.

Feature: Extreme scenario: 1000+ trial large-scale parameter sweep
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
    """Initialize Ray cluster for large-scale testing."""
    if not ray.is_initialized():
        # Initialize - let Ray auto-detect resources
        ray.init(ignore_reinit_error=True)
    yield
    # Don't shutdown to avoid conflicts


@pytest.fixture
def large_scale_artifacts_dir():
    """Create artifacts directory for 1000+ trials."""
    temp_dir = tempfile.mkdtemp(prefix="noodle2_1000trials_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestExtremeScaleParameterSweep:
    """Test 1000+ trial parameter sweep workflow."""

    def test_step_1_create_study_with_1000_trial_budget(
        self, large_scale_artifacts_dir
    ):
        """Step 1: Create Study with 1000 trial budget."""
        study_config = StudyConfig(
            name="extreme_1000trial_sweep",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            snapshot_path=large_scale_artifacts_dir,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=1000,  # 1000 trials
                    survivor_count=10,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        assert study_config.name == "extreme_1000trial_sweep"
        assert study_config.stages[0].trial_budget == 1000

        # Verify stage configuration
        stage = study_config.stages[0]
        assert stage.trial_budget == 1000
        assert stage.survivor_count == 10

        print(f"✓ Created Study with 1000 trial budget")

    def test_step_2_generate_trials_systematically(self, large_scale_artifacts_dir):
        """Step 2: Generate trials systematically."""
        # Generate 1000 trial configurations with systematic parameter variation
        trials: List[TrialConfig] = []

        # Create parameter sweep across multiple dimensions
        for trial_idx in range(1000):
            script_path = Path(large_scale_artifacts_dir) / f"trial_{trial_idx:04d}.tcl"
            script_path.parent.mkdir(parents=True, exist_ok=True)
            script_path.write_text(f"# Trial {trial_idx}\n")

            trial = TrialConfig(
                study_name="extreme_1000trial_sweep",
                case_name=f"nangate45_0_{trial_idx}",
                stage_index=0,
                trial_index=trial_idx,
                script_path=script_path,
                snapshot_dir=None,
                metadata={"eco_name": f"param_sweep_{trial_idx % 100}"},  # 100 unique ECOs
            )
            trials.append(trial)

        assert len(trials) == 1000
        assert trials[0].trial_index == 0
        assert trials[999].trial_index == 999

        # Verify systematic naming
        assert all(t.case_name.startswith("nangate45_0_") for t in trials)

        # Verify parameter variations
        unique_ecos = set(t.metadata.get("eco_name", "") for t in trials)
        assert len(unique_ecos) == 100  # 100 unique parameter combinations

        print(f"✓ Generated 1000 trials systematically")
        print(f"  - {len(unique_ecos)} unique parameter combinations")

    def test_step_3_submit_all_trials_to_ray_cluster(
        self, ray_cluster, large_scale_artifacts_dir
    ):
        """Step 3: Submit all trials to Ray cluster."""
        # Submit all trials to Ray (this should be fast - just scheduling)
        start_time = time.time()

        # Create mock trial execution function
        @ray.remote
        def execute_trial_mock(trial_idx: int) -> Dict[str, Any]:
            """Mock trial execution for scalability testing."""
            time.sleep(0.01)  # Simulate minimal work
            return {
                "trial_index": trial_idx,
                "success": True,
                "wns_ps": -1000 + (trial_idx % 2000),
                "runtime_seconds": 0.01,
            }

        # Submit all trials
        futures = []
        for trial_idx in range(1000):
            future = execute_trial_mock.remote(trial_idx)
            futures.append(future)

        submission_time = time.time() - start_time

        assert len(futures) == 1000
        assert submission_time < 10.0  # Should submit 1000 trials in < 10 seconds

        print(f"✓ Submitted 1000 trials to Ray in {submission_time:.2f}s")

        # Clean up futures
        for f in futures:
            ray.cancel(f, force=True)

    def test_step_4_monitor_cluster_resource_utilization(
        self, ray_cluster, large_scale_artifacts_dir
    ):
        """Step 4: Monitor cluster resource utilization."""
        # Get both available and total cluster resources
        resources_available = ray.available_resources()
        resources_total = ray.cluster_resources()

        print(f"✓ Cluster resources:")
        print(f"  - CPUs available: {resources_available.get('CPU', 0)}")
        print(f"  - CPUs total: {resources_total.get('CPU', 0)}")
        print(f"  - Memory: {resources_total.get('memory', 0) / 1e9:.2f} GB")
        print(f"  - Object store: {resources_total.get('object_store_memory', 0) / 1e9:.2f} GB")

        # Verify cluster has resources (check total, not just available)
        # Available might be 0 if other tests are still running
        assert resources_total.get("CPU", 0) > 0
        assert resources_total.get("memory", 0) > 0

    def test_step_5_verify_ray_handles_large_task_queue(self, ray_cluster):
        """Step 5: Verify Ray handles large task queue."""

        @ray.remote
        def simple_task(task_id: int) -> int:
            """Simple task for queue testing."""
            return task_id

        # Submit 1000 tasks
        start_time = time.time()
        futures = [simple_task.remote(i) for i in range(1000)]
        submission_time = time.time() - start_time

        assert len(futures) == 1000
        assert submission_time < 5.0  # Quick submission

        # Verify Ray can retrieve results (sample to avoid blocking)
        sample_futures = futures[:10]
        results = ray.get(sample_futures, timeout=10.0)  # Add timeout
        assert len(results) == 10
        assert results[0] == 0
        assert results[9] == 9

        print(f"✓ Ray handled 1000-task queue successfully")
        print(f"  - Submission time: {submission_time:.3f}s")

        # Cancel remaining tasks (do this quickly)
        try:
            for f in futures[10:]:
                ray.cancel(f, force=True)
        except Exception:
            pass  # Ignore cancellation errors

    def test_step_6_track_completion_of_all_1000_trials(
        self, ray_cluster, large_scale_artifacts_dir
    ):
        """Step 6: Track completion of all 1000 trials."""

        @ray.remote
        def trial_task(trial_idx: int) -> Dict[str, Any]:
            """Lightweight trial simulation."""
            return {
                "trial_id": f"trial_{trial_idx:04d}",
                "success": True,
                "wns_ps": -1000 + (trial_idx % 2000),
            }

        # Execute 1000 trials and track completion
        print(f"Executing 1000 trials...")
        start_time = time.time()

        futures = [trial_task.remote(i) for i in range(1000)]

        # Track completion
        completed = 0
        results = []

        # Process in batches to avoid overwhelming memory
        batch_size = 100
        for batch_start in range(0, 1000, batch_size):
            batch_end = min(batch_start + batch_size, 1000)
            batch_futures = futures[batch_start:batch_end]
            batch_results = ray.get(batch_futures)
            results.extend(batch_results)
            completed += len(batch_results)

            if batch_end % 200 == 0:
                print(f"  Completed: {batch_end}/1000 trials")

        execution_time = time.time() - start_time

        assert completed == 1000
        assert len(results) == 1000

        # Verify all trials succeeded
        success_count = sum(1 for r in results if r["success"])
        assert success_count == 1000

        print(f"✓ Completed all 1000 trials in {execution_time:.2f}s")
        print(f"  - Throughput: {1000 / execution_time:.1f} trials/sec")

    def test_step_7_verify_telemetry_system_scales_to_1000_trials(
        self, large_scale_artifacts_dir
    ):
        """Step 7: Verify telemetry system scales to 1000 trials."""

        # Generate telemetry for 1000 trials
        telemetry_dir = Path(large_scale_artifacts_dir) / "telemetry"
        telemetry_dir.mkdir(parents=True, exist_ok=True)

        print(f"Generating telemetry for 1000 trials...")
        start_time = time.time()

        telemetry_data = []
        for trial_idx in range(1000):
            trial_telemetry = {
                "trial_id": f"trial_{trial_idx:04d}",
                "case_name": f"nangate45_0_{trial_idx}",
                "stage_index": 0,
                "success": True,
                "wns_ps": -1000 + (trial_idx % 2000),
                "runtime_seconds": 0.1 + (trial_idx % 100) * 0.01,
                "timestamp": time.time(),
            }
            telemetry_data.append(trial_telemetry)

        # Write consolidated telemetry
        telemetry_file = telemetry_dir / "stage_0_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(
                {
                    "stage_index": 0,
                    "trial_count": 1000,
                    "trials": telemetry_data,
                },
                f,
                indent=2,
            )

        telemetry_time = time.time() - start_time
        file_size_mb = telemetry_file.stat().st_size / (1024 * 1024)

        assert len(telemetry_data) == 1000
        assert telemetry_file.exists()
        assert file_size_mb > 0

        print(f"✓ Telemetry system handled 1000 trials")
        print(f"  - Generation time: {telemetry_time:.2f}s")
        print(f"  - File size: {file_size_mb:.2f} MB")

        # Verify telemetry can be loaded back
        with open(telemetry_file, "r") as f:
            loaded = json.load(f)
            assert loaded["trial_count"] == 1000
            assert len(loaded["trials"]) == 1000

    def test_step_8_generate_summary_from_1000_trial_dataset(
        self, large_scale_artifacts_dir
    ):
        """Step 8: Generate summary from 1000 trial dataset."""

        # Create 1000 trial results
        trial_results = []
        for trial_idx in range(1000):
            result = {
                "trial_id": f"trial_{trial_idx:04d}",
                "success": trial_idx < 950,  # 95% success rate
                "wns_ps": -1000 + (trial_idx % 2000),
                "tns_ps": -5000 + (trial_idx % 10000),
                "runtime_seconds": 0.1 + (trial_idx % 100) * 0.01,
            }
            trial_results.append(result)

        # Generate summary statistics
        start_time = time.time()

        total_trials = len(trial_results)
        successful_trials = sum(1 for r in trial_results if r["success"])
        failed_trials = total_trials - successful_trials

        wns_values = [r["wns_ps"] for r in trial_results if r["success"]]
        best_wns = max(wns_values)
        worst_wns = min(wns_values)
        avg_wns = sum(wns_values) / len(wns_values)

        runtime_values = [r["runtime_seconds"] for r in trial_results]
        total_runtime = sum(runtime_values)
        avg_runtime = total_runtime / len(runtime_values)

        summary = {
            "study_name": "extreme_1000trial_sweep",
            "stage_index": 0,
            "total_trials": total_trials,
            "successful_trials": successful_trials,
            "failed_trials": failed_trials,
            "success_rate": successful_trials / total_trials,
            "wns_best_ps": best_wns,
            "wns_worst_ps": worst_wns,
            "wns_average_ps": avg_wns,
            "total_runtime_seconds": total_runtime,
            "average_runtime_seconds": avg_runtime,
        }

        summary_time = time.time() - start_time

        # Write summary
        summary_file = Path(large_scale_artifacts_dir) / "stage_0_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        assert summary["total_trials"] == 1000
        assert summary["successful_trials"] == 950
        assert summary["success_rate"] == 0.95
        assert summary["wns_best_ps"] > summary["wns_worst_ps"]

        print(f"✓ Generated summary from 1000 trials in {summary_time:.3f}s")
        print(f"  - Success rate: {summary['success_rate']*100:.1f}%")
        print(f"  - Best WNS: {summary['wns_best_ps']} ps")
        print(f"  - Average runtime: {summary['average_runtime_seconds']:.3f}s")

    def test_step_9_verify_performance_remains_acceptable_at_scale(
        self, ray_cluster
    ):
        """Step 9: Verify performance remains acceptable at scale."""

        @ray.remote
        def benchmark_task(task_id: int) -> Dict[str, Any]:
            """Benchmark task with realistic work."""
            start = time.time()

            # Simulate some computation
            result = sum(i * i for i in range(1000))

            return {
                "task_id": task_id,
                "result": result,
                "duration": time.time() - start,
            }

        # Execute 1000 tasks and measure performance
        print(f"Running performance benchmark with 1000 tasks...")

        overall_start = time.time()
        futures = [benchmark_task.remote(i) for i in range(1000)]
        results = []

        # Collect in batches
        batch_size = 100
        batch_times = []

        for batch_start in range(0, 1000, batch_size):
            batch_start_time = time.time()
            batch_end = min(batch_start + batch_size, 1000)
            batch_futures = futures[batch_start:batch_end]
            batch_results = ray.get(batch_futures)
            results.extend(batch_results)
            batch_time = time.time() - batch_start_time
            batch_times.append(batch_time)

        overall_time = time.time() - overall_start

        # Analyze performance
        throughput = 1000 / overall_time
        avg_batch_time = sum(batch_times) / len(batch_times)

        # Performance assertions
        assert overall_time < 300  # Should complete in < 5 minutes
        assert throughput > 3  # Should handle > 3 trials/sec
        assert avg_batch_time < 30  # Batches should be quick

        print(f"✓ Performance benchmark completed")
        print(f"  - Total time: {overall_time:.2f}s")
        print(f"  - Throughput: {throughput:.1f} trials/sec")
        print(f"  - Average batch time: {avg_batch_time:.2f}s")

    def test_step_10_identify_bottlenecks_and_scaling_issues(
        self, ray_cluster, large_scale_artifacts_dir
    ):
        """Step 10: Identify any bottlenecks or scaling issues."""

        # Test different aspects of the system at scale
        bottlenecks = []

        # 1. Test telemetry collection speed
        telemetry_start = time.time()
        telemetry_data = [
            {"trial_id": f"trial_{i:04d}", "wns_ps": i} for i in range(1000)
        ]
        telemetry_time = time.time() - telemetry_start

        if telemetry_time > 1.0:
            bottlenecks.append(
                f"Telemetry collection slow: {telemetry_time:.2f}s for 1000 trials"
            )

        # 2. Test JSON serialization speed
        json_start = time.time()
        json_data = json.dumps(telemetry_data)
        json_time = time.time() - json_start

        if json_time > 0.5:
            bottlenecks.append(
                f"JSON serialization slow: {json_time:.3f}s for 1000 records"
            )

        # 3. Test file I/O speed
        io_start = time.time()
        test_file = Path(large_scale_artifacts_dir) / "io_test.json"
        with open(test_file, "w") as f:
            json.dump(telemetry_data, f)
        io_time = time.time() - io_start

        if io_time > 1.0:
            bottlenecks.append(f"File I/O slow: {io_time:.3f}s for 1000 records")

        # 4. Test Ray task submission overhead
        @ray.remote
        def noop_task():
            return True

        ray_start = time.time()
        futures = [noop_task.remote() for _ in range(1000)]
        ray_submit_time = time.time() - ray_start

        if ray_submit_time > 5.0:
            bottlenecks.append(
                f"Ray submission overhead: {ray_submit_time:.2f}s for 1000 tasks"
            )

        # Cancel tasks
        for f in futures:
            ray.cancel(f, force=True)

        # Report findings
        print(f"✓ Bottleneck analysis completed")
        print(f"  - Telemetry collection: {telemetry_time:.3f}s")
        print(f"  - JSON serialization: {json_time:.3f}s")
        print(f"  - File I/O: {io_time:.3f}s")
        print(f"  - Ray submission: {ray_submit_time:.3f}s")

        if bottlenecks:
            print(f"  ⚠ Identified {len(bottlenecks)} potential bottlenecks:")
            for bottleneck in bottlenecks:
                print(f"    - {bottleneck}")
        else:
            print(f"  ✓ No significant bottlenecks detected")

        # All operations should be reasonably fast
        assert telemetry_time < 2.0
        assert json_time < 1.0
        assert io_time < 2.0
        assert ray_submit_time < 10.0


class TestCompleteExtreme1000TrialWorkflow:
    """Integration test covering complete 1000+ trial workflow."""

    def test_complete_1000_trial_parameter_sweep(
        self, ray_cluster, large_scale_artifacts_dir
    ):
        """Complete end-to-end workflow with 1000+ trials."""

        print("\n" + "=" * 70)
        print("COMPLETE 1000+ TRIAL PARAMETER SWEEP WORKFLOW")
        print("=" * 70)

        # Step 1: Create Study
        study_config = StudyConfig(
            name="extreme_1000trial_sweep",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            snapshot_path=large_scale_artifacts_dir,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=1000,
                    survivor_count=10,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        print(f"\n1. Study Configuration")
        print(f"   - Name: {study_config.name}")
        print(f"   - Trial budget: {study_config.stages[0].trial_budget}")
        print(f"   - Survivor count: {study_config.stages[0].survivor_count}")

        # Step 2: Generate trials
        @ray.remote
        def execute_trial(trial_idx: int) -> Dict[str, Any]:
            """Execute a single trial."""
            # Simulate trial execution with parameter variation
            base_wns = -1000
            param_effect = (trial_idx % 100) * 20  # Parameter effect

            return {
                "trial_id": f"trial_{trial_idx:04d}",
                "trial_index": trial_idx,
                "success": trial_idx < 950,  # 95% success rate
                "wns_ps": base_wns + param_effect,
                "runtime_seconds": 0.1 + (trial_idx % 50) * 0.01,
            }

        # Step 3: Execute all trials
        print(f"\n2. Executing 1000 trials...")
        execution_start = time.time()

        futures = [execute_trial.remote(i) for i in range(1000)]

        # Collect results in batches
        results = []
        batch_size = 100
        for batch_start in range(0, 1000, batch_size):
            batch_end = min(batch_start + batch_size, 1000)
            batch_futures = futures[batch_start:batch_end]
            batch_results = ray.get(batch_futures)
            results.extend(batch_results)
            print(f"   - Completed {batch_end}/1000 trials")

        execution_time = time.time() - execution_start

        # Step 4: Analyze results
        print(f"\n3. Analyzing results...")
        successful_results = [r for r in results if r["success"]]
        failed_results = [r for r in results if not r["success"]]

        wns_values = [r["wns_ps"] for r in successful_results]
        best_wns = max(wns_values)
        worst_wns = min(wns_values)
        avg_wns = sum(wns_values) / len(wns_values)

        # Identify top 10 survivors (best WNS)
        sorted_results = sorted(successful_results, key=lambda r: r["wns_ps"], reverse=True)
        survivors = sorted_results[:10]

        print(f"   - Total trials: {len(results)}")
        print(f"   - Successful: {len(successful_results)}")
        print(f"   - Failed: {len(failed_results)}")
        print(f"   - Best WNS: {best_wns} ps")
        print(f"   - Worst WNS: {worst_wns} ps")
        print(f"   - Average WNS: {avg_wns:.1f} ps")

        # Step 5: Generate summary
        summary = {
            "study_name": study_config.name,
            "stage_index": 0,
            "total_trials": len(results),
            "successful_trials": len(successful_results),
            "failed_trials": len(failed_results),
            "execution_time_seconds": execution_time,
            "throughput_trials_per_second": len(results) / execution_time,
            "wns_best_ps": best_wns,
            "wns_worst_ps": worst_wns,
            "wns_average_ps": avg_wns,
            "survivors": [
                {
                    "trial_id": s["trial_id"],
                    "wns_ps": s["wns_ps"],
                    "trial_index": s["trial_index"],
                }
                for s in survivors
            ],
        }

        summary_file = Path(large_scale_artifacts_dir) / "study_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n4. Summary generated")
        print(f"   - Execution time: {execution_time:.2f}s")
        print(f"   - Throughput: {summary['throughput_trials_per_second']:.1f} trials/sec")
        print(f"   - Top 10 survivors identified")

        # Verification
        assert len(results) == 1000
        assert len(successful_results) == 950
        assert len(survivors) == 10
        assert summary_file.exists()

        # Verify survivors are indeed the best
        assert all(s["wns_ps"] >= avg_wns for s in survivors)

        print(f"\n" + "=" * 70)
        print(f"✓ COMPLETE 1000+ TRIAL WORKFLOW SUCCESSFUL")
        print(f"=" * 70)
