"""Pareto frontier computation for multi-objective optimization.

This module provides functions to compute Pareto-optimal trials when
balancing multiple objectives (e.g., timing, congestion, area, power).

A trial is Pareto-optimal (non-dominated) if no other trial is strictly
better in all objectives simultaneously.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.trial_runner.trial import TrialResult


@dataclass
class ObjectiveSpec:
    """Specification for a single optimization objective."""

    name: str  # Objective name (e.g., "wns_ps", "hot_ratio", "area")
    metric_path: list[str]  # Path to metric in trial JSON (e.g., ["timing", "wns_ps"])
    minimize: bool  # True to minimize, False to maximize
    weight: float = 1.0  # Weight for weighted scoring (not used in Pareto computation)

    def __post_init__(self) -> None:
        """Validate objective specification."""
        if not self.name:
            raise ValueError("Objective name cannot be empty")
        if not self.metric_path:
            raise ValueError("Metric path cannot be empty")
        if self.weight <= 0:
            raise ValueError(f"Weight must be positive, got {self.weight}")


@dataclass
class ParetoTrial:
    """Trial data for Pareto analysis."""

    case_name: str
    trial_result: TrialResult
    objective_values: dict[str, float]  # Objective name -> value
    is_pareto_optimal: bool = False
    dominated_by: list[str] = field(default_factory=list)  # Case names that dominate this trial

    def dominates(self, other: ParetoTrial, objectives: list[ObjectiveSpec]) -> bool:
        """
        Check if this trial dominates another trial.

        Trial A dominates trial B if:
        - A is at least as good as B in all objectives
        - A is strictly better than B in at least one objective

        Args:
            other: Trial to compare against
            objectives: List of objective specifications

        Returns:
            True if this trial dominates the other trial
        """
        at_least_as_good = True
        strictly_better_in_one = False

        for obj in objectives:
            self_value = self.objective_values.get(obj.name)
            other_value = other.objective_values.get(obj.name)

            # If either value is missing, cannot establish dominance
            if self_value is None or other_value is None:
                return False

            if obj.minimize:
                # For minimization: lower is better
                if self_value > other_value:
                    at_least_as_good = False
                    break
                if self_value < other_value:
                    strictly_better_in_one = True
            else:
                # For maximization: higher is better
                if self_value < other_value:
                    at_least_as_good = False
                    break
                if self_value > other_value:
                    strictly_better_in_one = True

        return at_least_as_good and strictly_better_in_one


@dataclass
class ParetoFrontier:
    """Pareto frontier analysis result."""

    objectives: list[ObjectiveSpec]
    all_trials: list[ParetoTrial]
    pareto_optimal_trials: list[ParetoTrial]
    dominated_trials: list[ParetoTrial]

    def get_pareto_case_names(self) -> list[str]:
        """Get list of case names for Pareto-optimal trials."""
        return [t.case_name for t in self.pareto_optimal_trials]

    def to_dict(self) -> dict[str, Any]:
        """
        Serialize Pareto frontier to dictionary.

        Returns:
            Dictionary representation suitable for JSON export
        """
        return {
            "objectives": [
                {
                    "name": obj.name,
                    "metric_path": obj.metric_path,
                    "minimize": obj.minimize,
                    "weight": obj.weight,
                }
                for obj in self.objectives
            ],
            "pareto_optimal_trials": [
                {
                    "case_name": t.case_name,
                    "objective_values": t.objective_values,
                }
                for t in self.pareto_optimal_trials
            ],
            "dominated_trials": [
                {
                    "case_name": t.case_name,
                    "objective_values": t.objective_values,
                    "dominated_by": t.dominated_by,
                }
                for t in self.dominated_trials
            ],
            "summary": {
                "total_trials": len(self.all_trials),
                "pareto_optimal_count": len(self.pareto_optimal_trials),
                "dominated_count": len(self.dominated_trials),
            },
        }


def extract_objective_value(
    metrics: dict[str, Any], metric_path: list[str]
) -> float | None:
    """
    Extract objective value from nested metrics dictionary.

    Args:
        metrics: Trial metrics dictionary
        metric_path: Path to metric (e.g., ["timing", "wns_ps"])

    Returns:
        Metric value or None if not found
    """
    current = metrics
    for key in metric_path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None

    # Handle both numeric values and dictionaries
    if isinstance(current, (int, float)):
        return float(current)
    return None


def compute_pareto_frontier(
    trial_results: list[TrialResult], objectives: list[ObjectiveSpec]
) -> ParetoFrontier:
    """
    Compute Pareto frontier from trial results.

    Args:
        trial_results: All trial results from stage
        objectives: List of optimization objectives

    Returns:
        ParetoFrontier containing Pareto-optimal and dominated trials

    Raises:
        ValueError: If objectives list is empty
    """
    if not objectives:
        raise ValueError("At least one objective must be specified")

    # Filter successful trials with metrics
    successful_trials = [
        t
        for t in trial_results
        if t.success and t.artifacts.metrics_json and t.artifacts.metrics_json.exists()
    ]

    if not successful_trials:
        return ParetoFrontier(
            objectives=objectives,
            all_trials=[],
            pareto_optimal_trials=[],
            dominated_trials=[],
        )

    # Load metrics and create ParetoTrial objects
    pareto_trials: list[ParetoTrial] = []
    for trial in successful_trials:
        with open(trial.artifacts.metrics_json) as f:
            metrics = json.load(f)

        # Extract objective values
        objective_values = {}
        skip_trial = False
        for obj in objectives:
            value = extract_objective_value(metrics, obj.metric_path)
            if value is None:
                skip_trial = True
                break
            objective_values[obj.name] = value

        if skip_trial:
            continue

        pareto_trials.append(
            ParetoTrial(
                case_name=trial.config.case_name,
                trial_result=trial,
                objective_values=objective_values,
            )
        )

    if not pareto_trials:
        return ParetoFrontier(
            objectives=objectives,
            all_trials=[],
            pareto_optimal_trials=[],
            dominated_trials=[],
        )

    # Compute dominance relationships
    for i, trial_a in enumerate(pareto_trials):
        for j, trial_b in enumerate(pareto_trials):
            if i == j:
                continue

            if trial_b.dominates(trial_a, objectives):
                trial_a.dominated_by.append(trial_b.case_name)

    # Identify Pareto-optimal trials (those that are not dominated by any other trial)
    pareto_optimal = []
    dominated = []
    for trial in pareto_trials:
        if not trial.dominated_by:
            trial.is_pareto_optimal = True
            pareto_optimal.append(trial)
        else:
            dominated.append(trial)

    return ParetoFrontier(
        objectives=objectives,
        all_trials=pareto_trials,
        pareto_optimal_trials=pareto_optimal,
        dominated_trials=dominated,
    )


def write_pareto_analysis(
    pareto_frontier: ParetoFrontier, output_path: Path
) -> None:
    """
    Write Pareto frontier analysis to JSON file.

    Args:
        pareto_frontier: Pareto frontier to export
        output_path: Path to output JSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(pareto_frontier.to_dict(), f, indent=2)


# Common objective specifications for typical studies
TIMING_OBJECTIVE = ObjectiveSpec(
    name="wns_ps",
    metric_path=["timing", "wns_ps"],
    minimize=False,  # Maximize WNS (less negative = better)
)

CONGESTION_OBJECTIVE = ObjectiveSpec(
    name="hot_ratio",
    metric_path=["congestion", "hot_ratio"],
    minimize=True,  # Minimize congestion
)

AREA_OBJECTIVE = ObjectiveSpec(
    name="area_um2",
    metric_path=["area", "total_area_um2"],
    minimize=True,  # Minimize area
)

POWER_OBJECTIVE = ObjectiveSpec(
    name="total_power_mw",
    metric_path=["power", "total_power_mw"],
    minimize=True,  # Minimize power
)

DRV_OBJECTIVE = ObjectiveSpec(
    name="total_violations",
    metric_path=["drv", "total_violations"],
    minimize=True,  # Minimize DRC violations
)
