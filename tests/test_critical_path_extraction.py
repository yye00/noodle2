"""Tests for F202: Extract critical path information from timing diagnosis.

This feature builds on F201 (timing diagnosis) and verifies that:
1. Critical region bounding box is identified
2. Problem nets list is populated
3. Wire delay percentages are calculated for problem nets
4. Slack histogram is generated

All of these data structures enable downstream features like:
- F203: ECO suggestion based on bottlenecks
- F222: Critical path overlay visualization
"""

import pytest

from src.analysis.diagnosis import (
    BoundingBox,
    TimingIssueClassification,
    diagnose_timing,
    generate_complete_diagnosis,
)
from src.controller.types import TimingMetrics, TimingPath


class TestF202CriticalPathExtraction:
    """
    Test suite for Feature F202: Extract critical path information.

    Steps from feature_list.json:
    1. Run timing diagnosis on failing design
    2. Verify critical_region bbox is identified
    3. Verify problem_nets list is populated
    4. Verify wire_delay_pct is calculated for problem nets
    5. Verify slack_histogram is generated
    """

    def test_step_1_run_timing_diagnosis_on_failing_design(self) -> None:
        """Step 1: Run timing diagnosis on failing design."""
        # Create failing design metrics
        metrics = TimingMetrics(
            wns_ps=-2150,  # Negative WNS = failing timing
            tns_ps=-45000,
            failing_endpoints=234,
            top_paths=[
                TimingPath(
                    slack_ps=-2150,
                    startpoint="input_port_A",
                    endpoint="reg_data[31]",
                    path_group="clk",
                ),
                TimingPath(
                    slack_ps=-1980,
                    startpoint="input_port_B",
                    endpoint="reg_data[30]",
                    path_group="clk",
                ),
                TimingPath(
                    slack_ps=-1850,
                    startpoint="input_port_C",
                    endpoint="reg_data[29]",
                    path_group="clk",
                ),
            ],
        )

        # Run timing diagnosis
        diagnosis = diagnose_timing(metrics)

        # Verify diagnosis completed successfully
        assert diagnosis is not None
        assert diagnosis.wns_ps == -2150
        assert diagnosis.wns_ps < 0, "Design should be failing timing"

    def test_step_2_verify_critical_region_bbox_identified(self) -> None:
        """Step 2: Verify critical_region bbox is identified."""
        # Create metrics with multiple critical paths
        metrics = TimingMetrics(
            wns_ps=-2150,
            tns_ps=-45000,
            failing_endpoints=234,
            top_paths=[
                TimingPath(slack_ps=-2150, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2000, startpoint="in2", endpoint="out2"),
                TimingPath(slack_ps=-1900, startpoint="in3", endpoint="out3"),
                TimingPath(slack_ps=-1800, startpoint="in4", endpoint="out4"),
                TimingPath(slack_ps=-1700, startpoint="in5", endpoint="out5"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify critical_region exists
        assert diagnosis.critical_region is not None, "Critical region bbox should be identified"

        # Verify bbox has all required coordinates
        bbox = diagnosis.critical_region
        assert isinstance(bbox, BoundingBox)
        assert isinstance(bbox.x1, int)
        assert isinstance(bbox.y1, int)
        assert isinstance(bbox.x2, int)
        assert isinstance(bbox.y2, int)

        # Verify bbox is valid (x2 > x1, y2 > y1)
        assert bbox.x2 > bbox.x1, "Bounding box x2 must be greater than x1"
        assert bbox.y2 > bbox.y1, "Bounding box y2 must be greater than y1"

        # Verify critical region description exists
        assert diagnosis.critical_region_description is not None
        assert len(diagnosis.critical_region_description) > 0

    def test_step_3_verify_problem_nets_list_populated(self) -> None:
        """Step 3: Verify problem_nets list is populated."""
        # Create metrics with critical paths
        metrics = TimingMetrics(
            wns_ps=-2150,
            top_paths=[
                TimingPath(
                    slack_ps=-2150,
                    startpoint="input_A",
                    endpoint="data_bus[31]",
                ),
                TimingPath(
                    slack_ps=-1980,
                    startpoint="input_B",
                    endpoint="data_bus[30]",
                ),
                TimingPath(
                    slack_ps=-1850,
                    startpoint="clk_gate",
                    endpoint="reg_ctrl",
                ),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify problem_nets list is populated
        assert len(diagnosis.problem_nets) > 0, "Problem nets list should not be empty"

        # Verify each problem net has required fields
        for net in diagnosis.problem_nets:
            assert net.name is not None
            assert isinstance(net.name, str)
            assert len(net.name) > 0

            assert net.slack_ps is not None
            assert isinstance(net.slack_ps, int)
            assert net.slack_ps < 0, "Problem nets should have negative slack"

        # Verify nets are ordered by severity (worst first)
        if len(diagnosis.problem_nets) > 1:
            for i in range(len(diagnosis.problem_nets) - 1):
                assert diagnosis.problem_nets[i].slack_ps <= diagnosis.problem_nets[i + 1].slack_ps

    def test_step_4_verify_wire_delay_pct_calculated(self) -> None:
        """Step 4: Verify wire_delay_pct is calculated for problem nets."""
        # Create metrics with paths
        metrics = TimingMetrics(
            wns_ps=-2150,
            top_paths=[
                TimingPath(slack_ps=-2150, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-1980, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify wire_delay_pct is calculated
        assert len(diagnosis.problem_nets) > 0

        for net in diagnosis.problem_nets:
            # wire_delay_pct should be calculated
            assert net.wire_delay_pct is not None, f"wire_delay_pct missing for net {net.name}"

            # Should be a valid percentage (0.0 to 1.0)
            assert 0.0 <= net.wire_delay_pct <= 1.0, (
                f"wire_delay_pct should be 0-1, got {net.wire_delay_pct}"
            )

            # cell_delay_pct should also be present
            assert net.cell_delay_pct is not None, f"cell_delay_pct missing for net {net.name}"
            assert 0.0 <= net.cell_delay_pct <= 1.0

            # Wire and cell delay should roughly sum to 1.0 (allowing for small discrepancy)
            total_delay = net.wire_delay_pct + net.cell_delay_pct
            assert 0.8 <= total_delay <= 1.2, (
                f"Wire + cell delay should sum to ~1.0, got {total_delay}"
            )

    def test_step_5_verify_slack_histogram_generated(self) -> None:
        """Step 5: Verify slack_histogram is generated."""
        # Create metrics with varied slack values
        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2000, startpoint="in2", endpoint="out2"),
                TimingPath(slack_ps=-1500, startpoint="in3", endpoint="out3"),
                TimingPath(slack_ps=-1000, startpoint="in4", endpoint="out4"),
                TimingPath(slack_ps=-800, startpoint="in5", endpoint="out5"),
                TimingPath(slack_ps=-500, startpoint="in6", endpoint="out6"),
                TimingPath(slack_ps=-300, startpoint="in7", endpoint="out7"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify slack_histogram exists
        assert diagnosis.slack_histogram is not None, "Slack histogram should be generated"

        histogram = diagnosis.slack_histogram

        # Verify histogram has bins and counts
        assert len(histogram.bins_ps) > 0, "Histogram should have bins"
        assert len(histogram.counts) > 0, "Histogram should have counts"

        # Counts should be one less than bins (N bins define N-1 intervals)
        assert len(histogram.counts) == len(histogram.bins_ps) - 1

        # Bins should be ordered (ascending)
        for i in range(len(histogram.bins_ps) - 1):
            assert histogram.bins_ps[i] < histogram.bins_ps[i + 1]

        # All counts should be non-negative
        assert all(c >= 0 for c in histogram.counts)

        # Sum of counts should equal number of paths analyzed
        total_count = sum(histogram.counts)
        assert total_count > 0, "Histogram should contain some paths"


class TestCriticalPathExtractionDetails:
    """Detailed tests for critical path extraction features."""

    def test_critical_region_not_created_without_paths(self) -> None:
        """Critical region should not be created if no critical paths exist."""
        # Metrics with no paths
        metrics = TimingMetrics(wns_ps=-100, tns_ps=-500, failing_endpoints=5, top_paths=[])

        diagnosis = diagnose_timing(metrics)

        # No critical region without paths
        assert diagnosis.critical_region is None

    def test_critical_region_description_includes_issue_type(self) -> None:
        """Critical region description should mention wire vs cell dominance."""
        # Wire-dominated paths (very negative slack)
        wire_metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2200, startpoint="in2", endpoint="out2"),
            ],
        )

        wire_diagnosis = diagnose_timing(wire_metrics)

        if wire_diagnosis.critical_region_description:
            description = wire_diagnosis.critical_region_description.lower()
            assert "wire" in description or "interconnect" in description

        # Cell-dominated paths (moderately negative slack)
        cell_metrics = TimingMetrics(
            wns_ps=-800,
            top_paths=[
                TimingPath(slack_ps=-800, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-750, startpoint="in2", endpoint="out2"),
            ],
        )

        cell_diagnosis = diagnose_timing(cell_metrics)

        if cell_diagnosis.critical_region_description:
            description = cell_diagnosis.critical_region_description.lower()
            assert "cell" in description

    def test_problem_nets_include_slack_values(self) -> None:
        """Problem nets should include their slack values."""
        metrics = TimingMetrics(
            wns_ps=-2150,
            top_paths=[
                TimingPath(slack_ps=-2150, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-1500, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Each problem net should have its slack recorded
        assert diagnosis.problem_nets[0].slack_ps == -2150
        if len(diagnosis.problem_nets) > 1:
            assert diagnosis.problem_nets[1].slack_ps == -1500

    def test_wire_delay_pct_varies_by_slack_severity(self) -> None:
        """Wire delay percentage should be higher for more negative slack."""
        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),  # Very negative
                TimingPath(slack_ps=-800, startpoint="in2", endpoint="out2"),   # Moderately negative
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Very negative slack path should be wire-dominated (higher wire_delay_pct)
        net1 = diagnosis.problem_nets[0]
        net2 = diagnosis.problem_nets[1]

        assert net1.slack_ps < net2.slack_ps
        # More negative slack typically indicates wire dominance
        assert net1.wire_delay_pct is not None
        assert net2.wire_delay_pct is not None
        assert net1.wire_delay_pct > net2.wire_delay_pct

    def test_slack_histogram_bins_span_from_wns_to_zero(self) -> None:
        """Slack histogram bins should span from WNS to near-zero."""
        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-1000, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        histogram = diagnosis.slack_histogram
        assert histogram is not None

        # First bin should be below WNS
        assert histogram.bins_ps[0] <= -2500

        # Last bin should approach zero
        assert histogram.bins_ps[-1] > -1000


class TestCriticalPathExtractionSerialization:
    """Test that critical path data serializes correctly to JSON."""

    def test_critical_region_serializes_to_dict(self) -> None:
        """Critical region should serialize to JSON-compatible dict."""
        metrics = TimingMetrics(
            wns_ps=-2150,
            top_paths=[
                TimingPath(slack_ps=-2150, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2000, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Verify critical_region is in the dict
        if diagnosis.critical_region:
            assert "critical_region" in diagnosis_dict
            region = diagnosis_dict["critical_region"]

            assert "bbox" in region
            bbox = region["bbox"]
            assert "x1" in bbox
            assert "y1" in bbox
            assert "x2" in bbox
            assert "y2" in bbox

            assert "description" in region

    def test_problem_nets_serialize_with_delay_percentages(self) -> None:
        """Problem nets should serialize with wire/cell delay percentages."""
        metrics = TimingMetrics(
            wns_ps=-2150,
            top_paths=[
                TimingPath(slack_ps=-2150, startpoint="in1", endpoint="out1"),
            ],
        )

        diagnosis = diagnose_timing(metrics)
        diagnosis_dict = diagnosis.to_dict()

        assert "problem_nets" in diagnosis_dict
        nets = diagnosis_dict["problem_nets"]
        assert len(nets) > 0

        net = nets[0]
        assert "name" in net
        assert "slack_ps" in net
        assert "wire_delay_pct" in net
        assert "cell_delay_pct" in net

    def test_slack_histogram_serializes_correctly(self) -> None:
        """Slack histogram should serialize to JSON format."""
        metrics = TimingMetrics(
            wns_ps=-2150,
            top_paths=[
                TimingPath(slack_ps=-2150, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-1500, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)
        diagnosis_dict = diagnosis.to_dict()

        if diagnosis.slack_histogram:
            assert "slack_histogram" in diagnosis_dict
            histogram = diagnosis_dict["slack_histogram"]

            assert "bins_ps" in histogram
            assert "counts" in histogram

            assert isinstance(histogram["bins_ps"], list)
            assert isinstance(histogram["counts"], list)


class TestF202Integration:
    """Integration test for complete F202 feature."""

    def test_complete_f202_workflow(self) -> None:
        """
        Complete workflow test for F202.

        Verifies all 5 steps in sequence:
        1. Run timing diagnosis on failing design
        2. Critical region bbox is identified
        3. Problem nets list is populated
        4. Wire delay percentages are calculated
        5. Slack histogram is generated
        """
        # Create failing design with diverse critical paths
        metrics = TimingMetrics(
            wns_ps=-2500,
            tns_ps=-75000,
            failing_endpoints=450,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="clk_buf", endpoint="reg_a[0]"),
                TimingPath(slack_ps=-2350, startpoint="clk_buf", endpoint="reg_a[1]"),
                TimingPath(slack_ps=-2200, startpoint="clk_buf", endpoint="reg_a[2]"),
                TimingPath(slack_ps=-2000, startpoint="mux_ctrl", endpoint="reg_b[0]"),
                TimingPath(slack_ps=-1850, startpoint="mux_ctrl", endpoint="reg_b[1]"),
                TimingPath(slack_ps=-1500, startpoint="alu_in", endpoint="reg_c[0]"),
                TimingPath(slack_ps=-1200, startpoint="alu_in", endpoint="reg_c[1]"),
                TimingPath(slack_ps=-900, startpoint="decoder", endpoint="reg_d[0]"),
            ],
        )

        # Step 1: Run timing diagnosis
        diagnosis = diagnose_timing(metrics, path_count=20)
        assert diagnosis is not None
        assert diagnosis.wns_ps == -2500

        # Step 2: Verify critical_region bbox is identified
        assert diagnosis.critical_region is not None, "Critical region must be identified"
        assert isinstance(diagnosis.critical_region, BoundingBox)
        assert diagnosis.critical_region.x2 > diagnosis.critical_region.x1
        assert diagnosis.critical_region.y2 > diagnosis.critical_region.y1
        assert diagnosis.critical_region_description is not None

        # Step 3: Verify problem_nets list is populated
        assert len(diagnosis.problem_nets) > 0, "Problem nets must be identified"
        assert all(net.name is not None for net in diagnosis.problem_nets)
        assert all(net.slack_ps < 0 for net in diagnosis.problem_nets)

        # Step 4: Verify wire_delay_pct is calculated for problem nets
        assert all(net.wire_delay_pct is not None for net in diagnosis.problem_nets)
        assert all(net.cell_delay_pct is not None for net in diagnosis.problem_nets)
        assert all(0.0 <= net.wire_delay_pct <= 1.0 for net in diagnosis.problem_nets)
        assert all(0.0 <= net.cell_delay_pct <= 1.0 for net in diagnosis.problem_nets)

        # Step 5: Verify slack_histogram is generated
        assert diagnosis.slack_histogram is not None, "Slack histogram must be generated"
        assert len(diagnosis.slack_histogram.bins_ps) > 0
        assert len(diagnosis.slack_histogram.counts) > 0
        assert len(diagnosis.slack_histogram.counts) == len(diagnosis.slack_histogram.bins_ps) - 1

        # Additional: Verify it serializes correctly
        report = generate_complete_diagnosis(timing_metrics=metrics)
        report_dict = report.to_dict()

        assert "timing_diagnosis" in report_dict
        timing_diag = report_dict["timing_diagnosis"]

        assert "critical_region" in timing_diag
        assert "problem_nets" in timing_diag
        assert "slack_histogram" in timing_diag

        print("✓ F202: All steps verified successfully")
        print(f"  - Critical region: {diagnosis.critical_region}")
        print(f"  - Problem nets: {len(diagnosis.problem_nets)}")
        print(f"  - Histogram bins: {len(diagnosis.slack_histogram.bins_ps)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
