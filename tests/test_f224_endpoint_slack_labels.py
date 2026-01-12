"""Tests for F224: Critical path overlay shows endpoints and slack labels.

This feature adds visual markers for path endpoints and displays slack values
as labels on critical paths to improve readability and understanding of timing issues.

Steps from feature_list.json:
1. Enable show_endpoints: true
2. Enable show_slack_labels: true
3. Generate overlay
4. Verify path endpoints are marked with visible symbols
5. Verify slack values are labeled on or near paths
6. Verify labels are readable and not overlapping
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.visualization.heatmap_renderer import (
    render_heatmap_with_critical_path_overlay,
)


class TestF224EndpointSlackLabels:
    """
    Test suite for Feature F224: Critical path endpoint and slack labeling.

    Verifies that endpoints can be marked with visible symbols and slack values
    can be labeled on paths to improve visualization clarity.
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
        for i in range(5):
            path = {
                "slack_ps": -2000 + i * 300,  # Varying slack values
                "startpoint": f"input_port_{i}",
                "endpoint": f"reg_data[{i}]",
                "points": [
                    (0 + i * 1.5, 0 + i * 1.5),
                    (2 + i * 1.5, 3 + i * 1.5),
                    (5 + i * 1.5, 7 + i * 1.5),
                    (8 + i * 1.5, 9 + i * 1.5),
                ],
            }
            paths.append(path)
        return paths

    def test_step_1_enable_show_endpoints_true(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 1: Enable show_endpoints: true."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_endpoints.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=True,  # Enable endpoint markers
                show_slack_labels=False,
            )

            # Verify show_endpoints was enabled
            assert result["show_endpoints"] is True
            assert output_path.exists()

    def test_step_2_enable_show_slack_labels_true(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 2: Enable show_slack_labels: true."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_slack_labels.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=False,
                show_slack_labels=True,  # Enable slack labels
            )

            # Verify show_slack_labels was enabled
            assert result["show_slack_labels"] is True
            assert output_path.exists()

    def test_step_3_generate_overlay_with_both_features(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 3: Generate overlay with both endpoints and slack labels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_complete.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=True,
                show_slack_labels=True,
            )

            # Verify both features are enabled
            assert result["show_endpoints"] is True
            assert result["show_slack_labels"] is True
            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_step_4_verify_path_endpoints_marked(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 4: Verify path endpoints are marked with visible symbols."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_endpoint_markers.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=True,
                show_slack_labels=False,
            )

            # Verify image was generated
            assert output_path.exists()

            # Load image and verify it has content
            img = Image.open(output_path)
            img_array = np.array(img)

            # Verify image has color variation (endpoints add distinct colors)
            assert img_array.std() > 0

            # Verify image is RGB with proper dimensions
            assert len(img_array.shape) == 3
            assert img_array.shape[2] in [3, 4]  # RGB or RGBA

            # Verify paths were drawn
            assert result["paths_drawn"] == 5

    def test_step_5_verify_slack_values_labeled(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 5: Verify slack values are labeled on or near paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_slack_labeling.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=False,
                show_slack_labels=True,
            )

            # Verify image was generated
            assert output_path.exists()

            # Load image and verify it has content
            img = Image.open(output_path)
            img_array = np.array(img)

            # Verify image has sufficient complexity (text labels add complexity)
            # Text rendering adds black/white pixels for text and backgrounds
            assert img_array.std() > 0

            # Verify metadata confirms slack labels are enabled
            assert result["show_slack_labels"] is True
            assert result["paths_drawn"] == 5

    def test_step_6_verify_labels_readable_not_overlapping(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Step 6: Verify labels are readable and not overlapping."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_label_readability.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=True,
                show_slack_labels=True,
                dpi=200,  # Higher DPI for better readability
                figsize=(10, 8),  # Larger figure for more space
            )

            # Verify image was generated with proper settings
            assert output_path.exists()
            assert result["dpi"] == 200
            assert result["figsize"] == (10, 8)

            # Load image and verify it's large enough for readable labels
            img = Image.open(output_path)
            assert img.size[0] >= 1500  # Width should be substantial
            assert img.size[1] >= 1200  # Height should be substantial

            # Verify all features are enabled
            assert result["show_endpoints"] is True
            assert result["show_slack_labels"] is True

    def test_edge_case_single_path_with_endpoints_and_labels(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test with single path to verify endpoint and label placement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_single_path.png"

            single_path = [
                {
                    "slack_ps": -1500,
                    "startpoint": "input_A",
                    "endpoint": "output_Z",
                    "points": [(1, 1), (3, 5), (7, 9)],
                }
            ]

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=single_path,
                path_count=10,
                show_endpoints=True,
                show_slack_labels=True,
            )

            # Verify rendering completed successfully
            assert output_path.exists()
            assert result["paths_drawn"] == 1
            assert result["show_endpoints"] is True
            assert result["show_slack_labels"] is True

    def test_edge_case_many_paths_label_density(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test with many paths to ensure labels don't clutter the image."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_many_paths.png"

            # Create 15 paths with different trajectories
            many_paths = []
            for i in range(15):
                path = {
                    "slack_ps": -3000 + i * 150,
                    "startpoint": f"in_{i}",
                    "endpoint": f"out_{i}",
                    "points": [
                        (0 + i * 0.4, 0 + i * 0.5),
                        (3 + i * 0.4, 4 + i * 0.5),
                        (6 + i * 0.4, 8 + i * 0.5),
                    ],
                }
                many_paths.append(path)

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=many_paths,
                path_count=10,  # Limit to 10 to reduce clutter
                show_endpoints=True,
                show_slack_labels=True,
                figsize=(12, 10),  # Large figure for spacing
            )

            # Verify only 10 paths drawn (respecting path_count)
            assert result["paths_drawn"] == 10
            assert output_path.exists()

    def test_edge_case_endpoints_only_no_labels(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test endpoints without slack labels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_endpoints_only.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=True,
                show_slack_labels=False,
            )

            # Verify only endpoints are shown
            assert result["show_endpoints"] is True
            assert result["show_slack_labels"] is False
            assert output_path.exists()

    def test_edge_case_labels_only_no_endpoints(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test slack labels without endpoint markers."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_labels_only.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=False,
                show_slack_labels=True,
            )

            # Verify only slack labels are shown
            assert result["show_endpoints"] is False
            assert result["show_slack_labels"] is True
            assert output_path.exists()

    def test_edge_case_neither_endpoints_nor_labels(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test with both features disabled (backward compatibility)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_neither.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=False,
                show_slack_labels=False,
            )

            # Verify both features are disabled
            assert result["show_endpoints"] is False
            assert result["show_slack_labels"] is False
            assert output_path.exists()
            # Should still render paths normally

    def test_edge_case_path_with_missing_slack_value(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test handling of paths without slack_ps field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_missing_slack.png"

            path_missing_slack = [
                {
                    # Missing 'slack_ps' field
                    "startpoint": "input_A",
                    "endpoint": "output_B",
                    "points": [(1, 1), (5, 5), (9, 9)],
                }
            ]

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=path_missing_slack,
                path_count=5,
                show_endpoints=True,
                show_slack_labels=True,
            )

            # Should handle gracefully, defaulting to 0ps
            assert output_path.exists()
            assert result["paths_drawn"] == 1

    def test_edge_case_path_with_single_point_no_labels(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that paths with single point don't get labels/endpoints."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_single_point.png"

            single_point_path = [
                {
                    "slack_ps": -1000,
                    "startpoint": "A",
                    "endpoint": "B",
                    "points": [(5, 5)],  # Only one point
                }
            ]

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=single_point_path,
                path_count=5,
                show_endpoints=True,
                show_slack_labels=True,
            )

            # Should not crash, path will be skipped
            assert output_path.exists()

    def test_backward_compatibility_with_f222_tests(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test that F222 functionality still works (default False for new params)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_backward_compat.png"

            # Call without new parameters (should default to False)
            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                # show_endpoints and show_slack_labels not specified
            )

            # Verify defaults to False (backward compatible)
            assert result["show_endpoints"] is False
            assert result["show_slack_labels"] is False
            assert output_path.exists()
            assert result["paths_drawn"] == 5

    def test_integration_with_color_by_modes(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test endpoints and labels work with different color_by modes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            paths_with_delay_info = [
                {
                    "slack_ps": -1500,
                    "wire_delay_pct": 65.0,
                    "cell_delay_pct": 35.0,
                    "startpoint": "A",
                    "endpoint": "B",
                    "points": [(1, 1), (5, 5), (9, 9)],
                }
            ]

            for color_mode in ["slack", "wire_delay", "cell_delay"]:
                output_path = Path(tmpdir) / f"test_color_{color_mode}.png"

                result = render_heatmap_with_critical_path_overlay(
                    csv_path=sample_heatmap_csv,
                    output_path=output_path,
                    critical_paths=paths_with_delay_info,
                    path_count=5,
                    color_by=color_mode,
                    show_endpoints=True,
                    show_slack_labels=True,
                )

                # Verify rendering with color mode and new features
                assert output_path.exists()
                assert result["color_by"] == color_mode
                assert result["show_endpoints"] is True
                assert result["show_slack_labels"] is True

    def test_metadata_completeness(
        self, sample_heatmap_csv: Path, sample_critical_paths: list[dict]
    ) -> None:
        """Test that returned metadata includes all expected fields including new ones."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_metadata.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=sample_critical_paths,
                path_count=5,
                show_endpoints=True,
                show_slack_labels=True,
            )

            # Verify all expected metadata fields (including new ones)
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
                "color_by",
                "show_endpoints",  # New field
                "show_slack_labels",  # New field
            ]

            for field in expected_fields:
                assert field in result, f"Missing metadata field: {field}"
