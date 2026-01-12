"""Tests for F218: Generate improvement summary quantifying differential heatmap changes."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.visualization.heatmap_renderer import (
    compute_heatmap_diff,
    compute_improvement_summary,
    generate_improvement_summary_json,
)


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


class TestImprovementSummaryF218:
    """
    Test suite for Feature F218: Generate improvement summary quantifying differential heatmap changes.

    Steps from feature_list.json:
    1. Generate differential heatmaps
    2. Compute improvement summary statistics
    3. Verify improved_bins count is calculated
    4. Verify worsened_bins count is calculated
    5. Verify net_improvement_pct is computed
    6. Verify max_improvement_region location is identified
    7. Export as improvement_summary.json
    """

    def test_step_1_generate_differential_heatmaps(self) -> None:
        """Step 1: Generate differential heatmaps."""
        # Create baseline and comparison heatmaps
        baseline = np.array(
            [
                [0.5, 0.6, 0.7],
                [0.6, 0.8, 0.6],
                [0.5, 0.6, 0.7],
            ]
        )

        comparison = np.array(
            [
                [0.4, 0.5, 0.6],  # Improved
                [0.5, 0.6, 0.5],  # Improved
                [0.4, 0.5, 0.6],  # Improved
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_csv = Path(tmpdir) / "baseline.csv"
            comparison_csv = Path(tmpdir) / "comparison.csv"

            create_test_heatmap_csv(baseline_csv, baseline)
            create_test_heatmap_csv(comparison_csv, comparison)

            # Compute differential
            diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

            # Verify differential computed
            assert diff is not None
            assert diff.shape == baseline.shape
            assert metadata is not None
            assert "improved_bins" in metadata
            assert "degraded_bins" in metadata

    def test_step_2_compute_improvement_summary_statistics(self) -> None:
        """Step 2: Compute improvement summary statistics."""
        # Create differential array with known pattern
        diff = np.array(
            [
                [0.1, 0.2, 0.3],  # All improved
                [-0.1, -0.2, 0.0],  # Mixed
                [0.1, 0.0, 0.1],  # Mostly improved
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff[diff > 0])),
            "total_degradation": float(np.abs(np.sum(diff[diff < 0]))),
        }

        # Compute summary
        summary = compute_improvement_summary(diff, metadata)

        # Verify summary computed
        assert summary is not None
        assert isinstance(summary, dict)
        assert "improved_bins" in summary
        assert "worsened_bins" in summary
        assert "unchanged_bins" in summary
        assert "net_improvement_pct" in summary
        assert "max_improvement_location" in summary

    def test_step_3_verify_improved_bins_count(self) -> None:
        """Step 3: Verify improved_bins count is calculated."""
        # Create differential with known improvement count
        diff = np.array(
            [
                [0.1, 0.2, 0.3],  # 3 improved
                [0.1, 0.2, 0.3],  # 3 improved
                [0.0, 0.0, 0.0],  # 0 improved
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff[diff > 0])),
            "total_degradation": 0.0,
        }

        summary = compute_improvement_summary(diff, metadata)

        # Verify improved bins count
        assert "improved_bins" in summary
        assert summary["improved_bins"] == 6, "Should count 6 bins with positive diff"
        assert summary["improved_bins"] == int(
            np.sum(diff > 0)
        ), "Should match numpy count"

    def test_step_4_verify_worsened_bins_count(self) -> None:
        """Step 4: Verify worsened_bins count is calculated."""
        # Create differential with known worsening count
        diff = np.array(
            [
                [-0.1, -0.2, 0.0],  # 2 worsened
                [-0.1, -0.2, 0.0],  # 2 worsened
                [0.1, 0.2, 0.3],  # 0 worsened
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff[diff > 0])),
            "total_degradation": float(np.abs(np.sum(diff[diff < 0]))),
        }

        summary = compute_improvement_summary(diff, metadata)

        # Verify worsened bins count
        assert "worsened_bins" in summary
        assert summary["worsened_bins"] == 4, "Should count 4 bins with negative diff"
        assert summary["worsened_bins"] == int(
            np.sum(diff < 0)
        ), "Should match numpy count"

    def test_step_5_verify_net_improvement_pct(self) -> None:
        """Step 5: Verify net_improvement_pct is computed."""
        # Create differential with known net improvement
        # 6 improved, 3 worsened, 0 unchanged = net +3 out of 9 = +33.33%
        diff = np.array(
            [
                [0.1, 0.2, 0.3],  # 3 improved
                [0.1, 0.2, 0.3],  # 3 improved
                [-0.1, -0.2, -0.3],  # 3 worsened
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff[diff > 0])),
            "total_degradation": float(np.abs(np.sum(diff[diff < 0]))),
        }

        summary = compute_improvement_summary(diff, metadata)

        # Verify net improvement percentage
        assert "net_improvement_pct" in summary

        # Calculate expected: (6 improved - 3 worsened) / 9 total * 100 = 33.33%
        expected_pct = (6 - 3) / 9 * 100
        assert (
            abs(summary["net_improvement_pct"] - expected_pct) < 0.01
        ), f"Expected {expected_pct}%, got {summary['net_improvement_pct']}%"

    def test_step_6_verify_max_improvement_region_location(self) -> None:
        """Step 6: Verify max_improvement_region location is identified."""
        # Create differential with known maximum at (1, 2)
        diff = np.array(
            [
                [0.1, 0.2, 0.3],
                [0.2, 0.3, 0.9],  # Maximum at row 1, col 2
                [0.1, 0.2, 0.3],
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff[diff > 0])),
            "total_degradation": 0.0,
        }

        summary = compute_improvement_summary(diff, metadata)

        # Verify max improvement location identified
        assert "max_improvement_location" in summary
        assert "max_improvement_value" in summary

        max_loc = summary["max_improvement_location"]
        assert max_loc["row"] == 1, "Max should be at row 1"
        assert max_loc["col"] == 2, "Max should be at col 2"
        assert (
            abs(summary["max_improvement_value"] - 0.9) < 0.01
        ), "Max value should be 0.9"

    def test_step_7_export_as_improvement_summary_json(self) -> None:
        """Step 7: Export as improvement_summary.json."""
        baseline = np.array(
            [
                [0.5, 0.6, 0.7],
                [0.6, 0.8, 0.6],
                [0.5, 0.6, 0.7],
            ]
        )

        comparison = np.array(
            [
                [0.4, 0.5, 0.6],
                [0.5, 0.6, 0.5],
                [0.4, 0.5, 0.6],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_csv = Path(tmpdir) / "baseline.csv"
            comparison_csv = Path(tmpdir) / "comparison.csv"
            summary_json = Path(tmpdir) / "improvement_summary.json"

            create_test_heatmap_csv(baseline_csv, baseline)
            create_test_heatmap_csv(comparison_csv, comparison)

            # Generate improvement summary JSON
            summary = generate_improvement_summary_json(
                baseline_csv=baseline_csv,
                comparison_csv=comparison_csv,
                output_path=summary_json,
            )

            # Verify JSON file created
            assert summary_json.exists(), "improvement_summary.json should be created"

            # Verify JSON is valid and contains expected fields
            with open(summary_json) as f:
                loaded_summary = json.load(f)

            assert loaded_summary == summary, "Loaded JSON should match returned summary"

            # Verify all required fields present
            required_fields = [
                "improved_bins",
                "worsened_bins",
                "unchanged_bins",
                "net_improvement_pct",
                "max_improvement_location",
                "max_improvement_value",
                "total_bins",
                "baseline_csv",
                "comparison_csv",
                "heatmap_shape",
            ]

            for field in required_fields:
                assert field in loaded_summary, f"Field {field} should be in JSON"

    def test_complete_f218_workflow(self) -> None:
        """Test complete F218 workflow: differential heatmaps -> improvement summary JSON."""
        # Simulate realistic ECO impact scenario
        baseline = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],
                [0.3, 0.5, 0.6, 0.5, 0.3],
                [0.4, 0.6, 0.9, 0.6, 0.4],  # Dense hotspot
                [0.3, 0.5, 0.6, 0.5, 0.3],
                [0.2, 0.3, 0.4, 0.3, 0.2],
            ]
        )

        # ECO successfully reduces density in hotspot
        comparison = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],  # Unchanged
                [0.3, 0.4, 0.5, 0.4, 0.3],  # Improved
                [0.4, 0.5, 0.6, 0.5, 0.4],  # Significantly improved
                [0.3, 0.4, 0.5, 0.4, 0.3],  # Improved
                [0.2, 0.3, 0.4, 0.3, 0.2],  # Unchanged
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_csv = Path(tmpdir) / "baseline_placement_density.csv"
            comparison_csv = Path(tmpdir) / "comparison_placement_density.csv"
            summary_json = Path(tmpdir) / "improvement_summary.json"

            create_test_heatmap_csv(baseline_csv, baseline)
            create_test_heatmap_csv(comparison_csv, comparison)

            # Step 1: Generate differential heatmaps
            diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

            # Step 2: Compute improvement summary
            summary = compute_improvement_summary(diff, diff_metadata)

            # Step 3: Verify improved bins
            assert summary["improved_bins"] > 0, "Should have improved bins"

            # Step 4: Verify worsened bins (should be 0 in this scenario)
            assert summary["worsened_bins"] == 0, "No bins should worsen in this ECO"

            # Step 5: Verify net improvement percentage
            assert (
                summary["net_improvement_pct"] > 0
            ), "Net improvement should be positive"

            # Step 6: Verify max improvement location (should be hotspot center at [2,2])
            max_loc = summary["max_improvement_location"]
            assert max_loc["row"] == 2, "Max improvement should be at hotspot center row"
            assert max_loc["col"] == 2, "Max improvement should be at hotspot center col"

            # Step 7: Export as JSON
            final_summary = generate_improvement_summary_json(
                baseline_csv=baseline_csv,
                comparison_csv=comparison_csv,
                output_path=summary_json,
            )

            assert summary_json.exists()

            # Verify JSON content
            with open(summary_json) as f:
                loaded = json.load(f)

            assert loaded["improved_bins"] == summary["improved_bins"]
            assert loaded["net_improvement_pct"] == summary["net_improvement_pct"]
            assert loaded["max_improvement_location"] == summary["max_improvement_location"]

    def test_improvement_summary_with_mixed_results(self) -> None:
        """Test improvement summary with both improvements and degradations."""
        # Create scenario with mixed results
        diff = np.array(
            [
                [0.3, 0.2, 0.1],  # 3 improved
                [-0.1, 0.0, 0.1],  # 1 worsened, 1 unchanged, 1 improved
                [0.2, 0.1, -0.2],  # 2 improved, 1 worsened
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff[diff > 0])),
            "total_degradation": float(np.abs(np.sum(diff[diff < 0]))),
        }

        summary = compute_improvement_summary(diff, metadata)

        # Verify counts
        assert summary["improved_bins"] == 6, "Should have 6 improved bins"
        assert summary["worsened_bins"] == 2, "Should have 2 worsened bins"
        assert summary["unchanged_bins"] == 1, "Should have 1 unchanged bin"
        assert summary["total_bins"] == 9, "Total should be 9 bins"

        # Verify net improvement
        # (6 - 2) / 9 * 100 = 44.44%
        expected_net = (6 - 2) / 9 * 100
        assert abs(summary["net_improvement_pct"] - expected_net) < 0.01

    def test_improvement_summary_all_unchanged(self) -> None:
        """Test improvement summary when no changes occurred."""
        diff = np.zeros((3, 3))

        metadata = {
            "mean_diff": 0.0,
            "total_improvement": 0.0,
            "total_degradation": 0.0,
        }

        summary = compute_improvement_summary(diff, metadata)

        assert summary["improved_bins"] == 0
        assert summary["worsened_bins"] == 0
        assert summary["unchanged_bins"] == 9
        assert summary["net_improvement_pct"] == 0.0

    def test_improvement_summary_json_schema(self) -> None:
        """Test that improvement summary JSON has correct schema."""
        baseline = np.array([[0.5, 0.6], [0.7, 0.8]])
        comparison = np.array([[0.4, 0.5], [0.6, 0.7]])

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_csv = Path(tmpdir) / "baseline.csv"
            comparison_csv = Path(tmpdir) / "comparison.csv"
            summary_json = Path(tmpdir) / "summary.json"

            create_test_heatmap_csv(baseline_csv, baseline)
            create_test_heatmap_csv(comparison_csv, comparison)

            summary = generate_improvement_summary_json(
                baseline_csv, comparison_csv, summary_json
            )

            # Verify schema
            assert isinstance(summary["improved_bins"], int)
            assert isinstance(summary["worsened_bins"], int)
            assert isinstance(summary["unchanged_bins"], int)
            assert isinstance(summary["total_bins"], int)
            assert isinstance(summary["net_improvement_pct"], (int, float))
            assert isinstance(summary["max_improvement_value"], (int, float))
            assert isinstance(summary["max_improvement_location"], dict)
            assert "row" in summary["max_improvement_location"]
            assert "col" in summary["max_improvement_location"]
            assert isinstance(summary["baseline_csv"], str)
            assert isinstance(summary["comparison_csv"], str)
            assert isinstance(summary["heatmap_shape"], list)

    def test_max_improvement_region_identification(self) -> None:
        """Test that max improvement region is correctly identified."""
        # Create diff with clear maximum at specific location
        diff = np.array(
            [
                [0.1, 0.1, 0.1, 0.1, 0.1],
                [0.1, 0.2, 0.2, 0.2, 0.1],
                [0.1, 0.2, 0.5, 0.2, 0.1],  # Max at (2, 2)
                [0.1, 0.2, 0.2, 0.2, 0.1],
                [0.1, 0.1, 0.1, 0.1, 0.1],
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff)),
            "total_degradation": 0.0,
        }

        summary = compute_improvement_summary(diff, metadata)

        # Verify max location
        assert summary["max_improvement_value"] == 0.5
        assert summary["max_improvement_location"]["row"] == 2
        assert summary["max_improvement_location"]["col"] == 2

    def test_improvement_summary_includes_degradation_location(self) -> None:
        """Test that improvement summary also identifies max degradation location."""
        diff = np.array(
            [
                [0.1, 0.2, 0.3],
                [0.2, -0.8, 0.2],  # Max degradation at (1, 1)
                [0.1, 0.2, 0.3],
            ]
        )

        metadata = {
            "mean_diff": float(np.mean(diff)),
            "total_improvement": float(np.sum(diff[diff > 0])),
            "total_degradation": float(np.abs(np.sum(diff[diff < 0]))),
        }

        summary = compute_improvement_summary(diff, metadata)

        # Verify max degradation tracked
        assert "max_degradation_value" in summary
        assert "max_degradation_location" in summary
        assert summary["max_degradation_value"] == -0.8
        assert summary["max_degradation_location"]["row"] == 1
        assert summary["max_degradation_location"]["col"] == 1
