"""Tests for F242: Study comparison includes ECO effectiveness comparison.

Feature: Study comparison includes ECO effectiveness comparison

Steps:
1. Run study comparison
2. Verify ECO effectiveness table is included
3. Verify success rate per ECO is compared (v1 vs v2)
4. Verify deltas show which ECOs improved or regressed
5. Verify eco_effectiveness_comparison.png is generated (placeholer for now)
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.study_comparison import (
    ECOEffectivenessComparison,
    ECOEffectivenessData,
    StudyComparisonReport,
    compare_studies,
    format_comparison_report,
    load_eco_effectiveness_data,
    write_comparison_report,
)


class TestStep1RunStudyComparison:
    """Step 1: Run study comparison with ECO effectiveness data."""

    def test_compare_studies_includes_eco_effectiveness(self, tmp_path: Path) -> None:
        """Test that compare_studies includes ECO effectiveness comparisons."""
        # Create mock telemetry for two studies
        telemetry_dir = tmp_path / "telemetry"
        artifacts_dir = tmp_path / "artifacts"

        # Study 1
        study1_dir = telemetry_dir / "study_v1"
        study1_dir.mkdir(parents=True)
        study1_summary = study1_dir / "study_summary.json"
        study1_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.8,
                    "final_total_power_mw": 50.0,
                    "best_case_name": "case_1",
                }
            )
        )

        # Study 2
        study2_dir = telemetry_dir / "study_v2"
        study2_dir.mkdir(parents=True)
        study2_summary = study2_dir / "study_summary.json"
        study2_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -50.0,
                    "final_tns_ps": -200.0,
                    "final_hot_ratio": 0.5,
                    "final_total_power_mw": 40.0,
                    "best_case_name": "case_2",
                }
            )
        )

        # Create ECO leaderboard data for study 1
        study1_artifacts = artifacts_dir / "study_v1"
        study1_artifacts.mkdir(parents=True)
        eco_leaderboard1 = study1_artifacts / "eco_leaderboard.json"
        eco_leaderboard1.write_text(
            json.dumps(
                {
                    "study_name": "study_v1",
                    "total_ecos": 2,
                    "total_applications": 20,
                    "entries": [
                        {
                            "rank": 1,
                            "eco_name": "buffer_insertion",
                            "eco_class": "placement_local",
                            "total_applications": 10,
                            "successful_applications": 7,
                            "success_rate": 0.7,
                            "average_wns_improvement_ps": 50.0,
                            "best_wns_improvement_ps": 100.0,
                            "worst_wns_degradation_ps": -10.0,
                            "prior": "trusted",
                        },
                        {
                            "rank": 2,
                            "eco_name": "gate_sizing",
                            "eco_class": "topology_neutral",
                            "total_applications": 10,
                            "successful_applications": 5,
                            "success_rate": 0.5,
                            "average_wns_improvement_ps": 30.0,
                            "best_wns_improvement_ps": 80.0,
                            "worst_wns_degradation_ps": -20.0,
                            "prior": "mixed",
                        },
                    ],
                }
            )
        )

        # Create ECO leaderboard data for study 2
        study2_artifacts = artifacts_dir / "study_v2"
        study2_artifacts.mkdir(parents=True)
        eco_leaderboard2 = study2_artifacts / "eco_leaderboard.json"
        eco_leaderboard2.write_text(
            json.dumps(
                {
                    "study_name": "study_v2",
                    "total_ecos": 2,
                    "total_applications": 20,
                    "entries": [
                        {
                            "rank": 1,
                            "eco_name": "buffer_insertion",
                            "eco_class": "placement_local",
                            "total_applications": 10,
                            "successful_applications": 9,
                            "success_rate": 0.9,
                            "average_wns_improvement_ps": 70.0,
                            "best_wns_improvement_ps": 120.0,
                            "worst_wns_degradation_ps": 0.0,
                            "prior": "trusted",
                        },
                        {
                            "rank": 2,
                            "eco_name": "gate_sizing",
                            "eco_class": "topology_neutral",
                            "total_applications": 10,
                            "successful_applications": 3,
                            "success_rate": 0.3,
                            "average_wns_improvement_ps": 20.0,
                            "best_wns_improvement_ps": 60.0,
                            "worst_wns_degradation_ps": -30.0,
                            "prior": "suspicious",
                        },
                    ],
                }
            )
        )

        # Compare studies
        report = compare_studies(
            "study_v1", "study_v2", telemetry_root=telemetry_dir, artifacts_root=artifacts_dir
        )

        # Verify ECO effectiveness comparisons are included
        assert len(report.eco_effectiveness_comparisons) > 0
        assert isinstance(report.eco_effectiveness_comparisons[0], ECOEffectivenessComparison)

    def test_compare_studies_without_eco_data(self, tmp_path: Path) -> None:
        """Test that compare_studies works even without ECO leaderboard data."""
        # Create mock telemetry for two studies (no ECO data)
        telemetry_dir = tmp_path / "telemetry"

        # Study 1
        study1_dir = telemetry_dir / "study_v1"
        study1_dir.mkdir(parents=True)
        study1_summary = study1_dir / "study_summary.json"
        study1_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.8,
                    "final_total_power_mw": 50.0,
                    "best_case_name": "case_1",
                }
            )
        )

        # Study 2
        study2_dir = telemetry_dir / "study_v2"
        study2_dir.mkdir(parents=True)
        study2_summary = study2_dir / "study_summary.json"
        study2_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -50.0,
                    "final_tns_ps": -200.0,
                    "final_hot_ratio": 0.5,
                    "final_total_power_mw": 40.0,
                    "best_case_name": "case_2",
                }
            )
        )

        # Compare studies (no artifacts directory)
        report = compare_studies("study_v1", "study_v2", telemetry_root=telemetry_dir)

        # Verify report is created without ECO comparisons
        assert len(report.eco_effectiveness_comparisons) == 0


class TestStep2VerifyECOEffectivenessTableIncluded:
    """Step 2: Verify ECO effectiveness table is included in report."""

    def test_formatted_report_includes_eco_table(self) -> None:
        """Test that formatted report includes ECO effectiveness table."""
        from src.controller.study_comparison import MetricComparison, StudyMetricsSummary

        # Create a comparison report with ECO effectiveness
        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_tns_ps=-500.0,
            final_hot_ratio=0.8,
            final_total_power_mw=50.0,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_tns_ps=-200.0,
            final_hot_ratio=0.5,
            final_total_power_mw=40.0,
        )

        metric_comparisons = [
            MetricComparison(metric_name="wns_ps", study1_value=-100.0, study2_value=-50.0),
        ]

        eco_comparisons = [
            ECOEffectivenessComparison(
                eco_name="buffer_insertion",
                study1_success_rate=0.7,
                study2_success_rate=0.9,
                study1_applications=10,
                study2_applications=10,
            ),
        ]

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=metric_comparisons,
            eco_effectiveness_comparisons=eco_comparisons,
        )

        # Format report
        formatted = format_comparison_report(report)

        # Verify ECO table is included
        assert "ECO EFFECTIVENESS COMPARISON" in formatted
        assert "buffer_insertion" in formatted

    def test_eco_table_has_correct_columns(self) -> None:
        """Test that ECO table has the correct column headers."""
        from src.controller.study_comparison import MetricComparison, StudyMetricsSummary

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
        )

        eco_comparisons = [
            ECOEffectivenessComparison(
                eco_name="buffer_insertion",
                study1_success_rate=0.7,
                study2_success_rate=0.9,
                study1_applications=10,
                study2_applications=10,
            ),
        ]

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=eco_comparisons,
        )

        formatted = format_comparison_report(report)

        # Verify column headers
        assert "ECO Name" in formatted
        assert "V1 Rate" in formatted
        assert "V2 Rate" in formatted
        assert "Delta" in formatted
        assert "Dir" in formatted


class TestStep3VerifySuccessRateComparison:
    """Step 3: Verify success rate per ECO is compared (v1 vs v2)."""

    def test_success_rate_comparison_for_each_eco(self) -> None:
        """Test that success rates are compared for each ECO."""
        eco_comp = ECOEffectivenessComparison(
            eco_name="buffer_insertion",
            study1_success_rate=0.7,
            study2_success_rate=0.9,
            study1_applications=10,
            study2_applications=10,
        )

        # Verify both study rates are captured
        assert eco_comp.study1_success_rate == 0.7
        assert eco_comp.study2_success_rate == 0.9

    def test_success_rate_delta_calculated(self) -> None:
        """Test that success rate delta is calculated correctly."""
        eco_comp = ECOEffectivenessComparison(
            eco_name="buffer_insertion",
            study1_success_rate=0.7,
            study2_success_rate=0.9,
            study1_applications=10,
            study2_applications=10,
        )

        # Delta should be study2 - study1 = 0.9 - 0.7 = 0.2
        assert eco_comp.success_rate_delta == pytest.approx(0.2)

    def test_success_rate_comparison_with_missing_data(self) -> None:
        """Test success rate comparison when one study has no data for an ECO."""
        eco_comp = ECOEffectivenessComparison(
            eco_name="new_eco",
            study1_success_rate=None,
            study2_success_rate=0.8,
            study1_applications=None,
            study2_applications=5,
        )

        # Delta should be None when data is missing
        assert eco_comp.success_rate_delta is None
        assert eco_comp.direction == "N/A"

    def test_load_eco_effectiveness_data(self, tmp_path: Path) -> None:
        """Test loading ECO effectiveness data from leaderboard file."""
        artifacts_dir = tmp_path / "artifacts"
        study_artifacts = artifacts_dir / "test_study"
        study_artifacts.mkdir(parents=True)

        # Create ECO leaderboard
        eco_leaderboard = study_artifacts / "eco_leaderboard.json"
        eco_leaderboard.write_text(
            json.dumps(
                {
                    "study_name": "test_study",
                    "total_ecos": 1,
                    "total_applications": 10,
                    "entries": [
                        {
                            "rank": 1,
                            "eco_name": "buffer_insertion",
                            "total_applications": 10,
                            "successful_applications": 8,
                            "success_rate": 0.8,
                            "average_wns_improvement_ps": 60.0,
                        },
                    ],
                }
            )
        )

        # Load ECO effectiveness data
        eco_data = load_eco_effectiveness_data("test_study", artifacts_root=artifacts_dir)

        # Verify data was loaded
        assert "buffer_insertion" in eco_data
        assert eco_data["buffer_insertion"].success_rate == 0.8
        assert eco_data["buffer_insertion"].total_applications == 10
        assert eco_data["buffer_insertion"].successful_applications == 8


class TestStep4VerifyDeltasShowImprovementOrRegression:
    """Step 4: Verify deltas show which ECOs improved or regressed."""

    def test_improvement_indicator_for_improved_eco(self) -> None:
        """Test that improvement is correctly identified."""
        eco_comp = ECOEffectivenessComparison(
            eco_name="buffer_insertion",
            study1_success_rate=0.7,
            study2_success_rate=0.9,
            study1_applications=10,
            study2_applications=10,
        )

        # Success rate improved from 0.7 to 0.9
        assert eco_comp.improved is True
        assert eco_comp.direction == "▲"

    def test_regression_indicator_for_regressed_eco(self) -> None:
        """Test that regression is correctly identified."""
        eco_comp = ECOEffectivenessComparison(
            eco_name="gate_sizing",
            study1_success_rate=0.8,
            study2_success_rate=0.5,
            study1_applications=10,
            study2_applications=10,
        )

        # Success rate regressed from 0.8 to 0.5
        assert eco_comp.improved is False
        assert eco_comp.direction == "▼"

    def test_no_change_indicator_for_stable_eco(self) -> None:
        """Test that no change is correctly identified."""
        eco_comp = ECOEffectivenessComparison(
            eco_name="buffer_insertion",
            study1_success_rate=0.75,
            study2_success_rate=0.755,
            study1_applications=10,
            study2_applications=10,
        )

        # Success rate change is < 1% threshold (0.005 = 0.5%)
        assert eco_comp.improved is None
        assert eco_comp.direction == "="

    def test_formatted_report_shows_direction_indicators(self) -> None:
        """Test that formatted report shows direction indicators."""
        from src.controller.study_comparison import StudyMetricsSummary

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
        )

        eco_comparisons = [
            ECOEffectivenessComparison(
                eco_name="buffer_insertion",
                study1_success_rate=0.7,
                study2_success_rate=0.9,
                study1_applications=10,
                study2_applications=10,
            ),
            ECOEffectivenessComparison(
                eco_name="gate_sizing",
                study1_success_rate=0.8,
                study2_success_rate=0.5,
                study1_applications=10,
                study2_applications=10,
            ),
        ]

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=eco_comparisons,
        )

        formatted = format_comparison_report(report)

        # Verify direction indicators are present
        assert "▲" in formatted  # Improvement
        assert "▼" in formatted  # Regression


class TestStep5VerifyECOEffectivenessVisualization:
    """Step 5: Verify eco_effectiveness_comparison.png is generated (placeholder)."""

    def test_eco_comparison_in_json_output(self, tmp_path: Path) -> None:
        """Test that ECO comparison data is included in JSON output."""
        from src.controller.study_comparison import StudyMetricsSummary

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
        )

        eco_comparisons = [
            ECOEffectivenessComparison(
                eco_name="buffer_insertion",
                study1_success_rate=0.7,
                study2_success_rate=0.9,
                study1_applications=10,
                study2_applications=10,
            ),
        ]

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=eco_comparisons,
        )

        # Write to file
        output_file = tmp_path / "comparison.json"
        write_comparison_report(report, output_file)

        # Read back and verify
        with open(output_file) as f:
            data = json.load(f)

        assert "eco_effectiveness_comparisons" in data
        assert len(data["eco_effectiveness_comparisons"]) == 1
        assert data["eco_effectiveness_comparisons"][0]["eco_name"] == "buffer_insertion"
        assert data["eco_effectiveness_comparisons"][0]["study1_success_rate"] == 0.7
        assert data["eco_effectiveness_comparisons"][0]["study2_success_rate"] == 0.9

    def test_eco_comparison_data_structure(self) -> None:
        """Test that ECO comparison has correct data structure."""
        eco_comp = ECOEffectivenessComparison(
            eco_name="buffer_insertion",
            study1_success_rate=0.7,
            study2_success_rate=0.9,
            study1_applications=10,
            study2_applications=10,
        )

        # Verify all required fields are present
        assert eco_comp.eco_name == "buffer_insertion"
        assert eco_comp.study1_success_rate == 0.7
        assert eco_comp.study2_success_rate == 0.9
        assert eco_comp.study1_applications == 10
        assert eco_comp.study2_applications == 10
        assert eco_comp.success_rate_delta is not None
        assert eco_comp.direction in ["▲", "▼", "=", "N/A"]
        assert eco_comp.improved is not None


class TestIntegration:
    """Integration tests for complete ECO effectiveness comparison workflow."""

    def test_complete_eco_effectiveness_comparison_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow from loading data to generating report."""
        # Create mock telemetry and artifacts
        telemetry_dir = tmp_path / "telemetry"
        artifacts_dir = tmp_path / "artifacts"

        # Study 1
        study1_dir = telemetry_dir / "study_v1"
        study1_dir.mkdir(parents=True)
        study1_summary = study1_dir / "study_summary.json"
        study1_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.8,
                    "best_case_name": "case_1",
                }
            )
        )

        study1_artifacts = artifacts_dir / "study_v1"
        study1_artifacts.mkdir(parents=True)
        eco_leaderboard1 = study1_artifacts / "eco_leaderboard.json"
        eco_leaderboard1.write_text(
            json.dumps(
                {
                    "study_name": "study_v1",
                    "entries": [
                        {
                            "eco_name": "buffer_insertion",
                            "total_applications": 10,
                            "successful_applications": 7,
                            "success_rate": 0.7,
                            "average_wns_improvement_ps": 50.0,
                        },
                    ],
                }
            )
        )

        # Study 2
        study2_dir = telemetry_dir / "study_v2"
        study2_dir.mkdir(parents=True)
        study2_summary = study2_dir / "study_summary.json"
        study2_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -50.0,
                    "final_tns_ps": -200.0,
                    "final_hot_ratio": 0.5,
                    "best_case_name": "case_2",
                }
            )
        )

        study2_artifacts = artifacts_dir / "study_v2"
        study2_artifacts.mkdir(parents=True)
        eco_leaderboard2 = study2_artifacts / "eco_leaderboard.json"
        eco_leaderboard2.write_text(
            json.dumps(
                {
                    "study_name": "study_v2",
                    "entries": [
                        {
                            "eco_name": "buffer_insertion",
                            "total_applications": 10,
                            "successful_applications": 9,
                            "success_rate": 0.9,
                            "average_wns_improvement_ps": 70.0,
                        },
                    ],
                }
            )
        )

        # Compare studies
        report = compare_studies(
            "study_v1", "study_v2", telemetry_root=telemetry_dir, artifacts_root=artifacts_dir
        )

        # Verify ECO comparisons
        assert len(report.eco_effectiveness_comparisons) == 1
        eco_comp = report.eco_effectiveness_comparisons[0]
        assert eco_comp.eco_name == "buffer_insertion"
        assert eco_comp.study1_success_rate == 0.7
        assert eco_comp.study2_success_rate == 0.9
        assert eco_comp.improved is True
        assert eco_comp.direction == "▲"

        # Format report
        formatted = format_comparison_report(report)
        assert "ECO EFFECTIVENESS COMPARISON" in formatted
        assert "buffer_insertion" in formatted
        assert "70.0%" in formatted
        assert "90.0%" in formatted

        # Write to file
        output_file = tmp_path / "comparison.json"
        write_comparison_report(report, output_file)
        assert output_file.exists()

        # Verify JSON contains ECO data
        with open(output_file) as f:
            data = json.load(f)
        assert "eco_effectiveness_comparisons" in data
        assert len(data["eco_effectiveness_comparisons"]) == 1
