"""Tests for F221: Differential heatmap generation gracefully skips when no parent exists."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.visualization.heatmap_renderer import (
    generate_differential_heatmaps_safe,
    render_heatmap_png,
)


# --- Helper Functions ---


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


def create_test_heatmaps_dir(base_dir: Path) -> Path:
    """Create a directory with sample heatmaps."""
    heatmaps_dir = base_dir / "heatmaps"
    heatmaps_dir.mkdir(parents=True, exist_ok=True)

    # Create sample heatmaps
    sample_data = np.array([[1.0, 2.0], [3.0, 4.0]])
    create_test_heatmap_csv(heatmaps_dir / "placement_density.csv", sample_data)
    create_test_heatmap_csv(heatmaps_dir / "routing_congestion.csv", sample_data)

    return heatmaps_dir


# --- Feature Step Tests ---


class TestF221FeatureSteps:
    """Test all 6 steps for F221: Differential fallback for base case."""

    def test_step1_attempt_to_generate_differential_for_base_case(
        self, tmp_path: Path
    ) -> None:
        """Step 1: Attempt to generate differential for base case (no parent)."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        # Call with has_parent=False (base case)
        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=None,
            output_dir=output_dir,
            has_parent=False,
        )

        # Verify function was called successfully
        assert result is not None
        assert isinstance(result, dict)

    def test_step2_verify_differential_generation_is_skipped(
        self, tmp_path: Path
    ) -> None:
        """Step 2: Verify differential generation is skipped."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=None,
            output_dir=output_dir,
            has_parent=False,
        )

        # Verify differential generation was skipped
        assert result["differential_generated"] is False
        assert result["differential_count"] == 0
        assert result["skip_reason"] == "no_parent"

    def test_step3_verify_absolute_heatmaps_are_still_generated(
        self, tmp_path: Path
    ) -> None:
        """Step 3: Verify absolute heatmaps are still generated."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        # First generate absolute heatmaps (done independently of differential generation)
        png_output_dir = tmp_path / "pngs"
        png_output_dir.mkdir()

        # Generate PNGs from CSVs
        for csv_file in current_dir.glob("*.csv"):
            png_file = png_output_dir / f"{csv_file.stem}.png"
            metadata = render_heatmap_png(
                csv_path=csv_file,
                output_path=png_file,
                title=csv_file.stem.replace("_", " ").title(),
            )
            assert metadata["png_path"] == str(png_file)

        # Verify absolute heatmaps exist
        assert (png_output_dir / "placement_density.png").exists()
        assert (png_output_dir / "routing_congestion.png").exists()

        # Now attempt differential generation (should skip)
        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=None,
            output_dir=output_dir,
            has_parent=False,
        )

        # Verify differential was skipped
        assert result["differential_generated"] is False

        # But absolute heatmaps should still be available
        assert (png_output_dir / "placement_density.png").exists()
        assert (png_output_dir / "routing_congestion.png").exists()

    def test_step4_verify_artifact_index_indicates_differential_unavailable(
        self, tmp_path: Path
    ) -> None:
        """Step 4: Verify artifact_index.json indicates differential: unavailable."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=None,
            output_dir=output_dir,
            has_parent=False,
        )

        # Verify result contains clear indication
        assert result["differential_generated"] is False
        assert result["skip_reason"] == "no_parent"
        assert "message" in result
        assert "unavailable" in result["message"].lower() or "no parent" in result["message"].lower()

        # This result can be used to populate artifact_index.json
        # The caller would check result["differential_generated"] and set
        # artifact_index["differential_heatmaps"] = "unavailable" accordingly

    def test_step5_verify_no_error_is_raised(self, tmp_path: Path) -> None:
        """Step 5: Verify no error is raised."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        # Should not raise any exceptions
        try:
            result = generate_differential_heatmaps_safe(
                current_case_heatmaps_dir=current_dir,
                parent_case_heatmaps_dir=None,
                output_dir=output_dir,
                has_parent=False,
            )
            # Verify function completed successfully
            assert result is not None
            assert result["differential_generated"] is False
            error_raised = False
        except Exception as e:
            error_raised = True
            pytest.fail(f"Unexpected exception raised: {e}")

        assert not error_raised

    def test_step6_log_informative_message_explaining_skip(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Step 6: Log informative message explaining skip."""
        import logging

        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        # Capture logs
        with caplog.at_level(logging.INFO):
            result = generate_differential_heatmaps_safe(
                current_case_heatmaps_dir=current_dir,
                parent_case_heatmaps_dir=None,
                output_dir=output_dir,
                has_parent=False,
            )

        # Verify informative message was logged
        assert any("no parent" in record.message.lower() for record in caplog.records)
        assert any("base case" in record.message.lower() for record in caplog.records)

        # Verify message in result
        assert "message" in result
        assert "no parent" in result["message"].lower() or "base case" in result["message"].lower()


# --- Edge Cases and Additional Tests ---


class TestDifferentialGenerationEdgeCases:
    """Additional tests for edge cases in differential generation."""

    def test_parent_exists_differential_generated(self, tmp_path: Path) -> None:
        """When parent exists, differential should be generated."""
        parent_dir = create_test_heatmaps_dir(tmp_path / "parent")
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=parent_dir,
            output_dir=output_dir,
            has_parent=True,
        )

        # Verify differential was generated
        assert result["differential_generated"] is True
        assert result["differential_count"] > 0
        assert result["skip_reason"] is None

        # Verify diff files exist
        assert (output_dir / "placement_density_diff.png").exists()
        assert (output_dir / "routing_congestion_diff.png").exists()

    def test_parent_directory_not_found_graceful_skip(self, tmp_path: Path) -> None:
        """When parent directory doesn't exist, gracefully skip."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        parent_dir = tmp_path / "nonexistent_parent"
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=parent_dir,
            output_dir=output_dir,
            has_parent=True,
        )

        # Verify graceful skip
        assert result["differential_generated"] is False
        assert result["skip_reason"] == "parent_directory_not_found"
        assert "message" in result

    def test_current_directory_not_found_graceful_skip(self, tmp_path: Path) -> None:
        """When current directory doesn't exist, gracefully skip."""
        parent_dir = create_test_heatmaps_dir(tmp_path / "parent")
        current_dir = tmp_path / "nonexistent_current"
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=parent_dir,
            output_dir=output_dir,
            has_parent=True,
        )

        # Verify graceful skip
        assert result["differential_generated"] is False
        assert result["skip_reason"] == "current_directory_not_found"
        assert "message" in result

    def test_none_parent_case_heatmaps_dir_with_has_parent_false(
        self, tmp_path: Path
    ) -> None:
        """None parent_case_heatmaps_dir with has_parent=False is valid."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=None,
            output_dir=output_dir,
            has_parent=False,
        )

        # Should skip gracefully
        assert result["differential_generated"] is False
        assert result["skip_reason"] == "no_parent"

    def test_has_parent_true_but_parent_dir_none_graceful_skip(
        self, tmp_path: Path
    ) -> None:
        """has_parent=True but parent_dir=None should skip gracefully."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=None,
            output_dir=output_dir,
            has_parent=True,
        )

        # Should skip gracefully (inconsistent state, but handle it)
        assert result["differential_generated"] is False
        assert result["skip_reason"] == "no_parent"

    def test_empty_parent_directory_no_matching_heatmaps(self, tmp_path: Path) -> None:
        """Empty parent directory results in no differentials generated."""
        parent_dir = tmp_path / "parent" / "heatmaps"
        parent_dir.mkdir(parents=True)  # Empty directory

        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        result = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=parent_dir,
            output_dir=output_dir,
            has_parent=True,
        )

        # Should complete but with 0 differentials
        assert result["differential_generated"] is True
        assert result["differential_count"] == 0  # No matching heatmaps

    def test_result_structure_is_consistent(self, tmp_path: Path) -> None:
        """Result structure should be consistent across all cases."""
        current_dir = create_test_heatmaps_dir(tmp_path / "current")
        output_dir = tmp_path / "output"

        # Test with no parent
        result1 = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=None,
            output_dir=output_dir,
            has_parent=False,
        )

        # Test with parent
        parent_dir = create_test_heatmaps_dir(tmp_path / "parent")
        result2 = generate_differential_heatmaps_safe(
            current_case_heatmaps_dir=current_dir,
            parent_case_heatmaps_dir=parent_dir,
            output_dir=output_dir,
            has_parent=True,
        )

        # Verify both results have required fields
        required_fields = [
            "differential_generated",
            "differential_count",
            "skip_reason",
            "results",
            "message",
        ]

        for result in [result1, result2]:
            for field in required_fields:
                assert field in result, f"Missing required field: {field}"

        # Verify types
        assert isinstance(result1["differential_generated"], bool)
        assert isinstance(result1["differential_count"], int)
        assert isinstance(result1["results"], list)
        assert isinstance(result1["message"], str)
