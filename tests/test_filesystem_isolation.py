"""Tests for filesystem isolation verification."""

import time
from pathlib import Path

import pytest

from src.trial_runner.filesystem_isolation import (
    FilesystemIsolationVerifier,
    IsolationVerificationResult,
    IsolationViolation,
    check_working_directory_isolation,
    verify_trial_isolation,
)


class TestIsolationViolation:
    """Tests for IsolationViolation dataclass."""

    def test_violation_creation(self) -> None:
        """Test creating an isolation violation."""
        violation = IsolationViolation(
            path="/outside/file.txt",
            operation="write",
            description="File written outside working directory",
        )

        assert violation.path == "/outside/file.txt"
        assert violation.operation == "write"
        assert "outside working directory" in violation.description


class TestIsolationVerificationResult:
    """Tests for IsolationVerificationResult dataclass."""

    def test_result_creation_isolated(self) -> None:
        """Test creating a result for successful isolation."""
        result = IsolationVerificationResult(
            isolated=True,
            violations=[],
            working_dir="/work",
            files_created=["output.txt"],
            files_modified=[],
        )

        assert result.isolated is True
        assert len(result.violations) == 0
        assert len(result.files_created) == 1

    def test_result_creation_violated(self) -> None:
        """Test creating a result with violations."""
        violation = IsolationViolation(
            path="/tmp/bad.txt",
            operation="create",
            description="Created file in /tmp",
        )

        result = IsolationVerificationResult(
            isolated=False,
            violations=[violation],
            working_dir="/work",
            files_created=[],
            files_modified=[],
            error_message="Isolation violated",
        )

        assert result.isolated is False
        assert len(result.violations) == 1
        assert result.error_message is not None


class TestFilesystemIsolationVerifier:
    """Tests for FilesystemIsolationVerifier."""

    def test_verifier_initialization(self, tmp_path: Path) -> None:
        """Test verifier initialization."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        verifier = FilesystemIsolationVerifier(working_dir)

        assert verifier.working_dir == working_dir.resolve()
        assert working_dir.resolve() in verifier.allowed_dirs

    def test_verifier_with_additional_allowed_dirs(self, tmp_path: Path) -> None:
        """Test verifier with additional allowed directories."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        verifier = FilesystemIsolationVerifier(
            working_dir, allowed_dirs=[temp_dir]
        )

        assert working_dir.resolve() in verifier.allowed_dirs
        assert temp_dir.resolve() in verifier.allowed_dirs

    def test_capture_before_state_empty_dir(self, tmp_path: Path) -> None:
        """Test capturing state of empty directory."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        assert len(verifier._before_state) == 0

    def test_capture_before_state_with_files(self, tmp_path: Path) -> None:
        """Test capturing state with existing files."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        (working_dir / "existing.txt").write_text("content")

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        assert len(verifier._before_state) > 0
        assert any("existing.txt" in str(p) for p in verifier._before_state)

    def test_capture_after_state(self, tmp_path: Path) -> None:
        """Test capturing state after execution."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        # Simulate trial execution creating a file
        (working_dir / "output.txt").write_text("result")

        verifier.capture_after_state()

        assert len(verifier._after_state) > 0


class TestIsolationVerification:
    """Tests for isolation verification logic."""

    def test_verify_no_changes(self, tmp_path: Path) -> None:
        """Test verification when no files are created/modified."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()
        verifier.capture_after_state()

        result = verifier.verify_isolation()

        assert result.isolated is True
        assert len(result.violations) == 0
        assert len(result.files_created) == 0
        assert len(result.files_modified) == 0

    def test_verify_file_created_in_working_dir(self, tmp_path: Path) -> None:
        """Test verification when file is created in working directory."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        # Create file in working directory
        (working_dir / "output.txt").write_text("result")

        verifier.capture_after_state()
        result = verifier.verify_isolation()

        assert result.isolated is True
        assert len(result.violations) == 0
        assert len(result.files_created) == 1
        assert "output.txt" in result.files_created[0]

    def test_verify_file_modified_in_working_dir(self, tmp_path: Path) -> None:
        """Test verification when file is modified in working directory."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        test_file = working_dir / "file.txt"
        test_file.write_text("initial")

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        # Sleep briefly to ensure mtime changes
        time.sleep(0.01)

        # Modify file
        test_file.write_text("modified")

        verifier.capture_after_state()
        result = verifier.verify_isolation()

        assert result.isolated is True
        assert len(result.violations) == 0
        assert len(result.files_modified) == 1

    def test_verify_subdirectory_creation(self, tmp_path: Path) -> None:
        """Test verification when subdirectories are created."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        # Create subdirectory and file
        subdir = working_dir / "subdir"
        subdir.mkdir()
        (subdir / "output.txt").write_text("result")

        verifier.capture_after_state()
        result = verifier.verify_isolation()

        assert result.isolated is True
        assert len(result.violations) == 0
        assert len(result.files_created) >= 1


class TestIsolationViolations:
    """Tests for detecting isolation violations."""

    def test_detect_file_created_outside_working_dir(self, tmp_path: Path) -> None:
        """Test detection of file created outside working directory."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()

        # Create verifier that scans both directories
        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state(scan_paths=[working_dir, outside_dir])

        # Create file outside working directory
        (outside_dir / "bad.txt").write_text("violation")

        verifier.capture_after_state(scan_paths=[working_dir, outside_dir])
        result = verifier.verify_isolation()

        assert result.isolated is False
        assert len(result.violations) >= 1
        assert any(v.operation == "create" for v in result.violations)
        assert result.error_message is not None

    def test_detect_file_modified_outside_working_dir(self, tmp_path: Path) -> None:
        """Test detection of file modified outside working directory."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "existing.txt"
        outside_file.write_text("initial")

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state(scan_paths=[working_dir, outside_dir])

        time.sleep(0.01)  # Ensure mtime changes

        # Modify file outside working directory
        outside_file.write_text("modified")

        verifier.capture_after_state(scan_paths=[working_dir, outside_dir])
        result = verifier.verify_isolation()

        assert result.isolated is False
        assert len(result.violations) >= 1
        assert any(v.operation == "modify" for v in result.violations)

    def test_allowed_dirs_dont_cause_violations(self, tmp_path: Path) -> None:
        """Test that writes to allowed directories don't cause violations."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        temp_dir = tmp_path / "temp"
        temp_dir.mkdir()

        # temp_dir is explicitly allowed
        verifier = FilesystemIsolationVerifier(
            working_dir, allowed_dirs=[temp_dir]
        )
        verifier.capture_before_state()

        # Create files in both directories
        (working_dir / "work_output.txt").write_text("work")
        (temp_dir / "temp_output.txt").write_text("temp")

        verifier.capture_after_state()
        result = verifier.verify_isolation()

        assert result.isolated is True
        assert len(result.violations) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_verify_trial_isolation(self, tmp_path: Path) -> None:
        """Test verify_trial_isolation convenience function."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        (working_dir / "output.txt").write_text("result")

        result = verify_trial_isolation(working_dir)

        assert isinstance(result, IsolationVerificationResult)
        assert result.working_dir == str(working_dir)

    def test_check_working_directory_isolation_exists(self, tmp_path: Path) -> None:
        """Test check for existing writable directory."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        result = check_working_directory_isolation(working_dir)

        assert result.isolated is True
        assert len(result.violations) == 0

    def test_check_working_directory_isolation_missing(self, tmp_path: Path) -> None:
        """Test check for non-existent directory."""
        working_dir = tmp_path / "nonexistent"

        result = check_working_directory_isolation(working_dir)

        assert result.isolated is False
        assert len(result.violations) > 0
        assert any(v.operation == "access" for v in result.violations)
        assert "does not exist" in result.error_message

    def test_check_working_directory_isolation_readonly(self, tmp_path: Path) -> None:
        """Test check for read-only directory."""
        working_dir = tmp_path / "readonly"
        working_dir.mkdir()

        # Make directory read-only (Unix-like systems)
        import os
        try:
            os.chmod(working_dir, 0o444)

            result = check_working_directory_isolation(working_dir)

            assert result.isolated is False
            assert len(result.violations) > 0
            assert any(v.operation == "write" for v in result.violations)
        finally:
            # Restore permissions for cleanup
            os.chmod(working_dir, 0o755)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_nonexistent_scan_path(self, tmp_path: Path) -> None:
        """Test scanning non-existent path doesn't crash."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        nonexistent = tmp_path / "nonexistent"

        verifier = FilesystemIsolationVerifier(working_dir)

        # Should not raise
        verifier.capture_before_state(scan_paths=[nonexistent])
        verifier.capture_after_state(scan_paths=[nonexistent])

        result = verifier.verify_isolation()
        assert result.isolated is True

    def test_permission_denied_handling(self, tmp_path: Path) -> None:
        """Test handling of permission-denied errors during scan."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()
        restricted = tmp_path / "restricted"
        restricted.mkdir()
        (restricted / "file.txt").write_text("content")

        import os
        try:
            # Make directory inaccessible
            os.chmod(restricted, 0o000)

            verifier = FilesystemIsolationVerifier(working_dir)

            # Should not raise
            verifier.capture_before_state(scan_paths=[working_dir, restricted])
            verifier.capture_after_state(scan_paths=[working_dir, restricted])

            result = verifier.verify_isolation()
            # Should succeed even though we couldn't scan restricted
            assert isinstance(result, IsolationVerificationResult)
        finally:
            # Restore permissions
            os.chmod(restricted, 0o755)

    def test_many_files_performance(self, tmp_path: Path) -> None:
        """Test performance with many files (should complete quickly)."""
        working_dir = tmp_path / "work"
        working_dir.mkdir()

        # Create many files
        for i in range(100):
            (working_dir / f"file_{i}.txt").write_text(f"content {i}")

        verifier = FilesystemIsolationVerifier(working_dir)

        import time
        start = time.time()

        verifier.capture_before_state()
        verifier.capture_after_state()
        result = verifier.verify_isolation()

        elapsed = time.time() - start

        assert result.isolated is True
        assert elapsed < 1.0  # Should be fast


class TestRealWorldScenarios:
    """Tests simulating real trial execution scenarios."""

    def test_typical_trial_execution(self, tmp_path: Path) -> None:
        """Test typical trial execution scenario."""
        working_dir = tmp_path / "trial_0"
        working_dir.mkdir()

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        # Simulate trial creating typical outputs
        (working_dir / "trial.log").write_text("Execution log")
        (working_dir / "metrics.json").write_text('{"wns": -100}')
        reports_dir = working_dir / "reports"
        reports_dir.mkdir()
        (reports_dir / "timing.rpt").write_text("Timing report")

        verifier.capture_after_state()
        result = verifier.verify_isolation()

        assert result.isolated is True
        assert len(result.files_created) >= 3
        assert result.error_message is None

    def test_trial_with_snapshot_access(self, tmp_path: Path) -> None:
        """Test trial that reads from snapshot but only writes to working dir."""
        working_dir = tmp_path / "trial_0"
        working_dir.mkdir()
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()
        (snapshot_dir / "design.v").write_text("module design; endmodule")

        # Snapshot is read-only, not in allowed dirs
        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state()

        # Trial reads snapshot (no modification)
        _ = (snapshot_dir / "design.v").read_text()

        # Trial writes to working dir
        (working_dir / "output.def").write_text("DESIGN output ;")

        verifier.capture_after_state()
        result = verifier.verify_isolation()

        assert result.isolated is True

    def test_trial_attempting_snapshot_modification(self, tmp_path: Path) -> None:
        """Test detection when trial attempts to modify snapshot."""
        working_dir = tmp_path / "trial_0"
        working_dir.mkdir()
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()
        snapshot_file = snapshot_dir / "design.v"
        snapshot_file.write_text("module design; endmodule")

        verifier = FilesystemIsolationVerifier(working_dir)
        verifier.capture_before_state(scan_paths=[working_dir, snapshot_dir])

        time.sleep(0.01)

        # Trial attempts to modify snapshot (violation!)
        snapshot_file.write_text("module design_modified; endmodule")

        verifier.capture_after_state(scan_paths=[working_dir, snapshot_dir])
        result = verifier.verify_isolation()

        assert result.isolated is False
        assert len(result.violations) >= 1
        assert "design.v" in str(result.violations[0].path)
