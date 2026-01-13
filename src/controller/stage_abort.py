"""Stage abort detection and decision logic for safety-critical execution control."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.controller.types import StageConfig
    from src.trial_runner.trial import TrialResult


class AbortReason(Enum):
    """Reasons why a stage or study might be aborted."""

    WNS_THRESHOLD_VIOLATED = "wns_threshold_violated"
    CATASTROPHIC_FAILURE_RATE = "catastrophic_failure_rate"
    ECO_CLASS_BLOCKED = "eco_class_blocked"
    NO_SURVIVORS = "no_survivors"
    TIMEOUT_EXCEEDED = "timeout_exceeded"
    CATASTROPHIC_FAILURE_COUNT = "catastrophic_failure_count"


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


@dataclass
class StudyAbortDecision:
    """
    Decision about whether to abort an entire study.

    This captures study-level abort conditions that span multiple stages.
    """

    should_abort: bool
    reason: AbortReason | None
    details: str
    catastrophic_count: int = 0  # Total catastrophic failures across all stages

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "should_abort": self.should_abort,
            "reason": self.reason.value if self.reason else None,
            "details": self.details,
            "catastrophic_count": self.catastrophic_count,
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

        # Handle both dict and object formats for metrics
        if isinstance(trial.metrics, dict):
            if "timing" not in trial.metrics:
                continue
            timing = trial.metrics["timing"]
            if isinstance(timing, dict):
                wns_ps = timing.get("wns_ps")
            else:
                wns_ps = timing.wns_ps
        else:
            # Object format
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


def check_timeout_violation(
    trial_results: list[TrialResult],
    timeout_seconds: int | None,
) -> StageAbortDecision:
    """
    Check if any trials exceeded the timeout threshold.

    The timeout is specified in seconds. If ANY trial's runtime exceeds this
    threshold, it is classified as a timeout violation.

    This is a critical safety mechanism to prevent runaway trials from consuming
    excessive compute resources.

    Args:
        trial_results: All trials executed in this stage
        timeout_seconds: Maximum allowed runtime in seconds

    Returns:
        StageAbortDecision indicating whether to abort and why

    Example:
        timeout_seconds = 60  # Abort if runtime > 60 seconds
        trial_runtime = 75    # Trial took 75 seconds
        # Result: ABORT (trial exceeded timeout)
    """
    if timeout_seconds is None:
        # No timeout configured - never abort based on timeout
        return StageAbortDecision(
            should_abort=False,
            reason=None,
            details="No timeout configured",
        )

    # Find trials that violated the timeout
    violating_trials: list[str] = []
    longest_runtime: float = 0.0

    for trial in trial_results:
        # Check runtime
        runtime = trial.runtime_seconds

        if runtime > timeout_seconds:
            violating_trials.append(trial.config.case_name)
            if runtime > longest_runtime:
                longest_runtime = runtime

    if violating_trials:
        # At least one trial violated the timeout - abort stage
        details = (
            f"Timeout violated: {len(violating_trials)} trial(s) "
            f"exceeded {timeout_seconds}s limit. Longest runtime: {longest_runtime:.1f}s. "
            f"Violating trials: {', '.join(violating_trials[:5])}"
        )
        if len(violating_trials) > 5:
            details += f" and {len(violating_trials) - 5} more"

        return StageAbortDecision(
            should_abort=True,
            reason=AbortReason.TIMEOUT_EXCEEDED,
            details=details,
            violating_trials=violating_trials,
        )

    # No violations - do not abort
    return StageAbortDecision(
        should_abort=False,
        reason=None,
        details=f"All trials completed within {timeout_seconds}s timeout",
    )


def check_stage_failure_rate(
    trial_results: list[TrialResult],
    failure_rate_threshold: float | None,
) -> StageAbortDecision:
    """
    Check if the stage failure rate exceeds the configured threshold.

    If too many trials fail (regardless of failure type), the stage should abort
    to avoid wasting compute on an ineffective ECO strategy.

    This is distinct from catastrophic_failure_rate which only counts critical
    failures like segfaults. This counts ALL failures.

    Args:
        trial_results: All trials executed in this stage
        failure_rate_threshold: Maximum acceptable failure rate (0.0-1.0)

    Returns:
        StageAbortDecision indicating whether to abort

    Example:
        failure_rate_threshold = 0.8  # Abort if >80% fail
        8 out of 10 trials failed     # 80% failure rate
        # Result: NO ABORT (exactly at threshold)
        9 out of 10 trials failed     # 90% failure rate
        # Result: ABORT (exceeds threshold)
    """
    if failure_rate_threshold is None:
        # No threshold configured - never abort based on failure rate
        return StageAbortDecision(
            should_abort=False,
            reason=None,
            details="No failure rate threshold configured",
        )

    if not trial_results:
        return StageAbortDecision(
            should_abort=False,
            reason=None,
            details="No trials executed",
        )

    # Count failures
    failure_count = 0
    failed_trials: list[str] = []

    for trial in trial_results:
        if not trial.success:
            failure_count += 1
            failed_trials.append(trial.config.case_name)

    failure_rate = failure_count / len(trial_results)

    if failure_rate > failure_rate_threshold:
        details = (
            f"Failure rate too high: {failure_count}/{len(trial_results)} "
            f"({failure_rate:.1%}) exceeds threshold ({failure_rate_threshold:.1%}). "
            f"Failed trials: {', '.join(failed_trials[:5])}"
        )
        if len(failed_trials) > 5:
            details += f" and {len(failed_trials) - 5} more"

        return StageAbortDecision(
            should_abort=True,
            reason=AbortReason.CATASTROPHIC_FAILURE_RATE,
            details=details,
            violating_trials=failed_trials,
        )

    return StageAbortDecision(
        should_abort=False,
        reason=None,
        details=f"Failure rate acceptable: {failure_rate:.1%}",
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
    abort_timeout_seconds: int | None = None,
    stage_failure_rate_threshold: float | None = None,
) -> StageAbortDecision:
    """
    Evaluate all abort conditions and make a deterministic decision.

    This is the main entry point for stage abort logic. It checks all
    configured abort conditions in priority order:

    1. WNS threshold violations (configured per-stage)
    2. Timeout violations (configured in abort rail)
    3. Stage failure rate (configured in stage rail)
    4. Catastrophic failure rate (safety limit)
    5. No survivors (cannot continue)

    Args:
        stage_config: Stage configuration with abort thresholds
        trial_results: All trial results from this stage
        survivors: List of survivor case IDs
        baseline_wns_ps: Optional baseline WNS for context
        abort_timeout_seconds: Optional timeout threshold from abort rail
        stage_failure_rate_threshold: Optional failure rate threshold from stage rail

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

    # 2. Check timeout violations
    timeout_decision = check_timeout_violation(
        trial_results=trial_results,
        timeout_seconds=abort_timeout_seconds,
    )
    if timeout_decision.should_abort:
        return timeout_decision

    # 3. Check stage failure rate
    stage_failure_decision = check_stage_failure_rate(
        trial_results=trial_results,
        failure_rate_threshold=stage_failure_rate_threshold,
    )
    if stage_failure_decision.should_abort:
        return stage_failure_decision

    # 4. Check catastrophic failure rate
    catastrophic_decision = check_catastrophic_failure_rate(trial_results)
    if catastrophic_decision.should_abort:
        return catastrophic_decision

    # 5. Check survivor count
    survivor_decision = check_no_survivors(len(survivors))
    if survivor_decision.should_abort:
        return survivor_decision

    # No abort conditions triggered
    return StageAbortDecision(
        should_abort=False,
        reason=None,
        details="All abort checks passed",
    )


def check_study_catastrophic_failure_count(
    all_trial_results: list[TrialResult],
    max_catastrophic_failures: int | None,
) -> StudyAbortDecision:
    """
    Check if the study has exceeded the catastrophic failure count threshold.

    This is a study-level check that counts catastrophic failures across ALL stages.
    If the total count exceeds the threshold, the entire study should be halted.

    This is distinct from stage-level catastrophic_failure_rate which looks at
    the percentage within a single stage. This counts absolute failures across
    the entire study.

    Args:
        all_trial_results: All trial results from all stages in the study
        max_catastrophic_failures: Maximum allowed catastrophic failures (study-wide)

    Returns:
        StudyAbortDecision indicating whether to abort the study

    Example:
        max_catastrophic_failures = 3  # Abort study after 3 catastrophic failures
        2 catastrophic failures so far # Study continues
        3 catastrophic failures        # Study halts
    """
    if max_catastrophic_failures is None:
        # No threshold configured - never abort based on catastrophic count
        return StudyAbortDecision(
            should_abort=False,
            reason=None,
            details="No catastrophic failure count threshold configured",
            catastrophic_count=0,
        )

    if not all_trial_results:
        return StudyAbortDecision(
            should_abort=False,
            reason=None,
            details="No trials executed yet",
            catastrophic_count=0,
        )

    # Count catastrophic failures across all trials
    catastrophic_count = 0
    catastrophic_trials: list[str] = []

    for trial in all_trial_results:
        if not trial.success and trial.failure is not None:
            # Check if failure is catastrophic
            from src.controller.failure import FailureClassifier

            if FailureClassifier.is_catastrophic(trial.failure):
                catastrophic_count += 1
                catastrophic_trials.append(trial.config.case_name)

    if catastrophic_count >= max_catastrophic_failures:
        details = (
            f"Study catastrophic failure threshold reached: {catastrophic_count} "
            f"catastrophic failures (threshold: {max_catastrophic_failures}). "
            f"Study must be halted. "
            f"Failed trials: {', '.join(catastrophic_trials[:5])}"
        )
        if len(catastrophic_trials) > 5:
            details += f" and {len(catastrophic_trials) - 5} more"

        return StudyAbortDecision(
            should_abort=True,
            reason=AbortReason.CATASTROPHIC_FAILURE_COUNT,
            details=details,
            catastrophic_count=catastrophic_count,
        )

    return StudyAbortDecision(
        should_abort=False,
        reason=None,
        details=f"Catastrophic failure count acceptable: {catastrophic_count}/{max_catastrophic_failures}",
        catastrophic_count=catastrophic_count,
    )
