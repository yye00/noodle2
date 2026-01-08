"""Tests for timing report parser."""

import pytest
import tempfile
from pathlib import Path

from src.parsers.timing import (
    parse_timing_report,
    parse_timing_report_content,
    parse_openroad_metrics_json,
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
