"""Tests for F241: Compare two studies and generate comparison report.

F241 Requirements:
- Step 1: Complete two studies: nangate45_v1 and nangate45_v2
- Step 2: Execute: noodle2 compare --study1 nangate45_v1 --study2 nangate45_v2
- Step 3: Verify comparison report is generated
- Step 4: Verify overall metrics comparison table is present
- Step 5: Verify final WNS, TNS, hot_ratio deltas are calculated
- Step 6: Verify delta percentages and direction indicators (▲/▼)
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.study_comparison import (
    MetricComparison,
    StudyComparisonReport,
    StudyMetricsSummary,
    compare_studies,
    format_comparison_report,
    load_study_summary,
    write_comparison_report,
)


class TestStep1CreateTwoStudies:
    """Step 1: Complete two studies: nangate45_v1 and nangate45_v2."""

    def test_create_mock_study_telemetry_v1(self, tmp_path):
        """Create mock telemetry for nangate45_v1."""
        study_dir = tmp_path / "telemetry" / "nangate45_v1"
        study_dir.mkdir(parents=True)

        summary = {
            "total_cases": 3,
            "final_wns_ps": -150.0,
            "final_tns_ps": -500.0,
            "final_hot_ratio": 0.35,
            "final_total_power_mw": 12.5,
            "best_case_name": "case_002",
        }

        (study_dir / "study_summary.json").write_text(json.dumps(summary, indent=2))

        assert (study_dir / "study_summary.json").exists()

    def test_create_mock_study_telemetry_v2(self, tmp_path):
        """Create mock telemetry for nangate45_v2."""
        study_dir = tmp_path / "telemetry" / "nangate45_v2"
        study_dir.mkdir(parents=True)

        summary = {
            "total_cases": 5,
            "final_wns_ps": -100.0,  # Improved (less negative)
            "final_tns_ps": -300.0,  # Improved (less negative)
            "final_hot_ratio": 0.25,  # Improved (lower)
            "final_total_power_mw": 11.0,  # Improved (lower)
            "best_case_name": "case_004",
        }

        (study_dir / "study_summary.json").write_text(json.dumps(summary, indent=2))

        assert (study_dir / "study_summary.json").exists()

    def test_load_study_v1_summary(self, tmp_path):
        """Verify we can load nangate45_v1 summary."""
        # Create telemetry
        study_dir = tmp_path / "telemetry" / "nangate45_v1"
        study_dir.mkdir(parents=True)

        summary = {
            "total_cases": 3,
            "final_wns_ps": -150.0,
            "final_tns_ps": -500.0,
            "final_hot_ratio": 0.35,
            "final_total_power_mw": 12.5,
            "best_case_name": "case_002",
        }

        (study_dir / "study_summary.json").write_text(json.dumps(summary, indent=2))

        # Load summary
        loaded = load_study_summary("nangate45_v1", telemetry_root=tmp_path / "telemetry")

        assert loaded.study_name == "nangate45_v1"
        assert loaded.total_cases == 3
        assert loaded.final_wns_ps == -150.0

    def test_load_study_v2_summary(self, tmp_path):
        """Verify we can load nangate45_v2 summary."""
        # Create telemetry
        study_dir = tmp_path / "telemetry" / "nangate45_v2"
        study_dir.mkdir(parents=True)

        summary = {
            "total_cases": 5,
            "final_wns_ps": -100.0,
            "final_tns_ps": -300.0,
            "final_hot_ratio": 0.25,
            "final_total_power_mw": 11.0,
            "best_case_name": "case_004",
        }

        (study_dir / "study_summary.json").write_text(json.dumps(summary, indent=2))

        # Load summary
        loaded = load_study_summary("nangate45_v2", telemetry_root=tmp_path / "telemetry")

        assert loaded.study_name == "nangate45_v2"
        assert loaded.total_cases == 5
        assert loaded.final_wns_ps == -100.0


class TestStep2ExecuteCompareCommand:
    """Step 2: Execute: noodle2 compare --study1 nangate45_v1 --study2 nangate45_v2."""

    def test_compare_studies_function_exists(self):
        """Verify compare_studies function exists."""
        assert callable(compare_studies)

    def test_compare_two_studies(self, tmp_path):
        """Execute comparison between two studies."""
        # Create telemetry for both studies
        study1_dir = tmp_path / "telemetry" / "nangate45_v1"
        study1_dir.mkdir(parents=True)
        study1_summary = {
            "total_cases": 3,
            "final_wns_ps": -150.0,
            "final_tns_ps": -500.0,
            "final_hot_ratio": 0.35,
            "final_total_power_mw": 12.5,
            "best_case_name": "case_002",
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(study1_summary))

        study2_dir = tmp_path / "telemetry" / "nangate45_v2"
        study2_dir.mkdir(parents=True)
        study2_summary = {
            "total_cases": 5,
            "final_wns_ps": -100.0,
            "final_tns_ps": -300.0,
            "final_hot_ratio": 0.25,
            "final_total_power_mw": 11.0,
            "best_case_name": "case_004",
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(study2_summary))

        # Execute comparison
        report = compare_studies(
            "nangate45_v1",
            "nangate45_v2",
            telemetry_root=tmp_path / "telemetry",
        )

        assert report is not None
        assert isinstance(report, StudyComparisonReport)

    def test_comparison_includes_both_study_names(self, tmp_path):
        """Verify comparison report includes both study names."""
        # Setup
        study1_dir = tmp_path / "telemetry" / "nangate45_v1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 3,
                    "final_wns_ps": -150.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.35,
                }
            )
        )

        study2_dir = tmp_path / "telemetry" / "nangate45_v2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 5,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -300.0,
                    "final_hot_ratio": 0.25,
                }
            )
        )

        # Execute
        report = compare_studies(
            "nangate45_v1",
            "nangate45_v2",
            telemetry_root=tmp_path / "telemetry",
        )

        assert report.study1_name == "nangate45_v1"
        assert report.study2_name == "nangate45_v2"


class TestStep3VerifyComparisonReportGenerated:
    """Step 3: Verify comparison report is generated."""

    def test_comparison_report_has_timestamp(self, tmp_path):
        """Verify comparison report includes timestamp."""
        # Setup
        study1_dir = tmp_path / "telemetry" / "s1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -100.0})
        )

        study2_dir = tmp_path / "telemetry" / "s2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -80.0})
        )

        # Execute
        report = compare_studies("s1", "s2", telemetry_root=tmp_path / "telemetry")

        assert report.comparison_timestamp is not None
        assert isinstance(report.comparison_timestamp, str)

    def test_write_comparison_report_to_file(self, tmp_path):
        """Verify comparison report can be written to file."""
        # Create minimal report
        report = StudyComparisonReport(
            study1_name="study1",
            study2_name="study2",
            study1_summary=StudyMetricsSummary(study_name="study1", total_cases=1),
            study2_summary=StudyMetricsSummary(study_name="study2", total_cases=1),
        )

        output_file = tmp_path / "comparison_report.json"
        write_comparison_report(report, output_file)

        assert output_file.exists()

    def test_written_report_is_valid_json(self, tmp_path):
        """Verify written report is valid JSON."""
        # Create minimal report
        report = StudyComparisonReport(
            study1_name="study1",
            study2_name="study2",
            study1_summary=StudyMetricsSummary(study_name="study1", total_cases=1),
            study2_summary=StudyMetricsSummary(study_name="study2", total_cases=1),
        )

        output_file = tmp_path / "comparison_report.json"
        write_comparison_report(report, output_file)

        # Load and verify
        with open(output_file) as f:
            data = json.load(f)

        assert data["study1_name"] == "study1"
        assert data["study2_name"] == "study2"


class TestStep4VerifyMetricsComparisonTable:
    """Step 4: Verify overall metrics comparison table is present."""

    def test_comparison_includes_metric_comparisons(self, tmp_path):
        """Verify comparison report includes metric comparisons list."""
        # Setup
        study1_dir = tmp_path / "telemetry" / "s1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -100.0})
        )

        study2_dir = tmp_path / "telemetry" / "s2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -80.0})
        )

        # Execute
        report = compare_studies("s1", "s2", telemetry_root=tmp_path / "telemetry")

        assert hasattr(report, "metric_comparisons")
        assert isinstance(report.metric_comparisons, list)
        assert len(report.metric_comparisons) > 0

    def test_formatted_report_includes_table(self, tmp_path):
        """Verify formatted report includes comparison table."""
        # Setup
        study1_dir = tmp_path / "telemetry" / "s1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 1,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.35,
                }
            )
        )

        study2_dir = tmp_path / "telemetry" / "s2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 1,
                    "final_wns_ps": -80.0,
                    "final_tns_ps": -300.0,
                    "final_hot_ratio": 0.25,
                }
            )
        )

        # Execute
        report = compare_studies("s1", "s2", telemetry_root=tmp_path / "telemetry")
        formatted = format_comparison_report(report)

        assert "METRICS COMPARISON" in formatted
        assert "Study 1" in formatted
        assert "Study 2" in formatted


class TestStep5VerifyDeltasCalculated:
    """Step 5: Verify final WNS, TNS, hot_ratio deltas are calculated."""

    def test_wns_delta_calculated(self):
        """Verify WNS delta is calculated correctly."""
        comparison = MetricComparison(
            metric_name="wns_ps",
            study1_value=-150.0,
            study2_value=-100.0,
        )

        assert comparison.delta == 50.0  # -100 - (-150) = 50

    def test_tns_delta_calculated(self):
        """Verify TNS delta is calculated correctly."""
        comparison = MetricComparison(
            metric_name="tns_ps",
            study1_value=-500.0,
            study2_value=-300.0,
        )

        assert comparison.delta == 200.0  # -300 - (-500) = 200

    def test_hot_ratio_delta_calculated(self):
        """Verify hot_ratio delta is calculated correctly."""
        comparison = MetricComparison(
            metric_name="hot_ratio",
            study1_value=0.35,
            study2_value=0.25,
        )

        assert comparison.delta == pytest.approx(-0.10)  # 0.25 - 0.35 = -0.10

    def test_comparison_report_includes_all_metrics(self, tmp_path):
        """Verify comparison includes WNS, TNS, and hot_ratio."""
        # Setup
        study1_dir = tmp_path / "telemetry" / "s1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 1,
                    "final_wns_ps": -150.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.35,
                    "final_total_power_mw": 12.5,
                }
            )
        )

        study2_dir = tmp_path / "telemetry" / "s2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 1,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -300.0,
                    "final_hot_ratio": 0.25,
                    "final_total_power_mw": 11.0,
                }
            )
        )

        # Execute
        report = compare_studies("s1", "s2", telemetry_root=tmp_path / "telemetry")

        metric_names = {c.metric_name for c in report.metric_comparisons}
        assert "wns_ps" in metric_names
        assert "tns_ps" in metric_names
        assert "hot_ratio" in metric_names


class TestStep6VerifyDeltaPercentagesAndDirections:
    """Step 6: Verify delta percentages and direction indicators (▲/▼)."""

    def test_wns_improvement_shows_up_arrow(self):
        """Verify WNS improvement shows ▲."""
        comparison = MetricComparison(
            metric_name="wns_ps",
            study1_value=-150.0,
            study2_value=-100.0,  # Less negative = better
        )

        assert comparison.direction == "▲"
        assert comparison.improved is True

    def test_wns_regression_shows_down_arrow(self):
        """Verify WNS regression shows ▼."""
        comparison = MetricComparison(
            metric_name="wns_ps",
            study1_value=-100.0,
            study2_value=-150.0,  # More negative = worse
        )

        assert comparison.direction == "▼"
        assert comparison.improved is False

    def test_hot_ratio_improvement_shows_up_arrow(self):
        """Verify hot_ratio improvement shows ▲."""
        comparison = MetricComparison(
            metric_name="hot_ratio",
            study1_value=0.35,
            study2_value=0.25,  # Lower = better
        )

        assert comparison.direction == "▲"
        assert comparison.improved is True

    def test_hot_ratio_regression_shows_down_arrow(self):
        """Verify hot_ratio regression shows ▼."""
        comparison = MetricComparison(
            metric_name="hot_ratio",
            study1_value=0.25,
            study2_value=0.35,  # Higher = worse
        )

        assert comparison.direction == "▼"
        assert comparison.improved is False

    def test_delta_percentage_calculated(self):
        """Verify delta percentage is calculated."""
        comparison = MetricComparison(
            metric_name="wns_ps",
            study1_value=-150.0,
            study2_value=-100.0,
        )

        # Delta = 50, percent = (50 / 150) * 100 = 33.33%
        assert comparison.delta_percent == pytest.approx(33.33, rel=0.01)

    def test_formatted_report_includes_delta_percentages(self, tmp_path):
        """Verify formatted report shows delta percentages."""
        # Setup
        study1_dir = tmp_path / "telemetry" / "s1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -150.0, "final_hot_ratio": 0.35})
        )

        study2_dir = tmp_path / "telemetry" / "s2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -100.0, "final_hot_ratio": 0.25})
        )

        # Execute
        report = compare_studies("s1", "s2", telemetry_root=tmp_path / "telemetry")
        formatted = format_comparison_report(report)

        # Should contain percentage symbol and arrows
        assert "%" in formatted
        assert "▲" in formatted  # At least one improvement

    def test_formatted_report_includes_direction_indicators(self, tmp_path):
        """Verify formatted report shows direction indicators (▲/▼)."""
        # Setup
        study1_dir = tmp_path / "telemetry" / "s1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -150.0})
        )

        study2_dir = tmp_path / "telemetry" / "s2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps({"total_cases": 1, "final_wns_ps": -100.0})
        )

        # Execute
        report = compare_studies("s1", "s2", telemetry_root=tmp_path / "telemetry")
        formatted = format_comparison_report(report)

        # WNS improved, should show ▲
        assert "▲" in formatted


class TestIntegration:
    """Integration tests for complete study comparison workflow."""

    def test_complete_comparison_workflow(self, tmp_path):
        """Test complete workflow: load two studies, compare, format, write."""
        # Create study 1
        study1_dir = tmp_path / "telemetry" / "nangate45_v1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 3,
                    "final_wns_ps": -150.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.35,
                    "final_total_power_mw": 12.5,
                    "best_case_name": "case_002",
                }
            )
        )

        # Create study 2
        study2_dir = tmp_path / "telemetry" / "nangate45_v2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 5,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -300.0,
                    "final_hot_ratio": 0.25,
                    "final_total_power_mw": 11.0,
                    "best_case_name": "case_004",
                }
            )
        )

        # Compare
        report = compare_studies(
            "nangate45_v1",
            "nangate45_v2",
            telemetry_root=tmp_path / "telemetry",
        )

        # Format
        formatted = format_comparison_report(report)

        # Write
        output_file = tmp_path / "comparison_report.json"
        write_comparison_report(report, output_file)

        # Verify
        assert report.overall_improvement is True  # All metrics improved
        assert "IMPROVEMENT" in formatted
        assert output_file.exists()

        # Load and verify written report
        with open(output_file) as f:
            data = json.load(f)

        assert data["study1_name"] == "nangate45_v1"
        assert data["study2_name"] == "nangate45_v2"
        assert data["overall_improvement"] is True

    def test_overall_improvement_detection(self, tmp_path):
        """Verify overall improvement is correctly determined."""
        # Setup: Study 2 improves in 3/4 metrics
        study1_dir = tmp_path / "telemetry" / "s1"
        study1_dir.mkdir(parents=True)
        (study1_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 1,
                    "final_wns_ps": -150.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.35,
                    "final_total_power_mw": 12.5,
                }
            )
        )

        study2_dir = tmp_path / "telemetry" / "s2"
        study2_dir.mkdir(parents=True)
        (study2_dir / "study_summary.json").write_text(
            json.dumps(
                {
                    "total_cases": 1,
                    "final_wns_ps": -100.0,  # Improved
                    "final_tns_ps": -300.0,  # Improved
                    "final_hot_ratio": 0.25,  # Improved
                    "final_total_power_mw": 13.0,  # Regressed
                }
            )
        )

        # Execute
        report = compare_studies("s1", "s2", telemetry_root=tmp_path / "telemetry")

        # 3 out of 4 improved = overall improvement
        assert report.overall_improvement is True
