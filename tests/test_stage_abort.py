"""Tests for stage abort detection and decision logic."""

import pytest

from src.controller.failure import (
    FailureClassification,
    FailureSeverity,
    FailureType,
)
from src.controller.stage_abort import (
    AbortReason,
    StageAbortDecision,
    check_catastrophic_failure_rate,
    check_no_survivors,
    check_wns_threshold_violation,
    evaluate_stage_abort,
)
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    StageConfig,
    TimingMetrics,
    TrialMetrics,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult
from pathlib import Path


def create_trial_result(
    case_name: str,
    wns_ps: int | None = None,
    success: bool = True,
    failure: FailureClassification | None = None,
) -> TrialResult:
    """Helper to create a TrialResult for testing."""
    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path="/tmp/test.tcl",
        snapshot_dir="/tmp/snapshot",
    )

    metrics = None
    if wns_ps is not None:
        metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=wns_ps),
            congestion=None,
        )

    return TrialResult(
        config=config,
        success=success,
        return_code=0 if success else 1,
        runtime_seconds=1.0,
        artifacts=TrialArtifacts(trial_dir=Path("/tmp/artifacts")),
        metrics=metrics,
        failure=failure,
    )


class TestStageAbortDecision:
    """Tests for StageAbortDecision dataclass."""

    def test_stage_abort_decision_creation(self) -> None:
        """Test creating a StageAbortDecision."""
        decision = StageAbortDecision(
            should_abort=True,
            reason=AbortReason.WNS_THRESHOLD_VIOLATED,
            details="WNS too negative",
            violating_trials=["case1", "case2"],
        )

        assert decision.should_abort is True
        assert decision.reason == AbortReason.WNS_THRESHOLD_VIOLATED
        assert decision.details == "WNS too negative"
        assert decision.violating_trials == ["case1", "case2"]

    def test_stage_abort_decision_no_violating_trials(self) -> None:
        """Test StageAbortDecision with no violating trials."""
        decision = StageAbortDecision(
            should_abort=False,
            reason=None,
            details="All good",
        )

        assert decision.should_abort is False
        assert decision.reason is None
        assert decision.violating_trials == []

    def test_stage_abort_decision_to_dict(self) -> None:
        """Test serialization to dictionary."""
        decision = StageAbortDecision(
            should_abort=True,
            reason=AbortReason.WNS_THRESHOLD_VIOLATED,
            details="Bad timing",
            violating_trials=["case1"],
        )

        result = decision.to_dict()

        assert result["should_abort"] is True
        assert result["reason"] == "wns_threshold_violated"
        assert result["details"] == "Bad timing"
        assert result["violating_trials"] == ["case1"]


class TestCheckWNSThresholdViolation:
    """Tests for WNS threshold violation checking."""

    def test_no_threshold_configured_never_aborts(self) -> None:
        """Test that when no threshold is configured, we never abort."""
        trials = [
            create_trial_result("case1", wns_ps=-10000),  # Very negative
            create_trial_result("case2", wns_ps=-20000),  # Even worse
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=None,  # No threshold
        )

        assert decision.should_abort is False
        assert decision.reason is None
        assert "No WNS abort threshold configured" in decision.details

    def test_all_trials_within_threshold(self) -> None:
        """Test that trials within threshold don't trigger abort."""
        trials = [
            create_trial_result("case1", wns_ps=-1000),  # -1 ns
            create_trial_result("case2", wns_ps=-2000),  # -2 ns
            create_trial_result("case3", wns_ps=-3000),  # -3 ns
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=-5000,  # Threshold: -5 ns
        )

        assert decision.should_abort is False
        assert decision.reason is None
        assert "All trials within WNS threshold" in decision.details

    def test_single_trial_violates_threshold(self) -> None:
        """Test that a single violating trial triggers abort."""
        trials = [
            create_trial_result("case1", wns_ps=-1000),  # OK
            create_trial_result("case2", wns_ps=-6000),  # VIOLATES (-6 ns < -5 ns)
            create_trial_result("case3", wns_ps=-2000),  # OK
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=-5000,  # Threshold: -5 ns
        )

        assert decision.should_abort is True
        assert decision.reason == AbortReason.WNS_THRESHOLD_VIOLATED
        assert "WNS threshold violated" in decision.details
        assert "-6.000 ns" in decision.details
        assert "-5.000 ns" in decision.details
        assert decision.violating_trials == ["case2"]

    def test_multiple_trials_violate_threshold(self) -> None:
        """Test multiple violating trials are all captured."""
        trials = [
            create_trial_result("case1", wns_ps=-6000),  # VIOLATES
            create_trial_result("case2", wns_ps=-7000),  # VIOLATES (worst)
            create_trial_result("case3", wns_ps=-2000),  # OK
            create_trial_result("case4", wns_ps=-5500),  # VIOLATES
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=-5000,
        )

        assert decision.should_abort is True
        assert decision.reason == AbortReason.WNS_THRESHOLD_VIOLATED
        assert len(decision.violating_trials) == 3
        assert set(decision.violating_trials) == {"case1", "case2", "case4"}
        assert "-7.000 ns" in decision.details  # Worst WNS reported

    def test_failed_trials_are_skipped(self) -> None:
        """Test that failed trials don't count toward threshold."""
        trials = [
            create_trial_result("case1", wns_ps=-6000, success=False),  # Failed, ignored
            create_trial_result("case2", wns_ps=-2000),  # OK
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=-5000,
        )

        assert decision.should_abort is False  # Only successful trial is OK
        assert decision.violating_trials == []

    def test_trials_without_metrics_are_skipped(self) -> None:
        """Test that trials without WNS metrics don't trigger abort."""
        trials = [
            create_trial_result("case1", wns_ps=None),  # No metrics
            create_trial_result("case2", wns_ps=-2000),  # OK
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=-5000,
        )

        assert decision.should_abort is False

    def test_threshold_exactly_at_boundary(self) -> None:
        """Test behavior when WNS is exactly at threshold."""
        trials = [
            create_trial_result("case1", wns_ps=-5000),  # Exactly at threshold
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=-5000,
        )

        # At threshold is OK (not strictly less than)
        assert decision.should_abort is False

    def test_positive_wns_never_violates(self) -> None:
        """Test that positive WNS (slack met) never violates."""
        trials = [
            create_trial_result("case1", wns_ps=1000),  # Positive slack
            create_trial_result("case2", wns_ps=2000),
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=0,
            abort_threshold_wns_ps=-5000,
        )

        assert decision.should_abort is False


class TestCheckCatastrophicFailureRate:
    """Tests for catastrophic failure rate checking."""

    def test_no_catastrophic_failures(self) -> None:
        """Test that non-catastrophic failures don't trigger abort."""
        trials = [
            create_trial_result("case1", wns_ps=-1000),
            create_trial_result(
                "case2",
                success=False,
                failure=FailureClassification(
                    failure_type=FailureType.STA_FAILED,
                    severity=FailureSeverity.MEDIUM,
                    reason="Timing not met",
                ),
            ),
        ]

        decision = check_catastrophic_failure_rate(trials)

        assert decision.should_abort is False
        assert "acceptable" in decision.details.lower()

    def test_high_catastrophic_failure_rate_triggers_abort(self) -> None:
        """Test that high catastrophic failure rate triggers abort."""
        # Create 10 trials: 6 catastrophic (60%), 4 successful
        trials = []
        for i in range(6):
            trials.append(
                create_trial_result(
                    f"case{i}",
                    success=False,
                    failure=FailureClassification(
                        failure_type=FailureType.SEGFAULT,
                        severity=FailureSeverity.CRITICAL,
                        reason="Segmentation fault",
                    ),
                )
            )
        for i in range(6, 10):
            trials.append(create_trial_result(f"case{i}", wns_ps=-1000))

        decision = check_catastrophic_failure_rate(trials, max_catastrophic_rate=0.5)

        assert decision.should_abort is True
        assert decision.reason == AbortReason.CATASTROPHIC_FAILURE_RATE
        assert "6/10" in decision.details
        assert "60%" in decision.details or "60.0%" in decision.details
        assert len(decision.violating_trials) == 6

    def test_catastrophic_rate_at_threshold_does_not_abort(self) -> None:
        """Test that exactly at threshold (not over) doesn't abort."""
        # Create 10 trials: exactly 5 catastrophic (50%)
        trials = []
        for i in range(5):
            trials.append(
                create_trial_result(
                    f"case{i}",
                    success=False,
                    failure=FailureClassification(
                        failure_type=FailureType.OOM,
                        severity=FailureSeverity.CRITICAL,
                        reason="Out of memory",
                    ),
                )
            )
        for i in range(5, 10):
            trials.append(create_trial_result(f"case{i}", wns_ps=-1000))

        decision = check_catastrophic_failure_rate(trials, max_catastrophic_rate=0.5)

        # Exactly at 50% threshold should not abort (not strictly greater)
        assert decision.should_abort is False

    def test_empty_trial_list_does_not_abort(self) -> None:
        """Test that empty trial list doesn't trigger abort."""
        decision = check_catastrophic_failure_rate([])

        assert decision.should_abort is False
        assert "No trials executed" in decision.details

    def test_custom_threshold(self) -> None:
        """Test custom catastrophic failure threshold."""
        # 2/10 = 20% catastrophic
        trials = []
        for i in range(2):
            trials.append(
                create_trial_result(
                    f"case{i}",
                    success=False,
                    failure=FailureClassification(
                        failure_type=FailureType.CORE_DUMP,
                        severity=FailureSeverity.CRITICAL,
                        reason="Core dumped",
                    ),
                )
            )
        for i in range(2, 10):
            trials.append(create_trial_result(f"case{i}", wns_ps=-1000))

        # With 10% threshold, 20% should abort
        decision = check_catastrophic_failure_rate(trials, max_catastrophic_rate=0.1)
        assert decision.should_abort is True

        # With 30% threshold, 20% should not abort
        decision = check_catastrophic_failure_rate(trials, max_catastrophic_rate=0.3)
        assert decision.should_abort is False


class TestCheckNoSurvivors:
    """Tests for no survivors checking."""

    def test_no_survivors_triggers_abort(self) -> None:
        """Test that zero survivors triggers abort."""
        decision = check_no_survivors(survivor_count=0)

        assert decision.should_abort is True
        assert decision.reason == AbortReason.NO_SURVIVORS
        assert "Cannot proceed" in decision.details

    def test_survivors_present_does_not_abort(self) -> None:
        """Test that having survivors doesn't trigger abort."""
        decision = check_no_survivors(survivor_count=5)

        assert decision.should_abort is False
        assert decision.reason is None
        assert "Sufficient survivors" in decision.details

    def test_custom_required_survivors(self) -> None:
        """Test custom required survivor count."""
        # Require at least 3 survivors
        decision = check_no_survivors(survivor_count=2, required_survivors=3)
        assert decision.should_abort is True

        decision = check_no_survivors(survivor_count=3, required_survivors=3)
        assert decision.should_abort is False

        decision = check_no_survivors(survivor_count=5, required_survivors=3)
        assert decision.should_abort is False


class TestEvaluateStageAbort:
    """Integration tests for complete stage abort evaluation."""

    def test_wns_threshold_violation_has_highest_priority(self) -> None:
        """Test that WNS violation is checked first."""
        stage_config = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            abort_threshold_wns_ps=-5000,
        )

        trials = [
            create_trial_result("case1", wns_ps=-6000),  # Violates WNS
        ]
        survivors = []  # No survivors (would also trigger abort)

        decision = evaluate_stage_abort(
            stage_config=stage_config,
            trial_results=trials,
            survivors=survivors,
        )

        # WNS violation should be reported, not no_survivors
        assert decision.should_abort is True
        assert decision.reason == AbortReason.WNS_THRESHOLD_VIOLATED

    def test_catastrophic_failure_checked_second(self) -> None:
        """Test catastrophic failures checked after WNS."""
        stage_config = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            abort_threshold_wns_ps=None,  # No WNS threshold
        )

        # All trials catastrophic
        trials = []
        for i in range(10):
            trials.append(
                create_trial_result(
                    f"case{i}",
                    success=False,
                    failure=FailureClassification(
                        failure_type=FailureType.SEGFAULT,
                        severity=FailureSeverity.CRITICAL,
                        reason="Segfault",
                    ),
                )
            )

        survivors = []  # No survivors

        decision = evaluate_stage_abort(
            stage_config=stage_config,
            trial_results=trials,
            survivors=survivors,
        )

        # Catastrophic rate should be reported
        assert decision.should_abort is True
        assert decision.reason == AbortReason.CATASTROPHIC_FAILURE_RATE

    def test_no_survivors_checked_last(self) -> None:
        """Test no survivors is checked last."""
        stage_config = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            abort_threshold_wns_ps=None,
        )

        trials = [
            create_trial_result("case1", wns_ps=-1000),
            create_trial_result("case2", wns_ps=-2000),
        ]
        survivors = []  # No survivors selected

        decision = evaluate_stage_abort(
            stage_config=stage_config,
            trial_results=trials,
            survivors=survivors,
        )

        assert decision.should_abort is True
        assert decision.reason == AbortReason.NO_SURVIVORS

    def test_all_checks_pass(self) -> None:
        """Test when all abort checks pass."""
        stage_config = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            abort_threshold_wns_ps=-5000,
        )

        trials = [
            create_trial_result("case1", wns_ps=-1000),
            create_trial_result("case2", wns_ps=-2000),
            create_trial_result("case3", wns_ps=-3000),
        ]
        survivors = ["case1", "case2", "case3"]

        decision = evaluate_stage_abort(
            stage_config=stage_config,
            trial_results=trials,
            survivors=survivors,
        )

        assert decision.should_abort is False
        assert decision.reason is None
        assert "All abort checks passed" in decision.details

    def test_baseline_wns_passed_for_context(self) -> None:
        """Test that baseline WNS can be passed for context."""
        stage_config = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            abort_threshold_wns_ps=-5000,
        )

        trials = [create_trial_result("case1", wns_ps=-2000)]
        survivors = ["case1"]

        # Should not crash with baseline_wns_ps provided
        decision = evaluate_stage_abort(
            stage_config=stage_config,
            trial_results=trials,
            survivors=survivors,
            baseline_wns_ps=-1000,
        )

        assert decision.should_abort is False
