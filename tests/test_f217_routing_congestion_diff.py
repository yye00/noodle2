"""Tests for F217: Generate differential routing congestion heatmap."""

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


class TestRoutingCongestionDifferentialF217:
    """
    Test suite for Feature F217: Generate differential routing congestion heatmap.

    Steps from feature_list.json:
    1. Generate routing congestion heatmap for parent case
    2. Generate routing congestion heatmap for derived case
    3. Compute differential heatmap
    4. Export as routing_congestion_diff.csv and .png
    5. Verify hotspot resolution is visible in differential
    6. Verify new hotspots (if any) are highlighted
    """

    def test_step_1_generate_parent_routing_congestion(self) -> None:
        """Step 1: Generate routing congestion heatmap for parent case."""
        # Create a parent routing congestion heatmap with hotspots
        parent_congestion = np.array(
            [
                [1.0, 2.0, 3.0, 2.0, 1.0],
                [2.0, 4.0, 6.0, 4.0, 2.0],
                [3.0, 6.0, 9.0, 6.0, 3.0],  # Severe congestion hotspot
                [2.0, 4.0, 6.0, 4.0, 2.0],
                [1.0, 2.0, 3.0, 2.0, 1.0],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_routing_congestion.csv"
            create_test_heatmap_csv(parent_csv, parent_congestion)

            # Verify file created
            assert parent_csv.exists()

            # Verify data can be loaded
            loaded = np.loadtxt(parent_csv, delimiter=",")
            np.testing.assert_array_almost_equal(loaded, parent_congestion)

    def test_step_2_generate_derived_routing_congestion(self) -> None:
        """Step 2: Generate routing congestion heatmap for derived case."""
        # Create a derived (post-ECO) routing congestion heatmap
        # This should show hotspot resolution
        derived_congestion = np.array(
            [
                [1.0, 2.0, 3.0, 2.0, 1.0],
                [2.0, 3.0, 4.0, 3.0, 2.0],  # Reduced congestion
                [3.0, 4.0, 5.0, 4.0, 3.0],  # Hotspot resolved!
                [2.0, 3.0, 4.0, 3.0, 2.0],  # Reduced congestion
                [1.0, 2.0, 3.0, 2.0, 1.0],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            derived_csv = Path(tmpdir) / "derived_routing_congestion.csv"
            create_test_heatmap_csv(derived_csv, derived_congestion)

            # Verify file created
            assert derived_csv.exists()

            # Verify data can be loaded
            loaded = np.loadtxt(derived_csv, delimiter=",")
            np.testing.assert_array_almost_equal(loaded, derived_congestion)

    def test_step_3_compute_differential_heatmap(self) -> None:
        """Step 3: Compute differential heatmap."""
        parent_congestion = np.array(
            [
                [2.0, 4.0, 6.0],
                [4.0, 8.0, 4.0],  # Hotspot at center
                [2.0, 4.0, 6.0],
            ]
        )

        derived_congestion = np.array(
            [
                [2.0, 3.0, 5.0],  # Reduced
                [3.0, 5.0, 3.0],  # Hotspot resolved!
                [2.0, 3.0, 5.0],  # Reduced
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_routing_congestion.csv"
            derived_csv = Path(tmpdir) / "derived_routing_congestion.csv"

            create_test_heatmap_csv(parent_csv, parent_congestion)
            create_test_heatmap_csv(derived_csv, derived_congestion)

            # Compute differential
            diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

            # Verify differential computed correctly
            # Diff = parent - derived, so positive = improvement (congestion reduced)
            expected_diff = parent_congestion - derived_congestion
            np.testing.assert_array_almost_equal(diff, expected_diff)

            # Verify metadata
            assert "min_diff" in metadata
            assert "max_diff" in metadata
            assert "mean_diff" in metadata
            assert "improved_bins" in metadata
            assert "degraded_bins" in metadata

            # Should show improvement
            assert metadata["mean_diff"] > 0, "Overall congestion should be reduced"
            assert (
                metadata["improved_bins"] > 0
            ), "Some bins should show improvement"

    def test_step_4_export_as_csv_and_png(self) -> None:
        """Step 4: Export as routing_congestion_diff.csv and .png."""
        parent_congestion = np.array(
            [
                [1.0, 3.0, 5.0],
                [3.0, 7.0, 3.0],
                [1.0, 3.0, 5.0],
            ]
        )

        derived_congestion = np.array(
            [
                [1.0, 2.0, 4.0],
                [2.0, 4.0, 2.0],
                [1.0, 2.0, 4.0],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_routing_congestion.csv"
            derived_csv = Path(tmpdir) / "derived_routing_congestion.csv"
            diff_csv = Path(tmpdir) / "routing_congestion_diff.csv"
            diff_png = Path(tmpdir) / "routing_congestion_diff.png"

            create_test_heatmap_csv(parent_csv, parent_congestion)
            create_test_heatmap_csv(derived_csv, derived_congestion)

            # Compute and export differential CSV
            diff, _ = compute_heatmap_diff(parent_csv, derived_csv)
            np.savetxt(diff_csv, diff, delimiter=",", fmt="%.4f")

            # Verify CSV created
            assert diff_csv.exists()

            # Render differential PNG
            metadata = render_diff_heatmap(
                baseline_csv=parent_csv,
                comparison_csv=derived_csv,
                output_path=diff_png,
                title="Routing Congestion - ECO Impact",
            )

            # Verify PNG created
            assert diff_png.exists()

            # Verify metadata
            assert metadata["diff_png"] == str(diff_png)
            assert "data_shape" in metadata
            assert "improved_bins" in metadata
            assert "degraded_bins" in metadata

    def test_step_5_verify_hotspot_resolution_visible(self) -> None:
        """Step 5: Verify hotspot resolution is visible in differential."""
        # Parent has severe hotspot at center
        parent_congestion = np.array(
            [
                [1.0, 1.0, 1.0, 1.0, 1.0],
                [1.0, 2.0, 3.0, 2.0, 1.0],
                [1.0, 3.0, 9.0, 3.0, 1.0],  # Severe hotspot!
                [1.0, 2.0, 3.0, 2.0, 1.0],
                [1.0, 1.0, 1.0, 1.0, 1.0],
            ]
        )

        # Derived has hotspot resolved
        derived_congestion = np.array(
            [
                [1.0, 1.0, 1.0, 1.0, 1.0],
                [1.0, 2.0, 2.5, 2.0, 1.0],
                [1.0, 2.5, 3.0, 2.5, 1.0],  # Hotspot resolved!
                [1.0, 2.0, 2.5, 2.0, 1.0],
                [1.0, 1.0, 1.0, 1.0, 1.0],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_routing_congestion.csv"
            derived_csv = Path(tmpdir) / "derived_routing_congestion.csv"

            create_test_heatmap_csv(parent_csv, parent_congestion)
            create_test_heatmap_csv(derived_csv, derived_congestion)

            # Compute differential
            diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

            # Center hotspot should show maximum improvement
            center_diff = diff[2, 2]
            assert (
                center_diff == np.max(diff)
            ), "Center hotspot should show maximum improvement"
            assert center_diff == 6.0, "Hotspot improvement should be 9.0 - 3.0 = 6.0"

            # Surrounding area should also show improvement
            assert diff[1, 2] > 0, "Surrounding bins should also improve"
            assert diff[2, 1] > 0, "Surrounding bins should also improve"

            # Metadata should reflect improvement
            assert (
                metadata["mean_diff"] > 0
            ), "Mean diff should be positive (improvement)"
            assert metadata["improved_bins"] > 0, "Multiple bins should be improved"

    def test_step_6_verify_new_hotspots_highlighted(self) -> None:
        """Step 6: Verify new hotspots (if any) are highlighted."""
        # Parent has hotspot at top-left
        parent_congestion = np.array(
            [
                [8.0, 4.0, 2.0],  # Hotspot at top-left
                [4.0, 2.0, 1.0],
                [2.0, 1.0, 1.0],
            ]
        )

        # Derived resolves top-left but creates new hotspot at bottom-right
        derived_congestion = np.array(
            [
                [3.0, 2.0, 1.0],  # Original hotspot resolved
                [2.0, 2.0, 4.0],
                [1.0, 4.0, 7.0],  # New hotspot!
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            parent_csv = Path(tmpdir) / "parent_routing_congestion.csv"
            derived_csv = Path(tmpdir) / "derived_routing_congestion.csv"
            diff_png = Path(tmpdir) / "routing_congestion_diff.png"

            create_test_heatmap_csv(parent_csv, parent_congestion)
            create_test_heatmap_csv(derived_csv, derived_congestion)

            # Compute differential
            diff, metadata = compute_heatmap_diff(parent_csv, derived_csv)

            # Top-left should show improvement (positive diff)
            assert diff[0, 0] > 0, "Original hotspot area should show improvement"
            assert diff[0, 0] == 5.0, "Top-left improvement should be 8.0 - 3.0 = 5.0"

            # Bottom-right should show degradation (negative diff)
            assert diff[2, 2] < 0, "New hotspot should show degradation"
            assert diff[2, 2] == -6.0, "Bottom-right degradation should be 1.0 - 7.0 = -6.0"

            # Metadata should reflect both changes
            assert metadata["improved_bins"] > 0, "Some bins improved"
            assert metadata["degraded_bins"] > 0, "Some bins degraded"

            # Render to verify visualization
            render_metadata = render_diff_heatmap(
                baseline_csv=parent_csv,
                comparison_csv=derived_csv,
                output_path=diff_png,
                title="Routing Congestion - Hotspot Migration",
            )

            assert diff_png.exists()
            assert render_metadata["improved_bins"] > 0
            assert render_metadata["degraded_bins"] > 0

    def test_complete_f217_workflow(self) -> None:
        """Test complete F217 workflow: parent -> derived -> diff."""
        # Simulate a realistic congestion reduction scenario
        parent_congestion = np.array(
            [
                [1.0, 2.0, 3.0, 2.0, 1.0],
                [2.0, 4.0, 6.0, 4.0, 2.0],
                [3.0, 6.0, 10.0, 6.0, 3.0],  # Severe hotspot
                [2.0, 4.0, 6.0, 4.0, 2.0],
                [1.0, 2.0, 3.0, 2.0, 1.0],
            ]
        )

        # ECO reroutes congested nets, reducing hotspot
        derived_congestion = np.array(
            [
                [1.0, 2.0, 3.0, 2.0, 1.0],
                [2.0, 3.0, 4.0, 3.0, 2.0],  # Reduced
                [3.0, 4.0, 5.0, 4.0, 3.0],  # Hotspot resolved!
                [2.0, 3.0, 4.0, 3.0, 2.0],  # Reduced
                [1.0, 2.0, 3.0, 2.0, 1.0],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1 & 2: Create parent and derived heatmaps
            parent_csv = Path(tmpdir) / "parent_routing_congestion.csv"
            derived_csv = Path(tmpdir) / "derived_routing_congestion.csv"

            create_test_heatmap_csv(parent_csv, parent_congestion)
            create_test_heatmap_csv(derived_csv, derived_congestion)

            # Step 3: Compute differential
            diff, diff_metadata = compute_heatmap_diff(parent_csv, derived_csv)

            # Step 4: Export CSV and PNG
            diff_csv = Path(tmpdir) / "routing_congestion_diff.csv"
            diff_png = Path(tmpdir) / "routing_congestion_diff.png"

            np.savetxt(diff_csv, diff, delimiter=",", fmt="%.4f")

            render_metadata = render_diff_heatmap(
                baseline_csv=parent_csv,
                comparison_csv=derived_csv,
                output_path=diff_png,
                title="Routing Congestion - ECO Impact",
            )

            # Verify all artifacts created
            assert parent_csv.exists()
            assert derived_csv.exists()
            assert diff_csv.exists()
            assert diff_png.exists()

            # Step 5: Verify hotspot resolution
            center_diff = diff[2, 2]
            assert center_diff > 0, "Center hotspot should be resolved"
            assert center_diff == 5.0, "Center improvement should be 10.0 - 5.0 = 5.0"

            # Step 6: Verify overall improvement
            assert diff_metadata["mean_diff"] > 0, "Overall congestion reduced"
            assert (
                diff_metadata["improved_bins"] > diff_metadata["degraded_bins"]
            ), "More bins improved than degraded"

            # Metadata is complete
            assert "total_improvement" in diff_metadata
            assert "total_degradation" in diff_metadata
            assert render_metadata["improved_bins"] > 0
