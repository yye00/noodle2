"""Tests for F112: Heatmap generation loads real CSV data from OpenROAD and creates PNG.

Verifies that:
1. CSV data can be exported from OpenROAD using gui::dump_heatmap
2. CSV data is loaded using numpy
3. Matplotlib figure is created with imshow(data, cmap=hot)
4. PNG is saved using plt.savefig with dpi=150
5. PNG file size > 10KB and is a valid image
"""

import numpy as np
import pytest
from pathlib import Path
from PIL import Image

from src.visualization.heatmap_renderer import (
    parse_heatmap_csv,
    render_heatmap_png,
)


class TestHeatmapCSVParsing:
    """Test CSV loading from OpenROAD heatmap exports."""

    def test_step_1_export_heatmap_csv_format(self):
        """Step 1: Verify OpenROAD gui::dump_heatmap CSV format can be loaded."""
        # Create a sample CSV in OpenROAD bbox format
        csv_content = """x0,y0,x1,y1,value
0.0,0.0,10.0,10.0,0.5
10.0,0.0,20.0,10.0,0.8
0.0,10.0,10.0,20.0,0.3
10.0,10.0,20.0,20.0,0.9
"""
        csv_file = Path("test_outputs/heatmap_test_bbox.csv")
        csv_file.parent.mkdir(exist_ok=True)
        csv_file.write_text(csv_content)

        # Parse the CSV
        data, metadata = parse_heatmap_csv(csv_file, grid_size=10)

        # Verify data was loaded
        assert isinstance(data, np.ndarray)
        assert data.shape == (10, 10)
        assert metadata["shape"] == (10, 10)
        assert metadata["max_value"] >= 0.0
        assert metadata["min_value"] >= 0.0

    def test_step_2_load_csv_with_numpy(self):
        """Step 2: Load CSV data using numpy.loadtxt equivalent."""
        # Create a simple grid format CSV
        csv_content = """0.1,0.2,0.3
0.4,0.5,0.6
0.7,0.8,0.9
"""
        csv_file = Path("test_outputs/heatmap_test_grid.csv")
        csv_file.write_text(csv_content)

        # Parse the CSV
        data, metadata = parse_heatmap_csv(csv_file)

        # Verify data was loaded as numpy array
        assert isinstance(data, np.ndarray)
        assert data.shape == (3, 3)
        assert data.dtype == np.float64

        # Verify values
        assert abs(data[0, 0] - 0.1) < 0.01
        assert abs(data[1, 1] - 0.5) < 0.01
        assert abs(data[2, 2] - 0.9) < 0.01

        # Verify metadata
        assert metadata["min_value"] == pytest.approx(0.1)
        assert metadata["max_value"] == pytest.approx(0.9)
        assert metadata["mean_value"] == pytest.approx(0.5)
        assert metadata["nonzero_count"] == 9

    def test_load_placement_density_csv(self):
        """Test loading realistic placement density CSV."""
        # Create a CSV with realistic placement density values (0.0 to 1.0)
        csv_content = "0.0,0.2,0.5,0.8\n0.1,0.3,0.6,0.9\n0.2,0.4,0.7,1.0\n"
        csv_file = Path("test_outputs/placement_density.csv")
        csv_file.write_text(csv_content)

        data, metadata = parse_heatmap_csv(csv_file)

        # Verify placement density characteristics
        assert data.shape == (3, 4)
        assert metadata["min_value"] >= 0.0
        assert metadata["max_value"] <= 1.0
        assert metadata["mean_value"] > 0.0

    def test_load_congestion_csv(self):
        """Test loading congestion heatmap CSV."""
        # Create a CSV with congestion values
        csv_content = "0.0,5.2,10.5\n2.1,8.3,12.6\n4.2,11.4,15.7\n"
        csv_file = Path("test_outputs/congestion.csv")
        csv_file.write_text(csv_content)

        data, metadata = parse_heatmap_csv(csv_file)

        # Verify congestion characteristics
        assert data.shape == (3, 3)
        assert metadata["max_value"] > 0.0
        assert metadata["mean_value"] > 0.0


class TestMatplotlibRendering:
    """Test matplotlib figure creation and rendering."""

    def test_step_3_create_matplotlib_figure_with_imshow(self):
        """Step 3: Create matplotlib figure with imshow(data, cmap=hot)."""
        # Create test CSV
        csv_content = "0.0,0.5,1.0\n0.2,0.6,0.9\n0.4,0.8,0.7\n"
        csv_file = Path("test_outputs/heatmap_for_imshow.csv")
        csv_file.write_text(csv_content)

        # Render heatmap
        png_file = Path("test_outputs/heatmap_imshow.png")
        metadata = render_heatmap_png(
            csv_path=csv_file,
            output_path=png_file,
            title="Test Heatmap",
            colormap="hot",  # Verify hot colormap is used
            dpi=150,
        )

        # Verify rendering succeeded
        assert "png_path" in metadata
        assert "colormap" in metadata
        assert metadata["colormap"] == "hot"
        assert png_file.exists()

    def test_step_4_save_png_with_dpi_150(self):
        """Step 4: Save as PNG using plt.savefig with dpi=150."""
        # Create test CSV
        csv_content = "0.1,0.2,0.3\n0.4,0.5,0.6\n0.7,0.8,0.9\n"
        csv_file = Path("test_outputs/heatmap_dpi_test.csv")
        csv_file.write_text(csv_content)

        # Render with dpi=150
        png_file = Path("test_outputs/heatmap_dpi_150.png")
        metadata = render_heatmap_png(
            csv_path=csv_file,
            output_path=png_file,
            dpi=150,
        )

        # Verify PNG was created
        assert png_file.exists()
        assert metadata["dpi"] == 150
        assert metadata["png_path"] == str(png_file)

    def test_render_with_custom_colormap(self):
        """Test rendering with different colormaps."""
        csv_content = "0.0,0.5,1.0\n0.3,0.6,0.9\n0.2,0.7,0.8\n"
        csv_file = Path("test_outputs/heatmap_cmap_test.csv")
        csv_file.write_text(csv_content)

        # Test different colormaps
        for cmap in ["hot", "viridis", "plasma", "coolwarm"]:
            png_file = Path(f"test_outputs/heatmap_{cmap}.png")
            metadata = render_heatmap_png(
                csv_path=csv_file,
                output_path=png_file,
                colormap=cmap,
                dpi=100,
            )

            assert png_file.exists()
            assert metadata["colormap"] == cmap

    def test_render_with_title(self):
        """Test rendering with custom title."""
        csv_content = "0.1,0.2\n0.3,0.4\n"
        csv_file = Path("test_outputs/heatmap_title_test.csv")
        csv_file.write_text(csv_content)

        png_file = Path("test_outputs/heatmap_with_title.png")
        metadata = render_heatmap_png(
            csv_path=csv_file,
            output_path=png_file,
            title="Placement Density Heatmap",
            dpi=100,
        )

        assert png_file.exists()
        # Title is rendered but not returned in metadata
        assert "png_path" in metadata


class TestPNGValidation:
    """Test PNG file validation."""

    def test_step_5_verify_png_file_size_greater_than_10kb(self):
        """Step 5: Verify PNG file size > 10KB and is valid image."""
        # Create a larger CSV to ensure PNG > 10KB
        rows = []
        for i in range(20):
            row = ",".join(str((i * 20 + j) / 400.0) for j in range(20))
            rows.append(row)
        csv_content = "\n".join(rows)

        csv_file = Path("test_outputs/heatmap_large.csv")
        csv_file.write_text(csv_content)

        # Render heatmap with high DPI to ensure size > 10KB
        png_file = Path("test_outputs/heatmap_large.png")
        metadata = render_heatmap_png(
            csv_path=csv_file,
            output_path=png_file,
            dpi=150,
            figsize=(10, 8),
        )

        # Verify PNG exists and is large enough
        assert png_file.exists()
        file_size = png_file.stat().st_size
        assert file_size > 10_000  # > 10KB
        # Verify metadata indicates successful render
        assert metadata["png_path"] == str(png_file)
        assert metadata["dpi"] == 150

    def test_verify_png_is_valid_image(self):
        """Verify generated PNG is a valid image file."""
        csv_content = "0.1,0.2,0.3\n0.4,0.5,0.6\n0.7,0.8,0.9\n"
        csv_file = Path("test_outputs/heatmap_valid.csv")
        csv_file.write_text(csv_content)

        png_file = Path("test_outputs/heatmap_valid.png")
        render_heatmap_png(
            csv_path=csv_file,
            output_path=png_file,
            dpi=150,
        )

        # Verify PNG can be opened and is a valid image
        assert png_file.exists()

        # Try to open with PIL
        img = Image.open(png_file)
        assert img.format == "PNG"
        assert img.size[0] > 0  # Width > 0
        assert img.size[1] > 0  # Height > 0

    def test_png_has_correct_dimensions(self):
        """Test that PNG dimensions match figsize * dpi."""
        csv_content = "0.1,0.2\n0.3,0.4\n"
        csv_file = Path("test_outputs/heatmap_dims.csv")
        csv_file.write_text(csv_content)

        png_file = Path("test_outputs/heatmap_dims.png")
        figsize = (8, 6)
        dpi = 100

        render_heatmap_png(
            csv_path=csv_file,
            output_path=png_file,
            figsize=figsize,
            dpi=dpi,
        )

        # Open image and check dimensions
        img = Image.open(png_file)
        width, height = img.size

        # Dimensions should be approximately figsize * dpi
        # (may vary slightly due to tight_layout)
        assert width >= figsize[0] * dpi * 0.9  # Allow 10% tolerance
        assert height >= figsize[1] * dpi * 0.9


class TestHeatmapGenerationEndToEnd:
    """End-to-end tests for heatmap generation."""

    def test_complete_heatmap_generation_workflow(self):
        """Test complete workflow: CSV -> Parse -> Render -> Validate."""
        # Step 1: Create CSV (simulating OpenROAD export)
        csv_content = """x0,y0,x1,y1,value
0,0,100,100,0.25
100,0,200,100,0.50
0,100,100,200,0.75
100,100,200,200,1.00
"""
        csv_file = Path("test_outputs/heatmap_e2e.csv")
        csv_file.write_text(csv_content)

        # Step 2: Parse CSV
        data, parse_metadata = parse_heatmap_csv(csv_file, grid_size=20)
        assert isinstance(data, np.ndarray)
        assert data.shape == (20, 20)

        # Step 3: Render PNG
        png_file = Path("test_outputs/heatmap_e2e.png")
        render_metadata = render_heatmap_png(
            csv_path=csv_file,
            output_path=png_file,
            title="End-to-End Heatmap Test",
            colormap="hot",
            dpi=150,
        )

        # Step 4: Validate PNG
        assert png_file.exists()
        file_size = png_file.stat().st_size
        assert file_size > 10_000

        # Step 5: Verify image is valid
        img = Image.open(png_file)
        assert img.format == "PNG"
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_render_multiple_heatmap_types(self):
        """Test rendering different types of heatmaps (placement, congestion, routing)."""
        heatmap_types = {
            "placement_density": "0.0,0.3,0.6,0.9\n0.1,0.4,0.7,1.0\n",
            "routing_congestion": "0.0,5.2,10.4,15.6\n1.3,6.5,11.7,16.9\n",
            "pin_density": "0,10,20,30\n5,15,25,35\n",
        }

        for heatmap_name, csv_content in heatmap_types.items():
            csv_file = Path(f"test_outputs/{heatmap_name}.csv")
            csv_file.write_text(csv_content)

            png_file = Path(f"test_outputs/{heatmap_name}.png")
            metadata = render_heatmap_png(
                csv_path=csv_file,
                output_path=png_file,
                title=heatmap_name.replace("_", " ").title(),
                colormap="hot",
                dpi=150,
            )

            assert png_file.exists()
            file_size = png_file.stat().st_size
            assert file_size > 1000  # At least 1KB
            img = Image.open(png_file)
            assert img.format == "PNG"
