"""Tests for Case diff report generation.

This module tests the functionality for:
- Computing metric deltas between baseline and derived Cases
- Generating diff reports showing improvements/regressions
- Saving diff reports in JSON and text formats
- Using diff reports for survivor ranking
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.diff_report import (
    CaseDiffReport,
    MetricDelta,
    generate_diff_report,
    save_diff_report,
)
from src.controller.types import CongestionMetrics, TimingMetrics, TrialMetrics


class TestMetricDelta:
    """Tests for MetricDelta calculation."""

    def test_positive_delta_integer(self):
        """Test positive delta with integer values."""
        delta = MetricDelta(
            metric_name="wns_ps",
            baseline_value=-5000,
            derived_value=-3000,
        )
        assert delta.delta == 2000  # -3000 - (-5000) = 2000
        assert delta.delta_percent == pytest.approx(40.0)  # (2000 / 5000) * 100

    def test_negative_delta_integer(self):
        """Test negative delta with integer values."""
        delta = MetricDelta(
            metric_name="wns_ps",
            baseline_value=-3000,
            derived_value=-5000,
        )
        assert delta.delta == -2000  # -5000 - (-3000) = -2000
        assert delta.delta_percent == pytest.approx(-66.67, rel=0.01)

    def test_delta_float(self):
        """Test delta with float values."""
        delta = MetricDelta(
            metric_name="hot_ratio",
            baseline_value=0.25,
            derived_value=0.20,
        )
        assert delta.delta == pytest.approx(-0.05)
        assert delta.delta_percent == pytest.approx(-20.0)

    def test_zero_baseline(self):
        """Test delta when baseline is zero."""
        delta = MetricDelta(
            metric_name="bins_hot",
            baseline_value=0,
            derived_value=10,
        )
        assert delta.delta == 10
        assert delta.delta_percent == float('inf')  # Division by zero case

    def test_both_zero(self):
        """Test delta when both values are zero."""
        delta = MetricDelta(
            metric_name="bins_hot",
            baseline_value=0,
            derived_value=0,
        )
        assert delta.delta == 0
        assert delta.delta_percent is None  # No change

    def test_none_values(self):
        """Test delta with None values (metric not available)."""
        delta = MetricDelta(
            metric_name="tns_ps",
            baseline_value=None,
            derived_value=None,
        )
        assert delta.delta is None
        assert delta.delta_percent is None

    def test_to_dict(self):
        """Test serialization to dictionary."""
        delta = MetricDelta(
            metric_name="wns_ps",
            baseline_value=-5000,
            derived_value=-3000,
        )
        delta_dict = delta.to_dict()
        assert delta_dict["metric_name"] == "wns_ps"
        assert delta_dict["baseline_value"] == -5000
        assert delta_dict["derived_value"] == -3000
        assert delta_dict["delta"] == 2000
        assert delta_dict["delta_percent"] == pytest.approx(40.0)


class TestCaseDiffReportGeneration:
    """Tests for CaseDiffReport generation."""

    def test_generate_diff_report_timing_only(self):
        """Test diff report generation with timing metrics only."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-5000,
                tns_ps=-50000,
                failing_endpoints=10,
            )
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-3000,
                tns_ps=-30000,
                failing_endpoints=5,
            )
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="buffer_insertion",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Check basic fields
        assert report.baseline_case_id == "baseline_0_0"
        assert report.derived_case_id == "derived_0_1"
        assert report.eco_name == "buffer_insertion"

        # Check WNS delta
        assert report.wns_delta is not None
        assert report.wns_delta.delta == 2000  # Improvement
        assert report.wns_delta.improved is True

        # Check TNS delta
        assert report.tns_delta is not None
        assert report.tns_delta.delta == 20000  # Improvement
        assert report.tns_delta.improved is True

        # Check failing endpoints delta
        assert report.failing_endpoints_delta is not None
        assert report.failing_endpoints_delta.delta == -5  # Reduction is good
        assert report.failing_endpoints_delta.improved is True

        # Overall should be improvement
        assert report.overall_improvement is True
        assert "WNS improved" in report.improvement_summary

    def test_generate_diff_report_congestion_only(self):
        """Test diff report generation with congestion metrics only."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=0),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=100,
                hot_ratio=0.10,
                max_overflow=50,
            )
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=0),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=75,
                hot_ratio=0.075,
                max_overflow=30,
            )
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="placement_density_adjust",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Check hot ratio delta
        assert report.hot_ratio_delta is not None
        assert report.hot_ratio_delta.delta == pytest.approx(-0.025)
        assert report.hot_ratio_delta.improved is True

        # Check bins hot delta
        assert report.bins_hot_delta is not None
        assert report.bins_hot_delta.delta == -25
        assert report.bins_hot_delta.improved is True

        # Check max overflow delta
        assert report.max_overflow_delta is not None
        assert report.max_overflow_delta.delta == -20
        assert report.max_overflow_delta.improved is True

        assert "Hot ratio reduced" in report.improvement_summary

    def test_generate_diff_report_mixed_results(self):
        """Test diff report with both improvements and regressions."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-5000,
                tns_ps=-50000,
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=100,
                hot_ratio=0.10,
            )
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-3000,  # Improved
                tns_ps=-30000,  # Improved
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=120,  # Worse
                hot_ratio=0.12,  # Worse
            )
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="mixed_impact_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # WNS improved
        assert report.wns_delta.improved is True

        # Congestion got worse
        assert report.hot_ratio_delta.improved is False

        # Overall improvement still True because WNS is most important
        assert report.overall_improvement is True

        # Summary should mention both
        assert "WNS improved" in report.improvement_summary
        assert "Hot ratio increased" in report.improvement_summary

    def test_generate_diff_report_regression(self):
        """Test diff report showing pure regression."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-3000)
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-6000)  # Worse
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="bad_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # WNS degraded
        assert report.wns_delta.improved is False
        assert report.wns_delta.delta == -3000

        # Overall should NOT be improvement
        assert report.overall_improvement is False
        assert "WNS degraded" in report.improvement_summary

    def test_generate_diff_report_neutral(self):
        """Test diff report with no significant changes."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000)
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000)  # Same
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="neutral_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # No change
        assert report.wns_delta.delta == 0
        assert report.wns_delta.improved is None

        # Not an overall improvement
        assert report.overall_improvement is False

    def test_all_deltas_tracked(self):
        """Test that all deltas are tracked in all_deltas dict."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-5000,
                tns_ps=-50000,
                failing_endpoints=10,
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=100,
                hot_ratio=0.10,
                max_overflow=50,
            )
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-3000,
                tns_ps=-30000,
                failing_endpoints=5,
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=75,
                hot_ratio=0.075,
                max_overflow=30,
            )
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="comprehensive_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # All deltas should be in all_deltas dict
        assert "wns_ps" in report.all_deltas
        assert "tns_ps" in report.all_deltas
        assert "failing_endpoints" in report.all_deltas
        assert "hot_ratio" in report.all_deltas
        assert "bins_hot" in report.all_deltas
        assert "max_overflow" in report.all_deltas

        assert len(report.all_deltas) == 6


class TestCaseDiffReportSerialization:
    """Tests for CaseDiffReport serialization."""

    def test_to_dict(self):
        """Test serialization to dictionary."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000, tns_ps=-50000)
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-3000, tns_ps=-30000)
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        report_dict = report.to_dict()

        # Check structure
        assert "baseline_case_id" in report_dict
        assert "derived_case_id" in report_dict
        assert "eco_name" in report_dict
        assert "timing_deltas" in report_dict
        assert "congestion_deltas" in report_dict
        assert "overall_improvement" in report_dict
        assert "improvement_summary" in report_dict
        assert "all_deltas" in report_dict

        # Check values
        assert report_dict["baseline_case_id"] == "baseline_0_0"
        assert report_dict["derived_case_id"] == "derived_0_1"
        assert report_dict["eco_name"] == "test_eco"
        assert report_dict["overall_improvement"] is True

    def test_to_text(self):
        """Test generation of human-readable text report."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-5000,
                tns_ps=-50000,
                failing_endpoints=10,
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=100,
                hot_ratio=0.10,
            )
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-3000,
                tns_ps=-30000,
                failing_endpoints=5,
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=75,
                hot_ratio=0.075,
            )
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        text = report.to_text()

        # Check that text contains expected sections
        assert "CASE DIFF REPORT" in text
        assert "baseline_0_0" in text
        assert "derived_0_1" in text
        assert "test_eco" in text
        assert "TIMING METRICS" in text
        assert "CONGESTION METRICS" in text
        assert "OVERALL ASSESSMENT" in text

        # Check for metric values
        assert "-5000 ps" in text  # Baseline WNS
        assert "-3000 ps" in text  # Derived WNS
        assert "+2000 ps" in text  # Delta

        # Check for improvement symbols
        assert "✓" in text  # Should have checkmarks for improvements


class TestDiffReportSaving:
    """Tests for saving diff reports to disk."""

    def test_save_diff_report_creates_json_and_text(self):
        """Test that save_diff_report creates both JSON and text files."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000)
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-3000)
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "case_artifacts"
            save_diff_report(report, output_dir)

            # Check JSON file exists and is valid
            json_path = output_dir / "diff_report.json"
            assert json_path.exists()
            with open(json_path) as f:
                data = json.load(f)
                assert data["baseline_case_id"] == "baseline_0_0"
                assert data["derived_case_id"] == "derived_0_1"

            # Check text file exists and contains expected content
            text_path = output_dir / "diff_report.txt"
            assert text_path.exists()
            with open(text_path) as f:
                text = f.read()
                assert "CASE DIFF REPORT" in text
                assert "baseline_0_0" in text

    def test_save_diff_report_creates_directory(self):
        """Test that save_diff_report creates output directory if needed."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000)
        )
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-3000)
        )

        report = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_0_1",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "case_artifacts"
            assert not output_dir.exists()

            save_diff_report(report, output_dir)

            assert output_dir.exists()
            assert (output_dir / "diff_report.json").exists()
            assert (output_dir / "diff_report.txt").exists()


class TestDiffReportForSurvivorRanking:
    """Tests for using diff reports in survivor ranking."""

    def test_diff_report_supports_ranking_by_wns_improvement(self):
        """Test that diff reports can be used to rank trials by WNS improvement."""
        # Create three ECO scenarios with different WNS improvements
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000)
        )

        scenarios = [
            ("eco_best", -2000, 3000),  # Best improvement
            ("eco_good", -3500, 1500),  # Moderate improvement
            ("eco_bad", -6000, -1000),  # Regression
        ]

        reports = []
        for eco_name, derived_wns, expected_delta in scenarios:
            derived_metrics = TrialMetrics(
                timing=TimingMetrics(wns_ps=derived_wns)
            )
            report = generate_diff_report(
                baseline_case_id="baseline_0_0",
                derived_case_id=f"derived_{eco_name}",
                eco_name=eco_name,
                baseline_metrics=baseline_metrics,
                derived_metrics=derived_metrics,
            )
            reports.append(report)

        # Rank by WNS delta (higher delta = better improvement)
        ranked = sorted(reports, key=lambda r: r.wns_delta.delta if r.wns_delta else float('-inf'), reverse=True)

        # Best should be first
        assert ranked[0].eco_name == "eco_best"
        assert ranked[0].wns_delta.delta == 3000
        assert ranked[0].overall_improvement is True

        # Good should be second
        assert ranked[1].eco_name == "eco_good"
        assert ranked[1].wns_delta.delta == 1500

        # Bad should be last
        assert ranked[2].eco_name == "eco_bad"
        assert ranked[2].wns_delta.delta == -1000
        assert ranked[2].overall_improvement is False

    def test_diff_report_supports_ranking_by_congestion_improvement(self):
        """Test that diff reports can be used to rank trials by congestion reduction."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=0),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=100,
                hot_ratio=0.10,
            )
        )

        scenarios = [
            ("eco_best", 0.05),  # Best congestion reduction
            ("eco_good", 0.08),  # Moderate reduction
            ("eco_bad", 0.12),   # Congestion increased
        ]

        reports = []
        for eco_name, derived_hot_ratio in scenarios:
            derived_metrics = TrialMetrics(
                timing=TimingMetrics(wns_ps=0),
                congestion=CongestionMetrics(
                    bins_total=1000,
                    bins_hot=int(derived_hot_ratio * 1000),
                    hot_ratio=derived_hot_ratio,
                )
            )
            report = generate_diff_report(
                baseline_case_id="baseline_0_0",
                derived_case_id=f"derived_{eco_name}",
                eco_name=eco_name,
                baseline_metrics=baseline_metrics,
                derived_metrics=derived_metrics,
            )
            reports.append(report)

        # Rank by hot_ratio delta (negative delta = improvement)
        ranked = sorted(reports, key=lambda r: r.hot_ratio_delta.delta if r.hot_ratio_delta else float('inf'))

        # Best should be first (most negative delta)
        assert ranked[0].eco_name == "eco_best"
        assert ranked[0].hot_ratio_delta.delta == pytest.approx(-0.05)

        # Bad should be last (positive delta)
        assert ranked[2].eco_name == "eco_bad"
        assert ranked[2].hot_ratio_delta.delta == pytest.approx(0.02)

    def test_diff_report_overall_improvement_flag(self):
        """Test that overall_improvement flag correctly identifies net improvements."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000)
        )

        # Test improvement case
        improved_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-3000)
        )
        report_improved = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_improved",
            eco_name="eco_improved",
            baseline_metrics=baseline_metrics,
            derived_metrics=improved_metrics,
        )
        assert report_improved.overall_improvement is True

        # Test regression case
        regressed_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-7000)
        )
        report_regressed = generate_diff_report(
            baseline_case_id="baseline_0_0",
            derived_case_id="derived_regressed",
            eco_name="eco_regressed",
            baseline_metrics=baseline_metrics,
            derived_metrics=regressed_metrics,
        )
        assert report_regressed.overall_improvement is False

        # Filter to only improvements for survivor selection
        all_reports = [report_improved, report_regressed]
        survivors = [r for r in all_reports if r.overall_improvement]
        assert len(survivors) == 1
        assert survivors[0].eco_name == "eco_improved"


class TestDiffReportIntegration:
    """Integration tests for diff report generation workflow."""

    def test_end_to_end_diff_report_workflow(self):
        """Test complete workflow: execute baseline, execute derived, generate diff."""
        # Step 1: Execute baseline Case
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-5000,
                tns_ps=-50000,
                failing_endpoints=10,
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=100,
                hot_ratio=0.10,
                max_overflow=50,
            )
        )

        # Step 2: Execute derived Case with ECO applied
        derived_metrics = TrialMetrics(
            timing=TimingMetrics(
                wns_ps=-3000,
                tns_ps=-30000,
                failing_endpoints=5,
            ),
            congestion=CongestionMetrics(
                bins_total=1000,
                bins_hot=75,
                hot_ratio=0.075,
                max_overflow=30,
            )
        )

        # Step 3: Generate diff report
        report = generate_diff_report(
            baseline_case_id="nangate45_baseline",
            derived_case_id="nangate45_buffer_inserted",
            eco_name="buffer_insertion",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Step 4: Verify diff report shows improvements
        assert report.overall_improvement is True
        assert report.wns_delta.improved is True
        assert report.tns_delta.improved is True
        assert report.failing_endpoints_delta.improved is True
        assert report.hot_ratio_delta.improved is True

        # Step 5: Save diff report to Case artifacts
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_dir = Path(tmpdir) / "artifacts" / "nangate45_buffer_inserted"
            save_diff_report(report, artifact_dir)

            # Step 6: Verify diff report is in Case artifacts
            assert (artifact_dir / "diff_report.json").exists()
            assert (artifact_dir / "diff_report.txt").exists()

            # Verify JSON content
            with open(artifact_dir / "diff_report.json") as f:
                data = json.load(f)
                assert data["overall_improvement"] is True
                assert data["timing_deltas"]["wns"]["delta"] == 2000

    def test_diff_report_used_for_survivor_ranking(self):
        """Test using diff reports to rank and select survivors."""
        baseline_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-5000)
        )

        # Generate diff reports for multiple ECO trials
        eco_trials = [
            ("eco_A", -2000),  # Best
            ("eco_B", -3500),  # Good
            ("eco_C", -4000),  # Okay
            ("eco_D", -6000),  # Regression
            ("eco_E", -3000),  # Good
        ]

        reports = []
        for eco_name, derived_wns in eco_trials:
            derived_metrics = TrialMetrics(
                timing=TimingMetrics(wns_ps=derived_wns)
            )
            report = generate_diff_report(
                baseline_case_id="baseline_0_0",
                derived_case_id=f"derived_{eco_name}",
                eco_name=eco_name,
                baseline_metrics=baseline_metrics,
                derived_metrics=derived_metrics,
            )
            reports.append(report)

        # Rank by WNS improvement
        ranked = sorted(
            reports,
            key=lambda r: r.wns_delta.delta if r.wns_delta else float('-inf'),
            reverse=True
        )

        # Select top 3 survivors
        survivor_count = 3
        survivors = ranked[:survivor_count]

        # Verify survivors are the best 3
        assert len(survivors) == 3
        assert survivors[0].eco_name == "eco_A"
        assert survivors[1].eco_name == "eco_E"
        assert survivors[2].eco_name == "eco_B"

        # Verify regression was not selected
        survivor_names = [s.eco_name for s in survivors]
        assert "eco_D" not in survivor_names
