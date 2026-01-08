"""Ray-based parallel trial execution for Noodle 2."""

import logging
from pathlib import Path
from typing import Any

import ray

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
        Submit a trial as a Ray task.

        Args:
            config: Trial configuration with resource requirements

        Returns:
            Ray ObjectRef for the submitted task
        """
        # Submit with explicit resource requirements
        task_ref = execute_trial_remote.options(
            num_cpus=config.num_cpus,
            num_gpus=config.num_gpus,
            memory=int(config.memory_mb * 1024 * 1024),  # Convert MB to bytes
        ).remote(
            config=config,
            artifacts_root=str(self.artifacts_root),
            docker_config=self.docker_config,
        )

        logger.info(
            f"Submitted trial {config.study_name}/{config.case_name}/stage_{config.stage_index}/trial_{config.trial_index} "
            f"with {config.num_cpus} CPUs, {config.num_gpus} GPUs, {config.memory_mb} MB"
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
