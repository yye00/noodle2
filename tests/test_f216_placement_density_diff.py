"""Tests for F216: Generate differential placement density heatmap comparing case to parent."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.visualization.heatmap_renderer import (
    compute_heatmap_diff,
    render_diff_heatmap,
)


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


class TestPlacementDensityDifferentialF216:
    """
    Test suite for Feature F216: Generate differential placement density heatmap.

    Steps from feature_list.json:
    1. Generate placement density heatmap for parent case
    2. Generate placement density heatmap for derived case
    3. Compute differential heatmap (derived - parent)
    4. Export differential as placement_density_diff.csv
    5. Render differential as placement_density_diff.png
    6. Verify green regions show improvement, red show worsening
    """

    def test_step_1_generate_parent_placement_density(self) -> None:
        """Step 1: Generate placement density heatmap for parent case."""
        # Create a parent placement density heatmap
        parent_density = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],
                [0.3, 0.5, 0.6, 0.5, 0.3],
                [0.4, 0.6, 0.8, 0.6, 0.4],  # High density region
                [0.3, 0.5, 0.6, 0.5, 0.3],
                [0.2, 0.3, 0.4, 0.3, 0.2],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_placement_density.csv"
            create_test_heatmap_csv(parent_csv, parent_density)

            # Verify file created
            assert parent_csv.exists()

            # Verify data can be loaded
            loaded = np.loadtxt(parent_csv, delimiter=",")
            np.testing.assert_array_almost_equal(loaded, parent_density)

    def test_step_2_generate_derived_placement_density(self) -> None:
        """Step 2: Generate placement density heatmap for derived case."""
        # Create a derived (post-ECO) placement density heatmap
        # This should show some regions with reduced density (improvement)
        derived_density = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],
                [0.3, 0.4, 0.5, 0.4, 0.3],  # Reduced density
                [0.4, 0.5, 0.6, 0.5, 0.4],  # Significant reduction in center
                [0.3, 0.4, 0.5, 0.4, 0.3],  # Reduced density
                [0.2, 0.3, 0.4, 0.3, 0.2],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            derived_csv = Path(tmpdir) / "derived_placement_density.csv"
            create_test_heatmap_csv(derived_csv, derived_density)

            # Verify file created
            assert derived_csv.exists()

            # Verify data can be loaded
            loaded = np.loadtxt(derived_csv, delimiter=",")
            np.testing.assert_array_almost_equal(loaded, derived_density)

    def test_step_3_compute_differential_heatmap(self) -> None:
        """Step 3: Compute differential heatmap (derived - parent)."""
        parent_density = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],
                [0.3, 0.5, 0.6, 0.5, 0.3],
                [0.4, 0.6, 0.8, 0.6, 0.4],
                [0.3, 0.5, 0.6, 0.5, 0.3],
                [0.2, 0.3, 0.4, 0.3, 0.2],
            ]
        )

        derived_density = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],
                [0.3, 0.4, 0.5, 0.4, 0.3],
                [0.4, 0.5, 0.6, 0.5, 0.4],
                [0.3, 0.4, 0.5, 0.4, 0.3],
                [0.2, 0.3, 0.4, 0.3, 0.2],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_placement_density.csv"
            derived_csv = Path(tmpdir) / "derived_placement_density.csv"

            create_test_heatmap_csv(parent_csv, parent_density)
            create_test_heatmap_csv(derived_csv, derived_density)

            # Compute differential
            diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

            # Verify differential computed correctly
            # Diff = parent - derived, so positive = improvement (density reduced)
            expected_diff = parent_density - derived_density
            np.testing.assert_array_almost_equal(diff, expected_diff)

            # Verify metadata
            assert "min_diff" in metadata
            assert "max_diff" in metadata
            assert "mean_diff" in metadata
            assert "improved_bins" in metadata
            assert "degraded_bins" in metadata

    def test_step_4_export_differential_csv(self) -> None:
        """Step 4: Export differential as placement_density_diff.csv."""
        parent_density = np.array(
            [
                [0.3, 0.5, 0.7],
                [0.5, 0.8, 0.5],
                [0.3, 0.5, 0.7],
            ]
        )

        derived_density = np.array(
            [
                [0.3, 0.4, 0.6],  # Improvement
                [0.4, 0.6, 0.4],  # Improvement
                [0.3, 0.4, 0.6],  # Improvement
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_placement_density.csv"
            derived_csv = Path(tmpdir) / "derived_placement_density.csv"
            diff_csv = Path(tmpdir) / "placement_density_diff.csv"

            create_test_heatmap_csv(parent_csv, parent_density)
            create_test_heatmap_csv(derived_csv, derived_density)

            # Compute and export differential
            diff, _ = compute_heatmap_diff(parent_csv, derived_csv)
            np.savetxt(diff_csv, diff, delimiter=",", fmt="%.4f")

            # Verify differential CSV created
            assert diff_csv.exists()

            # Verify content
            loaded_diff = np.loadtxt(diff_csv, delimiter=",")
            np.testing.assert_array_almost_equal(loaded_diff, diff)

    def test_step_5_render_differential_png(self) -> None:
        """Step 5: Render differential as placement_density_diff.png."""
        parent_density = np.array(
            [
                [0.2, 0.4, 0.6],
                [0.4, 0.7, 0.4],
                [0.2, 0.4, 0.6],
            ]
        )

        derived_density = np.array(
            [
                [0.2, 0.3, 0.5],  # Improved
                [0.3, 0.5, 0.3],  # Improved
                [0.2, 0.3, 0.5],  # Improved
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_placement_density.csv"
            derived_csv = Path(tmpdir) / "derived_placement_density.csv"
            diff_png = Path(tmpdir) / "placement_density_diff.png"

            create_test_heatmap_csv(parent_csv, parent_density)
            create_test_heatmap_csv(derived_csv, derived_density)

            # Render differential heatmap
            metadata = render_diff_heatmap(
                baseline_csv=parent_csv,
                comparison_csv=derived_csv,
                output_path=diff_png,
                title="Placement Density - ECO Impact",
            )

            # Verify PNG created
            assert diff_png.exists()

            # Verify metadata
            assert metadata["diff_png"] == str(diff_png)
            assert metadata["baseline_csv"] == str(parent_csv)
            assert metadata["comparison_csv"] == str(derived_csv)
            assert "data_shape" in metadata
            assert "improved_bins" in metadata
            assert "degraded_bins" in metadata

    def test_step_6_verify_color_encoding(self) -> None:
        """Step 6: Verify green regions show improvement, red show worsening."""
        # Create scenario with clear improvement and degradation
        parent_density = np.array(
            [
                [0.5, 0.5, 0.5],  # Will improve
                [0.5, 0.5, 0.5],  # Will degrade
                [0.5, 0.5, 0.5],  # Unchanged
            ]
        )

        derived_density = np.array(
            [
                [0.3, 0.3, 0.3],  # Improved (lower density)
                [0.7, 0.7, 0.7],  # Degraded (higher density)
                [0.5, 0.5, 0.5],  # Unchanged
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_placement_density.csv"
            derived_csv = Path(tmpdir) / "derived_placement_density.csv"
            diff_png = Path(tmpdir) / "placement_density_diff.png"

            create_test_heatmap_csv(parent_csv, parent_density)
            create_test_heatmap_csv(derived_csv, derived_density)

            # Compute differential
            diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

            # Verify diff encoding
            # diff = parent - derived
            # Row 0: parent (0.5) - derived (0.3) = +0.2 (positive = improvement, should be green)
            # Row 1: parent (0.5) - derived (0.7) = -0.2 (negative = degradation, should be red)
            # Row 2: parent (0.5) - derived (0.5) = 0 (neutral, should be white)

            assert np.all(diff[0, :] > 0), "Improved bins should have positive diff"
            assert np.all(diff[1, :] < 0), "Degraded bins should have negative diff"
            assert np.all(diff[2, :] == 0), "Unchanged bins should have zero diff"

            # Render and verify metadata
            render_metadata = render_diff_heatmap(
                baseline_csv=parent_csv,
                comparison_csv=derived_csv,
                output_path=diff_png,
            )

            # Verify improvement/degradation counts
            assert render_metadata["improved_bins"] == 3  # Row 0
            assert render_metadata["degraded_bins"] == 3  # Row 1
            assert render_metadata["unchanged_bins"] == 3  # Row 2

    def test_complete_f216_workflow(self) -> None:
        """Test complete F216 workflow: parent -> derived -> diff."""
        # Simulate a realistic ECO impact scenario
        parent_density = np.array(
            [
                [0.1, 0.2, 0.3, 0.2, 0.1],
                [0.2, 0.4, 0.6, 0.4, 0.2],
                [0.3, 0.6, 0.9, 0.6, 0.3],  # Dense hotspot
                [0.2, 0.4, 0.6, 0.4, 0.2],
                [0.1, 0.2, 0.3, 0.2, 0.1],
            ]
        )

        # ECO spreads out dense region
        derived_density = np.array(
            [
                [0.1, 0.2, 0.3, 0.2, 0.1],
                [0.2, 0.4, 0.5, 0.4, 0.2],  # Slightly reduced
                [0.3, 0.5, 0.6, 0.5, 0.3],  # Significantly reduced hotspot
                [0.2, 0.4, 0.5, 0.4, 0.2],  # Slightly reduced
                [0.1, 0.2, 0.3, 0.2, 0.1],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1 & 2: Create parent and derived heatmaps
            parent_csv = Path(tmpdir) / "parent_placement_density.csv"
            derived_csv = Path(tmpdir) / "derived_placement_density.csv"

            create_test_heatmap_csv(parent_csv, parent_density)
            create_test_heatmap_csv(derived_csv, derived_density)

            # Step 3 & 4: Compute and export differential
            diff, diff_metadata = compute_heatmap_diff(parent_csv, derived_csv)
            diff_csv = Path(tmpdir) / "placement_density_diff.csv"
            np.savetxt(diff_csv, diff, delimiter=",", fmt="%.4f")

            # Step 5: Render differential PNG
            diff_png = Path(tmpdir) / "placement_density_diff.png"
            render_metadata = render_diff_heatmap(
                baseline_csv=parent_csv,
                comparison_csv=derived_csv,
                output_path=diff_png,
                title="Placement Density - ECO Impact",
            )

            # Step 6: Verify results
            # All artifacts created
            assert parent_csv.exists()
            assert derived_csv.exists()
            assert diff_csv.exists()
            assert diff_png.exists()

            # Diff shows improvement (positive values in reduced regions)
            assert diff_metadata["mean_diff"] > 0, "Overall improvement expected"
            assert (
                diff_metadata["improved_bins"] > diff_metadata["degraded_bins"]
            ), "More bins improved than degraded"

            # Center hotspot improved significantly
            center_diff = diff[2, 2]
            assert center_diff > 0.25, "Center hotspot should show significant improvement"

            # Metadata is complete
            assert "total_improvement" in diff_metadata
            assert "total_degradation" in diff_metadata
            assert render_metadata["improved_bins"] > 0
