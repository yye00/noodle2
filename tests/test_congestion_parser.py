"""Tests for congestion report parser."""

import tempfile
from pathlib import Path

import pytest

from parsers.congestion import (
    format_congestion_summary,
    parse_congestion_json,
    parse_congestion_report,
    parse_congestion_report_file,
)


class TestParseCongestionReport:
    """Test parsing congestion reports from text."""

    def test_parse_basic_report(self):
        """Test parsing basic congestion report."""
        report = """
        Total bins: 10000
        Overflow bins: 150
        Max overflow: 25
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 10000
        assert metrics.bins_hot == 150
        assert metrics.hot_ratio == 0.015  # 150/10000
        assert metrics.max_overflow == 25

    def test_parse_no_congestion(self):
        """Test parsing report with no congestion."""
        report = """
        Total bins: 5000
        Overflow bins: 0
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 5000
        assert metrics.bins_hot == 0
        assert metrics.hot_ratio == 0.0

    def test_parse_alternative_format(self):
        """Test parsing alternative report format."""
        report = """
        total bins = 8000
        hot bins = 120
        maximum overflow = 30
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 8000
        assert metrics.bins_hot == 120
        assert metrics.hot_ratio == 0.015  # 120/8000
        assert metrics.max_overflow == 30

    def test_parse_bins_with_overflow_format(self):
        """Test parsing 'bins with overflow' format."""
        report = """
        Total bins: 12000
        Bins with overflow > 20%: 75
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 12000
        assert metrics.bins_hot == 75
        assert metrics.hot_ratio == 0.00625  # 75/12000

    def test_parse_with_layer_metrics(self):
        """Test parsing report with per-layer overflow."""
        report = """
        Total bins: 10000
        Overflow bins: 200
        Layer metal2 overflow: 50
        Layer metal3 overflow: 75
        Layer metal4 overflow: 45
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 10000
        assert metrics.bins_hot == 200
        assert metrics.layer_metrics["metal2"] == 50
        assert metrics.layer_metrics["metal3"] == 75
        assert metrics.layer_metrics["metal4"] == 45
        assert len(metrics.layer_metrics) == 3

    def test_parse_case_insensitive(self):
        """Test parsing is case insensitive."""
        report = """
        TOTAL BINS: 5000
        OVERFLOW BINS: 100
        MAX OVERFLOW: 15
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 5000
        assert metrics.bins_hot == 100
        assert metrics.max_overflow == 15

    def test_parse_with_whitespace_variations(self):
        """Test parsing handles various whitespace."""
        report = """
        Total bins:10000
        Overflow bins   :   150
        Max overflow  =25
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 10000
        assert metrics.bins_hot == 150
        assert metrics.max_overflow == 25

    def test_parse_missing_total_bins_raises_error(self):
        """Test parsing without total bins raises error."""
        report = """
        Overflow bins: 100
        """
        with pytest.raises(ValueError, match="Could not parse total bins"):
            parse_congestion_report(report)

    def test_parse_empty_report_raises_error(self):
        """Test parsing empty report raises error."""
        with pytest.raises(ValueError, match="Could not parse total bins"):
            parse_congestion_report("")

    def test_parse_defaults_hot_bins_to_zero(self):
        """Test hot bins default to 0 if not found."""
        report = """
        Total bins: 8000
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 8000
        assert metrics.bins_hot == 0
        assert metrics.hot_ratio == 0.0

    def test_parse_max_overflow_optional(self):
        """Test max overflow is optional."""
        report = """
        Total bins: 5000
        Overflow bins: 50
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 5000
        assert metrics.bins_hot == 50
        assert metrics.max_overflow is None

    def test_parse_with_extra_content(self):
        """Test parsing with extra irrelevant lines."""
        report = """
        OpenROAD congestion report
        Design: test_design
        Total bins: 10000
        Some other information
        Overflow bins: 150
        Another line
        Max overflow: 25
        End of report
        """
        metrics = parse_congestion_report(report)

        assert metrics.bins_total == 10000
        assert metrics.bins_hot == 150
        assert metrics.max_overflow == 25


class TestParseCongestionReportFile:
    """Test parsing congestion reports from files."""

    def test_parse_from_file(self):
        """Test parsing congestion report from file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("Total bins: 10000\n")
            f.write("Overflow bins: 150\n")
            f.write("Max overflow: 25\n")
            file_path = f.name

        try:
            metrics = parse_congestion_report_file(file_path)

            assert metrics.bins_total == 10000
            assert metrics.bins_hot == 150
            assert metrics.max_overflow == 25
        finally:
            Path(file_path).unlink()

    def test_parse_missing_file_raises_error(self):
        """Test parsing nonexistent file raises error."""
        with pytest.raises(FileNotFoundError, match="not found"):
            parse_congestion_report_file("/nonexistent/path/file.txt")


class TestParseCongestionJson:
    """Test parsing congestion metrics from JSON."""

    def test_parse_basic_json(self):
        """Test parsing basic JSON format."""
        json_data = {
            "bins_total": 10000,
            "bins_hot": 150,
            "max_overflow": 25,
        }
        metrics = parse_congestion_json(json_data)

        assert metrics.bins_total == 10000
        assert metrics.bins_hot == 150
        assert metrics.hot_ratio == 0.015
        assert metrics.max_overflow == 25

    def test_parse_json_with_overflow_bins_key(self):
        """Test parsing JSON with 'overflow_bins' key."""
        json_data = {
            "bins_total": 8000,
            "overflow_bins": 120,
        }
        metrics = parse_congestion_json(json_data)

        assert metrics.bins_total == 8000
        assert metrics.bins_hot == 120

    def test_parse_json_with_layer_metrics(self):
        """Test parsing JSON with per-layer metrics."""
        json_data = {
            "bins_total": 10000,
            "bins_hot": 200,
            "layer_metrics": {
                "metal2": 50,
                "metal3": 75,
                "metal4": 45,
            },
        }
        metrics = parse_congestion_json(json_data)

        assert metrics.bins_total == 10000
        assert metrics.bins_hot == 200
        assert metrics.layer_metrics["metal2"] == 50
        assert metrics.layer_metrics["metal3"] == 75

    def test_parse_json_defaults_bins_hot_to_zero(self):
        """Test JSON parsing defaults hot bins to 0."""
        json_data = {
            "bins_total": 5000,
        }
        metrics = parse_congestion_json(json_data)

        assert metrics.bins_total == 5000
        assert metrics.bins_hot == 0
        assert metrics.hot_ratio == 0.0

    def test_parse_json_missing_required_field(self):
        """Test parsing JSON without required fields raises error."""
        json_data = {
            "bins_hot": 150,
        }
        with pytest.raises(ValueError, match="Missing required field"):
            parse_congestion_json(json_data)


class TestFormatCongestionSummary:
    """Test formatting congestion metrics as human-readable text."""

    def test_format_basic_summary(self):
        """Test formatting basic congestion summary."""
        from controller.types import CongestionMetrics

        metrics = CongestionMetrics(
            bins_total=10000,
            bins_hot=150,
            hot_ratio=0.015,
            max_overflow=25,
        )
        summary = format_congestion_summary(metrics)

        assert "Total bins: 10000" in summary
        assert "Hot bins: 150" in summary
        assert "Hot ratio: 1.5%" in summary
        assert "Max overflow: 25" in summary

    def test_format_with_layer_metrics(self):
        """Test formatting with per-layer metrics."""
        from controller.types import CongestionMetrics

        metrics = CongestionMetrics(
            bins_total=10000,
            bins_hot=200,
            hot_ratio=0.02,
            layer_metrics={
                "metal2": 50,
                "metal3": 75,
                "metal4": 45,
            },
        )
        summary = format_congestion_summary(metrics)

        assert "Total bins: 10000" in summary
        assert "Hot bins: 200" in summary
        assert "Per-layer overflow:" in summary
        assert "metal2: 50" in summary
        assert "metal3: 75" in summary
        assert "metal4: 45" in summary

    def test_format_without_max_overflow(self):
        """Test formatting when max overflow is None."""
        from controller.types import CongestionMetrics

        metrics = CongestionMetrics(
            bins_total=5000,
            bins_hot=50,
            hot_ratio=0.01,
        )
        summary = format_congestion_summary(metrics)

        assert "Total bins: 5000" in summary
        assert "Hot bins: 50" in summary
        assert "Max overflow" not in summary

    def test_format_zero_hot_ratio(self):
        """Test formatting with zero hot ratio."""
        from controller.types import CongestionMetrics

        metrics = CongestionMetrics(
            bins_total=10000,
            bins_hot=0,
            hot_ratio=0.0,
        )
        summary = format_congestion_summary(metrics)

        assert "Hot ratio: 0.0%" in summary
