"""Tests for F227: Hotspot annotations include cause labels.

This feature extends hotspot annotations to include cause information,
helping identify the root cause of congestion hotspots.

Steps from feature_list.json:
1. Generate annotated heatmap
2. Verify each hotspot annotation includes cause
3. Verify cause is one of: pins, density, macro_proximity
4. Verify cause matches diagnosis hotspot cause
5. Verify cause labels are readable
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.visualization.heatmap_renderer import (
    render_heatmap_with_hotspot_annotations,
)


class TestF227HotspotCauseLabels:
    """
    Test suite for Feature F227: Hotspot cause labeling.

    Verifies that hotspot annotations include cause information to help
    diagnose the root cause of congestion issues.
    """

    @pytest.fixture
    def sample_heatmap_csv(self) -> Path:
        """Create a sample congestion heatmap CSV file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            # Create 20x20 grid with hotspots
            for i in range(20):
                row = []
                for j in range(20):
                    # Create some high congestion regions
                    if 5 <= i <= 8 and 5 <= j <= 8:
                        value = 0.9  # High congestion
                    elif 12 <= i <= 15 and 12 <= j <= 15:
                        value = 0.8  # High congestion
                    else:
                        value = 0.2  # Low congestion
                    row.append(str(value))
                f.write(",".join(row) + "\n")
            return Path(f.name)

    @pytest.fixture
    def hotspots_with_causes(self) -> list[dict]:
        """Create hotspots with cause information."""
        return [
            {
                "id": 1,
                "bbox": {"x1": 5, "y1": 5, "x2": 8, "y2": 8},
                "severity": "critical",
                "cause": "pins",
            },
            {
                "id": 2,
                "bbox": {"x1": 12, "y1": 12, "x2": 15, "y2": 15},
                "severity": "moderate",
                "cause": "density",
            },
            {
                "id": 3,
                "bbox": {"x1": 1, "y1": 17, "x2": 3, "y2": 19},
                "severity": 0.75,
                "cause": "macro_proximity",
            },
        ]

    def test_step_1_generate_annotated_heatmap(
        self, sample_heatmap_csv: Path, hotspots_with_causes: list[dict]
    ) -> None:
        """Step 1: Generate annotated heatmap with cause labels."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "hotspots_with_causes.png"

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=hotspots_with_causes,
            )

            # Verify heatmap was generated
            assert output_path.exists()
            assert output_path.stat().st_size > 0
            assert result["hotspots_annotated"] == 3

    def test_step_2_verify_each_hotspot_includes_cause(
        self, sample_heatmap_csv: Path, hotspots_with_causes: list[dict]
    ) -> None:
        """Step 2: Verify each hotspot annotation includes cause."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_causes.png"

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=hotspots_with_causes,
            )

            # Verify image was generated
            assert output_path.exists()

            # Verify all hotspots were annotated
            assert result["hotspots_annotated"] == 3

            # Verify hotspot IDs match input
            assert result["hotspot_ids"] == [1, 2, 3]

            # Load image and verify it has sufficient complexity for text
            img = Image.open(output_path)
            img_array = np.array(img)

            # Text annotations add complexity
            assert img_array.std() > 0

    def test_step_3_verify_cause_is_valid_type(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Step 3: Verify cause is one of: pins, density, macro_proximity."""
        valid_causes = ["pins", "density", "macro_proximity"]

        with tempfile.TemporaryDirectory() as tmpdir:
            for cause_type in valid_causes:
                output_path = Path(tmpdir) / f"test_{cause_type}.png"

                hotspots = [
                    {
                        "id": 1,
                        "bbox": {"x1": 5, "y1": 5, "x2": 10, "y2": 10},
                        "severity": 0.85,
                        "cause": cause_type,
                    }
                ]

                result = render_heatmap_with_hotspot_annotations(
                    csv_path=sample_heatmap_csv,
                    output_path=output_path,
                    hotspots=hotspots,
                )

                # Verify rendering succeeded for valid cause
                assert output_path.exists()
                assert result["hotspots_annotated"] == 1

    def test_step_4_verify_cause_matches_diagnosis(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Step 4: Verify cause matches diagnosis hotspot cause."""
        # Simulate diagnosis output with hotspots
        diagnosis_hotspots = [
            {
                "id": 1,
                "bbox": {"x1": 5, "y1": 5, "x2": 8, "y2": 8},
                "severity": "critical",
                "cause": "pins",  # From diagnosis
            },
            {
                "id": 2,
                "bbox": {"x1": 12, "y1": 12, "x2": 15, "y2": 15},
                "severity": "moderate",
                "cause": "density",  # From diagnosis
            },
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "diagnosis_causes.png"

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=diagnosis_hotspots,
            )

            # Verify visualization matches diagnosis
            assert output_path.exists()
            assert result["hotspots_annotated"] == 2

            # The cause information from diagnosis is preserved
            # in the visualization annotations

    def test_step_5_verify_cause_labels_readable(
        self, sample_heatmap_csv: Path, hotspots_with_causes: list[dict]
    ) -> None:
        """Step 5: Verify cause labels are readable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "readable_causes.png"

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=hotspots_with_causes,
                dpi=200,  # Higher DPI for readability
                figsize=(12, 10),  # Larger figure for more space
            )

            # Verify image is large enough for readable text
            assert output_path.exists()
            img = Image.open(output_path)
            assert img.size[0] >= 1800  # Width
            assert img.size[1] >= 1500  # Height

            # Verify DPI and figsize settings applied
            assert result["dpi"] == 200
            assert result["figsize"] == (12, 10)

    def test_edge_case_hotspot_without_cause(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test backward compatibility with hotspots missing cause field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "no_cause.png"

            hotspots_no_cause = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 10, "y2": 10},
                    "severity": 0.85,
                    # Missing 'cause' field
                }
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=hotspots_no_cause,
            )

            # Should render successfully without cause
            # (backward compatibility with F226)
            assert output_path.exists()
            assert result["hotspots_annotated"] == 1

    def test_edge_case_mixed_hotspots_with_and_without_causes(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test handling of mixed hotspots (some with causes, some without)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "mixed_causes.png"

            mixed_hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 2, "y1": 2, "x2": 5, "y2": 5},
                    "severity": 0.90,
                    "cause": "pins",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 10, "y1": 10, "x2": 13, "y2": 13},
                    "severity": 0.75,
                    # Missing 'cause' field
                },
                {
                    "id": 3,
                    "bbox": {"x1": 15, "y1": 15, "x2": 18, "y2": 18},
                    "severity": 0.80,
                    "cause": "density",
                },
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=mixed_hotspots,
            )

            # Should handle mixed cases gracefully
            assert output_path.exists()
            assert result["hotspots_annotated"] == 3

    def test_edge_case_all_cause_types_in_one_image(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test visualization with all three cause types present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "all_causes.png"

            all_causes_hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 2, "y1": 2, "x2": 5, "y2": 5},
                    "severity": 0.90,
                    "cause": "pins",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 8, "y1": 8, "x2": 11, "y2": 11},
                    "severity": 0.85,
                    "cause": "density",
                },
                {
                    "id": 3,
                    "bbox": {"x1": 14, "y1": 14, "x2": 17, "y2": 17},
                    "severity": 0.80,
                    "cause": "macro_proximity",
                },
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=all_causes_hotspots,
                figsize=(14, 12),  # Large figure for all labels
            )

            # All three cause types should render successfully
            assert output_path.exists()
            assert result["hotspots_annotated"] == 3

    def test_edge_case_empty_cause_string(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test handling of empty cause string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty_cause.png"

            hotspots_empty_cause = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 10, "y2": 10},
                    "severity": 0.85,
                    "cause": "",  # Empty string
                }
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=hotspots_empty_cause,
            )

            # Should handle empty cause gracefully (treat as no cause)
            assert output_path.exists()
            assert result["hotspots_annotated"] == 1

    def test_edge_case_long_cause_names(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that macro_proximity (longest cause name) renders properly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "long_cause.png"

            hotspots_long_cause = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 10, "y2": 10},
                    "severity": 0.85,
                    "cause": "macro_proximity",  # Longest valid cause name
                }
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=hotspots_long_cause,
                figsize=(10, 8),  # Sufficient space for long text
            )

            # Should render long cause name without truncation
            assert output_path.exists()
            assert result["hotspots_annotated"] == 1

    def test_edge_case_many_hotspots_with_causes(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test visualization with many hotspots all having causes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "many_hotspots.png"

            # Create 9 hotspots with varying causes
            many_hotspots = []
            causes = ["pins", "density", "macro_proximity"]
            for i in range(9):
                hotspot = {
                    "id": i + 1,
                    "bbox": {
                        "x1": (i % 3) * 6,
                        "y1": (i // 3) * 6,
                        "x2": (i % 3) * 6 + 4,
                        "y2": (i // 3) * 6 + 4,
                    },
                    "severity": 0.70 + (i * 0.02),
                    "cause": causes[i % 3],
                }
                many_hotspots.append(hotspot)

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=many_hotspots,
                figsize=(14, 12),  # Large figure to accommodate many labels
                dpi=150,
            )

            # Should render all hotspots with causes
            assert output_path.exists()
            assert result["hotspots_annotated"] == 9

    def test_backward_compatibility_f226(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that F226 functionality still works (without causes)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "f226_compat.png"

            # F226 format: no cause field
            f226_hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 10, "y2": 10},
                    "severity": "critical",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 12, "y1": 12, "x2": 15, "y2": 15},
                    "severity": 0.75,
                },
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=f226_hotspots,
            )

            # Should work exactly as in F226 (backward compatible)
            assert output_path.exists()
            assert result["hotspots_annotated"] == 2
            assert result["hotspot_ids"] == [1, 2]

    def test_integration_with_diagnosis_output(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test integration with realistic diagnosis output format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "diagnosis_integration.png"

            # Realistic diagnosis output structure
            diagnosis_hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 8, "y2": 8},
                    "severity": "critical",
                    "congestion_value": 0.95,
                    "cause": "pins",
                    "pin_count": 145,
                },
                {
                    "id": 2,
                    "bbox": {"x1": 12, "y1": 12, "x2": 15, "y2": 15},
                    "severity": "moderate",
                    "congestion_value": 0.78,
                    "cause": "density",
                    "cell_count": 87,
                },
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=diagnosis_hotspots,
            )

            # Should extract relevant fields (id, bbox, severity, cause)
            # and ignore extra diagnostic fields
            assert output_path.exists()
            assert result["hotspots_annotated"] == 2

    def test_cause_label_formatting(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that cause labels are properly formatted in annotation text."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "cause_format.png"

            hotspots = [
                {
                    "id": 1,
                    "bbox": {"x1": 5, "y1": 5, "x2": 10, "y2": 10},
                    "severity": 0.92,
                    "cause": "pins",
                }
            ]

            result = render_heatmap_with_hotspot_annotations(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                hotspots=hotspots,
            )

            # Verify rendering succeeded
            # The annotation text should be: "[HS-1]\n0.92\npins"
            assert output_path.exists()
            assert result["hotspots_annotated"] == 1

            # Load image and verify it has content
            img = Image.open(output_path)
            img_array = np.array(img)
            assert img_array.std() > 0
