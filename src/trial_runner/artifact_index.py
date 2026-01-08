"""Artifact indexing and cataloging for trial outputs."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ArtifactEntry:
    """
    Single artifact entry in the index.

    Each entry describes one file produced by the trial,
    with metadata to support navigation and visualization.
    """

    path: Path
    """Relative path from trial root"""

    label: str
    """Human-readable description"""

    content_type: str
    """MIME type or classification (text, csv, image, json, verilog, etc.)"""

    size_bytes: int = 0
    """File size in bytes"""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": str(self.path),
            "label": self.label,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
        }


@dataclass
class TrialArtifactIndex:
    """
    Complete artifact index for a single trial.

    This index enables:
    - Ray Dashboard navigation via deep links
    - Automated artifact validation
    - Content-type-aware visualization
    - Structured exploration of trial outputs
    """

    study_name: str
    case_name: str
    stage_index: int
    trial_index: int

    trial_root: Path
    """Absolute path to trial directory"""

    entries: list[ArtifactEntry] = field(default_factory=list)
    """List of discovered artifacts"""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata (ECO names, timestamps, etc.)"""

    def add_artifact(
        self,
        path: Path,
        label: str,
        content_type: str,
    ) -> None:
        """
        Add an artifact to the index.

        Args:
            path: Absolute path to artifact file
            label: Human-readable description
            content_type: Content type classification
        """
        # Calculate relative path from trial root
        rel_path = path.relative_to(self.trial_root) if path.is_absolute() else path

        # Get file size
        size_bytes = path.stat().st_size if path.exists() else 0

        entry = ArtifactEntry(
            path=rel_path,
            label=label,
            content_type=content_type,
            size_bytes=size_bytes,
        )

        self.entries.append(entry)

    def to_dict(self) -> dict[str, Any]:
        """Convert index to dictionary for JSON serialization."""
        return {
            "study_name": self.study_name,
            "case_name": self.case_name,
            "stage_index": self.stage_index,
            "trial_index": self.trial_index,
            "trial_root": str(self.trial_root),
            "entries": [entry.to_dict() for entry in self.entries],
            "metadata": self.metadata,
        }

    def write_to_file(self, output_path: Path | None = None) -> Path:
        """
        Write artifact index to JSON file.

        Args:
            output_path: Optional custom output path.
                        Defaults to trial_root/artifact_index.json

        Returns:
            Path to written index file
        """
        if output_path is None:
            output_path = self.trial_root / "artifact_index.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(self.to_dict(), f, indent=2)

        return output_path


@dataclass
class StageArtifactSummary:
    """
    Aggregated artifact summary for all trials in a stage.

    This provides:
    - Overview of trial outcomes
    - Links to individual trial artifact indexes
    - Stage-level metrics summary
    """

    study_name: str
    case_name: str
    stage_index: int

    stage_root: Path
    """Absolute path to stage directory"""

    trial_count: int = 0
    """Total number of trials executed"""

    success_count: int = 0
    """Number of successful trials"""

    failure_count: int = 0
    """Number of failed trials"""

    trial_indexes: list[Path] = field(default_factory=list)
    """Paths to individual trial artifact_index.json files"""

    metrics_summary: dict[str, Any] = field(default_factory=dict)
    """Aggregated metrics across all trials"""

    def add_trial(
        self,
        trial_index: int,
        success: bool,
        artifact_index_path: Path,
        metrics: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a trial in the stage summary.

        Args:
            trial_index: Trial number
            success: Whether trial succeeded
            artifact_index_path: Path to trial's artifact_index.json
            metrics: Optional trial metrics to aggregate
        """
        self.trial_count += 1

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        self.trial_indexes.append(artifact_index_path)

        # Aggregate metrics if provided
        if metrics:
            for key, value in metrics.items():
                if key not in self.metrics_summary:
                    self.metrics_summary[key] = []
                self.metrics_summary[key].append(value)

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary for JSON serialization."""
        return {
            "study_name": self.study_name,
            "case_name": self.case_name,
            "stage_index": self.stage_index,
            "stage_root": str(self.stage_root),
            "trial_count": self.trial_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "trial_indexes": [str(p) for p in self.trial_indexes],
            "metrics_summary": self.metrics_summary,
        }

    def write_to_file(self, output_path: Path | None = None) -> Path:
        """
        Write stage summary to JSON file.

        Args:
            output_path: Optional custom output path.
                        Defaults to stage_root/stage_artifact_summary.json

        Returns:
            Path to written summary file
        """
        if output_path is None:
            output_path = self.stage_root / "stage_artifact_summary.json"

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w") as f:
            json.dump(self.to_dict(), f, indent=2)

        return output_path


def infer_content_type(path: Path) -> str:
    """
    Infer content type from file extension.

    Args:
        path: Path to file

    Returns:
        Content type string
    """
    suffix = path.suffix.lower()

    content_type_map = {
        ".txt": "text/plain",
        ".log": "text/plain",
        ".rpt": "text/plain",
        ".json": "application/json",
        ".csv": "text/csv",
        ".v": "text/x-verilog",
        ".vg": "text/x-verilog",
        ".tcl": "text/x-tcl",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".def": "text/x-def",
        ".lef": "text/x-lef",
        ".sdc": "text/x-sdc",
        ".spef": "text/x-spef",
    }

    return content_type_map.get(suffix, "application/octet-stream")


def generate_trial_artifact_index(
    trial_root: Path,
    study_name: str,
    case_name: str,
    stage_index: int,
    trial_index: int,
    eco_names: list[str] | None = None,
) -> TrialArtifactIndex:
    """
    Generate artifact index for a trial by scanning the trial directory.

    Args:
        trial_root: Path to trial directory
        study_name: Study name
        case_name: Case name
        stage_index: Stage index
        trial_index: Trial index
        eco_names: Optional list of ECO names applied in this trial

    Returns:
        TrialArtifactIndex with discovered artifacts
    """
    index = TrialArtifactIndex(
        study_name=study_name,
        case_name=case_name,
        stage_index=stage_index,
        trial_index=trial_index,
        trial_root=trial_root,
    )

    # Add ECO metadata if provided
    if eco_names:
        index.metadata["eco_names"] = eco_names

    # Define expected artifacts with labels
    artifact_patterns = [
        ("timing_report.txt", "Timing Analysis Report (STA)", "text/plain"),
        ("timing.rpt", "Timing Analysis Report", "text/plain"),
        ("sta.rpt", "Static Timing Analysis Report", "text/plain"),
        ("congestion_report.txt", "Congestion Report", "text/plain"),
        ("congestion.rpt", "Congestion Report", "text/plain"),
        ("metrics.json", "Trial Metrics (JSON)", "application/json"),
        ("trial_summary.json", "Trial Summary", "application/json"),
        ("logs/stdout.txt", "OpenROAD stdout", "text/plain"),
        ("logs/stderr.txt", "OpenROAD stderr", "text/plain"),
    ]

    # Add known artifacts
    for pattern, label, content_type in artifact_patterns:
        path = trial_root / pattern
        if path.exists():
            index.add_artifact(path, label, content_type)

    # Find verilog netlists
    for netlist_path in trial_root.glob("*.v"):
        index.add_artifact(
            netlist_path,
            f"Verilog Netlist ({netlist_path.name})",
            "text/x-verilog",
        )

    for netlist_path in trial_root.glob("*.vg"):
        index.add_artifact(
            netlist_path,
            f"Verilog Netlist ({netlist_path.name})",
            "text/x-verilog",
        )

    # Find heatmap CSVs (if present)
    heatmaps_dir = trial_root / "heatmaps"
    if heatmaps_dir.exists():
        for heatmap_path in heatmaps_dir.glob("*.csv"):
            index.add_artifact(
                heatmap_path,
                f"Heatmap: {heatmap_path.stem}",
                "text/csv",
            )

    return index
