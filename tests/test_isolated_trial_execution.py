"""Tests for isolated trial execution with immutable snapshots."""

import tempfile
from pathlib import Path

import pytest

from src.trial_runner.trial import Trial, TrialConfig


def test_snapshot_copied_to_trial_directory():
    """Test that snapshot is copied to trial directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a simple snapshot
        snapshot_dir = tmpdir / "snapshot_src"
        snapshot_dir.mkdir()
        (snapshot_dir / "design.v").write_text("module test; endmodule")
        (snapshot_dir / "constraints.sdc").write_text("set_clock_period 10")

        # Create a minimal script
        script_path = tmpdir / "test.tcl"
        script_path.write_text("puts 'test'")

        # Create trial
        artifacts_root = tmpdir / "artifacts"
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=snapshot_dir,
        )

        trial = Trial(config, artifacts_root=artifacts_root)

        # Copy snapshot manually (without executing)
        snapshot_copy = trial._copy_snapshot_to_trial_dir()

        # Verify snapshot was copied to trial directory
        assert snapshot_copy is not None
        assert snapshot_copy.exists()
        assert snapshot_copy == trial.trial_dir / "snapshot"

        # Verify all files were copied
        assert (snapshot_copy / "design.v").exists()
        assert (snapshot_copy / "constraints.sdc").exists()

        # Verify content matches
        assert (snapshot_copy / "design.v").read_text() == "module test; endmodule"
        assert (snapshot_copy / "constraints.sdc").read_text() == "set_clock_period 10"


def test_base_snapshot_remains_unmodified():
    """Test that the base snapshot is never modified during trial execution."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a snapshot with a marker file
        snapshot_dir = tmpdir / "snapshot_src"
        snapshot_dir.mkdir()
        marker_file = snapshot_dir / "marker.txt"
        original_content = "original content"
        marker_file.write_text(original_content)

        # Create a script that tries to modify files in the snapshot
        script_path = tmpdir / "test.tcl"
        script_path.write_text("puts 'test'")

        # Create trial
        artifacts_root = tmpdir / "artifacts"
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=snapshot_dir,
        )

        trial = Trial(config, artifacts_root=artifacts_root)

        # Copy snapshot
        snapshot_copy = trial._copy_snapshot_to_trial_dir()

        # Modify the copied snapshot (simulating trial execution)
        (snapshot_copy / "marker.txt").write_text("modified content")
        (snapshot_copy / "new_file.txt").write_text("new file")

        # Verify original snapshot is unchanged
        assert marker_file.read_text() == original_content
        assert not (snapshot_dir / "new_file.txt").exists()

        # Verify copied snapshot was modified
        assert (snapshot_copy / "marker.txt").read_text() == "modified content"
        assert (snapshot_copy / "new_file.txt").exists()


def test_trial_artifacts_written_to_trial_directory_only():
    """Test that all artifacts are written only to the trial directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create snapshot
        snapshot_dir = tmpdir / "snapshot_src"
        snapshot_dir.mkdir()
        (snapshot_dir / "design.v").write_text("module test; endmodule")

        # Create a script
        script_path = tmpdir / "test.tcl"
        script_path.write_text("puts 'test'")

        # Create trial
        artifacts_root = tmpdir / "artifacts"
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=snapshot_dir,
        )

        trial = Trial(config, artifacts_root=artifacts_root)

        # Verify trial directory exists and is in correct location
        expected_path = (
            artifacts_root
            / "test_study"
            / "test_case"
            / "stage_0"
            / "trial_0"
        )
        assert trial.trial_dir == expected_path
        assert trial.trial_dir.exists()


def test_multiple_trials_isolated_from_each_other():
    """Test that multiple trials do not interfere with each other."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create shared snapshot
        snapshot_dir = tmpdir / "snapshot_src"
        snapshot_dir.mkdir()
        (snapshot_dir / "design.v").write_text("module test; endmodule")

        # Create script
        script_path = tmpdir / "test.tcl"
        script_path.write_text("puts 'test'")

        artifacts_root = tmpdir / "artifacts"

        # Create multiple trials
        trial_0 = Trial(
            TrialConfig(
                study_name="study",
                case_name="case",
                stage_index=0,
                trial_index=0,
                script_path=script_path,
                snapshot_dir=snapshot_dir,
            ),
            artifacts_root=artifacts_root,
        )

        trial_1 = Trial(
            TrialConfig(
                study_name="study",
                case_name="case",
                stage_index=0,
                trial_index=1,
                script_path=script_path,
                snapshot_dir=snapshot_dir,
            ),
            artifacts_root=artifacts_root,
        )

        trial_2 = Trial(
            TrialConfig(
                study_name="study",
                case_name="case",
                stage_index=0,
                trial_index=2,
                script_path=script_path,
                snapshot_dir=snapshot_dir,
            ),
            artifacts_root=artifacts_root,
        )

        # Copy snapshots for each trial
        snapshot_0 = trial_0._copy_snapshot_to_trial_dir()
        snapshot_1 = trial_1._copy_snapshot_to_trial_dir()
        snapshot_2 = trial_2._copy_snapshot_to_trial_dir()

        # Verify each has its own directory
        assert snapshot_0 != snapshot_1 != snapshot_2
        assert snapshot_0.exists()
        assert snapshot_1.exists()
        assert snapshot_2.exists()

        # Modify each snapshot copy independently
        (snapshot_0 / "marker.txt").write_text("trial 0")
        (snapshot_1 / "marker.txt").write_text("trial 1")
        (snapshot_2 / "marker.txt").write_text("trial 2")

        # Verify independence
        assert (snapshot_0 / "marker.txt").read_text() == "trial 0"
        assert (snapshot_1 / "marker.txt").read_text() == "trial 1"
        assert (snapshot_2 / "marker.txt").read_text() == "trial 2"

        # Verify original snapshot is unchanged
        assert not (snapshot_dir / "marker.txt").exists()


def test_trial_with_no_snapshot():
    """Test that trials work correctly when no snapshot is provided."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create script
        script_path = tmpdir / "test.tcl"
        script_path.write_text("puts 'test'")

        # Create trial without snapshot
        artifacts_root = tmpdir / "artifacts"
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=None,  # No snapshot
        )

        trial = Trial(config, artifacts_root=artifacts_root)

        # Copy should return None
        snapshot_copy = trial._copy_snapshot_to_trial_dir()
        assert snapshot_copy is None

        # Trial directory should still exist
        assert trial.trial_dir.exists()


def test_snapshot_not_found_raises_error():
    """Test that missing snapshot directory raises appropriate error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Reference non-existent snapshot
        snapshot_dir = tmpdir / "nonexistent_snapshot"

        script_path = tmpdir / "test.tcl"
        script_path.write_text("puts 'test'")

        artifacts_root = tmpdir / "artifacts"
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=snapshot_dir,
        )

        trial = Trial(config, artifacts_root=artifacts_root)

        # Should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Snapshot directory not found"):
            trial._copy_snapshot_to_trial_dir()


def test_snapshot_with_subdirectories():
    """Test that snapshot copying preserves directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create snapshot with nested directories
        snapshot_dir = tmpdir / "snapshot_src"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        src_dir = snapshot_dir / "src"
        src_dir.mkdir()
        (src_dir / "module1.v").write_text("module m1; endmodule")
        (src_dir / "module2.v").write_text("module m2; endmodule")

        lib_dir = snapshot_dir / "lib"
        lib_dir.mkdir()
        (lib_dir / "cells.lib").write_text("library cells;")

        # Create script
        script_path = tmpdir / "test.tcl"
        script_path.write_text("puts 'test'")

        # Create trial
        artifacts_root = tmpdir / "artifacts"
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=snapshot_dir,
        )

        trial = Trial(config, artifacts_root=artifacts_root)
        snapshot_copy = trial._copy_snapshot_to_trial_dir()

        # Verify directory structure is preserved
        assert (snapshot_copy / "design.v").exists()
        assert (snapshot_copy / "src").is_dir()
        assert (snapshot_copy / "src" / "module1.v").exists()
        assert (snapshot_copy / "src" / "module2.v").exists()
        assert (snapshot_copy / "lib").is_dir()
        assert (snapshot_copy / "lib" / "cells.lib").exists()

        # Verify content
        assert (snapshot_copy / "src" / "module1.v").read_text() == "module m1; endmodule"


@pytest.mark.slow
def test_nangate45_base_case_snapshot_isolation():
    """Integration test: Nangate45 base case with snapshot isolation."""
    # This test requires the actual Nangate45 base case
    snapshot_dir = Path("studies/nangate45_base")
    script_path = snapshot_dir / "run_sta.tcl"

    if not snapshot_dir.exists() or not script_path.exists():
        pytest.skip("Nangate45 base case not available")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        artifacts_root = tmpdir / "artifacts"

        # Record original snapshot state
        original_files = set(snapshot_dir.rglob("*"))

        # Create and execute trial
        config = TrialConfig(
            study_name="nangate45",
            case_name="base",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=snapshot_dir,
        )

        trial = Trial(config, artifacts_root=artifacts_root)

        # Copy snapshot
        snapshot_copy = trial._copy_snapshot_to_trial_dir()

        # Verify snapshot was copied
        assert snapshot_copy is not None
        assert snapshot_copy.exists()
        assert (snapshot_copy / "counter.v").exists()
        assert (snapshot_copy / "counter.sdc").exists()
        assert (snapshot_copy / "run_sta.tcl").exists()

        # Verify original snapshot files are unchanged
        current_files = set(snapshot_dir.rglob("*"))
        assert original_files == current_files, "Original snapshot was modified!"
