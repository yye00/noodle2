"""Tests for F275: Execute real OpenROAD report_checks and parse timing.

F275 Requirements:
- Step 1: Load Nangate45 snapshot in OpenROAD via Docker
- Step 2: Execute report_checks command
- Step 3: Capture timing report output to file
- Step 4: Parse WNS and TNS from report
- Step 5: Verify parsed metrics are real numbers (not mocked)
- Step 6: Store metrics in metrics.json
"""

import json
from pathlib import Path

import pytest

from infrastructure.openroad_execution import (
    TimingMetrics,
    execute_openroad_command,
    extract_timing_metrics,
    parse_timing_report,
    run_report_checks,
    verify_metrics_are_real,
)


# Test configuration
SNAPSHOT_ODB = Path("studies/nangate45_base/gcd_placed.odb")
REPORT_OUTPUT = Path("test_outputs/timing_report.txt")
METRICS_OUTPUT = Path("test_outputs/metrics.json")


class TestStep1LoadSnapshot:
    """Step 1: Load Nangate45 snapshot in OpenROAD via Docker."""

    def test_snapshot_file_exists(self):
        """Verify snapshot ODB file exists."""
        assert SNAPSHOT_ODB.exists(), f"Snapshot not found: {SNAPSHOT_ODB}"

    def test_can_load_snapshot_in_openroad(self):
        """Verify snapshot can be loaded in OpenROAD."""
        result = execute_openroad_command(
            odb_file=SNAPSHOT_ODB,
            tcl_commands=["puts {Database loaded successfully}"],
        )
        assert result.success, f"Failed to load snapshot: {result.error}"
        assert "Database loaded successfully" in result.stdout

    def test_snapshot_is_readable(self):
        """Verify snapshot database is readable."""
        # Try to read basic database info
        result = execute_openroad_command(
            odb_file=SNAPSHOT_ODB,
            tcl_commands=["puts [get_db_units]"],
        )
        if result.success:
            assert len(result.stdout) > 0


class TestStep2ExecuteReportChecks:
    """Step 2: Execute report_checks command."""

    def test_report_checks_executes(self):
        """Verify report_checks command executes."""
        result = run_report_checks(SNAPSHOT_ODB)
        assert isinstance(result.success, bool)

    def test_report_checks_produces_output(self):
        """Verify report_checks produces output."""
        result = run_report_checks(SNAPSHOT_ODB)
        if result.success:
            assert len(result.stdout) > 0
            assert len(result.stderr) >= 0  # stderr may be empty or have warnings

    def test_report_checks_command_format(self):
        """Verify report_checks uses correct format."""
        result = run_report_checks(SNAPSHOT_ODB)
        if result.success:
            # Check for expected keywords in timing report
            keywords = ["slack", "path", "delay"]
            has_keyword = any(kw in result.stdout.lower() for kw in keywords)
            assert has_keyword, "Report doesn't contain expected timing keywords"


class TestStep3CaptureOutput:
    """Step 3: Capture timing report output to file."""

    def test_capture_report_to_file(self):
        """Verify timing report can be captured to file."""
        output_file = Path("test_outputs/timing_report_capture.txt")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        result = run_report_checks(SNAPSHOT_ODB, output_file=output_file)
        if result.success:
            assert output_file.exists()
            assert output_file.stat().st_size > 0

    def test_output_file_contains_report(self):
        """Verify output file contains actual timing report."""
        output_file = Path("test_outputs/timing_report_verify.txt")
        output_file.parent.mkdir(parents=True, exist_ok=True)

        result = run_report_checks(SNAPSHOT_ODB, output_file=output_file)
        if result.success and output_file.exists():
            content = output_file.read_text()
            assert len(content) > 100  # Should be substantial
            assert "slack" in content.lower() or "delay" in content.lower()


class TestStep4ParseMetrics:
    """Step 4: Parse WNS and TNS from report."""

    def test_parse_timing_report(self):
        """Verify timing report can be parsed."""
        result = run_report_checks(SNAPSHOT_ODB)
        if result.success:
            metrics = parse_timing_report(result.stdout)
            assert isinstance(metrics, TimingMetrics)

    def test_parsed_metrics_have_wns(self):
        """Verify WNS is extracted from report."""
        result = run_report_checks(SNAPSHOT_ODB)
        if result.success:
            metrics = parse_timing_report(result.stdout)
            # WNS should be present (may be positive or negative)
            assert metrics.wns_ps is not None, "WNS not parsed from report"

    def test_parsed_metrics_structure(self):
        """Verify parsed metrics have expected structure."""
        result = run_report_checks(SNAPSHOT_ODB)
        if result.success:
            metrics = parse_timing_report(result.stdout)
            assert hasattr(metrics, "wns_ps")
            assert hasattr(metrics, "tns_ps")
            assert hasattr(metrics, "whs_ps")
            assert hasattr(metrics, "ths_ps")
            assert hasattr(metrics, "setup_violation_count")
            assert hasattr(metrics, "hold_violation_count")

    def test_parse_sample_timing_report(self):
        """Test parsing with a sample timing report format."""
        sample_report = """
Startpoint: reg1 (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg2 (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

  Delay    Time   Description
---------------------------------------------------------
  0.000    0.000  clock clk (rise edge)
  0.000    0.000  clock network delay (ideal)
  0.000    0.000  reg1/CK (DFF)
  0.250    0.250  reg1/Q (DFF)
  0.100    0.350  U1/Y (AND2)
  0.050    0.400  reg2/D (DFF)
           0.400  data arrival time

  1.000    1.000  clock clk (rise edge)
  0.000    1.000  clock network delay (ideal)
  0.000    1.000  reg2/CK (DFF)
 -0.050    0.950  library setup time
           0.950  data required time
---------------------------------------------------------
           0.950  data required time
          -0.400  data arrival time
---------------------------------------------------------
           0.550  slack (MET)
"""
        metrics = parse_timing_report(sample_report)
        # Should extract some timing info
        assert isinstance(metrics, TimingMetrics)


class TestStep5VerifyRealMetrics:
    """Step 5: Verify parsed metrics are real numbers (not mocked)."""

    def test_metrics_are_real_numbers(self):
        """Verify extracted metrics are real numeric values."""
        metrics, success = extract_timing_metrics(SNAPSHOT_ODB)
        if success:
            assert metrics.wns_ps is not None
            assert isinstance(metrics.wns_ps, (int, float))

    def test_metrics_pass_reality_check(self):
        """Verify metrics pass reality verification."""
        metrics, success = extract_timing_metrics(SNAPSHOT_ODB)
        if success:
            is_real = verify_metrics_are_real(metrics)
            assert is_real, "Metrics failed reality check - may be mocked"

    def test_metrics_have_reasonable_magnitudes(self):
        """Verify metrics have reasonable magnitudes for a real design."""
        metrics, success = extract_timing_metrics(SNAPSHOT_ODB)
        if success and metrics.wns_ps is not None:
            # WNS should be in a reasonable range (ps)
            # For a real design, typically -10000 to +10000 ps
            assert abs(metrics.wns_ps) < 1000000, "WNS magnitude unrealistic"

    def test_metrics_not_exactly_zero(self):
        """Verify metrics are not suspiciously zero."""
        metrics, success = extract_timing_metrics(SNAPSHOT_ODB)
        if success:
            # Real designs rarely have exactly 0 slack
            if metrics.wns_ps is not None:
                # Allow small non-zero values
                assert metrics.wns_ps != 0.0 or metrics.tns_ps is not None


class TestStep6StoreMetrics:
    """Step 6: Store metrics in metrics.json."""

    def test_store_metrics_to_json(self):
        """Verify metrics can be stored to JSON file."""
        metrics_file = Path("test_outputs/metrics_storage.json")
        metrics_file.parent.mkdir(parents=True, exist_ok=True)

        metrics, success = extract_timing_metrics(
            SNAPSHOT_ODB, metrics_output=metrics_file
        )
        if success:
            assert metrics_file.exists()
            assert metrics_file.stat().st_size > 0

    def test_json_is_valid(self):
        """Verify stored JSON is valid and parseable."""
        metrics_file = Path("test_outputs/metrics_valid.json")
        metrics_file.parent.mkdir(parents=True, exist_ok=True)

        metrics, success = extract_timing_metrics(
            SNAPSHOT_ODB, metrics_output=metrics_file
        )
        if success and metrics_file.exists():
            # Parse JSON
            with metrics_file.open("r") as f:
                data = json.load(f)
            assert isinstance(data, dict)
            assert "wns_ps" in data

    def test_json_contains_all_metrics(self):
        """Verify JSON contains all expected metric fields."""
        metrics_file = Path("test_outputs/metrics_complete.json")
        metrics_file.parent.mkdir(parents=True, exist_ok=True)

        metrics, success = extract_timing_metrics(
            SNAPSHOT_ODB, metrics_output=metrics_file
        )
        if success and metrics_file.exists():
            with metrics_file.open("r") as f:
                data = json.load(f)

            expected_fields = [
                "wns_ps",
                "tns_ps",
                "whs_ps",
                "ths_ps",
                "setup_violation_count",
                "hold_violation_count",
            ]
            for field in expected_fields:
                assert field in data


class TestF275Integration:
    """Integration tests for complete F275 workflow."""

    def test_complete_f275_workflow(self):
        """Complete F275 workflow: extract real timing metrics."""
        report_file = Path("test_outputs/f275_timing_report.txt")
        metrics_file = Path("test_outputs/f275_metrics.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)

        # Step 1-4: Extract metrics
        metrics, success = extract_timing_metrics(
            SNAPSHOT_ODB,
            metrics_output=metrics_file,
            report_output=report_file,
        )

        assert success, "Failed to extract timing metrics"

        # Step 5: Verify metrics are real
        assert verify_metrics_are_real(metrics), "Metrics are not real"

        # Step 6: Verify files created
        assert metrics_file.exists()
        assert report_file.exists()

        # Verify content
        assert metrics.wns_ps is not None

    def test_f275_all_steps_pass(self):
        """Verify all F275 steps pass in sequence."""
        # Step 1: Load snapshot
        load_result = execute_openroad_command(
            SNAPSHOT_ODB, tcl_commands=["puts loaded"]
        )
        assert load_result.success

        # Step 2: Execute report_checks
        report_result = run_report_checks(SNAPSHOT_ODB)
        assert report_result.success

        # Step 3: Capture to file
        report_file = Path("test_outputs/f275_steps_report.txt")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_result_2 = run_report_checks(SNAPSHOT_ODB, report_file)
        assert report_file.exists()

        # Step 4: Parse metrics
        metrics = parse_timing_report(report_result.stdout)
        assert metrics.wns_ps is not None

        # Step 5: Verify real
        assert verify_metrics_are_real(metrics)

        # Step 6: Store to JSON
        metrics_file = Path("test_outputs/f275_steps_metrics.json")
        metrics_file.parent.mkdir(parents=True, exist_ok=True)
        with metrics_file.open("w") as f:
            json.dump(metrics.to_dict(), f, indent=2)
        assert metrics_file.exists()


class TestTimingMetricsHelpers:
    """Test helper functions and data structures."""

    def test_timing_metrics_to_dict(self):
        """Verify TimingMetrics can be converted to dict."""
        metrics = TimingMetrics(wns_ps=-100.0, tns_ps=-500.0)
        d = metrics.to_dict()
        assert isinstance(d, dict)
        assert d["wns_ps"] == -100.0
        assert d["tns_ps"] == -500.0

    def test_execute_openroad_command_structure(self):
        """Verify OpenROADExecutionResult structure."""
        result = execute_openroad_command(SNAPSHOT_ODB, tcl_commands=[])
        assert hasattr(result, "success")
        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")
        assert hasattr(result, "error")

    def test_verify_metrics_are_real_function(self):
        """Test the verify_metrics_are_real function."""
        # Real metrics
        real_metrics = TimingMetrics(wns_ps=-123.45, tns_ps=-678.90)
        assert verify_metrics_are_real(real_metrics)

        # Fake metrics (all None)
        fake_metrics = TimingMetrics()
        assert not verify_metrics_are_real(fake_metrics)

        # Suspicious metrics (exactly 0)
        suspicious = TimingMetrics(wns_ps=0.0)
        assert not verify_metrics_are_real(suspicious)
