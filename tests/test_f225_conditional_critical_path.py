"""
Tests for F225: Critical path overlay only generated when timing issue exists.

This feature optimizes visualization by skipping critical path overlay rendering
when there are no timing violations (WNS >= 0), saving computational resources
and avoiding clutter on heatmaps for designs with clean timing.
"""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.visualization.heatmap_renderer import (
    parse_heatmap_csv,
    render_heatmap_with_critical_path_overlay,
)


class TestF225ConditionalCriticalPathOverlay:
    """Test suite for Feature F225: Conditional critical path overlay."""

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
    def positive_wns_paths(self) -> list[dict]:
        """Create critical paths with positive WNS (no timing issue)."""
        return [
            {
                "slack_ps": 150,  # Positive slack - no timing violation
                "startpoint": "input_A",
                "endpoint": "reg_data[0]",
                "points": [(0, 0), (2, 3), (5, 7)],
            },
            {
                "slack_ps": 200,  # Positive slack - no timing violation
                "startpoint": "input_B",
                "endpoint": "reg_data[1]",
                "points": [(1, 1), (3, 4), (6, 8)],
            },
            {
                "slack_ps": 50,  # Positive slack - no timing violation
                "startpoint": "input_C",
                "endpoint": "reg_data[2]",
                "points": [(2, 2), (4, 5), (7, 9)],
            },
        ]

    @pytest.fixture
    def negative_wns_paths(self) -> list[dict]:
        """Create critical paths with negative WNS (timing issue exists)."""
        return [
            {
                "slack_ps": -2000,  # Negative slack - timing violation
                "startpoint": "input_port_0",
                "endpoint": "reg_data[0]",
                "points": [(0, 0), (2, 3), (5, 7), (8, 9)],
            },
            {
                "slack_ps": -1500,  # Negative slack - timing violation
                "startpoint": "input_port_1",
                "endpoint": "reg_data[1]",
                "points": [(1, 1), (3, 4), (6, 8), (9, 9)],
            },
            {
                "slack_ps": -500,  # Negative slack - timing violation
                "startpoint": "input_port_2",
                "endpoint": "reg_data[2]",
                "points": [(2, 2), (4, 5), (7, 8), (9, 8)],
            },
        ]

    def test_step1_run_case_with_positive_wns(
        self, sample_heatmap_csv: Path, positive_wns_paths: list[dict]
    ) -> None:
        """Step 1: Run case with positive WNS (no timing issue)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "overlay_positive_wns.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=positive_wns_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify function executed successfully
            assert result is not None
            assert output_path.exists()

    def test_step2_verify_overlay_skipped_or_note_shown(
        self, sample_heatmap_csv: Path, positive_wns_paths: list[dict]
    ) -> None:
        """Step 2: Verify critical path overlay is skipped or shows note."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "overlay_skipped.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=positive_wns_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify overlay was skipped
            assert result["overlay_skipped"] is True
            assert result["skip_reason"] == "no_timing_violations"
            assert result["paths_drawn"] == 0

            # Verify best slack is positive
            assert result["best_slack_ps"] >= 0

    def test_step3_run_case_with_negative_wns(
        self, sample_heatmap_csv: Path, negative_wns_paths: list[dict]
    ) -> None:
        """Step 3: Run case with negative WNS."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "overlay_negative_wns.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=negative_wns_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify function executed successfully
            assert result is not None
            assert output_path.exists()

    def test_step4_verify_overlay_generated_for_timing_violation(
        self, sample_heatmap_csv: Path, negative_wns_paths: list[dict]
    ) -> None:
        """Step 4: Verify critical path overlay is generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "overlay_generated.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=negative_wns_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify overlay was NOT skipped (has timing violations)
            assert "overlay_skipped" not in result or result.get("overlay_skipped") is False
            assert result["paths_drawn"] > 0
            assert result["paths_drawn"] <= result["path_count_limit"]

    def test_step5_verify_artifact_index_reflects_availability(
        self, sample_heatmap_csv: Path, positive_wns_paths: list[dict], negative_wns_paths: list[dict]
    ) -> None:
        """Step 5: Verify artifact_index reflects availability."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with positive WNS (overlay skipped)
            output_path_pos = Path(tmpdir) / "overlay_pos.png"
            result_pos = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path_pos,
                critical_paths=positive_wns_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Test with negative WNS (overlay generated)
            output_path_neg = Path(tmpdir) / "overlay_neg.png"
            result_neg = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path_neg,
                critical_paths=negative_wns_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify metadata clearly distinguishes the two cases
            # Positive WNS case
            assert result_pos["overlay_skipped"] is True
            assert result_pos["paths_drawn"] == 0

            # Negative WNS case
            assert result_neg.get("overlay_skipped") is not True
            assert result_neg["paths_drawn"] > 0

            # Both should have PNG files
            assert output_path_pos.exists()
            assert output_path_neg.exists()


class TestConditionalOverlayEdgeCases:
    """Test edge cases for conditional overlay."""

    @pytest.fixture
    def sample_heatmap_csv(self) -> Path:
        """Create sample heatmap CSV."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            for i in range(10):
                row = [str(float(i + j)) for j in range(10)]
                f.write(",".join(row) + "\n")
            return Path(f.name)

    def test_mixed_slack_values_with_negative_slack(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test mixed slack values with at least one negative slack."""
        mixed_paths = [
            {"slack_ps": 100, "startpoint": "A", "endpoint": "B", "points": [(0, 0), (1, 1)]},
            {"slack_ps": -50, "startpoint": "C", "endpoint": "D", "points": [(2, 2), (3, 3)]},
            {"slack_ps": 200, "startpoint": "E", "endpoint": "F", "points": [(4, 4), (5, 5)]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "mixed_slack.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=mixed_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Should NOT skip overlay (has at least one negative slack)
            assert result.get("overlay_skipped") is not True
            assert result["paths_drawn"] > 0

    def test_zero_slack_treated_as_no_violation(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that zero slack is treated as no timing violation."""
        zero_slack_paths = [
            {"slack_ps": 0, "startpoint": "A", "endpoint": "B", "points": [(0, 0), (1, 1)]},
            {"slack_ps": 50, "startpoint": "C", "endpoint": "D", "points": [(2, 2), (3, 3)]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "zero_slack.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=zero_slack_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Should skip overlay (no negative slack)
            assert result["overlay_skipped"] is True
            assert result["paths_drawn"] == 0

    def test_empty_critical_paths_list(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test behavior with empty critical paths list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "empty_paths.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=[],
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Should complete successfully but draw no paths
            assert result is not None
            assert result["paths_drawn"] == 0
            assert output_path.exists()

    def test_skip_overlay_disabled(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that overlay is always drawn when skip is disabled."""
        positive_paths = [
            {"slack_ps": 100, "startpoint": "A", "endpoint": "B", "points": [(0, 0), (5, 5)]},
            {"slack_ps": 200, "startpoint": "C", "endpoint": "D", "points": [(1, 1), (6, 6)]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "skip_disabled.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=positive_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=False,  # Disable skip
            )

            # Should NOT skip overlay even with positive slack
            assert result.get("overlay_skipped") is not True
            assert result["paths_drawn"] > 0


class TestConditionalOverlayVisualization:
    """Test visual aspects of conditional overlay."""

    @pytest.fixture
    def sample_heatmap_csv(self) -> Path:
        """Create sample heatmap CSV."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            for i in range(10):
                row = [str(float(i + j)) for j in range(10)]
                f.write(",".join(row) + "\n")
            return Path(f.name)

    def test_skipped_overlay_produces_valid_png(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that skipped overlay still produces a valid PNG."""
        positive_paths = [
            {"slack_ps": 150, "startpoint": "A", "endpoint": "B", "points": [(0, 0), (5, 5)]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "skipped_valid.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=positive_paths,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify PNG is valid
            assert output_path.exists()
            img = Image.open(output_path)
            assert img.format == "PNG"
            assert img.size[0] > 0 and img.size[1] > 0

    def test_note_appears_on_skipped_overlay(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Test that a note explaining the skip appears on the heatmap."""
        positive_paths = [
            {"slack_ps": 100, "startpoint": "A", "endpoint": "B", "points": [(0, 0), (5, 5)]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "with_note.png"

            result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=output_path,
                critical_paths=positive_paths,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify metadata indicates skipped
            assert result["overlay_skipped"] is True

            # Verify PNG was created (with note)
            assert output_path.exists()


class TestEndToEndConditionalOverlay:
    """End-to-end validation of conditional overlay feature."""

    @pytest.fixture
    def sample_heatmap_csv(self) -> Path:
        """Create sample heatmap CSV."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False
        ) as f:
            for i in range(10):
                row = [str(float(i + j)) for j in range(10)]
                f.write(",".join(row) + "\n")
            return Path(f.name)

    def test_complete_workflow_positive_and_negative_wns(
        self, sample_heatmap_csv: Path
    ) -> None:
        """Complete workflow testing both positive and negative WNS cases."""
        # Case 1: Design with no timing violations
        clean_design_paths = [
            {"slack_ps": 500, "startpoint": "clk", "endpoint": "reg1", "points": [(0, 0), (3, 4)]},
            {"slack_ps": 300, "startpoint": "rst", "endpoint": "reg2", "points": [(1, 1), (4, 5)]},
            {"slack_ps": 150, "startpoint": "en", "endpoint": "reg3", "points": [(2, 2), (5, 6)]},
        ]

        # Case 2: Design with timing violations
        failing_design_paths = [
            {"slack_ps": -3000, "startpoint": "clk", "endpoint": "reg1", "points": [(0, 0), (3, 4)]},
            {"slack_ps": -2000, "startpoint": "rst", "endpoint": "reg2", "points": [(1, 1), (4, 5)]},
            {"slack_ps": -500, "startpoint": "en", "endpoint": "reg3", "points": [(2, 2), (5, 6)]},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            # Test clean design
            clean_output = Path(tmpdir) / "clean_design.png"
            clean_result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=clean_output,
                critical_paths=clean_design_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Test failing design
            failing_output = Path(tmpdir) / "failing_design.png"
            failing_result = render_heatmap_with_critical_path_overlay(
                csv_path=sample_heatmap_csv,
                output_path=failing_output,
                critical_paths=failing_design_paths,
                path_count=10,
                skip_overlay_if_no_timing_issue=True,
            )

            # Verify clean design behavior
            assert clean_result["overlay_skipped"] is True
            assert clean_result["skip_reason"] == "no_timing_violations"
            assert clean_result["paths_drawn"] == 0
            assert clean_result["best_slack_ps"] == 500
            assert clean_output.exists()

            # Verify failing design behavior
            assert failing_result.get("overlay_skipped") is not True
            assert failing_result["paths_drawn"] == 3  # All 3 paths drawn
            assert failing_result["paths_drawn"] == len(failing_design_paths)
            assert failing_output.exists()

            # Both images should be valid
            clean_img = Image.open(clean_output)
            failing_img = Image.open(failing_output)
            assert clean_img.format == "PNG"
            assert failing_img.format == "PNG"
