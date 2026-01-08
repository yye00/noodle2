"""
Tests for timing violation detection and classification.

Feature: Detect and classify timing violations (setup, hold)
"""

import pytest

from src.parsers.timing import (
    parse_timing_report_content,
    parse_timing_paths,
    classify_timing_violations,
)
from src.controller.types import TimingPath, TimingViolationBreakdown


# ============================================================================
# Feature Step 1: Execute STA producing report_checks output
# ============================================================================


def test_execute_sta_with_report_checks() -> None:
    """
    Feature Step 1: Execute STA producing report_checks output.

    This test simulates executing STA and receiving report_checks output
    that contains timing path information.
    """
    # Simulated report_checks output from OpenROAD STA
    report_content = """
Startpoint: reg1/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg2/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

           -5.50   slack (VIOLATED)

wns -5.50
tns -12.30
failing endpoints: 2
"""

    # Verify we can parse this report
    metrics = parse_timing_report_content(report_content)
    assert metrics.wns_ps == -5500
    assert metrics.tns_ps == -12300
    assert metrics.failing_endpoints == 2


# ============================================================================
# Feature Step 2: Parse timing paths and identify violation types
# ============================================================================


def test_parse_timing_paths_and_identify_violations() -> None:
    """
    Feature Step 2: Parse timing paths and identify violation types.

    Parse paths from report_checks output and extract path_type information.
    """
    report_content = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Group: clk
Path Type: max
           -3.50   slack (VIOLATED)

Startpoint: reg3/Q
Endpoint: reg4/D
Path Group: clk
Path Type: min
           -1.20   slack (VIOLATED)

wns -3.50
"""

    paths = parse_timing_paths(report_content)

    # Verify we extracted both paths
    assert len(paths) == 2

    # First path: setup violation (max path)
    assert paths[0].path_type == "max"
    assert paths[0].slack_ps == -3500

    # Second path: hold violation (min path)
    assert paths[1].path_type == "min"
    assert paths[1].slack_ps == -1200


# ============================================================================
# Feature Step 3: Classify setup violations (negative WNS on max paths)
# ============================================================================


def test_classify_setup_violations() -> None:
    """
    Feature Step 3: Classify setup violations (negative WNS on max paths).

    Setup violations occur on max paths with negative slack.
    """
    # Create paths with setup violations
    paths = [
        TimingPath(
            slack_ps=-5500,
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=-3200,
            startpoint="reg3/Q",
            endpoint="reg4/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=2000,  # Positive slack - no violation
            startpoint="reg5/Q",
            endpoint="reg6/D",
            path_group="clk",
            path_type="max",
        ),
    ]

    breakdown = classify_timing_violations(paths)

    # Verify setup violations are counted
    assert breakdown.setup_violations == 2
    assert breakdown.hold_violations == 0
    assert breakdown.total_violations == 2
    assert breakdown.worst_setup_slack_ps == -5500  # Worst of the two
    assert breakdown.worst_hold_slack_ps is None


def test_classify_setup_violations_without_path_type() -> None:
    """
    Test that violations without path_type are assumed to be setup (max).

    This is the default behavior when path_type is not specified.
    """
    paths = [
        TimingPath(
            slack_ps=-4500,
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type=None,  # No path type specified
        ),
    ]

    breakdown = classify_timing_violations(paths)

    # Should be classified as setup violation by default
    assert breakdown.setup_violations == 1
    assert breakdown.hold_violations == 0
    assert breakdown.worst_setup_slack_ps == -4500


# ============================================================================
# Feature Step 4: Classify hold violations (negative slack on min paths)
# ============================================================================


def test_classify_hold_violations() -> None:
    """
    Feature Step 4: Classify hold violations (negative slack on min paths).

    Hold violations occur on min paths with negative slack.
    """
    # Create paths with hold violations
    paths = [
        TimingPath(
            slack_ps=-1200,
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="min",
        ),
        TimingPath(
            slack_ps=-800,
            startpoint="reg3/Q",
            endpoint="reg4/D",
            path_group="clk",
            path_type="min",
        ),
        TimingPath(
            slack_ps=500,  # Positive slack - no violation
            startpoint="reg5/Q",
            endpoint="reg6/D",
            path_group="clk",
            path_type="min",
        ),
    ]

    breakdown = classify_timing_violations(paths)

    # Verify hold violations are counted
    assert breakdown.setup_violations == 0
    assert breakdown.hold_violations == 2
    assert breakdown.total_violations == 2
    assert breakdown.worst_hold_slack_ps == -1200  # Worst of the two
    assert breakdown.worst_setup_slack_ps is None


def test_classify_mixed_violations() -> None:
    """
    Test classification of mixed setup and hold violations.
    """
    paths = [
        TimingPath(
            slack_ps=-5500,
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="max",  # Setup violation
        ),
        TimingPath(
            slack_ps=-1200,
            startpoint="reg3/Q",
            endpoint="reg4/D",
            path_group="clk",
            path_type="min",  # Hold violation
        ),
        TimingPath(
            slack_ps=-3200,
            startpoint="reg5/Q",
            endpoint="reg6/D",
            path_group="clk",
            path_type="max",  # Another setup violation
        ),
    ]

    breakdown = classify_timing_violations(paths)

    # Verify both types are counted
    assert breakdown.setup_violations == 2
    assert breakdown.hold_violations == 1
    assert breakdown.total_violations == 3
    assert breakdown.worst_setup_slack_ps == -5500
    assert breakdown.worst_hold_slack_ps == -1200


# ============================================================================
# Feature Step 5: Emit violation breakdown to telemetry
# ============================================================================


def test_emit_violation_breakdown_to_telemetry() -> None:
    """
    Feature Step 5: Emit violation breakdown to telemetry.

    The violation breakdown should be included in TimingMetrics
    and available for telemetry export.
    """
    report_content = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Group: clk
Path Type: max
           -5.50   slack (VIOLATED)

Startpoint: reg3/Q
Endpoint: reg4/D
Path Group: clk
Path Type: min
           -1.20   slack (VIOLATED)

Startpoint: reg5/Q
Endpoint: reg6/D
Path Group: clk
Path Type: max
           -3.20   slack (VIOLATED)

wns -5.50
"""

    # Parse with path extraction enabled (default)
    metrics = parse_timing_report_content(report_content)

    # Verify violation breakdown is present
    assert metrics.violation_breakdown is not None
    breakdown = metrics.violation_breakdown

    # Verify counts
    assert breakdown.setup_violations == 2
    assert breakdown.hold_violations == 1
    assert breakdown.total_violations == 3

    # Verify worst slacks
    assert breakdown.worst_setup_slack_ps == -5500
    assert breakdown.worst_hold_slack_ps == -1200


def test_violation_breakdown_only_when_paths_extracted() -> None:
    """
    Test that violation breakdown is only computed when paths are extracted.
    """
    report_content = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: max
           -5.50   slack (VIOLATED)

wns -5.50
"""

    # Parse without path extraction
    metrics = parse_timing_report_content(report_content, extract_paths=False)

    # Violation breakdown should not be present
    assert metrics.violation_breakdown is None


# ============================================================================
# Feature Step 6: Use violation classification for ECO targeting
# ============================================================================


def test_violation_classification_for_eco_targeting() -> None:
    """
    Feature Step 6: Use violation classification for ECO targeting.

    Violation classification enables targeted ECO strategies:
    - Setup violations: buffer insertion, cell upsizing, timing optimization
    - Hold violations: buffer insertion, cell downsizing, hold fixing
    """
    # Scenario: Design with both setup and hold violations
    report_content = """
Startpoint: critical_setup_path/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: critical_setup_endpoint/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

  Delay    Time   Description
---------------------------------------------------------
           0.00   clock clk (rise edge)
     5.25  5.25 ^ critical_setup_path/Q (DFF_X2)
     8.75 14.00 ^ logic_chain/Z (NAND3_X1)
          14.00   data arrival time

          10.00   clock clk (rise edge)
          -0.50   library setup time
           9.50   data required time
---------------------------------------------------------
          -4.50   slack (VIOLATED)

Startpoint: critical_hold_path/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: critical_hold_endpoint/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: min

  Delay    Time   Description
---------------------------------------------------------
           0.00   clock clk (rise edge)
     0.25  0.25 ^ critical_hold_path/Q (DFF_X2)
     0.50  0.75 ^ fast_buffer/Z (BUF_X1)
           0.75   data arrival time

           0.00   clock clk (rise edge)
           0.10   library hold time
           1.10   data required time
---------------------------------------------------------
          -0.35   slack (VIOLATED)

wns -4.50
"""

    metrics = parse_timing_report_content(report_content)

    # Verify we have violation breakdown for ECO targeting
    assert metrics.violation_breakdown is not None
    breakdown = metrics.violation_breakdown

    # ECO strategy decision based on violation types:
    if breakdown.setup_violations > 0:
        # Setup violations detected - use aggressive timing optimization
        assert breakdown.setup_violations == 1
        assert breakdown.worst_setup_slack_ps == -4500

        # ECO targeting information from paths:
        setup_paths = [p for p in metrics.top_paths if p.path_type == "max" and p.slack_ps < 0]
        assert len(setup_paths) == 1
        assert "critical_setup_path" in setup_paths[0].startpoint
        assert "critical_setup_endpoint" in setup_paths[0].endpoint

    if breakdown.hold_violations > 0:
        # Hold violations detected - use conservative hold fixing
        assert breakdown.hold_violations == 1
        assert breakdown.worst_hold_slack_ps == -350

        # ECO targeting information from paths:
        hold_paths = [p for p in metrics.top_paths if p.path_type == "min" and p.slack_ps < 0]
        assert len(hold_paths) == 1
        assert "critical_hold_path" in hold_paths[0].startpoint
        assert "critical_hold_endpoint" in hold_paths[0].endpoint


# ============================================================================
# Edge Cases and Robustness Tests
# ============================================================================


def test_no_violations() -> None:
    """Test with no violations (all paths have positive slack)."""
    paths = [
        TimingPath(
            slack_ps=2000,
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=500,
            startpoint="reg3/Q",
            endpoint="reg4/D",
            path_group="clk",
            path_type="min",
        ),
    ]

    breakdown = classify_timing_violations(paths)

    assert breakdown.setup_violations == 0
    assert breakdown.hold_violations == 0
    assert breakdown.total_violations == 0
    assert breakdown.worst_setup_slack_ps is None
    assert breakdown.worst_hold_slack_ps is None


def test_empty_paths() -> None:
    """Test with empty path list."""
    paths: list[TimingPath] = []

    breakdown = classify_timing_violations(paths)

    assert breakdown.setup_violations == 0
    assert breakdown.hold_violations == 0
    assert breakdown.total_violations == 0
    assert breakdown.worst_setup_slack_ps is None
    assert breakdown.worst_hold_slack_ps is None


def test_case_insensitive_path_type() -> None:
    """Test that path_type matching is case-insensitive."""
    paths = [
        TimingPath(
            slack_ps=-1000,
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="MAX",  # Uppercase
        ),
        TimingPath(
            slack_ps=-500,
            startpoint="reg3/Q",
            endpoint="reg4/D",
            path_group="clk",
            path_type="Min",  # Mixed case
        ),
    ]

    breakdown = classify_timing_violations(paths)

    assert breakdown.setup_violations == 1
    assert breakdown.hold_violations == 1


def test_only_setup_violations() -> None:
    """Test scenario with only setup violations."""
    report_content = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: max
           -5.50   slack (VIOLATED)

Startpoint: reg3/Q
Endpoint: reg4/D
Path Type: max
           -3.20   slack (VIOLATED)

wns -5.50
"""

    metrics = parse_timing_report_content(report_content)

    assert metrics.violation_breakdown is not None
    breakdown = metrics.violation_breakdown

    assert breakdown.setup_violations == 2
    assert breakdown.hold_violations == 0
    assert breakdown.total_violations == 2
    assert breakdown.worst_setup_slack_ps == -5500
    assert breakdown.worst_hold_slack_ps is None


def test_only_hold_violations() -> None:
    """Test scenario with only hold violations."""
    report_content = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: min
           -1.20   slack (VIOLATED)

Startpoint: reg3/Q
Endpoint: reg4/D
Path Type: min
           -0.80   slack (VIOLATED)

wns -1.20
"""

    metrics = parse_timing_report_content(report_content)

    assert metrics.violation_breakdown is not None
    breakdown = metrics.violation_breakdown

    assert breakdown.setup_violations == 0
    assert breakdown.hold_violations == 2
    assert breakdown.total_violations == 2
    assert breakdown.worst_setup_slack_ps is None
    assert breakdown.worst_hold_slack_ps == -1200


def test_worst_slack_tracking() -> None:
    """Test that worst slacks are correctly identified."""
    paths = [
        TimingPath(slack_ps=-5500, startpoint="r1", endpoint="r2", path_type="max"),
        TimingPath(slack_ps=-3200, startpoint="r3", endpoint="r4", path_type="max"),
        TimingPath(slack_ps=-7800, startpoint="r5", endpoint="r6", path_type="max"),
        TimingPath(slack_ps=-1200, startpoint="r7", endpoint="r8", path_type="min"),
        TimingPath(slack_ps=-800, startpoint="r9", endpoint="r10", path_type="min"),
    ]

    breakdown = classify_timing_violations(paths)

    # Worst setup should be -7800 (most negative)
    assert breakdown.worst_setup_slack_ps == -7800

    # Worst hold should be -1200 (most negative)
    assert breakdown.worst_hold_slack_ps == -1200


# ============================================================================
# Integration Tests
# ============================================================================


def test_end_to_end_violation_classification() -> None:
    """
    End-to-end test of violation classification from report parsing.

    This test validates all 6 feature steps in sequence.
    """
    # Step 1: Execute STA producing report_checks output (simulated)
    report_content = """
Startpoint: input_port (input port clocked by clk)
Endpoint: output_port (output port clocked by clk)
Path Group: clk
Path Type: max
           4.50   slack (MET)

Startpoint: reg1/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg2/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max
          -5.50   slack (VIOLATED)

Startpoint: reg3/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg4/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: min
          -1.20   slack (VIOLATED)

Startpoint: reg5/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg6/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max
          -3.20   slack (VIOLATED)

wns -5.50
tns -9.90
failing endpoints: 3
"""

    # Step 2: Parse timing paths and identify violation types
    metrics = parse_timing_report_content(report_content)

    assert metrics.wns_ps == -5500
    assert metrics.tns_ps == -9900
    assert metrics.failing_endpoints == 3
    assert len(metrics.top_paths) == 4

    # Step 3 & 4: Classify setup and hold violations
    assert metrics.violation_breakdown is not None
    breakdown = metrics.violation_breakdown

    assert breakdown.setup_violations == 2  # Two max paths with negative slack
    assert breakdown.hold_violations == 1  # One min path with negative slack
    assert breakdown.total_violations == 3

    # Step 5: Emit violation breakdown to telemetry (verified by structure)
    assert breakdown.worst_setup_slack_ps == -5500
    assert breakdown.worst_hold_slack_ps == -1200

    # Step 6: Use violation classification for ECO targeting (verified by data availability)
    # We have all the information needed to target ECOs:
    # - Which violations are setup vs hold
    # - Which paths are affected
    # - What are the worst slacks for prioritization
    setup_paths = [p for p in metrics.top_paths if p.path_type == "max" and p.slack_ps < 0]
    hold_paths = [p for p in metrics.top_paths if p.path_type == "min" and p.slack_ps < 0]

    assert len(setup_paths) == 2
    assert len(hold_paths) == 1
