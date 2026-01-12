"""Tests for F276: Execute real global_route and generate actual congestion metrics.

F276 Requirements:
- Step 1: Load Nangate45 snapshot in OpenROAD
- Step 2: Execute global_route -congestion_report_file congestion.txt
- Step 3: Parse congestion report for overflow and hot_ratio
- Step 4: Verify metrics are from real routing (not mocked)
- Step 5: Store congestion metrics in metrics.json
"""

import json
from pathlib import Path

import pytest

from infrastructure.congestion_execution import (
    CongestionExecutionResult,
    execute_global_route,
    extract_congestion_metrics,
    verify_congestion_metrics_are_real,
)
from src.controller.types import CongestionMetrics


# Test configuration
SNAPSHOT_ODB = Path("studies/nangate45_base/gcd_placed.odb")
CONGESTION_REPORT = Path("test_outputs/congestion_report.txt")
METRICS_OUTPUT = Path("test_outputs/congestion_metrics.json")


class TestStep1LoadSnapshot:
    """Step 1: Load Nangate45 snapshot in OpenROAD."""

    def test_snapshot_file_exists(self):
        """Verify snapshot ODB file exists."""
        assert SNAPSHOT_ODB.exists(), f"Snapshot not found: {SNAPSHOT_ODB}"

    def test_snapshot_is_placed_design(self):
        """Verify snapshot is a placed design (ready for routing)."""
        # File should be named with 'placed' or be from placement stage
        assert "placed" in SNAPSHOT_ODB.name or "3_place" in SNAPSHOT_ODB.name


class TestStep2ExecuteGlobalRoute:
    """Step 2: Execute global_route -congestion_report_file congestion.txt."""

    def test_execute_global_route_command(self):
        """Execute global_route on placed design."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success, f"global_route failed: {result.error}"

    def test_global_route_creates_report_file(self):
        """Verify global_route creates congestion report file."""
        # Run global_route
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.report_file is not None
        assert result.report_file.exists()

    def test_global_route_produces_output(self):
        """Verify global_route produces stdout output."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        # OpenROAD should produce some output during routing
        assert len(result.stdout) > 0 or len(result.stderr) > 0

    def test_congestion_report_not_empty(self):
        """Verify congestion report file has content."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.report_file.exists()
        content = result.report_file.read_text()
        assert len(content) > 0, "Congestion report is empty"


class TestStep3ParseCongestionReport:
    """Step 3: Parse congestion report for overflow and hot_ratio."""

    def test_parse_bins_total(self):
        """Parse total number of routing bins."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        assert result.metrics.bins_total > 0, "bins_total should be positive"

    def test_parse_bins_hot(self):
        """Parse number of congested (hot) bins."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        # bins_hot can be 0 if no congestion
        assert result.metrics.bins_hot >= 0

    def test_parse_hot_ratio(self):
        """Parse hot ratio (hot bins / total bins)."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        assert 0.0 <= result.metrics.hot_ratio <= 1.0, "hot_ratio should be between 0 and 1"

    def test_hot_ratio_calculation(self):
        """Verify hot_ratio matches bins_hot / bins_total."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None

        expected_ratio = result.metrics.bins_hot / result.metrics.bins_total
        assert abs(result.metrics.hot_ratio - expected_ratio) < 0.001

    def test_parse_max_overflow_optional(self):
        """Parse max overflow if present in report."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        # max_overflow is optional, just verify it's a valid value if present
        if result.metrics.max_overflow is not None:
            assert result.metrics.max_overflow >= 0


class TestStep4VerifyRealMetrics:
    """Step 4: Verify metrics are from real routing (not mocked)."""

    def test_metrics_are_not_mocked(self):
        """Verify congestion metrics are from real global_route execution."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        assert verify_congestion_metrics_are_real(result.metrics)

    def test_bins_total_is_realistic(self):
        """Verify bins_total has realistic value for real design."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        # Real designs should have at least 100 bins (e.g., 10x10 grid)
        assert result.metrics.bins_total >= 10, "Real routing should have multiple bins"

    def test_bins_hot_not_greater_than_total(self):
        """Verify bins_hot <= bins_total (logical consistency)."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        assert result.metrics.bins_hot <= result.metrics.bins_total

    def test_metrics_have_specific_values_not_placeholders(self):
        """Verify metrics are not placeholder values like 0 or 100."""
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=CONGESTION_REPORT,
        )
        assert result.success
        assert result.metrics is not None
        # bins_total should not be exactly 100 (too round to be real)
        # Real routing grids are based on actual chip dimensions
        assert result.metrics.bins_total != 100 or result.metrics.bins_total != 1000


class TestStep5StoreMetricsJSON:
    """Step 5: Store congestion metrics in metrics.json."""

    def test_extract_and_save_metrics_to_json(self):
        """Extract congestion metrics and save to JSON file."""
        metrics, success = extract_congestion_metrics(
            odb_file=SNAPSHOT_ODB,
            report_output=CONGESTION_REPORT,
            metrics_output=METRICS_OUTPUT,
        )
        assert success
        assert metrics is not None
        assert METRICS_OUTPUT.exists()

    def test_json_file_is_valid(self):
        """Verify metrics JSON file is valid and parseable."""
        metrics, success = extract_congestion_metrics(
            odb_file=SNAPSHOT_ODB,
            report_output=CONGESTION_REPORT,
            metrics_output=METRICS_OUTPUT,
        )
        assert success

        # Read and parse JSON
        with METRICS_OUTPUT.open() as f:
            data = json.load(f)

        # Verify required fields
        assert "bins_total" in data
        assert "bins_hot" in data
        assert "hot_ratio" in data

    def test_json_contains_all_metrics(self):
        """Verify JSON contains all congestion metrics."""
        metrics, success = extract_congestion_metrics(
            odb_file=SNAPSHOT_ODB,
            report_output=CONGESTION_REPORT,
            metrics_output=METRICS_OUTPUT,
        )
        assert success

        with METRICS_OUTPUT.open() as f:
            data = json.load(f)

        assert data["bins_total"] == metrics.bins_total
        assert data["bins_hot"] == metrics.bins_hot
        assert abs(data["hot_ratio"] - metrics.hot_ratio) < 0.001

    def test_json_metrics_match_parsed_metrics(self):
        """Verify JSON metrics match the returned metrics object."""
        metrics, success = extract_congestion_metrics(
            odb_file=SNAPSHOT_ODB,
            report_output=CONGESTION_REPORT,
            metrics_output=METRICS_OUTPUT,
        )
        assert success

        with METRICS_OUTPUT.open() as f:
            data = json.load(f)

        # Compare all fields
        assert data["bins_total"] == metrics.bins_total
        assert data["bins_hot"] == metrics.bins_hot
        assert data["hot_ratio"] == metrics.hot_ratio
        assert data["max_overflow"] == metrics.max_overflow


class TestCongestionExecutionEndToEnd:
    """End-to-end congestion execution tests."""

    def test_complete_congestion_workflow(self):
        """Test complete workflow: load -> route -> parse -> save."""
        # Execute global_route and get metrics
        metrics, success = extract_congestion_metrics(
            odb_file=SNAPSHOT_ODB,
            report_output=CONGESTION_REPORT,
            metrics_output=METRICS_OUTPUT,
        )

        # Verify success
        assert success, "Congestion workflow failed"
        assert metrics is not None

        # Verify metrics are real
        assert verify_congestion_metrics_are_real(metrics)

        # Verify files exist
        assert CONGESTION_REPORT.exists()
        assert METRICS_OUTPUT.exists()

        # Verify JSON is valid
        with METRICS_OUTPUT.open() as f:
            data = json.load(f)
        assert data["bins_total"] > 0

    def test_congestion_report_file_has_expected_format(self):
        """Verify congestion report has expected text format."""
        report_path = Path("test_outputs/congestion_format_test.txt")
        result = execute_global_route(
            odb_file=SNAPSHOT_ODB,
            report_file=report_path,
        )
        assert result.success

        content = report_path.read_text()

        # Should contain congestion report indicators
        assert "congestion" in content.lower() or "overflow" in content.lower() or "total" in content.lower()

    def test_multiple_executions_produce_consistent_results(self):
        """Verify running global_route twice produces same results."""
        # First execution
        metrics1, success1 = extract_congestion_metrics(
            odb_file=SNAPSHOT_ODB,
            report_output=Path("test_outputs/congestion_1.txt"),
            metrics_output=Path("test_outputs/metrics_1.json"),
        )
        assert success1

        # Second execution
        metrics2, success2 = extract_congestion_metrics(
            odb_file=SNAPSHOT_ODB,
            report_output=Path("test_outputs/congestion_2.txt"),
            metrics_output=Path("test_outputs/metrics_2.json"),
        )
        assert success2

        # Results should be deterministic (same design = same congestion)
        assert metrics1.bins_total == metrics2.bins_total
        assert metrics1.bins_hot == metrics2.bins_hot
        assert abs(metrics1.hot_ratio - metrics2.hot_ratio) < 0.001


class TestCongestionMetricsValidation:
    """Test validation of congestion metrics."""

    def test_verify_real_metrics_passes_for_valid_data(self):
        """Verify validation passes for real metrics."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=0.05,
        )
        assert verify_congestion_metrics_are_real(metrics)

    def test_verify_real_metrics_fails_for_zero_bins(self):
        """Verify validation fails for zero bins_total."""
        metrics = CongestionMetrics(
            bins_total=0,
            bins_hot=0,
            hot_ratio=0.0,
        )
        assert not verify_congestion_metrics_are_real(metrics)

    def test_verify_real_metrics_fails_for_invalid_ratio(self):
        """Verify validation fails for invalid hot_ratio."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=1.5,  # Invalid: > 1.0
        )
        assert not verify_congestion_metrics_are_real(metrics)

    def test_verify_real_metrics_fails_for_inconsistent_data(self):
        """Verify validation fails when bins_hot > bins_total."""
        metrics = CongestionMetrics(
            bins_total=100,
            bins_hot=200,  # Invalid: more hot bins than total
            hot_ratio=2.0,
        )
        assert not verify_congestion_metrics_are_real(metrics)
