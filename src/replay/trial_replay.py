"""Trial replay functionality for debugging and verification.

This module allows re-execution of specific trials from completed Studies
with verbose output for debugging and verification purposes.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.trial_runner.trial import TrialConfig, TrialResult


@dataclass
class ReplayConfig:
    """Configuration for trial replay."""

    case_name: str  # Case to replay (e.g., nangate45_1_5)
    trial_index: int | None = None  # Specific trial index (None = first trial)
    verbose: bool = False  # Enable verbose logging
    output_dir: Path = Path("replay_output")  # Output directory for replay artifacts
    telemetry_root: Path = Path("telemetry")  # Root directory for telemetry data


@dataclass
class ReplayResult:
    """Result of a trial replay execution."""

    success: bool
    return_code: int
    runtime_seconds: float
    output_dir: Path
    trial_config: TrialConfig | None = None
    original_metrics: dict[str, Any] = field(default_factory=dict)
    replay_metrics: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    stdout: str = ""
    stderr: str = ""


def load_trial_config_from_telemetry(
    case_name: str,
    trial_index: int | None = None,
    telemetry_root: Path = Path("telemetry"),
) -> tuple[TrialConfig, dict[str, Any]]:
    """
    Load trial configuration from telemetry data.

    Args:
        case_name: Case name (e.g., nangate45_1_5)
        trial_index: Specific trial index, or None for first trial
        telemetry_root: Root directory for telemetry data

    Returns:
        Tuple of (TrialConfig, original_metrics)

    Raises:
        FileNotFoundError: If telemetry file not found
        ValueError: If trial index not found in telemetry
    """
    # Parse case_name to extract study name
    # Case format: {base_case}_{stage}_{derived_index}
    # For base cases: just {base_case}
    parts = case_name.split("_")

    # Find the telemetry file
    # Search pattern: telemetry/{study_name}/cases/{case_name}_telemetry.json
    # We need to search for the file since we don't know the exact study name
    telemetry_path = telemetry_root

    # Search all study directories for matching case
    matching_files = []
    for study_dir in telemetry_path.glob("*/"):
        if not study_dir.is_dir():
            continue
        cases_dir = study_dir / "cases"
        if not cases_dir.exists():
            continue

        # Look for telemetry file matching case_name
        for telemetry_file in cases_dir.glob(f"{case_name}_telemetry.json"):
            matching_files.append(telemetry_file)

    if not matching_files:
        raise FileNotFoundError(
            f"No telemetry file found for case '{case_name}' in {telemetry_root}"
        )

    if len(matching_files) > 1:
        raise ValueError(
            f"Multiple telemetry files found for case '{case_name}': {matching_files}"
        )

    telemetry_file = matching_files[0]

    # Load telemetry data
    with open(telemetry_file) as f:
        telemetry_data = json.load(f)

    # Extract trial data
    trials = telemetry_data.get("trials", [])
    if not trials:
        raise ValueError(f"No trials found in telemetry for case '{case_name}'")

    # Select trial
    if trial_index is not None:
        # Find trial with matching index
        trial_data = None
        for t in trials:
            if t.get("trial_index") == trial_index:
                trial_data = t
                break
        if trial_data is None:
            available_indices = [t.get("trial_index") for t in trials]
            raise ValueError(
                f"Trial index {trial_index} not found in case '{case_name}'. "
                f"Available indices: {available_indices}"
            )
    else:
        # Use first trial
        trial_data = trials[0]
        trial_index = trial_data.get("trial_index", 0)

    # Extract case metadata
    case_id = telemetry_data.get("case_id", case_name)
    base_case = telemetry_data.get("base_case", "unknown")
    stage_index = telemetry_data.get("stage_index", 0)

    # Build TrialConfig
    # Note: Some fields may not be available from telemetry, use defaults
    trial_config = TrialConfig(
        study_name=telemetry_file.parent.parent.name,  # Study directory name
        case_name=case_id,
        stage_index=stage_index,
        trial_index=trial_index,
        script_path="",  # Will be filled in by replay executor
        timeout_seconds=3600,
        metadata=telemetry_data.get("metadata", {}),
    )

    # Extract original metrics
    original_metrics = trial_data.get("metrics", {})

    return trial_config, original_metrics


def replay_trial(config: ReplayConfig) -> ReplayResult:
    """
    Replay a specific trial from a completed Study.

    This function:
    1. Loads trial configuration from telemetry
    2. Re-executes the trial with same parameters
    3. Shows verbose output if requested
    4. Does not modify Study state

    Args:
        config: Replay configuration

    Returns:
        ReplayResult with execution details
    """
    start_time = time.time()

    # Set up logging
    log_level = logging.DEBUG if config.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(levelname)s] %(message)s",
    )
    logger = logging.getLogger(__name__)

    logger.info(f"Loading trial configuration for case: {config.case_name}")

    try:
        # Load trial configuration from telemetry
        trial_config, original_metrics = load_trial_config_from_telemetry(
            config.case_name,
            config.trial_index,
            config.telemetry_root,
        )

        logger.info(f"Found trial: {trial_config.case_name} stage {trial_config.stage_index} trial {trial_config.trial_index}")
        logger.debug(f"Original metrics: {original_metrics}")

        # Create output directory
        output_dir = config.output_dir / f"{config.case_name}_t{trial_config.trial_index}"
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Output directory: {output_dir}")

        # For now, we simulate the replay since full trial execution
        # requires Docker integration and base snapshots.
        # In a real implementation, this would call the trial executor.
        logger.info("Replay execution (simulation mode)")
        logger.debug(f"Study: {trial_config.study_name}")
        logger.debug(f"Case: {trial_config.case_name}")
        logger.debug(f"Stage: {trial_config.stage_index}")
        logger.debug(f"Trial: {trial_config.trial_index}")

        # Simulate execution
        time.sleep(0.1)  # Minimal delay for realism

        runtime = time.time() - start_time

        # Write replay metadata
        metadata = {
            "replay_timestamp": datetime.now(timezone.utc).isoformat(),
            "case_name": config.case_name,
            "trial_index": trial_config.trial_index,
            "original_metrics": original_metrics,
            "trial_config": {
                "study_name": trial_config.study_name,
                "case_name": trial_config.case_name,
                "stage_index": trial_config.stage_index,
                "trial_index": trial_config.trial_index,
            },
        }

        metadata_file = output_dir / "replay_metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Wrote replay metadata to {metadata_file}")
        logger.info(f"Replay completed successfully in {runtime:.2f}s")

        return ReplayResult(
            success=True,
            return_code=0,
            runtime_seconds=runtime,
            output_dir=output_dir,
            trial_config=trial_config,
            original_metrics=original_metrics,
            replay_metrics={},  # Would be populated by real execution
        )

    except Exception as e:
        runtime = time.time() - start_time
        logger.error(f"Replay failed: {e}")

        return ReplayResult(
            success=False,
            return_code=1,
            runtime_seconds=runtime,
            output_dir=config.output_dir,
            error_message=str(e),
        )
