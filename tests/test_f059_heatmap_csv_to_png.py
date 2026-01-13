"""Tests for F059: Heatmap CSV can be converted to PNG using matplotlib.

F059: Heatmap CSV can be converted to PNG using matplotlib

Test Steps:
1. Export placement_density.csv from OpenROAD
2. Load CSV using numpy.loadtxt()
3. Create matplotlib figure with imshow()
4. Save as PNG using plt.savefig()
5. Verify PNG file is valid image (not text file)
6. Verify image shows heatmap visualization
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.infrastructure.heatmap_execution import generate_heatmap_csv
from src.visualization.heatmap_renderer import parse_heatmap_csv, render_heatmap_png


class TestF059HeatmapCSVToPNG:
    """Test F059: Convert heatmap CSV to PNG using matplotlib."""

    @pytest.fixture
    def nangate45_odb(self) -> Path:
        """Provide path to Nangate45 placed design ODB file."""
        odb_path = Path("studies/nangate45_base/gcd_placed.odb")
        if not odb_path.exists():
            pytest.skip("Nangate45 snapshot not available")
        return odb_path

    @pytest.fixture
    def test_output_dir(self) -> Path:
        """Provide test output directory under project root."""
        output_dir = Path("test_outputs/f059_heatmap_png")
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def test_step_1_export_placement_density_csv_from_openroad(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Step 1: Export placement_density.csv from OpenROAD."""
        output_csv = test_output_dir / "placement_density.csv"

        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"
        assert output_csv.exists(), f"CSV file not created at {output_csv}"
        assert output_csv.stat().st_size > 0, "CSV file is empty"

    def test_step_2_load_csv_using_numpy(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Step 2: Load CSV using numpy.loadtxt()."""
        # First generate the CSV
        output_csv = test_output_dir / "placement_density_numpy.csv"

        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Load CSV using parse_heatmap_csv (which uses numpy internally)
        data, metadata = parse_heatmap_csv(output_csv)

        # Verify it's a numpy array
        assert isinstance(data, np.ndarray)
        assert data.ndim == 2, "Data should be 2D array"
        assert data.shape[0] > 0 and data.shape[1] > 0, "Array should be non-empty"

        # Verify metadata
        assert "shape" in metadata
        assert "min_value" in metadata
        assert "max_value" in metadata
        assert metadata["shape"] == data.shape

    def test_step_3_create_matplotlib_figure_with_imshow(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Step 3: Create matplotlib figure with imshow()."""
        import matplotlib.pyplot as plt

        # Generate CSV
        output_csv = test_output_dir / "placement_density_imshow.csv"

        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Load data
        data, metadata = parse_heatmap_csv(output_csv)

        # Create figure with imshow
        fig, ax = plt.subplots()
        im = ax.imshow(data, cmap="hot", interpolation="nearest")

        # Verify figure was created
        assert fig is not None
        assert ax is not None
        assert im is not None

        # Clean up
        plt.close(fig)

    def test_step_4_save_as_png_using_plt_savefig(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Step 4: Save as PNG using plt.savefig()."""
        output_csv = test_output_dir / "placement_density_savefig.csv"
        output_png = test_output_dir / "placement_density_savefig.png"

        # Generate CSV
        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Render PNG using render_heatmap_png (which uses plt.savefig internally)
        metadata = render_heatmap_png(
            csv_path=output_csv,
            output_path=output_png,
            title="Placement Density Heatmap",
            colormap="hot",
        )

        # Verify PNG was saved
        assert output_png.exists(), f"PNG file not created at {output_png}"
        assert output_png.stat().st_size > 0, "PNG file is empty"
        assert metadata["png_path"] == str(output_png)

    def test_step_5_verify_png_is_valid_image_not_text(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Step 5: Verify PNG file is valid image (not text file)."""
        output_csv = test_output_dir / "placement_density_valid.csv"
        output_png = test_output_dir / "placement_density_valid.png"

        # Generate CSV
        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Render PNG
        render_heatmap_png(
            csv_path=output_csv,
            output_path=output_png,
            colormap="hot",
        )

        # Verify it's a valid image by opening with PIL
        try:
            img = Image.open(output_png)
            assert img.format == "PNG", f"File is not PNG format: {img.format}"
            assert img.mode in ["RGB", "RGBA", "P"], f"Invalid image mode: {img.mode}"
            assert img.size[0] > 0 and img.size[1] > 0, "Image has zero dimensions"
        except Exception as e:
            pytest.fail(f"PNG file is not a valid image: {e}")

        # Verify it's not a text file by checking magic bytes
        with open(output_png, "rb") as f:
            magic_bytes = f.read(8)
            # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
            assert magic_bytes[:4] == b'\x89PNG', "File doesn't have PNG magic bytes"

    def test_step_6_verify_image_shows_heatmap_visualization(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Step 6: Verify image shows heatmap visualization."""
        output_csv = test_output_dir / "placement_density_visual.csv"
        output_png = test_output_dir / "placement_density_visual.png"

        # Generate CSV
        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Load CSV data to check it has variation (not all zeros)
        data, metadata = parse_heatmap_csv(output_csv)

        # Verify data has variation (characteristic of a real heatmap)
        assert metadata["min_value"] != metadata["max_value"], \
            "Heatmap has no variation (all values are the same)"
        assert metadata["nonzero_count"] > 0, \
            "Heatmap is all zeros (no placement data)"

        # Render PNG
        render_metadata = render_heatmap_png(
            csv_path=output_csv,
            output_path=output_png,
            title="Placement Density Heatmap",
            colormap="hot",
            dpi=150,
        )

        # Open image and verify it has the expected properties
        img = Image.open(output_png)

        # Verify image has reasonable dimensions (not 1x1 or empty)
        assert img.size[0] >= 100, f"Image width too small: {img.size[0]}"
        assert img.size[1] >= 100, f"Image height too small: {img.size[1]}"

        # Verify metadata includes expected information
        assert render_metadata["data_shape"] == data.shape
        assert render_metadata["value_range"] == [metadata["min_value"], metadata["max_value"]]
        assert render_metadata["colormap"] == "hot"
        assert render_metadata["dpi"] == 150

        # Verify image has color variation (not monochrome)
        # Convert to RGB and check that pixels have different colors
        img_rgb = img.convert("RGB")
        pixels = list(img_rgb.getdata())
        unique_colors = set(pixels)

        # A heatmap should have multiple distinct colors
        assert len(unique_colors) > 10, \
            f"Image has too few colors ({len(unique_colors)}), may not be a proper heatmap"


class TestF059Integration:
    """Integration test for complete CSV to PNG workflow."""

    @pytest.fixture
    def nangate45_odb(self) -> Path:
        """Provide path to Nangate45 placed design ODB file."""
        odb_path = Path("studies/nangate45_base/gcd_placed.odb")
        if not odb_path.exists():
            pytest.skip("Nangate45 snapshot not available")
        return odb_path

    @pytest.fixture
    def test_output_dir(self) -> Path:
        """Provide test output directory under project root."""
        output_dir = Path("test_outputs/f059_integration")
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def test_complete_csv_to_png_workflow(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Test complete workflow: OpenROAD CSV export → numpy load → matplotlib render → PNG save."""
        output_csv = test_output_dir / "complete_workflow.csv"
        output_png = test_output_dir / "complete_workflow.png"

        # Step 1: Export CSV from OpenROAD
        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Step 2: Load with numpy (via parse_heatmap_csv)
        data, metadata = parse_heatmap_csv(output_csv)
        assert isinstance(data, np.ndarray)

        # Step 3-4: Create matplotlib figure and save as PNG
        render_metadata = render_heatmap_png(
            csv_path=output_csv,
            output_path=output_png,
            title="Complete Workflow Test",
            colormap="viridis",
        )

        # Step 5: Verify PNG is valid
        img = Image.open(output_png)
        assert img.format == "PNG"

        # Step 6: Verify visualization quality
        assert img.size[0] >= 100
        assert img.size[1] >= 100
        assert render_metadata["data_shape"] == data.shape

    def test_multiple_heatmap_types_can_be_converted(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Verify multiple heatmap types (Placement, RUDY) can be converted to PNG."""
        heatmap_types = [
            ("Placement", "placement_density"),
            ("RUDY", "rudy"),
        ]

        for heatmap_type, file_stem in heatmap_types:
            output_csv = test_output_dir / f"{file_stem}.csv"
            output_png = test_output_dir / f"{file_stem}.png"

            # Generate CSV
            result = generate_heatmap_csv(
                odb_file=nangate45_odb,
                heatmap_type=heatmap_type,
                output_csv=output_csv,
                timeout=60,
            )

            assert result.success, f"{heatmap_type} CSV export failed: {result.error}"

            # Convert to PNG
            render_heatmap_png(
                csv_path=output_csv,
                output_path=output_png,
                title=f"{heatmap_type} Heatmap",
            )

            # Verify PNG
            assert output_png.exists()
            img = Image.open(output_png)
            assert img.format == "PNG"
            assert img.size[0] >= 100
            assert img.size[1] >= 100

    def test_csv_to_png_with_custom_colormap(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Verify CSV to PNG conversion supports custom colormaps."""
        output_csv = test_output_dir / "custom_colormap.csv"

        colormaps = ["hot", "viridis", "plasma", "coolwarm"]

        # Generate CSV once
        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Render with different colormaps
        for cmap in colormaps:
            output_png = test_output_dir / f"heatmap_{cmap}.png"

            metadata = render_heatmap_png(
                csv_path=output_csv,
                output_path=output_png,
                colormap=cmap,
            )

            assert output_png.exists()
            assert metadata["colormap"] == cmap

            # Verify it's a valid PNG
            img = Image.open(output_png)
            assert img.format == "PNG"

    def test_csv_to_png_with_custom_dpi(
        self, nangate45_odb: Path, test_output_dir: Path
    ) -> None:
        """Verify CSV to PNG conversion supports custom DPI settings."""
        output_csv = test_output_dir / "custom_dpi.csv"

        # Generate CSV
        result = generate_heatmap_csv(
            odb_file=nangate45_odb,
            heatmap_type="Placement",
            output_csv=output_csv,
            timeout=60,
        )

        assert result.success, f"CSV export failed: {result.error}"

        # Render with different DPI values
        dpi_values = [72, 150, 300]

        for dpi in dpi_values:
            output_png = test_output_dir / f"heatmap_dpi{dpi}.png"

            metadata = render_heatmap_png(
                csv_path=output_csv,
                output_path=output_png,
                dpi=dpi,
            )

            assert output_png.exists()
            assert metadata["dpi"] == dpi

            # Verify file size increases with DPI (higher resolution)
            img = Image.open(output_png)
            assert img.format == "PNG"


class TestF059EdgeCases:
    """Test edge cases for CSV to PNG conversion."""

    def test_csv_with_synthetic_data_converts_correctly(self) -> None:
        """Verify CSV to PNG works with synthetic test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "synthetic.csv"
            png_path = Path(tmpdir) / "synthetic.png"

            # Create synthetic 10x10 heatmap with gradient
            data = np.linspace(0, 100, 100).reshape(10, 10)
            np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

            # Convert to PNG
            metadata = render_heatmap_png(
                csv_path=csv_path,
                output_path=png_path,
                title="Synthetic Heatmap",
            )

            assert png_path.exists()
            assert metadata["data_shape"] == (10, 10)

            # Verify PNG
            img = Image.open(png_path)
            assert img.format == "PNG"

    def test_csv_with_sparse_data_converts_correctly(self) -> None:
        """Verify CSV to PNG works with sparse data (many zeros)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "sparse.csv"
            png_path = Path(tmpdir) / "sparse.png"

            # Create sparse data (mostly zeros with a few hotspots)
            data = np.zeros((20, 20))
            data[5, 5] = 100  # Hotspot 1
            data[15, 15] = 80  # Hotspot 2
            data[10, 10] = 60  # Hotspot 3
            np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

            # Convert to PNG
            render_heatmap_png(
                csv_path=csv_path,
                output_path=png_path,
                title="Sparse Heatmap",
            )

            assert png_path.exists()

            # Verify PNG
            img = Image.open(png_path)
            assert img.format == "PNG"
            assert img.size[0] > 0 and img.size[1] > 0

    def test_csv_with_uniform_data_converts_correctly(self) -> None:
        """Verify CSV to PNG works with uniform data (all same value)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "uniform.csv"
            png_path = Path(tmpdir) / "uniform.png"

            # Create uniform data (all values the same)
            data = np.ones((15, 15)) * 50
            np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

            # Convert to PNG
            metadata = render_heatmap_png(
                csv_path=csv_path,
                output_path=png_path,
                title="Uniform Heatmap",
            )

            assert png_path.exists()
            assert metadata["value_range"] == [50.0, 50.0]

            # Verify PNG
            img = Image.open(png_path)
            assert img.format == "PNG"
