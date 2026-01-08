"""Trial ranking and survivor selection for multi-objective optimization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from src.trial_runner.trial import TrialResult


class RankingPolicy(str, Enum):
    """Ranking policy for trial survivor selection."""

    WNS_DELTA = "wns_delta"  # Rank by timing improvement
    CONGESTION_DELTA = "congestion_delta"  # Rank by congestion reduction
    MULTI_OBJECTIVE = "multi_objective"  # Combine timing and congestion


@dataclass
class RankingWeights:
    """Weights for multi-objective ranking."""

    timing_weight: float = 0.6  # Weight for timing improvement (0.0 to 1.0)
    congestion_weight: float = 0.4  # Weight for congestion reduction (0.0 to 1.0)

    def __post_init__(self) -> None:
        """Validate weights."""
        if not (0.0 <= self.timing_weight <= 1.0):
            raise ValueError("timing_weight must be between 0.0 and 1.0")
        if not (0.0 <= self.congestion_weight <= 1.0):
            raise ValueError("congestion_weight must be between 0.0 and 1.0")
        total = self.timing_weight + self.congestion_weight
        if not (0.99 <= total <= 1.01):  # Allow small floating point error
            raise ValueError(
                f"timing_weight + congestion_weight must equal 1.0, got {total}"
            )


def rank_by_wns_delta(
    trial_results: list[TrialResult],
    baseline_wns_ps: int,
    survivor_count: int,
) -> list[str]:
    """
    Rank trials by WNS improvement (delta from baseline).

    Trials with better (higher/less negative) WNS are ranked first.

    Args:
        trial_results: All trial results from stage
        baseline_wns_ps: Baseline WNS in picoseconds (from base case)
        survivor_count: Number of survivors to select

    Returns:
        List of case IDs for survivors, ordered by WNS improvement
    """
    # Filter successful trials with timing metrics
    successful_trials = [
        t
        for t in trial_results
        if t.success and t.artifacts.metrics_json and t.artifacts.metrics_json.exists()
    ]

    if not successful_trials:
        return []

    # Compute WNS delta for each trial
    trials_with_delta = []
    for trial in successful_trials:
        # Load metrics from trial
        with open(trial.artifacts.metrics_json) as f:
            metrics = json.load(f)

        wns_ps = metrics.get("timing", {}).get("wns_ps")
        if wns_ps is None:
            continue

        # Delta is improvement: current WNS - baseline WNS
        # Higher delta = better (e.g., -500 - (-1000) = +500 improvement)
        delta = wns_ps - baseline_wns_ps
        trials_with_delta.append((trial, delta))

    if not trials_with_delta:
        return []

    # Sort by delta descending (best improvement first)
    sorted_trials = sorted(trials_with_delta, key=lambda x: x[1], reverse=True)

    # Select top N survivors
    survivors = sorted_trials[:survivor_count]

    return [trial.config.case_name for trial, _ in survivors]


def rank_by_congestion_delta(
    trial_results: list[TrialResult],
    baseline_hot_ratio: float,
    survivor_count: int,
) -> list[str]:
    """
    Rank trials by congestion reduction (delta from baseline).

    Trials with lower hot_ratio (less congestion) are ranked first.

    Args:
        trial_results: All trial results from stage
        baseline_hot_ratio: Baseline hot_ratio (from base case)
        survivor_count: Number of survivors to select

    Returns:
        List of case IDs for survivors, ordered by congestion reduction
    """
    # Filter successful trials with congestion metrics
    successful_trials = [
        t
        for t in trial_results
        if t.success and t.artifacts.metrics_json and t.artifacts.metrics_json.exists()
    ]

    if not successful_trials:
        return []

    # Compute hot_ratio delta for each trial
    trials_with_delta = []
    for trial in successful_trials:
        # Load metrics from trial
        with open(trial.artifacts.metrics_json) as f:
            metrics = json.load(f)

        congestion = metrics.get("congestion")
        if not congestion:
            continue

        hot_ratio = congestion.get("hot_ratio")
        if hot_ratio is None:
            continue

        # Delta is reduction: baseline - current hot_ratio
        # Higher delta = better (e.g., 0.8 - 0.5 = +0.3 reduction)
        delta = baseline_hot_ratio - hot_ratio
        trials_with_delta.append((trial, delta))

    if not trials_with_delta:
        return []

    # Sort by delta descending (best reduction first)
    sorted_trials = sorted(trials_with_delta, key=lambda x: x[1], reverse=True)

    # Select top N survivors
    survivors = sorted_trials[:survivor_count]

    return [trial.config.case_name for trial, _ in survivors]


def rank_multi_objective(
    trial_results: list[TrialResult],
    baseline_wns_ps: int,
    baseline_hot_ratio: float,
    survivor_count: int,
    weights: RankingWeights | None = None,
) -> list[str]:
    """
    Rank trials using multi-objective scoring (timing + congestion).

    Combines WNS improvement and congestion reduction into a weighted score.

    Args:
        trial_results: All trial results from stage
        baseline_wns_ps: Baseline WNS in picoseconds
        baseline_hot_ratio: Baseline hot_ratio
        survivor_count: Number of survivors to select
        weights: Ranking weights (default: 60% timing, 40% congestion)

    Returns:
        List of case IDs for survivors, ordered by combined score
    """
    if weights is None:
        weights = RankingWeights()

    # Filter successful trials with both timing and congestion metrics
    successful_trials = [
        t
        for t in trial_results
        if t.success and t.artifacts.metrics_json and t.artifacts.metrics_json.exists()
    ]

    if not successful_trials:
        return []

    # Compute normalized scores for each trial
    trials_with_score = []
    wns_deltas = []
    congestion_deltas = []

    # First pass: collect all deltas for normalization
    for trial in successful_trials:
        with open(trial.artifacts.metrics_json) as f:
            metrics = json.load(f)

        wns_ps = metrics.get("timing", {}).get("wns_ps")
        congestion = metrics.get("congestion")
        hot_ratio = congestion.get("hot_ratio") if congestion else None

        if wns_ps is None:
            continue

        # Calculate deltas
        wns_delta = wns_ps - baseline_wns_ps
        wns_deltas.append(wns_delta)

        if hot_ratio is not None:
            congestion_delta = baseline_hot_ratio - hot_ratio
            congestion_deltas.append(congestion_delta)
        else:
            congestion_deltas.append(0.0)

    if not wns_deltas:
        return []

    # Normalize deltas to [0, 1] range
    # For WNS: higher delta = better
    wns_min = min(wns_deltas)
    wns_max = max(wns_deltas)
    wns_range = wns_max - wns_min if wns_max != wns_min else 1.0

    # For congestion: higher delta = better (more reduction)
    congestion_min = min(congestion_deltas)
    congestion_max = max(congestion_deltas)
    congestion_range = (
        congestion_max - congestion_min if congestion_max != congestion_min else 1.0
    )

    # Second pass: compute weighted scores
    for idx, trial in enumerate(successful_trials):
        with open(trial.artifacts.metrics_json) as f:
            metrics = json.load(f)

        wns_ps = metrics.get("timing", {}).get("wns_ps")
        if wns_ps is None:
            continue

        # Normalize WNS delta to [0, 1]
        wns_delta = wns_ps - baseline_wns_ps
        wns_score = (wns_delta - wns_min) / wns_range

        # Normalize congestion delta to [0, 1]
        congestion_delta = congestion_deltas[idx]
        congestion_score = (congestion_delta - congestion_min) / congestion_range

        # Compute weighted combined score
        combined_score = (
            weights.timing_weight * wns_score
            + weights.congestion_weight * congestion_score
        )

        trials_with_score.append((trial, combined_score))

    if not trials_with_score:
        return []

    # Sort by combined score descending (best score first)
    sorted_trials = sorted(trials_with_score, key=lambda x: x[1], reverse=True)

    # Select top N survivors
    survivors = sorted_trials[:survivor_count]

    return [trial.config.case_name for trial, _ in survivors]


def create_survivor_selector(
    policy: RankingPolicy,
    baseline_wns_ps: int,
    baseline_hot_ratio: float | None = None,
    weights: RankingWeights | None = None,
) -> Callable[[list[TrialResult], int], list[str]]:
    """
    Create a survivor selector function for a given ranking policy.

    Args:
        policy: Ranking policy to use
        baseline_wns_ps: Baseline WNS in picoseconds
        baseline_hot_ratio: Baseline hot_ratio (required for congestion/multi-objective)
        weights: Ranking weights (for multi-objective only)

    Returns:
        Survivor selector function compatible with StudyExecutor

    Raises:
        ValueError: If baseline_hot_ratio is required but not provided
    """
    if policy == RankingPolicy.WNS_DELTA:

        def selector(trial_results: list[TrialResult], survivor_count: int) -> list[str]:
            return rank_by_wns_delta(trial_results, baseline_wns_ps, survivor_count)

        return selector

    elif policy == RankingPolicy.CONGESTION_DELTA:
        if baseline_hot_ratio is None:
            raise ValueError(
                "baseline_hot_ratio is required for congestion-based ranking"
            )

        def selector(trial_results: list[TrialResult], survivor_count: int) -> list[str]:
            return rank_by_congestion_delta(
                trial_results, baseline_hot_ratio, survivor_count
            )

        return selector

    elif policy == RankingPolicy.MULTI_OBJECTIVE:
        if baseline_hot_ratio is None:
            raise ValueError(
                "baseline_hot_ratio is required for multi-objective ranking"
            )

        def selector(trial_results: list[TrialResult], survivor_count: int) -> list[str]:
            return rank_multi_objective(
                trial_results,
                baseline_wns_ps,
                baseline_hot_ratio,
                survivor_count,
                weights,
            )

        return selector

    else:
        raise ValueError(f"Unknown ranking policy: {policy}")
