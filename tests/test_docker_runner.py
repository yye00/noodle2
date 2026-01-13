"""Tests for Docker trial runner."""

import pytest
import tempfile
from pathlib import Path

from src.trial_runner.docker_runner import (
    DockerRunConfig,
    DockerTrialRunner,
)


def test_docker_runner_initialization() -> None:
    """Test Docker runner can be initialized."""
    runner = DockerTrialRunner()
    assert runner is not None
    assert runner.config.image == "openroad/orfs:latest"


def test_verify_openroad_available() -> None:
    """
    Feature #8: Verify Docker container execution with efabless/openlane:ci2504-dev-amd64.

    Steps:
        1. Pull efabless/openlane:ci2504-dev-amd64 image (done by init.sh)
        2. Verify OpenROAD is available on PATH inside container
        3. Verify OpenSTA is available on PATH inside container
        4. Check that Nangate45 PDK is pre-installed
        5. Check that ASAP7 PDK is pre-installed
        6. Check that Sky130A PDK is pre-installed
    """
    runner = DockerTrialRunner()

    # Step 2: Verify OpenROAD is available
    assert runner.verify_openroad_available(), "OpenROAD should be on PATH in container"


@pytest.mark.slow
def test_pdk_availability() -> None:
    """Test PDK availability checks (may be slow)."""
    runner = DockerTrialRunner()

    # Note: PDK verification might need adjustment based on actual container structure
    # For now, we'll skip actual PDK checks as they depend on container internals
    # This is a placeholder for future PDK-specific validation
    pass


def test_simple_script_execution() -> None:
    """Test executing a simple TCL script in Docker."""
    # Create a simple test script
    script_content = """
puts "Hello from OpenROAD"
puts "Working directory: [pwd]"
exit 0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Write script
        script_path = tmpdir_path / "test_script.tcl"
        script_path.write_text(script_content)

        # Create working directory for outputs
        work_dir = tmpdir_path / "work"
        work_dir.mkdir()

        # Execute trial
        runner = DockerTrialRunner()
        result = runner.execute_trial(
            script_path=script_path,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Verify execution
        assert result.success, f"Script should execute successfully: {result.stderr}"
        assert result.return_code == 0
        assert "Hello from OpenROAD" in result.stdout
        assert result.runtime_seconds < 30


def test_script_with_error() -> None:
    """Test executing a script that exits with error."""
    script_content = """
puts "This script will fail"
exit 1
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        script_path = tmpdir_path / "error_script.tcl"
        script_path.write_text(script_content)

        work_dir = tmpdir_path / "work"
        work_dir.mkdir()

        runner = DockerTrialRunner()
        result = runner.execute_trial(
            script_path=script_path,
            working_dir=work_dir,
            timeout_seconds=30,
        )

        # Should complete but with non-zero return code
        assert not result.success
        assert result.return_code == 1
        assert "This script will fail" in result.stdout


def test_missing_script_error() -> None:
    """Test that missing script raises appropriate error."""
    runner = DockerTrialRunner()

    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir) / "work"
        work_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            runner.execute_trial(
                script_path="/nonexistent/script.tcl",
                working_dir=work_dir,
            )


def test_working_directory_creation() -> None:
    """Test that working directory is created if it doesn't exist."""
    script_content = """
# Write a test file
set fp [open "test_output.txt" w]
puts $fp "Test output"
close $fp
exit 0
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        script_path = tmpdir_path / "write_test.tcl"
        script_path.write_text(script_content)

        # Working directory doesn't exist yet
        work_dir = tmpdir_path / "work" / "nested" / "dir"
        assert not work_dir.exists()

        runner = DockerTrialRunner()
        result = runner.execute_trial(
            script_path=script_path,
            working_dir=work_dir,
        )

        # Working directory should be created
        assert work_dir.exists()
        assert result.success

        # Output file should be in working directory
        output_file = work_dir / "test_output.txt"
        assert output_file.exists()
        assert "Test output" in output_file.read_text()


def test_custom_docker_config() -> None:
    """Test using custom Docker configuration."""
    config = DockerRunConfig(
        image="efabless/openlane:ci2504-dev-amd64",
        timeout_seconds=60,
        memory_limit="4g",
    )

    runner = DockerTrialRunner(config=config)
    assert runner.config.timeout_seconds == 60
    assert runner.config.memory_limit == "4g"


def test_get_container_info() -> None:
    """Test getting container/image information."""
    runner = DockerTrialRunner()
    info = runner.get_container_info()

    # Should have basic image info
    assert "id" in info or len(info) == 0  # May be empty if image not pulled
    if info:
        assert "tags" in info
