"""Ray-based parallel trial execution for Noodle 2."""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import ray

from src.controller.early_stopping import (
    EarlyStoppingConfig,
    SurvivorDeterminationResult,
    can_determine_survivors_early,
)
from src.trial_runner.docker_runner import DockerRunConfig
from src.trial_runner.trial import Trial, TrialConfig, TrialResult

logger = logging.getLogger(__name__)


@ray.remote
def execute_trial_remote(
    config: TrialConfig,
    artifacts_root: str | Path = "artifacts",
    docker_config: DockerRunConfig | None = None,
) -> TrialResult:
    """
    Execute a single trial as a Ray remote function.

    This function runs in a separate Ray worker process and executes
    a trial in complete isolation.

    Args:
        config: Trial configuration with resource requirements
        artifacts_root: Root directory for artifacts
        docker_config: Docker configuration

    Returns:
        TrialResult with complete execution details

    Notes:
        - This function is decorated with @ray.remote and is executed
          on a Ray worker node
        - Resource requirements from TrialConfig are used by the caller
          via .options(num_cpus=..., memory=...)
        - Each trial executes in an isolated Docker container
        - Artifacts are written to shared filesystem
    """
    # Print artifact root path for Ray Dashboard visibility
    trial_id = f"{config.study_name}/{config.case_name}/stage_{config.stage_index}/trial_{config.trial_index}"
    artifact_path = Path(artifacts_root) / config.study_name / config.case_name / f"stage_{config.stage_index}" / f"trial_{config.trial_index}"

    logger.info(f"[Ray Task] Executing trial: {trial_id}")
    logger.info(f"[Ray Task] Artifact path: {artifact_path}")
    print(f"[TRIAL_ARTIFACT_ROOT] {artifact_path}")  # For Ray Dashboard parsing

    # Create and execute trial
    trial = Trial(
        config=config,
        artifacts_root=artifacts_root,
        docker_config=docker_config,
    )

    result = trial.execute()

    logger.info(f"[Ray Task] Trial {trial_id} completed: success={result.success}, rc={result.return_code}")
    return result


class RayTrialExecutor:
    """
    Manages parallel execution of trials using Ray.

    Key responsibilities:
    - Submit trials as Ray tasks with explicit resource requirements
    - Execute multiple trials in parallel within a stage
    - Collect and aggregate results
    - Handle failures gracefully

    Ray Integration:
    - Each trial is submitted as a Ray remote task
    - Resource requirements are specified per-trial
    - Ray scheduler handles parallel execution
    - Results are collected via ray.get()
    """

    def __init__(
        self,
        artifacts_root: str | Path = "artifacts",
        docker_config: DockerRunConfig | None = None,
    ) -> None:
        """
        Initialize Ray trial executor.

        Args:
            artifacts_root: Root directory for trial artifacts
            docker_config: Docker execution configuration
        """
        self.artifacts_root = Path(artifacts_root)
        self.docker_config = docker_config

        # Verify Ray is initialized
        if not ray.is_initialized():
            raise RuntimeError(
                "Ray is not initialized. Call ray.init() before using RayTrialExecutor."
            )

    def submit_trial(self, config: TrialConfig) -> ray.ObjectRef:
        """
        Submit a trial as a Ray task with metadata for dashboard visibility.

        Args:
            config: Trial configuration with resource requirements

        Returns:
            Ray ObjectRef for the submitted task

        Notes:
            Task metadata is attached to enable filtering and sorting in Ray Dashboard:
            - Task name follows pattern: study/case/stage_N/trial_M
            - Metadata includes: study_name, case_name, stage_index, trial_index
            - ECO name is included if present in config.metadata
        """
        # Generate task name and metadata for Ray Dashboard
        task_name = self.format_task_name(config)
        task_metadata = self.extract_metadata_from_config(config)

        # Submit with explicit resource requirements and metadata
        task_ref = execute_trial_remote.options(
            num_cpus=config.num_cpus,
            num_gpus=config.num_gpus,
            memory=int(config.memory_mb * 1024 * 1024),  # Convert MB to bytes
            name=task_name,  # Task name visible in Ray Dashboard
            # Note: Ray doesn't support arbitrary metadata in .options()
            # but the task name and logs provide discoverability
        ).remote(
            config=config,
            artifacts_root=str(self.artifacts_root),
            docker_config=self.docker_config,
        )

        logger.info(
            f"Submitted Ray task '{task_name}' "
            f"with {config.num_cpus} CPUs, {config.num_gpus} GPUs, {config.memory_mb} MB "
            f"metadata={task_metadata}"
        )

        return task_ref

    def execute_trials_parallel(
        self, configs: list[TrialConfig]
    ) -> list[TrialResult]:
        """
        Execute multiple trials in parallel using Ray.

        Args:
            configs: List of trial configurations

        Returns:
            List of trial results in the same order as configs
        """
        if not configs:
            return []

        logger.info(f"Executing {len(configs)} trials in parallel via Ray")

        # Submit all trials as Ray tasks
        task_refs = [self.submit_trial(config) for config in configs]

        # Wait for all trials to complete and collect results
        results = ray.get(task_refs)

        logger.info(
            f"Completed {len(results)} trials: "
            f"{sum(1 for r in results if r.success)} successful, "
            f"{sum(1 for r in results if not r.success)} failed"
        )

        return results

    def execute_trial_sync(self, config: TrialConfig) -> TrialResult:
        """
        Execute a single trial synchronously.

        This is a convenience method for single-trial execution.

        Args:
            config: Trial configuration

        Returns:
            TrialResult
        """
        task_ref = self.submit_trial(config)
        result = ray.get(task_ref)
        return result

    @staticmethod
    def get_cluster_resources() -> dict[str, Any]:
        """
        Get current Ray cluster resource availability.

        Returns:
            Dictionary with cluster resource information
        """
        if not ray.is_initialized():
            return {}

        return {
            "available": ray.available_resources(),
            "total": ray.cluster_resources(),
        }

    @staticmethod
    def format_task_name(config: TrialConfig) -> str:
        """
        Format a Ray task name from trial configuration.

        This provides a consistent naming convention for Ray Dashboard display.

        Args:
            config: Trial configuration

        Returns:
            Formatted task name string

        Example:
            >>> config = TrialConfig(
            ...     study_name="study1",
            ...     case_name="base_case",
            ...     stage_index=0,
            ...     trial_index=5,
            ...     metadata={"eco_name": "buffer_insertion"}
            ... )
            >>> RayTrialExecutor.format_task_name(config)
            "study1/base_case/stage_0/trial_5/buffer_insertion"
        """
        task_name = f"{config.study_name}/{config.case_name}/stage_{config.stage_index}/trial_{config.trial_index}"
        if "eco_name" in config.metadata:
            task_name = f"{task_name}/{config.metadata['eco_name']}"
        return task_name

    @staticmethod
    def extract_metadata_from_config(config: TrialConfig) -> dict[str, Any]:
        """
        Extract Ray Dashboard metadata from trial configuration.

        This provides structured metadata for filtering and sorting in Ray Dashboard.

        Args:
            config: Trial configuration

        Returns:
            Dictionary with metadata fields for Ray Dashboard

        Example:
            >>> config = TrialConfig(
            ...     study_name="study1",
            ...     case_name="base_case",
            ...     stage_index=0,
            ...     trial_index=5,
            ...     metadata={"eco_name": "buffer_insertion"}
            ... )
            >>> RayTrialExecutor.extract_metadata_from_config(config)
            {
                "study_name": "study1",
                "case_name": "base_case",
                "stage_index": 0,
                "trial_index": 5,
                "eco_name": "buffer_insertion"
            }
        """
        metadata = {
            "study_name": config.study_name,
            "case_name": config.case_name,
            "stage_index": config.stage_index,
            "trial_index": config.trial_index,
        }

        # Add ECO name if present
        if "eco_name" in config.metadata:
            metadata["eco_name"] = config.metadata["eco_name"]

        # Add execution mode
        if hasattr(config, "execution_mode") and config.execution_mode:
            metadata["execution_mode"] = config.execution_mode.value

        return metadata

    def execute_trials_with_early_stopping(
        self,
        configs: list[TrialConfig],
        required_survivor_count: int,
        early_stopping_config: EarlyStoppingConfig,
        progress_callback: Callable[[list[TrialResult], int], None] | None = None,
    ) -> tuple[list[TrialResult], list[str], int]:
        """
        Execute trials in parallel with early stopping when survivors are determined.

        This method incrementally checks completed trials and cancels remaining trials
        once survivors can be confidently determined, saving compute resources.

        Args:
            configs: List of trial configurations to execute
            required_survivor_count: Number of survivors required
            early_stopping_config: Configuration for early stopping behavior
            progress_callback: Optional callback called with (results_so_far, remaining_count)

        Returns:
            Tuple of:
            - list[TrialResult]: All completed trial results
            - list[str]: Case IDs of cancelled trials
            - int: Number of trials saved by early stopping

        Notes:
            - Uses ray.wait() to check completed trials incrementally
            - Evaluates survivor determination after each completion
            - Cancels remaining trials when survivors are determined
            - All completed trials are returned regardless of success
        """
        if not configs:
            return [], [], 0

        logger.info(
            f"Executing {len(configs)} trials with early stopping "
            f"(policy={early_stopping_config.policy.value}, survivors={required_survivor_count})"
        )

        # Submit all trials as Ray tasks
        task_refs = [self.submit_trial(config) for config in configs]
        config_map = {task_refs[i]: configs[i] for i in range(len(configs))}

        # Track results and remaining tasks
        completed_results: list[TrialResult] = []
        remaining_refs = task_refs.copy()
        cancelled_case_ids: list[str] = []

        # Process trials as they complete
        while remaining_refs:
            # Wait for next batch of completions (timeout 0.1s for responsiveness)
            ready_refs, remaining_refs = ray.wait(
                remaining_refs, num_returns=1, timeout=0.1
            )

            if not ready_refs:
                # No completions yet, continue waiting
                continue

            # Collect completed results
            for ref in ready_refs:
                try:
                    result = ray.get(ref)
                    completed_results.append(result)
                    logger.info(
                        f"Trial completed: {result.config.case_name} "
                        f"(success={result.success}, {len(completed_results)}/{len(configs)})"
                    )
                except Exception as e:
                    logger.error(f"Trial failed with exception: {e}")
                    # Continue processing other trials

            # Call progress callback if provided
            if progress_callback:
                progress_callback(completed_results, len(remaining_refs))

            # Check if we can determine survivors early
            determination = can_determine_survivors_early(
                config=early_stopping_config,
                completed_results=completed_results,
                required_survivor_count=required_survivor_count,
                total_trial_budget=len(configs),
            )

            if determination.can_determine and remaining_refs:
                # We can determine survivors - cancel remaining trials
                trials_saved = len(remaining_refs)
                logger.info(
                    f"Early stopping triggered: {determination.reason}"
                )
                logger.info(
                    f"Cancelling {trials_saved} remaining trials "
                    f"(survivors: {determination.survivors})"
                )

                # Cancel remaining Ray tasks
                for ref in remaining_refs:
                    try:
                        ray.cancel(ref, force=True)
                        config = config_map[ref]
                        cancelled_case_ids.append(config.case_name)
                        logger.info(f"Cancelled trial: {config.case_name}")
                    except Exception as e:
                        logger.warning(f"Failed to cancel task: {e}")

                # Clear remaining refs since we've cancelled them
                remaining_refs = []

                logger.info(
                    f"Early stopping complete: {len(completed_results)} trials completed, "
                    f"{trials_saved} trials saved"
                )

                return completed_results, cancelled_case_ids, trials_saved

        # All trials completed without early stopping
        logger.info(
            f"All {len(completed_results)} trials completed "
            f"(no early stopping triggered)"
        )

        return completed_results, [], 0


@dataclass
class EarlyStoppingExecutionResult:
    """Result of trial execution with early stopping."""

    completed_results: list[TrialResult]
    cancelled_case_ids: list[str]
    trials_saved: int
    determination: SurvivorDeterminationResult | None
    total_trials: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "completed_count": len(self.completed_results),
            "cancelled_count": len(self.cancelled_case_ids),
            "cancelled_case_ids": self.cancelled_case_ids,
            "trials_saved": self.trials_saved,
            "total_trials": self.total_trials,
            "early_stopped": self.trials_saved > 0,
            "determination": self.determination.to_dict() if self.determination else None,
            "metadata": self.metadata,
        }

    @property
    def compute_savings_percent(self) -> float:
        """Calculate compute savings as percentage of total trials."""
        if self.total_trials == 0:
            return 0.0
        return (self.trials_saved / self.total_trials) * 100
