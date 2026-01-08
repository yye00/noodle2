"""Stage abort detection and decision logic for safety-critical execution control."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.controller.types import StageConfig
    from src.trial_runner.trial import TrialResult


class AbortReason(Enum):
    """Reasons why a stage might be aborted."""

    WNS_THRESHOLD_VIOLATED = "wns_threshold_violated"
    CATASTROPHIC_FAILURE_RATE = "catastrophic_failure_rate"
    ECO_CLASS_BLOCKED = "eco_class_blocked"
    NO_SURVIVORS = "no_survivors"
    TIMEOUT_EXCEEDED = "timeout_exceeded"


@dataclass
class StageAbortDecision:
    """
    Decision about whether to abort a stage.

    This captures the deterministic abort decision logic based on
    trial results and stage configuration.
    """

    should_abort: bool
    reason: AbortReason | None
    details: str
    violating_trials: list[str] = None  # Case IDs of trials that violated thresholds

    def __post_init__(self) -> None:
        """Initialize violating_trials list if None."""
        if self.violating_trials is None:
            self.violating_trials = []

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "should_abort": self.should_abort,
            "reason": self.reason.value if self.reason else None,
            "details": self.details,
            "violating_trials": self.violating_trials,
        }


def check_wns_threshold_violation(
    trial_results: list[TrialResult],
    baseline_wns_ps: int | None,
    abort_threshold_wns_ps: int | None,
) -> StageAbortDecision:
    """
    Check if any trials violate the WNS abort threshold.

    The threshold is specified as an absolute WNS value (in picoseconds).
    If ANY trial's WNS is worse (more negative) than the threshold, the stage aborts.

    This is a critical safety mechanism to prevent pursuing pathological ECOs
    that drastically worsen timing.

    Args:
        trial_results: All trials executed in this stage
        baseline_wns_ps: Baseline WNS from base case (for context, not used for threshold)
        abort_threshold_wns_ps: Absolute WNS threshold (e.g., -5000 ps = -5 ns).
                                If any trial has WNS < this value, abort.

    Returns:
        StageAbortDecision indicating whether to abort and why

    Example:
        abort_threshold_wns_ps = -5000  # Abort if WNS worse than -5 ns
        trial_wns_ps = -6000            # Trial has -6 ns WNS
        # Result: ABORT (trial is worse than threshold)
    """
    if abort_threshold_wns_ps is None:
        # No threshold configured - never abort based on WNS
        return StageAbortDecision(
            should_abort=False,
            reason=None,
            details="No WNS abort threshold configured",
        )

    # Find trials that violate the threshold
    violating_trials: list[str] = []
    worst_wns_ps: int | None = None

    for trial in trial_results:
        # Skip failed trials (they're already handled by early failure classification)
        if not trial.success:
            continue

        # Extract WNS from metrics
        if trial.metrics is None:
            continue

        timing = trial.metrics.timing
        if timing is None:
            continue

        wns_ps = timing.wns_ps
        if wns_ps is None:
            continue

        # Check if this trial violates the threshold
        # WNS is more negative = worse timing
        # Example: wns_ps = -6000, threshold = -5000
        # -6000 < -5000 is True, so this violates
        if wns_ps < abort_threshold_wns_ps:
            violating_trials.append(trial.config.case_name)
            if worst_wns_ps is None or wns_ps < worst_wns_ps:
                worst_wns_ps = wns_ps

    if violating_trials:
        # At least one trial violated the threshold - abort stage
        wns_ns = worst_wns_ps / 1000.0 if worst_wns_ps else 0.0
        threshold_ns = abort_threshold_wns_ps / 1000.0

        details = (
            f"WNS threshold violated: {len(violating_trials)} trial(s) "
            f"exceeded threshold. Worst WNS: {wns_ns:.3f} ns "
            f"(threshold: {threshold_ns:.3f} ns). "
            f"Violating trials: {', '.join(violating_trials[:5])}"
        )
        if len(violating_trials) > 5:
            details += f" and {len(violating_trials) - 5} more"

        return StageAbortDecision(
            should_abort=True,
            reason=AbortReason.WNS_THRESHOLD_VIOLATED,
            details=details,
            violating_trials=violating_trials,
        )

    # No violations - do not abort
    return StageAbortDecision(
        should_abort=False,
        reason=None,
        details="All trials within WNS threshold",
    )


def check_catastrophic_failure_rate(
    trial_results: list[TrialResult],
    max_catastrophic_rate: float = 0.5,
) -> StageAbortDecision:
    """
    Check if the catastrophic failure rate exceeds acceptable limits.

    If too many trials fail catastrophically (segfaults, OOM, etc.), the stage
    should abort to prevent wasting compute on a fundamentally broken ECO set.

    Args:
        trial_results: All trials executed in this stage
        max_catastrophic_rate: Maximum acceptable rate (default: 0.5 = 50%)

    Returns:
        StageAbortDecision indicating whether to abort
    """
    if not trial_results:
        return StageAbortDecision(
            should_abort=False,
            reason=None,
            details="No trials executed",
        )

    catastrophic_count = 0
    catastrophic_trials: list[str] = []

    for trial in trial_results:
        if not trial.success and trial.failure is not None:
            # Check if failure is catastrophic
            from src.controller.failure import FailureClassifier

            if FailureClassifier.is_catastrophic(trial.failure):
                catastrophic_count += 1
                catastrophic_trials.append(trial.config.case_name)

    catastrophic_rate = catastrophic_count / len(trial_results)

    if catastrophic_rate > max_catastrophic_rate:
        details = (
            f"Catastrophic failure rate too high: {catastrophic_count}/{len(trial_results)} "
            f"({catastrophic_rate:.1%}) exceeds threshold ({max_catastrophic_rate:.1%}). "
            f"Failing trials: {', '.join(catastrophic_trials[:5])}"
        )
        if len(catastrophic_trials) > 5:
            details += f" and {len(catastrophic_trials) - 5} more"

        return StageAbortDecision(
            should_abort=True,
            reason=AbortReason.CATASTROPHIC_FAILURE_RATE,
            details=details,
            violating_trials=catastrophic_trials,
        )

    return StageAbortDecision(
        should_abort=False,
        reason=None,
        details=f"Catastrophic failure rate acceptable: {catastrophic_rate:.1%}",
    )


def check_no_survivors(
    survivor_count: int,
    required_survivors: int = 1,
) -> StageAbortDecision:
    """
    Check if the stage produced enough survivors to continue.

    If no trials survived (all failed or were below quality threshold),
    the study cannot continue to the next stage.

    Args:
        survivor_count: Number of survivors selected
        required_survivors: Minimum required (default: 1)

    Returns:
        StageAbortDecision indicating whether to abort
    """
    if survivor_count < required_survivors:
        return StageAbortDecision(
            should_abort=True,
            reason=AbortReason.NO_SURVIVORS,
            details=f"No survivors selected ({survivor_count} < {required_survivors}). "
            "Cannot proceed to next stage.",
        )

    return StageAbortDecision(
        should_abort=False,
        reason=None,
        details=f"Sufficient survivors: {survivor_count}",
    )


def evaluate_stage_abort(
    stage_config: StageConfig,
    trial_results: list[TrialResult],
    survivors: list[str],
    baseline_wns_ps: int | None = None,
) -> StageAbortDecision:
    """
    Evaluate all abort conditions and make a deterministic decision.

    This is the main entry point for stage abort logic. It checks all
    configured abort conditions in priority order:

    1. WNS threshold violations (configured per-stage)
    2. Catastrophic failure rate (safety limit)
    3. No survivors (cannot continue)

    Args:
        stage_config: Stage configuration with abort thresholds
        trial_results: All trial results from this stage
        survivors: List of survivor case IDs
        baseline_wns_ps: Optional baseline WNS for context

    Returns:
        StageAbortDecision with the highest-priority abort reason, or no abort
    """
    # Check abort conditions in priority order
    # If any condition triggers abort, return immediately

    # 1. Check WNS threshold
    wns_decision = check_wns_threshold_violation(
        trial_results=trial_results,
        baseline_wns_ps=baseline_wns_ps,
        abort_threshold_wns_ps=stage_config.abort_threshold_wns_ps,
    )
    if wns_decision.should_abort:
        return wns_decision

    # 2. Check catastrophic failure rate
    catastrophic_decision = check_catastrophic_failure_rate(trial_results)
    if catastrophic_decision.should_abort:
        return catastrophic_decision

    # 3. Check survivor count
    survivor_decision = check_no_survivors(len(survivors))
    if survivor_decision.should_abort:
        return survivor_decision

    # No abort conditions triggered
    return StageAbortDecision(
        should_abort=False,
        reason=None,
        details="All abort checks passed",
    )
