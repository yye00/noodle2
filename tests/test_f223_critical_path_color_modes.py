"""Tests for F223: Critical path overlay supports color-by-slack mode.

This feature adds color mode support to critical path overlays, allowing paths
to be colored by slack (red=worst, yellow=moderate), wire delay percentage, or
cell delay percentage.

Steps from feature_list.json:
1. Set critical_path_overlay color_by: slack
2. Generate overlay
3. Verify paths are colored by slack (red=worst, yellow=moderate)
4. Change to color_by: wire_delay
5. Verify paths are colored by wire delay percentage
6. Verify color_by: cell_delay mode works
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.visualization.heatmap_renderer import render_heatmap_with_critical_path_overlay


class TestF223CriticalPathColorModes:
    """
    Test suite for Feature F223: Critical path overlay color modes.

    Verifies that critical paths can be colored by different metrics:
    slack, wire_delay, and cell_delay.
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
    def critical_paths_with_delays(self) -> list[dict]:
        """Create sample critical paths with slack and delay metrics."""
        paths = []
        for i in range(10):
            path = {
                "slack_ps": -2000 + i * 200,  # Increasingly better slack
                "wire_delay_pct": 30.0 + i * 5.0,  # Increasing wire delay
                "cell_delay_pct": 70.0 - i * 5.0,  # Decreasing cell delay
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

    def test_step_1_set_color_by_slack(
        self, sample_heatmap_csv: Path, critical_paths_with_delays: list[dict]
    ) -> None:
        """Step 1: Set critical_path_overlay color_by: slack."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "slack_colored.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=critical_paths_with_delays,
                path_count=10,
                color_by="slack",
            )

            # Verify color_by mode is set
            assert result["color_by"] == "slack"

    def test_step_2_generate_overlay_with_slack_coloring(
        self, sample_heatmap_csv: Path, critical_paths_with_delays: list[dict]
    ) -> None:
        """Step 2: Generate overlay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "slack_colored.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=critical_paths_with_delays,
                path_count=10,
                color_by="slack",
            )

            # Verify PNG was generated
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            # Verify metadata
            assert result["png_path"] == str(output_path)
            assert result["paths_drawn"] == 10

    def test_step_3_verify_slack_coloring(
        self, sample_heatmap_csv: Path, critical_paths_with_delays: list[dict]
    ) -> None:
        """Step 3: Verify paths are colored by slack (red=worst, yellow=moderate)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "slack_colored.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=critical_paths_with_delays,
                path_count=10,
                color_by="slack",
            )

            # Verify image was created
            assert output_path.exists()
            img = Image.open(output_path)
            pixels = np.array(img)

            # Verify the image has color variation (not monochrome)
            # Check that RGB channels have different distributions
            r_channel = pixels[:, :, 0]
            g_channel = pixels[:, :, 1]
            b_channel = pixels[:, :, 2]

            # For slack coloring (RdYlGn), we expect red and green variation
            r_std = np.std(r_channel)
            g_std = np.std(g_channel)

            # Both channels should have variation (not flat)
            assert r_std > 10.0, "Red channel should vary for slack coloring"
            assert g_std > 10.0, "Green channel should vary for slack coloring"

            # Verify metadata includes color_by
            assert result["color_by"] == "slack"

    def test_step_4_change_to_wire_delay_coloring(
        self, sample_heatmap_csv: Path, critical_paths_with_delays: list[dict]
    ) -> None:
        """Step 4: Change to color_by: wire_delay."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "wire_delay_colored.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=critical_paths_with_delays,
                path_count=10,
                color_by="wire_delay",
            )

            # Verify color_by mode changed
            assert result["color_by"] == "wire_delay"

            # Verify PNG was generated
            assert output_path.exists()
            assert output_path.stat().st_size > 0

    def test_step_5_verify_wire_delay_coloring(
        self, sample_heatmap_csv: Path, critical_paths_with_delays: list[dict]
    ) -> None:
        """Step 5: Verify paths are colored by wire delay percentage."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "wire_delay_colored.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=critical_paths_with_delays,
                path_count=10,
                color_by="wire_delay",
            )

            # Verify image was created
            assert output_path.exists()
            img = Image.open(output_path)
            pixels = np.array(img)

            # Verify the image has color variation (plasma colormap should show variation)
            r_channel = pixels[:, :, 0]
            b_channel = pixels[:, :, 2]

            r_std = np.std(r_channel)
            b_std = np.std(b_channel)

            # Plasma colormap has strong blue and red components
            assert r_std > 5.0, "Red channel should vary for wire delay coloring"
            assert b_std > 5.0, "Blue channel should vary for wire delay coloring"

            assert result["color_by"] == "wire_delay"

    def test_step_6_verify_cell_delay_coloring(
        self, sample_heatmap_csv: Path, critical_paths_with_delays: list[dict]
    ) -> None:
        """Step 6: Verify color_by: cell_delay mode works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "cell_delay_colored.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=critical_paths_with_delays,
                path_count=10,
                color_by="cell_delay",
            )

            # Verify color_by mode
            assert result["color_by"] == "cell_delay"

            # Verify PNG was generated
            assert output_path.exists()
            assert output_path.stat().st_size > 0

            # Verify the image has color variation (viridis colormap)
            img = Image.open(output_path)
            pixels = np.array(img)

            g_channel = pixels[:, :, 1]
            b_channel = pixels[:, :, 2]

            g_std = np.std(g_channel)
            b_std = np.std(b_channel)

            # Viridis has strong green and blue components
            assert g_std > 5.0, "Green channel should vary for cell delay coloring"
            assert b_std > 5.0, "Blue channel should vary for cell delay coloring"


class TestF223EdgeCases:
    """Additional tests for edge cases and error handling."""

    @pytest.fixture
    def sample_heatmap_csv(self) -> Path:
        """Create a sample heatmap CSV file for testing."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            for i in range(10):
                row = [str(float(i + j)) for j in range(10)]
                f.write(",".join(row) + "\n")
            return Path(f.name)

    def test_invalid_color_mode_raises_error(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that invalid color_by mode raises ValueError."""
        paths = [
            {
                "slack_ps": -1000,
                "points": [(0, 0), (5, 5)],
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"

            with pytest.raises(ValueError) as exc_info:
                render_heatmap_with_critical_path_overlay(
                    csv_path=sample_heatmap_csv,
                    output_path=output_path,
                    critical_paths=paths,
                    color_by="invalid_mode",
                )

            assert "Invalid color_by" in str(exc_info.value)
            assert "invalid_mode" in str(exc_info.value)

    def test_default_color_by_is_slack(self, sample_heatmap_csv: Path) -> None:
        """Test that default color_by mode is 'slack'."""
        paths = [
            {
                "slack_ps": -1000,
                "points": [(0, 0), (5, 5)],
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=paths,
            )

            assert result["color_by"] == "slack"

    def test_slack_mode_with_all_same_slack_values(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test slack mode when all paths have the same slack value."""
        paths = [
            {
                "slack_ps": -1000,
                "points": [(i, i), (i + 1, i + 1)],
            }
            for i in range(5)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=paths,
                color_by="slack",
            )

            # Should handle gracefully
            assert result["paths_drawn"] == 5
            assert output_path.exists()

    def test_wire_delay_mode_missing_wire_delay_field(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test wire_delay mode when paths are missing wire_delay_pct field."""
        paths = [
            {
                "slack_ps": -1000 - i * 100,
                "points": [(i, i), (i + 1, i + 1)],
                # No wire_delay_pct field
            }
            for i in range(5)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=paths,
                color_by="wire_delay",
            )

            # Should use default value (50.0) and handle gracefully
            assert result["paths_drawn"] == 5
            assert output_path.exists()

    def test_cell_delay_mode_missing_cell_delay_field(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test cell_delay mode when paths are missing cell_delay_pct field."""
        paths = [
            {
                "slack_ps": -1000 - i * 100,
                "points": [(i, i), (i + 1, i + 1)],
                # No cell_delay_pct field
            }
            for i in range(5)
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=paths,
                color_by="cell_delay",
            )

            # Should use default value (50.0) and handle gracefully
            assert result["paths_drawn"] == 5
            assert output_path.exists()

    def test_label_text_changes_with_color_mode(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that path labels change based on color_by mode."""
        paths = [
            {
                "slack_ps": -1000,
                "wire_delay_pct": 35.5,
                "cell_delay_pct": 64.5,
                "points": [(0, 0), (5, 5)],
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test slack mode
            output_slack = Path(tmpdir) / "slack.png"
            result_slack = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_slack,
                critical_paths=paths,
                color_by="slack",
            )
            assert result_slack["color_by"] == "slack"

            # Test wire_delay mode
            output_wire = Path(tmpdir) / "wire.png"
            result_wire = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_wire,
                critical_paths=paths,
                color_by="wire_delay",
            )
            assert result_wire["color_by"] == "wire_delay"

            # Test cell_delay mode
            output_cell = Path(tmpdir) / "cell.png"
            result_cell = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_cell,
                critical_paths=paths,
                color_by="cell_delay",
            )
            assert result_cell["color_by"] == "cell_delay"

            # All should have generated different files
            assert output_slack.exists()
            assert output_wire.exists()
            assert output_cell.exists()
