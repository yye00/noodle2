"""Tests for F038: Trial failure classification works for metric regressions."""

import pytest

from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)


class TestMetricRegressionClassification:
    """Test metric regression detection and classification."""

    def test_classify_metric_regression_creates_correct_classification(self):
        """Test that classify_metric_regression creates correct classification."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION
        assert classification.severity == FailureSeverity.MEDIUM

    def test_metric_regression_includes_metric_name(self):
        """Test that metric regression includes the metric name."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert classification is not None
        assert "wns_ps" in classification.reason

    def test_metric_regression_includes_baseline_and_current_values(self):
        """Test that metric regression includes baseline and current values."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert classification is not None
        assert "-500" in classification.reason
        assert "-2000" in classification.reason

    def test_metric_regression_calculates_percentage_change(self):
        """Test that metric regression calculates percentage change."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-100,
            current_value=-150,
        )

        assert classification is not None
        # 50% worse
        assert classification.metrics is not None
        assert "percent_change" in classification.metrics
        assert classification.metrics["percent_change"] == pytest.approx(50.0, abs=0.1)

    def test_metric_regression_severity_is_medium(self):
        """Test that metric regressions have MEDIUM severity."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert classification is not None
        assert classification.severity == FailureSeverity.MEDIUM

    def test_metric_regression_is_recoverable(self):
        """Test that metric regressions are marked as recoverable."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert classification is not None
        assert classification.recoverable is True


class TestMetricRegressionScenarios:
    """Test specific metric regression scenarios."""

    def test_wns_regression(self):
        """Test WNS (Worst Negative Slack) regression."""
        # Baseline: -500 ps (small violation)
        # After ECO: -5000 ps (large violation) - significantly worse
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-5000,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION
        assert "wns_ps" in classification.reason

    def test_tns_regression(self):
        """Test TNS (Total Negative Slack) regression."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="tns_ps",
            baseline_value=-1000,
            current_value=-10000,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION

    def test_congestion_regression(self):
        """Test congestion score regression."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="hot_ratio",
            baseline_value=0.1,
            current_value=0.8,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION

    def test_power_regression(self):
        """Test power consumption regression."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="total_power_mw",
            baseline_value=100.0,
            current_value=500.0,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION


class TestMetricRegressionDeltaLogging:
    """Test delta metrics logging for regressions."""

    def test_delta_metrics_are_logged(self):
        """Test that delta metrics are included in classification."""
        delta_metrics = {
            "wns_ps": {"baseline": -500, "current": -2000, "delta": -1500},
            "tns_ps": {"baseline": -1000, "current": -5000, "delta": -4000},
        }

        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
            delta_metrics=delta_metrics,
        )

        assert classification is not None
        assert classification.metrics is not None
        assert classification.metrics == delta_metrics

    def test_default_delta_metrics_if_not_provided(self):
        """Test that default delta metrics are created if not provided."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert classification is not None
        assert classification.metrics is not None
        assert "metric_name" in classification.metrics
        assert "baseline_value" in classification.metrics
        assert "current_value" in classification.metrics
        assert "percent_change" in classification.metrics

    def test_metrics_can_be_serialized(self):
        """Test that metric regression with delta can be serialized."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
            delta_metrics={
                "wns_delta": -1500,
                "tns_delta": -3000,
            },
        )

        # Serialize to dict
        data = classification.to_dict()

        assert isinstance(data, dict)
        assert data["failure_type"] == "metric_regression"
        assert data["severity"] == "medium"
        assert "metrics" in data
        assert isinstance(data["metrics"], dict)


class TestFeatureStepValidation:
    """Validate all steps from feature F038."""

    def test_step1_run_eco_that_makes_wns_significantly_worse(self):
        """Step 1: Run ECO that makes WNS significantly worse.

        This simulates running an ECO (e.g., aggressive buffer insertion)
        that makes WNS much worse than the baseline.
        """
        # Baseline: -500 ps (small violation)
        baseline_wns = -500

        # After bad ECO: -8000 ps (very large violation)
        current_wns = -8000

        # This ECO made things significantly worse
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=baseline_wns,
            current_value=current_wns,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION

    def test_step2_verify_failure_type_is_metric_regression(self):
        """Step 2: Verify failure type is classified as 'metric_regression'."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-5000,
        )

        assert classification is not None
        # Verify failure_type is exactly METRIC_REGRESSION
        assert classification.failure_type == FailureType.METRIC_REGRESSION
        assert classification.failure_type.value == "metric_regression"

    def test_step3_verify_severity_is_medium(self):
        """Step 3: Verify severity is 'medium'."""
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-5000,
        )

        assert classification is not None
        assert classification.severity == FailureSeverity.MEDIUM
        assert classification.severity.value == "medium"

    def test_step4_verify_delta_metrics_are_logged(self):
        """Step 4: Verify delta metrics are logged."""
        # Create detailed delta metrics
        delta_metrics = {
            "wns_ps": {
                "baseline": -500,
                "current": -5000,
                "delta": -4500,
            },
            "tns_ps": {
                "baseline": -1000,
                "current": -10000,
                "delta": -9000,
            },
            "failing_endpoints": {
                "baseline": 10,
                "current": 50,
                "delta": 40,
            },
        }

        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-5000,
            delta_metrics=delta_metrics,
        )

        assert classification is not None
        assert classification.metrics is not None

        # Verify delta metrics are preserved
        assert classification.metrics == delta_metrics

        # Verify can be serialized (for logging)
        data = classification.to_dict()
        assert "metrics" in data
        assert data["metrics"] == delta_metrics


class TestMetricRegressionVsOtherFailures:
    """Test distinction between metric regressions and other failures."""

    def test_metric_regression_vs_tool_crash(self):
        """Test that metric regressions are distinct from tool crashes."""
        # Metric regression
        regression = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert regression.failure_type == FailureType.METRIC_REGRESSION
        assert regression.failure_type != FailureType.TOOL_CRASH

    def test_metric_regression_vs_parse_failure(self):
        """Test that metric regressions are distinct from parse failures."""
        # Metric regression
        regression = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        # Parse failure
        from pathlib import Path

        parse_fail = FailureClassifier.classify_parse_failure(
            file_path=Path("/tmp/file.txt"),
            error_message="Parse error",
        )

        assert regression.failure_type != parse_fail.failure_type

    def test_metric_regression_has_medium_severity(self):
        """Test that metric regressions have MEDIUM severity.

        This is different from tool crashes (HIGH) and parse failures (HIGH).
        Medium severity means it's recoverable and worth trying different ECOs.
        """
        regression = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-2000,
        )

        assert regression.severity == FailureSeverity.MEDIUM
        # Should be recoverable (can try different ECOs)
        assert regression.recoverable is True


class TestRealWorldMetricRegressions:
    """Test real-world metric regression scenarios."""

    def test_aggressive_eco_makes_timing_worse(self):
        """Test aggressive ECO that helps congestion but hurts timing."""
        # Scenario: Added too many buffers, helped congestion but hurt timing
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-200,  # Small violation
            current_value=-3000,  # Much worse
            delta_metrics={
                "wns_ps": {"baseline": -200, "current": -3000, "delta": -2800},
                "hot_ratio": {"baseline": 0.5, "current": 0.3, "delta": -0.2},  # Improved
            },
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION
        assert classification.severity == FailureSeverity.MEDIUM

    def test_small_regression_still_classified(self):
        """Test that even small but significant regressions are classified."""
        # 30% regression should be classified
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-1000,
            current_value=-1300,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION

    def test_large_regression_still_medium_severity(self):
        """Test that even large regressions stay MEDIUM severity.

        Metric regressions are recoverable (can try different ECOs),
        so they don't escalate to HIGH or CRITICAL severity.
        """
        # 10x regression
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=-500,
            current_value=-5000,
        )

        assert classification is not None
        assert classification.severity == FailureSeverity.MEDIUM
        # Still recoverable - can try different approach
        assert classification.recoverable is True

    def test_zero_baseline_handled_correctly(self):
        """Test that zero baseline values are handled correctly."""
        # Baseline was 0 (no violations), now has violations
        classification = FailureClassifier.classify_metric_regression(
            metric_name="wns_ps",
            baseline_value=0,
            current_value=-1000,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.METRIC_REGRESSION
        # Should treat as 100% change
        assert classification.metrics["percent_change"] == 100.0
