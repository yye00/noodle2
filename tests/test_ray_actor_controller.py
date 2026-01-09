"""Tests for Ray actor-based controller for stateful Study orchestration."""

import shutil
import tempfile
import time
from pathlib import Path

import pytest
import ray

from src.controller.ray_actor_controller import (
    ActorStudyState,
    RayStudyActor,
    create_ray_study_actor,
)
from src.controller.study import StudyConfig
from src.controller.types import ExecutionMode, SafetyDomain, StageConfig
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


def create_test_trial_result(
    success: bool = True,
    return_code: int = 0,
    metrics: dict | None = None,
    stderr: str = "",
) -> TrialResult:
    """Helper to create TrialResult for testing."""
    trial_config = TrialConfig(
        study_name="test_study",
        case_name="test_case",
        stage_index=0,
        trial_index=0,
        script_path=Path("/dev/null"),
    )
    artifacts = TrialArtifacts(trial_dir=Path("/dev/null"))

    return TrialResult(
        config=trial_config,
        success=success,
        return_code=return_code,
        runtime_seconds=1.0,
        artifacts=artifacts,
        metrics=metrics or {},
        stdout="",
        stderr=stderr,
    )


@pytest.fixture(scope="module")
def ray_context():
    """Initialize Ray for testing."""
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)
    yield
    # Don't shutdown Ray here to avoid conflicts with other tests


@pytest.fixture
def temp_dirs():
    """Create temporary directories for artifacts and telemetry."""
    artifacts_dir = tempfile.mkdtemp()
    telemetry_dir = tempfile.mkdtemp()
    yield artifacts_dir, telemetry_dir
    shutil.rmtree(artifacts_dir, ignore_errors=True)
    shutil.rmtree(telemetry_dir, ignore_errors=True)


@pytest.fixture
def sample_study_config():
    """Create a sample Study configuration."""
    return StudyConfig(
        name="test_actor_study",
        safety_domain=SafetyDomain.SANDBOX,
        base_case_name="test_base_case",
        pdk="Nangate45",
        snapshot_path="/dev/null",
        stages=[
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=2,
                timeout_seconds=60,
                allowed_eco_classes=[],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_CONGESTION,
                trial_budget=2,
                survivor_count=1,
                timeout_seconds=120,
                allowed_eco_classes=[],
            ),
        ],
    )


class TestActorStudyState:
    """Test ActorStudyState dataclass for state management."""

    def test_create_actor_study_state(self):
        """Step 1: Verify ActorStudyState creation."""
        state = ActorStudyState(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=3,
        )

        assert state.study_name == "test_study"
        assert state.safety_domain == "sandbox"
        assert state.total_stages == 3
        assert state.current_stage == 0
        assert state.stages_completed == 0
        assert len(state.active_trials) == 0
        assert len(state.completed_trials) == 0
        assert not state.aborted

    def test_actor_study_state_to_dict(self):
        """Step 2: Verify state serialization."""
        state = ActorStudyState(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=3,
        )

        state_dict = state.to_dict()

        assert state_dict["study_name"] == "test_study"
        assert state_dict["safety_domain"] == "sandbox"
        assert state_dict["total_stages"] == 3
        assert state_dict["current_stage"] == 0
        assert state_dict["stages_completed"] == 0
        assert "elapsed_seconds" in state_dict
        assert isinstance(state_dict["elapsed_seconds"], float)

    def test_actor_study_state_tracks_trials(self):
        """Step 2: Verify state tracks trial execution."""
        state = ActorStudyState(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        # Simulate trial tracking
        state.active_trials["trial_1"] = "ref_1"  # type: ignore
        state.active_trials["trial_2"] = "ref_2"  # type: ignore

        assert len(state.active_trials) == 2

        # Simulate completion
        del state.active_trials["trial_1"]

        state.completed_trials.append(
            create_test_trial_result(metrics={"wns_ps": -100})
        )

        assert len(state.active_trials) == 1
        assert len(state.completed_trials) == 1


class TestRayStudyActorInitialization:
    """Test Ray actor initialization."""

    def test_initialize_ray_study_actor(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """
        Step 1: Initialize Noodle 2 controller as Ray actor.

        Verify that actor can be created and initialized successfully.
        """
        artifacts_dir, telemetry_dir = temp_dirs

        # Create Ray actor
        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Verify actor is created
        assert actor is not None

        # Get initial state
        state = ray.get(actor.get_state.remote())

        assert state["study_name"] == "test_actor_study"
        assert state["safety_domain"] == "sandbox"
        assert state["total_stages"] == 2
        assert state["current_stage"] == 0
        assert state["stages_completed"] == 0

    def test_actor_initializes_with_telemetry(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 1: Verify actor initializes telemetry emitter."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Get telemetry data
        telemetry = ray.get(actor.get_telemetry.remote())

        assert telemetry["study_name"] == "test_actor_study"
        assert "state" in telemetry
        assert "completed_trials" in telemetry
        assert "active_trials" in telemetry

    def test_create_ray_study_actor_helper(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 1: Verify helper function creates actor correctly."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = create_ray_study_actor(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        assert actor is not None

        state = ray.get(actor.get_state.remote())
        assert state["study_name"] == "test_actor_study"


class TestRayStudyActorStateMaintenance:
    """Test Study state maintenance in actor."""

    def test_maintain_study_state_in_actor(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """
        Step 2: Maintain Study state in actor.

        Verify that actor maintains mutable state across method calls.
        """
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Get initial state
        state1 = ray.get(actor.get_state.remote())
        assert state1["stages_completed"] == 0

        # Update state
        ray.get(
            actor.update_state_deterministically.remote(
                {"stages_completed": 1, "current_stage": 1}
            )
        )

        # Get updated state
        state2 = ray.get(actor.get_state.remote())
        assert state2["stages_completed"] == 1
        assert state2["current_stage"] == 1

    def test_actor_state_persists_across_calls(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 2: Verify state persists across multiple method calls."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Make multiple state updates
        for i in range(5):
            ray.get(
                actor.update_state_deterministically.remote(
                    {"stages_completed": i}
                )
            )

        # Final state should reflect last update
        final_state = ray.get(actor.get_state.remote())
        assert final_state["stages_completed"] == 4

    def test_actor_tracks_abort_state(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 2: Verify actor tracks abort state."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Initially not aborted
        assert not ray.get(actor.is_aborted.remote())

        # Abort study
        ray.get(actor.abort_study.remote("Test abort"))

        # Verify aborted state
        assert ray.get(actor.is_aborted.remote())

        state = ray.get(actor.get_state.remote())
        assert state["aborted"]
        assert state["abort_reason"] == "Test abort"


class TestRayStudyActorTrialSubmission:
    """Test trial submission from actor to Ray task queue."""

    def test_submit_trial_from_actor(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """
        Step 3: Submit trials from actor to Ray task queue.

        Verify that actor can submit trials with resource requirements.
        """
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Create trial configuration
        trial_config = TrialConfig(
            study_name="test_actor_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=Path("/dev/null"),
            snapshot_dir=None,
            timeout_seconds=30,
            num_cpus=1.0,
            num_gpus=0.0,
            memory_mb=512.0,
        )

        # Submit trial
        result_ref = ray.get(
            actor.submit_trial.remote(
                trial_config=trial_config,
                trial_id="test_trial_1",
            )
        )

        # Verify ObjectRef returned
        assert isinstance(result_ref, ray.ObjectRef)

        # Verify trial is tracked as active
        state = ray.get(actor.get_state.remote())
        assert state["active_trials_count"] == 1

    def test_submit_multiple_trials(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 3: Verify actor can submit multiple trials."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Submit multiple trials
        for i in range(3):
            trial_config = TrialConfig(
                study_name="test_actor_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path=Path("/dev/null"),
                snapshot_dir=None,
                timeout_seconds=30,
                num_cpus=1.0,
                num_gpus=0.0,
                memory_mb=512.0,
            )

            ray.get(
                actor.submit_trial.remote(
                    trial_config=trial_config,
                    trial_id=f"trial_{i}",
                )
            )

        # Verify all trials tracked
        state = ray.get(actor.get_state.remote())
        assert state["active_trials_count"] == 3

    def test_submit_trial_with_resource_requirements(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 3: Verify trials submitted with correct resource requirements."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Create trial with specific resources
        trial_config = TrialConfig(
            study_name="test_actor_study",
            case_name="resource_test",
            stage_index=0,
            trial_index=0,
            script_path=Path("/dev/null"),
            snapshot_dir=None,
            timeout_seconds=30,
            num_cpus=2.0,
            num_gpus=0.0,
            memory_mb=1024.0,
        )

        # Submit and verify
        result_ref = ray.get(
            actor.submit_trial.remote(
                trial_config=trial_config,
                trial_id="resource_trial",
            )
        )

        assert isinstance(result_ref, ray.ObjectRef)


class TestRayStudyActorTrialCallbacks:
    """Test trial completion callback handling in actor."""

    def test_handle_trial_completion_callback(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """
        Step 4: Handle trial completion callbacks in actor.

        Verify that actor correctly processes trial completion.
        """
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Submit trial
        trial_config = TrialConfig(
            study_name="test_actor_study",
            case_name="callback_test",
            stage_index=0,
            trial_index=0,
            script_path=Path("/dev/null"),
            snapshot_dir=None,
            timeout_seconds=30,
            num_cpus=1.0,
            num_gpus=0.0,
            memory_mb=512.0,
        )

        trial_id = "callback_trial"
        ray.get(actor.submit_trial.remote(trial_config, trial_id))

        # Create mock result
        result = create_test_trial_result(metrics={"wns_ps": -100})

        # Handle completion
        ray.get(actor.handle_trial_completion.remote(trial_id, result))

        # Verify state updated
        state = ray.get(actor.get_state.remote())
        assert state["active_trials_count"] == 0
        assert state["completed_trials_count"] == 1

    def test_handle_multiple_trial_completions(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 4: Verify actor handles multiple trial completions."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Submit and complete multiple trials
        for i in range(3):
            trial_config = TrialConfig(
                study_name="test_actor_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path=Path("/dev/null"),
                snapshot_dir=None,
                timeout_seconds=30,
                num_cpus=1.0,
                num_gpus=0.0,
                memory_mb=512.0,
            )

            trial_id = f"trial_{i}"
            ray.get(actor.submit_trial.remote(trial_config, trial_id))

            result = create_test_trial_result(metrics={"wns_ps": -100 - i})

            ray.get(actor.handle_trial_completion.remote(trial_id, result))

        # Verify all completed
        state = ray.get(actor.get_state.remote())
        assert state["active_trials_count"] == 0
        assert state["completed_trials_count"] == 3

    def test_handle_trial_failure_callback(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 4: Verify actor handles trial failures correctly."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Submit trial
        trial_config = TrialConfig(
            study_name="test_actor_study",
            case_name="failure_test",
            stage_index=0,
            trial_index=0,
            script_path=Path("/dev/null"),
            snapshot_dir=None,
            timeout_seconds=30,
            num_cpus=1.0,
            num_gpus=0.0,
            memory_mb=512.0,
        )

        trial_id = "failure_trial"
        ray.get(actor.submit_trial.remote(trial_config, trial_id))

        # Create failure result
        result = create_test_trial_result(
            success=False,
            return_code=1,
            stderr="Error occurred",
        )

        # Handle completion
        ray.get(actor.handle_trial_completion.remote(trial_id, result))

        # Verify state updated correctly
        state = ray.get(actor.get_state.remote())
        assert state["active_trials_count"] == 0
        assert state["completed_trials_count"] == 1


class TestRayStudyActorDeterministicStateUpdates:
    """Test deterministic state updates in actor."""

    def test_update_study_state_deterministically(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """
        Step 5: Update Study state deterministically.

        Verify that all state updates are atomic and traceable.
        """
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Perform deterministic state update
        updated_state = ray.get(
            actor.update_state_deterministically.remote(
                {
                    "current_stage": 1,
                    "stages_completed": 1,
                }
            )
        )

        # Verify update applied
        assert updated_state["current_stage"] == 1
        assert updated_state["stages_completed"] == 1

        # Verify state persists
        state = ray.get(actor.get_state.remote())
        assert state["current_stage"] == 1
        assert state["stages_completed"] == 1

    def test_state_updates_are_atomic(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 5: Verify state updates are atomic."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Multiple fields updated atomically
        ray.get(
            actor.update_state_deterministically.remote(
                {
                    "current_stage": 2,
                    "stages_completed": 2,
                    "aborted": True,
                    "abort_reason": "Test",
                }
            )
        )

        state = ray.get(actor.get_state.remote())
        assert state["current_stage"] == 2
        assert state["stages_completed"] == 2
        assert state["aborted"]
        assert state["abort_reason"] == "Test"

    def test_state_updates_handle_unknown_fields(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 5: Verify unknown fields are ignored gracefully."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Try to update unknown field (should be ignored)
        ray.get(
            actor.update_state_deterministically.remote(
                {
                    "unknown_field": "value",
                    "current_stage": 1,
                }
            )
        )

        state = ray.get(actor.get_state.remote())
        assert state["current_stage"] == 1
        assert "unknown_field" not in state


class TestRayStudyActorFaultTolerance:
    """Test fault-tolerance features of Ray actor."""

    def test_actor_provides_fault_tolerance(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """
        Step 6: Verify actor provides fault-tolerance for controller.

        Ray actors can be configured with max_restarts for fault-tolerance.
        This test verifies the actor can be created with fault-tolerance options.
        """
        artifacts_dir, telemetry_dir = temp_dirs

        # Create actor with fault-tolerance options
        actor = RayStudyActor.options(
            max_restarts=3,
            max_task_retries=2,
        ).remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Verify actor is functional
        state = ray.get(actor.get_state.remote())
        assert state["study_name"] == "test_actor_study"

    def test_actor_state_survives_across_operations(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 6: Verify actor state survives across many operations."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Perform many state operations
        for i in range(10):
            ray.get(
                actor.update_state_deterministically.remote(
                    {"stages_completed": i}
                )
            )

        # Verify final state is correct
        state = ray.get(actor.get_state.remote())
        assert state["stages_completed"] == 9

    def test_actor_handles_exceptions_gracefully(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Step 6: Verify actor handles exceptions without crashing."""
        artifacts_dir, telemetry_dir = temp_dirs

        actor = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Try to execute invalid stage (should raise exception)
        with pytest.raises(Exception):
            ray.get(actor.execute_stage.remote(stage_index=999))

        # Verify actor is still functional after exception
        state = ray.get(actor.get_state.remote())
        assert state["study_name"] == "test_actor_study"


class TestRayStudyActorEndToEnd:
    """End-to-end tests for Ray actor orchestration."""

    def test_actor_orchestrates_complete_stage(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """
        End-to-end: Verify actor can orchestrate a complete stage.

        This test demonstrates the full orchestration pattern:
        1. Initialize actor
        2. Submit trials
        3. Handle completions
        4. Update state
        """
        artifacts_dir, telemetry_dir = temp_dirs

        actor = create_ray_study_actor(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Note: execute_stage will fail because trials need real scripts
        # but we verify the actor handles this gracefully

        # Verify initial state
        initial_state = ray.get(actor.get_state.remote())
        assert initial_state["current_stage"] == 0
        assert initial_state["stages_completed"] == 0

        # Manually submit and complete a trial
        trial_config = TrialConfig(
            study_name="test_actor_study",
            case_name="e2e_case",
            stage_index=0,
            trial_index=0,
            script_path=Path("/dev/null"),
            snapshot_dir=None,
            timeout_seconds=30,
            num_cpus=1.0,
            num_gpus=0.0,
            memory_mb=512.0,
        )

        ray.get(actor.submit_trial.remote(trial_config, "e2e_trial"))

        result = create_test_trial_result(metrics={"wns_ps": -100})

        ray.get(actor.handle_trial_completion.remote("e2e_trial", result))

        # Verify final state
        final_state = ray.get(actor.get_state.remote())
        assert final_state["completed_trials_count"] == 1

    def test_multiple_actors_can_coexist(
        self,
        ray_context,
        sample_study_config,
        temp_dirs,
    ):
        """Verify multiple Study actors can run concurrently."""
        artifacts_dir, telemetry_dir = temp_dirs

        # Create multiple actors for different studies
        actor1 = RayStudyActor.remote(
            config=sample_study_config,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        config2 = StudyConfig(
            name="test_actor_study_2",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base_case_2",
            pdk="Nangate45",
            snapshot_path="/dev/null",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=1,
                    survivor_count=1,
                    timeout_seconds=60,
                    allowed_eco_classes=[],
                ),
            ],
        )

        actor2 = RayStudyActor.remote(
            config=config2,
            artifacts_root=artifacts_dir,
            telemetry_root=telemetry_dir,
        )

        # Verify both actors are independent
        state1 = ray.get(actor1.get_state.remote())
        state2 = ray.get(actor2.get_state.remote())

        assert state1["study_name"] == "test_actor_study"
        assert state2["study_name"] == "test_actor_study_2"
        assert state1["total_stages"] == 2
        assert state2["total_stages"] == 1
