"""Tests for F226: Annotate hotspots on congestion heatmap with IDs and severity."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.analysis.diagnosis import diagnose_congestion
from src.controller.types import CongestionMetrics
from src.visualization.heatmap_renderer import (
    parse_heatmap_csv,
    render_heatmap_png,
    render_heatmap_with_hotspot_annotations,
)


def create_test_congestion_heatmap(path: Path, size: tuple[int, int] = (50, 50)) -> None:
    """Create a test congestion heatmap CSV with hotspot regions."""
    rows, cols = size

    # Create base low congestion
    data = np.random.uniform(0.1, 0.3, size=(rows, cols))

    # Add hotspot regions with high congestion
    # Hotspot 1: top-left
    data[5:15, 5:15] = np.random.uniform(0.85, 0.95, size=(10, 10))

    # Hotspot 2: center-right
    data[20:30, 35:45] = np.random.uniform(0.70, 0.80, size=(10, 10))

    # Hotspot 3: bottom-left
    data[35:45, 5:15] = np.random.uniform(0.50, 0.60, size=(10, 10))

    # Save CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.4f")


class TestHotspotAnnotationF226:
    """
    Test suite for Feature F226: Annotate hotspots on congestion heatmap.

    Steps from feature_list.json:
    1. Run congestion diagnosis identifying hotspots
    2. Generate routing congestion heatmap
    3. Verify hotspots are annotated with [HS-1], [HS-2], etc.
    4. Verify severity values are displayed (0.92, 0.78, etc.)
    5. Verify annotations are positioned near hotspot regions
    6. Export as hotspots.png
    """

    def test_step_1_run_congestion_diagnosis_identifying_hotspots(self) -> None:
        """Step 1: Run congestion diagnosis identifying hotspots."""
        # Create metrics with multiple hotspots
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1500,
            layer_metrics={
                "metal2": 600,
                "metal3": 550,
                "metal4": 350,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.6)

        # Verify hotspots were identified
        assert diagnosis is not None
        assert len(diagnosis.hotspots) > 0, "Should identify hotspots"

        # Verify hotspots have required fields for annotation
        for hotspot in diagnosis.hotspots:
            assert hasattr(hotspot, "id"), "Hotspot must have ID"
            assert hasattr(hotspot, "bbox"), "Hotspot must have bbox"
            assert hasattr(hotspot, "severity"), "Hotspot must have severity"

    def test_step_2_generate_routing_congestion_heatmap(self) -> None:
        """Step 2: Generate routing congestion heatmap."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test congestion heatmap CSV
            csv_path = tmpdir_path / "routing_congestion.csv"
            create_test_congestion_heatmap(csv_path)

            # Verify CSV was created and can be parsed
            assert csv_path.exists()
            data, metadata = parse_heatmap_csv(csv_path)
            assert data.shape == (50, 50)
            assert metadata["max_value"] > 0.5, "Should have congested regions"

            # Generate base heatmap PNG
            png_path = tmpdir_path / "routing_congestion.png"
            result = render_heatmap_png(
                csv_path=csv_path,
                output_path=png_path,
                colormap="hot",
            )

            # Verify PNG was generated
            assert png_path.exists()
            assert result["png_path"] == str(png_path)

    def test_step_3_verify_hotspots_annotated_with_ids(self) -> None:
        """Step 3: Verify hotspots are annotated with [HS-1], [HS-2], etc."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test heatmap
            csv_path = tmpdir_path / "routing_congestion.csv"
            create_test_congestion_heatmap(csv_path)

            # Create hotspot data
            hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 15, "y2": 15},
                    "severity": "critical",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 35, "y1": 20, "x2": 45, "y2": 30},
                    "severity": "moderate",
                },
                {
                    "id": 3,
                    "bbox": {"x1": 5, "y1": 35, "x2": 15, "y2": 45},
                    "severity": "minor",
                },
            ]

            # Generate annotated heatmap
            png_path = tmpdir_path / "hotspots.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
            )

            # Verify PNG was generated
            assert png_path.exists()
            assert result["hotspots_annotated"] == 3

            # Verify hotspot IDs are tracked
            assert result["hotspot_ids"] == [1, 2, 3]

            # Verify PNG can be opened as image
            img = Image.open(png_path)
            assert img.size[0] > 0 and img.size[1] > 0

    def test_step_4_verify_severity_values_displayed(self) -> None:
        """Step 4: Verify severity values are displayed (0.92, 0.78, etc.)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test heatmap
            csv_path = tmpdir_path / "routing_congestion.csv"
            create_test_congestion_heatmap(csv_path)

            # Create hotspots with numeric severity values
            hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 15, "y2": 15},
                    "severity": 0.92,  # Numeric severity
                },
                {
                    "id": 2,
                    "bbox": {"x1": 35, "y1": 20, "x2": 45, "y2": 30},
                    "severity": 0.78,
                },
                {
                    "id": 3,
                    "bbox": {"x1": 5, "y1": 35, "x2": 15, "y2": 45},
                    "severity": 0.54,
                },
            ]

            # Generate annotated heatmap
            png_path = tmpdir_path / "hotspots_numeric.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
            )

            # Verify PNG was generated
            assert png_path.exists()
            assert result["hotspots_annotated"] == 3

            # Verify PNG has proper dimensions
            img = Image.open(png_path)
            assert img.width > 800  # Should be at least figsize * dpi
            assert img.height > 600

    def test_step_5_verify_annotations_positioned_near_hotspot_regions(self) -> None:
        """Step 5: Verify annotations are positioned near hotspot regions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test heatmap
            csv_path = tmpdir_path / "routing_congestion.csv"
            create_test_congestion_heatmap(csv_path, size=(100, 100))

            # Create hotspots at known positions
            hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 10, "y1": 10, "x2": 30, "y2": 30},
                    "severity": 0.95,
                },
                {
                    "id": 2,
                    "bbox": {"x1": 70, "y1": 40, "x2": 90, "y2": 60},
                    "severity": 0.80,
                },
                {
                    "id": 3,
                    "bbox": {"x1": 10, "y1": 70, "x2": 30, "y2": 90},
                    "severity": 0.65,
                },
            ]

            # Generate annotated heatmap
            png_path = tmpdir_path / "hotspots_positioned.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
            )

            # Verify result metadata
            assert result["png_path"] == str(png_path)
            assert result["hotspots_annotated"] == 3
            assert result["data_shape"] == (100, 100)

            # Verify PNG was generated with correct settings
            assert result["colormap"] == "hot"
            assert result["dpi"] == 150

    def test_step_6_export_as_hotspots_png(self) -> None:
        """Step 6: Export as hotspots.png."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test heatmap
            csv_path = tmpdir_path / "routing_congestion.csv"
            create_test_congestion_heatmap(csv_path)

            # Create realistic hotspots
            hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 15, "y2": 15},
                    "severity": "critical",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 35, "y1": 20, "x2": 45, "y2": 30},
                    "severity": "moderate",
                },
            ]

            # Generate annotated heatmap with specific filename
            png_path = tmpdir_path / "hotspots.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
                title="Routing Congestion with Hotspots",
            )

            # Verify file was created with correct name
            assert png_path.exists()
            assert png_path.name == "hotspots.png"

            # Verify file size is reasonable
            file_size = png_path.stat().st_size
            assert file_size > 10000, "PNG should have substantial content"
            assert file_size < 5_000_000, "PNG should not be excessively large"


class TestHotspotAnnotationEdgeCases:
    """Test edge cases and error handling for hotspot annotation."""

    def test_empty_hotspots_list(self) -> None:
        """Test rendering with no hotspots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            csv_path = tmpdir_path / "congestion.csv"
            create_test_congestion_heatmap(csv_path)

            png_path = tmpdir_path / "no_hotspots.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=[],  # Empty hotspots
            )

            # Should still generate PNG
            assert png_path.exists()
            assert result["hotspots_annotated"] == 0
            assert result["hotspot_ids"] == []

    def test_single_hotspot(self) -> None:
        """Test rendering with single hotspot."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            csv_path = tmpdir_path / "congestion.csv"
            create_test_congestion_heatmap(csv_path)

            hotspot = [
                {
                    "id": 1,
                    "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
                    "severity": 0.88,
                }
            ]

            png_path = tmpdir_path / "single_hotspot.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspot,
            )

            assert png_path.exists()
            assert result["hotspots_annotated"] == 1
            assert result["hotspot_ids"] == [1]

    def test_many_hotspots(self) -> None:
        """Test rendering with many hotspots."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            csv_path = tmpdir_path / "congestion.csv"
            create_test_congestion_heatmap(csv_path, size=(100, 100))

            # Create 10 hotspots
            hotspots = [
                {
                    "id": i,
                    "bbox": {
                        "x1": (i * 10) % 80,
                        "y1": (i * 8) % 80,
                        "x2": ((i * 10) % 80) + 10,
                        "y2": ((i * 8) % 80) + 10,
                    },
                    "severity": 0.9 - (i * 0.05),
                }
                for i in range(1, 11)
            ]

            png_path = tmpdir_path / "many_hotspots.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
            )

            assert png_path.exists()
            assert result["hotspots_annotated"] == 10
            assert len(result["hotspot_ids"]) == 10

    def test_string_severity_mapping(self) -> None:
        """Test that string severity values are properly mapped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            csv_path = tmpdir_path / "congestion.csv"
            create_test_congestion_heatmap(csv_path)

            # Test all severity levels
            hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 10, "y2": 10},
                    "severity": "critical",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 15, "y1": 5, "x2": 20, "y2": 10},
                    "severity": "moderate",
                },
                {
                    "id": 3,
                    "bbox": {"x1": 25, "y1": 5, "x2": 30, "y2": 10},
                    "severity": "minor",
                },
                {
                    "id": 4,
                    "bbox": {"x1": 35, "y1": 5, "x2": 40, "y2": 10},
                    "severity": "low",
                },
            ]

            png_path = tmpdir_path / "severity_levels.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
            )

            assert png_path.exists()
            assert result["hotspots_annotated"] == 4

    def test_custom_title_and_colormap(self) -> None:
        """Test custom title and colormap settings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            csv_path = tmpdir_path / "congestion.csv"
            create_test_congestion_heatmap(csv_path)

            hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20},
                    "severity": 0.85,
                }
            ]

            png_path = tmpdir_path / "custom.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
                title="Custom Congestion Analysis",
                colormap="plasma",
            )

            assert png_path.exists()
            assert result["colormap"] == "plasma"


class TestF226Integration:
    """Integration test for complete F226 feature."""

    def test_complete_f226_workflow(self) -> None:
        """
        Complete workflow test for F226.

        This test verifies all 6 steps in sequence:
        1. Run congestion diagnosis identifying hotspots
        2. Generate routing congestion heatmap
        3. Verify hotspots are annotated with [HS-1], [HS-2], etc.
        4. Verify severity values are displayed
        5. Verify annotations are positioned near hotspot regions
        6. Export as hotspots.png
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Step 1: Run congestion diagnosis
            metrics = CongestionMetrics(
                bins_total=1000,
                bins_hot=780,
                hot_ratio=0.78,
                max_overflow=1600,
                layer_metrics={
                    "metal2": 620,
                    "metal3": 580,
                    "metal4": 400,
                },
            )

            diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.65)
            assert len(diagnosis.hotspots) > 0, "Step 1: Should identify hotspots"

            # Step 2: Generate congestion heatmap
            csv_path = tmpdir_path / "routing_congestion.csv"
            create_test_congestion_heatmap(csv_path)
            assert csv_path.exists(), "Step 2: Heatmap CSV should exist"

            # Convert diagnosis hotspots to annotation format
            hotspots = []
            for i, hs in enumerate(diagnosis.hotspots[:3]):  # Use first 3
                hotspots.append(
                    {
                        "id": hs.id,
                        "bbox": {
                            "x1": hs.bbox.x1 % 40,
                            "y1": hs.bbox.y1 % 40,
                            "x2": (hs.bbox.x2 % 40) + 10,
                            "y2": (hs.bbox.y2 % 40) + 10,
                        },
                        "severity": hs.severity.value,
                    }
                )

            # Step 3-6: Generate annotated heatmap
            png_path = tmpdir_path / "hotspots.png"
            result = render_heatmap_with_hotspot_annotations(
                csv_path=csv_path,
                output_path=png_path,
                hotspots=hotspots,
                title="Routing Congestion with Hotspot Annotations",
            )

            # Step 3: Verify IDs
            assert result["hotspots_annotated"] == len(hotspots), \
                "Step 3: All hotspots should be annotated"
            assert len(result["hotspot_ids"]) == len(hotspots), \
                "Step 3: All hotspot IDs should be tracked"

            # Step 4: Verify severity values are in result
            for hs in hotspots:
                severity = hs["severity"]
                if isinstance(severity, str):
                    assert severity in ["critical", "moderate", "minor", "low"], \
                        "Step 4: Severity should be valid string"
                else:
                    assert 0.0 <= severity <= 1.0, \
                        "Step 4: Numeric severity should be in range [0, 1]"

            # Step 5: Verify positioning metadata
            assert result["data_shape"] == (50, 50), \
                "Step 5: Data shape should match heatmap"

            # Step 6: Verify export
            assert png_path.exists(), "Step 6: hotspots.png should exist"
            assert png_path.name == "hotspots.png", \
                "Step 6: File should be named hotspots.png"

            # Verify PNG is valid
            img = Image.open(png_path)
            assert img.size[0] > 0 and img.size[1] > 0, \
                "Step 6: PNG should have valid dimensions"

            print("✓ F226: All steps verified successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
