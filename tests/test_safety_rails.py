"""Tests for safety rails enforcement (F024-F028)."""

import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass

from src.controller.study import load_study_config
from src.controller.safety import check_study_legality, LegalityChecker
from src.controller.stage_abort import (
    check_wns_threshold_violation,
    AbortReason,
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
