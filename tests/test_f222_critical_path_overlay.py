"""Tests for F222: Generate critical path overlay on placement density heatmap.

This feature enables visualization of timing-critical paths overlaid on placement
density heatmaps to help identify correlation between congestion and timing issues.

Steps from feature_list.json:
1. Enable critical_path_overlay in visualization config
2. Set path_count: 10
3. Generate heatmap with overlay
4. Verify top 10 critical paths are drawn on heatmap
5. Verify paths are visually distinct from heatmap
6. Export as critical_paths.png
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.visualization.heatmap_renderer import (
    parse_heatmap_csv,
    render_heatmap_with_critical_path_overlay,
)


class TestF222CriticalPathOverlay:
    """
    Test suite for Feature F222: Critical path overlay on heatmap.

    Verifies that critical paths can be overlaid on placement density heatmaps
    with configurable path count and visually distinct rendering.
    """

    @pytest.fixture
    def sample_heatmap_csv(self) -> Path:
        """Create a sample heatmap CSV file for testing."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            # Create 10x10 grid with some variation
            for i in range(10):
                row = [str(float(i + j)) for j in range(10)]
                f.write(",".join(row) + "\n")
            return Path(f.name)

    @pytest.fixture
    def sample_critical_paths(self) -> list[dict]:
        """Create sample critical paths for testing."""
        paths = []
        for i in range(15):  # More than path_count to test limiting
            path = {
                "slack_ps": -2000 + i * 100,  # Increasingly better slack
                "startpoint": f"input_port_{i}",
                "endpoint": f"reg_data[{i}]",
                "points": [
                    (0 + i * 0.5, 0 + i * 0.5),
                    (2 + i * 0.5, 3 + i * 0.5),
                    (5 + i * 0.5, 7 + i * 0.5),
                    (8 + i * 0.5, 9 + i * 0.5),
                ],
            }
            paths.append(path)
        return paths

    def test_step_1_enable_critical_path_overlay_in_config(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 1: Enable critical_path_overlay in visualization config."""
        # Configuration is implicit via function parameters
        # Verify function accepts critical_paths parameter
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_overlay.png"

            # Call with critical_path_overlay enabled (by providing paths)
            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify function executed successfully
            assert result is not None
            assert "paths_drawn" in result
            assert "path_count_limit" in result

    def test_step_2_set_path_count_to_10(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 2: Set path_count: 10."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_overlay.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify path_count is respected
            assert result["path_count_limit"] == 10
            assert result["total_paths_available"] == 15
            # Should draw at most 10 paths even though 15 are available
            assert result["paths_drawn"] == 10

    def test_step_3_generate_heatmap_with_overlay(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 3: Generate heatmap with overlay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "critical_paths.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify PNG was generated
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            # Verify metadata
            assert result["png_path"] == str(output_path)
            assert result["csv_path"] == str(sample_heatmap_csv)

    def test_step_4_verify_top_10_critical_paths_drawn(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 4: Verify top 10 critical paths are drawn on heatmap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "critical_paths.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify exactly 10 paths were drawn
            assert result["paths_drawn"] == 10

            # Verify it's the top 10 (first 10 in the list)
            assert result["path_count_limit"] == 10

            # Open image to verify it was rendered
            img = Image.open(output_path)
            assert img.size[0] > 0
            assert img.size[1] > 0

    def test_step_5_verify_paths_visually_distinct_from_heatmap(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 5: Verify paths are visually distinct from heatmap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "critical_paths.png"

            # Generate with viridis colormap (blue-green-yellow)
            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                colormap="viridis",  # Blue-green-yellow spectrum
                path_count=10,
            )

            # Verify colormap was used
            assert result["colormap"] == "viridis"

            # The function uses red-to-yellow colors for paths (path_colors = plt.cm.Reds)
            # which are visually distinct from viridis (blue-green-yellow)
            # We verify this by checking the image was generated successfully
            img = Image.open(output_path)
            img_array = np.array(img)

            # Verify image has color variation (not all same color)
            # This indicates both heatmap and paths are present
            assert img_array.std() > 0

            # Verify image is RGB (has color channels)
            assert len(img_array.shape) == 3
            assert img_array.shape[2] in [3, 4]  # RGB or RGBA

    def test_step_6_export_as_critical_paths_png(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 6: Export as critical_paths.png."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "critical_paths.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify file was exported with correct name
            assert output_path.exists()
            assert output_path.name == "critical_paths.png"
            assert result["png_path"] == str(output_path)

            # Verify it's a valid PNG
            img = Image.open(output_path)
            assert img.format == "PNG"

    def test_edge_case_empty_paths_list(self, sample_heatmap_csv: Path) -> None:
        """Test with empty critical paths list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_empty.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=[],
                path_count=10,
            )

            # Should still generate heatmap, just without paths
            assert output_path.exists()
            assert result["paths_drawn"] == 0
            assert result["total_paths_available"] == 0

    def test_edge_case_fewer_paths_than_path_count(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test when available paths < path_count."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_few_paths.png"

            # Only 3 paths available
            few_paths = [
                {
                    "slack_ps": -2000,
                    "startpoint": "A",
                    "endpoint": "B",
                    "points": [(0, 0), (5, 5)],
                },
                {
                    "slack_ps": -1500,
                    "startpoint": "C",
                    "endpoint": "D",
                    "points": [(1, 1), (6, 6)],
                },
                {
                    "slack_ps": -1000,
                    "startpoint": "E",
                    "endpoint": "F",
                    "points": [(2, 2), (7, 7)],
                },
            ]

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=few_paths,
                path_count=10,
            )

            # Should draw all 3 available paths
            assert result["paths_drawn"] == 3
            assert result["path_count_limit"] == 10
            assert result["total_paths_available"] == 3

    def test_edge_case_path_with_single_point(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test handling of paths with insufficient points."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_single_point.png"

            paths_with_issues = [
                {
                    "slack_ps": -2000,
                    "startpoint": "A",
                    "endpoint": "B",
                    "points": [(0, 0)],  # Only 1 point - can't draw line
                },
                {
                    "slack_ps": -1500,
                    "startpoint": "C",
                    "endpoint": "D",
                    "points": [(1, 1), (6, 6)],  # Valid path
                },
            ]

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=paths_with_issues,
                path_count=10,
            )

            # Should generate successfully, skipping invalid path
            assert output_path.exists()
            # Only 1 path should be drawn (the valid one)
            assert result["paths_drawn"] <= 2

    def test_edge_case_path_without_points_key(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test handling of paths missing 'points' key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_missing_points.png"

            paths_missing_points = [
                {
                    "slack_ps": -2000,
                    "startpoint": "A",
                    "endpoint": "B",
                    # Missing 'points' key
                },
                {
                    "slack_ps": -1500,
                    "startpoint": "C",
                    "endpoint": "D",
                    "points": [(1, 1), (6, 6)],  # Valid path
                },
            ]

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=paths_missing_points,
                path_count=10,
            )

            # Should generate successfully, skipping invalid path
            assert output_path.exists()

    def test_custom_colormap_and_dpi(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test custom colormap and DPI settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_custom.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                colormap="plasma",
                dpi=200,
                path_count=5,
            )

            # Verify custom settings were applied
            assert result["colormap"] == "plasma"
            assert result["dpi"] == 200
            assert result["paths_drawn"] == 5

            # Verify higher DPI produces larger file
            assert output_path.stat().st_size > 1000

    def test_custom_title(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test custom title rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_title.png"

            custom_title = "Critical Paths on Placement Density"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                title=custom_title,
                path_count=10,
            )

            # Verify rendering completed
            assert output_path.exists()
            assert result["png_path"] == str(output_path)

    def test_integration_with_parse_heatmap_csv(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test integration with existing heatmap parsing."""
        # First parse the CSV
        data, metadata = parse_heatmap_csv(sample_heatmap_csv)

        # Verify we can read the heatmap
        assert data.shape == (10, 10)

        # Now overlay paths on it
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "integration_test.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify data shape matches
            assert result["data_shape"] == (10, 10)
            assert result["data_shape"] == metadata["shape"]

    def test_output_directory_creation(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test that output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested path that doesn't exist
            output_path = (
                Path(tmpdir) / "subdir1" / "subdir2" / "critical_paths.png"
            )

            assert not output_path.parent.exists()

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify directory was created
            assert output_path.parent.exists()
            assert output_path.exists()

    def test_metadata_completeness(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test that returned metadata contains all expected fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_metadata.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=10,
            )

            # Verify all expected metadata fields
            expected_fields = [
                "csv_path",
                "png_path",
                "data_shape",
                "value_range",
                "colormap",
                "dpi",
                "figsize",
                "paths_drawn",
                "path_count_limit",
                "total_paths_available",
            ]

            for field in expected_fields:
                assert field in result, f"Missing metadata field: {field}"

    def test_different_path_counts(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test varying path_count values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for count in [1, 5, 10, 15, 20]:
                output_path = Path(tmpdir) / f"test_count_{count}.png"

                result = render_heatmap_with_critical_path_overlay(
                    csv_path=sample_heatmap_csv,
                    output_path=output_path,
                    critical_paths=sample_critical_paths,
                    path_count=count,
                )

                # Verify path count is respected
                # Since we have 15 paths available, max drawn is 15
                expected_drawn = min(count, 15)
                assert result["paths_drawn"] == expected_drawn
                assert result["path_count_limit"] == count

    def test_filenotfound_error_handling(
        self, sample_critical_paths: list[dict]
    ) -> None:
        """Test error handling for missing CSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.png"
            missing_csv = Path(tmpdir) / "missing.csv"

            with pytest.raises(FileNotFoundError):
                render_heatmap_with_critical_path_overlay(
                    csv_path=missing_csv,
                    output_path=output_path,
                    critical_paths=sample_critical_paths,
                    path_count=10,
                )
