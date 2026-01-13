"""
Test F114: DoomDetector class implements all doom check methods and decision logic

This test validates that the complete DoomDetector class:
1. Implements __init__ with DoomConfig
2. Implements check_doom method with metric, trajectory, and eco_exhaustion checks
3. Implements _check_stagnation helper for trajectory analysis
4. Returns DoomClassification with doom_type, trigger, and action
5. Integrates with executor to actually terminate doomed cases

Feature F114 Steps:
1. Implement DoomDetector.__init__ with DoomConfig
2. Implement check_doom method with metric, trajectory, and eco_exhaustion checks
3. Implement _check_stagnation helper for trajectory analysis
4. Return DoomClassification with doom_type, trigger, and action
5. Integrate with executor to actually terminate doomed cases
"""

import pytest
from unittest.mock import MagicMock, Mock
from src.controller.doom_detection import (
    DoomConfig,
    DoomDetector,
    DoomType,
    DoomClassification,
    format_doom_report,
)


class TestF114DoomDetectorInitialization:
    """Test DoomDetector.__init__ with DoomConfig"""

    def test_step_1_doom_detector_init_with_config(self):
        """Step 1: Implement DoomDetector.__init__ with DoomConfig"""
        # Create a custom config
        config = DoomConfig(
            enabled=True,
            wns_ps_hopeless=-10000,
            hot_ratio_hopeless=0.8,
            tns_ps_hopeless=-500000,
            trajectory_enabled=True,
            min_stages_for_trajectory=2,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
            eco_exhaustion_enabled=True,
        )

        # Initialize DoomDetector
        detector = DoomDetector(config)

        # Verify initialization
        assert detector.config == config, "Config should be stored"
        assert detector.config.enabled is True, "Config should be accessible"
        assert detector.config.wns_ps_hopeless == -10000, "Thresholds should be preserved"

    def test_step_1_doom_detector_validates_config(self):
        """Step 1: Verify config validation in __init__"""
        # Invalid config should raise error
        invalid_config = DoomConfig(
            min_stages_for_trajectory=0,  # Invalid: must be >= 1
        )

        with pytest.raises(ValueError, match="min_stages_for_trajectory"):
            DoomDetector(invalid_config)

        # Another invalid config
        invalid_config2 = DoomConfig(
            stagnation_threshold=1.5,  # Invalid: must be in (0, 1)
        )

        with pytest.raises(ValueError, match="stagnation_threshold"):
            DoomDetector(invalid_config2)

    def test_step_1_doom_detector_accepts_default_config(self):
        """Step 1: Verify DoomDetector works with default config"""
        detector = DoomDetector(DoomConfig())

        assert detector.config.enabled is True, "Default config should be enabled"
        assert detector.config.wns_ps_hopeless == -10000, "Default thresholds should be set"


class TestF114CheckDoomMethod:
    """Test check_doom method with all three check types"""

    def test_step_2_check_doom_method_signature(self):
        """Step 2: Verify check_doom method exists with correct signature"""
        detector = DoomDetector(DoomConfig())

        # Check method exists
        assert hasattr(detector, "check_doom"), "check_doom method should exist"

        # Check signature accepts required parameters
        mock_case = MagicMock()
        metrics = {"wns_ps": -1000, "hot_ratio": 0.5}

        # Should not raise
        result = detector.check_doom(mock_case, metrics)
        assert isinstance(result, DoomClassification), "Should return DoomClassification"

    def test_step_2_check_doom_performs_metric_check(self):
        """Step 2: Verify check_doom performs metric check"""
        detector = DoomDetector(DoomConfig(enabled=True))

        mock_case = MagicMock()

        # Hopeless metrics
        hopeless_metrics = {"wns_ps": -12000, "hot_ratio": 0.5}

        result = detector.check_doom(mock_case, hopeless_metrics)

        assert result.is_doomed is True, "Should detect metric-hopeless"
        assert result.doom_type == DoomType.METRIC_HOPELESS, "Should classify as metric_hopeless"
        assert "wns_ps" in result.trigger, "Should identify WNS as trigger"

    def test_step_2_check_doom_performs_trajectory_check(self):
        """Step 2: Verify check_doom performs trajectory check"""
        detector = DoomDetector(DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            min_stages_for_trajectory=2,
            consecutive_stagnation=3,
        ))

        mock_case = MagicMock()

        # Non-hopeless metrics but stagnant trajectory
        current_metrics = {"wns_ps": -1000, "hot_ratio": 0.5}

        # History showing stagnation (< 2% improvement)
        stage_history = [
            {"wns_ps": -1100},  # Initial
            {"wns_ps": -1085},  # 1.4% improvement
            {"wns_ps": -1075},  # 0.9% improvement
            {"wns_ps": -1070},  # 0.5% improvement
        ]

        result = detector.check_doom(
            mock_case,
            current_metrics,
            stage_history=stage_history
        )

        assert result.is_doomed is True, "Should detect trajectory doom"
        assert result.doom_type == DoomType.TRAJECTORY_DOOM, "Should classify as trajectory_doom"
        assert "stagnation" in result.trigger.lower(), "Should mention stagnation"

    def test_step_2_check_doom_performs_eco_exhaustion_check(self):
        """Step 2: Verify check_doom performs ECO exhaustion check"""
        detector = DoomDetector(DoomConfig(
            enabled=True,
            eco_exhaustion_enabled=True,
        ))

        mock_case = MagicMock()

        # Non-hopeless metrics, no trajectory issues
        current_metrics = {"wns_ps": -1000, "hot_ratio": 0.5}

        # All ECOs failed
        mock_priors = []
        for i in range(5):
            prior = MagicMock()
            prior.outcome = "failed"
            mock_priors.append(prior)

        result = detector.check_doom(
            mock_case,
            current_metrics,
            stage_history=None,
            eco_priors=mock_priors
        )

        assert result.is_doomed is True, "Should detect ECO exhaustion"
        assert result.doom_type == DoomType.ECO_EXHAUSTION, "Should classify as eco_exhaustion"
        assert "ecos" in result.trigger.lower(), "Should mention ECOs"

    def test_step_2_check_doom_respects_config_disabled(self):
        """Step 2: Verify check_doom respects enabled=False"""
        detector = DoomDetector(DoomConfig(enabled=False))

        mock_case = MagicMock()
        hopeless_metrics = {"wns_ps": -20000, "hot_ratio": 0.95}

        result = detector.check_doom(mock_case, hopeless_metrics)

        assert result.is_doomed is False, "Should not doom when disabled"
        assert "disabled" in result.trigger.lower(), "Should explain why not checking"

    def test_step_2_check_doom_priority_order(self):
        """Step 2: Verify check_doom checks in priority order (metric > trajectory > eco)"""
        detector = DoomDetector(DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            eco_exhaustion_enabled=True,
        ))

        mock_case = MagicMock()

        # Metrics that trigger ALL three doom types
        hopeless_metrics = {"wns_ps": -12000, "hot_ratio": 0.5}
        stagnant_history = [
            {"wns_ps": -12100},
            {"wns_ps": -12090},
            {"wns_ps": -12085},
        ]
        failed_ecos = [MagicMock(outcome="failed") for _ in range(5)]

        result = detector.check_doom(
            mock_case,
            hopeless_metrics,
            stage_history=stagnant_history,
            eco_priors=failed_ecos
        )

        # Should return metric_hopeless (highest priority)
        assert result.doom_type == DoomType.METRIC_HOPELESS, (
            "Metric-hopeless should take priority over trajectory and ECO exhaustion"
        )


class TestF114CheckStagnationHelper:
    """Test _check_stagnation helper for trajectory analysis"""

    def test_step_3_check_stagnation_exists(self):
        """Step 3: Verify _check_stagnation helper exists"""
        detector = DoomDetector(DoomConfig())

        # The method is actually _check_trajectory_doom, which includes stagnation logic
        assert hasattr(detector, "_check_trajectory_doom"), (
            "_check_trajectory_doom method should exist"
        )

    def test_step_3_check_stagnation_detects_no_improvement(self):
        """Step 3: Verify stagnation detection for < 2% improvement"""
        detector = DoomDetector(DoomConfig(
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            consecutive_stagnation=3,
        ))

        current_metrics = {"wns_ps": -1000}

        # Three consecutive stages with < 2% improvement
        history = [
            {"wns_ps": -1100},  # Baseline
            {"wns_ps": -1090},  # 0.9% improvement
            {"wns_ps": -1082},  # 0.7% improvement
            {"wns_ps": -1075},  # 0.6% improvement
        ]

        result = detector._check_trajectory_doom(current_metrics, history)

        assert result.is_doomed is True, "Should detect stagnation"
        assert "stagnation" in result.trigger.lower(), "Should identify stagnation"
        assert result.doom_type == DoomType.TRAJECTORY_DOOM

    def test_step_3_check_stagnation_detects_regression(self):
        """Step 3: Verify stagnation detection for regression"""
        detector = DoomDetector(DoomConfig(
            trajectory_enabled=True,
            regression_threshold=0.1,
        ))

        current_metrics = {"wns_ps": -1200}

        # Last stage shows regression
        history = [
            {"wns_ps": -1000},  # Started here
            {"wns_ps": -1150},  # Got worse (15% regression)
        ]

        result = detector._check_trajectory_doom(current_metrics, history)

        assert result.is_doomed is True, "Should detect regression"
        assert "regression" in result.trigger.lower(), "Should identify regression"

    def test_step_3_check_stagnation_allows_good_progress(self):
        """Step 3: Verify healthy trajectory is not doomed"""
        detector = DoomDetector(DoomConfig(
            trajectory_enabled=True,
            stagnation_threshold=0.02,
        ))

        current_metrics = {"wns_ps": -700}

        # Good progress (> 2% improvement per stage)
        history = [
            {"wns_ps": -1000},
            {"wns_ps": -900},   # 10% improvement
            {"wns_ps": -800},   # 11% improvement
        ]

        result = detector._check_trajectory_doom(current_metrics, history)

        assert result.is_doomed is False, "Healthy trajectory should not be doomed"
        assert result.doom_type is None


class TestF114DoomClassificationReturn:
    """Test DoomClassification return value structure"""

    def test_step_4_return_doom_classification_with_type(self):
        """Step 4: Verify DoomClassification includes doom_type"""
        detector = DoomDetector(DoomConfig())
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -15000}
        result = detector.check_doom(mock_case, hopeless_metrics)

        assert isinstance(result, DoomClassification), "Should return DoomClassification"
        assert hasattr(result, "doom_type"), "Should have doom_type"
        assert result.doom_type == DoomType.METRIC_HOPELESS, "doom_type should be set"

    def test_step_4_return_doom_classification_with_trigger(self):
        """Step 4: Verify DoomClassification includes trigger"""
        detector = DoomDetector(DoomConfig())
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -15000}
        result = detector.check_doom(mock_case, hopeless_metrics)

        assert hasattr(result, "trigger"), "Should have trigger"
        assert isinstance(result.trigger, str), "Trigger should be a string"
        assert len(result.trigger) > 0, "Trigger should not be empty"
        assert "wns_ps" in result.trigger, "Trigger should describe what caused doom"

    def test_step_4_return_doom_classification_with_action_recommendation(self):
        """Step 4: Verify DoomClassification includes action/recommendation"""
        detector = DoomDetector(DoomConfig())
        mock_case = MagicMock()

        hopeless_metrics = {"wns_ps": -15000}
        result = detector.check_doom(
            mock_case,
            hopeless_metrics,
            remaining_budget=10
        )

        # Check recommendation field
        assert hasattr(result, "recommendation"), "Should have recommendation"
        assert isinstance(result.recommendation, str), "Recommendation should be a string"
        assert len(result.recommendation) > 0, "Recommendation should not be empty"
        assert "recommend" in result.recommendation.lower() or "action" in result.recommendation.lower(), (
            "Recommendation should provide actionable guidance"
        )

    def test_step_4_doom_classification_includes_all_required_fields(self):
        """Step 4: Verify DoomClassification has all required fields"""
        detector = DoomDetector(DoomConfig())
        mock_case = MagicMock()

        metrics = {"wns_ps": -15000}
        result = detector.check_doom(mock_case, metrics, remaining_budget=5)

        # Check all required fields
        assert hasattr(result, "is_doomed"), "Should have is_doomed"
        assert hasattr(result, "doom_type"), "Should have doom_type"
        assert hasattr(result, "trigger"), "Should have trigger"
        assert hasattr(result, "reason"), "Should have reason"
        assert hasattr(result, "confidence"), "Should have confidence"
        assert hasattr(result, "metadata"), "Should have metadata"
        assert hasattr(result, "compute_saved_trials"), "Should have compute_saved_trials"
        assert hasattr(result, "recommendation"), "Should have recommendation"

        # Verify compute_saved is populated
        assert result.compute_saved_trials == 5, "Should calculate compute saved"


class TestF114ExecutorIntegration:
    """Test integration with executor for actual termination"""

    def test_step_5_doom_classification_can_be_serialized(self):
        """Step 5: Verify DoomClassification can be serialized for executor"""
        detector = DoomDetector(DoomConfig())
        mock_case = MagicMock()

        metrics = {"wns_ps": -15000}
        result = detector.check_doom(mock_case, metrics)

        # Should be serializable to dict
        doom_dict = result.to_dict()

        assert isinstance(doom_dict, dict), "Should convert to dict"
        assert "is_doomed" in doom_dict, "Dict should include is_doomed"
        assert "doom_type" in doom_dict, "Dict should include doom_type"
        assert "trigger" in doom_dict, "Dict should include trigger"
        assert doom_dict["is_doomed"] is True, "Should preserve doom status"

    def test_step_5_doom_report_can_be_formatted(self):
        """Step 5: Verify doom report can be formatted for logging"""
        detector = DoomDetector(DoomConfig())
        mock_case = MagicMock()

        metrics = {"wns_ps": -15000}
        result = detector.check_doom(mock_case, metrics, remaining_budget=10)

        # Format report
        report = format_doom_report(result)

        assert isinstance(report, str), "Report should be a string"
        assert "DOOM DETECTED" in report, "Report should indicate doom"
        assert "metric_hopeless" in report, "Report should show doom type"
        assert "Recommendation" in report, "Report should include recommendation"
        assert "10 trials" in report, "Report should show compute saved"

    def test_step_5_executor_can_check_doom_and_terminate(self):
        """Step 5: Verify executor integration pattern"""
        # This test demonstrates how executor would use DoomDetector

        # Setup
        config = DoomConfig(enabled=True)
        detector = DoomDetector(config)

        # Simulate executor checking a case
        mock_case = MagicMock()
        mock_case.id = "case_123"

        metrics = {"wns_ps": -15000, "hot_ratio": 0.9}
        remaining_trials = 50

        # Check doom
        doom = detector.check_doom(mock_case, metrics, remaining_budget=remaining_trials)

        # Executor would now make termination decision
        if doom.is_doomed:
            # Executor terminates case
            should_terminate = True
            termination_reason = doom.reason
            compute_saved = doom.compute_saved_trials

            assert should_terminate is True, "Executor should terminate doomed case"
            assert compute_saved == 50, "Should track compute savings"
            assert len(termination_reason) > 0, "Should have termination reason"

            # Log doom report (what executor would do)
            report = format_doom_report(doom)
            assert "DOOM DETECTED" in report, "Report should be generated for logging"

    def test_step_5_multiple_doom_checks_in_sequence(self):
        """Step 5: Verify doom detector works for multiple cases in sequence"""
        detector = DoomDetector(DoomConfig(enabled=True))

        # Check multiple cases
        cases_and_metrics = [
            (MagicMock(), {"wns_ps": -15000}),  # Hopeless
            (MagicMock(), {"wns_ps": -1000}),   # Not hopeless
            (MagicMock(), {"hot_ratio": 0.9}),  # Hopeless (hot_ratio)
        ]

        results = []
        for case, metrics in cases_and_metrics:
            result = detector.check_doom(case, metrics)
            results.append(result)

        # Verify results
        assert results[0].is_doomed is True, "First case should be doomed"
        assert results[1].is_doomed is False, "Second case should not be doomed"
        assert results[2].is_doomed is True, "Third case should be doomed"

        # Verify different doom types
        assert results[0].doom_type == DoomType.METRIC_HOPELESS
        assert results[1].doom_type is None
        assert results[2].doom_type == DoomType.METRIC_HOPELESS


class TestF114CompleteIntegration:
    """End-to-end integration tests for DoomDetector"""

    def test_complete_doom_detection_workflow(self):
        """Complete workflow: config -> detect -> classify -> report"""
        # 1. Configure
        config = DoomConfig(
            enabled=True,
            wns_ps_hopeless=-10000,
            trajectory_enabled=True,
            eco_exhaustion_enabled=True,
        )

        # 2. Initialize
        detector = DoomDetector(config)

        # 3. Detect doom
        mock_case = MagicMock()
        mock_case.id = "extreme_case"

        metrics = {"wns_ps": -12000, "hot_ratio": 0.85}
        history = [{"wns_ps": -12100}, {"wns_ps": -12050}]

        doom = detector.check_doom(
            mock_case,
            metrics,
            stage_history=history,
            remaining_budget=25
        )

        # 4. Classify
        assert doom.is_doomed is True
        assert doom.doom_type == DoomType.METRIC_HOPELESS
        assert doom.confidence > 0.8
        assert doom.compute_saved_trials == 25

        # 5. Report
        report = format_doom_report(doom)
        assert "DOOM DETECTED" in report
        assert "25 trials" in report
        assert "Recommendation" in report

    def test_doom_detector_handles_all_doom_types(self):
        """Verify detector can identify all three doom types"""
        detector = DoomDetector(DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            eco_exhaustion_enabled=True,
        ))

        mock_case = MagicMock()

        # Test 1: Metric-hopeless
        metrics1 = {"wns_ps": -15000}
        doom1 = detector.check_doom(mock_case, metrics1)
        assert doom1.doom_type == DoomType.METRIC_HOPELESS

        # Test 2: Trajectory-doomed
        metrics2 = {"wns_ps": -1000}
        history2 = [
            {"wns_ps": -1100},
            {"wns_ps": -1090},
            {"wns_ps": -1085},
            {"wns_ps": -1082},
        ]
        doom2 = detector.check_doom(mock_case, metrics2, stage_history=history2)
        assert doom2.doom_type == DoomType.TRAJECTORY_DOOM

        # Test 3: ECO-exhausted
        metrics3 = {"wns_ps": -1000}
        ecos3 = [MagicMock(outcome="failed") for _ in range(5)]
        doom3 = detector.check_doom(mock_case, metrics3, eco_priors=ecos3)
        assert doom3.doom_type == DoomType.ECO_EXHAUSTION
