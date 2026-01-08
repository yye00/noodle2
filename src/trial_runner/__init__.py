"""
Trial runner module - OpenROAD execution in Docker containers.
"""

from src.trial_runner.docker_runner import (
    DockerRunConfig,
    DockerTrialRunner,
    TrialExecutionResult,
)
from src.trial_runner.ray_executor import RayTrialExecutor, execute_trial_remote
from src.trial_runner.trial import Trial, TrialArtifacts, TrialConfig, TrialResult

__all__ = [
    "DockerRunConfig",
    "DockerTrialRunner",
    "TrialExecutionResult",
    "Trial",
    "TrialConfig",
    "TrialResult",
    "TrialArtifacts",
    "RayTrialExecutor",
    "execute_trial_remote",
]
