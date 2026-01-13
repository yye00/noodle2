"""Tests for safety rails enforcement (F024-F028)."""

import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass

from src.controller.study import load_study_config
from src.controller.safety import check_study_legality, LegalityChecker
from src.controller.stage_abort import (
    check_wns_threshold_violation,
    check_timeout_violation,
    check_stage_failure_rate,
    check_study_catastrophic_failure_count,
    AbortReason,
)
from src.controller.failure import (
    FailureClassification,
    FailureType,
    FailureSeverity,
)
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
    TimingMetrics,
    TrialMetrics,
)
from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts


class TestF024ECOClassEnforcement:
    """
    Feature #F024: ECO class enforcement works for safety domains.

    Steps:
        1. Create study with safety_domain: locked
        2. Attempt to run ECO with class global_disruptive
        3. Verify ECO is rejected before execution
        4. Verify error message indicates domain restriction
        5. Test that allowed classes (topology_neutral, placement_local) are permitted
    """

    def test_step_1_2_3_4_locked_domain_blocks_global_disruptive(self) -> None:
        """Steps 1-4: Locked domain blocks global_disruptive ECO class."""
        # Step 1: Create study with safety_domain: locked
        yaml_content = """
name: locked_domain_study
safety_domain: locked
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - global_disruptive
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)

            # Step 2-3: Attempt to run ECO with global_disruptive class - should be rejected
            checker = LegalityChecker(config)
            result = checker.check_legality()

            # Step 3: Verify ECO is rejected before execution
            assert result.is_legal is False
            assert result.has_violations is True
            assert len(result.violations) == 1

            # Step 4: Verify error message indicates domain restriction
            violation = result.violations[0]
            assert violation.eco_class == ECOClass.GLOBAL_DISRUPTIVE
            assert "not allowed" in violation.reason.lower()
            assert "locked" in violation.reason.lower()
            assert violation.severity == "error"

        finally:
            Path(yaml_path).unlink()

    def test_step_5_locked_domain_allows_safe_classes(self) -> None:
        """Step 5: Locked domain permits topology_neutral and placement_local."""
        # Create study with allowed classes for locked domain
        yaml_content = """
name: locked_domain_safe_study
safety_domain: locked
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
      - placement_local
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)

            # Verify allowed classes are permitted
            checker = LegalityChecker(config)
            result = checker.check_legality()

            assert result.is_legal is True
            assert result.has_violations is False
            assert len(result.violations) == 0

        finally:
            Path(yaml_path).unlink()

    def test_guarded_domain_blocks_global_disruptive(self) -> None:
        """Guarded domain also blocks global_disruptive ECO class."""
        yaml_content = """
name: guarded_domain_study
safety_domain: guarded
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - global_disruptive
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)
            checker = LegalityChecker(config)
            result = checker.check_legality()

            assert result.is_legal is False
            assert result.has_violations is True

        finally:
            Path(yaml_path).unlink()

    def test_sandbox_domain_allows_all_classes(self) -> None:
        """Sandbox domain permits all ECO classes including global_disruptive."""
        yaml_content = """
name: sandbox_domain_study
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
      - placement_local
      - routing_affecting
      - global_disruptive
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)
            checker = LegalityChecker(config)
            result = checker.check_legality()

            # Sandbox allows all classes
            assert result.is_legal is True
            assert result.has_violations is False

        finally:
            Path(yaml_path).unlink()

    def test_check_study_legality_raises_on_violation(self) -> None:
        """Test that check_study_legality convenience function raises on illegal study."""
        yaml_content = """
name: illegal_study
safety_domain: locked
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - global_disruptive
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)

            # Should raise ValueError for illegal study
            with pytest.raises(ValueError, match="ILLEGAL"):
                check_study_legality(config)

        finally:
            Path(yaml_path).unlink()


class TestF025AbortRailWNSThreshold:
    """
    Feature #F025: Abort rail triggers on WNS threshold violation.

    Steps:
        1. Create study with abort rail wns_ps: -5000
        2. Run trial that produces WNS worse than -5000ps
        3. Verify trial is aborted immediately
        4. Verify abort reason is logged in safety_trace.json
        5. Verify trial classified as rail_violation
    """

    def test_step_1_2_3_wns_threshold_triggers_abort(self) -> None:
        """Steps 1-3: WNS threshold violation triggers abort."""
        # Step 1: Create study with abort rail wns_ps: -5000
        yaml_content = """
name: wns_abort_study
safety_domain: guarded
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

rails:
  abort:
    wns_ps: -5000

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)

            # Verify rails configuration is loaded
            assert config.rails.abort.wns_ps == -5000

            # Step 2: Simulate trial that produces WNS worse than -5000ps (e.g., -6000ps)
            trial_config = TrialConfig(
                study_name="wns_abort_study",
                case_name="nangate45_base_0_0",
                stage_index=0,
                trial_index=0,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

            # Create a trial result with WNS = -6000 ps (worse than threshold)
            bad_metrics = TrialMetrics(
                timing=TimingMetrics(
                    wns_ps=-6000,  # Worse than -5000 threshold
                    tns_ps=-10000,
                    failing_endpoints=5,
                ),
                congestion=None,
            )

            bad_trial = TrialResult(
                config=trial_config,
                success=True,
                return_code=0,
                metrics=bad_metrics,
                artifacts=artifacts,
                runtime_seconds=100.0,
            )

            # Step 3: Verify trial triggers abort
            decision = check_wns_threshold_violation(
                trial_results=[bad_trial],
                baseline_wns_ps=None,
                abort_threshold_wns_ps=-5000,
            )

            assert decision.should_abort is True
            assert decision.reason == AbortReason.WNS_THRESHOLD_VIOLATED
            assert "nangate45_base_0_0" in decision.violating_trials
            assert "-6.000 ns" in decision.details
            assert "-5.000 ns" in decision.details

        finally:
            Path(yaml_path).unlink()

    def test_step_4_5_wns_within_threshold_no_abort(self) -> None:
        """Trial with WNS within threshold does not abort."""
        # Create trial with WNS = -4000 ps (better than -5000 threshold)
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="nangate45_base_0_0",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            execution_mode=ExecutionMode.STA_ONLY,
        )
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        good_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-4000,  # Better than -5000 threshold
                tns_ps=-8000,
                failing_endpoints=3,
            ),
            congestion=None,
        )

        good_trial = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            metrics=good_metrics,
            artifacts=artifacts,
            runtime_seconds=100.0,
        )

        # Verify no abort
        decision = check_wns_threshold_violation(
            trial_results=[good_trial],
            baseline_wns_ps=None,
            abort_threshold_wns_ps=-5000,
        )

        assert decision.should_abort is False
        assert decision.reason is None
        assert len(decision.violating_trials) == 0

    def test_no_threshold_configured_never_aborts(self) -> None:
        """When no WNS threshold is configured, never abort."""
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="nangate45_base_0_0",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            execution_mode=ExecutionMode.STA_ONLY,
        )
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        # Even with very bad WNS
        very_bad_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-100000,  # Very bad
                tns_ps=-200000,
                failing_endpoints=50,
            ),
            congestion=None,
        )

        trial = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            metrics=very_bad_metrics,
            artifacts=artifacts,
            runtime_seconds=100.0,
        )

        # No threshold configured - should not abort
        decision = check_wns_threshold_violation(
            trial_results=[trial],
            baseline_wns_ps=None,
            abort_threshold_wns_ps=None,  # No threshold
        )

        assert decision.should_abort is False
        assert decision.reason is None

    def test_multiple_trials_violation(self) -> None:
        """Multiple trials can violate WNS threshold."""
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(3)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        # Create mix of good and bad trials
        trials = [
            TrialResult(
                config=trial_configs[0],
                success=True,
                return_code=0,
                metrics=TrialMetrics(
                    timing=TimingMetrics(wns_ps=-6000, tns_ps=-10000, failing_endpoints=5),
                    congestion=None,
                ),
                artifacts=artifacts,
                runtime_seconds=100.0,
            ),
            TrialResult(
                config=trial_configs[1],
                success=True,
                return_code=0,
                metrics=TrialMetrics(
                    timing=TimingMetrics(wns_ps=-4000, tns_ps=-8000, failing_endpoints=3),
                    congestion=None,
                ),
                artifacts=artifacts,
                runtime_seconds=100.0,
            ),
            TrialResult(
                config=trial_configs[2],
                success=True,
                return_code=0,
                metrics=TrialMetrics(
                    timing=TimingMetrics(wns_ps=-7000, tns_ps=-12000, failing_endpoints=7),
                    congestion=None,
                ),
                artifacts=artifacts,
                runtime_seconds=100.0,
            ),
        ]

        decision = check_wns_threshold_violation(
            trial_results=trials,
            baseline_wns_ps=None,
            abort_threshold_wns_ps=-5000,
        )

        # Should abort due to trials 0 and 2
        assert decision.should_abort is True
        assert len(decision.violating_trials) == 2
        assert "nangate45_base_0_0" in decision.violating_trials
        assert "nangate45_base_0_2" in decision.violating_trials
        assert "nangate45_base_0_1" not in decision.violating_trials


class TestF026AbortRailTimeoutViolation:
    """
    Feature #F026: Abort rail triggers on timeout violation.

    Steps:
        1. Create study with abort rail timeout_seconds: 60
        2. Run trial that takes longer than 60 seconds
        3. Verify trial is killed after timeout
        4. Verify abort reason is logged
        5. Verify trial classified as timeout failure
    """

    def test_step_1_2_3_timeout_triggers_abort(self) -> None:
        """Steps 1-3: Timeout violation triggers abort."""
        # Step 1: Create study with abort rail timeout_seconds: 60
        yaml_content = """
name: timeout_abort_study
safety_domain: guarded
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

rails:
  abort:
    timeout_seconds: 60

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)

            # Verify rails configuration is loaded
            assert config.rails.abort.timeout_seconds == 60

            # Step 2: Simulate trial that takes longer than 60 seconds (e.g., 75 seconds)
            trial_config = TrialConfig(
                study_name="timeout_abort_study",
                case_name="nangate45_base_0_0",
                stage_index=0,
                trial_index=0,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

            # Create a trial result with runtime = 75 seconds (exceeds 60s timeout)
            slow_metrics = TrialMetrics(
                timing=TimingMetrics(
                    wns_ps=-2000,
                    tns_ps=-5000,
                    failing_endpoints=2,
                ),
                congestion=None,
            )

            slow_trial = TrialResult(
                config=trial_config,
                success=True,
                return_code=0,
                metrics=slow_metrics,
                artifacts=artifacts,
                runtime_seconds=75.0,  # Exceeds 60s timeout
            )

            # Step 3: Verify trial triggers abort
            decision = check_timeout_violation(
                trial_results=[slow_trial],
                timeout_seconds=60,
            )

            assert decision.should_abort is True
            assert decision.reason == AbortReason.TIMEOUT_EXCEEDED
            assert "nangate45_base_0_0" in decision.violating_trials
            assert "75.0s" in decision.details
            assert "60s" in decision.details

        finally:
            Path(yaml_path).unlink()

    def test_step_4_5_trial_within_timeout_no_abort(self) -> None:
        """Steps 4-5: Trial within timeout does not abort."""
        # Create trial with runtime = 50 seconds (within 60s timeout)
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="nangate45_base_0_0",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            execution_mode=ExecutionMode.STA_ONLY,
        )
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        fast_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-2000,
                tns_ps=-5000,
                failing_endpoints=2,
            ),
            congestion=None,
        )

        fast_trial = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            metrics=fast_metrics,
            artifacts=artifacts,
            runtime_seconds=50.0,  # Within 60s timeout
        )

        # Verify no abort
        decision = check_timeout_violation(
            trial_results=[fast_trial],
            timeout_seconds=60,
        )

        assert decision.should_abort is False
        assert decision.reason is None
        assert len(decision.violating_trials) == 0

    def test_no_timeout_configured_never_aborts(self) -> None:
        """When no timeout is configured, never abort."""
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="nangate45_base_0_0",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            execution_mode=ExecutionMode.STA_ONLY,
        )
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        # Even with very long runtime
        very_slow_trial = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            metrics=TrialMetrics(
                timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                congestion=None,
            ),
            artifacts=artifacts,
            runtime_seconds=300.0,  # Very slow
        )

        # No timeout configured - should not abort
        decision = check_timeout_violation(
            trial_results=[very_slow_trial],
            timeout_seconds=None,  # No timeout
        )

        assert decision.should_abort is False
        assert decision.reason is None

    def test_multiple_trials_timeout_violation(self) -> None:
        """Multiple trials can violate timeout."""
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(3)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
            congestion=None,
        )

        # Create mix of fast and slow trials
        trials = [
            TrialResult(
                config=trial_configs[0],
                success=True,
                return_code=0,
                metrics=metrics,
                artifacts=artifacts,
                runtime_seconds=75.0,  # Exceeds timeout
            ),
            TrialResult(
                config=trial_configs[1],
                success=True,
                return_code=0,
                metrics=metrics,
                artifacts=artifacts,
                runtime_seconds=50.0,  # Within timeout
            ),
            TrialResult(
                config=trial_configs[2],
                success=True,
                return_code=0,
                metrics=metrics,
                artifacts=artifacts,
                runtime_seconds=80.0,  # Exceeds timeout
            ),
        ]

        decision = check_timeout_violation(
            trial_results=trials,
            timeout_seconds=60,
        )

        # Should abort due to trials 0 and 2
        assert decision.should_abort is True
        assert len(decision.violating_trials) == 2
        assert "nangate45_base_0_0" in decision.violating_trials
        assert "nangate45_base_0_2" in decision.violating_trials
        assert "nangate45_base_0_1" not in decision.violating_trials

    def test_timeout_at_boundary(self) -> None:
        """Test behavior when runtime is exactly at timeout."""
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="nangate45_base_0_0",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            execution_mode=ExecutionMode.STA_ONLY,
        )
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trial = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            metrics=TrialMetrics(
                timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                congestion=None,
            ),
            artifacts=artifacts,
            runtime_seconds=60.0,  # Exactly at timeout
        )

        decision = check_timeout_violation(
            trial_results=[trial],
            timeout_seconds=60,
        )

        # At timeout is OK (not strictly greater than)
        assert decision.should_abort is False


class TestF027StageRailFailureRate:
    """
    Feature #F027: Stage rail triggers on high failure rate.

    Steps:
        1. Create stage with stage rail failure_rate: 0.8
        2. Run trials where 80%+ fail
        3. Verify stage is terminated early
        4. Verify termination reason is logged
        5. Verify only current survivors advance to next stage
    """

    def test_step_1_2_3_high_failure_rate_triggers_abort(self) -> None:
        """Steps 1-3: High failure rate triggers stage abort."""
        # Step 1: Create study with stage rail failure_rate: 0.8
        yaml_content = """
name: failure_rate_study
safety_domain: guarded
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

rails:
  stage:
    failure_rate: 0.8

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)

            # Verify rails configuration is loaded
            assert config.rails.stage.failure_rate == 0.8

            # Step 2: Simulate trials where 9/10 fail (90% failure rate > 80% threshold)
            trial_configs = [
                TrialConfig(
                    study_name="failure_rate_study",
                    case_name=f"nangate45_base_0_{i}",
                    stage_index=0,
                    trial_index=i,
                    script_path="/tmp/test.tcl",
                    execution_mode=ExecutionMode.STA_ONLY,
                )
                for i in range(10)
            ]
            artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

            trials = []
            # 9 failures
            for i in range(9):
                trials.append(
                    TrialResult(
                        config=trial_configs[i],
                        success=False,  # Failed
                        return_code=1,
                        metrics=None,
                        artifacts=artifacts,
                        runtime_seconds=50.0,
                    )
                )
            # 1 success
            trials.append(
                TrialResult(
                    config=trial_configs[9],
                    success=True,
                    return_code=0,
                    metrics=TrialMetrics(
                        timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                        congestion=None,
                    ),
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                )
            )

            # Step 3: Verify stage is terminated due to high failure rate
            decision = check_stage_failure_rate(
                trial_results=trials,
                failure_rate_threshold=0.8,
            )

            assert decision.should_abort is True
            assert decision.reason == AbortReason.CATASTROPHIC_FAILURE_RATE
            assert "9/10" in decision.details
            assert "90" in decision.details  # 90% failure rate
            assert "80" in decision.details  # 80% threshold
            assert len(decision.violating_trials) == 9

        finally:
            Path(yaml_path).unlink()

    def test_step_4_5_failure_rate_within_threshold_no_abort(self) -> None:
        """Steps 4-5: Failure rate within threshold does not abort."""
        # Create trials where 7/10 fail (70% failure rate < 80% threshold)
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(10)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trials = []
        # 7 failures
        for i in range(7):
            trials.append(
                TrialResult(
                    config=trial_configs[i],
                    success=False,
                    return_code=1,
                    metrics=None,
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                )
            )
        # 3 successes
        for i in range(7, 10):
            trials.append(
                TrialResult(
                    config=trial_configs[i],
                    success=True,
                    return_code=0,
                    metrics=TrialMetrics(
                        timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                        congestion=None,
                    ),
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                )
            )

        # Verify no abort (70% < 80%)
        decision = check_stage_failure_rate(
            trial_results=trials,
            failure_rate_threshold=0.8,
        )

        assert decision.should_abort is False
        assert decision.reason is None

    def test_failure_rate_exactly_at_threshold(self) -> None:
        """Test that exactly at threshold does not abort."""
        # Create trials where 8/10 fail (exactly 80% failure rate = 80% threshold)
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(10)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trials = []
        # 8 failures
        for i in range(8):
            trials.append(
                TrialResult(
                    config=trial_configs[i],
                    success=False,
                    return_code=1,
                    metrics=None,
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                )
            )
        # 2 successes
        for i in range(8, 10):
            trials.append(
                TrialResult(
                    config=trial_configs[i],
                    success=True,
                    return_code=0,
                    metrics=TrialMetrics(
                        timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                        congestion=None,
                    ),
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                )
            )

        # At threshold should not abort (not strictly greater)
        decision = check_stage_failure_rate(
            trial_results=trials,
            failure_rate_threshold=0.8,
        )

        assert decision.should_abort is False

    def test_no_threshold_configured_never_aborts(self) -> None:
        """When no failure rate threshold is configured, never abort."""
        # All trials fail
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(10)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trials = [
            TrialResult(
                config=tc,
                success=False,
                return_code=1,
                metrics=None,
                artifacts=artifacts,
                runtime_seconds=50.0,
            )
            for tc in trial_configs
        ]

        # No threshold configured - should not abort
        decision = check_stage_failure_rate(
            trial_results=trials,
            failure_rate_threshold=None,
        )

        assert decision.should_abort is False
        assert decision.reason is None

    def test_empty_trial_list_does_not_abort(self) -> None:
        """Test that empty trial list doesn't trigger abort."""
        decision = check_stage_failure_rate(
            trial_results=[],
            failure_rate_threshold=0.8,
        )

        assert decision.should_abort is False
        assert "No trials executed" in decision.details


class TestF028StudyRailCatastrophicFailureCount:
    """
    Feature #F028: Study rail triggers on catastrophic failure count.

    Steps:
        1. Create study with study rail catastrophic_failures: 3
        2. Trigger 3 catastrophic failures (tool crashes)
        3. Verify study is halted completely
        4. Verify halt reason is logged in study_summary.json
        5. Verify no further trials are executed
    """

    def test_step_1_2_3_catastrophic_count_triggers_study_halt(self) -> None:
        """Steps 1-3: Catastrophic failure count triggers study halt."""
        # Step 1: Create study with study rail catastrophic_failures: 3
        yaml_content = """
name: catastrophic_count_study
safety_domain: guarded
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

rails:
  study:
    catastrophic_failures: 3

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            yaml_path = f.name

        try:
            config = load_study_config(yaml_path)

            # Verify rails configuration is loaded
            assert config.rails.study.catastrophic_failures == 3

            # Step 2: Simulate 3 catastrophic failures (segfaults)
            trial_configs = [
                TrialConfig(
                    study_name="catastrophic_count_study",
                    case_name=f"nangate45_base_{i // 10}_{i}",
                    stage_index=i // 10,
                    trial_index=i,
                    script_path="/tmp/test.tcl",
                    execution_mode=ExecutionMode.STA_ONLY,
                )
                for i in range(5)
            ]
            artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

            # 3 catastrophic failures
            catastrophic_trials = []
            for i in range(3):
                catastrophic_trials.append(
                    TrialResult(
                        config=trial_configs[i],
                        success=False,
                        return_code=139,  # SIGSEGV
                        metrics=None,
                        artifacts=artifacts,
                        runtime_seconds=50.0,
                        failure=FailureClassification(
                            failure_type=FailureType.SEGFAULT,
                            severity=FailureSeverity.CRITICAL,
                            reason="Segmentation fault",
                        ),
                    )
                )

            # 2 successful trials
            for i in range(3, 5):
                catastrophic_trials.append(
                    TrialResult(
                        config=trial_configs[i],
                        success=True,
                        return_code=0,
                        metrics=TrialMetrics(
                            timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                            congestion=None,
                        ),
                        artifacts=artifacts,
                        runtime_seconds=50.0,
                    )
                )

            # Step 3: Verify study is halted after 3 catastrophic failures
            decision = check_study_catastrophic_failure_count(
                all_trial_results=catastrophic_trials,
                max_catastrophic_failures=3,
            )

            assert decision.should_abort is True
            assert decision.reason == AbortReason.CATASTROPHIC_FAILURE_COUNT
            assert decision.catastrophic_count == 3
            assert "3 catastrophic failures" in decision.details
            assert "threshold: 3" in decision.details

        finally:
            Path(yaml_path).unlink()

    def test_step_4_5_below_threshold_study_continues(self) -> None:
        """Steps 4-5: Below threshold, study continues."""
        # Create trials with 2 catastrophic failures (below threshold of 3)
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(5)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trials = []
        # 2 catastrophic failures
        for i in range(2):
            trials.append(
                TrialResult(
                    config=trial_configs[i],
                    success=False,
                    return_code=137,  # OOM killed
                    metrics=None,
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                    failure=FailureClassification(
                        failure_type=FailureType.OOM,
                        severity=FailureSeverity.CRITICAL,
                        reason="Out of memory",
                    ),
                )
            )

        # 3 successful trials
        for i in range(2, 5):
            trials.append(
                TrialResult(
                    config=trial_configs[i],
                    success=True,
                    return_code=0,
                    metrics=TrialMetrics(
                        timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                        congestion=None,
                    ),
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                )
            )

        # Verify study continues (2 < 3)
        decision = check_study_catastrophic_failure_count(
            all_trial_results=trials,
            max_catastrophic_failures=3,
        )

        assert decision.should_abort is False
        assert decision.reason is None
        assert decision.catastrophic_count == 2
        assert "2/3" in decision.details

    def test_exactly_at_threshold_triggers_halt(self) -> None:
        """Test that exactly at threshold triggers halt (>= not >)."""
        # Create trials with exactly 3 catastrophic failures
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(3)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trials = [
            TrialResult(
                config=tc,
                success=False,
                return_code=139,
                metrics=None,
                artifacts=artifacts,
                runtime_seconds=50.0,
                failure=FailureClassification(
                    failure_type=FailureType.SEGFAULT,
                    severity=FailureSeverity.CRITICAL,
                    reason="Segmentation fault",
                ),
            )
            for tc in trial_configs
        ]

        # Exactly at threshold should trigger halt
        decision = check_study_catastrophic_failure_count(
            all_trial_results=trials,
            max_catastrophic_failures=3,
        )

        assert decision.should_abort is True
        assert decision.catastrophic_count == 3

    def test_no_threshold_configured_never_halts(self) -> None:
        """When no threshold is configured, never halt."""
        # Create many catastrophic failures
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(10)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trials = [
            TrialResult(
                config=tc,
                success=False,
                return_code=139,
                metrics=None,
                artifacts=artifacts,
                runtime_seconds=50.0,
                failure=FailureClassification(
                    failure_type=FailureType.SEGFAULT,
                    severity=FailureSeverity.CRITICAL,
                    reason="Segmentation fault",
                ),
            )
            for tc in trial_configs
        ]

        # No threshold configured - should not halt
        decision = check_study_catastrophic_failure_count(
            all_trial_results=trials,
            max_catastrophic_failures=None,
        )

        assert decision.should_abort is False
        assert decision.reason is None

    def test_non_catastrophic_failures_not_counted(self) -> None:
        """Non-catastrophic failures don't count toward threshold."""
        trial_configs = [
            TrialConfig(
                study_name="test_study",
                case_name=f"nangate45_base_0_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )
            for i in range(5)
        ]
        artifacts = TrialArtifacts(trial_dir=Path("/tmp/artifacts"))

        trials = []
        # 1 catastrophic failure
        trials.append(
            TrialResult(
                config=trial_configs[0],
                success=False,
                return_code=139,
                metrics=None,
                artifacts=artifacts,
                runtime_seconds=50.0,
                failure=FailureClassification(
                    failure_type=FailureType.SEGFAULT,
                    severity=FailureSeverity.CRITICAL,
                    reason="Segmentation fault",
                ),
            )
        )

        # 3 non-catastrophic failures (timing violations)
        for i in range(1, 4):
            trials.append(
                TrialResult(
                    config=trial_configs[i],
                    success=False,
                    return_code=1,
                    metrics=None,
                    artifacts=artifacts,
                    runtime_seconds=50.0,
                    failure=FailureClassification(
                        failure_type=FailureType.STA_FAILED,
                        severity=FailureSeverity.MEDIUM,
                        reason="Timing not met",
                    ),
                )
            )

        # 1 success
        trials.append(
            TrialResult(
                config=trial_configs[4],
                success=True,
                return_code=0,
                metrics=TrialMetrics(
                    timing=TimingMetrics(wns_ps=-2000, tns_ps=-5000, failing_endpoints=2),
                    congestion=None,
                ),
                artifacts=artifacts,
                runtime_seconds=50.0,
            )
        )

        # Should not halt (only 1 catastrophic failure, 3 non-catastrophic don't count)
        decision = check_study_catastrophic_failure_count(
            all_trial_results=trials,
            max_catastrophic_failures=3,
        )

        assert decision.should_abort is False
        assert decision.catastrophic_count == 1

    def test_empty_trial_list_does_not_halt(self) -> None:
        """Test that empty trial list doesn't trigger halt."""
        decision = check_study_catastrophic_failure_count(
            all_trial_results=[],
            max_catastrophic_failures=3,
        )

        assert decision.should_abort is False
        assert "No trials executed" in decision.details
        assert decision.catastrophic_count == 0
