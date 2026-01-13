"""
Test F089: Doom response logs compute saved and provides recommendations.

This test validates that when doom is detected, the system:
1. Calculates how many trials were saved by early termination
2. Provides actionable recommendations based on doom type
3. Includes this information in the doom classification JSON
4. Shows up in study summaries

Feature F089 Steps:
1. Trigger a doom condition on a case
2. Verify doom classification JSON is created
3. Verify compute_saved_trials count is calculated
4. Verify recommendation message is included
5. Verify doom event appears in study summary
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from src.controller.doom_detection import (
    DoomConfig,
    DoomDetector,
    DoomType,
    DoomClassification,
    format_doom_report,
)


class TestF089DoomComputeSavedAndRecommendations:
    """Test doom response with compute saved and recommendations."""

    def test_step_1_trigger_doom_condition_with_remaining_budget(self):
        """Step 1: Trigger a doom condition on a case with remaining budget."""
        config = DoomConfig(
            enabled=True,
            wns_ps_hopeless=-10000,
        )

        detector = DoomDetector(config)

        # Hopeless case with 50 trials remaining in budget
        hopeless_metrics = {
            "wns_ps": -12000,  # Beyond hopeless threshold
            "hot_ratio": 0.5,
        }

        # Create a mock case
        case = MagicMock()

        # Trigger doom with remaining budget
        doom = detector.check_doom(
            case=case,
            metrics=hopeless_metrics,
            remaining_budget=50,  # 50 trials would have been attempted
        )

        assert doom.is_doomed, "Case should be doomed"
        assert doom.doom_type == DoomType.METRIC_HOPELESS
        assert doom.compute_saved_trials == 50, "Should save 50 trials"
        assert doom.recommendation != "", "Should have recommendation"

    def test_step_2_verify_doom_classification_json_serialization(self):
        """Step 2: Verify doom classification JSON is created."""
        config = DoomConfig(enabled=True, wns_ps_hopeless=-10000)
        detector = DoomDetector(config)

        hopeless_metrics = {"wns_ps": -15000, "hot_ratio": 0.6}
        case = MagicMock()

        doom = detector.check_doom(
            case=case,
            metrics=hopeless_metrics,
            remaining_budget=100,
        )

        # Convert to JSON
        doom_dict = doom.to_dict()

        assert isinstance(doom_dict, dict), "Should serialize to dict"
        assert doom_dict["is_doomed"] is True
        assert doom_dict["doom_type"] == "metric_hopeless"
        assert doom_dict["compute_saved_trials"] == 100
        assert doom_dict["recommendation"] != ""
        assert "confidence" in doom_dict
        assert "trigger" in doom_dict
        assert "reason" in doom_dict

        # Verify JSON serializable
        json_str = json.dumps(doom_dict, indent=2)
        assert len(json_str) > 0, "Should be valid JSON"

        # Verify can be loaded back
        loaded = json.loads(json_str)
        assert loaded["compute_saved_trials"] == 100
        assert loaded["recommendation"] == doom_dict["recommendation"]

    def test_step_3_verify_compute_saved_trials_calculation(self):
        """Step 3: Verify compute_saved_trials count is calculated correctly."""
        config = DoomConfig(enabled=True, wns_ps_hopeless=-10000)
        detector = DoomDetector(config)
        case = MagicMock()

        # Test with different remaining budgets
        test_budgets = [0, 1, 10, 50, 100, 500]

        for budget in test_budgets:
            hopeless_metrics = {"wns_ps": -12000}
            doom = detector.check_doom(
                case=case,
                metrics=hopeless_metrics,
                remaining_budget=budget,
            )

            assert doom.is_doomed, f"Should be doomed for budget={budget}"
            assert doom.compute_saved_trials == budget, (
                f"Expected compute_saved_trials={budget}, got {doom.compute_saved_trials}"
            )

    def test_step_4_verify_recommendation_message_included(self):
        """Step 4: Verify recommendation message is included for all doom types."""
        config = DoomConfig(
            enabled=True,
            wns_ps_hopeless=-10000,
            hot_ratio_hopeless=0.8,
            tns_ps_hopeless=-500000,
            trajectory_enabled=True,
            eco_exhaustion_enabled=True,
        )
        detector = DoomDetector(config)
        case = MagicMock()

        # Test 1: Metric hopeless (WNS)
        wns_doom = detector.check_doom(
            case=case,
            metrics={"wns_ps": -12000},
            remaining_budget=50,
        )
        assert wns_doom.is_doomed
        assert wns_doom.recommendation != ""
        assert "Relax clock period" in wns_doom.recommendation
        assert "Recommended actions:" in wns_doom.recommendation

        # Test 2: Metric hopeless (hot_ratio)
        hot_doom = detector.check_doom(
            case=case,
            metrics={"hot_ratio": 0.85, "wns_ps": -1000},
            remaining_budget=30,
        )
        assert hot_doom.is_doomed
        assert hot_doom.recommendation != ""
        assert "80% of paths are timing-critical" in hot_doom.recommendation

        # Test 3: Metric hopeless (TNS)
        tns_doom = detector.check_doom(
            case=case,
            metrics={"tns_ps": -600000, "wns_ps": -1000},
            remaining_budget=25,
        )
        assert tns_doom.is_doomed
        assert tns_doom.recommendation != ""
        assert "Total negative slack" in tns_doom.recommendation

        # Test 4: Trajectory doom (stagnation)
        stage_history = [
            {"wns_ps": -1000},
            {"wns_ps": -995},   # 0.5% improvement
            {"wns_ps": -992},   # 0.3% improvement
            {"wns_ps": -990},   # 0.2% improvement
        ]
        trajectory_doom = detector.check_doom(
            case=case,
            metrics={"wns_ps": -989},
            stage_history=stage_history,
            remaining_budget=40,
        )
        assert trajectory_doom.is_doomed
        assert trajectory_doom.recommendation != ""
        assert "no meaningful progress" in trajectory_doom.recommendation.lower()

    def test_step_5_verify_doom_report_formatting_includes_compute_and_recommendation(self):
        """Step 5: Verify doom event appears in formatted report with all info."""
        config = DoomConfig(enabled=True, wns_ps_hopeless=-10000)
        detector = DoomDetector(config)
        case = MagicMock()

        # Generate doom with compute saved and recommendation
        doom = detector.check_doom(
            case=case,
            metrics={"wns_ps": -15000},
            remaining_budget=75,
        )

        # Format as report
        report = format_doom_report(doom)

        # Verify report structure
        assert "DOOM DETECTED" in report
        assert "metric_hopeless" in report
        assert "Compute Saved:" in report
        assert "75 trials avoided" in report
        assert "Recommendation:" in report
        assert "Relax clock period" in report

        # Verify report is multi-line and well-formatted
        lines = report.split("\n")
        assert len(lines) > 10, "Report should be comprehensive"

        # Check for key sections
        has_compute_section = any("Compute Saved" in line for line in lines)
        has_recommendation_section = any("Recommendation" in line for line in lines)
        has_reason_section = any("Reason:" in line for line in lines)

        assert has_compute_section, "Report missing Compute Saved section"
        assert has_recommendation_section, "Report missing Recommendation section"
        assert has_reason_section, "Report missing Reason section"


class TestF089RecommendationQuality:
    """Additional tests for recommendation quality and usefulness."""

    def test_wns_recommendation_is_actionable(self):
        """Verify WNS recommendations are specific and actionable."""
        config = DoomConfig(enabled=True, wns_ps_hopeless=-10000)
        detector = DoomDetector(config)
        case = MagicMock()

        doom = detector.check_doom(
            case=case,
            metrics={"wns_ps": -12000},
            remaining_budget=50,
        )

        rec = doom.recommendation

        # Should contain at least 3 specific actions
        assert "(1)" in rec and "(2)" in rec and "(3)" in rec
        assert "Relax clock period" in rec
        assert "synthesis" in rec or "placement" in rec

    def test_trajectory_stagnation_vs_regression_recommendations(self):
        """Verify different recommendations for stagnation vs regression."""
        config = DoomConfig(
            enabled=True,
            trajectory_enabled=True,
            stagnation_threshold=0.02,
            regression_threshold=0.1,
        )
        detector = DoomDetector(config)
        case = MagicMock()

        # Stagnation case
        stagnation_history = [
            {"wns_ps": -1000},
            {"wns_ps": -995},
            {"wns_ps": -992},
            {"wns_ps": -990},
        ]
        stagnation_doom = detector.check_doom(
            case=case,
            metrics={"wns_ps": -989},
            stage_history=stagnation_history,
            remaining_budget=40,
        )

        # Regression case
        regression_history = [
            {"wns_ps": -1000},
            {"wns_ps": -800},
            {"wns_ps": -1200},  # Regression!
        ]
        regression_doom = detector.check_doom(
            case=case,
            metrics={"wns_ps": -1300},
            stage_history=regression_history,
            remaining_budget=50,
        )

        assert stagnation_doom.is_doomed
        assert regression_doom.is_doomed

        # Should have different recommendations
        assert "aggressive eco" in stagnation_doom.recommendation.lower()
        assert "regression" in regression_doom.recommendation.lower()
        assert stagnation_doom.recommendation != regression_doom.recommendation

    def test_eco_exhaustion_recommendation_details(self):
        """Verify ECO exhaustion recommendations are specific to failure modes."""
        from dataclasses import dataclass

        @dataclass
        class MockECOPrior:
            name: str
            outcome: str

        config = DoomConfig(enabled=True, eco_exhaustion_enabled=True)
        detector = DoomDetector(config)
        case = MagicMock()

        # All failed
        failed_priors = [
            MockECOPrior("eco1", "failed"),
            MockECOPrior("eco2", "failed"),
            MockECOPrior("eco3", "failed"),
        ]

        failed_doom = detector.check_doom(
            case=case,
            metrics={"wns_ps": -1000},
            eco_priors=failed_priors,
            remaining_budget=30,
        )

        assert failed_doom.is_doomed
        assert failed_doom.doom_type == DoomType.ECO_EXHAUSTION
        assert "failed" in failed_doom.recommendation.lower()
        assert "analyze failure patterns" in failed_doom.recommendation.lower()

    def test_compute_saved_appears_in_json_output(self):
        """Verify compute_saved_trials is in JSON output for study summaries."""
        config = DoomConfig(enabled=True, hot_ratio_hopeless=0.8)
        detector = DoomDetector(config)
        case = MagicMock()

        doom = detector.check_doom(
            case=case,
            metrics={"hot_ratio": 0.9, "wns_ps": -1000},
            remaining_budget=120,
        )

        doom_json = doom.to_dict()

        # Verify fields exist and are correct
        assert "compute_saved_trials" in doom_json
        assert doom_json["compute_saved_trials"] == 120
        assert "recommendation" in doom_json
        assert len(doom_json["recommendation"]) > 50, "Recommendation should be detailed"

        # Verify JSON is complete for logging
        required_fields = [
            "is_doomed",
            "doom_type",
            "trigger",
            "reason",
            "confidence",
            "compute_saved_trials",
            "recommendation",
            "metadata",
        ]

        for field in required_fields:
            assert field in doom_json, f"Missing field: {field}"
