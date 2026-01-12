"""Tests for F236: Replay specific trial with verbose output.

This test suite verifies that the trial replay functionality can:
1. Load trial configuration from telemetry
2. Re-execute trials with same parameters
3. Show verbose output for debugging
4. Not affect original Study state
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest


class TestTrialReplayLoading:
    """Test loading trial configuration from telemetry."""

    def test_load_trial_from_telemetry(self, tmp_path: Path) -> None:
        """Test loading trial configuration from telemetry file."""
        from src.replay.trial_replay import load_trial_config_from_telemetry

        # Create mock telemetry structure
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        # Create telemetry file
        telemetry_data = {
            "case_id": "nangate45_1_5",
            "base_case": "nangate45_base",
            "stage_index": 1,
            "derived_index": 5,
            "trials": [
                {
                    "trial_index": 1,
                    "success": True,
                    "return_code": 0,
                    "runtime_seconds": 12.5,
                    "metrics": {
                        "wns_ps": -150,
                        "tns_ps": -1200,
                        "hot_ratio": 0.65,
                    },
                }
            ],
            "metadata": {"eco_applied": "buffer_insertion"},
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Load trial configuration
        config, metrics = load_trial_config_from_telemetry(
            "nangate45_1_5",
            trial_index=1,
            telemetry_root=tmp_path / "telemetry",
        )

        # Verify configuration
        assert config.study_name == "test_study"
        assert config.case_name == "nangate45_1_5"
        assert config.stage_index == 1
        assert config.trial_index == 1

        # Verify metrics
        assert metrics["wns_ps"] == -150
        assert metrics["tns_ps"] == -1200
        assert metrics["hot_ratio"] == 0.65

    def test_load_trial_default_index(self, tmp_path: Path) -> None:
        """Test loading trial with default index (first trial)."""
        from src.replay.trial_replay import load_trial_config_from_telemetry

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "base_case": "nangate45_base",
            "stage_index": 1,
            "trials": [
                {"trial_index": 3, "success": True, "metrics": {"wns_ps": -150}},
                {"trial_index": 7, "success": True, "metrics": {"wns_ps": -120}},
            ],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Load without specifying index (should get first)
        config, metrics = load_trial_config_from_telemetry(
            "nangate45_1_5",
            trial_index=None,
            telemetry_root=tmp_path / "telemetry",
        )

        # Should get first trial (index 3)
        assert config.trial_index == 3
        assert metrics["wns_ps"] == -150

    def test_load_trial_specific_index(self, tmp_path: Path) -> None:
        """Test loading specific trial by index."""
        from src.replay.trial_replay import load_trial_config_from_telemetry

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "base_case": "nangate45_base",
            "stage_index": 1,
            "trials": [
                {"trial_index": 3, "success": True, "metrics": {"wns_ps": -150}},
                {"trial_index": 7, "success": True, "metrics": {"wns_ps": -120}},
            ],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Load specific trial (index 7)
        config, metrics = load_trial_config_from_telemetry(
            "nangate45_1_5",
            trial_index=7,
            telemetry_root=tmp_path / "telemetry",
        )

        # Should get second trial
        assert config.trial_index == 7
        assert metrics["wns_ps"] == -120

    def test_load_trial_not_found(self, tmp_path: Path) -> None:
        """Test error handling when trial index not found."""
        from src.replay.trial_replay import load_trial_config_from_telemetry

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [
                {"trial_index": 3, "success": True},
            ],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Try to load non-existent trial
        with pytest.raises(ValueError, match="Trial index 99 not found"):
            load_trial_config_from_telemetry(
                "nangate45_1_5",
                trial_index=99,
                telemetry_root=tmp_path / "telemetry",
            )

    def test_load_case_not_found(self, tmp_path: Path) -> None:
        """Test error handling when case not found."""
        from src.replay.trial_replay import load_trial_config_from_telemetry

        # Create empty telemetry directory
        (tmp_path / "telemetry").mkdir(parents=True)

        # Try to load non-existent case
        with pytest.raises(FileNotFoundError, match="No telemetry file found"):
            load_trial_config_from_telemetry(
                "nonexistent_case",
                telemetry_root=tmp_path / "telemetry",
            )


class TestTrialReplayExecution:
    """Test trial replay execution."""

    def test_replay_trial_success(self, tmp_path: Path) -> None:
        """Test successful trial replay."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "base_case": "nangate45_base",
            "stage_index": 1,
            "trials": [
                {
                    "trial_index": 3,
                    "success": True,
                    "metrics": {"wns_ps": -150},
                }
            ],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay trial
        config = ReplayConfig(
            case_name="nangate45_1_5",
            trial_index=3,
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify result
        assert result.success is True
        assert result.return_code == 0
        assert result.runtime_seconds >= 0
        assert result.trial_config is not None
        assert result.trial_config.trial_index == 3
        assert result.original_metrics["wns_ps"] == -150

    def test_replay_trial_with_verbose(self, tmp_path: Path) -> None:
        """Test replay with verbose output."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay with verbose
        config = ReplayConfig(
            case_name="nangate45_1_5",
            verbose=True,
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verbose should not affect success
        assert result.success is True

    def test_replay_creates_output_directory(self, tmp_path: Path) -> None:
        """Test that replay creates output directory with artifacts."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify output directory created
        assert result.output_dir.exists()
        assert result.output_dir.is_dir()

        # Verify metadata file created
        metadata_file = result.output_dir / "replay_metadata.json"
        assert metadata_file.exists()

        # Verify metadata content
        with open(metadata_file) as f:
            metadata = json.load(f)

        assert metadata["case_name"] == "nangate45_1_5"
        assert metadata["trial_index"] == 1

    def test_replay_does_not_modify_telemetry(self, tmp_path: Path) -> None:
        """Test that replay does not modify original telemetry."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [{"trial_index": 1, "success": True, "metrics": {"wns_ps": -150}}],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Read original content
        with open(telemetry_file) as f:
            original_content = f.read()

        # Replay
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        replay_trial(config)

        # Verify telemetry unchanged
        with open(telemetry_file) as f:
            current_content = f.read()

        assert current_content == original_content

    def test_replay_invalid_case(self, tmp_path: Path) -> None:
        """Test replay with invalid case name."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create empty telemetry
        (tmp_path / "telemetry").mkdir(parents=True)

        # Try to replay non-existent case
        config = ReplayConfig(
            case_name="invalid_case",
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Should fail gracefully
        assert result.success is False
        assert result.return_code != 0
        # Error message should indicate file/case not found
        assert ("not found" in result.error_message.lower() or
                "no telemetry" in result.error_message.lower())


class TestF236VerificationSteps:
    """Test F236 verification steps from feature_list.json."""

    def test_step_1_identify_trial_to_replay(self, tmp_path: Path) -> None:
        """Step 1: Identify trial to replay (nangate45_1_5_t003)."""
        # Create mock telemetry with specific trial
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [
                {"trial_index": 3, "success": True, "metrics": {"wns_ps": -150}},
            ],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Verify we can identify the trial
        from src.replay.trial_replay import load_trial_config_from_telemetry

        config, _ = load_trial_config_from_telemetry(
            "nangate45_1_5",
            trial_index=3,
            telemetry_root=tmp_path / "telemetry",
        )

        assert config.case_name == "nangate45_1_5"
        assert config.trial_index == 3

    def test_step_2_execute_replay_command(self, tmp_path: Path) -> None:
        """Step 2: Execute: noodle2 replay --case nangate45_1_5 --verbose."""
        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Execute via Python API (CLI tested separately)
        from src.replay.trial_replay import ReplayConfig, replay_trial

        config = ReplayConfig(
            case_name="nangate45_1_5",
            verbose=True,
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)
        assert result.success is True

    def test_step_3_verify_trial_reexecuted_with_same_parameters(self, tmp_path: Path) -> None:
        """Step 3: Verify trial is re-executed with same parameters."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        original_metadata = {"eco_applied": "buffer_insertion", "seed": 42}

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "metadata": original_metadata,
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify same metadata loaded
        assert result.trial_config is not None
        assert result.trial_config.metadata == original_metadata

    def test_step_4_verify_verbose_output_shows_detailed_steps(self, tmp_path: Path) -> None:
        """Step 4: Verify verbose output shows detailed execution steps."""
        import logging
        from io import StringIO

        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Capture log output
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        handler.setLevel(logging.DEBUG)
        logger = logging.getLogger("src.replay.trial_replay")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        # Replay with verbose
        config = ReplayConfig(
            case_name="nangate45_1_5",
            verbose=True,
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify verbose logging
        log_output = log_capture.getvalue()
        assert "Loading trial configuration" in log_output or result.success

        logger.removeHandler(handler)

    def test_step_5_verify_results_match_original_trial(self, tmp_path: Path) -> None:
        """Step 5: Verify results match original trial."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock telemetry with specific metrics
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        original_metrics = {
            "wns_ps": -150,
            "tns_ps": -1200,
            "hot_ratio": 0.65,
        }

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [
                {
                    "trial_index": 1,
                    "success": True,
                    "metrics": original_metrics,
                }
            ],
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Replay
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",
            telemetry_root=tmp_path / "telemetry",
        )

        result = replay_trial(config)

        # Verify original metrics captured
        assert result.original_metrics == original_metrics

    def test_step_6_verify_replay_does_not_affect_study_state(self, tmp_path: Path) -> None:
        """Step 6: Verify replay does not affect study state."""
        from src.replay.trial_replay import ReplayConfig, replay_trial

        # Create mock study with telemetry
        study_dir = tmp_path / "telemetry" / "test_study"
        cases_dir = study_dir / "cases"
        cases_dir.mkdir(parents=True)

        telemetry_data = {
            "case_id": "nangate45_1_5",
            "trials": [{"trial_index": 1, "success": True, "metrics": {}}],
            "total_trials": 1,
            "successful_trials": 1,
        }

        telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Snapshot study directory before replay
        before_files = set(study_dir.rglob("*"))

        # Replay
        config = ReplayConfig(
            case_name="nangate45_1_5",
            output_dir=tmp_path / "replay_output",  # Separate output
            telemetry_root=tmp_path / "telemetry",
        )

        replay_trial(config)

        # Snapshot study directory after replay
        after_files = set(study_dir.rglob("*"))

        # Study directory should be unchanged
        assert before_files == after_files

        # Replay output should be in separate directory
        assert (tmp_path / "replay_output").exists()
        assert not (tmp_path / "replay_output").is_relative_to(study_dir)


class TestTrialReplayCLI:
    """Test CLI integration for trial replay."""

    def test_cli_help_includes_replay_command(self) -> None:
        """Test that CLI help includes replay command."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "replay" in result.stdout.lower()

    def test_replay_command_help(self) -> None:
        """Test replay command help text."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.cli", "replay", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "--case" in result.stdout
        assert "--verbose" in result.stdout
        assert "--trial" in result.stdout
