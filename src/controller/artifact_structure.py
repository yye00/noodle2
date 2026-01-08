"""Well-organized and self-documenting Study artifact directory structure.

This module defines and enforces Noodle 2's standard artifact directory layout,
ensuring operators can easily navigate Study outputs and find key files.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ArtifactDirectoryLayout:
    """
    Standard directory layout for Study artifacts.

    This defines the canonical structure that all Studies follow,
    making it easy for operators to find results and reports.
    """

    study_root: Path
    """Root directory for the Study"""

    @property
    def config_file(self) -> Path:
        """Study configuration file (study_config.yaml)"""
        return self.study_root / "study_config.yaml"

    @property
    def summary_dir(self) -> Path:
        """Summary reports and high-level results"""
        return self.study_root / "summaries"

    @property
    def cases_dir(self) -> Path:
        """Per-case directories with trial results"""
        return self.study_root / "cases"

    @property
    def stages_dir(self) -> Path:
        """Per-stage summaries and aggregated results"""
        return self.study_root / "stages"

    @property
    def telemetry_dir(self) -> Path:
        """Structured telemetry and metrics"""
        return self.study_root / "telemetry"

    @property
    def reports_dir(self) -> Path:
        """Generated reports (safety, legality, diffs)"""
        return self.study_root / "reports"

    @property
    def checkpoints_dir(self) -> Path:
        """Study checkpoints for resumption"""
        return self.study_root / "checkpoints"

    @property
    def logs_dir(self) -> Path:
        """Controller and orchestration logs"""
        return self.study_root / "logs"

    @property
    def readme_file(self) -> Path:
        """README explaining directory structure"""
        return self.study_root / "README.txt"

    def case_dir(self, case_name: str) -> Path:
        """Get directory for a specific case."""
        return self.cases_dir / case_name

    def case_stage_dir(self, case_name: str, stage_index: int) -> Path:
        """Get directory for a case at a specific stage."""
        return self.case_dir(case_name) / f"stage_{stage_index}"

    def trial_dir(self, case_name: str, stage_index: int, trial_index: int) -> Path:
        """Get directory for a specific trial."""
        return self.case_stage_dir(case_name, stage_index) / f"trial_{trial_index}"

    def stage_summary_file(self, stage_index: int) -> Path:
        """Get summary file for a stage."""
        return self.stages_dir / f"stage_{stage_index}_summary.json"

    def create_structure(self) -> None:
        """
        Create the standard directory structure.

        This creates all standard directories with proper permissions.
        Does not fail if directories already exist.
        """
        # Create all standard directories
        dirs_to_create = [
            self.study_root,
            self.summary_dir,
            self.cases_dir,
            self.stages_dir,
            self.telemetry_dir,
            self.reports_dir,
            self.checkpoints_dir,
            self.logs_dir,
        ]

        for directory in dirs_to_create:
            directory.mkdir(parents=True, exist_ok=True)

    def validate_structure(self) -> dict[str, bool]:
        """
        Validate that the directory structure exists and is complete.

        Returns:
            Dictionary mapping directory names to existence status
        """
        return {
            "study_root": self.study_root.exists(),
            "summaries": self.summary_dir.exists(),
            "cases": self.cases_dir.exists(),
            "stages": self.stages_dir.exists(),
            "telemetry": self.telemetry_dir.exists(),
            "reports": self.reports_dir.exists(),
            "checkpoints": self.checkpoints_dir.exists(),
            "logs": self.logs_dir.exists(),
            "readme": self.readme_file.exists(),
        }


def generate_readme_content(study_name: str) -> str:
    """
    Generate README content explaining the directory structure.

    This README helps operators understand where to find key files
    and what each directory contains.

    Args:
        study_name: Name of the Study

    Returns:
        README content as a string
    """
    return f"""Noodle 2 Study Artifacts
=========================

Study Name: {study_name}

This directory contains all artifacts produced by a Noodle 2 Study.
The structure is standardized to make it easy to find results and reports.


Directory Structure
-------------------

summaries/
    High-level Study results and winner selection
    - study_summary.json: Complete Study summary
    - winner_selection.json: Final winner and selection rationale
    - eco_leaderboard.json: ECO effectiveness rankings

cases/
    Per-case trial results organized by case name
    Each case directory contains:
    - stage_0/, stage_1/, ...: Results for each stage
    - trial_0/, trial_1/, ...: Individual trial outputs
    - timing_report.txt: OpenROAD timing analysis
    - congestion_report.json: Routing congestion metrics
    - stdout.log, stderr.log: Tool output
    - artifact_index.json: Catalog of all trial artifacts

stages/
    Per-stage summaries and aggregated metrics
    - stage_0_summary.json: Stage 0 results
    - stage_1_summary.json: Stage 1 results
    - ...

telemetry/
    Structured metrics and telemetry data
    - trial_metrics.json: Per-trial timing and congestion
    - stage_metrics.json: Aggregated stage statistics
    - case_lineage.json: Case derivation DAG

reports/
    Generated analysis reports
    - run_legality_report.txt: Pre-execution safety validation
    - safety_trace.json: Safety evaluation chronology
    - diff_reports/: Case vs baseline comparisons

checkpoints/
    Study state snapshots for resumption
    - checkpoint_stage_0.json
    - checkpoint_stage_1.json
    - ...

logs/
    Controller and orchestration logs
    - controller.log: Main orchestration log
    - ray_executor.log: Ray execution logs
    - error.log: Error and warning messages


Key Files Quick Reference
--------------------------

Looking for...                      Check here:
────────────────────────────────────────────────────────────────
Study results                       summaries/study_summary.json
Best case (winner)                  summaries/winner_selection.json
ECO rankings                        summaries/eco_leaderboard.json
Specific case results               cases/<case_name>/
Stage summary                       stages/stage_<N>_summary.json
Timing metrics                      telemetry/trial_metrics.json
Safety validation                   reports/run_legality_report.txt
Case lineage graph                  telemetry/case_lineage.json
Resume Study                        checkpoints/checkpoint_stage_<N>.json


Navigation Tips
---------------

1. Start with summaries/ for high-level results
2. Drill into cases/ for detailed trial outputs
3. Check reports/ for safety and comparison analysis
4. Review telemetry/ for structured metrics export
5. Use artifact_index.json in each trial directory for file catalog


File Naming Conventions
-----------------------

Cases:   <base>_<stage>_<derived>
         Example: nangate45_0_5 = base nangate45, stage 0, 5th derived case

Stages:  stage_<index>/
         Example: stage_0/ = first stage (STA-only)

Trials:  trial_<index>/
         Example: trial_3/ = fourth trial (0-indexed)


For More Information
--------------------

Noodle 2 Documentation: https://github.com/your-org/noodle2
Feature Specifications: app_spec.txt
Study Configuration: study_config.yaml
"""


def write_readme(layout: ArtifactDirectoryLayout, study_name: str) -> None:
    """
    Write the README file explaining directory structure.

    Args:
        layout: Artifact directory layout
        study_name: Name of the Study
    """
    content = generate_readme_content(study_name)
    layout.readme_file.write_text(content)


def create_study_artifact_structure(study_root: Path, study_name: str) -> ArtifactDirectoryLayout:
    """
    Create a well-organized, self-documenting Study artifact directory.

    This is the primary entry point for setting up Study artifacts.
    It creates the standard structure and generates a README.

    Args:
        study_root: Root directory for Study artifacts
        study_name: Name of the Study

    Returns:
        ArtifactDirectoryLayout for the created structure
    """
    layout = ArtifactDirectoryLayout(study_root=study_root)
    layout.create_structure()
    write_readme(layout, study_name)
    return layout


def get_key_files_summary(layout: ArtifactDirectoryLayout) -> dict[str, Any]:
    """
    Generate a summary of key files and their locations.

    This helps operators quickly locate important files.

    Args:
        layout: Artifact directory layout

    Returns:
        Dictionary mapping file purposes to paths
    """
    return {
        "study_config": str(layout.config_file),
        "study_summary": str(layout.summary_dir / "study_summary.json"),
        "winner_selection": str(layout.summary_dir / "winner_selection.json"),
        "eco_leaderboard": str(layout.summary_dir / "eco_leaderboard.json"),
        "run_legality_report": str(layout.reports_dir / "run_legality_report.txt"),
        "safety_trace": str(layout.reports_dir / "safety_trace.json"),
        "case_lineage": str(layout.telemetry_dir / "case_lineage.json"),
        "trial_metrics": str(layout.telemetry_dir / "trial_metrics.json"),
        "controller_log": str(layout.logs_dir / "controller.log"),
        "readme": str(layout.readme_file),
    }


def is_well_organized(study_root: Path) -> tuple[bool, list[str]]:
    """
    Check if a Study directory follows the standard organization.

    Args:
        study_root: Root directory to check

    Returns:
        Tuple of (is_organized, missing_directories)
    """
    layout = ArtifactDirectoryLayout(study_root=study_root)
    validation = layout.validate_structure()

    missing = [name for name, exists in validation.items() if not exists]
    is_organized = len(missing) == 0

    return is_organized, missing
