"""Early stopping logic for trial cancellation when survivors are determined."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.trial_runner.trial import TrialResult


class EarlyStoppingPolicy(str, Enum):
    """Policy for early stopping when survivors can be determined."""

    DISABLED = "disabled"  # No early stopping, execute all trials
    CONSERVATIVE = "conservative"  # Stop when top N are clearly ahead
    AGGRESSIVE = "aggressive"  # Stop as soon as N viable candidates exist
    ADAPTIVE = "adaptive"  # Adjust based on metric variance


@dataclass
class EarlyStoppingConfig:
    """Configuration for early stopping behavior."""

    policy: EarlyStoppingPolicy = EarlyStoppingPolicy.DISABLED
    min_trials_before_stopping: int = 5  # Minimum trials before considering early stop
    confidence_threshold: float = 0.95  # Confidence level for survivor determination
    metric_key: str = "wns_ps"  # Metric to use for survivor ranking
    margin_percent: float = 10.0  # Required margin between survivors and non-survivors

    def validate(self) -> None:
        """Validate early stopping configuration."""
        if self.min_trials_before_stopping < 1:
            raise ValueError("min_trials_before_stopping must be >= 1")
        if not (0.0 < self.confidence_threshold <= 1.0):
            raise ValueError("confidence_threshold must be in (0, 1]")
        if self.margin_percent < 0:
            raise ValueError("margin_percent must be non-negative")


@dataclass
class SurvivorDeterminationResult:
    """Result of checking if survivors can be determined early."""

    can_determine: bool
    survivors: list[str]  # Case IDs of determined survivors
    remaining_trials: list[Any]  # Trial refs that can be cancelled
    reason: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "can_determine": self.can_determine,
            "survivors": self.survivors,
            "remaining_trial_count": len(self.remaining_trials),
            "reason": self.reason,
            "metadata": self.metadata,
        }


def can_determine_survivors_early(
    config: EarlyStoppingConfig,
    completed_results: list[Any],  # list[TrialResult] but avoiding circular import
    required_survivor_count: int,
    total_trial_budget: int,
) -> SurvivorDeterminationResult:
    """
    Determine if survivors can be selected before all trials complete.

    This function analyzes completed trial results to decide if we have
    enough information to confidently select survivors without running
    remaining trials.

    Args:
        config: Early stopping configuration
        completed_results: Trial results completed so far
        required_survivor_count: Number of survivors needed
        total_trial_budget: Total trials planned for this stage

    Returns:
        SurvivorDeterminationResult with determination and reasoning

    Notes:
        - Only successful trials are considered for survivor selection
        - Different policies use different criteria:
          - CONSERVATIVE: Requires clear gap between survivors and rest
          - AGGRESSIVE: Stops as soon as we have N viable candidates
          - ADAPTIVE: Adjusts based on metric variance
    """
    # If early stopping is disabled, never determine early
    if config.policy == EarlyStoppingPolicy.DISABLED:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason="Early stopping is disabled",
        )

    # Must have completed minimum trials before considering early stop
    if len(completed_results) < config.min_trials_before_stopping:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason=f"Only {len(completed_results)} trials completed, need {config.min_trials_before_stopping} minimum",
        )

    # Must have completed at least the required survivor count
    successful_trials = [r for r in completed_results if r.success]
    if len(successful_trials) < required_survivor_count:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason=f"Only {len(successful_trials)} successful trials, need {required_survivor_count} survivors",
        )

    # Extract metrics and rank trials
    trials_with_metrics = []
    for result in successful_trials:
        if result.metrics and config.metric_key in result.metrics:
            metric_value = result.metrics[config.metric_key]
            trials_with_metrics.append((result.config.case_name, metric_value))

    if len(trials_with_metrics) < required_survivor_count:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason=f"Only {len(trials_with_metrics)} trials have metric '{config.metric_key}'",
        )

    # Sort by metric (higher is better for WNS)
    trials_with_metrics.sort(key=lambda x: x[1], reverse=True)

    # Apply policy-specific logic
    if config.policy == EarlyStoppingPolicy.CONSERVATIVE:
        return _check_conservative_early_stop(
            config, trials_with_metrics, required_survivor_count,
            len(completed_results), total_trial_budget
        )
    elif config.policy == EarlyStoppingPolicy.AGGRESSIVE:
        return _check_aggressive_early_stop(
            config, trials_with_metrics, required_survivor_count,
            len(completed_results), total_trial_budget
        )
    elif config.policy == EarlyStoppingPolicy.ADAPTIVE:
        return _check_adaptive_early_stop(
            config, trials_with_metrics, required_survivor_count,
            len(completed_results), total_trial_budget
        )

    # Unknown policy
    return SurvivorDeterminationResult(
        can_determine=False,
        survivors=[],
        remaining_trials=[],
        reason=f"Unknown early stopping policy: {config.policy}",
    )


def _check_conservative_early_stop(
    config: EarlyStoppingConfig,
    ranked_trials: list[tuple[str, float]],
    required_survivor_count: int,
    completed_count: int,
    total_budget: int,
) -> SurvivorDeterminationResult:
    """
    Conservative early stopping: requires clear gap between survivors and rest.

    Only stops if:
    1. We have at least 50% of trials completed
    2. Top N trials have a significant margin over the (N+1)th trial
    """
    # Require at least half the trials to be completed
    if completed_count < total_budget / 2:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason=f"Conservative policy requires 50% completion ({completed_count}/{total_budget})",
        )

    # Check if there's a significant gap after the Nth trial
    if len(ranked_trials) <= required_survivor_count:
        # All completed trials would be survivors, need more data
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason="Not enough trials to establish gap beyond survivors",
        )

    nth_value = ranked_trials[required_survivor_count - 1][1]
    next_value = ranked_trials[required_survivor_count][1]

    # Calculate margin (handle negative values for WNS)
    if nth_value >= 0:
        # Positive or zero values
        margin = (nth_value - next_value) / max(abs(nth_value), 1) * 100
    else:
        # Both negative (typical for WNS): less negative is better
        margin = (nth_value - next_value) / abs(nth_value) * 100

    if margin < config.margin_percent:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason=f"Gap between survivors and rest is only {margin:.1f}%, need {config.margin_percent}%",
            metadata={"margin_percent": margin, "nth_value": nth_value, "next_value": next_value},
        )

    # Gap is sufficient, can determine survivors
    survivors = [case_name for case_name, _ in ranked_trials[:required_survivor_count]]
    return SurvivorDeterminationResult(
        can_determine=True,
        survivors=survivors,
        remaining_trials=[],
        reason=f"Top {required_survivor_count} have {margin:.1f}% margin over rest",
        metadata={"margin_percent": margin, "nth_value": nth_value, "next_value": next_value},
    )


def _check_aggressive_early_stop(
    config: EarlyStoppingConfig,
    ranked_trials: list[tuple[str, float]],
    required_survivor_count: int,
    completed_count: int,
    total_budget: int,
) -> SurvivorDeterminationResult:
    """
    Aggressive early stopping: stops as soon as we have N viable candidates.

    Only requires:
    1. Minimum trials completed
    2. At least N successful trials with metrics
    """
    # Already validated in parent function that we have enough successful trials
    survivors = [case_name for case_name, _ in ranked_trials[:required_survivor_count]]

    return SurvivorDeterminationResult(
        can_determine=True,
        survivors=survivors,
        remaining_trials=[],
        reason=f"Aggressive policy: {required_survivor_count} viable candidates identified",
        metadata={"completed_percent": completed_count / total_budget * 100},
    )


def _check_adaptive_early_stop(
    config: EarlyStoppingConfig,
    ranked_trials: list[tuple[str, float]],
    required_survivor_count: int,
    completed_count: int,
    total_budget: int,
) -> SurvivorDeterminationResult:
    """
    Adaptive early stopping: adjusts based on metric variance.

    Stops when:
    1. Top N trials have low variance (stable performance)
    2. Gap to next trial is significant relative to variance
    """
    import statistics

    if len(ranked_trials) <= required_survivor_count:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason="Not enough trials for adaptive variance analysis",
        )

    # Calculate variance in top N
    top_n_values = [value for _, value in ranked_trials[:required_survivor_count]]
    if len(top_n_values) < 2:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason="Need at least 2 survivors for variance calculation",
        )

    try:
        top_n_stdev = statistics.stdev(top_n_values)
        top_n_mean = statistics.mean(top_n_values)
    except statistics.StatisticsError:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason="Cannot calculate variance",
        )

    # Check if variance is low (coefficient of variation < 10%)
    if abs(top_n_mean) > 0:
        cv = abs(top_n_stdev / top_n_mean) * 100
    else:
        cv = float('inf')

    nth_value = ranked_trials[required_survivor_count - 1][1]
    next_value = ranked_trials[required_survivor_count][1]
    gap = abs(nth_value - next_value)

    # Gap should be larger than 2 standard deviations for confidence
    if gap < 2 * top_n_stdev:
        return SurvivorDeterminationResult(
            can_determine=False,
            survivors=[],
            remaining_trials=[],
            reason=f"Gap ({gap:.1f}) less than 2*stdev ({2*top_n_stdev:.1f})",
            metadata={"gap": gap, "stdev": top_n_stdev, "cv_percent": cv},
        )

    survivors = [case_name for case_name, _ in ranked_trials[:required_survivor_count]]
    return SurvivorDeterminationResult(
        can_determine=True,
        survivors=survivors,
        remaining_trials=[],
        reason=f"Adaptive: top {required_survivor_count} stable (CV={cv:.1f}%), gap={gap:.1f} > 2*σ",
        metadata={"gap": gap, "stdev": top_n_stdev, "cv_percent": cv},
    )
