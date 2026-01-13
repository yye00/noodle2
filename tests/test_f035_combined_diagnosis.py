"""
Tests for Feature F035: Auto-diagnosis produces combined diagnosis report prioritizing primary issue.

Verification steps from feature_list.json:
1. Create case with both timing and congestion issues
2. Run auto-diagnosis
3. Verify primary_issue is identified (timing or congestion)
4. Verify secondary_issue is identified
5. Verify ECO priority queue is generated with addresses field
6. Verify recommended strategy is provided with reasoning
"""

import pytest

from src.analysis.diagnosis import (
    IssueType,
    generate_complete_diagnosis,
)
from src.controller.types import CongestionMetrics, TimingMetrics, TimingPath


class TestF035CombinedDiagnosisPrioritization:
    """Tests for F035: Combined diagnosis report with primary/secondary prioritization."""

    def test_step_1_create_case_with_both_issues(self) -> None:
        """
        Step 1: Create case with both timing and congestion issues.

        Verify we can create metrics representing a design with both problems.
        """
        # Create timing metrics with violations
        timing_metrics = TimingMetrics(
            wns_ps=-2000,  # Severe timing violation
            tns_ps=-45000,
            failing_endpoints=200,
            top_paths=[
                TimingPath(
                    slack_ps=-2000,
                    startpoint="input_clk",
                    endpoint="reg_0/D",
                    path_group="clk",
                    path_type="max",
                ),
                TimingPath(
                    slack_ps=-1800,
                    startpoint="reg_1/Q",
                    endpoint="reg_2/D",
                    path_group="clk",
                    path_type="max",
                ),
            ],
        )

        # Create congestion metrics with hotspots
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=550,
            hot_ratio=0.55,  # Severe congestion (>0.3 is bad)
            max_overflow=300,
            layer_metrics={
                "metal2": 150,
                "metal3": 200,
                "metal4": 300,
                "metal5": 180,
            },
        )

        # Verify both metrics are problematic
        assert timing_metrics.wns_ps < 0, "Should have timing violation"
        assert congestion_metrics.hot_ratio > 0.3, "Should have congestion"

    def test_step_2_run_auto_diagnosis(self) -> None:
        """
        Step 2: Run auto-diagnosis.

        Verify that diagnosis runs successfully with both issue types.
        """
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-30000,
            failing_endpoints=120,
            top_paths=[
                TimingPath(
                    slack_ps=-1500,
                    startpoint="input_A",
                    endpoint="reg_out[0]",
                    path_group="clk",
                ),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=200,
            layer_metrics={"metal3": 150, "metal4": 200},
        )

        # Run diagnosis
        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Verify all three sections are present
        assert report.timing_diagnosis is not None
        assert report.congestion_diagnosis is not None
        assert report.diagnosis_summary is not None

    def test_step_3_verify_primary_issue_identified(self) -> None:
        """
        Step 3: Verify primary_issue is identified (timing or congestion).

        The primary issue should be the more severe problem.
        """
        # Test 1: Timing is more severe
        timing_metrics = TimingMetrics(
            wns_ps=-3000,  # Very severe
            tns_ps=-60000,
            failing_endpoints=250,
            top_paths=[
                TimingPath(slack_ps=-3000, startpoint="A", endpoint="B", path_group="clk"),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=200,  # Moderate
            hot_ratio=0.20,
            max_overflow=100,
            layer_metrics={"metal3": 100},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        assert report.diagnosis_summary.primary_issue == IssueType.TIMING

        # Test 2: Congestion is more severe
        timing_metrics_mild = TimingMetrics(
            wns_ps=-500,  # Mild
            tns_ps=-5000,
            failing_endpoints=20,
            top_paths=[
                TimingPath(slack_ps=-500, startpoint="A", endpoint="B", path_group="clk"),
            ],
        )

        congestion_metrics_severe = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,  # Very severe
            hot_ratio=0.75,
            max_overflow=400,
            layer_metrics={"metal3": 300, "metal4": 400},
        )

        report2 = generate_complete_diagnosis(
            timing_metrics=timing_metrics_mild,
            congestion_metrics=congestion_metrics_severe,
        )

        assert report2.diagnosis_summary is not None
        assert report2.diagnosis_summary.primary_issue == IssueType.CONGESTION

    def test_step_4_verify_secondary_issue_identified(self) -> None:
        """
        Step 4: Verify secondary_issue is identified.

        When both issues exist, the less severe one should be marked as secondary.
        """
        timing_metrics = TimingMetrics(
            wns_ps=-1800,  # Moderate-severe
            tns_ps=-35000,
            failing_endpoints=150,
            top_paths=[
                TimingPath(slack_ps=-1800, startpoint="A", endpoint="B", path_group="clk"),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,  # Moderate-severe
            hot_ratio=0.45,
            max_overflow=250,
            layer_metrics={"metal3": 180, "metal4": 250},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        # Both issues present, so secondary should be set
        assert report.diagnosis_summary.secondary_issue is not None
        assert report.diagnosis_summary.secondary_issue in [
            IssueType.TIMING,
            IssueType.CONGESTION,
        ]
        # Primary and secondary should be different
        assert report.diagnosis_summary.primary_issue != report.diagnosis_summary.secondary_issue

    def test_step_5_verify_eco_priority_queue_with_addresses(self) -> None:
        """
        Step 5: Verify ECO priority queue is generated with addresses field.

        The ECO queue should prioritize ECOs that address the primary issue,
        and each ECO should have an 'addresses' field indicating what it fixes.
        """
        timing_metrics = TimingMetrics(
            wns_ps=-2500,  # Primary issue
            tns_ps=-50000,
            failing_endpoints=200,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="A", endpoint="B", path_group="clk"),
                TimingPath(slack_ps=-2200, startpoint="C", endpoint="D", path_group="clk"),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=300,  # Secondary issue
            hot_ratio=0.30,
            max_overflow=150,
            layer_metrics={"metal3": 150},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        eco_queue = report.diagnosis_summary.eco_priority_queue

        # Verify ECO queue exists and has entries
        assert len(eco_queue) > 0

        # Verify all ECOs have 'addresses' field
        for eco in eco_queue:
            assert hasattr(eco, "addresses")
            assert eco.addresses in ["timing", "congestion"]

        # Verify primary issue ECOs come first (lower priority number = higher priority)
        primary_issue = report.diagnosis_summary.primary_issue
        if len(eco_queue) > 1:
            first_eco_addresses = eco_queue[0].addresses
            if primary_issue == IssueType.TIMING:
                assert first_eco_addresses == "timing"
            elif primary_issue == IssueType.CONGESTION:
                assert first_eco_addresses == "congestion"

    def test_step_6_verify_recommended_strategy_with_reasoning(self) -> None:
        """
        Step 6: Verify recommended strategy is provided with reasoning.

        The diagnosis should provide a recommended strategy (e.g., "timing_first")
        along with reasoning explaining why that strategy was chosen.
        """
        timing_metrics = TimingMetrics(
            wns_ps=-1600,
            tns_ps=-32000,
            failing_endpoints=140,
            top_paths=[
                TimingPath(slack_ps=-1600, startpoint="A", endpoint="B", path_group="clk"),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=350,
            hot_ratio=0.35,
            max_overflow=180,
            layer_metrics={"metal3": 120, "metal4": 180},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None

        # Verify recommended_strategy exists
        assert hasattr(report.diagnosis_summary, "recommended_strategy")
        assert report.diagnosis_summary.recommended_strategy is not None
        assert len(report.diagnosis_summary.recommended_strategy) > 0

        # Verify it's one of the expected strategies
        assert report.diagnosis_summary.recommended_strategy in [
            "timing_first",
            "congestion_first",
            "timing_only",
            "congestion_only",
            "maintain",
        ]

        # Verify reasoning exists and is meaningful
        assert hasattr(report.diagnosis_summary, "reasoning")
        assert report.diagnosis_summary.reasoning is not None
        assert len(report.diagnosis_summary.reasoning) > 20  # Should be a real explanation

        # Reasoning should mention the metrics
        reasoning_lower = report.diagnosis_summary.reasoning.lower()
        assert "wns" in reasoning_lower or "timing" in reasoning_lower or "congestion" in reasoning_lower


class TestF035EdgeCases:
    """Edge case tests for combined diagnosis."""

    def test_timing_only_no_secondary(self) -> None:
        """Test diagnosis with only timing issues."""
        timing_metrics = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-30000,
            failing_endpoints=100,
            top_paths=[
                TimingPath(slack_ps=-1500, startpoint="A", endpoint="B", path_group="clk"),
            ],
        )

        # No congestion (hot_ratio < 0.15)
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=100,
            hot_ratio=0.10,
            max_overflow=0,
            layer_metrics={},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        assert report.diagnosis_summary.primary_issue == IssueType.TIMING
        assert report.diagnosis_summary.secondary_issue is None
        assert report.diagnosis_summary.recommended_strategy == "timing_only"

    def test_congestion_only_no_secondary(self) -> None:
        """Test diagnosis with only congestion issues."""
        # No timing violation
        timing_metrics = TimingMetrics(
            wns_ps=100,  # Positive slack
            tns_ps=0,
            failing_endpoints=0,
            top_paths=[],
        )

        # Severe congestion
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=600,
            hot_ratio=0.60,
            max_overflow=350,
            layer_metrics={"metal3": 250, "metal4": 350},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        assert report.diagnosis_summary.primary_issue == IssueType.CONGESTION
        assert report.diagnosis_summary.secondary_issue is None
        assert report.diagnosis_summary.recommended_strategy == "congestion_only"

    def test_healthy_design(self) -> None:
        """Test diagnosis on a healthy design with no issues."""
        # Met timing
        timing_metrics = TimingMetrics(
            wns_ps=500,  # Positive
            tns_ps=0,
            failing_endpoints=0,
            top_paths=[],
        )

        # Low congestion
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=0.05,
            max_overflow=0,
            layer_metrics={},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        assert report.diagnosis_summary is not None
        assert report.diagnosis_summary.primary_issue == IssueType.NONE
        assert report.diagnosis_summary.secondary_issue is None
        assert report.diagnosis_summary.recommended_strategy == "maintain"

    def test_json_serialization(self) -> None:
        """Test that combined diagnosis can be serialized to JSON."""
        timing_metrics = TimingMetrics(
            wns_ps=-1200,
            tns_ps=-25000,
            failing_endpoints=90,
            top_paths=[
                TimingPath(slack_ps=-1200, startpoint="A", endpoint="B", path_group="clk"),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=320,
            hot_ratio=0.32,
            max_overflow=160,
            layer_metrics={"metal3": 100, "metal4": 160},
        )

        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Convert to dict
        report_dict = report.to_dict()

        # Verify structure
        assert "diagnosis_summary" in report_dict
        summary = report_dict["diagnosis_summary"]
        assert "primary_issue" in summary
        assert "secondary_issue" in summary
        assert "recommended_strategy" in summary
        assert "reasoning" in summary
        assert "eco_priority_queue" in summary

        # Verify ECO queue structure
        if summary["eco_priority_queue"]:
            first_eco = summary["eco_priority_queue"][0]
            assert "eco" in first_eco
            assert "priority" in first_eco
            assert "addresses" in first_eco

    def test_integration_complete_workflow(self) -> None:
        """
        Integration test: Complete F035 workflow.

        This verifies the entire F035 feature end-to-end:
        1. Create case with both issues
        2. Run diagnosis
        3. Verify all required fields
        """
        # Step 1: Create metrics with both issues
        timing_metrics = TimingMetrics(
            wns_ps=-1750,
            tns_ps=-38000,
            failing_endpoints=165,
            top_paths=[
                TimingPath(slack_ps=-1750, startpoint="in_0", endpoint="reg_0/D", path_group="clk"),
                TimingPath(slack_ps=-1650, startpoint="reg_1/Q", endpoint="reg_2/D", path_group="clk"),
            ],
        )

        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=420,
            hot_ratio=0.42,
            max_overflow=230,
            layer_metrics={"metal2": 140, "metal3": 190, "metal4": 230},
        )

        # Step 2: Run diagnosis
        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            congestion_metrics=congestion_metrics,
        )

        # Step 3: Verify all required fields
        assert report.diagnosis_summary is not None
        summary = report.diagnosis_summary

        # Verify primary issue
        assert summary.primary_issue in [IssueType.TIMING, IssueType.CONGESTION]

        # Verify secondary issue
        assert summary.secondary_issue in [IssueType.TIMING, IssueType.CONGESTION]
        assert summary.primary_issue != summary.secondary_issue

        # Verify ECO priority queue with addresses
        assert len(summary.eco_priority_queue) > 0
        for eco in summary.eco_priority_queue:
            assert eco.addresses in ["timing", "congestion"]

        # Verify recommended strategy with reasoning
        assert summary.recommended_strategy in [
            "timing_first",
            "congestion_first",
            "timing_only",
            "congestion_only",
        ]
        assert len(summary.reasoning) > 20
        assert "WNS" in summary.reasoning or "wns" in summary.reasoning.lower()
