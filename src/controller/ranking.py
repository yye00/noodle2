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
    DIVERSE_TOP_N = "diverse_top_n"  # Select top N while maintaining diversity


class DiversityMetric(str, Enum):
    """Diversity metric for survivor selection."""

    ECO_PATH_DISTANCE = "eco_path_distance"  # Distance based on ECO application sequence


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


@dataclass
class DiversityConfig:
    """Configuration for diversity-aware survivor selection."""

    enabled: bool = False
    metric: DiversityMetric = DiversityMetric.ECO_PATH_DISTANCE
    min_diversity: float = 0.3  # Minimum pairwise distance between survivors
    always_keep_best: bool = True  # Always include the best-scoring trial
    random_survivors: int = 0  # Number of random survivors for exploration

    def __post_init__(self) -> None:
        """Validate diversity configuration."""
        if not (0.0 <= self.min_diversity <= 1.0):
            raise ValueError("min_diversity must be between 0.0 and 1.0")
        if self.random_survivors < 0:
            raise ValueError("random_survivors must be non-negative")


def compute_eco_path_distance(eco_sequence_1: list[str], eco_sequence_2: list[str]) -> float:
    """
    Compute normalized edit distance between two ECO sequences.

    Uses Levenshtein distance (edit distance) normalized by the length of the longer sequence.
    Distance ranges from 0.0 (identical) to 1.0 (completely different).

    Args:
        eco_sequence_1: First ECO sequence (list of ECO names)
        eco_sequence_2: Second ECO sequence (list of ECO names)

    Returns:
        Normalized distance in [0.0, 1.0]
    """
    # Handle empty sequences
    if not eco_sequence_1 and not eco_sequence_2:
        return 0.0
    if not eco_sequence_1 or not eco_sequence_2:
        return 1.0

    # Compute Levenshtein distance using dynamic programming
    m, n = len(eco_sequence_1), len(eco_sequence_2)

    # Create DP table
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Initialize first row and column
    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    # Fill DP table
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if eco_sequence_1[i - 1] == eco_sequence_2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]  # No operation needed
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],      # Deletion
                    dp[i][j - 1],      # Insertion
                    dp[i - 1][j - 1]   # Substitution
                )

    # Normalize by length of longer sequence
    edit_distance = dp[m][n]
    max_length = max(m, n)
    normalized_distance = edit_distance / max_length

    return normalized_distance


def get_eco_sequence_from_trial(trial: TrialResult) -> list[str]:
    """
    Extract ECO sequence from trial result.

    Attempts to extract ECO sequence from trial metadata or case name.

    Args:
        trial: Trial result to extract ECO sequence from

    Returns:
        List of ECO names applied to reach this trial
    """
    # Try to get from metadata first (most accurate)
    if "eco_sequence" in trial.config.metadata:
        return trial.config.metadata["eco_sequence"]

    # Try to get single ECO from metadata
    if "eco_name" in trial.config.metadata:
        eco_name = trial.config.metadata["eco_name"]
        # If there's a parent sequence, append to it
        if "parent_eco_sequence" in trial.config.metadata:
            parent_seq = trial.config.metadata["parent_eco_sequence"]
            return parent_seq + [eco_name]
        return [eco_name]

    # Fallback: return empty sequence (base case)
    return []


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


def rank_diverse_top_n(
    trial_results: list[TrialResult],
    baseline_wns_ps: int,
    baseline_hot_ratio: float,
    survivor_count: int,
    diversity_config: DiversityConfig,
    weights: RankingWeights | None = None,
) -> list[str]:
    """
    Select diverse survivors using diversity-aware selection.

    Greedily selects survivors that maintain minimum diversity while preferring
    better-performing trials. Uses multi-objective scoring for quality and
    ECO path distance for diversity.

    Args:
        trial_results: All trial results from stage
        baseline_wns_ps: Baseline WNS in picoseconds
        baseline_hot_ratio: Baseline hot_ratio
        survivor_count: Number of survivors to select
        diversity_config: Diversity configuration
        weights: Ranking weights for quality scoring

    Returns:
        List of case IDs for survivors, ordered by selection
    """
    if weights is None:
        weights = RankingWeights()

    # First, score all trials using multi-objective ranking
    successful_trials = [
        t
        for t in trial_results
        if t.success and t.artifacts.metrics_json and t.artifacts.metrics_json.exists()
    ]

    if not successful_trials:
        return []

    # Compute quality scores for all trials (reuse multi-objective logic)
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
    wns_min = min(wns_deltas)
    wns_max = max(wns_deltas)
    wns_range = wns_max - wns_min if wns_max != wns_min else 1.0

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

    # Extract ECO sequences for all trials
    trial_eco_sequences = {}
    for trial, _ in sorted_trials:
        trial_eco_sequences[trial.config.case_name] = get_eco_sequence_from_trial(trial)

    # Greedy diversity-aware selection
    survivors: list[str] = []

    # Step 1: Always keep the best trial if configured
    if diversity_config.always_keep_best and sorted_trials:
        best_trial = sorted_trials[0][0]
        survivors.append(best_trial.config.case_name)

    # Step 2: Greedily select remaining survivors with diversity constraint
    for trial, score in sorted_trials:
        case_name = trial.config.case_name

        # Skip if already selected
        if case_name in survivors:
            continue

        # Check diversity constraint with all existing survivors
        is_diverse = True
        if diversity_config.enabled and diversity_config.metric == DiversityMetric.ECO_PATH_DISTANCE:
            for survivor_name in survivors:
                distance = compute_eco_path_distance(
                    trial_eco_sequences[case_name],
                    trial_eco_sequences[survivor_name]
                )
                if distance < diversity_config.min_diversity:
                    is_diverse = False
                    break

        # Add if diverse enough (or diversity not enabled)
        if is_diverse or not diversity_config.enabled:
            survivors.append(case_name)

        # Stop when we have enough survivors
        if len(survivors) >= survivor_count:
            break

    # If we don't have enough survivors due to diversity constraint,
    # relax the constraint and add next best trials
    if len(survivors) < survivor_count:
        for trial, _ in sorted_trials:
            case_name = trial.config.case_name
            if case_name not in survivors:
                survivors.append(case_name)
                if len(survivors) >= survivor_count:
                    break

    # Step 3: Add random survivors for exploration (F248)
    if diversity_config.random_survivors > 0:
        # Determine how many random survivors to add
        max_random = min(diversity_config.random_survivors, survivor_count)

        # Reserve slots for random survivors
        # If we have more survivors than needed, replace some with random ones
        if len(survivors) >= survivor_count:
            # Keep best + diversity-selected, but replace last ones with random
            num_to_replace = min(max_random, len(survivors) - 1)  # Always keep at least the best
            if num_to_replace > 0:
                survivors = survivors[:-num_to_replace]  # Remove last N survivors

        # Get candidate pool (trials not yet selected)
        candidate_pool = [
            trial for trial, _ in sorted_trials
            if trial.config.case_name not in survivors
        ]

        if candidate_pool:
            # Use deterministic random selection with seed for reproducibility
            # Seed based on number of survivors to ensure consistent results
            import random
            rng = random.Random(len(survivors))

            # Randomly sample from candidate pool
            num_random_to_add = min(max_random, len(candidate_pool), survivor_count - len(survivors))
            random_selections = rng.sample(candidate_pool, num_random_to_add)

            for trial in random_selections:
                survivors.append(trial.config.case_name)
                if len(survivors) >= survivor_count:
                    break

    return survivors[:survivor_count]


def create_survivor_selector(
    policy: RankingPolicy,
    baseline_wns_ps: int,
    baseline_hot_ratio: float | None = None,
    weights: RankingWeights | None = None,
    diversity_config: DiversityConfig | None = None,
) -> Callable[[list[TrialResult], int], list[str]]:
    """
    Create a survivor selector function for a given ranking policy.

    Args:
        policy: Ranking policy to use
        baseline_wns_ps: Baseline WNS in picoseconds
        baseline_hot_ratio: Baseline hot_ratio (required for congestion/multi-objective/diverse)
        weights: Ranking weights (for multi-objective and diverse_top_n)
        diversity_config: Diversity configuration (for diverse_top_n only)

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

    elif policy == RankingPolicy.DIVERSE_TOP_N:
        if baseline_hot_ratio is None:
            raise ValueError(
                "baseline_hot_ratio is required for diverse_top_n ranking"
            )
        if diversity_config is None:
            diversity_config = DiversityConfig(enabled=True)

        def selector(trial_results: list[TrialResult], survivor_count: int) -> list[str]:
            return rank_diverse_top_n(
                trial_results,
                baseline_wns_ps,
                baseline_hot_ratio,
                survivor_count,
                diversity_config,
                weights,
            )

        return selector

    else:
        raise ValueError(f"Unknown ranking policy: {policy}")
