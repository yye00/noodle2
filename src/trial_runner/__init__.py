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
from src.trial_runner.provenance import (
    ToolProvenance,
    create_provenance,
    query_openroad_version,
)
from src.trial_runner.ray_executor import RayTrialExecutor, execute_trial_remote
from src.trial_runner.tcl_generator import (
    generate_trial_script,
    write_trial_script,
)
from src.trial_runner.command_logging import (
    CommandLogEntry,
    CommandLogParser,
    analyze_command_log,
    format_command_summary,
    generate_tcl_logging_epilogue,
    generate_tcl_logging_prologue,
)
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
    "generate_trial_script",
    "write_trial_script",
    "ToolProvenance",
    "create_provenance",
    "query_openroad_version",
    "CommandLogEntry",
    "CommandLogParser",
    "generate_tcl_logging_prologue",
    "generate_tcl_logging_epilogue",
    "format_command_summary",
    "analyze_command_log",
]
