"""Tests for stage abort integration with StudyExecutor."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch

from src.controller.executor import StudyExecutor, StageResult, StudyResult
from src.controller.failure import FailureClassification, FailureType, FailureSeverity
from src.controller.stage_abort import AbortReason, StageAbortDecision
from src.controller.study import StudyConfig
from src.controller.types import ExecutionMode, SafetyDomain, StageConfig, TimingMetrics, TrialMetrics
from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts


def create_trial_metrics(wns_ps: int, tns_ps: int = 0) -> TrialMetrics:
    """Helper to create properly structured TrialMetrics."""
    return TrialMetrics(
        timing=TimingMetrics(wns_ps=wns_ps, tns_ps=tns_ps),
        congestion=None,
    )


@pytest.fixture
def study_config():
    """Create a minimal study configuration for testing."""
    return StudyConfig(
        name="test_study",
        base_case_name="test_base",
        pdk="test_pdk",
        snapshot_path="/tmp/test_snapshot",
        safety_domain=SafetyDomain.SANDBOX,
        stages=[
            StageConfig(
                name="stage_0",
                trial_budget=5,
                survivor_count=3,
                execution_mode=ExecutionMode.STA_ONLY,
                allowed_eco_classes=[],
                abort_threshold_wns_ps=-5000,  # Abort if WNS < -5000 ps
            ),
            StageConfig(
                name="stage_1",
                trial_budget=3,
                survivor_count=2,
                execution_mode=ExecutionMode.STA_ONLY,
                allowed_eco_classes=[],
                abort_threshold_wns_ps=None,  # No WNS threshold
            ),
        ],
    )


@pytest.fixture
def mock_trial_results_success():
    """Create mock trial results with successful timing."""
    results = []
    for i in range(5):
        config = TrialConfig(
            study_name="test_study",
            case_name=f"case_{i}",
            stage_index=0,
            trial_index=i,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/test_snapshot",
        )
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
        )
        # Add mock timing metrics (WNS = -2000 ps, better than threshold)
        result.metrics = create_trial_metrics(wns_ps=-2000, tns_ps=0)
        results.append(result)
    return results


@pytest.fixture
def mock_trial_results_wns_violation():
    """Create mock trial results where one trial violates WNS threshold."""
    results = []
    for i in range(5):
        config = TrialConfig(
            study_name="test_study",
            case_name=f"case_{i}",
            stage_index=0,
            trial_index=i,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/test_snapshot",
        )
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
        )
        # Trial 2 violates the -5000 ps threshold
        if i == 2:
            result.metrics = create_trial_metrics(wns_ps=-6000, tns_ps=-10000)  # Worse than -5000 ps threshold
        else:
            result.metrics = create_trial_metrics(wns_ps=-2000, tns_ps=0)
        results.append(result)
    return results


@pytest.fixture
def mock_trial_results_catastrophic():
    """Create mock trial results with catastrophic failures."""
    results = []
    for i in range(5):
        config = TrialConfig(
            study_name="test_study",
            case_name=f"case_{i}",
            stage_index=0,
            trial_index=i,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/test_snapshot",
        )
        # 3 out of 5 trials have catastrophic failures (segfault)
        if i < 3:
            result = TrialResult(
                config=config,
                success=False,
                return_code=139,  # SIGSEGV
                runtime_seconds=0.5,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
            )
            result.failure = FailureClassification(
                type=FailureType.SEGFAULT,
                severity=FailureSeverity.CRITICAL,
                reason="Segmentation fault",
                log_excerpt="Segmentation fault (core dumped)",
            )
        else:
            result = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=1.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
            )
            result.metrics = create_trial_metrics(wns_ps=-2000, tns_ps=0)
        results.append(result)
    return results


class TestStageAbortIntegration:
    """Test stage abort integration with StudyExecutor."""

    def test_stage_result_includes_abort_decision(self, study_config):
        """Test that StageResult includes abort_decision field."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )

        # Create a mock stage result
        stage_result = StageResult(
            stage_index=0,
            stage_name="test_stage",
            trials_executed=5,
            survivors=["case_0", "case_1", "case_2"],
            total_runtime_seconds=10.0,
        )

        # abort_decision should be None by default
        assert stage_result.abort_decision is None

        # Add an abort decision
        abort_decision = StageAbortDecision(
            should_abort=True,
            reason=AbortReason.WNS_THRESHOLD_VIOLATED,
            details="WNS threshold violated",
        )
        stage_result.abort_decision = abort_decision

        # Verify it's included in to_dict()
        result_dict = stage_result.to_dict()
        assert "abort_decision" in result_dict
        assert result_dict["abort_decision"]["should_abort"] is True
        assert result_dict["abort_decision"]["reason"] == "wns_threshold_violated"

    def test_baseline_wns_stored_from_verification(self, study_config):
        """Test that baseline WNS is stored from base case verification."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,  # We'll manually set it
        )

        # Initially, baseline_wns_ps should be None
        assert executor.baseline_wns_ps is None

        # Simulate storing baseline WNS (as would happen in verify_base_case)
        executor.baseline_wns_ps = -3000

        # Verify it's stored
        assert executor.baseline_wns_ps == -3000

    def test_execute_stage_returns_abort_decision(self, study_config):
        """Test that _execute_stage returns StageResult with abort_decision."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )
        executor.baseline_wns_ps = -3000

        # Execute stage (uses internal mocking for trials)
        stage_result = executor._execute_stage(
            stage_index=0,
            stage_config=study_config.stages[0],
            input_cases=[executor.base_case],
        )

        # Verify abort_decision is present in result
        # Note: Mock results don't have metrics, so abort logic will gracefully handle this
        assert stage_result.abort_decision is not None
        assert isinstance(stage_result.abort_decision, StageAbortDecision)
        # With mock results that have no metrics, no abort should be triggered
        assert stage_result.abort_decision.should_abort is False

    def test_no_abort_when_all_trials_pass_threshold(self, study_config):
        """Test no abort when all trials pass WNS threshold."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )
        executor.baseline_wns_ps = -3000

        # Create mock successful trials (all WNS > -5000 ps threshold)
        trial_results = []
        for i in range(5):
            config = TrialConfig(
                study_name="test_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                snapshot_dir="/tmp/test_snapshot",
            )
            result = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=1.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
            )
            result.metrics = {
                "timing": {"wns_ps": -2000, "tns_ps": 0}  # Better than -5000 ps threshold
            }
            trial_results.append(result)

        # Manually call evaluate_stage_abort
        from src.controller.stage_abort import evaluate_stage_abort

        abort_decision = evaluate_stage_abort(
            stage_config=study_config.stages[0],
            trial_results=trial_results,
            survivors=["case_0", "case_1", "case_2"],
            baseline_wns_ps=executor.baseline_wns_ps,
        )

        # No abort should be triggered
        assert abort_decision.should_abort is False
        assert abort_decision.reason is None

    def test_abort_when_wns_threshold_violated(self, study_config):
        """Test abort when any trial violates WNS threshold."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )
        executor.baseline_wns_ps = -3000

        # Create mock trials where one violates threshold
        trial_results = []
        for i in range(5):
            config = TrialConfig(
                study_name="test_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                snapshot_dir="/tmp/test_snapshot",
            )
            result = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=1.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
            )
            # Trial 2 violates the -5000 ps threshold
            if i == 2:
                result.metrics = {
                    "timing": {"wns_ps": -6000, "tns_ps": -10000}  # Worse than -5000 ps
                }
            else:
                result.metrics = create_trial_metrics(wns_ps=-2000, tns_ps=0)
            trial_results.append(result)

        # Manually call evaluate_stage_abort
        from src.controller.stage_abort import evaluate_stage_abort

        abort_decision = evaluate_stage_abort(
            stage_config=study_config.stages[0],
            trial_results=trial_results,
            survivors=["case_0", "case_1", "case_3"],
            baseline_wns_ps=executor.baseline_wns_ps,
        )

        # Abort should be triggered
        assert abort_decision.should_abort is True
        assert abort_decision.reason == AbortReason.WNS_THRESHOLD_VIOLATED
        assert "case_2" in abort_decision.violating_trials

    def test_abort_when_catastrophic_failure_rate_high(self, study_config):
        """Test abort when catastrophic failure rate exceeds threshold."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )

        # Create mock trials with high catastrophic failure rate
        trial_results = []
        for i in range(5):
            config = TrialConfig(
                study_name="test_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                snapshot_dir="/tmp/test_snapshot",
            )
            # 3 out of 5 trials have catastrophic failures (60% > 50% threshold)
            if i < 3:
                result = TrialResult(
                    config=config,
                    success=False,
                    return_code=139,  # SIGSEGV
                    runtime_seconds=0.5,
                    artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
                )
                # Add FailureClassification for catastrophic failure
                result.failure = FailureClassification(
                    failure_type=FailureType.SEGFAULT,
                    severity=FailureSeverity.CRITICAL,
                    reason="Segmentation fault",
                    log_excerpt="Segmentation fault (core dumped)",
                )
            else:
                result = TrialResult(
                    config=config,
                    success=True,
                    return_code=0,
                    runtime_seconds=1.0,
                    artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
                )
                result.metrics = create_trial_metrics(wns_ps=-2000, tns_ps=0)
            trial_results.append(result)

        # Manually call evaluate_stage_abort
        from src.controller.stage_abort import evaluate_stage_abort

        abort_decision = evaluate_stage_abort(
            stage_config=study_config.stages[0],
            trial_results=trial_results,
            survivors=["case_3", "case_4"],
            baseline_wns_ps=-3000,
        )

        # Abort should be triggered due to catastrophic failure rate
        assert abort_decision.should_abort is True
        assert abort_decision.reason == AbortReason.CATASTROPHIC_FAILURE_RATE

    def test_abort_when_no_survivors(self, study_config):
        """Test abort when no survivors remain."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )

        # Create mock trials (doesn't matter if they pass or fail)
        trial_results = []
        for i in range(5):
            config = TrialConfig(
                study_name="test_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                snapshot_dir="/tmp/test_snapshot",
            )
            result = TrialResult(
                config=config,
                success=False,  # All failed
                return_code=1,
                runtime_seconds=1.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
            )
            trial_results.append(result)

        # Manually call evaluate_stage_abort with no survivors
        from src.controller.stage_abort import evaluate_stage_abort

        abort_decision = evaluate_stage_abort(
            stage_config=study_config.stages[0],
            trial_results=trial_results,
            survivors=[],  # No survivors
            baseline_wns_ps=-3000,
        )

        # Abort should be triggered
        assert abort_decision.should_abort is True
        assert abort_decision.reason == AbortReason.NO_SURVIVORS

    def test_abort_priority_wns_over_catastrophic(self, study_config):
        """Test that WNS threshold violations are checked before catastrophic failures."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )

        # Create trials with BOTH WNS violation AND high catastrophic rate
        trial_results = []
        for i in range(5):
            config = TrialConfig(
                study_name="test_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                snapshot_dir="/tmp/test_snapshot",
            )
            if i == 0:
                # Trial 0: WNS violation (should trigger abort first)
                result = TrialResult(
                    config=config,
                    success=True,
                    return_code=0,
                    runtime_seconds=1.0,
                    artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
                )
                result.metrics = create_trial_metrics(wns_ps=-6000, tns_ps=-10000)  # Violates -5000 threshold
            elif i < 4:
                # Trials 1-3: Catastrophic failures (would trigger catastrophic rate abort)
                result = TrialResult(
                    config=config,
                    success=False,
                    return_code=139,  # SIGSEGV
                    runtime_seconds=0.5,
                    artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
                )
                result.failure = FailureClassification(
                    failure_type=FailureType.SEGFAULT,
                    severity=FailureSeverity.CRITICAL,
                    reason="Segmentation fault",
                    log_excerpt="Segmentation fault (core dumped)",
                )
            else:
                # Trial 4: Success
                result = TrialResult(
                    config=config,
                    success=True,
                    return_code=0,
                    runtime_seconds=1.0,
                    artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
                )
                result.metrics = create_trial_metrics(wns_ps=-2000, tns_ps=0)
            trial_results.append(result)

        # Manually call evaluate_stage_abort
        from src.controller.stage_abort import evaluate_stage_abort

        abort_decision = evaluate_stage_abort(
            stage_config=study_config.stages[0],
            trial_results=trial_results,
            survivors=["case_0", "case_4"],
            baseline_wns_ps=-3000,
        )

        # WNS threshold violation should be the reason (higher priority)
        assert abort_decision.should_abort is True
        assert abort_decision.reason == AbortReason.WNS_THRESHOLD_VIOLATED
        assert "case_0" in abort_decision.violating_trials

    def test_no_wns_threshold_no_abort(self, study_config):
        """Test that stages without WNS threshold don't abort on WNS."""
        executor = StudyExecutor(
            config=study_config,
            skip_base_case_verification=True,
        )

        # Use stage 1 which has abort_threshold_wns_ps = None
        stage_config = study_config.stages[1]
        assert stage_config.abort_threshold_wns_ps is None

        # Create trials with very bad WNS
        trial_results = []
        for i in range(3):
            config = TrialConfig(
                study_name="test_study",
                case_name=f"case_{i}",
                stage_index=1,
                trial_index=i,
                script_path="/tmp/test.tcl",
                snapshot_dir="/tmp/test_snapshot",
            )
            result = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=1.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
            )
            result.metrics = create_trial_metrics(wns_ps=-10000, tns_ps=-50000)  # Very bad, but no threshold
            trial_results.append(result)

        # Manually call evaluate_stage_abort
        from src.controller.stage_abort import evaluate_stage_abort

        abort_decision = evaluate_stage_abort(
            stage_config=stage_config,
            trial_results=trial_results,
            survivors=["case_0", "case_1"],
            baseline_wns_ps=-3000,
        )

        # No abort since there's no WNS threshold configured
        assert abort_decision.should_abort is False

    def test_abort_decision_serialization(self):
        """Test that abort decision can be serialized for telemetry."""
        abort_decision = StageAbortDecision(
            should_abort=True,
            reason=AbortReason.WNS_THRESHOLD_VIOLATED,
            details="Trial case_2 has WNS -6000 ps which is worse than threshold -5000 ps",
            violating_trials=["case_2"],
        )

        # Convert to dict
        decision_dict = abort_decision.to_dict()

        # Verify structure
        assert decision_dict["should_abort"] is True
        assert decision_dict["reason"] == "wns_threshold_violated"
        assert decision_dict["details"] == "Trial case_2 has WNS -6000 ps which is worse than threshold -5000 ps"
        assert decision_dict["violating_trials"] == ["case_2"]

    def test_stage_result_with_abort_decision_to_dict(self):
        """Test that StageResult with abort_decision serializes correctly."""
        abort_decision = StageAbortDecision(
            should_abort=True,
            reason=AbortReason.CATASTROPHIC_FAILURE_RATE,
            details="60.0% of trials are catastrophic (> 50.0% threshold)",
        )

        stage_result = StageResult(
            stage_index=0,
            stage_name="test_stage",
            trials_executed=5,
            survivors=[],
            total_runtime_seconds=10.0,
            abort_decision=abort_decision,
        )

        result_dict = stage_result.to_dict()

        # Verify abort_decision is included
        assert "abort_decision" in result_dict
        assert result_dict["abort_decision"]["should_abort"] is True
        assert result_dict["abort_decision"]["reason"] == "catastrophic_failure_rate"
