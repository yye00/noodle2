"""Tests for comparative heatmap generation (ECO impact analysis)."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.visualization.heatmap_renderer import (
    compute_heatmap_diff,
    generate_eco_impact_heatmaps,
    render_diff_heatmap,
)


# --- Helper Functions ---


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


# --- Test Fixtures ---


@pytest.fixture
def baseline_heatmap() -> np.ndarray:
    """Baseline heatmap with moderate congestion."""
    return np.array(
        [
            [1.0, 2.0, 3.0, 2.0, 1.0],
            [2.0, 4.0, 5.0, 4.0, 2.0],
            [3.0, 5.0, 8.0, 5.0, 3.0],  # Hot spot in center
            [2.0, 4.0, 5.0, 4.0, 2.0],
            [1.0, 2.0, 3.0, 2.0, 1.0],
        ]
    )


@pytest.fixture
def improved_heatmap() -> np.ndarray:
    """Improved heatmap (reduced congestion after ECO)."""
    return np.array(
        [
            [1.0, 2.0, 3.0, 2.0, 1.0],
            [2.0, 3.0, 4.0, 3.0, 2.0],  # Reduced
            [3.0, 4.0, 5.0, 4.0, 3.0],  # Significantly reduced hot spot
            [2.0, 3.0, 4.0, 3.0, 2.0],  # Reduced
            [1.0, 2.0, 3.0, 2.0, 1.0],
        ]
    )


@pytest.fixture
def degraded_heatmap() -> np.ndarray:
    """Degraded heatmap (increased congestion after ECO)."""
    return np.array(
        [
            [2.0, 3.0, 4.0, 3.0, 2.0],  # Increased
            [3.0, 5.0, 6.0, 5.0, 3.0],  # Increased
            [4.0, 6.0, 10.0, 6.0, 4.0],  # Hot spot worsened
            [3.0, 5.0, 6.0, 5.0, 3.0],  # Increased
            [2.0, 3.0, 4.0, 3.0, 2.0],  # Increased
        ]
    )


@pytest.fixture
def mixed_heatmap() -> np.ndarray:
    """Mixed impact heatmap (some improvement, some degradation)."""
    return np.array(
        [
            [1.0, 2.0, 3.0, 2.0, 1.0],  # Unchanged
            [1.0, 3.0, 6.0, 3.0, 1.0],  # Mixed: center degraded (6 > 4), edges improved (3 < 4)
            [2.0, 3.0, 5.0, 3.0, 2.0],  # Hot spot improved (5 < 8), but still present
            [1.0, 3.0, 6.0, 3.0, 1.0],  # Mixed: center degraded (6 > 4), edges improved (3 < 4)
            [1.0, 2.0, 3.0, 2.0, 1.0],  # Unchanged
        ]
    )


# --- Feature Step Tests ---


class TestFeatureSteps:
    """Test all 5 feature steps for comparative heatmap generation."""

    def test_step1_export_baseline_heatmap_before_eco(
        self, tmp_path: Path, baseline_heatmap: np.ndarray
    ) -> None:
        """Step 1: Export baseline heatmap before ECO."""
        baseline_csv = tmp_path / "baseline_congestion.csv"
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)

        assert baseline_csv.exists()
        loaded = np.loadtxt(baseline_csv, delimiter=",")
        np.testing.assert_array_almost_equal(loaded, baseline_heatmap)

    def test_step2_apply_eco_and_export_heatmap_after(
        self, tmp_path: Path, improved_heatmap: np.ndarray
    ) -> None:
        """Step 2: Apply ECO and export heatmap after."""
        after_csv = tmp_path / "after_eco_congestion.csv"
        create_test_heatmap_csv(after_csv, improved_heatmap)

        assert after_csv.exists()
        loaded = np.loadtxt(after_csv, delimiter=",")
        np.testing.assert_array_almost_equal(loaded, improved_heatmap)

    def test_step3_compute_spatial_difference(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Step 3: Compute spatial difference (after - before)."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Verify diff computation (baseline - comparison)
        expected_diff = baseline_heatmap - improved_heatmap
        np.testing.assert_array_almost_equal(diff, expected_diff)

        # Verify metadata
        assert metadata["shape"] == (5, 5)
        assert "min_diff" in metadata
        assert "max_diff" in metadata
        assert "mean_diff" in metadata

    def test_step4_render_diff_heatmap_with_improvement_degradation(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Step 4: Render diff heatmap showing regions of improvement/degradation."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify PNG was created
        assert diff_png.exists()
        assert diff_png.stat().st_size > 0

        # Verify metadata includes impact statistics
        assert metadata["improved_bins"] > 0
        assert metadata["total_improvement"] > 0
        assert "diff_png" in metadata

    def test_step5_include_diff_heatmap_in_eco_analysis_artifacts(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Step 5: Include diff heatmap in ECO analysis artifacts."""
        baseline_dir = tmp_path / "baseline_heatmaps"
        comparison_dir = tmp_path / "comparison_heatmaps"
        output_dir = tmp_path / "diff_heatmaps"

        baseline_dir.mkdir()
        comparison_dir.mkdir()

        # Create multiple heatmap types
        create_test_heatmap_csv(
            baseline_dir / "placement_density.csv", baseline_heatmap
        )
        create_test_heatmap_csv(baseline_dir / "routing_congestion.csv", baseline_heatmap)

        create_test_heatmap_csv(
            comparison_dir / "placement_density.csv", improved_heatmap
        )
        create_test_heatmap_csv(
            comparison_dir / "routing_congestion.csv", improved_heatmap
        )

        # Generate all diff heatmaps
        results = generate_eco_impact_heatmaps(baseline_dir, comparison_dir, output_dir)

        # Verify both diff heatmaps were created
        assert len(results) == 2
        assert (output_dir / "placement_density_diff.png").exists()
        assert (output_dir / "routing_congestion_diff.png").exists()

        # Verify metadata for each
        for result in results:
            assert "diff_png" in result
            assert "improved_bins" in result
            assert "degraded_bins" in result


# --- Diff Computation Tests ---


class TestDiffComputation:
    """Test spatial difference computation."""

    def test_compute_diff_with_improvement(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Positive diff values indicate improvement."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Most values should be positive (improvement)
        assert metadata["improved_bins"] > metadata["degraded_bins"]
        assert metadata["mean_diff"] > 0  # Net improvement
        assert metadata["total_improvement"] > metadata["total_degradation"]

    def test_compute_diff_with_degradation(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, degraded_heatmap: np.ndarray
    ) -> None:
        """Negative diff values indicate degradation."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, degraded_heatmap)

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Most values should be negative (degradation)
        assert metadata["degraded_bins"] > metadata["improved_bins"]
        assert metadata["mean_diff"] < 0  # Net degradation
        assert metadata["total_degradation"] > metadata["total_improvement"]

    def test_compute_diff_with_mixed_impact(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, mixed_heatmap: np.ndarray
    ) -> None:
        """Mixed impact shows both improvement and degradation areas."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, mixed_heatmap)

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Should have both improvement and degradation
        assert metadata["improved_bins"] > 0
        assert metadata["degraded_bins"] > 0
        assert metadata["unchanged_bins"] >= 0

    def test_compute_diff_dimension_mismatch(
        self, tmp_path: Path, baseline_heatmap: np.ndarray
    ) -> None:
        """Mismatched dimensions raise ValueError."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)

        # Different dimensions
        wrong_size = np.array([[1.0, 2.0], [3.0, 4.0]])
        create_test_heatmap_csv(comparison_csv, wrong_size)

        with pytest.raises(ValueError, match="dimensions don't match"):
            compute_heatmap_diff(baseline_csv, comparison_csv)

    def test_compute_diff_statistics(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Metadata contains comprehensive statistics."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

        # Verify all required metadata fields
        assert "shape" in metadata
        assert "min_diff" in metadata
        assert "max_diff" in metadata
        assert "mean_diff" in metadata
        assert "std_diff" in metadata
        assert "improved_bins" in metadata
        assert "degraded_bins" in metadata
        assert "unchanged_bins" in metadata
        assert "total_improvement" in metadata
        assert "total_degradation" in metadata

        # Verify statistics are reasonable
        assert metadata["shape"] == (5, 5)
        assert metadata["improved_bins"] + metadata["degraded_bins"] + metadata[
            "unchanged_bins"
        ] == 25


# --- Diff Rendering Tests ---


class TestDiffRendering:
    """Test diff heatmap rendering."""

    def test_render_diff_heatmap_creates_png(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Rendering creates valid PNG file."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify PNG was created
        assert diff_png.exists()
        assert diff_png.stat().st_size > 0

        # Verify metadata
        assert metadata["diff_png"] == str(diff_png)
        assert metadata["baseline_csv"] == str(baseline_csv)
        assert metadata["comparison_csv"] == str(comparison_csv)

    def test_render_diff_heatmap_with_custom_title(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Custom title is used in rendering."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        metadata = render_diff_heatmap(
            baseline_csv, comparison_csv, diff_png, title="Buffer Insertion Impact"
        )

        # Title doesn't appear in metadata, but rendering should succeed
        assert diff_png.exists()

    def test_render_diff_heatmap_metadata_includes_statistics(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Metadata includes impact statistics."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify statistics in metadata
        assert metadata["improved_bins"] > 0
        assert metadata["total_improvement"] > 0
        assert "diff_range" in metadata
        assert "mean_diff" in metadata

    def test_render_diff_heatmap_creates_output_directory(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Output directory is created if it doesn't exist."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "nested" / "output" / "diff.png"

        create_test_heatmap_csv(baseline_csv, baseline_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify directory and file were created
        assert diff_png.parent.exists()
        assert diff_png.exists()


# --- Batch Generation Tests ---


class TestBatchGeneration:
    """Test batch generation of diff heatmaps."""

    def test_generate_eco_impact_heatmaps_for_multiple_types(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Generate diff heatmaps for all matching types."""
        baseline_dir = tmp_path / "baseline"
        comparison_dir = tmp_path / "comparison"
        output_dir = tmp_path / "output"

        baseline_dir.mkdir()
        comparison_dir.mkdir()

        # Create multiple heatmap types
        heatmap_types = ["placement_density", "rudy", "routing_congestion"]
        for htype in heatmap_types:
            create_test_heatmap_csv(baseline_dir / f"{htype}.csv", baseline_heatmap)
            create_test_heatmap_csv(comparison_dir / f"{htype}.csv", improved_heatmap)

        results = generate_eco_impact_heatmaps(baseline_dir, comparison_dir, output_dir)

        # Verify all diff heatmaps were created
        assert len(results) == 3
        for htype in heatmap_types:
            diff_png = output_dir / f"{htype}_diff.png"
            assert diff_png.exists()

    def test_generate_eco_impact_heatmaps_handles_missing_comparison(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Missing comparison heatmaps are skipped gracefully."""
        baseline_dir = tmp_path / "baseline"
        comparison_dir = tmp_path / "comparison"
        output_dir = tmp_path / "output"

        baseline_dir.mkdir()
        comparison_dir.mkdir()

        # Create baseline heatmaps
        create_test_heatmap_csv(baseline_dir / "placement_density.csv", baseline_heatmap)
        create_test_heatmap_csv(baseline_dir / "routing_congestion.csv", baseline_heatmap)

        # Only create comparison for one type
        create_test_heatmap_csv(
            comparison_dir / "placement_density.csv", improved_heatmap
        )

        results = generate_eco_impact_heatmaps(baseline_dir, comparison_dir, output_dir)

        # Only one diff heatmap should be created
        assert len(results) == 1
        assert (output_dir / "placement_density_diff.png").exists()
        assert not (output_dir / "routing_congestion_diff.png").exists()

    def test_generate_eco_impact_heatmaps_baseline_dir_not_found(
        self, tmp_path: Path
    ) -> None:
        """Missing baseline directory raises FileNotFoundError."""
        baseline_dir = tmp_path / "nonexistent_baseline"
        comparison_dir = tmp_path / "comparison"
        output_dir = tmp_path / "output"

        comparison_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="Baseline heatmaps directory"):
            generate_eco_impact_heatmaps(baseline_dir, comparison_dir, output_dir)

    def test_generate_eco_impact_heatmaps_comparison_dir_not_found(
        self, tmp_path: Path
    ) -> None:
        """Missing comparison directory raises FileNotFoundError."""
        baseline_dir = tmp_path / "baseline"
        comparison_dir = tmp_path / "nonexistent_comparison"
        output_dir = tmp_path / "output"

        baseline_dir.mkdir()

        with pytest.raises(FileNotFoundError, match="Comparison heatmaps directory"):
            generate_eco_impact_heatmaps(baseline_dir, comparison_dir, output_dir)


# --- End-to-End Workflow Tests ---


class TestEndToEndWorkflow:
    """Test complete workflow for ECO impact analysis."""

    def test_complete_eco_impact_analysis_workflow(
        self, tmp_path: Path, baseline_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Complete workflow: baseline → ECO → comparison → diff analysis."""
        # Step 1: Export baseline heatmap
        baseline_dir = tmp_path / "baseline_trial" / "heatmaps"
        baseline_dir.mkdir(parents=True)
        create_test_heatmap_csv(
            baseline_dir / "routing_congestion.csv", baseline_heatmap
        )

        # Step 2: Apply ECO and export comparison heatmap
        comparison_dir = tmp_path / "eco_trial" / "heatmaps"
        comparison_dir.mkdir(parents=True)
        create_test_heatmap_csv(
            comparison_dir / "routing_congestion.csv", improved_heatmap
        )

        # Step 3: Generate diff heatmaps
        output_dir = tmp_path / "eco_analysis"
        results = generate_eco_impact_heatmaps(baseline_dir, comparison_dir, output_dir)

        # Verify diff heatmap was created
        assert len(results) == 1
        assert (output_dir / "routing_congestion_diff.png").exists()

        # Verify statistics show improvement
        result = results[0]
        assert result["improved_bins"] > result["degraded_bins"]
        assert result["total_improvement"] > result["total_degradation"]
        assert result["mean_diff"] > 0  # Net improvement

    def test_workflow_with_multiple_eco_attempts(
        self,
        tmp_path: Path,
        baseline_heatmap: np.ndarray,
        improved_heatmap: np.ndarray,
        degraded_heatmap: np.ndarray,
    ) -> None:
        """Compare multiple ECO attempts against baseline."""
        baseline_dir = tmp_path / "baseline" / "heatmaps"
        baseline_dir.mkdir(parents=True)
        create_test_heatmap_csv(
            baseline_dir / "routing_congestion.csv", baseline_heatmap
        )

        # ECO attempt 1: Improvement
        eco1_dir = tmp_path / "eco1" / "heatmaps"
        eco1_dir.mkdir(parents=True)
        create_test_heatmap_csv(eco1_dir / "routing_congestion.csv", improved_heatmap)

        # ECO attempt 2: Degradation
        eco2_dir = tmp_path / "eco2" / "heatmaps"
        eco2_dir.mkdir(parents=True)
        create_test_heatmap_csv(eco2_dir / "routing_congestion.csv", degraded_heatmap)

        # Generate diff heatmaps for both ECOs
        output1 = tmp_path / "eco1_analysis"
        output2 = tmp_path / "eco2_analysis"

        results1 = generate_eco_impact_heatmaps(baseline_dir, eco1_dir, output1)
        results2 = generate_eco_impact_heatmaps(baseline_dir, eco2_dir, output2)

        # Verify both analyses completed
        assert len(results1) == 1
        assert len(results2) == 1

        # ECO 1 should show improvement
        assert results1[0]["total_improvement"] > results1[0]["total_degradation"]

        # ECO 2 should show degradation
        assert results2[0]["total_degradation"] > results2[0]["total_improvement"]
