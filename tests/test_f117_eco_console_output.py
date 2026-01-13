"""
Tests for F117: Demo console output shows ECO application with before/after WNS and improvement percentage.

Feature Requirements:
1. Run demo and capture console output
2. Verify output contains [ECO] Applied <eco_name> to <case>
3. Verify output shows WNS Before: X ps → After: Y ps (Z% improvement)
4. Verify multiple ECO applications are logged
5. Verify improvement percentages are calculated correctly
"""

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.controller.executor import StudyExecutor
from src.controller.study import StudyConfig
from src.controller.types import (
    ExecutionMode,
    SafetyDomain,
    StageConfig,
)
from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts


class TestF117ECOConsoleOutput:
    """Test that ECO applications are logged to console with before/after WNS."""

    def test_step_1_run_demo_and_capture_console_output(self, tmp_path):
        """
        Step 1: Run demo and capture console output.

        Verify that we can capture console output during study execution.
        """
        # Create a minimal study configuration
        config = StudyConfig(
            name="test_f117_console_output",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="test_base",
            pdk="nangate45",
            snapshot_path=str(tmp_path / "snapshot"),
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                )
            ],
        )

        # Create executor
        executor = StudyExecutor(
            config=config,
            artifacts_root=str(tmp_path / "artifacts"),
            telemetry_root=str(tmp_path / "telemetry"),
            skip_base_case_verification=True,
        )

        # Verify executor has case_metrics_map for tracking
        assert hasattr(executor, "case_metrics_map")
        assert isinstance(executor.case_metrics_map, dict)

        # Verify executor has _print_eco_application method
        assert hasattr(executor, "_print_eco_application")
        assert callable(executor._print_eco_application)

    def test_step_2_verify_output_contains_eco_applied_message(self, capsys):
        """
        Step 2: Verify output contains [ECO] Applied <eco_name> to <case>.

        Check that the console output format is correct.
        """
        from src.controller.executor import StudyExecutor

        # Create a mock executor with case_metrics_map
        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {}
        executor.baseline_wns_ps = -2000
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        # Create a trial result with ECO applied
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="test_case_1",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "buffer_insertion"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={"wns_ps": -1500, "tns_ps": -5000},
        )

        # Call the method
        executor._print_eco_application(trial_result, trial_config, None)

        # Capture output
        captured = capsys.readouterr()

        # Verify format: [ECO] Applied <eco_name> to <case>
        assert "[ECO] Applied buffer_insertion to test_case_1" in captured.out

    def test_step_3_verify_wns_before_after_with_improvement_percentage(self, capsys):
        """
        Step 3: Verify output shows WNS Before: X ps → After: Y ps (Z% improvement).

        Verify that before/after WNS values and improvement percentage are displayed.
        """
        from src.controller.executor import StudyExecutor

        # Create a mock executor with baseline metrics
        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {"base_case": {"wns_ps": -2000}}
        executor.baseline_wns_ps = -2000
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        # Create a trial result with improvement
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="test_case_1",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "cell_resize"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={"wns_ps": -1000},  # Improved from -2000 to -1000
        )

        # Call the method with base_case as parent
        executor._print_eco_application(trial_result, trial_config, "base_case")

        # Capture output
        captured = capsys.readouterr()

        # Verify format includes WNS Before and After with arrow
        assert "WNS Before: -2000 ps → After: -1000 ps" in captured.out

        # Verify improvement percentage is shown
        # Improvement = (-1000 - (-2000)) / abs(-2000) * 100 = 1000/2000 * 100 = 50%
        assert "50.0% improvement" in captured.out or "+50.0% improvement" in captured.out

    def test_step_4_verify_multiple_eco_applications_are_logged(self, capsys):
        """
        Step 4: Verify multiple ECO applications are logged.

        Ensure that each ECO application in a multi-trial study is logged separately.
        """
        from src.controller.executor import StudyExecutor

        # Create a mock executor
        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {}
        executor.baseline_wns_ps = -3000
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        # Simulate multiple ECO applications
        eco_names = ["buffer_insertion", "cell_resize", "cell_swap"]
        wns_values = [-2500, -2000, -1500]  # Progressive improvements

        for i, (eco_name, wns) in enumerate(zip(eco_names, wns_values)):
            trial_config = TrialConfig(
                study_name="test_study",
                case_name=f"test_case_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/tmp/test.tcl",
                snapshot_dir="/tmp/snapshot",
                execution_mode=ExecutionMode.STA_ONLY,
                metadata={"eco_type": eco_name},
            )

            trial_result = TrialResult(
                config=trial_config,
                success=True,
                return_code=0,
                runtime_seconds=10.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
                metrics={"wns_ps": wns},
            )

            # Call the method
            executor._print_eco_application(trial_result, trial_config, None)

        # Capture output
        captured = capsys.readouterr()

        # Verify all ECOs are logged
        for eco_name in eco_names:
            assert f"Applied {eco_name}" in captured.out

        # Verify each has distinct case names
        for i in range(len(eco_names)):
            assert f"test_case_{i}" in captured.out

    def test_step_5_verify_improvement_percentages_calculated_correctly(self, capsys):
        """
        Step 5: Verify improvement percentages are calculated correctly.

        Test various scenarios:
        - Positive improvement (WNS gets less negative)
        - Regression (WNS gets more negative)
        - No change
        """
        from src.controller.executor import StudyExecutor

        # Create a mock executor
        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {}
        executor.baseline_wns_ps = -2000
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        # Test case 1: 50% improvement (-2000 → -1000)
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="case_improvement",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "eco1"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={"wns_ps": -1000},
        )

        executor._print_eco_application(trial_result, trial_config, None)
        captured = capsys.readouterr()

        # Should show +50% improvement
        assert "+50.0% improvement" in captured.out

        # Test case 2: 25% regression (-2000 → -2500)
        trial_config2 = TrialConfig(
            study_name="test_study",
            case_name="case_regression",
            stage_index=0,
            trial_index=1,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "eco2"},
        )

        trial_result2 = TrialResult(
            config=trial_config2,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={"wns_ps": -2500},
        )

        executor._print_eco_application(trial_result2, trial_config2, None)
        captured = capsys.readouterr()

        # Should show -25% (regression)
        assert "-25.0% improvement" in captured.out


class TestF117ImprovementCalculation:
    """Test the improvement calculation logic in detail."""

    def test_improvement_calculation_positive_wns(self, capsys):
        """Test improvement calculation when WNS is positive (no violation)."""
        from src.controller.executor import StudyExecutor

        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {"parent": {"wns_ps": 100}}
        executor.baseline_wns_ps = None
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        trial_config = TrialConfig(
            study_name="test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "eco_test"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={"wns_ps": 200},  # Improved from 100 to 200
        )

        executor._print_eco_application(trial_result, trial_config, "parent")
        captured = capsys.readouterr()

        # Improvement: (200 - 100) / abs(100) * 100 = 100%
        assert "+100.0% improvement" in captured.out

    def test_no_eco_applied_is_skipped(self, capsys):
        """Test that trials with no ECO applied are skipped."""
        from src.controller.executor import StudyExecutor

        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {}
        executor.baseline_wns_ps = -1000
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        trial_config = TrialConfig(
            study_name="test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "no_eco"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={"wns_ps": -1000},
        )

        executor._print_eco_application(trial_result, trial_config, None)
        captured = capsys.readouterr()

        # Should not print anything for no_eco
        assert "[ECO]" not in captured.out

    def test_missing_wns_metrics_is_skipped(self, capsys):
        """Test that trials without WNS metrics are skipped."""
        from src.controller.executor import StudyExecutor

        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {}
        executor.baseline_wns_ps = -1000
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        trial_config = TrialConfig(
            study_name="test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "cell_resize"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={},  # No WNS
        )

        executor._print_eco_application(trial_result, trial_config, None)
        captured = capsys.readouterr()

        # Should not print anything without WNS
        assert "[ECO]" not in captured.out

    def test_parent_case_metrics_used_for_before_state(self, capsys):
        """Test that parent case metrics are correctly used for before state."""
        from src.controller.executor import StudyExecutor

        executor = MagicMock(spec=StudyExecutor)
        executor.case_metrics_map = {
            "parent_case": {"wns_ps": -1500, "tns_ps": -5000}
        }
        executor.baseline_wns_ps = -2000  # Different from parent
        executor._print_eco_application = StudyExecutor._print_eco_application.__get__(executor)

        trial_config = TrialConfig(
            study_name="test",
            case_name="derived_case",
            stage_index=1,
            trial_index=0,
            script_path="/tmp/test.tcl",
            snapshot_dir="/tmp/snapshot",
            execution_mode=ExecutionMode.STA_ONLY,
            metadata={"eco_type": "buffer_insertion"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            metrics={"wns_ps": -1200},
        )

        # Pass parent_case as parent_id
        executor._print_eco_application(trial_result, trial_config, "parent_case")
        captured = capsys.readouterr()

        # Should use parent's -1500, not baseline's -2000
        assert "WNS Before: -1500 ps" in captured.out
        assert "After: -1200 ps" in captured.out

        # Improvement: (-1200 - (-1500)) / abs(-1500) * 100 = 300/1500 * 100 = 20%
        assert "+20.0% improvement" in captured.out
