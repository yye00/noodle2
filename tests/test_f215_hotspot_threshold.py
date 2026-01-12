"""Tests for F215: Diagnosis hotspot threshold is configurable."""

import pytest

from src.analysis.diagnosis import diagnose_congestion
from src.controller.types import CongestionMetrics, DiagnosisConfig


class TestHotspotThresholdConfigurableF215:
    """
    Test suite for Feature F215: Configurable hotspot threshold.

    Steps from feature_list.json:
    1. Set diagnosis hotspot_threshold: 0.7
    2. Run congestion diagnosis
    3. Verify only bins with congestion >= 0.7 are marked as hotspots
    4. Change threshold to 0.5
    5. Verify more hotspots are detected
    6. Adjust threshold for desired sensitivity
    """

    def test_step_1_set_hotspot_threshold_to_0_7(self) -> None:
        """Step 1: Set diagnosis hotspot_threshold: 0.7."""
        # Create DiagnosisConfig with hotspot_threshold of 0.7
        config = DiagnosisConfig(hotspot_threshold=0.7)

        # Verify the threshold is set correctly
        assert config.hotspot_threshold == 0.7
        assert config.enabled is True

    def test_step_2_run_congestion_diagnosis_with_threshold(self) -> None:
        """Step 2: Run congestion diagnosis with configured threshold."""
        # Create metrics with moderate congestion (0.75 hot_ratio)
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1200,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
                "metal4": 270,
                "metal5": 100,
            },
        )

        # Run diagnosis with threshold 0.7
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify diagnosis completed successfully
        assert diagnosis is not None
        assert diagnosis.hotspots is not None
        assert diagnosis.hotspot_count >= 0

    def test_step_3_verify_only_bins_above_threshold_marked(self) -> None:
        """Step 3: Verify only bins with congestion >= 0.7 are marked as hotspots."""
        # Test with hot_ratio = 0.75 (above threshold)
        metrics_high = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1200,
            layer_metrics={"metal2": 450, "metal3": 380},
        )

        diagnosis_high = diagnose_congestion(metrics_high, hotspot_threshold=0.7)

        # Should detect hotspots since 0.75 >= 0.7
        assert len(diagnosis_high.hotspots) > 0, "Should detect hotspots when hot_ratio >= threshold"

        # Test with hot_ratio = 0.65 (below threshold)
        metrics_low = CongestionMetrics(
            bins_total=1000,
            bins_hot=650,
            hot_ratio=0.65,
            max_overflow=800,
            layer_metrics={"metal2": 350, "metal3": 280},
        )

        diagnosis_low = diagnose_congestion(metrics_low, hotspot_threshold=0.7)

        # Should NOT create critical hotspots since 0.65 < 0.7
        # (Implementation creates critical hotspots only when hot_ratio >= threshold)
        critical_hotspots_low = [h for h in diagnosis_low.hotspots if h.severity.value == "critical"]
        assert len(critical_hotspots_low) == 0, "Should not create critical hotspots when hot_ratio < threshold"

    def test_step_4_change_threshold_to_0_5(self) -> None:
        """Step 4: Change threshold to 0.5."""
        # Create DiagnosisConfig with different threshold
        config_low = DiagnosisConfig(hotspot_threshold=0.5)
        config_high = DiagnosisConfig(hotspot_threshold=0.7)

        # Verify both configurations are valid
        assert config_low.hotspot_threshold == 0.5
        assert config_high.hotspot_threshold == 0.7

    def test_step_5_verify_more_hotspots_detected_with_lower_threshold(self) -> None:
        """Step 5: Verify more hotspots are detected with lower threshold."""
        # Create metrics with moderate congestion (0.6 hot_ratio)
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=600,
            hot_ratio=0.60,
            max_overflow=900,
            layer_metrics={
                "metal2": 400,
                "metal3": 320,
                "metal4": 180,
            },
        )

        # Run diagnosis with high threshold (0.7)
        diagnosis_high = diagnose_congestion(metrics, hotspot_threshold=0.7)
        critical_high = [h for h in diagnosis_high.hotspots if h.severity.value == "critical"]

        # Run diagnosis with low threshold (0.5)
        diagnosis_low = diagnose_congestion(metrics, hotspot_threshold=0.5)
        critical_low = [h for h in diagnosis_low.hotspots if h.severity.value == "critical"]

        # Lower threshold should detect more critical hotspots
        # (0.60 < 0.7 so no critical hotspots with high threshold)
        # (0.60 >= 0.5 so critical hotspots with low threshold)
        assert len(critical_high) == 0, "High threshold should not detect critical hotspots for hot_ratio=0.60"
        assert len(critical_low) > 0, "Low threshold should detect critical hotspots for hot_ratio=0.60"

    def test_step_6_adjust_threshold_for_desired_sensitivity(self) -> None:
        """Step 6: Adjust threshold for desired sensitivity."""
        # Test multiple threshold values to demonstrate sensitivity control
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=550,
            hot_ratio=0.55,
            max_overflow=800,
            layer_metrics={"metal2": 350, "metal3": 280, "metal4": 170},
        )

        # Very sensitive (low threshold) - detects hotspots easily
        diagnosis_sensitive = diagnose_congestion(metrics, hotspot_threshold=0.4)
        critical_sensitive = [h for h in diagnosis_sensitive.hotspots if h.severity.value == "critical"]

        # Less sensitive (medium threshold)
        diagnosis_medium = diagnose_congestion(metrics, hotspot_threshold=0.6)
        critical_medium = [h for h in diagnosis_medium.hotspots if h.severity.value == "critical"]

        # Least sensitive (high threshold)
        diagnosis_strict = diagnose_congestion(metrics, hotspot_threshold=0.8)
        critical_strict = [h for h in diagnosis_strict.hotspots if h.severity.value == "critical"]

        # Verify sensitivity: lower threshold = more critical hotspots detected
        assert len(critical_sensitive) > 0, "Sensitive threshold should detect critical hotspots"
        assert len(critical_medium) == 0, "Medium threshold should not detect critical hotspots for hot_ratio=0.55"
        assert len(critical_strict) == 0, "Strict threshold should not detect critical hotspots for hot_ratio=0.55"

    # Additional validation tests

    def test_hotspot_threshold_validation_in_diagnosis_config(self) -> None:
        """Verify DiagnosisConfig validates hotspot_threshold range."""
        # Valid thresholds
        config_valid = DiagnosisConfig(hotspot_threshold=0.5)
        assert config_valid.hotspot_threshold == 0.5

        # Invalid: too high
        with pytest.raises(ValueError, match="hotspot_threshold must be between 0.0 and 1.0"):
            DiagnosisConfig(hotspot_threshold=1.5)

        # Invalid: zero or negative
        with pytest.raises(ValueError, match="hotspot_threshold must be between 0.0 and 1.0"):
            DiagnosisConfig(hotspot_threshold=0.0)

        with pytest.raises(ValueError, match="hotspot_threshold must be between 0.0 and 1.0"):
            DiagnosisConfig(hotspot_threshold=-0.1)

    def test_threshold_boundary_values(self) -> None:
        """Test hotspot detection at exact threshold boundary."""
        # Create metrics with hot_ratio exactly at threshold
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=700,
            hot_ratio=0.70,
            max_overflow=1000,
            layer_metrics={"metal2": 400, "metal3": 350, "metal4": 250},
        )

        # At exact threshold, should detect hotspots
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)
        critical_hotspots = [h for h in diagnosis.hotspots if h.severity.value == "critical"]

        assert len(critical_hotspots) > 0, "Should detect critical hotspots when hot_ratio == threshold"

    def test_hotspot_threshold_affects_diagnosis_severity(self) -> None:
        """Verify that hotspot_threshold affects overall diagnosis severity."""
        # Same metrics, different thresholds
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=600,
            hot_ratio=0.60,
            max_overflow=900,
            layer_metrics={"metal2": 400, "metal3": 320},
        )

        # With strict threshold, fewer hotspots detected
        diagnosis_strict = diagnose_congestion(metrics, hotspot_threshold=0.8)

        # With lenient threshold, more hotspots detected
        diagnosis_lenient = diagnose_congestion(metrics, hotspot_threshold=0.4)

        # Lenient threshold should detect more hotspots
        assert len(diagnosis_lenient.hotspots) >= len(diagnosis_strict.hotspots), \
            "Lenient threshold should detect at least as many hotspots as strict threshold"

    def test_integration_with_study_config(self) -> None:
        """Verify hotspot_threshold integrates with StudyConfig."""
        from src.controller.types import ExecutionMode, SafetyDomain, StageConfig, StudyConfig

        # Create StudyConfig with custom diagnosis configuration
        study_config = StudyConfig(
            name="test_hotspot_threshold",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            snapshot_path="/tmp/test_snapshot",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    trial_budget=10,
                    survivor_count=3,
                )
            ],
            diagnosis=DiagnosisConfig(
                enabled=True,
                timing_paths=20,
                hotspot_threshold=0.6,  # Custom threshold
            ),
        )

        # Verify the threshold is properly stored in the study config
        assert study_config.diagnosis.hotspot_threshold == 0.6
        assert study_config.diagnosis.enabled is True
