"""Ray actor-based controller for stateful Study orchestration.

This module provides a Ray actor implementation of the Study controller,
enabling fault-tolerant, stateful orchestration of long-running experiments.

Key benefits:
- Centralized state management in Ray actor
- Asynchronous trial submission and callback handling
- Fault-tolerance through Ray's actor restart mechanisms
- Clean separation between control plane (actor) and execution plane (tasks)
"""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ray

from src.controller.case import Case, CaseGraph
from src.controller.study import StudyConfig
from src.controller.telemetry import StageTelemetry, StudyTelemetry, TelemetryEmitter
from src.controller.types import ExecutionMode, StageConfig
from src.trial_runner.ray_executor import execute_trial_remote
from src.trial_runner.trial import TrialConfig, TrialResult

logger = logging.getLogger(__name__)


@dataclass
class ActorStudyState:
    """
    Stateful Study state maintained by Ray actor.

    This represents the complete mutable state of a Study execution,
    allowing the actor to track progress, handle failures, and make
    decisions deterministically.
    """

    study_name: str
    safety_domain: str
    total_stages: int
    current_stage: int = 0
    stages_completed: int = 0
    active_trials: dict[str, ray.ObjectRef] = field(default_factory=dict)
    completed_trials: list[TrialResult] = field(default_factory=list)
    survivors: list[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None
    start_time: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Convert state to dictionary for serialization."""
        return {
            "study_name": self.study_name,
            "safety_domain": self.safety_domain,
            "total_stages": self.total_stages,
            "current_stage": self.current_stage,
            "stages_completed": self.stages_completed,
            "active_trials_count": len(self.active_trials),
            "completed_trials_count": len(self.completed_trials),
            "survivors_count": len(self.survivors),
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "elapsed_seconds": time.time() - self.start_time,
        }


@ray.remote
class RayStudyActor:
    """
    Ray actor for stateful Study orchestration.

    This actor manages the complete lifecycle of a Study:
    1. Initialize and validate Study configuration
    2. Submit trials to Ray task queue with resource requirements
    3. Handle trial completion callbacks
    4. Update Study state deterministically
    5. Make progression decisions (survivor selection, stage transitions)
    6. Emit telemetry and maintain audit trail

    The actor provides fault-tolerance through Ray's actor restart
    mechanisms, allowing Studies to survive transient failures.

    Example usage:
        # Create and start actor
        actor = RayStudyActor.remote(config, artifacts_root)

        # Submit stage for execution
        ray.get(actor.execute_stage.remote(0))

        # Get current state
        state = ray.get(actor.get_state.remote())
    """

    def __init__(
        self,
        config: StudyConfig,
        artifacts_root: str | Path = "artifacts",
        telemetry_root: str | Path = "telemetry",
    ) -> None:
        """
        Initialize Ray actor for Study orchestration.

        Args:
            config: Study configuration
            artifacts_root: Root directory for artifacts
            telemetry_root: Root directory for telemetry
        """
        self.config = config
        self.artifacts_root = Path(artifacts_root)
        self.telemetry_root = Path(telemetry_root)

        # Initialize stateful Study state
        self.state = ActorStudyState(
            study_name=config.name,
            safety_domain=config.safety_domain.value,
            total_stages=len(config.stages),
        )

        # Initialize case graph for tracking lineage
        self.case_graph = CaseGraph()

        # Initialize telemetry emitter
        self.telemetry_emitter = TelemetryEmitter(
            study_name=config.name,
            telemetry_root=telemetry_root,
        )

        # Initialize Study telemetry
        self.study_telemetry = StudyTelemetry(
            study_name=config.name,
            safety_domain=config.safety_domain.value,
            total_stages=len(config.stages),
        )

        logger.info(f"RayStudyActor initialized: study={config.name}, stages={len(config.stages)}")

    def get_state(self) -> dict[str, Any]:
        """
        Get current Study state.

        Returns:
            Dictionary representation of current state
        """
        return self.state.to_dict()

    def submit_trial(
        self,
        trial_config: TrialConfig,
        trial_id: str,
    ) -> ray.ObjectRef:
        """
        Submit a single trial to Ray task queue.

        Args:
            trial_config: Trial configuration with resource requirements
            trial_id: Unique trial identifier

        Returns:
            Ray ObjectRef for trial result
        """
        # Submit trial as Ray remote task with resource requirements
        result_ref = execute_trial_remote.options(
            num_cpus=trial_config.num_cpus,
            memory=trial_config.memory_mb * 1024 * 1024,  # Convert MB to bytes
            num_gpus=trial_config.num_gpus,
        ).remote(
            config=trial_config,
            artifacts_root=str(self.artifacts_root),
            docker_config=None,
        )

        # Track active trial
        self.state.active_trials[trial_id] = result_ref

        logger.info(f"Trial submitted: {trial_id}, cpus={trial_config.num_cpus}, mem={trial_config.memory_mb}MB")

        return result_ref

    def handle_trial_completion(
        self,
        trial_id: str,
        result: TrialResult,
    ) -> None:
        """
        Handle trial completion callback.

        Updates Study state deterministically based on trial result.

        Args:
            trial_id: Trial identifier
            result: Trial execution result
        """
        # Remove from active trials
        if trial_id in self.state.active_trials:
            del self.state.active_trials[trial_id]

        # Add to completed trials
        self.state.completed_trials.append(result)

        logger.info(
            f"Trial completed: {trial_id}, success={result.success}, "
            f"active={len(self.state.active_trials)}, "
            f"completed={len(self.state.completed_trials)}"
        )

    def execute_stage(
        self,
        stage_index: int,
        cases_to_run: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a complete stage with all trials.

        This method demonstrates the actor-based orchestration pattern:
        1. Submit all trials asynchronously
        2. Wait for completion
        3. Handle results via callbacks
        4. Update state deterministically
        5. Return stage summary

        Args:
            stage_index: Stage index (0-based)
            cases_to_run: List of case IDs to run (default: base case only)

        Returns:
            Dictionary with stage execution summary
        """
        if stage_index >= len(self.config.stages):
            raise ValueError(f"Invalid stage index: {stage_index}")

        stage_config = self.config.stages[stage_index]
        self.state.current_stage = stage_index

        # Default to base case if no cases specified
        if cases_to_run is None:
            cases_to_run = [self.config.base_case.name]

        logger.info(f"Executing stage {stage_index}: {len(cases_to_run)} cases")

        # Submit all trials for this stage
        trial_refs: dict[str, ray.ObjectRef] = {}

        for case_name in cases_to_run:
            # Create trial configuration
            trial_config = TrialConfig(
                study_name=self.config.name,
                case_name=case_name,
                stage_index=stage_index,
                trial_index=0,  # Single trial per case for this implementation
                script_path=Path("/dev/null"),  # Placeholder
                snapshot_dir=None,
                timeout_seconds=stage_config.timeout_seconds,
                num_cpus=1.0,
                memory_mb=2048.0,
                num_gpus=0.0,
            )

            trial_id = f"{self.config.name}/{case_name}/stage_{stage_index}/trial_0"
            result_ref = self.submit_trial(trial_config, trial_id)
            trial_refs[trial_id] = result_ref

        # Wait for all trials to complete
        logger.info(f"Waiting for {len(trial_refs)} trials to complete...")

        for trial_id, result_ref in trial_refs.items():
            try:
                result = ray.get(result_ref, timeout=stage_config.timeout_seconds + 60)
                self.handle_trial_completion(trial_id, result)
            except Exception as e:
                logger.error(f"Trial {trial_id} failed: {e}")
                # Create failure result
                failure_result = TrialResult(
                    success=False,
                    return_code=-1,
                    stdout="",
                    stderr=str(e),
                    metrics=None,
                    artifact_path=Path("/dev/null"),
                    execution_time_seconds=0.0,
                )
                self.handle_trial_completion(trial_id, failure_result)

        # Update stage completion
        self.state.stages_completed = stage_index + 1

        # Prepare stage summary
        successful_trials = [r for r in self.state.completed_trials if r.success]

        summary = {
            "stage_index": stage_index,
            "trials_executed": len(trial_refs),
            "trials_successful": len(successful_trials),
            "trials_failed": len(trial_refs) - len(successful_trials),
            "state": self.state.to_dict(),
        }

        logger.info(f"Stage {stage_index} complete: {summary}")

        return summary

    def update_state_deterministically(
        self,
        state_update: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Update Study state deterministically.

        This method ensures all state updates are atomic and traceable.

        Args:
            state_update: Dictionary of state fields to update

        Returns:
            Updated state dictionary
        """
        # Apply updates atomically
        for key, value in state_update.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
                logger.info(f"State updated: {key} = {value}")
            else:
                logger.warning(f"Unknown state field: {key}")

        return self.state.to_dict()

    def abort_study(self, reason: str) -> None:
        """
        Abort the Study execution.

        Args:
            reason: Reason for abortion
        """
        self.state.aborted = True
        self.state.abort_reason = reason
        logger.warning(f"Study aborted: {reason}")

    def is_aborted(self) -> bool:
        """Check if Study is aborted."""
        return self.state.aborted

    def get_telemetry(self) -> dict[str, Any]:
        """
        Get Study telemetry data.

        Returns:
            Dictionary with telemetry data
        """
        return {
            "study_name": self.config.name,
            "state": self.state.to_dict(),
            "completed_trials": len(self.state.completed_trials),
            "active_trials": len(self.state.active_trials),
        }


def create_ray_study_actor(
    config: StudyConfig,
    artifacts_root: str | Path = "artifacts",
    telemetry_root: str | Path = "telemetry",
) -> ray.actor.ActorHandle:
    """
    Create and initialize a Ray actor for Study orchestration.

    Args:
        config: Study configuration
        artifacts_root: Root directory for artifacts
        telemetry_root: Root directory for telemetry

    Returns:
        Ray actor handle

    Example:
        actor = create_ray_study_actor(config)
        state = ray.get(actor.get_state.remote())
    """
    actor = RayStudyActor.remote(
        config=config,
        artifacts_root=artifacts_root,
        telemetry_root=telemetry_root,
    )

    logger.info(f"Created Ray Study actor for: {config.name}")

    return actor
