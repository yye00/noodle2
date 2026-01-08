"""Study resumption from checkpoints.

Enables long-running Studies to be interrupted and resumed from the last
completed stage. Checkpoints are saved after each stage completion and contain
all necessary state to resume execution.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json


@dataclass
class StageCheckpoint:
    """
    Checkpoint for a completed Stage.

    Captures:
    - Stage index and configuration
    - Survivor cases that advanced to next stage
    - Stage performance metrics
    - Completion timestamp
    """

    stage_index: int
    stage_name: str
    completed_at: str  # ISO 8601 timestamp
    survivor_case_ids: list[str]  # Case IDs that advanced
    trials_completed: int
    trials_failed: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "completed_at": self.completed_at,
            "survivor_case_ids": self.survivor_case_ids,
            "trials_completed": self.trials_completed,
            "trials_failed": self.trials_failed,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageCheckpoint":
        """Deserialize from dictionary."""
        return cls(
            stage_index=data["stage_index"],
            stage_name=data["stage_name"],
            completed_at=data["completed_at"],
            survivor_case_ids=data["survivor_case_ids"],
            trials_completed=data["trials_completed"],
            trials_failed=data["trials_failed"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class StudyCheckpoint:
    """
    Complete Study checkpoint for resumption.

    Captures:
    - Study configuration identifier
    - Last completed stage index
    - Checkpoints for all completed stages
    - Resumption metadata
    """

    study_name: str
    last_completed_stage_index: int  # -1 if no stages completed
    completed_stages: list[StageCheckpoint]
    checkpoint_version: str = "1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON export."""
        return {
            "study_name": self.study_name,
            "last_completed_stage_index": self.last_completed_stage_index,
            "completed_stages": [stage.to_dict() for stage in self.completed_stages],
            "checkpoint_version": self.checkpoint_version,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StudyCheckpoint":
        """Deserialize from dictionary."""
        completed_stages = [
            StageCheckpoint.from_dict(stage_data)
            for stage_data in data["completed_stages"]
        ]
        return cls(
            study_name=data["study_name"],
            last_completed_stage_index=data["last_completed_stage_index"],
            completed_stages=completed_stages,
            checkpoint_version=data.get("checkpoint_version", "1.0"),
            created_at=data["created_at"],
            metadata=data.get("metadata", {}),
        )

    def get_next_stage_index(self) -> int:
        """
        Get the index of the next stage to execute.

        Returns:
            Stage index to resume from (0 if no stages completed)
        """
        return self.last_completed_stage_index + 1

    def is_stage_completed(self, stage_index: int) -> bool:
        """
        Check if a stage has been completed.

        Args:
            stage_index: Stage index to check

        Returns:
            True if stage is completed, False otherwise
        """
        return stage_index <= self.last_completed_stage_index


def save_checkpoint(
    checkpoint: StudyCheckpoint, artifact_dir: Path | str
) -> Path:
    """
    Save Study checkpoint to disk.

    Args:
        checkpoint: StudyCheckpoint to save
        artifact_dir: Directory to save checkpoint (typically Study artifact root)

    Returns:
        Path to saved checkpoint file

    Raises:
        OSError: If file cannot be written
    """
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    checkpoint_path = artifact_dir / "study_checkpoint.json"

    with open(checkpoint_path, "w") as f:
        json.dump(checkpoint.to_dict(), f, indent=2)

    return checkpoint_path


def load_checkpoint(checkpoint_path: Path | str) -> StudyCheckpoint:
    """
    Load Study checkpoint from disk.

    Args:
        checkpoint_path: Path to checkpoint JSON file

    Returns:
        StudyCheckpoint object

    Raises:
        FileNotFoundError: If checkpoint file doesn't exist
        ValueError: If checkpoint is invalid or corrupted
    """
    checkpoint_path = Path(checkpoint_path)

    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")

    try:
        with open(checkpoint_path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid checkpoint JSON: {e}")

    try:
        checkpoint = StudyCheckpoint.from_dict(data)
    except (KeyError, TypeError) as e:
        raise ValueError(f"Malformed checkpoint data: {e}")

    return checkpoint


def create_stage_checkpoint(
    stage_index: int,
    stage_name: str,
    survivor_case_ids: list[str],
    trials_completed: int,
    trials_failed: int,
    metadata: dict[str, Any] | None = None,
) -> StageCheckpoint:
    """
    Create a checkpoint for a completed Stage.

    Args:
        stage_index: Index of the completed stage
        stage_name: Name of the completed stage
        survivor_case_ids: Case IDs that survived and advanced
        trials_completed: Number of successful trials
        trials_failed: Number of failed trials
        metadata: Optional additional metadata

    Returns:
        StageCheckpoint object
    """
    return StageCheckpoint(
        stage_index=stage_index,
        stage_name=stage_name,
        completed_at=datetime.now(timezone.utc).isoformat(),
        survivor_case_ids=survivor_case_ids,
        trials_completed=trials_completed,
        trials_failed=trials_failed,
        metadata=metadata or {},
    )


def update_checkpoint_after_stage(
    checkpoint: StudyCheckpoint,
    stage_checkpoint: StageCheckpoint,
) -> StudyCheckpoint:
    """
    Update Study checkpoint after a stage completes.

    Args:
        checkpoint: Current StudyCheckpoint
        stage_checkpoint: Checkpoint for the just-completed stage

    Returns:
        Updated StudyCheckpoint
    """
    # Add stage checkpoint to completed stages
    completed_stages = checkpoint.completed_stages + [stage_checkpoint]

    # Update last completed stage index
    last_completed = stage_checkpoint.stage_index

    return StudyCheckpoint(
        study_name=checkpoint.study_name,
        last_completed_stage_index=last_completed,
        completed_stages=completed_stages,
        checkpoint_version=checkpoint.checkpoint_version,
        created_at=checkpoint.created_at,  # Preserve original creation time
        metadata=checkpoint.metadata,
    )


def initialize_checkpoint(study_name: str) -> StudyCheckpoint:
    """
    Initialize a new Study checkpoint (no stages completed).

    Args:
        study_name: Name of the Study

    Returns:
        Fresh StudyCheckpoint with no completed stages
    """
    return StudyCheckpoint(
        study_name=study_name,
        last_completed_stage_index=-1,  # No stages completed
        completed_stages=[],
    )


def find_checkpoint(artifact_dir: Path | str) -> Path | None:
    """
    Find checkpoint file in Study artifact directory.

    Args:
        artifact_dir: Study artifact directory

    Returns:
        Path to checkpoint file if it exists, None otherwise
    """
    artifact_dir = Path(artifact_dir)
    checkpoint_path = artifact_dir / "study_checkpoint.json"

    if checkpoint_path.exists():
        return checkpoint_path

    return None


def should_skip_stage(
    checkpoint: StudyCheckpoint, stage_index: int
) -> tuple[bool, str]:
    """
    Determine if a stage should be skipped during resumption.

    Args:
        checkpoint: Current StudyCheckpoint
        stage_index: Stage index to check

    Returns:
        Tuple of (should_skip: bool, reason: str)
        If should_skip=True, reason explains why
    """
    if checkpoint.is_stage_completed(stage_index):
        stage_checkpoint = None
        for sc in checkpoint.completed_stages:
            if sc.stage_index == stage_index:
                stage_checkpoint = sc
                break

        if stage_checkpoint:
            reason = (
                f"Stage {stage_index} ('{stage_checkpoint.stage_name}') "
                f"already completed at {stage_checkpoint.completed_at}"
            )
        else:
            reason = f"Stage {stage_index} already completed (no checkpoint details)"

        return True, reason

    return False, ""


def get_survivor_cases_for_stage(
    checkpoint: StudyCheckpoint, stage_index: int
) -> list[str]:
    """
    Get survivor case IDs that should be used for a resumed stage.

    Args:
        checkpoint: Current StudyCheckpoint
        stage_index: Stage index to get survivors for

    Returns:
        List of case IDs to use as input for this stage.
        Returns empty list if this is stage 0 or if previous stage not completed.

    Note:
        - For stage 0: returns [] (use base case)
        - For stage N: returns survivors from stage N-1
    """
    if stage_index == 0:
        return []  # Base case, no previous stage

    # Get survivors from previous stage
    previous_stage_index = stage_index - 1

    for stage_checkpoint in checkpoint.completed_stages:
        if stage_checkpoint.stage_index == previous_stage_index:
            return stage_checkpoint.survivor_case_ids

    # Previous stage not found in checkpoint (shouldn't happen if properly validated)
    return []


def validate_resumption(
    checkpoint: StudyCheckpoint, total_stages: int
) -> tuple[bool, list[str]]:
    """
    Validate that resumption is possible and safe.

    Args:
        checkpoint: StudyCheckpoint to validate
        total_stages: Total number of stages in Study configuration

    Returns:
        Tuple of (is_valid: bool, issues: list[str])
        If is_valid=False, issues contains list of validation errors
    """
    issues = []

    # Check if already fully completed
    if checkpoint.last_completed_stage_index >= total_stages - 1:
        issues.append(
            f"Study already fully completed (last stage: {checkpoint.last_completed_stage_index}, "
            f"total stages: {total_stages})"
        )

    # Check for gaps in completed stages
    completed_indices = {sc.stage_index for sc in checkpoint.completed_stages}
    expected_indices = set(range(checkpoint.last_completed_stage_index + 1))

    missing = expected_indices - completed_indices
    if missing:
        issues.append(
            f"Missing stage checkpoints for indices: {sorted(missing)}"
        )

    # Check stage checkpoint ordering
    for i, stage_checkpoint in enumerate(checkpoint.completed_stages):
        if stage_checkpoint.stage_index != i:
            issues.append(
                f"Stage checkpoint order mismatch: "
                f"checkpoint {i} has stage_index {stage_checkpoint.stage_index}"
            )

    return len(issues) == 0, issues
