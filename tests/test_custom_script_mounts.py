"""Tests for custom script mounting feature."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.study import load_study_config
from src.controller.types import ExecutionMode, SafetyDomain, StageConfig, StudyConfig
from src.trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner


class TestCustomScriptMounts:
    """Tests for custom script mounting in Docker containers."""

    def test_study_config_has_custom_script_mounts_field(self) -> None:
        """Step 1: Verify StudyConfig has custom_script_mounts field."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/tmp/snapshot",
            custom_script_mounts={"/host/scripts": "/eco_scripts"},
        )

        assert hasattr(config, "custom_script_mounts")
        assert config.custom_script_mounts == {"/host/scripts": "/eco_scripts"}

    def test_study_config_custom_script_mounts_defaults_to_empty(self) -> None:
        """Verify custom_script_mounts defaults to empty dict."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/tmp/snapshot",
        )

        assert config.custom_script_mounts == {}

    def test_docker_run_config_has_custom_script_mounts_field(self) -> None:
        """Step 2: Verify DockerRunConfig has custom_script_mounts field."""
        config = DockerRunConfig(
            custom_script_mounts={"/host/scripts": "/eco_scripts"}
        )

        assert hasattr(config, "custom_script_mounts")
        assert config.custom_script_mounts == {"/host/scripts": "/eco_scripts"}

    def test_docker_run_config_custom_script_mounts_defaults_to_none(self) -> None:
        """Verify custom_script_mounts defaults to None."""
        config = DockerRunConfig()

        assert config.custom_script_mounts is None

    def test_load_study_config_with_custom_script_mounts(self, tmp_path: Path) -> None:
        """Step 2: Test loading Study config with custom_script_mounts from YAML."""
        # Create a temporary Study YAML with custom_script_mounts
        study_yaml = tmp_path / "study.yaml"
        study_yaml.write_text(
            """
name: test_custom_scripts
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshot

custom_script_mounts:
  /host/eco_scripts: /eco_scripts
  /host/helpers: /helpers

stages:
  - name: stage0
    execution_mode: sta_only
    trial_budget: 5
    survivor_count: 2
    allowed_eco_classes: []
"""
        )

        # Load the configuration
        config = load_study_config(study_yaml)

        # Verify custom_script_mounts was loaded correctly
        assert config.custom_script_mounts == {
            "/host/eco_scripts": "/eco_scripts",
            "/host/helpers": "/helpers",
        }

    def test_docker_runner_mounts_custom_scripts(self, tmp_path: Path) -> None:
        """Step 3: Verify Docker runner creates volume mounts for custom scripts."""
        # Create a custom script directory
        custom_script_dir = tmp_path / "custom_scripts"
        custom_script_dir.mkdir()
        script_file = custom_script_dir / "my_eco.tcl"
        script_file.write_text("puts \"Custom ECO script\"")

        # Create a test script to execute
        test_script = tmp_path / "test.tcl"
        test_script.write_text("puts \"Test script\"")

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with custom script mounts
        config = DockerRunConfig(
            custom_script_mounts={str(custom_script_dir): "/eco_scripts"}
        )
        runner = DockerTrialRunner(config)

        # Execute trial - this will attempt to mount the custom scripts
        # We expect this to succeed with the script mounted
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify the trial executed (even if it doesn't use the custom scripts)
        assert result.return_code == 0
        assert result.custom_script_mounts == {str(custom_script_dir): "/eco_scripts"}

    def test_custom_script_mount_only_if_path_exists(self, tmp_path: Path) -> None:
        """Step 4: Verify scripts are only mounted if host path exists."""
        # Create a test script to execute
        test_script = tmp_path / "test.tcl"
        test_script.write_text("puts \"Test script\"")

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with non-existent custom script path
        nonexistent_path = "/nonexistent/path/to/scripts"
        config = DockerRunConfig(
            custom_script_mounts={nonexistent_path: "/eco_scripts"}
        )
        runner = DockerTrialRunner(config)

        # Execute trial - should succeed even though custom script path doesn't exist
        # (the mount is simply not added to volumes)
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify the trial executed successfully
        assert result.return_code == 0
        # Provenance still tracks what was configured
        assert result.custom_script_mounts == {nonexistent_path: "/eco_scripts"}

    def test_execute_eco_using_custom_script(self, tmp_path: Path) -> None:
        """Step 5: Execute ECO using custom script from mounted directory."""
        # Create a custom ECO script that writes output
        custom_script_dir = tmp_path / "custom_scripts"
        custom_script_dir.mkdir()
        eco_script = custom_script_dir / "buffer_insertion.tcl"
        eco_script.write_text(
            """
# Custom buffer insertion ECO
puts "Running custom buffer insertion ECO"
set eco_output [open "/work/eco_output.txt" w]
puts $eco_output "Custom ECO executed successfully"
close $eco_output
"""
        )

        # Create a test script that sources the custom ECO
        test_script = tmp_path / "test.tcl"
        test_script.write_text(
            """
# Source custom ECO script
source /eco_scripts/buffer_insertion.tcl
"""
        )

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with custom script mounts
        config = DockerRunConfig(
            custom_script_mounts={str(custom_script_dir): "/eco_scripts"}
        )
        runner = DockerTrialRunner(config)

        # Execute trial
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify the trial executed successfully
        assert result.return_code == 0
        assert "Running custom buffer insertion ECO" in result.stdout

        # Verify the custom ECO wrote output
        eco_output_file = work_dir / "eco_output.txt"
        assert eco_output_file.exists()
        assert "Custom ECO executed successfully" in eco_output_file.read_text()

    def test_provenance_tracks_custom_script_locations(self, tmp_path: Path) -> None:
        """Step 6: Verify provenance tracks custom script mount locations."""
        # Create a custom script directory
        custom_script_dir = tmp_path / "custom_scripts"
        custom_script_dir.mkdir()

        # Create a test script to execute
        test_script = tmp_path / "test.tcl"
        test_script.write_text("puts \"Test script\"")

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with custom script mounts
        custom_mounts = {
            str(custom_script_dir): "/eco_scripts",
            str(tmp_path / "helpers"): "/helpers",
        }
        config = DockerRunConfig(custom_script_mounts=custom_mounts)
        runner = DockerTrialRunner(config)

        # Execute trial
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify provenance tracks custom script mounts
        assert result.custom_script_mounts is not None
        assert result.custom_script_mounts == custom_mounts

    def test_multiple_custom_script_mounts(self, tmp_path: Path) -> None:
        """Test mounting multiple custom script directories."""
        # Create multiple custom script directories
        eco_dir = tmp_path / "eco_scripts"
        eco_dir.mkdir()
        eco_script = eco_dir / "eco.tcl"
        eco_script.write_text("puts \"ECO script\"")

        helper_dir = tmp_path / "helpers"
        helper_dir.mkdir()
        helper_script = helper_dir / "helper.tcl"
        helper_script.write_text("puts \"Helper script\"")

        # Create a test script that sources both
        test_script = tmp_path / "test.tcl"
        test_script.write_text(
            """
source /eco_scripts/eco.tcl
source /helpers/helper.tcl
"""
        )

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with multiple custom script mounts
        config = DockerRunConfig(
            custom_script_mounts={
                str(eco_dir): "/eco_scripts",
                str(helper_dir): "/helpers",
            }
        )
        runner = DockerTrialRunner(config)

        # Execute trial
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify the trial executed successfully
        assert result.return_code == 0
        assert "ECO script" in result.stdout
        assert "Helper script" in result.stdout

    def test_custom_scripts_mounted_read_only(self, tmp_path: Path) -> None:
        """Verify custom scripts are mounted read-only for safety."""
        # Create a custom script directory
        custom_script_dir = tmp_path / "custom_scripts"
        custom_script_dir.mkdir()
        script_file = custom_script_dir / "script.tcl"
        script_file.write_text("puts \"Original content\"")

        # Create a test script that tries to modify the custom script
        test_script = tmp_path / "test.tcl"
        test_script.write_text(
            """
# Try to modify the mounted script (should fail due to read-only)
catch {
    set f [open "/eco_scripts/script.tcl" w]
    puts $f "Modified content"
    close $f
} err
if {$err != ""} {
    puts "Expected: Cannot write to read-only mount"
}
"""
        )

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with custom script mounts
        config = DockerRunConfig(
            custom_script_mounts={str(custom_script_dir): "/eco_scripts"}
        )
        runner = DockerTrialRunner(config)

        # Execute trial
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify the trial executed
        assert result.return_code == 0

        # Verify the original script file was not modified
        assert "Original content" in script_file.read_text()
        assert "Modified content" not in script_file.read_text()

    def test_study_yaml_validation_with_custom_mounts(self, tmp_path: Path) -> None:
        """Verify Study validation works with custom_script_mounts."""
        study_yaml = tmp_path / "study.yaml"
        study_yaml.write_text(
            """
name: test_study
safety_domain: sandbox
base_case_name: base
pdk: Nangate45
snapshot_path: /tmp/snapshot

custom_script_mounts:
  /host/scripts: /eco_scripts

stages:
  - name: stage0
    execution_mode: sta_only
    trial_budget: 5
    survivor_count: 2
    allowed_eco_classes: []
"""
        )

        # Load and validate
        config = load_study_config(study_yaml)
        config.validate()  # Should not raise

        assert config.custom_script_mounts == {"/host/scripts": "/eco_scripts"}

    def test_empty_custom_script_mounts(self, tmp_path: Path) -> None:
        """Test that empty custom_script_mounts is handled correctly."""
        # Create a test script to execute
        test_script = tmp_path / "test.tcl"
        test_script.write_text("puts \"Test script\"")

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with empty custom script mounts
        config = DockerRunConfig(custom_script_mounts={})
        runner = DockerTrialRunner(config)

        # Execute trial
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify the trial executed successfully
        assert result.return_code == 0
        assert result.custom_script_mounts == {}

    def test_custom_script_mounts_in_trial_result_dict(self, tmp_path: Path) -> None:
        """Verify custom_script_mounts can be serialized to dict/JSON."""
        # Create a test script to execute
        test_script = tmp_path / "test.tcl"
        test_script.write_text("puts \"Test script\"")

        # Create working directory
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Configure Docker runner with custom script mounts
        custom_mounts = {"/host/scripts": "/eco_scripts"}
        config = DockerRunConfig(custom_script_mounts=custom_mounts)
        runner = DockerTrialRunner(config)

        # Execute trial
        result = runner.execute_trial(
            script_path=test_script,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify result has custom_script_mounts
        assert result.custom_script_mounts == custom_mounts

        # Verify it can be serialized to JSON (for telemetry)
        result_dict = {
            "return_code": result.return_code,
            "success": result.success,
            "custom_script_mounts": result.custom_script_mounts,
        }
        json_str = json.dumps(result_dict)
        assert "/host/scripts" in json_str
        assert "/eco_scripts" in json_str
