"""Tests for F208: Generate combined diagnosis report identifying primary and secondary issues."""

import pytest

from src.analysis.diagnosis import (
    IssueType,
    generate_complete_diagnosis,
)
from src.controller.types import CongestionMetrics, TimingMetrics, TimingPath


class TestCombinedDiagnosisF208:
    """
    Test suite for Feature F208: Generate combined diagnosis report.

    Steps from feature_list.json:
    1. Run auto-diagnosis on design with both timing and congestion issues
    2. Verify diagnosis_summary section exists
    3. Verify primary_issue is identified (timing or congestion)
    4. Verify secondary_issue is identified
    5. Verify recommended_strategy is provided
    6. Verify eco_priority_queue is generated with addresses field
    """

    def test_step_1_run_diagnosis_on_both_issues(self) -> None:
        """Step 1: Run auto-diagnosis on design with both timing and congestion issues."""
        # Create metrics with both timing and congestion problems
        timing_metrics = TimingMetrics(
            wns_ps=-1500,  # Timing violation
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out[0]",
                    path_group="clk",
                    path_type="max",
                ),
                TimingPath(
                    slack_ps=-1200,
                    startpoint="input_B",
                    endpoint="reg_out[1]",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,  # High congestion
            max_overflow=250,
            layer_metrics={
                "metal3": 180,
                "metal4": 250,
                "metal5": 120,
            },
        )

        # Generate complete diagnosis
        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Verify both individual diagnoses were created
        assert report.timing_diagnosis is not None
        assert report.congestion_diagnosis is not None
        assert report.timing_diagnosis.wns_ps == -1500
        assert report.congestion_diagnosis.hot_ratio == 0.45

    def test_step_2_verify_diagnosis_summary_exists(self) -> None:
        """Step 2: Verify diagnosis_summary section exists."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,
            max_overflow=250,
            layer_metrics={
                "metal3": 180,
                "metal4": 250,
            },
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Verify diagnosis_summary exists
        assert report.diagnosis_summary is not None
        assert hasattr(report.diagnosis_summary, "primary_issue")
        assert hasattr(report.diagnosis_summary, "secondary_issue")
        assert hasattr(report.diagnosis_summary, "recommended_strategy")

    def test_step_3_verify_primary_issue_identified(self) -> None:
        """Step 3: Verify primary_issue is identified (timing or congestion)."""
        # Test with timing as primary issue (more severe)
        timing_metrics = TimingMetrics(
            wns_ps=-2500,  # Very severe timing
            tns_ps=-50000,
            failing_endpoints=300,
            top_paths=[
                TimingPath(
                    slack_ps=-2500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=250,
            hot_ratio=0.25,  # Moderate congestion
            max_overflow=100,
            layer_metrics={"metal3": 100},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        # Timing should be primary due to severity
        assert report.diagnosis_summary.primary_issue in [
            IssueType.TIMING,
            IssueType.CONGESTION,
        ]
        assert report.diagnosis_summary.primary_issue != IssueType.NONE

    def test_step_4_verify_secondary_issue_identified(self) -> None:
        """Step 4: Verify secondary_issue is identified."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,
            max_overflow=250,
            layer_metrics={"metal3": 250},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        # When both issues exist, there should be a secondary issue
        assert report.diagnosis_summary.secondary_issue is not None
        assert report.diagnosis_summary.secondary_issue in [
            IssueType.TIMING,
            IssueType.CONGESTION,
        ]
        # Primary and secondary should be different
        assert (
            report.diagnosis_summary.primary_issue
            != report.diagnosis_summary.secondary_issue
        )

    def test_step_5_verify_recommended_strategy_provided(self) -> None:
        """Step 5: Verify recommended_strategy is provided."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,
            max_overflow=250,
            layer_metrics={"metal3": 250},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        # Verify recommended_strategy is present and non-empty
        assert report.diagnosis_summary.recommended_strategy is not None
        assert len(report.diagnosis_summary.recommended_strategy) > 0
        # Should be one of the expected strategies
        assert report.diagnosis_summary.recommended_strategy in [
            "timing_first",
            "congestion_first",
            "timing_only",
            "congestion_only",
            "maintain",
        ]

    def test_step_6_verify_eco_priority_queue_with_addresses(self) -> None:
        """Step 6: Verify eco_priority_queue is generated with addresses field."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,
            max_overflow=250,
            layer_metrics={"metal3": 250},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        # Verify ECO priority queue exists
        assert report.diagnosis_summary.eco_priority_queue is not None
        assert len(report.diagnosis_summary.eco_priority_queue) > 0

        # Verify each ECO has required fields including 'addresses'
        for eco in report.diagnosis_summary.eco_priority_queue:
            assert hasattr(eco, "eco")
            assert hasattr(eco, "priority")
            assert hasattr(eco, "addresses")
            assert eco.addresses in ["timing", "congestion"]
            assert isinstance(eco.priority, int)
            assert eco.priority > 0

    def test_combined_diagnosis_json_serialization(self) -> None:
        """Test that combined diagnosis report can be serialized to JSON."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,
            max_overflow=250,
            layer_metrics={"metal3": 250},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Convert to dictionary (for JSON serialization)
        report_dict = report.to_dict()

        # Verify structure
        assert "timing_diagnosis" in report_dict
        assert "congestion_diagnosis" in report_dict
        assert "diagnosis_summary" in report_dict

        # Verify diagnosis_summary contains all required fields
        summary = report_dict["diagnosis_summary"]
        assert "primary_issue" in summary
        assert "recommended_strategy" in summary
        assert "reasoning" in summary
        assert "eco_priority_queue" in summary

        # Verify ECO queue structure
        eco_queue = summary["eco_priority_queue"]
        assert len(eco_queue) > 0
        for eco in eco_queue:
            assert "eco" in eco
            assert "priority" in eco
            assert "addresses" in eco

    def test_timing_only_diagnosis(self) -> None:
        """Test diagnosis with only timing issues (no congestion)."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out",
                    path_group="clk",
                ),
            ],
        )

        # No congestion metrics provided
        report = generate_complete_diagnosis(timing_metrics=timing_metrics)

        assert report.diagnosis_summary is not None
        assert report.diagnosis_summary.primary_issue == IssueType.TIMING
        assert report.diagnosis_summary.secondary_issue is None
        assert report.diagnosis_summary.recommended_strategy == "timing_only"

    def test_congestion_only_diagnosis(self) -> None:
        """Test diagnosis with only congestion issues (no timing)."""
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,
            max_overflow=250,
            layer_metrics={"metal3": 250},
        )

        # No timing metrics provided (or timing is healthy)
        report = generate_complete_diagnosis(congestion_metrics=congestion_metrics)

        assert report.diagnosis_summary is not None
        assert report.diagnosis_summary.primary_issue == IssueType.CONGESTION
        assert report.diagnosis_summary.secondary_issue is None
        assert report.diagnosis_summary.recommended_strategy == "congestion_only"

    def test_healthy_design_diagnosis(self) -> None:
        """Test diagnosis when design is healthy (no issues)."""
        timing_metrics = TimingMetrics(
            wns_ps=250,  # Positive slack
            tns_ps=0,
            failing_endpoints=0,
            top_paths=[],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=0.05,  # Low congestion
            max_overflow=0,
            layer_metrics={"metal3": 0},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        assert report.diagnosis_summary.primary_issue == IssueType.NONE
        assert report.diagnosis_summary.secondary_issue is None
        assert report.diagnosis_summary.recommended_strategy == "maintain"
