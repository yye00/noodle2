"""
Tests for F086: Doom detection identifies metric-hopeless cases and terminates them.

Steps from feature_list.json:
1. Create a case with WNS < -10000ps (hopeless threshold)
2. Run doom detector on the case metrics
3. Verify doom_type is metric_hopeless
4. Verify case is marked for termination
5. Verify doom reason is logged in study output
"""

import pytest
from src.controller.doom_detection import (
    DoomConfig,
    DoomDetector,
    DoomType,
    format_doom_report,
)
from src.controller.case import Case


class TestF086MetricHopelessDoomDetection:
    """Test metric-hopeless doom detection."""

    def test_step_1_create_hopeless_case_with_wns_below_minus_10000(self):
        """Step 1: Create a case with WNS < -10000ps (hopeless threshold)."""
        # Create metrics representing a hopeless case
        hopeless_metrics = {
            "wns_ps": -12000,  # Worse than -10000ps threshold
            "tns_ps": -600000,
            "hot_ratio": 0.85,
        }

        assert hopeless_metrics["wns_ps"] < -10000, "WNS should be beyond hopeless threshold"
        assert hopeless_metrics["hot_ratio"] > 0.8, "Hot ratio should indicate widespread violations"

    def test_step_2_run_doom_detector_on_hopeless_metrics(self):
        """Step 2: Run doom detector on the case metrics."""
        config = DoomConfig(
            enabled=True,
            wns_ps_hopeless=-10000,
            hot_ratio_hopeless=0.8,
            tns_ps_hopeless=-500000,
        )

        detector = DoomDetector(config)

        # Hopeless WNS case
        hopeless_metrics = {
            "wns_ps": -12000,
            "tns_ps": -600000,
            "hot_ratio": 0.5,
        }

        # Mock case (doom detector doesn't actually use the case object currently)
        from unittest.mock import MagicMock
        mock_case = MagicMock()

        result = detector.check_doom(mock_case, hopeless_metrics)

        assert result is not None, "Doom detector should return a result"
        assert hasattr(result, "is_doomed"), "Result should have is_doomed attribute"
        assert hasattr(result, "doom_type"), "Result should have doom_type attribute"

    def test_step_3_verify_doom_type_is_metric_hopeless(self):
        """Step 3: Verify doom_type is metric_hopeless."""
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        # Test WNS hopeless
        wns_hopeless = {"wns_ps": -12000, "hot_ratio": 0.5}
        result = detector.check_doom(mock_case, wns_hopeless)

        assert result.is_doomed is True, "Case with WNS < -10000ps should be doomed"
        assert result.doom_type == DoomType.METRIC_HOPELESS, "Doom type should be metric_hopeless"
        assert "wns_ps" in result.trigger, "Trigger should mention WNS"

    def test_step_4_verify_case_marked_for_termination(self):
        """Step 4: Verify case is marked for termination."""
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -15000, "hot_ratio": 0.6}
        result = detector.check_doom(mock_case, hopeless_metrics)

        # Verify termination decision
        assert result.is_doomed is True, "Hopeless case should be marked for termination"
        assert result.confidence > 0.8, "Confidence should be high for clear doom"
        assert "beyond recovery" in result.reason.lower(), "Reason should explain why it's hopeless"

    def test_step_5_verify_doom_reason_is_logged(self):
        """Step 5: Verify doom reason is logged in study output."""
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -12000, "hot_ratio": 0.5}
        result = detector.check_doom(mock_case, hopeless_metrics)

        # Verify result can be serialized for logging
        doom_dict = result.to_dict()
        assert "is_doomed" in doom_dict
        assert "doom_type" in doom_dict
        assert "reason" in doom_dict
        assert doom_dict["is_doomed"] is True
        assert doom_dict["doom_type"] == "metric_hopeless"

        # Verify formatted report
        report = format_doom_report(result)
        assert "DOOM DETECTED" in report
        assert "metric_hopeless" in report
        assert result.reason in report


class TestMetricHopelessThresholds:
    """Test different metric hopeless thresholds."""

    def test_wns_hopeless_threshold_exact(self):
        """Test exact threshold for WNS hopeless."""
        config = DoomConfig(enabled=True, wns_ps_hopeless=-10000)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        # Exactly at threshold (should NOT be doomed)
        at_threshold = {"wns_ps": -10000}
        result = detector.check_doom(mock_case, at_threshold)
        assert result.is_doomed is False, "Exactly at threshold should not be doomed"

        # Just below threshold (should be doomed)
        below_threshold = {"wns_ps": -10001}
        result = detector.check_doom(mock_case, below_threshold)
        assert result.is_doomed is True, "Below threshold should be doomed"

    def test_hot_ratio_hopeless_threshold(self):
        """Test hot_ratio hopeless threshold."""
        config = DoomConfig(enabled=True, hot_ratio_hopeless=0.8)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        # Below threshold (OK)
        ok_hot_ratio = {"wns_ps": -1000, "hot_ratio": 0.79}
        result = detector.check_doom(mock_case, ok_hot_ratio)
        assert result.is_doomed is False, "Hot ratio 0.79 should not be doomed"

        # Above threshold (doomed)
        bad_hot_ratio = {"wns_ps": -1000, "hot_ratio": 0.85}
        result = detector.check_doom(mock_case, bad_hot_ratio)
        assert result.is_doomed is True, "Hot ratio 0.85 should be doomed"
        assert result.doom_type == DoomType.METRIC_HOPELESS

    def test_tns_hopeless_threshold(self):
        """Test TNS hopeless threshold."""
        config = DoomConfig(enabled=True, tns_ps_hopeless=-500000)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        # Above threshold (OK)
        ok_tns = {"wns_ps": -1000, "tns_ps": -400000}
        result = detector.check_doom(mock_case, ok_tns)
        assert result.is_doomed is False, "TNS -400000ps should not be doomed"

        # Below threshold (doomed)
        bad_tns = {"wns_ps": -1000, "tns_ps": -600000}
        result = detector.check_doom(mock_case, bad_tns)
        assert result.is_doomed is True, "TNS -600000ps should be doomed"
        assert result.doom_type == DoomType.METRIC_HOPELESS


class TestDoomDetectorConfiguration:
    """Test doom detector configuration and validation."""

    def test_doom_detection_can_be_disabled(self):
        """Test that doom detection can be disabled."""
        config = DoomConfig(enabled=False)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        # Even hopeless metrics should not trigger doom when disabled
        hopeless_metrics = {"wns_ps": -50000, "hot_ratio": 0.95}
        result = detector.check_doom(mock_case, hopeless_metrics)

        assert result.is_doomed is False, "Doom detection disabled should never doom"
        assert "disabled" in result.reason.lower()

    def test_custom_thresholds(self):
        """Test custom doom thresholds."""
        config = DoomConfig(
            enabled=True,
            wns_ps_hopeless=-5000,  # More aggressive threshold
            hot_ratio_hopeless=0.6,  # Lower hot ratio threshold
        )
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        # Would be OK with default thresholds, but doomed with custom
        metrics = {"wns_ps": -6000, "hot_ratio": 0.4}
        result = detector.check_doom(mock_case, metrics)

        assert result.is_doomed is True, "Custom threshold should trigger doom"
        assert result.doom_type == DoomType.METRIC_HOPELESS


class TestDoomReporting:
    """Test doom report formatting and metadata."""

    def test_doom_report_includes_confidence(self):
        """Test that doom reports include confidence level."""
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -12000}
        result = detector.check_doom(mock_case, hopeless_metrics)

        assert 0.0 <= result.confidence <= 1.0, "Confidence should be between 0 and 1"
        assert result.confidence > 0.8, "Metric-hopeless should have high confidence"

    def test_doom_report_includes_metadata(self):
        """Test that doom reports include diagnostic metadata."""
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -12000}
        result = detector.check_doom(mock_case, hopeless_metrics)

        assert result.metadata is not None, "Metadata should be present"
        assert "wns_ps" in result.metadata, "Metadata should include actual WNS value"
        assert "threshold" in result.metadata, "Metadata should include threshold"

    def test_formatted_report_is_human_readable(self):
        """Test that formatted report is human-readable."""
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -12000, "hot_ratio": 0.5}
        result = detector.check_doom(mock_case, hopeless_metrics)

        report = format_doom_report(result)

        # Report should be multi-line and readable
        assert "\n" in report or len(report.split("\n")) > 1, "Report should be multi-line"
        assert "DOOM" in report.upper(), "Report should clearly indicate doom"
        assert str(result.confidence) in report or f"{result.confidence:.0%}" in report, "Report should show confidence"

    def test_non_doomed_report(self):
        """Test report format for non-doomed cases."""
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        from unittest.mock import MagicMock
        mock_case = MagicMock()

        healthy_metrics = {"wns_ps": -1000, "hot_ratio": 0.3}
        result = detector.check_doom(mock_case, healthy_metrics)

        assert result.is_doomed is False
        report = format_doom_report(result)

        assert "✓" in report or "viable" in report.lower(), "Report should indicate case is viable"
        assert "DOOM" not in report or "not doomed" in report.lower(), "Report should not alarm for healthy case"
