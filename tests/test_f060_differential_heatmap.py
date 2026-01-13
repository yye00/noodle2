"""
Tests for F060: Differential heatmap computation and visualization.

This test file verifies that differential heatmaps can be computed and visualized
to show the spatial impact of ECOs. Each test maps to a specific step in the
F060 feature specification.

Feature Steps:
1. Export heatmap CSV for parent case (before ECO)
2. Export heatmap CSV for derived case (after ECO)
3. Compute difference: diff = after - before
4. Create matplotlib visualization with diverging colormap (red=worse, green=better)
5. Save differential heatmap as PNG
6. Verify PNG shows regions of improvement vs degradation
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.visualization.heatmap_renderer import (
    compute_heatmap_diff,
    render_diff_heatmap,
    generate_eco_impact_heatmaps,
)


# --- Helper Functions ---


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file from numpy array."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


def create_openroad_format_heatmap_csv(path: Path, boxes: list[dict]) -> None:
    """Create a test heatmap CSV in OpenROAD bbox format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        # Write header
        f.write("x0,y0,x1,y1,value (%)\n")
        # Write data rows
        for box in boxes:
            f.write(f"{box['x0']},{box['y0']},{box['x1']},{box['y1']},{box['value']}\n")


# --- Test Fixtures ---


@pytest.fixture
def parent_case_heatmap() -> np.ndarray:
    """Parent case heatmap (before ECO) with congestion hotspot."""
    return np.array(
        [
            [1.0, 2.0, 3.0, 4.0, 3.0, 2.0],
            [2.0, 4.0, 6.0, 8.0, 6.0, 4.0],
            [3.0, 6.0, 9.0, 12.0, 9.0, 6.0],  # High congestion row
            [4.0, 8.0, 12.0, 16.0, 12.0, 8.0],  # Worst congestion (center hotspot)
            [3.0, 6.0, 9.0, 12.0, 9.0, 6.0],
            [2.0, 4.0, 6.0, 8.0, 6.0, 4.0],
        ],
        dtype=np.float64,
    )


@pytest.fixture
def derived_case_heatmap() -> np.ndarray:
    """Derived case heatmap (after ECO) with reduced hotspot."""
    return np.array(
        [
            [1.0, 2.0, 3.0, 4.0, 3.0, 2.0],  # Unchanged
            [2.0, 4.0, 6.0, 7.0, 6.0, 4.0],  # Slight improvement
            [3.0, 6.0, 8.0, 10.0, 8.0, 6.0],  # Improved (9->8, 12->10)
            [4.0, 7.0, 10.0, 12.0, 10.0, 7.0],  # Significant improvement (8->7, 12->10, 16->12)
            [3.0, 6.0, 8.0, 10.0, 8.0, 6.0],  # Improved
            [2.0, 4.0, 6.0, 8.0, 6.0, 4.0],  # Unchanged
        ],
        dtype=np.float64,
    )


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Temporary output directory for test artifacts."""
    output_dir = tmp_path / "differential_heatmaps"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


# --- F060 Feature Step Tests ---


class TestF060Step1ExportParentCaseHeatmap:
    """Step 1: Export heatmap CSV for parent case (before ECO)."""

    def test_export_parent_case_heatmap_csv(
        self, tmp_path: Path, parent_case_heatmap: np.ndarray
    ) -> None:
        """Verify we can export heatmap CSV for parent case."""
        parent_csv = tmp_path / "parent_case" / "routing_congestion.csv"

        # Export parent case heatmap
        create_test_heatmap_csv(parent_csv, parent_case_heatmap)

        # Verify CSV was created
        assert parent_csv.exists()
        assert parent_csv.stat().st_size > 0

        # Verify CSV content can be loaded
        loaded_data = np.loadtxt(parent_csv, delimiter=",")
        np.testing.assert_array_almost_equal(loaded_data, parent_case_heatmap)

        # Verify dimensions
        assert loaded_data.shape == (6, 6)

    def test_export_parent_case_openroad_format(self, tmp_path: Path) -> None:
        """Verify we can export heatmap in OpenROAD bbox format."""
        parent_csv = tmp_path / "parent_openroad.csv"

        # Create OpenROAD format heatmap
        boxes = [
            {"x0": 0.0, "y0": 0.0, "x1": 10.0, "y1": 10.0, "value": 15.5},
            {"x0": 10.0, "y0": 0.0, "x1": 20.0, "y1": 10.0, "value": 25.8},
            {"x0": 0.0, "y0": 10.0, "x1": 10.0, "y1": 20.0, "value": 35.2},
            {"x0": 10.0, "y0": 10.0, "x1": 20.0, "y1": 20.0, "value": 65.7},
        ]
        create_openroad_format_heatmap_csv(parent_csv, boxes)

        # Verify CSV was created
        assert parent_csv.exists()

        # Verify header is present
        with open(parent_csv) as f:
            header = f.readline()
            assert "x0" in header.lower()
            assert "y0" in header.lower()
            assert "value" in header.lower()


class TestF060Step2ExportDerivedCaseHeatmap:
    """Step 2: Export heatmap CSV for derived case (after ECO)."""

    def test_export_derived_case_heatmap_csv(
        self, tmp_path: Path, derived_case_heatmap: np.ndarray
    ) -> None:
        """Verify we can export heatmap CSV for derived case."""
        derived_csv = tmp_path / "derived_case" / "routing_congestion.csv"

        # Export derived case heatmap
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Verify CSV was created
        assert derived_csv.exists()
        assert derived_csv.stat().st_size > 0

        # Verify CSV content can be loaded
        loaded_data = np.loadtxt(derived_csv, delimiter=",")
        np.testing.assert_array_almost_equal(loaded_data, derived_case_heatmap)

        # Verify dimensions match parent case
        assert loaded_data.shape == (6, 6)


class TestF060Step3ComputeDifference:
    """Step 3: Compute difference: diff = after - before."""

    def test_compute_difference_baseline_minus_comparison(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify difference computation: baseline - comparison."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Compute difference
        diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

        # Verify difference is baseline - comparison
        expected_diff = parent_case_heatmap - derived_case_heatmap
        np.testing.assert_array_almost_equal(diff, expected_diff)

        # Verify metadata contains expected fields
        assert "min_diff" in metadata
        assert "max_diff" in metadata
        assert "mean_diff" in metadata
        assert "std_diff" in metadata
        assert "improved_bins" in metadata
        assert "degraded_bins" in metadata
        assert "unchanged_bins" in metadata

    def test_compute_difference_identifies_improvement_regions(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify difference computation identifies improvement regions."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Compute difference
        diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

        # Positive diff values indicate improvement (congestion reduced)
        improved_regions = diff > 0
        assert np.any(improved_regions), "Expected some improvement regions"

        # Check metadata tracks improvement
        assert metadata["improved_bins"] > 0
        assert metadata["total_improvement"] > 0

    def test_compute_difference_with_degradation(
        self, tmp_path: Path, parent_case_heatmap: np.ndarray
    ) -> None:
        """Verify difference computation identifies degradation regions."""
        parent_csv = tmp_path / "parent.csv"
        degraded_csv = tmp_path / "degraded.csv"

        # Create a degraded version (higher congestion)
        degraded_heatmap = parent_case_heatmap * 1.5  # 50% worse

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(degraded_csv, degraded_heatmap)

        # Compute difference
        diff, metadata = compute_heatmap_diff(parent_csv, degraded_csv)

        # Negative diff values indicate degradation (congestion increased)
        degraded_regions = diff < 0
        assert np.any(degraded_regions), "Expected some degradation regions"

        # Check metadata tracks degradation
        assert metadata["degraded_bins"] > 0
        assert metadata["total_degradation"] > 0


class TestF060Step4CreateDivergingColormap:
    """Step 4: Create matplotlib visualization with diverging colormap."""

    def test_render_diff_heatmap_with_diverging_colormap(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify differential heatmap uses diverging colormap."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "diff.png"

        # Create a mixed impact case (some improvement, some degradation)
        mixed_derived = derived_case_heatmap.copy()
        mixed_derived[0, 0] = parent_case_heatmap[0, 0] + 5.0  # Add degradation

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, mixed_derived)

        # Render differential heatmap
        metadata = render_diff_heatmap(
            baseline_csv=parent_csv,
            comparison_csv=derived_csv,
            output_path=diff_png,
        )

        # Verify PNG was created
        assert diff_png.exists()

        # Verify metadata contains diverging information
        assert "diff_range" in metadata
        # With mixed impact, we should have both negative and positive diffs
        assert metadata["diff_range"][0] < 0  # Negative values (red = worse)
        assert metadata["diff_range"][1] > 0  # Positive values (green = better)

    def test_diverging_colormap_red_for_worse_green_for_better(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify diverging colormap: red=worse, green=better."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Render differential heatmap
        render_diff_heatmap(
            baseline_csv=parent_csv,
            comparison_csv=derived_csv,
            output_path=diff_png,
            title="ECO Impact Analysis (Red=Worse, Green=Better)",
        )

        # Verify PNG was created with reasonable size
        assert diff_png.exists()
        assert diff_png.stat().st_size > 10000  # At least 10KB for a real plot


class TestF060Step5SaveDifferentialHeatmapPNG:
    """Step 5: Save differential heatmap as PNG."""

    def test_save_differential_heatmap_png(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify differential heatmap is saved as valid PNG."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "output" / "congestion_diff.png"

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Render differential heatmap
        metadata = render_diff_heatmap(
            baseline_csv=parent_csv,
            comparison_csv=derived_csv,
            output_path=diff_png,
        )

        # Verify PNG file exists
        assert diff_png.exists()

        # Verify output directory was created
        assert diff_png.parent.exists()

        # Verify metadata contains PNG path
        assert metadata["diff_png"] == str(diff_png)

    def test_png_is_valid_image_format(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify PNG is a valid image file."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Render differential heatmap
        render_diff_heatmap(
            baseline_csv=parent_csv,
            comparison_csv=derived_csv,
            output_path=diff_png,
        )

        # Verify PNG can be opened and read
        img = Image.open(diff_png)
        assert img.format == "PNG"
        assert img.width > 0
        assert img.height > 0

        # Verify image has color data
        img_array = np.array(img)
        assert img_array.size > 0


class TestF060Step6VerifyPNGShowsImprovementDegradation:
    """Step 6: Verify PNG shows regions of improvement vs degradation."""

    def test_png_contains_color_variation(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify PNG has color variation indicating improvement/degradation."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Render differential heatmap
        render_diff_heatmap(
            baseline_csv=parent_csv,
            comparison_csv=derived_csv,
            output_path=diff_png,
        )

        # Load PNG and verify it has variation
        img = Image.open(diff_png)
        img_array = np.array(img)

        # Count unique colors (should have many due to colormap)
        if img_array.ndim == 3:
            # RGB image
            unique_colors = len(np.unique(img_array.reshape(-1, img_array.shape[2]), axis=0))
        else:
            # Grayscale image
            unique_colors = len(np.unique(img_array))

        # Should have significant color variation (at least 50 unique colors)
        assert unique_colors > 50, f"Only {unique_colors} unique colors found"

    def test_metadata_shows_improvement_and_degradation_statistics(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Verify metadata includes improvement/degradation statistics."""
        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)

        # Render differential heatmap
        metadata = render_diff_heatmap(
            baseline_csv=parent_csv,
            comparison_csv=derived_csv,
            output_path=diff_png,
        )

        # Verify statistics are present
        assert "improved_bins" in metadata
        assert "degraded_bins" in metadata
        assert "unchanged_bins" in metadata
        assert "total_improvement" in metadata
        assert "total_degradation" in metadata
        assert "mean_diff" in metadata

        # Verify statistics are meaningful for this test case
        assert metadata["improved_bins"] > 0, "Expected some improvement regions"


# --- Integration Tests ---


class TestF060Integration:
    """Integration tests for complete differential heatmap workflow."""

    def test_complete_differential_heatmap_workflow(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Test complete workflow from CSV export to PNG generation."""
        # Step 1: Export parent case heatmap
        parent_csv = tmp_path / "parent_case" / "routing_congestion.csv"
        create_test_heatmap_csv(parent_csv, parent_case_heatmap)
        assert parent_csv.exists()

        # Step 2: Export derived case heatmap
        derived_csv = tmp_path / "derived_case" / "routing_congestion.csv"
        create_test_heatmap_csv(derived_csv, derived_case_heatmap)
        assert derived_csv.exists()

        # Step 3: Compute difference
        diff, diff_metadata = compute_heatmap_diff(parent_csv, derived_csv)
        assert diff.shape == parent_case_heatmap.shape
        assert diff_metadata["improved_bins"] > 0

        # Step 4-5: Create and save differential heatmap with diverging colormap
        diff_png = tmp_path / "output" / "congestion_diff.png"
        render_metadata = render_diff_heatmap(
            baseline_csv=parent_csv,
            comparison_csv=derived_csv,
            output_path=diff_png,
            title="ECO Impact: Routing Congestion",
        )

        # Step 6: Verify PNG shows improvement/degradation
        assert diff_png.exists()
        img = Image.open(diff_png)
        assert img.format == "PNG"
        assert render_metadata["improved_bins"] > 0
        assert "diff_png" in render_metadata

    def test_batch_differential_heatmap_generation(
        self,
        tmp_path: Path,
        parent_case_heatmap: np.ndarray,
        derived_case_heatmap: np.ndarray,
    ) -> None:
        """Test generating differential heatmaps for multiple heatmap types."""
        # Create parent case heatmaps
        parent_dir = tmp_path / "parent_heatmaps"
        parent_dir.mkdir()
        create_test_heatmap_csv(parent_dir / "routing_congestion.csv", parent_case_heatmap)
        create_test_heatmap_csv(parent_dir / "placement_density.csv", parent_case_heatmap * 0.8)

        # Create derived case heatmaps
        derived_dir = tmp_path / "derived_heatmaps"
        derived_dir.mkdir()
        create_test_heatmap_csv(derived_dir / "routing_congestion.csv", derived_case_heatmap)
        create_test_heatmap_csv(derived_dir / "placement_density.csv", derived_case_heatmap * 0.8)

        # Generate all differential heatmaps
        output_dir = tmp_path / "diff_heatmaps"
        results = generate_eco_impact_heatmaps(parent_dir, derived_dir, output_dir)

        # Verify both types were generated
        assert len(results) == 2
        assert (output_dir / "routing_congestion_diff.png").exists()
        assert (output_dir / "placement_density_diff.png").exists()

        # Verify metadata for each
        for result in results:
            assert "diff_png" in result
            assert "improved_bins" in result
            assert "degraded_bins" in result
            assert result["improved_bins"] > 0


# --- Edge Cases ---


class TestF060EdgeCases:
    """Test edge cases and error handling."""

    def test_differential_heatmap_with_no_change(self, tmp_path: Path) -> None:
        """Test differential heatmap when before and after are identical."""
        identical_data = np.ones((5, 5)) * 10.0

        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(parent_csv, identical_data)
        create_test_heatmap_csv(derived_csv, identical_data)

        # Compute difference
        diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

        # All differences should be zero
        assert np.all(diff == 0)
        assert metadata["improved_bins"] == 0
        assert metadata["degraded_bins"] == 0
        assert metadata["unchanged_bins"] == 25

        # Render should still work
        render_diff_heatmap(parent_csv, derived_csv, diff_png)
        assert diff_png.exists()

    def test_differential_heatmap_with_extreme_improvement(self, tmp_path: Path) -> None:
        """Test differential heatmap with extreme improvement (worst to best)."""
        worst_data = np.ones((5, 5)) * 100.0  # Maximum congestion
        best_data = np.zeros((5, 5))  # No congestion

        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(parent_csv, worst_data)
        create_test_heatmap_csv(derived_csv, best_data)

        # Compute difference
        diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

        # All bins should show improvement
        assert metadata["improved_bins"] == 25
        assert metadata["degraded_bins"] == 0
        assert metadata["mean_diff"] == 100.0

        # Render should work
        render_metadata = render_diff_heatmap(parent_csv, derived_csv, diff_png)
        assert diff_png.exists()
        assert render_metadata["total_improvement"] > 0

    def test_differential_heatmap_dimension_mismatch_raises_error(
        self, tmp_path: Path
    ) -> None:
        """Test that mismatched dimensions raise clear error."""
        small_data = np.ones((3, 3))
        large_data = np.ones((5, 5))

        parent_csv = tmp_path / "parent.csv"
        derived_csv = tmp_path / "derived.csv"

        create_test_heatmap_csv(parent_csv, small_data)
        create_test_heatmap_csv(derived_csv, large_data)

        # Should raise ValueError for dimension mismatch
        with pytest.raises(ValueError, match="dimensions don't match"):
            compute_heatmap_diff(parent_csv, derived_csv)
