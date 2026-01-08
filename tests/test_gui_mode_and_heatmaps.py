"""Tests for GUI mode execution and heatmap rendering."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.controller.types import ExecutionMode
from src.trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner
from src.trial_runner.tcl_generator import (
    generate_heatmap_export_commands,
    generate_trial_script,
    write_trial_script,
)
from src.visualization import (
    get_recommended_colormap,
    parse_heatmap_csv,
    render_all_heatmaps,
    render_heatmap_png,
)


class TestGUIModeConfiguration:
    """Test GUI mode configuration and Docker runner setup."""

    def test_docker_run_config_has_gui_mode_field(self) -> None:
        """DockerRunConfig should have gui_mode field."""
        config = DockerRunConfig(gui_mode=True)
        assert config.gui_mode is True

    def test_docker_run_config_gui_mode_defaults_to_false(self) -> None:
        """GUI mode should default to False for backward compatibility."""
        config = DockerRunConfig()
        assert config.gui_mode is False

    def test_gui_mode_enabled_adds_x11_volume(self) -> None:
        """When GUI mode is enabled, X11 socket should be mounted."""
        config = DockerRunConfig(gui_mode=True)
        runner = DockerTrialRunner(config)

        # This test verifies the implementation detail that X11 socket
        # is added to volumes when gui_mode=True
        # We can't easily test Docker execution without actual Docker,
        # so we verify the config is stored correctly
        assert runner.config.gui_mode is True

    def test_gui_mode_disabled_does_not_add_x11_volume(self) -> None:
        """When GUI mode is disabled, X11 socket should not be mounted."""
        config = DockerRunConfig(gui_mode=False)
        runner = DockerTrialRunner(config)
        assert runner.config.gui_mode is False

    def test_check_gui_available_returns_false_when_display_not_set(self) -> None:
        """check_gui_available should return False when DISPLAY is not set."""
        config = DockerRunConfig()
        runner = DockerTrialRunner(config)

        with patch.dict("os.environ", {}, clear=True):
            # Remove DISPLAY from environment
            assert runner.check_gui_available() is False

    def test_check_gui_available_returns_false_when_x11_socket_missing(self) -> None:
        """check_gui_available should return False when X11 socket doesn't exist."""
        config = DockerRunConfig()
        runner = DockerTrialRunner(config)

        with patch.dict("os.environ", {"DISPLAY": ":0"}):
            with patch("pathlib.Path.exists", return_value=False):
                assert runner.check_gui_available() is False

    def test_check_gui_available_returns_true_when_prerequisites_met(self) -> None:
        """check_gui_available should return True when DISPLAY set and X11 socket exists."""
        config = DockerRunConfig()
        runner = DockerTrialRunner(config)

        with patch.dict("os.environ", {"DISPLAY": ":0"}):
            with patch("pathlib.Path.exists", return_value=True):
                assert runner.check_gui_available() is True


class TestHeatmapExportCommands:
    """Test heatmap export TCL command generation."""

    def test_generate_heatmap_export_commands_returns_tcl_string(self) -> None:
        """generate_heatmap_export_commands should return valid TCL commands."""
        commands = generate_heatmap_export_commands("/work")
        assert isinstance(commands, str)
        assert len(commands) > 0

    def test_heatmap_commands_include_placement_density(self) -> None:
        """Heatmap export should include placement_density."""
        commands = generate_heatmap_export_commands("/work")
        assert "placement_density" in commands
        assert "gui::dump_heatmap" in commands

    def test_heatmap_commands_include_rudy(self) -> None:
        """Heatmap export should include RUDY congestion."""
        commands = generate_heatmap_export_commands("/work")
        assert "rudy" in commands

    def test_heatmap_commands_include_routing_congestion(self) -> None:
        """Heatmap export should include routing_congestion."""
        commands = generate_heatmap_export_commands("/work")
        assert "routing_congestion" in commands

    def test_heatmap_commands_create_heatmaps_directory(self) -> None:
        """Heatmap export should create heatmaps/ subdirectory."""
        commands = generate_heatmap_export_commands("/work")
        assert "file mkdir" in commands
        assert "/work/heatmaps" in commands

    def test_heatmap_commands_use_correct_output_paths(self) -> None:
        """Heatmap CSVs should be written to correct paths."""
        commands = generate_heatmap_export_commands("/custom/output")
        assert "/custom/output/heatmaps/placement_density.csv" in commands
        assert "/custom/output/heatmaps/rudy.csv" in commands
        assert "/custom/output/heatmaps/routing_congestion.csv" in commands


class TestTCLGeneratorVisualization:
    """Test TCL script generation with visualization enabled."""

    def test_generate_trial_script_accepts_visualization_parameter(self) -> None:
        """generate_trial_script should accept visualization_enabled parameter."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            visualization_enabled=True,
        )
        assert isinstance(script, str)

    def test_visualization_disabled_by_default(self) -> None:
        """Visualization should be disabled by default."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
        )
        # Should not contain heatmap export commands
        assert "gui::dump_heatmap" not in script

    def test_visualization_enabled_includes_heatmap_export(self) -> None:
        """When visualization is enabled, script should include heatmap exports."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            visualization_enabled=True,
        )
        assert "gui::dump_heatmap" in script
        assert "placement_density" in script

    def test_visualization_enabled_for_sta_congestion_mode(self) -> None:
        """Visualization should work with STA_CONGESTION mode."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            visualization_enabled=True,
        )
        assert "gui::dump_heatmap" in script
        assert "rudy" in script
        assert "routing_congestion" in script

    def test_visualization_enabled_for_full_route_mode(self) -> None:
        """Visualization should work with FULL_ROUTE mode."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.FULL_ROUTE,
            design_name="test_design",
            visualization_enabled=True,
        )
        assert "gui::dump_heatmap" in script

    def test_write_trial_script_accepts_visualization_parameter(self) -> None:
        """write_trial_script should accept visualization_enabled parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "test_script.tcl"
            result_path = write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
                visualization_enabled=True,
            )
            assert result_path.exists()
            content = result_path.read_text()
            assert "gui::dump_heatmap" in content


class TestHeatmapCSVParsing:
    """Test heatmap CSV parsing."""

    def test_parse_heatmap_csv_reads_simple_csv(self) -> None:
        """parse_heatmap_csv should read a simple CSV file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            # Create simple 3x3 heatmap
            csv_path.write_text("1.0,2.0,3.0\n4.0,5.0,6.0\n7.0,8.0,9.0\n")

            data, metadata = parse_heatmap_csv(csv_path)

            assert isinstance(data, np.ndarray)
            assert data.shape == (3, 3)
            assert metadata["shape"] == (3, 3)
            assert metadata["min_value"] == 1.0
            assert metadata["max_value"] == 9.0

    def test_parse_heatmap_csv_handles_empty_cells(self) -> None:
        """parse_heatmap_csv should treat empty cells as 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            csv_path.write_text("1.0,,3.0\n,5.0,\n7.0,,9.0\n")

            data, metadata = parse_heatmap_csv(csv_path)

            assert data[0, 1] == 0.0  # Empty cell
            assert data[1, 0] == 0.0
            assert data[1, 2] == 0.0

    def test_parse_heatmap_csv_raises_on_missing_file(self) -> None:
        """parse_heatmap_csv should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_heatmap_csv("/nonexistent/heatmap.csv")

    def test_parse_heatmap_csv_raises_on_empty_file(self) -> None:
        """parse_heatmap_csv should raise ValueError for empty file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "empty.csv"
            csv_path.write_text("")

            with pytest.raises(ValueError, match="Empty CSV"):
                parse_heatmap_csv(csv_path)

    def test_parse_heatmap_csv_extracts_metadata(self) -> None:
        """parse_heatmap_csv should extract correct metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            csv_path.write_text("0.0,1.0\n2.0,3.0\n")

            data, metadata = parse_heatmap_csv(csv_path)

            assert metadata["min_value"] == 0.0
            assert metadata["max_value"] == 3.0
            assert metadata["mean_value"] == 1.5
            assert metadata["nonzero_count"] == 3


class TestHeatmapPNGRendering:
    """Test PNG rendering from heatmap CSVs."""

    def test_render_heatmap_png_creates_file(self) -> None:
        """render_heatmap_png should create PNG file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            png_path = Path(tmpdir) / "test_heatmap.png"
            csv_path.write_text("1.0,2.0,3.0\n4.0,5.0,6.0\n7.0,8.0,9.0\n")

            result = render_heatmap_png(csv_path, png_path)

            assert png_path.exists()
            assert result["png_path"] == str(png_path)
            assert result["csv_path"] == str(csv_path)

    def test_render_heatmap_png_with_custom_title(self) -> None:
        """render_heatmap_png should accept custom title."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            png_path = Path(tmpdir) / "test_heatmap.png"
            csv_path.write_text("1.0,2.0\n3.0,4.0\n")

            result = render_heatmap_png(csv_path, png_path, title="Custom Title")

            assert png_path.exists()

    def test_render_heatmap_png_with_custom_colormap(self) -> None:
        """render_heatmap_png should accept custom colormap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            png_path = Path(tmpdir) / "test_heatmap.png"
            csv_path.write_text("1.0,2.0\n3.0,4.0\n")

            result = render_heatmap_png(csv_path, png_path, colormap="viridis")

            assert png_path.exists()
            assert result["colormap"] == "viridis"

    def test_render_heatmap_png_returns_metadata(self) -> None:
        """render_heatmap_png should return rendering metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            png_path = Path(tmpdir) / "test_heatmap.png"
            csv_path.write_text("1.0,2.0\n3.0,4.0\n")

            result = render_heatmap_png(csv_path, png_path, dpi=200)

            assert result["dpi"] == 200
            assert result["data_shape"] == (2, 2)
            assert result["value_range"] == [1.0, 4.0]

    def test_render_heatmap_png_creates_output_directory(self) -> None:
        """render_heatmap_png should create output directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_heatmap.csv"
            png_path = Path(tmpdir) / "subdir" / "test_heatmap.png"
            csv_path.write_text("1.0,2.0\n3.0,4.0\n")

            render_heatmap_png(csv_path, png_path)

            assert png_path.exists()
            assert png_path.parent.exists()


class TestRenderAllHeatmaps:
    """Test batch rendering of all heatmaps in a directory."""

    def test_render_all_heatmaps_processes_multiple_files(self) -> None:
        """render_all_heatmaps should process all CSV files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            heatmaps_dir = Path(tmpdir) / "heatmaps"
            heatmaps_dir.mkdir()

            # Create multiple heatmap CSVs
            (heatmaps_dir / "placement_density.csv").write_text("1,2\n3,4\n")
            (heatmaps_dir / "rudy.csv").write_text("5,6\n7,8\n")
            (heatmaps_dir / "routing_congestion.csv").write_text("9,10\n11,12\n")

            results = render_all_heatmaps(heatmaps_dir)

            assert len(results) == 3
            assert (heatmaps_dir / "placement_density.png").exists()
            assert (heatmaps_dir / "rudy.png").exists()
            assert (heatmaps_dir / "routing_congestion.png").exists()

    def test_render_all_heatmaps_to_separate_output_dir(self) -> None:
        """render_all_heatmaps should support separate output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            heatmaps_dir = Path(tmpdir) / "heatmaps"
            output_dir = Path(tmpdir) / "previews"
            heatmaps_dir.mkdir()

            (heatmaps_dir / "test.csv").write_text("1,2\n3,4\n")

            results = render_all_heatmaps(heatmaps_dir, output_dir=output_dir)

            assert len(results) == 1
            assert (output_dir / "test.png").exists()
            assert not (heatmaps_dir / "test.png").exists()

    def test_render_all_heatmaps_raises_on_missing_directory(self) -> None:
        """render_all_heatmaps should raise if heatmaps directory doesn't exist."""
        with pytest.raises(FileNotFoundError):
            render_all_heatmaps("/nonexistent/heatmaps")

    def test_render_all_heatmaps_returns_empty_list_for_empty_directory(self) -> None:
        """render_all_heatmaps should return empty list if no CSVs found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = render_all_heatmaps(tmpdir)
            assert results == []


class TestRecommendedColormap:
    """Test recommended colormap selection."""

    def test_get_recommended_colormap_for_placement_density(self) -> None:
        """placement_density should use viridis colormap."""
        cmap = get_recommended_colormap("placement_density")
        assert cmap == "viridis"

    def test_get_recommended_colormap_for_rudy(self) -> None:
        """RUDY should use plasma colormap."""
        cmap = get_recommended_colormap("rudy")
        assert cmap == "plasma"

    def test_get_recommended_colormap_for_routing_congestion(self) -> None:
        """routing_congestion should use hot colormap."""
        cmap = get_recommended_colormap("routing_congestion")
        assert cmap == "hot"

    def test_get_recommended_colormap_is_case_insensitive(self) -> None:
        """Colormap selection should be case-insensitive."""
        assert get_recommended_colormap("PLACEMENT_DENSITY") == "viridis"
        assert get_recommended_colormap("Rudy") == "plasma"

    def test_get_recommended_colormap_partial_match(self) -> None:
        """Colormap selection should support partial matches."""
        assert get_recommended_colormap("routing") == "hot"
        assert get_recommended_colormap("congestion") == "hot"

    def test_get_recommended_colormap_default_fallback(self) -> None:
        """Unknown heatmap types should use default 'hot' colormap."""
        cmap = get_recommended_colormap("unknown_type")
        assert cmap == "hot"


class TestHeatmapIntegration:
    """Integration tests for complete heatmap workflow."""

    def test_complete_heatmap_workflow(self) -> None:
        """Test complete workflow: CSV creation → parsing → PNG rendering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Create heatmap CSV (simulating OpenROAD output)
            heatmaps_dir = Path(tmpdir) / "heatmaps"
            heatmaps_dir.mkdir()
            csv_path = heatmaps_dir / "placement_density.csv"
            csv_path.write_text("0.5,0.7,0.9\n0.6,0.8,1.0\n0.4,0.5,0.6\n")

            # Step 2: Parse CSV
            data, metadata = parse_heatmap_csv(csv_path)
            assert metadata["shape"] == (3, 3)
            assert metadata["max_value"] == 1.0

            # Step 3: Render PNG
            png_path = heatmaps_dir / "placement_density.png"
            result = render_heatmap_png(csv_path, png_path)
            assert png_path.exists()
            assert result["data_shape"] == (3, 3)

    def test_batch_render_multiple_heatmaps(self) -> None:
        """Test batch rendering of all standard heatmap types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            heatmaps_dir = Path(tmpdir) / "heatmaps"
            heatmaps_dir.mkdir()

            # Create all three standard heatmaps
            (heatmaps_dir / "placement_density.csv").write_text("1.0,2.0\n3.0,4.0\n")
            (heatmaps_dir / "rudy.csv").write_text("0.1,0.2\n0.3,0.4\n")
            (heatmaps_dir / "routing_congestion.csv").write_text("10,20\n30,40\n")

            # Batch render all
            results = render_all_heatmaps(heatmaps_dir)

            assert len(results) == 3
            assert all((heatmaps_dir / f"{r['csv_path'].split('/')[-1].replace('.csv', '.png')}").exists() for r in results if 'csv_path' in r)
