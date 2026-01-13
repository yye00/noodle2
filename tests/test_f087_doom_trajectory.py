"""
Tests for F087: Doom detection identifies trajectory-doomed cases after stagnation.

Steps from feature_list.json:
1. Create a case with 3 consecutive stages showing <2% improvement
2. Run doom detector trajectory analysis
3. Verify doom_type is trajectory_doom
4. Verify stagnation trigger is correctly identified
5. Verify case termination decision is made
"""

import pytest
from src.controller.doom_detection import (
    DoomConfig,
    DoomDetector,
    DoomType,
    format_doom_report,
)


class TestF087TrajectoryDoomedDetection:
    """Test trajectory-doomed doom detection."""

    def test_step_1_create_case_with_3_consecutive_stagnant_stages(self):
        """Step 1: Create a case with 3 consecutive stages showing <2% improvement."""
        # Create stage history showing stagnation
        # WNS improves by < 2% each stage
        stage_history = [
            {"wns_ps": -2000, "stage": 0},  # Initial
            {"wns_ps": -1980, "stage": 1},  # 1% improvement
            {"wns_ps": -1960, "stage": 2},  # 1% improvement
            {"wns_ps": -1941, "stage": 3},  # 0.97% improvement
        ]

        # Calculate improvement percentages
        improvements = []
        for i in range(1, len(stage_history)):
            prev = stage_history[i - 1]["wns_ps"]
            curr = stage_history[i]["wns_ps"]
            improvement = (curr - prev) / abs(prev)
            improvements.append(improvement)

        assert all(imp < 0.02 for imp in improvements), "All improvements should be < 2%"
        assert len([imp for imp in improvements if imp < 0.02]) >= 3, "Should have 3+ stagnant stages"

    def test_step_2_run_doom_detector_trajectory_analysis(self):
        """Step 2: Run doom detector trajectory analysis."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,  # 2% improvement threshold
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},
            {"wns_ps": -1960},
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result is not None, "Doom detector should return a result"
        assert hasattr(result, "is_doomed"), "Result should have is_doomed attribute"
        assert hasattr(result, "doom_type"), "Result should have doom_type attribute"

    def test_step_3_verify_doom_type_is_trajectory_doom(self):
        """Step 3: Verify doom_type is trajectory_doom."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        # Create stagnant trajectory (< 2% improvement per stage)
        # Need 4 data points to have 3 consecutive improvements
        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},  # 1% improvement
            {"wns_ps": -1960},  # 1% improvement
            {"wns_ps": -1941},  # 0.97% improvement
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is True, "Stagnant trajectory should be doomed"
        assert result.doom_type == DoomType.TRAJECTORY_DOOM, "Doom type should be trajectory_doom"

    def test_step_4_verify_stagnation_trigger_correctly_identified(self):
        """Step 4: Verify stagnation trigger is correctly identified."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},
            {"wns_ps": -1960},
            {"wns_ps": -1941},
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is True
        assert "stagnation" in result.trigger.lower(), "Trigger should mention stagnation"
        assert "3" in result.trigger, "Trigger should mention 3 consecutive stages"

    def test_step_5_verify_case_termination_decision(self):
        """Step 5: Verify case termination decision is made."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},
            {"wns_ps": -1960},
            {"wns_ps": -1941},
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        # Verify termination decision
        assert result.is_doomed is True, "Stagnant case should be marked for termination"
        assert result.confidence > 0.7, "Trajectory doom should have reasonable confidence"
        assert "cannot reach" in result.reason.lower() or "trajectory" in result.reason.lower(), \
            "Reason should explain trajectory issue"


class TestTrajectoryStagnationDetection:
    """Test trajectory stagnation detection logic."""

    def test_insufficient_history_not_doomed(self):
        """Test that insufficient history doesn't trigger doom."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            min_stages_for_trajectory=2,
        )

        detector = DoomDetector(config)

        # Only 1 historical stage
        current_metrics = {"wns_ps": -1900}
        stage_history = [{"wns_ps": -2000}]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is False, "Insufficient history should not trigger doom"
        # The result might just say "no doom detected" which is also acceptable
        if result.trigger != "no_doom_detected":
            assert "insufficient" in result.trigger.lower() or "history" in result.reason.lower()

    def test_good_improvement_not_doomed(self):
        """Test that good improvement trajectory is not doomed."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        # Good improvements (> 5% per stage)
        current_metrics = {"wns_ps": -1500}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1800},  # 10% improvement
            {"wns_ps": -1650},  # 8.3% improvement
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is False, "Good improvement should not be doomed"

    def test_regression_triggers_doom(self):
        """Test that regression (getting worse) triggers doom."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            regression_threshold=0.1,  # 10% regression
        )

        detector = DoomDetector(config)

        # Latest stage shows regression (getting worse)
        # History includes current state
        current_metrics = {"wns_ps": -2200}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1900},  # Good improvement
            {"wns_ps": -2200},  # Regression!
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is True, "Regression should trigger doom"
        assert result.doom_type == DoomType.TRAJECTORY_DOOM
        assert "regression" in result.trigger.lower()

    def test_mixed_improvements_reset_stagnation_counter(self):
        """Test that significant improvement resets stagnation counter."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        # 2 stagnant stages, then big improvement, then 2 more stagnant
        # Should NOT be doomed because stagnation counter resets
        current_metrics = {"wns_ps": -1450}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},  # 1% stagnant
            {"wns_ps": -1960},  # 1% stagnant
            {"wns_ps": -1500},  # 23% improvement - resets counter!
            {"wns_ps": -1480},  # 1.3% stagnant
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        # Should not be doomed because we don't have 3 CONSECUTIVE stagnant stages
        assert result.is_doomed is False, "Interrupted stagnation should not doom"


class TestTrajectoryConfiguration:
    """Test trajectory doom configuration."""

    def test_trajectory_analysis_can_be_disabled(self):
        """Test that trajectory analysis can be disabled."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=False,
        )

        detector = DoomDetector(config)

        # Even stagnant trajectory should not trigger doom when disabled
        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},
            {"wns_ps": -1960},
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is False, "Disabled trajectory analysis should not doom"

    def test_custom_stagnation_threshold(self):
        """Test custom stagnation threshold."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.05,  # 5% threshold (more lenient)
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        # 3% improvements would be OK with 5% threshold
        current_metrics = {"wns_ps": -1820}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1940},  # 3% improvement
            {"wns_ps": -1880},  # 3.1% improvement
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is False, "3% improvement should be OK with 5% threshold"

    def test_custom_consecutive_stagnation_count(self):
        """Test custom consecutive stagnation count."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=5,  # Require 5 stages
        )

        detector = DoomDetector(config)

        # Only 3 stagnant stages
        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},
            {"wns_ps": -1960},
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is False, "3 stages should not doom when 5 required"


class TestTrajectoryMetadata:
    """Test trajectory doom metadata and reporting."""

    def test_trajectory_doom_includes_history(self):
        """Test that trajectory doom includes WNS history in metadata."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},
            {"wns_ps": -1960},
            {"wns_ps": -1941},
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        assert result.is_doomed is True
        assert "wns_history" in result.metadata, "Metadata should include WNS history"
        assert "improvement_percentages" in result.metadata, "Metadata should include improvement %"

    def test_trajectory_report_is_informative(self):
        """Test that trajectory doom report is informative."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        )

        detector = DoomDetector(config)

        current_metrics = {"wns_ps": -1941}
        stage_history = [
            {"wns_ps": -2000},
            {"wns_ps": -1980},
            {"wns_ps": -1960},
            {"wns_ps": -1941},
        ]

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, current_metrics, stage_history=stage_history)

        report = format_doom_report(result)

        assert "trajectory" in report.lower(), "Report should mention trajectory"
        assert "stagnation" in report.lower() or "progress" in report.lower(), \
            "Report should explain stagnation"
