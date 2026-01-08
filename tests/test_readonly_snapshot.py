"""Tests for read-only snapshot mounting to prevent accidental modification."""

import tempfile
from pathlib import Path

import pytest

from trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner


class TestReadOnlySnapshotMounting:
    """Test that snapshots can be mounted read-only to prevent modification."""

    def test_readonly_snapshot_flag_defaults_to_true(self) -> None:
        """Test that readonly_snapshot defaults to True for safety."""
        config = DockerRunConfig()
        assert config.readonly_snapshot is True

    def test_readonly_snapshot_can_be_disabled(self) -> None:
        """Test that readonly_snapshot can be explicitly disabled if needed."""
        config = DockerRunConfig(readonly_snapshot=False)
        assert config.readonly_snapshot is False

    def test_mount_snapshot_readonly_prevents_writes(self) -> None:
        """
        Test that mounting snapshot as read-only prevents file modification.

        Feature steps covered:
        - Step 1: Mount base snapshot as read-only in container
        - Step 2: Execute trial
        - Step 3: Verify trial can read snapshot files
        - Step 4: Verify trial cannot modify snapshot files
        - Step 5: Confirm snapshot integrity is preserved
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create snapshot directory with a test file
            snapshot_dir = tmpdir / "snapshot"
            snapshot_dir.mkdir()
            test_file = snapshot_dir / "test.txt"
            test_file.write_text("original content")

            # Create working directory
            working_dir = tmpdir / "work"
            working_dir.mkdir()

            # Create TCL script that tries to:
            # 1. Read the file (should succeed)
            # 2. Modify the file (should fail with read-only error)
            script_dir = tmpdir / "scripts"
            script_dir.mkdir()
            script = script_dir / "test.tcl"
            script.write_text("""
# Try to read the file (should work)
set fp [open "/snapshot/test.txt" r]
set content [read $fp]
close $fp
puts "Read content: $content"

# Try to write to the file (should fail)
if {[catch {
    set fp [open "/snapshot/test.txt" w]
    puts $fp "modified content"
    close $fp
} err]} {
    puts "Write failed as expected: $err"
    # Write success indicator to working directory
    set fp [open "/work/readonly_verified.txt" w]
    puts $fp "READONLY_VERIFIED"
    close $fp
} else {
    puts "ERROR: Write should have failed but succeeded!"
    exit 1
}
""")

            # Execute with read-only snapshot (default)
            config = DockerRunConfig(readonly_snapshot=True)
            runner = DockerTrialRunner(config)

            result = runner.execute_trial(
                script_path=script,
                working_dir=working_dir,
                snapshot_dir=snapshot_dir,
            )

            # Verify execution succeeded
            assert result.success, f"Trial should succeed. stderr: {result.stderr}"

            # Verify read operation worked
            assert "Read content: original content" in result.stdout

            # Verify write operation was blocked
            assert "Write failed as expected" in result.stdout

            # Verify the verification file was created
            verification_file = working_dir / "readonly_verified.txt"
            assert verification_file.exists()
            assert "READONLY_VERIFIED" in verification_file.read_text()

            # Most importantly: verify snapshot file was NOT modified
            assert test_file.read_text() == "original content"

    def test_mount_snapshot_readwrite_allows_writes(self) -> None:
        """Test that disabling read-only protection allows writes (for special cases)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create snapshot directory with a test file
            snapshot_dir = tmpdir / "snapshot"
            snapshot_dir.mkdir()
            test_file = snapshot_dir / "test.txt"
            test_file.write_text("original content")

            # Create working directory
            working_dir = tmpdir / "work"
            working_dir.mkdir()

            # Create TCL script that modifies the file
            script_dir = tmpdir / "scripts"
            script_dir.mkdir()
            script = script_dir / "test.tcl"
            script.write_text("""
# Write to the file
set fp [open "/snapshot/test.txt" w]
puts $fp "modified content"
close $fp
puts "Write succeeded"
""")

            # Execute with read-write snapshot (explicitly disabled protection)
            config = DockerRunConfig(readonly_snapshot=False)
            runner = DockerTrialRunner(config)

            result = runner.execute_trial(
                script_path=script,
                working_dir=working_dir,
                snapshot_dir=snapshot_dir,
            )

            # Verify execution succeeded
            assert result.success, f"Trial should succeed. stderr: {result.stderr}"
            assert "Write succeeded" in result.stdout

            # Verify snapshot file WAS modified (because protection was disabled)
            assert test_file.read_text() == "modified content\n"

    def test_readonly_snapshot_can_read_files(self) -> None:
        """Test that read-only snapshot still allows reading files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create snapshot with multiple files
            snapshot_dir = tmpdir / "snapshot"
            snapshot_dir.mkdir()
            (snapshot_dir / "file1.txt").write_text("content1")
            (snapshot_dir / "file2.txt").write_text("content2")
            subdir = snapshot_dir / "subdir"
            subdir.mkdir()
            (subdir / "file3.txt").write_text("content3")

            # Create working directory
            working_dir = tmpdir / "work"
            working_dir.mkdir()

            # Create TCL script that reads multiple files
            script_dir = tmpdir / "scripts"
            script_dir.mkdir()
            script = script_dir / "test.tcl"
            script.write_text("""
# Read all files
set fp1 [open "/snapshot/file1.txt" r]
puts "File1: [read $fp1]"
close $fp1

set fp2 [open "/snapshot/file2.txt" r]
puts "File2: [read $fp2]"
close $fp2

set fp3 [open "/snapshot/subdir/file3.txt" r]
puts "File3: [read $fp3]"
close $fp3

puts "All reads successful"
""")

            # Execute with read-only snapshot
            config = DockerRunConfig(readonly_snapshot=True)
            runner = DockerTrialRunner(config)

            result = runner.execute_trial(
                script_path=script,
                working_dir=working_dir,
                snapshot_dir=snapshot_dir,
            )

            # Verify all reads succeeded
            assert result.success
            assert "File1: content1" in result.stdout
            assert "File2: content2" in result.stdout
            assert "File3: content3" in result.stdout
            assert "All reads successful" in result.stdout

    def test_readonly_snapshot_prevents_file_creation(self) -> None:
        """Test that read-only snapshot prevents creating new files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create snapshot directory
            snapshot_dir = tmpdir / "snapshot"
            snapshot_dir.mkdir()

            # Create working directory
            working_dir = tmpdir / "work"
            working_dir.mkdir()

            # Create TCL script that tries to create a new file
            script_dir = tmpdir / "scripts"
            script_dir.mkdir()
            script = script_dir / "test.tcl"
            script.write_text("""
# Try to create a new file in snapshot
if {[catch {
    set fp [open "/snapshot/newfile.txt" w]
    puts $fp "new content"
    close $fp
} err]} {
    puts "Create failed as expected: $err"
    # Success - write verification
    set fp [open "/work/create_blocked.txt" w]
    puts $fp "CREATE_BLOCKED"
    close $fp
} else {
    puts "ERROR: File creation should have failed!"
    exit 1
}
""")

            # Execute with read-only snapshot
            config = DockerRunConfig(readonly_snapshot=True)
            runner = DockerTrialRunner(config)

            result = runner.execute_trial(
                script_path=script,
                working_dir=working_dir,
                snapshot_dir=snapshot_dir,
            )

            # Verify file creation was blocked
            assert result.success
            assert "Create failed as expected" in result.stdout
            verification_file = working_dir / "create_blocked.txt"
            assert verification_file.exists()

            # Verify no file was created in snapshot
            assert not (snapshot_dir / "newfile.txt").exists()

    def test_readonly_snapshot_prevents_file_deletion(self) -> None:
        """Test that read-only snapshot prevents deleting files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create snapshot with a file
            snapshot_dir = tmpdir / "snapshot"
            snapshot_dir.mkdir()
            test_file = snapshot_dir / "test.txt"
            test_file.write_text("content")

            # Create working directory
            working_dir = tmpdir / "work"
            working_dir.mkdir()

            # Create TCL script that tries to delete the file
            script_dir = tmpdir / "scripts"
            script_dir.mkdir()
            script = script_dir / "test.tcl"
            script.write_text("""
# Try to delete file
if {[catch {
    file delete "/snapshot/test.txt"
} err]} {
    puts "Delete failed as expected: $err"
    # Success - write verification
    set fp [open "/work/delete_blocked.txt" w]
    puts $fp "DELETE_BLOCKED"
    close $fp
} else {
    puts "ERROR: File deletion should have failed!"
    exit 1
}
""")

            # Execute with read-only snapshot
            config = DockerRunConfig(readonly_snapshot=True)
            runner = DockerTrialRunner(config)

            result = runner.execute_trial(
                script_path=script,
                working_dir=working_dir,
                snapshot_dir=snapshot_dir,
            )

            # Verify deletion was blocked
            assert result.success
            assert "Delete failed as expected" in result.stdout
            verification_file = working_dir / "delete_blocked.txt"
            assert verification_file.exists()

            # Verify file still exists in snapshot
            assert test_file.exists()
            assert test_file.read_text() == "content"

    def test_snapshot_integrity_preserved_after_trial(self) -> None:
        """
        Test that snapshot remains unchanged after trial execution.

        This is the core safety guarantee.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create snapshot with known state
            snapshot_dir = tmpdir / "snapshot"
            snapshot_dir.mkdir()
            file1 = snapshot_dir / "file1.txt"
            file2 = snapshot_dir / "file2.def"
            file1.write_text("snapshot content 1")
            file2.write_text("snapshot content 2")

            # Record initial state
            initial_file1_content = file1.read_text()
            initial_file2_content = file2.read_text()
            initial_files = set(snapshot_dir.rglob("*"))

            # Create working directory
            working_dir = tmpdir / "work"
            working_dir.mkdir()

            # Create TCL script that tries various modifications
            script_dir = tmpdir / "scripts"
            script_dir.mkdir()
            script = script_dir / "test.tcl"
            script.write_text("""
# Try to modify existing files (will fail)
catch {
    set fp [open "/snapshot/file1.txt" w]
    puts $fp "MODIFIED"
    close $fp
}

# Try to create new files (will fail)
catch { file mkdir "/snapshot/newdir" }
catch {
    set fp [open "/snapshot/newfile.txt" w]
    puts $fp "NEW"
    close $fp
}

# Try to delete files (will fail)
catch { file delete "/snapshot/file2.def" }

puts "Trial completed"
""")

            # Execute with read-only snapshot
            config = DockerRunConfig(readonly_snapshot=True)
            runner = DockerTrialRunner(config)

            result = runner.execute_trial(
                script_path=script,
                working_dir=working_dir,
                snapshot_dir=snapshot_dir,
            )

            # Verify trial ran
            assert result.success
            assert "Trial completed" in result.stdout

            # CRITICAL: Verify snapshot is completely unchanged
            assert file1.read_text() == initial_file1_content
            assert file2.read_text() == initial_file2_content
            final_files = set(snapshot_dir.rglob("*"))
            assert initial_files == final_files  # No new files, no deleted files


class TestReadOnlySnapshotConfiguration:
    """Test configuration and control of read-only snapshot feature."""

    def test_default_config_uses_readonly(self) -> None:
        """Test that default configuration enables read-only snapshots."""
        runner = DockerTrialRunner()
        assert runner.config.readonly_snapshot is True

    def test_explicit_readonly_config(self) -> None:
        """Test explicitly configuring read-only snapshot."""
        config = DockerRunConfig(readonly_snapshot=True)
        runner = DockerTrialRunner(config)
        assert runner.config.readonly_snapshot is True

    def test_explicit_readwrite_config(self) -> None:
        """Test explicitly disabling read-only protection."""
        config = DockerRunConfig(readonly_snapshot=False)
        runner = DockerTrialRunner(config)
        assert runner.config.readonly_snapshot is False


class TestReadOnlySnapshotDocumentation:
    """Test that read-only snapshot feature is properly documented."""

    def test_docstring_mentions_readonly_capability(self) -> None:
        """Test that DockerTrialRunner docstring mentions read-only capability."""
        docstring = DockerTrialRunner.__doc__
        assert docstring is not None
        assert "read-only" in docstring.lower() or "readonly" in docstring.lower()

    def test_execute_trial_docstring_mentions_readonly(self) -> None:
        """Test that execute_trial docstring mentions read-only snapshot mounting."""
        docstring = DockerTrialRunner.execute_trial.__doc__
        assert docstring is not None
        assert "readonly" in docstring.lower() or "read-only" in docstring.lower()
