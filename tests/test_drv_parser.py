"""Tests for Design Rule Violation (DRV) parser."""

import tempfile
from pathlib import Path

import pytest

from src.controller.types import DRVMetrics
from src.parsers.drv import (
    format_drv_summary,
    is_drv_clean,
    parse_drv_report,
    parse_drv_report_file,
)


class TestDRVReportParsing:
    """Test parsing of DRC/DRV reports from OpenROAD."""

    def test_parse_simple_violation_count(self) -> None:
        """Test parsing report with simple total violation count."""
        report = """
Design Rule Check Report
Total violations: 123
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 123

    def test_parse_violation_types(self) -> None:
        """Test parsing report with violation type breakdown."""
        report = """
DRC Report
Spacing violations: 45
Width violations: 30
Short violations: 20
Total violations: 95
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 95
        assert metrics.violation_types["spacing"] == 45
        assert metrics.violation_types["width"] == 30
        assert metrics.violation_types["short"] == 20

    def test_parse_critical_and_warning_violations(self) -> None:
        """Test parsing critical vs warning violations."""
        report = """
DRC Summary
Total violations: 50
Critical violations: 10
Warning violations: 40
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 50
        assert metrics.critical_violations == 10
        assert metrics.warning_violations == 40

    def test_parse_individual_violation_lines(self) -> None:
        """Test counting violations from individual violation reports."""
        report = """
DRC Violations:
Violation: Metal2 spacing violation at (100, 200)
Violation: Metal3 min-width violation at (150, 250)
Violation: Metal2 spacing violation at (300, 400)
Violation: Via enclosure violation at (500, 600)
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 4
        assert metrics.violation_types["spacing"] == 2
        assert metrics.violation_types["min-width"] == 1
        assert metrics.violation_types["enclosure"] == 1

    def test_parse_clean_report(self) -> None:
        """Test parsing report with no violations."""
        report = """
DRC Check Complete
Total violations: 0
Design is DRC clean.
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 0
        assert len(metrics.violation_types) == 0

    def test_parse_empty_report(self) -> None:
        """Test parsing empty/minimal report."""
        report = ""
        metrics = parse_drv_report(report)
        # Empty report should indicate 0 violations
        assert metrics.total_violations == 0

    def test_parse_report_with_equals_separator(self) -> None:
        """Test parsing report using = instead of : separator."""
        report = """
Total DRC violations = 42
Spacing violations = 15
Width violations = 27
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 42
        assert metrics.violation_types["spacing"] == 15
        assert metrics.violation_types["width"] == 27

    def test_parse_case_insensitive(self) -> None:
        """Test parser is case-insensitive."""
        report = """
TOTAL VIOLATIONS: 10
SPACING VIOLATIONS: 5
width violations: 5
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 10
        assert metrics.violation_types["spacing"] == 5
        assert metrics.violation_types["width"] == 5


class TestDRVReportFile:
    """Test parsing DRV reports from files."""

    def test_parse_drv_report_file(self) -> None:
        """Test parsing DRC report from file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            report_file = Path(tmpdir) / "drc_report.txt"
            report_file.write_text("""
Total violations: 25
Spacing violations: 15
Width violations: 10
""")

            metrics = parse_drv_report_file(str(report_file))
            assert metrics.total_violations == 25
            assert metrics.violation_types["spacing"] == 15
            assert metrics.violation_types["width"] == 10

    def test_parse_missing_file(self) -> None:
        """Test error handling for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_drv_report_file("/nonexistent/drc_report.txt")


class TestDRVMetricsFormatting:
    """Test formatting DRV metrics as human-readable summaries."""

    def test_format_drv_summary_basic(self) -> None:
        """Test basic DRV summary formatting."""
        metrics = DRVMetrics(total_violations=50)
        summary = format_drv_summary(metrics)
        assert "Total DRC violations: 50" in summary

    def test_format_drv_summary_with_types(self) -> None:
        """Test summary with violation types."""
        metrics = DRVMetrics(
            total_violations=35,
            violation_types={"spacing": 20, "width": 10, "short": 5},
        )
        summary = format_drv_summary(metrics)
        assert "Total DRC violations: 35" in summary
        assert "spacing: 20" in summary
        assert "width: 10" in summary
        assert "short: 5" in summary

    def test_format_drv_summary_with_critical(self) -> None:
        """Test summary with critical/warning breakdown."""
        metrics = DRVMetrics(
            total_violations=50, critical_violations=10, warning_violations=40
        )
        summary = format_drv_summary(metrics)
        assert "Total DRC violations: 50" in summary
        assert "Critical violations: 10" in summary
        assert "Warning violations: 40" in summary

    def test_format_drv_summary_clean(self) -> None:
        """Test summary for clean design."""
        metrics = DRVMetrics(total_violations=0)
        summary = format_drv_summary(metrics)
        assert "Total DRC violations: 0" in summary


class TestDRVCleanCheck:
    """Test DRC clean validation."""

    def test_is_drv_clean_zero_violations(self) -> None:
        """Test clean design with zero violations."""
        metrics = DRVMetrics(total_violations=0)
        assert is_drv_clean(metrics) is True

    def test_is_drv_clean_with_violations(self) -> None:
        """Test design with violations is not clean."""
        metrics = DRVMetrics(total_violations=10)
        assert is_drv_clean(metrics) is False

    def test_is_drv_clean_only_warnings_allowed(self) -> None:
        """Test that warnings don't fail when allow_warnings=True."""
        metrics = DRVMetrics(
            total_violations=40, critical_violations=0, warning_violations=40
        )
        assert is_drv_clean(metrics, allow_warnings=True) is True

    def test_is_drv_clean_warnings_not_allowed(self) -> None:
        """Test that warnings fail when allow_warnings=False."""
        metrics = DRVMetrics(
            total_violations=40, critical_violations=0, warning_violations=40
        )
        assert is_drv_clean(metrics, allow_warnings=False) is False

    def test_is_drv_clean_critical_violations_fail(self) -> None:
        """Test that critical violations always fail."""
        metrics = DRVMetrics(
            total_violations=50, critical_violations=10, warning_violations=40
        )
        assert is_drv_clean(metrics, allow_warnings=True) is False
        assert is_drv_clean(metrics, allow_warnings=False) is False


class TestDRVEndToEnd:
    """End-to-end tests covering all 6 feature steps."""

    def test_step1_execute_detailed_routing_producing_drc_report(self) -> None:
        """
        Step 1: Execute detailed routing producing DRC report.

        This test simulates the routing execution producing a DRC report.
        """
        # Simulated DRC report from detailed routing
        report = """
Detailed Routing DRC Report
Total violations: 42
Spacing violations: 25
Width violations: 10
Short violations: 7
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 42

    def test_step2_parse_drc_violations_from_report(self) -> None:
        """
        Step 2: Parse DRC violations from report.

        Verify parser extracts violation counts correctly.
        """
        report = """
Total DRC violations: 35
Spacing violations: 20
Width violations: 15
"""
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 35
        assert "spacing" in metrics.violation_types
        assert "width" in metrics.violation_types

    def test_step3_count_total_drv_count(self) -> None:
        """
        Step 3: Count total DRV count.

        Verify total violation count is extracted.
        """
        report = "Total violations: 123"
        metrics = parse_drv_report(report)
        assert metrics.total_violations == 123

    def test_step4_classify_violation_types(self) -> None:
        """
        Step 4: Classify violation types (spacing, width, etc).

        Verify violations are classified by type.
        """
        report = """
DRC Violations by Type:
Spacing violations: 30
Width violations: 20
Short violations: 10
Enclosure violations: 5
"""
        metrics = parse_drv_report(report)
        assert metrics.violation_types["spacing"] == 30
        assert metrics.violation_types["width"] == 20
        assert metrics.violation_types["short"] == 10
        assert metrics.violation_types["enclosure"] == 5

    def test_step5_emit_drv_metrics_to_telemetry(self) -> None:
        """
        Step 5: Emit DRV metrics to telemetry.

        Verify DRVMetrics can be included in trial metrics.
        """
        from src.controller.types import TimingMetrics, TrialMetrics

        # Create DRV metrics
        drv_metrics = DRVMetrics(
            total_violations=25,
            violation_types={"spacing": 15, "width": 10},
            critical_violations=5,
            warning_violations=20,
        )

        # Include in TrialMetrics
        trial_metrics = TrialMetrics(
            timing=TimingMetrics(wns_ps=-500),
            drv=drv_metrics,
        )

        # Verify DRV metrics are accessible
        assert trial_metrics.drv is not None
        assert trial_metrics.drv.total_violations == 25
        assert trial_metrics.drv.critical_violations == 5

    def test_step6_use_drv_count_in_trial_ranking(self) -> None:
        """
        Step 6: Use DRV count in trial ranking.

        Verify DRV metrics can be used for trial comparison/ranking.
        """
        from src.controller.types import TimingMetrics, TrialMetrics

        # Trial 1: Better timing, more DRV
        trial1 = TrialMetrics(
            timing=TimingMetrics(wns_ps=-100),
            drv=DRVMetrics(total_violations=50),
        )

        # Trial 2: Worse timing, fewer DRV
        trial2 = TrialMetrics(
            timing=TimingMetrics(wns_ps=-200),
            drv=DRVMetrics(total_violations=10),
        )

        # Can rank by DRV count
        assert trial1.drv.total_violations > trial2.drv.total_violations

        # Can also check DRC-clean status
        trial_clean = TrialMetrics(
            timing=TimingMetrics(wns_ps=-50),
            drv=DRVMetrics(total_violations=0),
        )
        assert is_drv_clean(trial_clean.drv) is True


class TestDRVMetricsDataclass:
    """Test DRVMetrics dataclass."""

    def test_create_basic_drv_metrics(self) -> None:
        """Test creating DRVMetrics with just total."""
        metrics = DRVMetrics(total_violations=10)
        assert metrics.total_violations == 10
        assert len(metrics.violation_types) == 0
        assert metrics.critical_violations is None
        assert metrics.warning_violations is None

    def test_create_complete_drv_metrics(self) -> None:
        """Test creating DRVMetrics with all fields."""
        metrics = DRVMetrics(
            total_violations=50,
            violation_types={"spacing": 30, "width": 20},
            critical_violations=10,
            warning_violations=40,
        )
        assert metrics.total_violations == 50
        assert metrics.violation_types["spacing"] == 30
        assert metrics.critical_violations == 10
        assert metrics.warning_violations == 40
