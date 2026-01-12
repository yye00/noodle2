"""Tests for F237: Replay trial with modified ECO parameters.

This test suite verifies that trials can be replayed with modified
ECO parameters for parameter sensitivity analysis.
"""

import json
import subprocess
from pathlib import Path

import pytest


class TestReplayWithParameterOverrides:
    """Test replaying trials with parameter modifications."""

    def test_replay_with_single_parameter_override(self, tmp_path: Path) -> None:
        """Test replay with a single parameter override."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry with ECO parameters
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "base_case": "nangate45_base",
            "stage_index": 1,
            "trials": [
                {
                    "trial_index": 1,
                    "success": True,
                    "metrics": {"wns_ps": -150},
                }
            ],
            "metadata": {
                "eco_class": "resize_critical_drivers",
                "eco_params": {
                    "size_multiplier": 1.5,
                    "threshold_ps": 100,
                },
            },
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with parameter override
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"size_multiplier": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify success
        assert result.success is True

        # Verify parameter change tracked
        assert "size_multiplier" in result.param_changes
        old_val, new_val = result.param_changes["size_multiplier"]
        assert old_val == 1.5
        assert new_val == 1.8

    def test_replay_with_multiple_parameter_overrides(self, tmp_path: Path) -> None:
        """Test replay with multiple parameter overrides."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {
                "eco_class": "resize_critical_drivers",
                "eco_params": {
                    "size_multiplier": 1.5,
                    "threshold_ps": 100,
                    "max_fanout": 8,
                },
            },
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with multiple overrides
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={
                "size_multiplier": 1.8,
                "threshold_ps": 50,
            },
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify both changes tracked
        assert len(result.param_changes) == 2
        assert result.param_changes["size_multiplier"] == (1.5, 1.8)
        assert result.param_changes["threshold_ps"] == (100, 50)

    def test_replay_with_eco_override(self, tmp_path: Path) -> None:
        """Test replay with ECO class override."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {
                "eco_class": "buffer_insertion",
                "eco_params": {"buffer_strength": 2},
            },
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with ECO override
        config = ReplayConfig(
            case_name="nangate45_1_3",
            eco_override="resize_critical_drivers",
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify ECO changed
        assert result.original_eco == "buffer_insertion"
        assert result.replay_eco == "resize_critical_drivers"

    def test_replay_with_new_parameter(self, tmp_path: Path) -> None:
        """Test replay adding a new parameter not in original."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {
                "eco_class": "resize_critical_drivers",
                "eco_params": {"size_multiplier": 1.5},
            },
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Add new parameter
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"new_param": 42},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # New parameter should be tracked (None → 42)
        assert "new_param" in result.param_changes
        old_val, new_val = result.param_changes["new_param"]
        assert old_val is None
        assert new_val == 42

    def test_replay_output_directory_with_modifications(self, tmp_path: Path) -> None:
        """Test that modified replays use different output directory."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {"eco_params": {"size": 1.5}},
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with modification
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"size": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Output directory should include "_modified" suffix
        assert "_modified" in str(result.output_dir)
        assert result.output_dir.exists()

    def test_replay_metadata_includes_parameter_changes(self, tmp_path: Path) -> None:
        """Test that replay metadata captures parameter changes."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {
                "eco_class": "resize",
                "eco_params": {"size_multiplier": 1.5},
            },
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with parameter override
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"size_multiplier": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Read metadata file
        metadata_file = result.output_dir / "replay_metadata.json"
        with open(metadata_file) as f:
            metadata = json.load(f)

        # Verify eco_info section
        assert "eco_info" in metadata
        eco_info = metadata["eco_info"]
        assert eco_info["original_eco"] == "resize"
        assert eco_info["original_params"]["size_multiplier"] == 1.5
        assert eco_info["replay_params"]["size_multiplier"] == 1.8
        assert "size_multiplier" in eco_info["param_changes"]
        assert eco_info["param_changes"]["size_multiplier"]["old"] == 1.5
        assert eco_info["param_changes"]["size_multiplier"]["new"] == 1.8


class TestF237VerificationSteps:
    """Test F237 verification steps from feature_list.json."""

    def test_step_1_identify_trial_with_eco_parameters(self, tmp_path: Path) -> None:
        """Step 1: Identify trial with ECO parameters."""
        from src.replay.trial_replay import load_trial_config_from_telemetry

        # Create trial with ECO parameters
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {
                "eco_class": "resize_critical_drivers",
                "eco_params": {"size_multiplier": 1.5},
            },
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Load trial configuration
        config, _ = load_trial_config_from_telemetry(
            "nangate45_1_3",
            telemetry_root=tmp_path / "telemetry",
        )

        # Verify ECO parameters present
        assert "eco_class" in config.metadata
        assert "eco_params" in config.metadata
        assert config.metadata["eco_params"]["size_multiplier"] == 1.5

    def test_step_2_execute_replay_with_modified_parameter(self, tmp_path: Path) -> None:
        """Step 2: Execute replay with --param size_multiplier=1.8."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {
                "eco_class": "resize_critical_drivers",
                "eco_params": {"size_multiplier": 1.5},
            },
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Execute replay with parameter override
        config = ReplayConfig(
            case_name="nangate45_1_3",
            eco_override="resize_critical_drivers",
            param_overrides={"size_multiplier": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)
        assert result.success is True

    def test_step_3_verify_trial_replayed_with_modified_parameter(self, tmp_path: Path) -> None:
        """Step 3: Verify trial is replayed with modified parameter."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {"eco_params": {"size_multiplier": 1.5}},
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with modification
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"size_multiplier": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify parameter was modified
        assert "size_multiplier" in result.param_changes

    def test_step_4_verify_original_parameter_was_size_multiplier_1_5(self, tmp_path: Path) -> None:
        """Step 4: Verify original parameter was size_multiplier=1.5."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {"eco_params": {"size_multiplier": 1.5}},
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"size_multiplier": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify original value
        old_val, _ = result.param_changes["size_multiplier"]
        assert old_val == 1.5

    def test_step_5_verify_modified_parameter_is_used_in_replay(self, tmp_path: Path) -> None:
        """Step 5: Verify modified parameter is used in replay."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": {"eco_params": {"size_multiplier": 1.5}},
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"size_multiplier": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify new value
        _, new_val = result.param_changes["size_multiplier"]
        assert new_val == 1.8

    def test_step_6_compare_results_to_understand_parameter_sensitivity(self, tmp_path: Path) -> None:
        """Step 6: Compare results to understand parameter sensitivity."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry with metrics
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_3",
            "trials": [
                {
                    "trial_index": 1,
                    "success": True,
                    "metrics": {"wns_ps": -150, "tns_ps": -1200},
                }
            ],
            "metadata": {"eco_params": {"size_multiplier": 1.5}},
        }

        telemetry_file = cases_dir / "nangate45_1_3_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with modification
        config = ReplayConfig(
            case_name="nangate45_1_3",
            param_overrides={"size_multiplier": 1.8},
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Original metrics should be available for comparison
        assert result.original_metrics["wns_ps"] == -150
        assert result.original_metrics["tns_ps"] == -1200

        # Parameter change is documented
        assert result.param_changes["size_multiplier"] == (1.5, 1.8)

        # This allows sensitivity analysis: if size_multiplier increases
        # from 1.5 to 1.8, how do metrics change?


class TestParameterOverrideCLI:
    """Test CLI integration for parameter overrides."""

    def test_cli_help_includes_param_flag(self) -> None:
        """Test that CLI help shows --param flag."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.cli", "replay", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--param" in result.stdout

    def test_cli_help_includes_eco_flag(self) -> None:
        """Test that CLI help shows --eco flag."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.cli", "replay", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--eco" in result.stdout
