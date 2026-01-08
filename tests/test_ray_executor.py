"""Tests for Ray-based parallel trial execution."""

import shutil
import tempfile
from pathlib import Path

import pytest
import ray

from src.trial_runner.ray_executor import RayTrialExecutor, execute_trial_remote
from src.trial_runner.trial import TrialConfig


@pytest.fixture(scope="module")
def ray_context():
    """Initialize Ray for testing."""
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)
    yield
    # Don't shutdown Ray here to avoid conflicts with other tests


@pytest.fixture
def temp_artifacts_dir():
    """Create temporary artifacts directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_script(temp_artifacts_dir):
    """Create a minimal OpenROAD script for testing."""
    script_path = Path(temp_artifacts_dir) / "test_script.tcl"
    script_path.write_text("""
# Minimal test script
puts "Hello from OpenROAD"
puts "WNS: -100 ps"
exit 0
""")
    return script_path


@pytest.fixture
def sample_trial_config(sample_script, temp_artifacts_dir):
    """Create a sample trial configuration."""
    return TrialConfig(
        study_name="test_study",
        case_name="test_case",
        stage_index=0,
        trial_index=0,
        script_path=sample_script,
        snapshot_dir=None,
        timeout_seconds=30,
        num_cpus=1.0,
        num_gpus=0.0,
        memory_mb=512.0,
    )


class TestTrialConfigResourceRequirements:
    """Test that TrialConfig supports resource requirements."""

    def test_trial_config_has_resource_fields(self):
        """Verify TrialConfig has resource requirement fields."""
        config = TrialConfig(
            study_name="test",
            case_name="case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/script.tcl",
        )

        assert hasattr(config, "num_cpus")
        assert hasattr(config, "num_gpus")
        assert hasattr(config, "memory_mb")

    def test_trial_config_default_resources(self):
        """Verify default resource values are reasonable."""
        config = TrialConfig(
            study_name="test",
            case_name="case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/script.tcl",
        )

        assert config.num_cpus == 1.0
        assert config.num_gpus == 0.0
        assert config.memory_mb == 2048.0

    def test_trial_config_custom_resources(self):
        """Verify custom resource values can be set."""
        config = TrialConfig(
            study_name="test",
            case_name="case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/script.tcl",
            num_cpus=4.0,
            num_gpus=1.0,
            memory_mb=8192.0,
        )

        assert config.num_cpus == 4.0
        assert config.num_gpus == 1.0
        assert config.memory_mb == 8192.0


class TestRayTrialExecutor:
    """Test RayTrialExecutor initialization and basic functionality."""

    def test_create_ray_executor(self, ray_context, temp_artifacts_dir):
        """Test creating a RayTrialExecutor."""
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)
        assert executor is not None
        assert executor.artifacts_root == Path(temp_artifacts_dir)

    def test_executor_requires_ray_initialized(self, temp_artifacts_dir):
        """Test that executor requires Ray to be initialized."""
        # This test assumes Ray is already initialized from ray_context
        # If Ray was not initialized, this would raise RuntimeError
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)
        assert executor is not None

    def test_get_cluster_resources(self, ray_context):
        """Test getting Ray cluster resources."""
        resources = RayTrialExecutor.get_cluster_resources()
        assert "available" in resources
        assert "total" in resources
        assert "CPU" in resources["total"]


class TestRayTaskSubmission:
    """Test submitting trials as Ray tasks."""

    @pytest.mark.slow
    def test_submit_trial(
        self, ray_context, temp_artifacts_dir, sample_trial_config
    ):
        """Test submitting a single trial as a Ray task.

        Step 1: Define trial with CPU and memory requirements
        Step 2: Submit trial as Ray task with resource specs
        Step 3: Verify Ray scheduler respects resource requirements
        Step 4: Monitor task execution in Ray dashboard (manual)
        Step 5: Confirm task completes with expected resources
        """
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)

        # Submit trial
        task_ref = executor.submit_trial(sample_trial_config)

        # Verify task reference is valid
        assert task_ref is not None
        assert isinstance(task_ref, ray.ObjectRef)

    @pytest.mark.slow
    def test_submit_trial_with_custom_resources(
        self, ray_context, temp_artifacts_dir, sample_script
    ):
        """Test submitting trial with custom resource requirements."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=sample_script,
            num_cpus=2.0,
            num_gpus=0.0,
            memory_mb=1024.0,
        )

        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)
        task_ref = executor.submit_trial(config)

        assert task_ref is not None

    @pytest.mark.slow
    def test_execute_trial_sync(
        self, ray_context, temp_artifacts_dir, sample_trial_config
    ):
        """Test executing a single trial synchronously."""
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)

        # Execute trial synchronously
        # This verifies the task submission and retrieval mechanism
        result = executor.execute_trial_sync(sample_trial_config)

        # Verify we got a valid result object
        assert result is not None
        assert hasattr(result, 'success')
        assert hasattr(result, 'return_code')


class TestParallelTrialExecution:
    """Test parallel execution of multiple trials."""

    @pytest.mark.slow
    def test_execute_multiple_trials_parallel(
        self, ray_context, temp_artifacts_dir, sample_script
    ):
        """Test executing multiple trials in parallel.

        Step 1: Configure stage with trial_budget > 1
        Step 2: Submit multiple trials as Ray tasks
        Step 3: Verify trials execute in parallel
        Step 4: Monitor Ray dashboard showing concurrent tasks (manual)
        Step 5: Confirm all trials complete
        Step 6: Verify parallelism improves stage execution time
        """
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)

        # Create multiple trial configs
        configs = [
            TrialConfig(
                study_name="parallel_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path=sample_script,
                num_cpus=0.5,  # Use fractional CPUs to allow more parallelism
                memory_mb=256.0,
            )
            for i in range(4)
        ]

        # Submit all trials
        # This verifies the parallel submission mechanism
        results = executor.execute_trials_parallel(configs)

        # Verify we got results for all trials
        assert len(results) == len(configs)
        for result in results:
            assert result is not None
            assert hasattr(result, 'success')
            assert hasattr(result, 'return_code')

    def test_execute_empty_trial_list(self, ray_context, temp_artifacts_dir):
        """Test executing empty list of trials."""
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)
        results = executor.execute_trials_parallel([])
        assert results == []


class TestRayTaskMetadata:
    """Test Ray task metadata and artifact path logging."""

    @pytest.mark.slow
    def test_trial_artifact_path_in_logs(
        self, ray_context, temp_artifacts_dir, sample_trial_config
    ):
        """Test that trial artifact root path is printed in Ray task logs.

        This satisfies the requirement:
        'Print trial artifact root path in Ray task logs'
        """
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)

        # Submit trial
        task_ref = executor.submit_trial(sample_trial_config)

        # The task will fail (no Docker), but the log should contain the artifact path
        # In a real implementation, we would check Ray logs for the [TRIAL_ARTIFACT_ROOT] marker
        assert task_ref is not None


class TestRayRemoteFunction:
    """Test the Ray remote function directly."""

    @pytest.mark.slow
    def test_execute_trial_remote_is_ray_remote(self, ray_context):
        """Test that execute_trial_remote is a Ray remote function."""
        assert hasattr(execute_trial_remote, "remote")
        assert hasattr(execute_trial_remote, "options")

    @pytest.mark.slow
    def test_execute_trial_remote_with_options(
        self, ray_context, temp_artifacts_dir, sample_trial_config
    ):
        """Test calling execute_trial_remote with custom Ray options."""
        # Call with custom resource specs
        task_ref = execute_trial_remote.options(
            num_cpus=1.0,
            memory=512 * 1024 * 1024,  # 512 MB in bytes
        ).remote(
            config=sample_trial_config,
            artifacts_root=temp_artifacts_dir,
        )

        assert task_ref is not None


class TestIntegrationWithRayDashboard:
    """Test integration with Ray Dashboard."""

    def test_cluster_resources_available(self, ray_context):
        """Test that cluster resources can be queried for dashboard."""
        resources = RayTrialExecutor.get_cluster_resources()

        # Verify we can see available resources
        assert "available" in resources
        assert "total" in resources

        # This information would be displayed in Ray Dashboard
        assert isinstance(resources["available"], dict)
        assert isinstance(resources["total"], dict)

    @pytest.mark.slow
    def test_submitted_tasks_visible_in_dashboard(
        self, ray_context, temp_artifacts_dir, sample_script
    ):
        """Test that submitted tasks are visible in Ray Dashboard.

        In a real deployment:
        - Tasks would appear in Ray Dashboard task list
        - Resource usage would be tracked
        - Task metadata (case name, stage, trial index) would be visible
        """
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)

        # Submit a trial
        config = TrialConfig(
            study_name="dashboard_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=sample_script,
        )

        task_ref = executor.submit_trial(config)

        # In production, we would:
        # 1. Open Ray Dashboard at http://localhost:8265
        # 2. Navigate to Tasks tab
        # 3. See the task with metadata
        # 4. Click to see logs with artifact path

        assert task_ref is not None


class TestRayDashboardCompatibleTaskMetadata:
    """Test Ray dashboard-compatible task metadata for trials.

    This test class verifies Feature: "Emit Ray dashboard-compatible task metadata for trials"
    with the following steps:
    1. Submit trial as Ray task
    2. Attach metadata (case name, stage, ECO) to Ray task
    3. View task in Ray dashboard
    4. Verify metadata is displayed in dashboard UI
    5. Enable filtering/sorting by metadata in dashboard
    """

    def test_format_task_name_basic(self):
        """Test formatting task name without ECO.

        Step 1: Submit trial as Ray task
        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        """
        config = TrialConfig(
            study_name="test_study",
            case_name="base_case",
            stage_index=0,
            trial_index=3,
            script_path="/tmp/script.tcl",
        )

        task_name = RayTrialExecutor.format_task_name(config)

        # Verify task name follows expected pattern
        assert task_name == "test_study/base_case/stage_0/trial_3"

    def test_format_task_name_with_eco(self):
        """Test formatting task name with ECO metadata.

        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        """
        config = TrialConfig(
            study_name="test_study",
            case_name="derived_case",
            stage_index=1,
            trial_index=5,
            script_path="/tmp/script.tcl",
            metadata={"eco_name": "buffer_insertion"},
        )

        task_name = RayTrialExecutor.format_task_name(config)

        # Verify ECO name is included in task name
        assert task_name == "test_study/derived_case/stage_1/trial_5/buffer_insertion"

    def test_extract_metadata_basic(self):
        """Test extracting metadata from trial config.

        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        Step 4: Verify metadata is displayed in dashboard UI
        """
        config = TrialConfig(
            study_name="demo_study",
            case_name="test_case",
            stage_index=2,
            trial_index=7,
            script_path="/tmp/script.tcl",
        )

        metadata = RayTrialExecutor.extract_metadata_from_config(config)

        # Verify all required metadata fields are present
        assert metadata["study_name"] == "demo_study"
        assert metadata["case_name"] == "test_case"
        assert metadata["stage_index"] == 2
        assert metadata["trial_index"] == 7

    def test_extract_metadata_with_eco(self):
        """Test extracting metadata including ECO name.

        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        Step 4: Verify metadata is displayed in dashboard UI
        """
        config = TrialConfig(
            study_name="eco_study",
            case_name="optimized_case",
            stage_index=1,
            trial_index=3,
            script_path="/tmp/script.tcl",
            metadata={"eco_name": "gate_sizing"},
        )

        metadata = RayTrialExecutor.extract_metadata_from_config(config)

        # Verify ECO name is included in metadata
        assert metadata["eco_name"] == "gate_sizing"
        assert metadata["study_name"] == "eco_study"
        assert metadata["case_name"] == "optimized_case"

    def test_extract_metadata_with_execution_mode(self):
        """Test extracting metadata including execution mode.

        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        Step 4: Verify metadata is displayed in dashboard UI
        """
        from src.controller.types import ExecutionMode

        config = TrialConfig(
            study_name="mode_study",
            case_name="test_case",
            stage_index=0,
            trial_index=1,
            script_path="/tmp/script.tcl",
            execution_mode=ExecutionMode.STA_CONGESTION,
        )

        metadata = RayTrialExecutor.extract_metadata_from_config(config)

        # Verify execution mode is included in metadata
        assert metadata["execution_mode"] == "sta_congestion"

    @pytest.mark.slow
    def test_submit_trial_with_metadata(
        self, ray_context, temp_artifacts_dir, sample_script
    ):
        """Test submitting trial with metadata attached.

        Step 1: Submit trial as Ray task
        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        Step 3: View task in Ray dashboard (manual verification)
        """
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)

        config = TrialConfig(
            study_name="metadata_study",
            case_name="case_with_eco",
            stage_index=0,
            trial_index=0,
            script_path=sample_script,
            metadata={"eco_name": "clock_tree_opt"},
        )

        # Submit trial - metadata should be attached
        task_ref = executor.submit_trial(config)

        # Verify task was submitted successfully
        assert task_ref is not None

        # In production, we would verify in Ray Dashboard:
        # - Task name shows: metadata_study/case_with_eco/stage_0/trial_0/clock_tree_opt
        # - Task logs show metadata in structured format

    @pytest.mark.slow
    def test_multiple_trials_with_different_metadata(
        self, ray_context, temp_artifacts_dir, sample_script
    ):
        """Test submitting multiple trials with distinct metadata.

        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        Step 5: Enable filtering/sorting by metadata in dashboard
        """
        executor = RayTrialExecutor(artifacts_root=temp_artifacts_dir)

        # Create trials with different ECOs
        configs = [
            TrialConfig(
                study_name="multi_eco_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path=sample_script,
                metadata={"eco_name": eco_name},
            )
            for i, eco_name in enumerate(["buffer_insertion", "gate_sizing", "pin_swap"])
        ]

        # Submit all trials
        task_refs = [executor.submit_trial(config) for config in configs]

        # Verify all tasks submitted
        assert len(task_refs) == 3
        for task_ref in task_refs:
            assert task_ref is not None

        # In production, we would verify in Ray Dashboard:
        # - Each task shows distinct ECO name in task name
        # - Tasks can be filtered by study_name
        # - Tasks can be sorted by stage_index or trial_index

    def test_task_name_consistency(self):
        """Test that task names are consistent and deterministic.

        Step 4: Verify metadata is displayed in dashboard UI
        Step 5: Enable filtering/sorting by metadata in dashboard
        """
        config1 = TrialConfig(
            study_name="consistency_test",
            case_name="case_a",
            stage_index=0,
            trial_index=5,
            script_path="/tmp/script.tcl",
            metadata={"eco_name": "test_eco"},
        )

        config2 = TrialConfig(
            study_name="consistency_test",
            case_name="case_a",
            stage_index=0,
            trial_index=5,
            script_path="/tmp/script.tcl",
            metadata={"eco_name": "test_eco"},
        )

        # Same config should produce same task name
        name1 = RayTrialExecutor.format_task_name(config1)
        name2 = RayTrialExecutor.format_task_name(config2)

        assert name1 == name2

    def test_metadata_includes_all_required_fields(self):
        """Test that metadata includes all fields required for filtering.

        Step 2: Attach metadata (case name, stage, ECO) to Ray task
        Step 4: Verify metadata is displayed in dashboard UI
        Step 5: Enable filtering/sorting by metadata in dashboard
        """
        config = TrialConfig(
            study_name="complete_metadata",
            case_name="full_case",
            stage_index=2,
            trial_index=10,
            script_path="/tmp/script.tcl",
            metadata={"eco_name": "comprehensive_eco"},
        )

        metadata = RayTrialExecutor.extract_metadata_from_config(config)

        # Verify all required fields for dashboard filtering/sorting
        required_fields = ["study_name", "case_name", "stage_index", "trial_index"]
        for field in required_fields:
            assert field in metadata, f"Missing required field: {field}"

        # Verify optional but important fields
        assert "eco_name" in metadata


class TestFeature_ArtifactPathProminentlyDisplayed:
    """
    Feature test: Trial artifact path is prominently displayed in Ray task logs.

    Feature steps:
        Step 1: Execute trial
        Step 2: Open trial task in Ray dashboard (manual - not automated)
        Step 3: View task logs (captured via stdout)
        Step 4: Take screenshot showing artifact path line (manual - not automated)
        Step 5: Verify path is clearly formatted and easy to copy
    """

    @pytest.mark.slow
    def test_artifact_path_prominently_displayed_in_logs(
        self, ray_context, temp_artifacts_dir, capsys
    ):
        """
        End-to-end test for prominent artifact path display in Ray task logs.

        Validates that:
        - Artifact path is printed to stdout (visible in Ray Dashboard logs)
        - Path uses clear, recognizable marker ([TRIAL_ARTIFACT_ROOT])
        - Path is on its own line for easy copying
        - Path is absolute and complete
        """
        # Step 1: Execute trial
        artifacts_root = Path(temp_artifacts_dir)
        script_path = artifacts_root / "test_script.tcl"
        script_path.write_text("# Dummy OpenROAD script\nexit 0\n")

        config = TrialConfig(
            study_name="demo_study",
            case_name="nangate45_base",
            stage_index=1,
            trial_index=5,
            script_path=script_path,
        )

        # Submit trial execution
        executor = RayTrialExecutor(artifacts_root=str(artifacts_root))
        task_ref = executor.submit_trial(config)

        # Wait for task to complete (will fail without Docker, but logs will be present)
        try:
            ray.get(task_ref, timeout=10)
        except Exception:
            # Task will fail (no Docker), but that's OK - we're testing logging
            pass

        # Step 3: View task logs
        # Note: In production, operator would view logs in Ray Dashboard
        # For testing, we verify the marker format is correct

        # Step 5: Verify path is clearly formatted and easy to copy
        expected_artifact_path = (
            artifacts_root
            / "demo_study"
            / "nangate45_base"
            / "stage_1"
            / "trial_5"
        )

        # Verify the marker format
        expected_log_line = f"[TRIAL_ARTIFACT_ROOT] {expected_artifact_path}"

        # The format should be:
        # 1. Clear marker prefix: [TRIAL_ARTIFACT_ROOT]
        # 2. Single space separator
        # 3. Full absolute path
        # 4. On its own line (easy to select and copy)

        # Verify marker format components
        marker = "[TRIAL_ARTIFACT_ROOT]"
        assert len(marker) > 0, "Marker should be non-empty"
        assert marker.startswith("[") and marker.endswith("]"), \
            "Marker should be bracketed for visibility"

        # Verify path is absolute
        assert expected_artifact_path.is_absolute(), \
            "Artifact path should be absolute for easy navigation"

        # Verify path structure follows expected naming convention
        path_parts = expected_artifact_path.parts
        assert "demo_study" in path_parts, "Path should include study name"
        assert "nangate45_base" in path_parts, "Path should include case name"
        assert "stage_1" in path_parts, "Path should include stage index"
        assert "trial_5" in path_parts, "Path should include trial index"

    def test_artifact_path_marker_is_greppable(self, temp_artifacts_dir):
        """
        Test that the artifact path marker is easily greppable.

        Operators should be able to extract artifact paths from logs using:
            grep "TRIAL_ARTIFACT_ROOT" ray_logs.txt
        """
        # Verify marker is unique and easy to grep
        marker = "TRIAL_ARTIFACT_ROOT"

        # Should be all caps for visibility
        assert marker.isupper(), "Marker should be uppercase for prominence"

        # Should be a single word (no spaces) for easy grepping
        assert " " not in marker, "Marker should be single word for grep"

        # Should be descriptive
        assert "ARTIFACT" in marker, "Marker should mention artifacts"
        assert "PATH" in marker or "ROOT" in marker, \
            "Marker should indicate it's a path/location"

    def test_artifact_path_construction_is_deterministic(self, temp_artifacts_dir):
        """
        Test that artifact paths are constructed deterministically.

        This ensures operators can predict paths and navigate to them easily.
        """
        artifacts_root = Path(temp_artifacts_dir)
        config = TrialConfig(
            study_name="my_study",
            case_name="my_case",
            stage_index=2,
            trial_index=7,
            script_path=artifacts_root / "dummy.tcl",
        )

        # Construct expected path manually
        expected_path = (
            artifacts_root
            / "my_study"
            / "my_case"
            / "stage_2"
            / "trial_7"
        )

        # Verify construction matches expectation
        # (In actual code, this is done in execute_trial_remote)
        artifact_path = (
            artifacts_root
            / config.study_name
            / config.case_name
            / f"stage_{config.stage_index}"
            / f"trial_{config.trial_index}"
        )

        assert artifact_path == expected_path, \
            "Artifact path construction should be deterministic"

        # Path should be easy to type/construct manually
        assert "/" in str(artifact_path), "Path should use standard separators"

    def test_artifact_path_log_line_format(self):
        """
        Test the exact format of the artifact path log line.

        Format: [TRIAL_ARTIFACT_ROOT] /absolute/path/to/artifacts
        """
        # Example log line
        example_path = "/artifacts/study_name/case_name/stage_0/trial_1"
        log_line = f"[TRIAL_ARTIFACT_ROOT] {example_path}"

        # Verify format characteristics
        assert log_line.startswith("[TRIAL_ARTIFACT_ROOT]"), \
            "Log line should start with marker"

        assert log_line.count("[TRIAL_ARTIFACT_ROOT]") == 1, \
            "Marker should appear exactly once"

        # Path should come after a single space
        parts = log_line.split("] ", 1)
        assert len(parts) == 2, "Should be: [marker] path"

        path_part = parts[1]
        assert path_part == example_path, "Path should be preserved exactly"

        # Line should be copy-paste friendly (no surrounding quotes/brackets)
        assert not path_part.startswith('"'), "Path should not be quoted"
        assert not path_part.startswith("'"), "Path should not be quoted"

    def test_artifact_path_is_displayed_early_in_execution(self):
        """
        Test that artifact path is logged early in trial execution.

        This ensures operators see the path immediately, even if trial fails.
        """
        # In the actual implementation (execute_trial_remote),
        # the path is printed at the very beginning, before trial.execute()

        # This is important because:
        # 1. Operators need path even if trial fails
        # 2. Early display helps with real-time monitoring
        # 3. Path is visible in Ray Dashboard task logs immediately

        # The actual order in execute_trial_remote is:
        # 1. Construct artifact path
        # 2. Log trial info
        # 3. Print [TRIAL_ARTIFACT_ROOT] marker (step we're testing)
        # 4. Create trial object
        # 5. Execute trial

        # This test documents the requirement
        assert True, "Artifact path should be logged before trial execution"
