"""Tests for F111: Timing path breakdown extracts wire vs cell delay.

Verifies that:
1. report_checks with detailed fields is parsed correctly
2. Cell delays and net delays are extracted separately
3. Delays are summed correctly
4. Wire-dominated classification works (>65% wire delay)
5. Classification matches actual path characteristics
"""

import pytest

from src.controller.types import TimingPath
from src.parsers.timing import parse_timing_path_delays


class TestTimingPathDelayExtraction:
    """Test parsing of timing paths with delay breakdown."""

    def test_step_1_parse_report_checks_with_fields(self):
        """Step 1: Run report_checks with -fields {fanout cap slew cell net} -digits 4."""
        # Simulate OpenROAD report_checks output with detailed fields
        report = """
Startpoint: reg1/Q (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg2/D (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

Point                                    Fanout Cap    Slew   Delay    Time
-----------------------------------------------------------------------------
clock clk (rise edge)                                          0.0000   0.0000
clock network delay (ideal)                                    0.0000   0.0000
reg1/CK (DFF_X1)                                      0.0000   0.0000   0.0000 r
reg1/Q (DFF_X1)                                       0.0520   0.0450   0.0450 r
U1/A (BUF_X2)                            2     0.0150 0.0520   0.0000   0.0450 r
U1/Z (BUF_X2)                                         0.0380   0.0320   0.0770 r
net1 (net)                                     0.0200 0.0380   0.0180   0.0950 r
U2/A (INV_X1)                            1     0.0080 0.0380   0.0000   0.0950 r
U2/ZN (INV_X1)                                        0.0250   0.0280   0.1230 f
net2 (net)                                     0.0120 0.0250   0.0110   0.1340 f
reg2/D (DFF_X1)                                       0.0250   0.0000   0.1340 f
data arrival time                                              0.1340

clock clk (rise edge)                                          0.1000   0.1000
clock network delay (ideal)                                    0.0000   0.1000
reg2/CK (DFF_X1)                                               0.0000   0.1000 r
library setup time                                            -0.0150   0.0850
data required time                                                      0.0850
-----------------------------------------------------------------------------
data required time                                                      0.0850
data arrival time                                                      -0.1340
-----------------------------------------------------------------------------
slack (VIOLATED)                                                       -0.0490
"""

        paths = parse_timing_path_delays(report)

        assert len(paths) == 1
        path = paths[0]

        # Verify basic path info
        assert path.startpoint == "reg1/Q"
        assert path.endpoint == "reg2/D"
        assert path.path_type == "max"
        assert path.slack_ps == -49  # -0.049 ns = -49 ps

        # Verify delays are extracted
        assert path.cell_delay_ps is not None
        assert path.wire_delay_ps is not None

    def test_step_2_extract_cell_and_net_delays_separately(self):
        """Step 2: Parse output to extract cell delays and net delays separately."""
        report = """
Startpoint: in1 (input port)
Endpoint: reg1/D (rising edge-triggered flip-flop)
Path Type: max

Point                                    Delay    Time
--------------------------------------------------------
in1 (in)                                 0.0000   0.0000
U1/A (BUF_X1)                            0.0000   0.0000
U1/Z (BUF_X1)                            0.0250   0.0250
net1 (net)                               0.0150   0.0400
U2/A (INV_X1)                            0.0000   0.0400
U2/ZN (INV_X1)                           0.0180   0.0580
net2 (net)                               0.0220   0.0800
reg1/D (DFF_X1)                          0.0000   0.0800
data arrival time                        0.0800

slack (VIOLATED)                        -0.0200
"""

        paths = parse_timing_path_delays(report)
        assert len(paths) == 1
        path = paths[0]

        # Cell delays: BUF_X1 (25ps) + INV_X1 (18ps) = 43ps
        # Net delays: net1 (15ps) + net2 (22ps) = 37ps
        assert path.cell_delay_ps == 43
        assert path.wire_delay_ps == 37
        assert path.slack_ps == -20

    def test_step_3_sum_cell_and_wire_delay(self):
        """Step 3: Sum cell_delay and wire_delay."""
        report = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: max

Point                                    Delay    Time
--------------------------------------------------------
reg1/Q (DFF_X1)                          0.0300   0.0300
net1 (net)                               0.0100   0.0400
U1/Z (BUF_X1)                            0.0400   0.0800
net2 (net)                               0.0200   0.1000
reg2/D (DFF_X1)                          0.0000   0.1000

slack (VIOLATED)                        -0.0500
"""

        paths = parse_timing_path_delays(report)
        path = paths[0]

        # Cell: 30 + 40 = 70ps
        # Wire: 10 + 20 = 30ps
        # Total: 100ps
        assert path.cell_delay_ps == 70
        assert path.wire_delay_ps == 30
        assert path.cell_delay_ps + path.wire_delay_ps == 100

    def test_step_4_calculate_wire_dominated_threshold(self):
        """Step 4: Calculate wire_dominated = (wire_delay > 0.65 * total)."""
        # Test case 1: Wire-dominated path (70% wire)
        path1 = TimingPath(
            slack_ps=-100,
            startpoint="reg1",
            endpoint="reg2",
            wire_delay_ps=70,
            cell_delay_ps=30,
        )
        assert path1.is_wire_dominated is True

        # Test case 2: Cell-dominated path (40% wire)
        path2 = TimingPath(
            slack_ps=-100,
            startpoint="reg1",
            endpoint="reg2",
            wire_delay_ps=40,
            cell_delay_ps=60,
        )
        assert path2.is_wire_dominated is False

        # Test case 3: Exactly 65% wire (not dominated)
        path3 = TimingPath(
            slack_ps=-100,
            startpoint="reg1",
            endpoint="reg2",
            wire_delay_ps=65,
            cell_delay_ps=35,
        )
        assert path3.is_wire_dominated is False

        # Test case 4: Just over 65% threshold
        path4 = TimingPath(
            slack_ps=-100,
            startpoint="reg1",
            endpoint="reg2",
            wire_delay_ps=66,
            cell_delay_ps=34,
        )
        assert path4.is_wire_dominated is True

    def test_step_5_verify_classification_matches_characteristics(self):
        """Step 5: Verify classification matches actual path characteristics."""
        # Long route path - should be wire-dominated
        long_route_report = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: max

Point                                    Delay    Time
--------------------------------------------------------
reg1/Q (DFF_X1)                          0.0200   0.0200
net_long (net)                           0.0800   0.1000
U1/Z (BUF_X1)                            0.0150   0.1150
net_long2 (net)                          0.0900   0.2050
reg2/D (DFF_X1)                          0.0000   0.2050

slack (VIOLATED)                        -0.1000
"""

        paths = parse_timing_path_delays(long_route_report)
        path = paths[0]

        # Wire: 80 + 90 = 170ps (0.0800 + 0.0900 ns)
        # Cell: 20 + 15 = 35ps (0.0200 + 0.0150 ns)
        # Total: 205ps, wire is 83% - should be wire-dominated
        assert path.wire_delay_ps == 170
        assert path.cell_delay_ps == 35
        assert path.is_wire_dominated is True

        # Short local path - should be cell-dominated
        short_path_report = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: max

Point                                    Delay    Time
--------------------------------------------------------
reg1/Q (DFF_X1)                          0.0400   0.0400
net1 (net)                               0.0050   0.0450
U1/Z (AND2_X1)                           0.0350   0.0800
net2 (net)                               0.0030   0.0830
U2/Z (BUF_X1)                            0.0280   0.1110
net3 (net)                               0.0040   0.1150
reg2/D (DFF_X1)                          0.0000   0.1150

slack (VIOLATED)                        -0.0500
"""

        paths = parse_timing_path_delays(short_path_report)
        path = paths[0]

        # Wire: 5 + 3 + 4 = 12ps (0.0050 + 0.0030 + 0.0040 ns)
        # Cell: 40 + 35 + 28 = 103ps (0.0400 + 0.0350 + 0.0280 ns)
        # Total: 115ps, wire is 10% - should be cell-dominated
        assert path.wire_delay_ps == 12
        assert path.cell_delay_ps == 103
        assert path.is_wire_dominated is False


class TestTimingPathDelayBreakdownEdgeCases:
    """Test edge cases for timing path delay breakdown."""

    def test_path_with_no_delay_information(self):
        """Test path without delay breakdown (legacy format)."""
        path = TimingPath(
            slack_ps=-100,
            startpoint="reg1",
            endpoint="reg2",
            wire_delay_ps=None,
            cell_delay_ps=None,
        )

        # Should not be classified as wire-dominated without data
        assert path.is_wire_dominated is False

    def test_path_with_zero_total_delay(self):
        """Test path with zero total delay."""
        path = TimingPath(
            slack_ps=-100,
            startpoint="reg1",
            endpoint="reg2",
            wire_delay_ps=0,
            cell_delay_ps=0,
        )

        assert path.is_wire_dominated is False

    def test_multiple_paths_in_report(self):
        """Test parsing multiple paths from a single report."""
        report = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: max

Point                                    Delay    Time
--------------------------------------------------------
reg1/Q (DFF_X1)                          0.0300   0.0300
net1 (net)                               0.0700   0.1000
reg2/D (DFF_X1)                          0.0000   0.1000

slack (VIOLATED)                        -0.0500

Startpoint: reg3/Q
Endpoint: reg4/D
Path Type: max

Point                                    Delay    Time
--------------------------------------------------------
reg3/Q (DFF_X1)                          0.0400   0.0400
net2 (net)                               0.0200   0.0600
U1/Z (BUF_X1)                            0.0300   0.0900
net3 (net)                               0.0100   0.1000
reg4/D (DFF_X1)                          0.0000   0.1000

slack (VIOLATED)                        -0.0300
"""

        paths = parse_timing_path_delays(report, max_paths=5)

        assert len(paths) == 2

        # First path: wire-dominated (70%)
        path1 = paths[0]
        assert path1.startpoint == "reg1/Q"
        assert path1.wire_delay_ps == 70  # 0.0700 ns = 70 ps
        assert path1.cell_delay_ps == 30  # 0.0300 ns = 30 ps
        assert path1.is_wire_dominated is True

        # Second path: cell-dominated (30% wire)
        path2 = paths[1]
        assert path2.startpoint == "reg3/Q"
        assert path2.wire_delay_ps == 30  # 0.0200 + 0.0100 = 30 ps
        assert path2.cell_delay_ps == 70  # 0.0400 + 0.0300 = 70 ps
        assert path2.is_wire_dominated is False

    def test_path_with_negative_delays(self):
        """Test handling of negative delays (can occur in timing analysis)."""
        report = """
Startpoint: reg1/Q
Endpoint: reg2/D
Path Type: max

Point                                    Delay    Time
--------------------------------------------------------
reg1/Q (DFF_X1)                          0.0300   0.0300
net1 (net)                              -0.0050   0.0250
U1/Z (BUF_X1)                            0.0400   0.0650
net2 (net)                               0.0150   0.0800
reg2/D (DFF_X1)                          0.0000   0.0800

slack (VIOLATED)                        -0.0200
"""

        paths = parse_timing_path_delays(report)
        path = paths[0]

        # Cell: 30 + 40 = 70ps (0.0300 + 0.0400 ns)
        # Wire: -5 + 15 = 10ps (-0.0050 + 0.0150 ns, negative delays can occur with ideal networks)
        assert path.cell_delay_ps == 70
        assert path.wire_delay_ps == 10


class TestTimingPathIntegration:
    """Integration tests for timing path delay breakdown."""

    def test_realistic_nangate45_path(self):
        """Test with realistic Nangate45 PDK path."""
        report = """
Startpoint: _123_ (rising edge-triggered flip-flop clocked by clk)
Endpoint: _456_ (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

Point                                    Fanout Cap    Slew   Delay    Time
-----------------------------------------------------------------------------
clock clk (rise edge)                                          0.0000   0.0000
clock network delay (ideal)                                    0.0000   0.0000
_123_/CK (DFF_X1)                                     0.0000   0.0000   0.0000 r
_123_/Q (DFF_X1)                                      0.0234   0.0512   0.0512 r
_789_/A (BUF_X4)                         8     0.0289 0.0234   0.0000   0.0512 r
_789_/Z (BUF_X4)                                      0.0198   0.0387   0.0899 r
net_123 (net)                                  0.0425 0.0198   0.0312   0.1211 r
_891_/A (AND2_X2)                        3     0.0156 0.0198   0.0000   0.1211 r
_891_/ZN (AND2_X2)                                    0.0289   0.0423   0.1634 r
net_456 (net)                                  0.0523 0.0289   0.0398   0.2032 r
_456_/D (DFF_X1)                                      0.0289   0.0000   0.2032 r
data arrival time                                              0.2032

clock clk (rise edge)                                          0.1000   0.1000
clock network delay (ideal)                                    0.0000   0.1000
_456_/CK (DFF_X1)                                              0.0000   0.1000 r
library setup time                                            -0.0089   0.0911
data required time                                                      0.0911
-----------------------------------------------------------------------------
slack (VIOLATED)                                                       -0.1121
"""

        paths = parse_timing_path_delays(report)
        assert len(paths) == 1
        path = paths[0]

        # Verify path is parsed
        assert path.startpoint == "_123_"
        assert path.endpoint == "_456_"
        assert path.slack_ps == -112  # -0.1121 ns

        # Cell delays: 51.2 + 38.7 + 42.3 = 132.2ps
        # Net delays: 31.2 + 39.8 = 71ps
        assert path.cell_delay_ps is not None
        assert path.wire_delay_ps is not None

        # This path should be cell-dominated (~65% cell)
        total = path.cell_delay_ps + path.wire_delay_ps
        cell_pct = path.cell_delay_ps / total
        assert cell_pct > 0.5
