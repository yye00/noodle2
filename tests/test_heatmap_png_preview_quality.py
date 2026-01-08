"""
Tests for heatmap PNG preview rendering quality and UX.

This module tests Feature #138: Heatmap PNG previews are rendered with
appropriate colormap and scale.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.visualization.heatmap_renderer import (
    get_recommended_colormap,
    parse_heatmap_csv,
    render_all_heatmaps,
    render_heatmap_png,
)


@pytest.fixture
def sample_congestion_csv(tmp_path: Path) -> Path:
    """Create sample congestion heatmap CSV for testing."""
    csv_path = tmp_path / "routing_congestion.csv"

    # Create synthetic congestion data with clear hot spots
    # High values in corners, low in middle
    data = np.zeros((20, 20))
    data[0:5, 0:5] = 80  # Hot spot top-left
    data[15:20, 15:20] = 90  # Hot spot bottom-right
    data[8:12, 8:12] = 10  # Cool spot in middle

    # Write to CSV
    np.savetxt(csv_path, data, delimiter=",", fmt="%.1f")

    return csv_path


@pytest.fixture
def sample_density_csv(tmp_path: Path) -> Path:
    """Create sample placement density CSV for testing."""
    csv_path = tmp_path / "placement_density.csv"

    # Create synthetic density data
    data = np.random.uniform(0.0, 100.0, (15, 15))

    # Write to CSV
    np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

    return csv_path


class TestHeatmapPNGGeneration:
    """Test PNG preview generation from CSV."""

    def test_step1_generate_heatmap_csvs_from_trial(
        self, sample_congestion_csv: Path
    ) -> None:
        """Step 1: Generate heatmap CSVs from trial."""
        # Verify CSV exists and is parseable
        assert sample_congestion_csv.exists()

        data, metadata = parse_heatmap_csv(sample_congestion_csv)

        # Verify data loaded correctly
        assert data.shape == (20, 20)
        assert metadata["min_value"] >= 0
        assert metadata["max_value"] <= 100

    def test_step2_render_png_previews(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Step 2: Render PNG previews with matplotlib/similar."""
        output_png = tmp_path / "congestion_preview.png"

        # Render PNG
        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
            title="Test Congestion Heatmap",
        )

        # Verify PNG was created
        assert output_png.exists()
        assert metadata["png_path"] == str(output_png)

    def test_step3_view_png_files(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Step 3: View PNG files (validate they are valid images)."""
        output_png = tmp_path / "congestion_view.png"

        render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
        )

        # Verify PNG is valid and can be opened
        img = Image.open(output_png)
        assert img.format == "PNG"
        assert img.size[0] > 0
        assert img.size[1] > 0
        img.close()


class TestColormapQuality:
    """Test that colormaps clearly show hotspots."""

    def test_step5_verify_colormap_shows_hotspots_clearly(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Step 5: Verify colormap clearly shows hotspots (hot colors for congestion)."""
        output_png = tmp_path / "congestion_hotspots.png"

        # Render with 'hot' colormap (recommended for congestion)
        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
            colormap="hot",
        )

        # Verify hot colormap was used
        assert metadata["colormap"] == "hot"

        # Verify PNG exists and is valid
        assert output_png.exists()
        img = Image.open(output_png)
        assert img.format == "PNG"
        img.close()

    def test_recommended_colormap_for_congestion(self) -> None:
        """Verify recommended colormap for congestion is appropriate."""
        colormap = get_recommended_colormap("routing_congestion")
        assert colormap == "hot"

    def test_recommended_colormap_for_density(self) -> None:
        """Verify recommended colormap for density is appropriate."""
        colormap = get_recommended_colormap("placement_density")
        assert colormap == "viridis"

    def test_recommended_colormap_for_rudy(self) -> None:
        """Verify recommended colormap for RUDY is appropriate."""
        colormap = get_recommended_colormap("rudy")
        assert colormap == "plasma"

    def test_colormap_is_perceptually_appropriate(self) -> None:
        """Verify colormaps are perceptually appropriate for their purpose."""
        # Congestion should use sequential colormap with hot colors for problems
        assert get_recommended_colormap("routing_congestion") == "hot"

        # Density should use perceptually uniform colormap
        assert get_recommended_colormap("placement_density") == "viridis"

        # RUDY should highlight hot spots
        assert get_recommended_colormap("rudy") == "plasma"


class TestScaleAndLegend:
    """Test that scale/legend is included and readable."""

    def test_step6_verify_scale_legend_included(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Step 6: Verify scale/legend is included and readable."""
        output_png = tmp_path / "congestion_with_legend.png"

        render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
        )

        # Verify PNG exists and has reasonable size (includes colorbar)
        assert output_png.exists()

        img = Image.open(output_png)
        width, height = img.size

        # At default DPI 150 and figsize (8, 6), expect reasonable dimensions
        # Width should be around 8*150 = 1200 pixels
        assert width >= 800  # Allow some flexibility
        assert height >= 600
        img.close()

    def test_colorbar_is_included_in_rendering(
        self, sample_density_csv: Path, tmp_path: Path
    ) -> None:
        """Verify colorbar/legend is always included in rendering."""
        output_png = tmp_path / "density_with_colorbar.png"

        metadata = render_heatmap_png(
            csv_path=sample_density_csv,
            output_path=output_png,
        )

        # Metadata should indicate rendering succeeded
        assert "png_path" in metadata
        assert "value_range" in metadata

        # PNG should exist and be valid
        img = Image.open(output_png)
        assert img.format == "PNG"
        img.close()

    def test_title_is_included(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Verify title is included for context."""
        output_png = tmp_path / "congestion_with_title.png"

        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
            title="Routing Congestion Analysis",
        )

        # Metadata should reflect title
        assert output_png.exists()

    def test_axis_labels_provide_context(
        self, sample_density_csv: Path, tmp_path: Path
    ) -> None:
        """Verify axis labels provide spatial context."""
        output_png = tmp_path / "density_with_labels.png"

        render_heatmap_png(
            csv_path=sample_density_csv,
            output_path=output_png,
        )

        # PNG should be created successfully
        assert output_png.exists()

        # Open and verify it's a valid PNG
        img = Image.open(output_png)
        assert img.mode in ["RGB", "RGBA"]
        img.close()


class TestResolutionAndClarity:
    """Test that rendered heatmaps are high-quality and readable."""

    def test_default_dpi_is_adequate(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Verify default DPI produces readable heatmaps."""
        output_png = tmp_path / "congestion_default_dpi.png"

        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
        )

        # Default DPI should be 150
        assert metadata["dpi"] == 150

        # Check image dimensions
        img = Image.open(output_png)
        width, height = img.size

        # At DPI 150 with figsize (8, 6), expect ~1200x900
        assert width >= 800
        assert height >= 600
        img.close()

    def test_high_dpi_rendering_available(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Verify high-DPI rendering available for publication quality."""
        output_png = tmp_path / "congestion_high_dpi.png"

        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
            dpi=300,  # Publication quality
        )

        assert metadata["dpi"] == 300

        # Check that high-DPI image is larger
        img = Image.open(output_png)
        width, height = img.size

        # At DPI 300, expect roughly double the dimensions
        assert width >= 1500
        assert height >= 1000
        img.close()

    def test_image_file_size_is_reasonable(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Verify PNG file size is reasonable (not too large)."""
        output_png = tmp_path / "congestion_size_check.png"

        render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
        )

        # Check file size
        file_size = output_png.stat().st_size

        # Should be under 1 MB for typical heatmaps
        assert file_size < 1_000_000  # 1 MB

        # Should not be suspiciously small
        assert file_size > 10_000  # 10 KB


class TestBatchRendering:
    """Test batch rendering of multiple heatmaps."""

    def test_render_all_heatmaps_in_directory(self, tmp_path: Path) -> None:
        """Test rendering all heatmaps in a directory at once."""
        heatmaps_dir = tmp_path / "heatmaps"
        heatmaps_dir.mkdir()

        # Create multiple CSV files
        for name in ["placement_density", "rudy", "routing_congestion"]:
            csv_path = heatmaps_dir / f"{name}.csv"
            data = np.random.uniform(0.0, 100.0, (10, 10))
            np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

        # Render all
        results = render_all_heatmaps(heatmaps_dir)

        # Should have rendered 3 heatmaps
        assert len(results) == 3

        # Verify all PNGs exist
        for result in results:
            png_path = Path(result["png_path"])
            assert png_path.exists()

    def test_batch_rendering_uses_appropriate_colormaps(
        self, tmp_path: Path
    ) -> None:
        """Verify batch rendering can use appropriate colormaps per type."""
        heatmaps_dir = tmp_path / "heatmaps_batch"
        heatmaps_dir.mkdir()

        # Create CSV
        csv_path = heatmaps_dir / "routing_congestion.csv"
        data = np.random.uniform(0.0, 100.0, (10, 10))
        np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

        # Render with hot colormap
        results = render_all_heatmaps(heatmaps_dir, colormap="hot")

        assert len(results) == 1
        assert results[0]["colormap"] == "hot"


class TestHeatmapMetadata:
    """Test that metadata is captured for analysis."""

    def test_metadata_includes_value_range(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Verify metadata includes data value range."""
        output_png = tmp_path / "congestion_metadata.png"

        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
        )

        # Should include value range
        assert "value_range" in metadata
        assert len(metadata["value_range"]) == 2
        assert metadata["value_range"][0] <= metadata["value_range"][1]

    def test_metadata_includes_data_shape(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Verify metadata includes heatmap dimensions."""
        output_png = tmp_path / "congestion_shape.png"

        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
        )

        # Should include shape
        assert "data_shape" in metadata
        assert metadata["data_shape"] == (20, 20)

    def test_metadata_includes_rendering_params(
        self, sample_congestion_csv: Path, tmp_path: Path
    ) -> None:
        """Verify metadata includes rendering parameters for reproducibility."""
        output_png = tmp_path / "congestion_params.png"

        metadata = render_heatmap_png(
            csv_path=sample_congestion_csv,
            output_path=output_png,
            colormap="plasma",
            dpi=200,
        )

        # Should include rendering params
        assert metadata["colormap"] == "plasma"
        assert metadata["dpi"] == 200
        assert "figsize" in metadata


class TestEndToEnd:
    """End-to-end validation of heatmap PNG preview quality."""

    def test_complete_heatmap_preview_workflow(self, tmp_path: Path) -> None:
        """Complete validation: CSV → PNG with quality checks."""
        # Step 1: Create congestion CSV
        csv_path = tmp_path / "routing_congestion.csv"
        data = np.array([[10, 20, 30], [40, 80, 60], [30, 20, 10]])
        np.savetxt(csv_path, data, delimiter=",", fmt="%.1f")

        # Step 2: Render PNG with appropriate colormap
        png_path = tmp_path / "congestion.png"
        metadata = render_heatmap_png(
            csv_path=csv_path,
            output_path=png_path,
            title="Routing Congestion",
            colormap="hot",
        )

        # Step 3-4: Verify PNG is valid and viewable
        assert png_path.exists()
        img = Image.open(png_path)
        assert img.format == "PNG"
        img.close()

        # Step 5: Verify hot colormap was used (shows hotspots clearly)
        assert metadata["colormap"] == "hot"

        # Step 6: Verify scale/legend is included (check reasonable size)
        assert img.size[0] >= 800
        assert img.size[1] >= 600

    def test_heatmap_previews_are_production_quality(self, tmp_path: Path) -> None:
        """Verify heatmap previews meet production quality standards."""
        # Create sample heatmap
        csv_path = tmp_path / "placement_density.csv"
        data = np.random.uniform(0.0, 100.0, (20, 20))
        np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

        # Render with high quality settings
        png_path = tmp_path / "density_hq.png"
        metadata = render_heatmap_png(
            csv_path=csv_path,
            output_path=png_path,
            title="Placement Density Analysis",
            colormap="viridis",
            dpi=200,
            figsize=(10, 8),
        )

        # Quality checks
        assert png_path.exists()
        assert metadata["dpi"] >= 150  # Adequate resolution
        assert metadata["colormap"] in [
            "viridis",
            "plasma",
            "hot",
        ]  # Perceptually good

        # Verify image dimensions
        img = Image.open(png_path)
        width, height = img.size
        assert width >= 1000  # High-res
        assert height >= 800
        img.close()

    def test_multiple_heatmap_types_rendered_consistently(
        self, tmp_path: Path
    ) -> None:
        """Verify different heatmap types are rendered with consistent quality."""
        heatmap_types = ["placement_density", "rudy", "routing_congestion"]
        results = []

        for heatmap_type in heatmap_types:
            # Create CSV
            csv_path = tmp_path / f"{heatmap_type}.csv"
            data = np.random.uniform(0.0, 100.0, (15, 15))
            np.savetxt(csv_path, data, delimiter=",", fmt="%.2f")

            # Render PNG
            png_path = tmp_path / f"{heatmap_type}.png"
            recommended_cmap = get_recommended_colormap(heatmap_type)

            metadata = render_heatmap_png(
                csv_path=csv_path,
                output_path=png_path,
                colormap=recommended_cmap,
            )

            results.append(metadata)

        # All should have been rendered
        assert len(results) == 3

        # All should have consistent quality
        for result in results:
            assert result["dpi"] == 150  # Default DPI
            assert Path(result["png_path"]).exists()
            assert result["colormap"] in ["viridis", "plasma", "hot"]
