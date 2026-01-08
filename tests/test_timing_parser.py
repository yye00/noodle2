"""Tests for timing report parser."""

import pytest
import tempfile
from pathlib import Path

from src.parsers.timing import (
    parse_timing_report,
    parse_timing_report_content,
    parse_openroad_metrics_json,
    parse_timing_paths,
)


def test_parse_timing_report_basic() -> None:
    """
    Feature #4: Parse OpenROAD report_checks output and extract WNS correctly.

    Steps:
        1. Execute STA run that produces report_checks output (simulated with test data)
        2. Locate timing report file in artifacts
        3. Parse report using timing parser
        4. Verify wns_ps field is extracted
        5. Optionally verify tns_ps field is extracted
        6. Validate parsed values are numeric and reasonable
    """
    # Step 1-2: Simulate report_checks output
    report_content = """
Startpoint: input_port (input port clocked by clk)
Endpoint: reg1/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

  Delay    Time   Description
---------------------------------------------------------
           0.00   clock clk (rise edge)
           0.00   clock network delay (ideal)
           0.00 ^ input_port (in)
     2.15  2.15 ^ input_buffer/A (BUF_X1)
     0.75  2.90 ^ input_buffer/Z (BUF_X1)
     1.25  4.15 ^ logic_gate/A (AND2_X1)
     0.85  5.00 ^ logic_gate/Z (AND2_X1)
           5.00   data arrival time

          10.00   clock clk (rise edge)
           0.00   clock network delay (ideal)
           0.00   clock uncertainty
          10.00   clock reconvergence pessimism
          -0.50   library setup time
           9.50   data required time
---------------------------------------------------------
           9.50   data required time
          -5.00   data arrival time
---------------------------------------------------------
           4.50   slack (MET)

wns 4.50
tns 0.00
"""

    # Step 3: Parse report using timing parser
    metrics = parse_timing_report_content(report_content)

    # Step 4: Verify wns_ps field is extracted
    assert metrics.wns_ps is not None, "WNS should be extracted"

    # Step 5: Verify tns_ps field is extracted
    assert metrics.tns_ps is not None, "TNS should be extracted"

    # Step 6: Validate parsed values are numeric and reasonable
    # WNS is 4.50 (in ns), should be 4500 ps
    assert metrics.wns_ps == 4500, f"Expected WNS=4500ps, got {metrics.wns_ps}"
    assert metrics.tns_ps == 0, f"Expected TNS=0ps, got {metrics.tns_ps}"


def test_parse_negative_slack() -> None:
    """Test parsing timing report with negative slack (timing violation)."""
    report_content = """
Timing Report
-------------
wns -123.45
tns -456.78
failing endpoints: 42
"""

    metrics = parse_timing_report_content(report_content)

    # WNS is -123.45 ns = -123450 ps
    assert metrics.wns_ps == -123450
    assert metrics.tns_ps == -456780
    assert metrics.failing_endpoints == 42


def test_parse_slack_keyword() -> None:
    """Test parsing using 'slack' keyword instead of 'wns'."""
    report_content = """
---------------------------------------------------------
           9.50   data required time
         -15.00   data arrival time
---------------------------------------------------------
          -5.50   slack (VIOLATED)

slack -5.50
"""

    metrics = parse_timing_report_content(report_content)
    assert metrics.wns_ps == -5500  # -5.50 ns = -5500 ps


def test_parse_with_units() -> None:
    """Test parsing with explicit units."""
    # Nanoseconds
    report_ns = "WNS: -10.5 ns"
    metrics_ns = parse_timing_report_content(report_ns)
    assert metrics_ns.wns_ps == -10500

    # Picoseconds
    report_ps = "WNS: -10500 ps"
    metrics_ps = parse_timing_report_content(report_ps)
    assert metrics_ps.wns_ps == -10500


def test_parse_from_file() -> None:
    """Test parsing from actual file."""
    report_content = "wns -42.0\ntns -100.5"

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".rpt", delete=False) as f:
        f.write(report_content)
        report_path = f.name

    try:
        metrics = parse_timing_report(report_path)
        assert metrics.wns_ps == -42000
        assert metrics.tns_ps == -100500
    finally:
        Path(report_path).unlink()


def test_parse_missing_file() -> None:
    """Test parsing non-existent file raises error."""
    with pytest.raises(FileNotFoundError):
        parse_timing_report("/nonexistent/timing.rpt")


def test_parse_invalid_report() -> None:
    """Test parsing report without WNS raises error."""
    invalid_content = """
This is not a timing report.
Just some random text.
"""

    with pytest.raises(ValueError, match="Could not extract WNS"):
        parse_timing_report_content(invalid_content)


def test_parse_json_metrics() -> None:
    """Test parsing OpenROAD metrics in JSON format."""
    json_content = """
{
    "wns": -5.25,
    "tns": -42.0,
    "failing_endpoints": 10,
    "design": "test_design"
}
"""

    metrics = parse_openroad_metrics_json(json_content)
    assert metrics.wns_ps == -5250  # -5.25 ns = -5250 ps
    assert metrics.tns_ps == -42000
    assert metrics.failing_endpoints == 10


def test_parse_positive_slack() -> None:
    """Test parsing with positive slack (timing met)."""
    report_content = "wns 100.25\ntns 0.0"

    metrics = parse_timing_report_content(report_content)
    assert metrics.wns_ps == 100250  # Positive slack
    assert metrics.tns_ps == 0


def test_parse_zero_slack() -> None:
    """Test parsing with exactly zero slack."""
    report_content = "wns 0.0\ntns 0.0"

    metrics = parse_timing_report_content(report_content)
    assert metrics.wns_ps == 0
    assert metrics.tns_ps == 0


def test_parse_various_formats() -> None:
    """Test parsing various report format variations."""
    # Colon separator
    metrics1 = parse_timing_report_content("WNS: -10.0 ns")
    assert metrics1.wns_ps == -10000

    # Space separator
    metrics2 = parse_timing_report_content("wns -10.0")
    assert metrics2.wns_ps == -10000

    # Mixed case
    metrics3 = parse_timing_report_content("Wns -10.0")
    assert metrics3.wns_ps == -10000


# ============================================================================
# Tests for Feature #20: Support inspection of top timing paths
# ============================================================================


def test_parse_timing_paths_single_path() -> None:
    """
    Feature #20: Support inspection of top timing paths from report_checks output.

    Test parsing a single timing path with all details.
    """
    report_content = """
Startpoint: input_port (input port clocked by clk)
Endpoint: reg1/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

  Delay    Time   Description
---------------------------------------------------------
           0.00   clock clk (rise edge)
           0.00   clock network delay (ideal)
           0.00 ^ input_port (in)
     2.15  2.15 ^ input_buffer/A (BUF_X1)
     0.75  2.90 ^ input_buffer/Z (BUF_X1)
           2.90   data arrival time

          10.00   clock clk (rise edge)
           0.00   clock network delay (ideal)
          -0.50   library setup time
           9.50   data required time
---------------------------------------------------------
           9.50   data required time
          -2.90   data arrival time
---------------------------------------------------------
           6.60   slack (MET)

wns 6.60
"""

    paths = parse_timing_paths(report_content)

    # Step 2: Parse top N critical paths
    assert len(paths) == 1, "Should extract one path"

    # Step 3: Extract path slack, startpoint, endpoint
    path = paths[0]
    assert path.slack_ps == 6600  # 6.60 ns = 6600 ps
    assert path.startpoint == "input_port"
    assert path.endpoint == "reg1/D"
    assert path.path_group == "clk"
    assert path.path_type == "max"


def test_parse_timing_paths_multiple_paths() -> None:
    """
    Feature #20: Test parsing multiple timing paths.

    Step 2: Parse top N critical paths
    """
    report_content = """
Startpoint: reg1/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg2/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

           4.50   slack (MET)

Startpoint: reg2/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg3/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

          -2.30   slack (VIOLATED)

Startpoint: input_a (input port clocked by clk)
Endpoint: output_z (output port clocked by clk)
Path Group: clk
Path Type: max

           8.75   slack (MET)

wns -2.30
"""

    paths = parse_timing_paths(report_content)

    assert len(paths) == 3, "Should extract three paths"

    # First path
    assert paths[0].slack_ps == 4500
    assert paths[0].startpoint == "reg1/Q"
    assert paths[0].endpoint == "reg2/D"

    # Second path (worst)
    assert paths[1].slack_ps == -2300
    assert paths[1].startpoint == "reg2/Q"
    assert paths[1].endpoint == "reg3/D"

    # Third path
    assert paths[2].slack_ps == 8750
    assert paths[2].startpoint == "input_a"
    assert paths[2].endpoint == "output_z"


def test_parse_timing_paths_with_max_limit() -> None:
    """
    Feature #20: Test limiting the number of paths extracted.

    Step 2: Parse top N critical paths (with limit)
    """
    # Create report with 5 paths
    report_content = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Group: clk
Path Type: max
           1.00   slack (MET)

Startpoint: reg3/Q
Endpoint: reg4/D
Path Group: clk
Path Type: max
           2.00   slack (MET)

Startpoint: reg5/Q
Endpoint: reg6/D
Path Group: clk
Path Type: max
           3.00   slack (MET)

Startpoint: reg7/Q
Endpoint: reg8/D
Path Group: clk
Path Type: max
           4.00   slack (MET)

Startpoint: reg9/Q
Endpoint: reg10/D
Path Group: clk
Path Type: max
           5.00   slack (MET)

wns 1.00
"""

    # Extract only top 3 paths
    paths = parse_timing_paths(report_content, max_paths=3)

    assert len(paths) == 3, "Should extract only 3 paths"
    assert paths[0].slack_ps == 1000
    assert paths[1].slack_ps == 2000
    assert paths[2].slack_ps == 3000


def test_parse_timing_report_with_paths() -> None:
    """
    Feature #20: Test complete parsing including WNS and top paths.

    Steps 1-5: Execute, parse, extract all metrics including paths.
    """
    report_content = """
Startpoint: input_port (input port clocked by clk)
Endpoint: reg1/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

           4.50   slack (MET)

Startpoint: reg1/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg2/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

          -5.50   slack (VIOLATED)

wns -5.50
tns -12.30
failing endpoints: 3
"""

    # Parse with path extraction enabled (default)
    metrics = parse_timing_report_content(report_content)

    # Step 4: Emit top paths to timing analysis artifacts
    assert metrics.wns_ps == -5500
    assert metrics.tns_ps == -12300
    assert metrics.failing_endpoints == 3

    # Step 3: Extract path slack, startpoint, endpoint
    assert len(metrics.top_paths) == 2
    assert metrics.top_paths[0].slack_ps == 4500
    assert metrics.top_paths[0].startpoint == "input_port"
    assert metrics.top_paths[1].slack_ps == -5500
    assert metrics.top_paths[1].startpoint == "reg1/Q"


def test_parse_timing_report_without_paths() -> None:
    """
    Feature #20: Test parsing with path extraction disabled.
    """
    report_content = """
Startpoint: input_port
Endpoint: reg1/D
           4.50   slack (MET)

wns 4.50
"""

    # Parse with path extraction disabled
    metrics = parse_timing_report_content(report_content, extract_paths=False)

    assert metrics.wns_ps == 4500
    assert len(metrics.top_paths) == 0, "Should not extract paths when disabled"


def test_parse_timing_paths_minimal_format() -> None:
    """
    Feature #20: Test parsing paths with minimal information.

    Paths may not always have all optional fields.
    """
    report_content = """
Startpoint: A
Endpoint: B
           -10.25   slack (VIOLATED)

wns -10.25
"""

    paths = parse_timing_paths(report_content)

    assert len(paths) == 1
    assert paths[0].slack_ps == -10250
    assert paths[0].startpoint == "A"
    assert paths[0].endpoint == "B"
    assert paths[0].path_group is None  # Optional field not present
    assert paths[0].path_type is None  # Optional field not present


def test_parse_timing_paths_empty_report() -> None:
    """
    Feature #20: Test parsing report with no path information.
    """
    report_content = """
Some header text
wns 0.0
tns 0.0
"""

    paths = parse_timing_paths(report_content)

    assert len(paths) == 0, "Should return empty list for report without paths"


def test_parse_timing_paths_for_eco_targeting() -> None:
    """
    Feature #20 Step 5: Enable path-level debugging and ECO targeting.

    Verify that parsed paths contain sufficient detail for ECO decisions.
    """
    report_content = """
Startpoint: critical_reg1/Q (rising edge-triggered flip-flop clocked by sys_clk)
Endpoint: critical_reg2/D (rising edge-triggered flip-flop clocked by sys_clk)
Path Group: sys_clk
Path Type: max

  Delay    Time   Description
---------------------------------------------------------
           0.00   clock sys_clk (rise edge)
     5.25  5.25 ^ critical_reg1/Q (DFF_X2)
     8.75 14.00 ^ logic_chain/Z (NAND3_X1)
          14.00   data arrival time

          10.00   clock sys_clk (rise edge)
          -0.50   library setup time
           9.50   data required time
---------------------------------------------------------
          -4.50   slack (VIOLATED)

wns -4.50
"""

    metrics = parse_timing_report_content(report_content)

    # Verify path details are sufficient for ECO targeting
    assert len(metrics.top_paths) == 1
    path = metrics.top_paths[0]

    # Critical information for ECO decisions:
    # 1. Which path is critical
    assert path.slack_ps == -4500  # Negative slack - needs fixing

    # 2. What are the endpoints (targets for buffering, resizing, etc.)
    assert "critical_reg1" in path.startpoint
    assert "critical_reg2" in path.endpoint

    # 3. Path characteristics (for understanding constraints)
    assert path.path_group == "sys_clk"  # Clock domain
    assert path.path_type == "max"  # Setup path

    # This information enables ECO targeting:
    # - Buffer insertion between critical_reg1 and critical_reg2
    # - Cell resizing on critical path
    # - Clock tree optimization for sys_clk domain
