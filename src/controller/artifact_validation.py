"""Trial artifact validation for ensuring completeness before marking trials as successful.

This module validates that all required artifacts are present, non-empty, and parseable
before a trial is marked as successful. Missing or invalid artifacts trigger early failure.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ArtifactType(str, Enum):
    """Types of trial artifacts."""

    TIMING_REPORT = "timing_report"
    CONGESTION_REPORT = "congestion_report"
    METRICS_JSON = "metrics_json"
    LOG_FILE = "log_file"
    TCL_SCRIPT = "tcl_script"
    HEATMAP_CSV = "heatmap_csv"


@dataclass
class ArtifactRequirement:
    """Defines a required artifact for a trial."""

    artifact_type: ArtifactType
    path_pattern: str  # Glob pattern or exact path
    required: bool = True
    min_size_bytes: int = 0
    validate_parseable: bool = False
    description: str = ""

    def validate_file(self, artifact_path: Path) -> tuple[bool, str | None]:
        """Validate that the artifact file meets requirements.

        Args:
            artifact_path: Path to the artifact file

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check existence
        if not artifact_path.exists():
            return False, f"Artifact not found: {artifact_path}"

        # Check it's a file
        if not artifact_path.is_file():
            return False, f"Artifact is not a file: {artifact_path}"

        # Check size
        file_size = artifact_path.stat().st_size
        if file_size < self.min_size_bytes:
            return (
                False,
                f"Artifact too small: {file_size} bytes < {self.min_size_bytes} bytes minimum",
            )

        # Check parseability for specific types
        if self.validate_parseable:
            try:
                if self.artifact_type == ArtifactType.METRICS_JSON:
                    with open(artifact_path) as f:
                        json.load(f)
                elif self.artifact_type == ArtifactType.HEATMAP_CSV:
                    # Basic CSV validation - check it has content with commas
                    with open(artifact_path) as f:
                        first_line = f.readline()
                        if "," not in first_line:
                            return False, "CSV file does not contain comma-separated values"
            except json.JSONDecodeError as e:
                return False, f"Invalid JSON: {e}"
            except Exception as e:
                return False, f"Failed to parse artifact: {e}"

        return True, None


@dataclass
class ArtifactChecklist:
    """Defines the complete set of required artifacts for a trial type."""

    trial_type: str  # e.g., "sta_only", "sta_congestion", "visualization"
    requirements: list[ArtifactRequirement] = field(default_factory=list)
    description: str = ""

    def add_requirement(self, requirement: ArtifactRequirement) -> None:
        """Add an artifact requirement to the checklist.

        Args:
            requirement: Artifact requirement to add
        """
        self.requirements.append(requirement)

    def get_required_artifacts(self) -> list[ArtifactRequirement]:
        """Get list of required artifacts.

        Returns:
            List of required artifact requirements
        """
        return [req for req in self.requirements if req.required]

    def get_optional_artifacts(self) -> list[ArtifactRequirement]:
        """Get list of optional artifacts.

        Returns:
            List of optional artifact requirements
        """
        return [req for req in self.requirements if not req.required]


@dataclass
class ArtifactValidationResult:
    """Result of validating trial artifacts."""

    is_complete: bool
    missing_required: list[str] = field(default_factory=list)
    invalid_artifacts: dict[str, str] = field(default_factory=dict)
    present_artifacts: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    validation_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_complete": self.is_complete,
            "missing_required": self.missing_required,
            "invalid_artifacts": self.invalid_artifacts,
            "present_artifacts": self.present_artifacts,
            "missing_optional": self.missing_optional,
            "validation_summary": self.validation_summary,
        }


class ArtifactValidator:
    """Validates trial artifacts against a checklist."""

    def __init__(self, checklist: ArtifactChecklist):
        """Initialize validator with a checklist.

        Args:
            checklist: Artifact checklist defining requirements
        """
        self.checklist = checklist

    def validate(self, artifact_dir: Path) -> ArtifactValidationResult:
        """Validate artifacts in a directory against the checklist.

        Args:
            artifact_dir: Directory containing trial artifacts

        Returns:
            ArtifactValidationResult with validation outcome
        """
        missing_required = []
        invalid_artifacts = {}
        present_artifacts = []
        missing_optional = []

        # Validate each requirement
        for requirement in self.checklist.requirements:
            # Resolve artifact path
            if "*" in requirement.path_pattern:
                # Glob pattern
                matches = list(artifact_dir.glob(requirement.path_pattern))
                if not matches:
                    if requirement.required:
                        missing_required.append(requirement.path_pattern)
                    else:
                        missing_optional.append(requirement.path_pattern)
                    continue

                # Validate first match
                artifact_path = matches[0]
            else:
                # Exact path
                artifact_path = artifact_dir / requirement.path_pattern

                # Check if file exists first
                if not artifact_path.exists():
                    if requirement.required:
                        missing_required.append(requirement.path_pattern)
                    else:
                        missing_optional.append(requirement.path_pattern)
                    continue

            # Check if artifact is valid
            is_valid, error_msg = requirement.validate_file(artifact_path)

            if not is_valid:
                if requirement.required:
                    invalid_artifacts[str(artifact_path)] = error_msg or "Unknown error"
                else:
                    # Optional artifact exists but is invalid
                    invalid_artifacts[str(artifact_path)] = error_msg or "Unknown error"
            else:
                present_artifacts.append(str(artifact_path))

        # Determine overall completeness
        is_complete = len(missing_required) == 0 and len(invalid_artifacts) == 0

        # Generate summary
        summary_parts = []
        if is_complete:
            summary_parts.append(
                f"All required artifacts present and valid ({len(present_artifacts)} artifacts)"
            )
        else:
            if missing_required:
                summary_parts.append(
                    f"Missing {len(missing_required)} required artifact(s): {', '.join(missing_required)}"
                )
            if invalid_artifacts:
                summary_parts.append(
                    f"{len(invalid_artifacts)} invalid artifact(s)"
                )

        validation_summary = "; ".join(summary_parts) if summary_parts else "Validation passed"

        return ArtifactValidationResult(
            is_complete=is_complete,
            missing_required=missing_required,
            invalid_artifacts=invalid_artifacts,
            present_artifacts=present_artifacts,
            missing_optional=missing_optional,
            validation_summary=validation_summary,
        )


# Standard checklists for common trial types
def get_sta_only_checklist() -> ArtifactChecklist:
    """Get artifact checklist for STA-only trials.

    Returns:
        ArtifactChecklist for STA-only trials
    """
    checklist = ArtifactChecklist(
        trial_type="sta_only",
        description="Static Timing Analysis only",
    )

    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.TIMING_REPORT,
            path_pattern="timing_report.txt",
            required=True,
            min_size_bytes=10,
            description="OpenROAD report_checks output",
        )
    )

    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.METRICS_JSON,
            path_pattern="metrics.json",
            required=True,
            min_size_bytes=10,
            validate_parseable=True,
            description="Parsed timing metrics",
        )
    )

    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.LOG_FILE,
            path_pattern="trial.log",
            required=True,
            min_size_bytes=10,
            description="Trial execution log",
        )
    )

    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.TCL_SCRIPT,
            path_pattern="trial.tcl",
            required=True,
            min_size_bytes=10,
            description="TCL script used for trial",
        )
    )

    return checklist


def get_sta_congestion_checklist() -> ArtifactChecklist:
    """Get artifact checklist for STA+congestion trials.

    Returns:
        ArtifactChecklist for STA+congestion trials
    """
    checklist = get_sta_only_checklist()
    checklist.trial_type = "sta_congestion"
    checklist.description = "Static Timing Analysis + Congestion Analysis"

    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.CONGESTION_REPORT,
            path_pattern="congestion_report.rpt",
            required=True,
            min_size_bytes=10,
            description="Global routing congestion report",
        )
    )

    return checklist


def get_visualization_checklist() -> ArtifactChecklist:
    """Get artifact checklist for trials with visualization.

    Returns:
        ArtifactChecklist for visualization trials
    """
    checklist = get_sta_congestion_checklist()
    checklist.trial_type = "visualization"
    checklist.description = "Full analysis with GUI heatmap exports"

    # Heatmaps are optional because GUI mode may not always be available
    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.HEATMAP_CSV,
            path_pattern="heatmaps/placement_density.csv",
            required=False,
            min_size_bytes=10,
            validate_parseable=True,
            description="Placement density heatmap",
        )
    )

    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.HEATMAP_CSV,
            path_pattern="heatmaps/rudy.csv",
            required=False,
            min_size_bytes=10,
            validate_parseable=True,
            description="RUDY congestion heatmap",
        )
    )

    checklist.add_requirement(
        ArtifactRequirement(
            artifact_type=ArtifactType.HEATMAP_CSV,
            path_pattern="heatmaps/routing_congestion.csv",
            required=False,
            min_size_bytes=10,
            validate_parseable=True,
            description="Routing congestion heatmap",
        )
    )

    return checklist
