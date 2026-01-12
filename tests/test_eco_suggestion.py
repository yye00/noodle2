"""Tests for F203: Timing diagnosis suggests appropriate ECOs based on bottleneck type.

This feature verifies that the timing diagnosis system automatically suggests
appropriate ECOs based on the dominant issue type (wire vs cell dominated).
"""

import pytest

from src.analysis.diagnosis import (
    TimingIssueClassification,
    diagnose_timing,
)
from src.controller.types import TimingMetrics, TimingPath


class TestF203ECOSuggestion:
    """
    Test suite for Feature F203: ECO suggestion based on bottleneck type.

    Steps from feature_list.json:
    1. Run timing diagnosis on wire-dominated failing design
    2. Verify suggested_ecos includes insert_buffers with priority 1
    3. Run timing diagnosis on cell-dominated failing design
    4. Verify suggested_ecos includes resize_critical_drivers
    5. Verify suggestions include reasoning
    """

    def test_step_1_run_diagnosis_on_wire_dominated_design(self) -> None:
        """Step 1: Run timing diagnosis on wire-dominated failing design."""
        # Create metrics with very negative slack (wire-dominated heuristic)
        metrics = TimingMetrics(
            wns_ps=-2500,  # Very negative WNS indicates wire issues
            tns_ps=-75000,
            failing_endpoints=450,
            top_paths=[
                # Very negative slack paths (> 1500ps) are classified as wire-dominated
                TimingPath(slack_ps=-2500, startpoint="clk_buf", endpoint="reg_a[0]"),
                TimingPath(slack_ps=-2350, startpoint="clk_buf", endpoint="reg_a[1]"),
                TimingPath(slack_ps=-2200, startpoint="clk_buf", endpoint="reg_a[2]"),
                TimingPath(slack_ps=-2000, startpoint="mux_ctrl", endpoint="reg_b[0]"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify wire-dominated classification
        assert diagnosis.dominant_issue == TimingIssueClassification.WIRE_DOMINATED
        assert diagnosis.confidence > 0.6

    def test_step_2_verify_insert_buffers_suggested_with_priority_1(self) -> None:
        """Step 2: Verify suggested_ecos includes insert_buffers with priority 1."""
        # Wire-dominated design
        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2350, startpoint="in2", endpoint="out2"),
                TimingPath(slack_ps=-2200, startpoint="in3", endpoint="out3"),
                TimingPath(slack_ps=-2000, startpoint="in4", endpoint="out4"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify ECO suggestions exist
        assert len(diagnosis.suggested_ecos) > 0, "ECO suggestions should be generated"

        # Verify insert_buffers is suggested
        eco_names = [eco.eco for eco in diagnosis.suggested_ecos]
        assert "insert_buffers" in eco_names, "insert_buffers should be suggested for wire-dominated paths"

        # Verify insert_buffers has priority 1
        insert_buffers_eco = [eco for eco in diagnosis.suggested_ecos if eco.eco == "insert_buffers"][0]
        assert insert_buffers_eco.priority == 1, "insert_buffers should have priority 1"

    def test_step_3_run_diagnosis_on_cell_dominated_design(self) -> None:
        """Step 3: Run timing diagnosis on cell-dominated failing design."""
        # Create metrics with moderately negative slack (cell-dominated heuristic)
        metrics = TimingMetrics(
            wns_ps=-800,  # Moderately negative WNS indicates cell issues
            tns_ps=-5000,
            failing_endpoints=50,
            top_paths=[
                # Moderately negative slack paths (< 1500ps) are classified as cell-dominated
                TimingPath(slack_ps=-800, startpoint="alu_in", endpoint="reg_c[0]"),
                TimingPath(slack_ps=-750, startpoint="alu_in", endpoint="reg_c[1]"),
                TimingPath(slack_ps=-700, startpoint="decoder", endpoint="reg_d[0]"),
                TimingPath(slack_ps=-650, startpoint="decoder", endpoint="reg_d[1]"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify cell-dominated classification
        assert diagnosis.dominant_issue == TimingIssueClassification.CELL_DOMINATED
        assert diagnosis.confidence > 0.6

    def test_step_4_verify_resize_critical_drivers_suggested(self) -> None:
        """Step 4: Verify suggested_ecos includes resize_critical_drivers."""
        # Cell-dominated design
        metrics = TimingMetrics(
            wns_ps=-800,
            top_paths=[
                TimingPath(slack_ps=-800, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-750, startpoint="in2", endpoint="out2"),
                TimingPath(slack_ps=-700, startpoint="in3", endpoint="out3"),
                TimingPath(slack_ps=-650, startpoint="in4", endpoint="out4"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify ECO suggestions exist
        assert len(diagnosis.suggested_ecos) > 0, "ECO suggestions should be generated"

        # Verify resize_critical_drivers is suggested
        eco_names = [eco.eco for eco in diagnosis.suggested_ecos]
        assert "resize_critical_drivers" in eco_names, (
            "resize_critical_drivers should be suggested for cell-dominated paths"
        )

        # Verify resize_critical_drivers has high priority (should be priority 1)
        resize_eco = [eco for eco in diagnosis.suggested_ecos if eco.eco == "resize_critical_drivers"][0]
        assert resize_eco.priority == 1, "resize_critical_drivers should have priority 1"

    def test_step_5_verify_suggestions_include_reasoning(self) -> None:
        """Step 5: Verify suggestions include reasoning."""
        # Test with wire-dominated design
        wire_metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2000, startpoint="in2", endpoint="out2"),
            ],
        )

        wire_diagnosis = diagnose_timing(wire_metrics)

        # Verify all ECO suggestions have reasoning
        assert all(eco.reason is not None for eco in wire_diagnosis.suggested_ecos)
        assert all(len(eco.reason) > 0 for eco in wire_diagnosis.suggested_ecos)

        # Verify reasoning mentions wire dominance
        insert_buffers_eco = [eco for eco in wire_diagnosis.suggested_ecos if eco.eco == "insert_buffers"][0]
        assert "wire" in insert_buffers_eco.reason.lower(), (
            "Reasoning should mention wire dominance"
        )

        # Test with cell-dominated design
        cell_metrics = TimingMetrics(
            wns_ps=-800,
            top_paths=[
                TimingPath(slack_ps=-800, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-750, startpoint="in2", endpoint="out2"),
            ],
        )

        cell_diagnosis = diagnose_timing(cell_metrics)

        # Verify all ECO suggestions have reasoning
        assert all(eco.reason is not None for eco in cell_diagnosis.suggested_ecos)
        assert all(len(eco.reason) > 0 for eco in cell_diagnosis.suggested_ecos)

        # Verify reasoning mentions cell dominance
        resize_eco = [eco for eco in cell_diagnosis.suggested_ecos if eco.eco == "resize_critical_drivers"][0]
        assert "cell" in resize_eco.reason.lower(), (
            "Reasoning should mention cell dominance"
        )


class TestECOSuggestionDetails:
    """Detailed tests for ECO suggestion features."""

    def test_wire_dominated_suggests_buffer_insertion(self) -> None:
        """Wire-dominated paths should suggest buffer insertion."""
        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2000, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Should be wire-dominated
        assert diagnosis.dominant_issue == TimingIssueClassification.WIRE_DOMINATED

        # Should suggest insert_buffers
        eco_names = [eco.eco for eco in diagnosis.suggested_ecos]
        assert "insert_buffers" in eco_names

    def test_cell_dominated_suggests_cell_resizing(self) -> None:
        """Cell-dominated paths should suggest cell resizing."""
        metrics = TimingMetrics(
            wns_ps=-800,
            top_paths=[
                TimingPath(slack_ps=-800, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-750, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Should be cell-dominated
        assert diagnosis.dominant_issue == TimingIssueClassification.CELL_DOMINATED

        # Should suggest resize_critical_drivers
        eco_names = [eco.eco for eco in diagnosis.suggested_ecos]
        assert "resize_critical_drivers" in eco_names

    def test_eco_suggestions_have_addresses_field(self) -> None:
        """ECO suggestions should indicate what they address (timing/congestion)."""
        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # All ECO suggestions should have addresses field
        for eco in diagnosis.suggested_ecos:
            assert eco.addresses is not None
            assert eco.addresses in ["timing", "congestion", "both"]

        # For timing diagnosis, ECOs should address timing
        assert all(eco.addresses == "timing" for eco in diagnosis.suggested_ecos)

    def test_eco_priority_ordering(self) -> None:
        """ECO suggestions should be ordered by priority."""
        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-2000, startpoint="in2", endpoint="out2"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Verify multiple suggestions exist
        assert len(diagnosis.suggested_ecos) >= 2

        # Verify priorities are assigned
        priorities = [eco.priority for eco in diagnosis.suggested_ecos]
        assert all(p >= 1 for p in priorities)

        # First ECO should have priority 1
        assert diagnosis.suggested_ecos[0].priority == 1

    def test_mixed_issue_suggests_both_eco_types(self) -> None:
        """Mixed wire/cell issues should suggest both buffer and cell ECOs."""
        # Create paths with mixed slack values
        metrics = TimingMetrics(
            wns_ps=-1500,
            top_paths=[
                # Some wire-dominated (very negative)
                TimingPath(slack_ps=-2000, startpoint="in1", endpoint="out1"),
                TimingPath(slack_ps=-1800, startpoint="in2", endpoint="out2"),
                # Some cell-dominated (moderately negative)
                TimingPath(slack_ps=-1000, startpoint="in3", endpoint="out3"),
                TimingPath(slack_ps=-900, startpoint="in4", endpoint="out4"),
                TimingPath(slack_ps=-800, startpoint="in5", endpoint="out5"),
            ],
        )

        diagnosis = diagnose_timing(metrics)

        # Should be classified as mixed
        assert diagnosis.dominant_issue == TimingIssueClassification.MIXED

        # Should suggest both types of ECOs
        eco_names = [eco.eco for eco in diagnosis.suggested_ecos]
        assert "insert_buffers" in eco_names, "Mixed issues should suggest buffer insertion"
        assert "resize_critical_drivers" in eco_names, "Mixed issues should suggest cell resizing"

    def test_eco_suggestions_serialize_to_json(self) -> None:
        """ECO suggestions should serialize to JSON format."""
        import json

        metrics = TimingMetrics(
            wns_ps=-2500,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="in1", endpoint="out1"),
            ],
        )

        diagnosis = diagnose_timing(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Should contain suggested_ecos
        assert "suggested_ecos" in diagnosis_dict

        # Should be JSON-serializable
        json_str = json.dumps(diagnosis_dict)
        assert len(json_str) > 0

        # Verify structure
        reloaded = json.loads(json_str)
        assert "suggested_ecos" in reloaded
        assert len(reloaded["suggested_ecos"]) > 0

        # Verify ECO fields
        eco = reloaded["suggested_ecos"][0]
        assert "eco" in eco
        assert "priority" in eco
        assert "reason" in eco


class TestF203Integration:
    """Integration test for complete F203 feature."""

    def test_complete_f203_workflow(self) -> None:
        """
        Complete workflow test for F203.

        Verifies all 5 steps in sequence:
        1. Wire-dominated design diagnosis
        2. insert_buffers suggested with priority 1
        3. Cell-dominated design diagnosis
        4. resize_critical_drivers suggested
        5. All suggestions include reasoning
        """
        # Step 1 & 2: Wire-dominated design
        wire_metrics = TimingMetrics(
            wns_ps=-2500,
            tns_ps=-75000,
            failing_endpoints=450,
            top_paths=[
                TimingPath(slack_ps=-2500, startpoint="clk_buf", endpoint="reg_a[0]"),
                TimingPath(slack_ps=-2350, startpoint="clk_buf", endpoint="reg_a[1]"),
                TimingPath(slack_ps=-2200, startpoint="clk_buf", endpoint="reg_a[2]"),
                TimingPath(slack_ps=-2000, startpoint="mux_ctrl", endpoint="reg_b[0]"),
            ],
        )

        wire_diagnosis = diagnose_timing(wire_metrics)

        # Verify wire-dominated classification
        assert wire_diagnosis.dominant_issue == TimingIssueClassification.WIRE_DOMINATED

        # Verify insert_buffers with priority 1
        assert len(wire_diagnosis.suggested_ecos) > 0
        assert wire_diagnosis.suggested_ecos[0].eco == "insert_buffers"
        assert wire_diagnosis.suggested_ecos[0].priority == 1
        assert wire_diagnosis.suggested_ecos[0].reason is not None
        assert len(wire_diagnosis.suggested_ecos[0].reason) > 0

        # Step 3 & 4: Cell-dominated design
        cell_metrics = TimingMetrics(
            wns_ps=-800,
            tns_ps=-5000,
            failing_endpoints=50,
            top_paths=[
                TimingPath(slack_ps=-800, startpoint="alu_in", endpoint="reg_c[0]"),
                TimingPath(slack_ps=-750, startpoint="alu_in", endpoint="reg_c[1]"),
                TimingPath(slack_ps=-700, startpoint="decoder", endpoint="reg_d[0]"),
                TimingPath(slack_ps=-650, startpoint="decoder", endpoint="reg_d[1]"),
            ],
        )

        cell_diagnosis = diagnose_timing(cell_metrics)

        # Verify cell-dominated classification
        assert cell_diagnosis.dominant_issue == TimingIssueClassification.CELL_DOMINATED

        # Verify resize_critical_drivers is suggested
        eco_names = [eco.eco for eco in cell_diagnosis.suggested_ecos]
        assert "resize_critical_drivers" in eco_names

        resize_eco = [eco for eco in cell_diagnosis.suggested_ecos if eco.eco == "resize_critical_drivers"][0]
        assert resize_eco.priority == 1
        assert resize_eco.reason is not None
        assert len(resize_eco.reason) > 0

        # Step 5: Verify all suggestions include reasoning
        for diagnosis in [wire_diagnosis, cell_diagnosis]:
            for eco in diagnosis.suggested_ecos:
                assert eco.reason is not None
                assert len(eco.reason) > 0
                assert eco.addresses == "timing"

        print("✓ F203: All steps verified successfully")
        print(f"  - Wire-dominated ECOs: {[e.eco for e in wire_diagnosis.suggested_ecos]}")
        print(f"  - Cell-dominated ECOs: {[e.eco for e in cell_diagnosis.suggested_ecos]}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
