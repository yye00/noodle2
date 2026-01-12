"""Tests for F238: Replay with forced visualization even if originally disabled.

Feature: F238 - Replay with forced visualization even if originally disabled
Priority: medium
Category: functional
Depends on: F236

Steps:
1. Identify trial run without visualization
2. Execute: noodle2 replay --case nangate45_1_5 --force-visualization
3. Verify trial is replayed
4. Verify all heatmaps are generated despite original config
5. Verify visualizations are saved to replay output directory
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.replay.trial_replay import (
    ReplayConfig,
    ReplayResult,
    load_trial_config_from_telemetry,
    replay_trial,
)


@pytest.fixture
def mock_telemetry_dir(tmp_path: Path) -> Path:
    """Create mock telemetry structure for testing."""
    study_dir = tmp_path / "telemetry" / "test_study"
    cases_dir = study_dir / "cases"
    cases_dir.mkdir(parents=True)

    # Create mock telemetry file
    telemetry_data = {
        "case_id": "nangate45_1_5",
        "base_case": "nangate45",
        "stage_index": 1,
        "metadata": {
            "eco_class": "BufferPlacement",
            "eco_params": {"buffer_size": "BUF_X4"},
            "visualization_enabled": False,  # Originally disabled
        },
        "trials": [
            {
                "trial_index": 0,
                "metrics": {
                    "timing": {"wns_ps": -500},
                    "congestion": {"hot_ratio": 0.6},
                },
            }
        ],
    }

    telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
    with open(telemetry_file, "w") as f:
        json.dump(telemetry_data, f, indent=2)

    return tmp_path / "telemetry"


class TestF238ForceVisualization:
    """Tests for F238: Replay with forced visualization."""

    def test_step_1_identify_trial_without_visualization(
        self, mock_telemetry_dir: Path
    ) -> None:
        """Step 1: Identify trial run without visualization."""
        # Load trial config
        trial_config, original_metrics = load_trial_config_from_telemetry(
            case_name="nangate45_1_5",
            trial_index=None,
            telemetry_root=mock_telemetry_dir,
        )

        # Verify trial was found
        assert trial_config.case_name == "nangate45_1_5"
        assert trial_config.stage_index == 1

        # Verify visualization was originally disabled
        assert trial_config.metadata.get("visualization_enabled") is False

    def test_step_2_execute_replay_with_force_visualization(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Step 2: Execute: noodle2 replay --case nangate45_1_5 --force-visualization."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            trial_index=None,
            verbose=False,
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,  # Force visualization on
        )

        # Execute replay
        result = replay_trial(config)

        # Verify replay was executed
        assert result is not None
        assert isinstance(result, ReplayResult)

    def test_step_3_verify_trial_is_replayed(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Step 3: Verify trial is replayed."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
        )

        result = replay_trial(config)

        # Verify replay succeeded
        assert result.success is True
        assert result.return_code == 0

        # Verify trial config was loaded
        assert result.trial_config is not None
        assert result.trial_config.case_name == "nangate45_1_5"

        # Verify original metrics were loaded
        assert "timing" in result.original_metrics
        assert "congestion" in result.original_metrics

    def test_step_4_verify_heatmaps_generated_despite_original_config(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Step 4: Verify all heatmaps are generated despite original config."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
        )

        result = replay_trial(config)

        # Verify visualization was forced
        assert result.visualization_forced is True

        # Verify heatmaps were generated
        assert len(result.visualizations_generated) > 0

        # Verify expected heatmaps are present
        generated_names = [p.name for p in result.visualizations_generated]
        expected_heatmaps = [
            "placement_density.png",
            "routing_congestion.png",
            "rudy_congestion.png",
        ]

        for expected in expected_heatmaps:
            assert expected in generated_names, f"Missing heatmap: {expected}"

    def test_step_5_verify_visualizations_saved_to_replay_output(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Step 5: Verify visualizations are saved to replay output directory."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
        )

        result = replay_trial(config)

        # Verify visualizations are in the replay output directory
        for viz_path in result.visualizations_generated:
            # Check path is under output_dir
            assert result.output_dir in viz_path.parents or viz_path.parent == result.output_dir

            # Check file exists
            assert viz_path.exists(), f"Visualization file not found: {viz_path}"

        # Verify heatmaps directory exists
        heatmaps_dir = result.output_dir / "heatmaps"
        assert heatmaps_dir.exists()
        assert heatmaps_dir.is_dir()


class TestF238ReplayMetadata:
    """Test replay metadata includes visualization information."""

    def test_replay_metadata_includes_visualization_info(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify replay metadata captures visualization forcing."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
        )

        result = replay_trial(config)

        # Load replay metadata
        metadata_file = result.output_dir / "replay_metadata.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            metadata = json.load(f)

        # Verify visualization section exists
        assert "visualization" in metadata

        # Verify visualization info is correct
        viz_info = metadata["visualization"]
        assert viz_info["forced"] is True
        assert viz_info["count"] > 0
        assert len(viz_info["visualizations_generated"]) > 0


class TestF238WithoutForceVisualization:
    """Test replay without force_visualization flag."""

    def test_replay_without_force_visualization(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify replay without force_visualization doesn't generate visualizations."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=False,  # Do not force
        )

        result = replay_trial(config)

        # Verify replay succeeded
        assert result.success is True

        # Verify visualization was NOT forced
        assert result.visualization_forced is False

        # Verify no visualizations were generated
        assert len(result.visualizations_generated) == 0

        # Verify heatmaps directory doesn't exist
        heatmaps_dir = result.output_dir / "heatmaps"
        assert not heatmaps_dir.exists()


class TestF238EdgeCases:
    """Test edge cases for forced visualization."""

    def test_force_visualization_with_eco_override(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Test force_visualization combined with ECO override."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
            eco_override="GateSize",  # Override ECO class
        )

        result = replay_trial(config)

        # Verify both features work together
        assert result.success is True
        assert result.visualization_forced is True
        assert len(result.visualizations_generated) > 0
        assert result.replay_eco == "GateSize"

    def test_force_visualization_with_param_overrides(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Test force_visualization combined with parameter overrides."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
            param_overrides={"buffer_size": "BUF_X8"},
        )

        result = replay_trial(config)

        # Verify both features work together
        assert result.success is True
        assert result.visualization_forced is True
        assert len(result.visualizations_generated) > 0
        assert "buffer_size" in result.param_changes

    def test_force_visualization_creates_heatmaps_directory(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Test that force_visualization creates heatmaps directory."""
        output_dir = tmp_path / "replay_output"

        # Verify directory doesn't exist yet
        heatmaps_dir = output_dir / "nangate45_1_5_t0" / "heatmaps"
        assert not heatmaps_dir.exists()

        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=output_dir,
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
        )

        result = replay_trial(config)

        # Verify heatmaps directory was created
        heatmaps_dir = result.output_dir / "heatmaps"
        assert heatmaps_dir.exists()
        assert heatmaps_dir.is_dir()

    def test_force_visualization_verbose_mode(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Test force_visualization with verbose logging."""
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=True,
            verbose=True,  # Enable verbose logging
        )

        result = replay_trial(config)

        # Verify replay succeeded with visualization
        assert result.success is True
        assert result.visualization_forced is True
        assert len(result.visualizations_generated) > 0


class TestF238ConfigDefaults:
    """Test ReplayConfig defaults."""

    def test_replay_config_force_visualization_defaults_to_false(self) -> None:
        """Test that force_visualization defaults to False."""
        config = ReplayConfig(case_name="test_case")

        assert config.force_visualization is False

    def test_replay_result_visualization_fields_have_defaults(
        self, mock_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Test that ReplayResult visualization fields have sensible defaults."""
        # Create a result without force_visualization
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=mock_telemetry_dir,
            force_visualization=False,
        )

        result = replay_trial(config)

        # Verify default values
        assert result.visualization_forced is False
        assert result.visualizations_generated == []
