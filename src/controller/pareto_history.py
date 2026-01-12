"""Pareto frontier history tracking for multi-stage studies.

This module tracks the evolution of Pareto frontiers across multiple stages,
enabling visualization of how the optimization progresses through the workflow.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.controller.pareto import ParetoFrontier


@dataclass
class ParetoStageSnapshot:
    """Snapshot of Pareto frontier at a specific stage."""

    stage_name: str
    stage_index: int
    pareto_optimal_count: int
    dominated_count: int
    total_trials: int
    pareto_optimal_cases: list[str]
    objectives: list[dict[str, Any]]
    frontier_data: dict[str, Any]  # Full ParetoFrontier.to_dict() output

    def to_dict(self) -> dict[str, Any]:
        """Serialize snapshot to dictionary."""
        return {
            "stage_name": self.stage_name,
            "stage_index": self.stage_index,
            "pareto_optimal_count": self.pareto_optimal_count,
            "dominated_count": self.dominated_count,
            "total_trials": self.total_trials,
            "pareto_optimal_cases": self.pareto_optimal_cases,
            "objectives": self.objectives,
            "frontier_data": self.frontier_data,
        }


@dataclass
class ParetoHistory:
    """Complete history of Pareto frontiers across all stages."""

    study_name: str
    stages: list[ParetoStageSnapshot] = field(default_factory=list)

    def add_stage_snapshot(
        self,
        stage_name: str,
        stage_index: int,
        pareto_frontier: ParetoFrontier,
    ) -> None:
        """
        Add a Pareto frontier snapshot for a specific stage.

        Args:
            stage_name: Name of the stage (e.g., "floorplan", "place")
            stage_index: Index of the stage in workflow
            pareto_frontier: Computed Pareto frontier for this stage
        """
        frontier_dict = pareto_frontier.to_dict()

        snapshot = ParetoStageSnapshot(
            stage_name=stage_name,
            stage_index=stage_index,
            pareto_optimal_count=len(pareto_frontier.pareto_optimal_trials),
            dominated_count=len(pareto_frontier.dominated_trials),
            total_trials=len(pareto_frontier.all_trials),
            pareto_optimal_cases=pareto_frontier.get_pareto_case_names(),
            objectives=frontier_dict["objectives"],
            frontier_data=frontier_dict,
        )

        self.stages.append(snapshot)

    def get_stage_snapshot(self, stage_index: int) -> ParetoStageSnapshot | None:
        """
        Get snapshot for a specific stage.

        Args:
            stage_index: Index of the stage

        Returns:
            Stage snapshot or None if not found
        """
        for snapshot in self.stages:
            if snapshot.stage_index == stage_index:
                return snapshot
        return None

    def get_pareto_evolution(self) -> list[list[str]]:
        """
        Get evolution of Pareto-optimal cases across stages.

        Returns:
            List of Pareto-optimal case lists, one per stage (in order)
        """
        return [snapshot.pareto_optimal_cases for snapshot in self.stages]

    def get_stage_count(self) -> int:
        """Get number of stages tracked."""
        return len(self.stages)

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize history to dictionary.

        Returns:
            Dictionary representation suitable for JSON export
        """
        return {
            "study_name": self.study_name,
            "total_stages": len(self.stages),
            "stages": [snapshot.to_dict() for snapshot in self.stages],
            "evolution_summary": {
                "pareto_counts_per_stage": [
                    snapshot.pareto_optimal_count for snapshot in self.stages
                ],
                "total_trials_per_stage": [
                    snapshot.total_trials for snapshot in self.stages
                ],
            },
        }


def write_pareto_history(history: ParetoHistory, output_path: Path) -> None:
    """
    Write Pareto history to JSON file.

    Args:
        history: Pareto history to export
        output_path: Path to output JSON file (typically pareto_history.json)
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(history.to_dict(), f, indent=2)


def load_pareto_history(input_path: Path) -> ParetoHistory:
    """
    Load Pareto history from JSON file.

    Args:
        input_path: Path to pareto_history.json file

    Returns:
        Loaded ParetoHistory object

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If JSON format is invalid
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Pareto history file not found: {input_path}")

    with open(input_path) as f:
        data = json.load(f)

    if "study_name" not in data or "stages" not in data:
        raise ValueError("Invalid pareto_history.json format: missing required fields")

    history = ParetoHistory(study_name=data["study_name"])

    for stage_data in data["stages"]:
        snapshot = ParetoStageSnapshot(
            stage_name=stage_data["stage_name"],
            stage_index=stage_data["stage_index"],
            pareto_optimal_count=stage_data["pareto_optimal_count"],
            dominated_count=stage_data["dominated_count"],
            total_trials=stage_data["total_trials"],
            pareto_optimal_cases=stage_data["pareto_optimal_cases"],
            objectives=stage_data["objectives"],
            frontier_data=stage_data["frontier_data"],
        )
        history.stages.append(snapshot)

    return history


def create_pareto_history_from_stage_frontiers(
    study_name: str,
    stage_names: list[str],
    stage_frontiers: list[ParetoFrontier],
) -> ParetoHistory:
    """
    Create Pareto history from a list of stage frontiers.

    Args:
        study_name: Name of the study
        stage_names: List of stage names (e.g., ["synth", "floorplan", "place"])
        stage_frontiers: List of ParetoFrontier objects, one per stage

    Returns:
        ParetoHistory object

    Raises:
        ValueError: If stage_names and stage_frontiers lengths don't match
    """
    if len(stage_names) != len(stage_frontiers):
        raise ValueError(
            f"Mismatched lengths: {len(stage_names)} stage names vs "
            f"{len(stage_frontiers)} frontiers"
        )

    history = ParetoHistory(study_name=study_name)

    for idx, (stage_name, frontier) in enumerate(zip(stage_names, stage_frontiers, strict=False)):
        history.add_stage_snapshot(
            stage_name=stage_name,
            stage_index=idx,
            pareto_frontier=frontier,
        )

    return history
