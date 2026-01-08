"""
Trial runner module - OpenROAD execution in Docker containers.
"""

from src.trial_runner.artifact_index import (
    ArtifactEntry,
    StageArtifactSummary,
    TrialArtifactIndex,
    generate_trial_artifact_index,
)
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
    "TrialArtifactIndex",
    "ArtifactEntry",
    "StageArtifactSummary",
    "generate_trial_artifact_index",
]
