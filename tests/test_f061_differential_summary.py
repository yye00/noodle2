"""
Tests for F061: Differential summary quantifies improvement per region.

This test file verifies that differential summaries can be computed to quantify
improvement per region after ECO application. Each test maps to a specific step
in the F061 feature specification.

Feature Steps:
1. Compute differential heatmap
2. Count bins with delta < 0 (improved)
3. Count bins with delta > 0 (worsened)
4. Count unchanged bins
5. Calculate net_improvement_pct
6. Save summary as JSON with improved_bins, worsened_bins, net_improvement_pct
"""

import json
from pathlib import Path

import numpy as np
import pytest

from src.visualization.heatmap_renderer import (
    compute_heatmap_diff,
    compute_improvement_summary,
    generate_improvement_summary_json,
)


# --- Helper Functions ---


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file from numpy array."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


# --- Test Fixtures ---


@pytest.fixture
def baseline_heatmap() -> np.ndarray:
    """Baseline heatmap (before ECO) with hotspot."""
    return np.array(
        [
            [10.0, 20.0, 30.0, 20.0, 10.0],
            [20.0, 40.0, 60.0, 40.0, 20.0],
            [30.0, 60.0, 90.0, 60.0, 30.0],  # Central hotspot
            [20.0, 40.0, 60.0, 40.0, 20.0],
            [10.0, 20.0, 30.0, 20.0, 10.0],
        ],
        dtype=np.float64,
    )


@pytest.fixture
def improved_heatmap() -> np.ndarray:
    """Improved heatmap (after ECO) with reduced hotspot."""
    return np.array(
        [
            [10.0, 20.0, 30.0, 20.0, 10.0],  # Unchanged
            [20.0, 35.0, 50.0, 35.0, 20.0],  # Improved
            [30.0, 50.0, 70.0, 50.0, 30.0],  # Significantly improved (90 -> 70)
            [20.0, 35.0, 50.0, 35.0, 20.0],  # Improved
            [10.0, 20.0, 30.0, 20.0, 10.0],  # Unchanged
        ],
        dtype=np.float64,
    )


@pytest.fixture
def mixed_impact_heatmap() -> np.ndarray:
    """Mixed impact heatmap with both improvement and degradation."""
    return np.array(
        [
            [15.0, 25.0, 35.0, 25.0, 15.0],  # Degraded (increased)
            [20.0, 35.0, 50.0, 35.0, 20.0],  # Improved
            [30.0, 50.0, 70.0, 50.0, 30.0],  # Improved
            [20.0, 45.0, 65.0, 45.0, 20.0],  # Mixed
            [10.0, 20.0, 30.0, 20.0, 10.0],  # Unchanged
        ],
        dtype=np.float64,
    )


# --- F061 Feature Step Tests ---


class TestF061Step1ComputeDifferentialHeatmap:
    """Step 1: Compute differential heatmap."""

    def test_compute_differential_heatmap(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify we can compute differential heatmap from baseline and comparison."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute differential heatmap
        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Verify diff array shape matches input
        assert diff.shape == baseline_heatmap.shape

        # Verify diff is computed correctly (baseline - comparison)
        expected_diff = baseline_heatmap - improved_heatmap
        np.testing.assert_array_almost_equal(diff, expected_diff)

        # Verify metadata is returned
        assert isinstance(metadata, dict)
        assert "shape" in metadata


class TestF061Step2CountImprovedBins:
    """Step 2: Count bins with delta < 0 (improved)."""

    def test_count_improved_bins(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify counting of improved bins (positive diff = reduced congestion)."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Verify improved_bins is present
        assert "improved_bins" in summary

        # Count expected improved bins manually
        expected_improved = int(np.sum(diff > 0))
        assert summary["improved_bins"] == expected_improved

        # For this test case, should have some improvements
        assert summary["improved_bins"] > 0

    def test_improved_bins_means_positive_diff(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify improved bins correspond to positive diff values."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Improved bins should match positive diff count
        improved_mask = diff > 0
        assert summary["improved_bins"] == np.sum(improved_mask)


class TestF061Step3CountWorsenedBins:
    """Step 3: Count bins with delta > 0 (worsened)."""

    def test_count_worsened_bins(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify counting of worsened bins (negative diff = increased congestion)."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Verify worsened_bins is present
        assert "worsened_bins" in summary

        # Count expected worsened bins manually
        expected_worsened = int(np.sum(diff < 0))
        assert summary["worsened_bins"] == expected_worsened

    def test_worsened_bins_with_degradation(
        self, tmp_path: Path, baseline_heatmap: np.ndarray
    ) -> None:
        """Verify worsened bins count when degradation occurs."""
        baseline_csv = tmp_path / "baseline.csv"
        degraded_csv = tmp_path / "degraded.csv"

        # Create degraded version (worse congestion)
        degraded_heatmap = baseline_heatmap * 1.5

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(degraded_csv, degraded_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, degraded_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # All bins should be worsened
        assert summary["worsened_bins"] == 25  # 5x5 grid
        assert summary["improved_bins"] == 0


class TestF061Step4CountUnchangedBins:
    """Step 4: Count unchanged bins."""

    def test_count_unchanged_bins(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify counting of unchanged bins (zero diff)."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Verify unchanged_bins is present
        assert "unchanged_bins" in summary

        # Count expected unchanged bins manually
        expected_unchanged = int(np.sum(diff == 0))
        assert summary["unchanged_bins"] == expected_unchanged

    def test_all_bins_unchanged_when_identical(self, tmp_path: Path) -> None:
        """Verify all bins unchanged when before and after are identical."""
        identical_data = np.ones((5, 5)) * 50.0

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, identical_data)
        create_test_heatmap_csv(comparison_csv, identical_data)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # All bins should be unchanged
        assert summary["unchanged_bins"] == 25
        assert summary["improved_bins"] == 0
        assert summary["worsened_bins"] == 0

    def test_total_bins_equals_sum_of_categories(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify total_bins = improved + worsened + unchanged."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Verify accounting
        total = summary["improved_bins"] + summary["worsened_bins"] + summary["unchanged_bins"]
        assert total == summary["total_bins"]
        assert summary["total_bins"] == 25  # 5x5 grid


class TestF061Step5CalculateNetImprovementPercentage:
    """Step 5: Calculate net_improvement_pct."""

    def test_calculate_net_improvement_pct(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify net_improvement_pct calculation."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Verify net_improvement_pct is present
        assert "net_improvement_pct" in summary

        # Calculate expected value
        improved = summary["improved_bins"]
        worsened = summary["worsened_bins"]
        total = summary["total_bins"]
        expected_pct = ((improved - worsened) / total * 100) if total > 0 else 0.0

        assert abs(summary["net_improvement_pct"] - expected_pct) < 0.01

    def test_net_improvement_pct_positive_when_mostly_improved(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify net_improvement_pct is positive when most bins improved."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # For this test case, should be net improvement
        assert summary["net_improvement_pct"] > 0

    def test_net_improvement_pct_negative_when_mostly_worsened(
        self, tmp_path: Path, baseline_heatmap: np.ndarray
    ) -> None:
        """Verify net_improvement_pct is negative when most bins worsened."""
        baseline_csv = tmp_path / "baseline.csv"
        degraded_csv = tmp_path / "degraded.csv"

        # Create degraded version
        degraded_heatmap = baseline_heatmap * 2.0

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(degraded_csv, degraded_heatmap)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, degraded_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Should be net degradation (negative percentage)
        assert summary["net_improvement_pct"] < 0

    def test_net_improvement_pct_zero_when_balanced(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, mixed_impact_heatmap: np.ndarray
    ) -> None:
        """Verify net_improvement_pct near zero when impacts are balanced."""
        # Create balanced impact (equal improved and worsened bins)
        baseline = np.array([[10, 20], [30, 40]], dtype=np.float64)
        comparison = np.array([[5, 25], [25, 45]], dtype=np.float64)
        # Diff: [5, -5], [-5, 5] -> 2 improved, 2 worsened

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"

        create_test_heatmap_csv(baseline_csv, baseline)
        create_test_heatmap_csv(comparison_csv, comparison)

        # Compute diff and summary
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        summary = compute_improvement_summary(diff, diff_metadata)

        # Should be zero (2 improved - 2 worsened = 0)
        assert abs(summary["net_improvement_pct"]) < 0.01


class TestF061Step6SaveSummaryAsJSON:
    """Step 6: Save summary as JSON with improved_bins, worsened_bins, net_improvement_pct."""

    def test_save_summary_as_json(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify summary can be saved as JSON file."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "improvement_summary.json"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Generate summary JSON
        summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # Verify JSON file was created
        assert summary_json.exists()

        # Verify JSON can be loaded
        with open(summary_json) as f:
            loaded_summary = json.load(f)

        # Verify required fields are present
        assert "improved_bins" in loaded_summary
        assert "worsened_bins" in loaded_summary
        assert "net_improvement_pct" in loaded_summary
        assert "unchanged_bins" in loaded_summary
        assert "total_bins" in loaded_summary

    def test_json_summary_matches_computed_summary(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify JSON summary matches directly computed summary."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "improvement_summary.json"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Compute summary directly
        diff, diff_metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
        computed_summary = compute_improvement_summary(diff, diff_metadata)

        # Generate JSON
        json_summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # Compare key fields
        assert json_summary["improved_bins"] == computed_summary["improved_bins"]
        assert json_summary["worsened_bins"] == computed_summary["worsened_bins"]
        assert json_summary["unchanged_bins"] == computed_summary["unchanged_bins"]
        assert (
            abs(json_summary["net_improvement_pct"] - computed_summary["net_improvement_pct"])
            < 0.01
        )

    def test_json_is_well_formatted(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify JSON output is well-formatted and human-readable."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "improvement_summary.json"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Generate JSON
        generate_improvement_summary_json(baseline_csv, comparison_csv, summary_json)

        # Read JSON as text
        json_text = summary_json.read_text()

        # Verify it's indented (human-readable)
        assert "\n" in json_text
        assert "  " in json_text  # Indentation present

        # Verify it's valid JSON
        loaded = json.loads(json_text)
        assert isinstance(loaded, dict)


# --- Integration Tests ---


class TestF061Integration:
    """Integration tests for complete differential summary workflow."""

    def test_complete_differential_summary_workflow(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Test complete workflow from heatmap to summary JSON."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "output" / "improvement_summary.json"

        # Step 1: Create heatmaps
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Step 2-6: Compute differential and generate summary
        summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # Verify all required fields
        assert "improved_bins" in summary
        assert "worsened_bins" in summary
        assert "unchanged_bins" in summary
        assert "total_bins" in summary
        assert "net_improvement_pct" in summary

        # Verify output file exists
        assert summary_json.exists()

        # Verify JSON is valid
        with open(summary_json) as f:
            loaded = json.load(f)
        assert loaded["total_bins"] == 25

    def test_differential_summary_with_mixed_impact(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, mixed_impact_heatmap: np.ndarray
    ) -> None:
        """Test differential summary with mixed improvement/degradation."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "summary.json"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, mixed_impact_heatmap)

        # Generate summary
        summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # Should have both improved and worsened bins
        assert summary["improved_bins"] > 0
        assert summary["worsened_bins"] > 0

        # Verify accounting
        total = (
            summary["improved_bins"] + summary["worsened_bins"] + summary["unchanged_bins"]
        )
        assert total == summary["total_bins"]


# --- Edge Cases ---


class TestF061EdgeCases:
    """Test edge cases and error handling."""

    def test_summary_with_no_change(self, tmp_path: Path) -> None:
        """Test summary when before and after are identical."""
        identical = np.ones((4, 4)) * 25.0

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "summary.json"

        create_test_heatmap_csv(baseline_csv, identical)
        create_test_heatmap_csv(comparison_csv, identical)

        # Generate summary
        summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # All bins should be unchanged
        assert summary["improved_bins"] == 0
        assert summary["worsened_bins"] == 0
        assert summary["unchanged_bins"] == 16
        assert summary["net_improvement_pct"] == 0.0

    def test_summary_with_complete_improvement(self, tmp_path: Path) -> None:
        """Test summary when all bins improved."""
        baseline = np.ones((3, 3)) * 100.0
        improved = np.zeros((3, 3))

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "summary.json"

        create_test_heatmap_csv(baseline_csv, baseline)
        create_test_heatmap_csv(comparison_csv, improved)

        # Generate summary
        summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # All bins should be improved
        assert summary["improved_bins"] == 9
        assert summary["worsened_bins"] == 0
        assert summary["net_improvement_pct"] == 100.0

    def test_summary_with_complete_degradation(self, tmp_path: Path) -> None:
        """Test summary when all bins worsened."""
        baseline = np.zeros((3, 3))
        degraded = np.ones((3, 3)) * 100.0

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "summary.json"

        create_test_heatmap_csv(baseline_csv, baseline)
        create_test_heatmap_csv(comparison_csv, degraded)

        # Generate summary
        summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # All bins should be worsened
        assert summary["improved_bins"] == 0
        assert summary["worsened_bins"] == 9
        assert summary["net_improvement_pct"] == -100.0

    def test_summary_includes_additional_statistics(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Verify summary includes additional useful statistics."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        summary_json = tmp_path / "summary.json"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        # Generate summary
        summary = generate_improvement_summary_json(
            baseline_csv, comparison_csv, summary_json
        )

        # Verify additional fields
        assert "max_improvement_value" in summary
        assert "max_improvement_location" in summary
        assert "max_degradation_value" in summary
        assert "max_degradation_location" in summary
        assert "mean_diff" in summary
        assert "total_improvement" in summary
        assert "total_degradation" in summary
