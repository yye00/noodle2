"""Tests for snapshot integrity verification."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.snapshot import (
    SnapshotHash,
    compute_file_hash,
    compute_snapshot_hash,
    detect_snapshot_tampering,
    format_snapshot_hash_summary,
    verify_snapshot_hash,
)


class TestComputeFileHash:
    """Tests for compute_file_hash function."""

    def test_compute_file_hash_basic(self, tmp_path):
        """Test computing hash of a simple file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, Noodle 2!")

        file_hash = compute_file_hash(test_file)

        assert file_hash is not None
        assert len(file_hash) == 64  # SHA-256 produces 64-character hex digest

    def test_compute_file_hash_deterministic(self, tmp_path):
        """Test that same file produces same hash."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Deterministic content")

        hash1 = compute_file_hash(test_file)
        hash2 = compute_file_hash(test_file)

        assert hash1 == hash2

    def test_compute_file_hash_different_content(self, tmp_path):
        """Test that different content produces different hash."""
        file1 = tmp_path / "test1.txt"
        file2 = tmp_path / "test2.txt"

        file1.write_text("Content A")
        file2.write_text("Content B")

        hash1 = compute_file_hash(file1)
        hash2 = compute_file_hash(file2)

        assert hash1 != hash2

    def test_compute_file_hash_missing_file(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        missing_file = tmp_path / "nonexistent.txt"

        with pytest.raises(FileNotFoundError):
            compute_file_hash(missing_file)

    def test_compute_file_hash_large_file(self, tmp_path):
        """Test hashing large file (tests chunked reading)."""
        large_file = tmp_path / "large.dat"

        # Write 1MB file
        large_file.write_bytes(b"X" * (1024 * 1024))

        file_hash = compute_file_hash(large_file)

        assert file_hash is not None
        assert len(file_hash) == 64


class TestComputeSnapshotHash:
    """Tests for compute_snapshot_hash function."""

    def test_compute_snapshot_hash_empty_dir(self, tmp_path):
        """Test hashing empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        snapshot_hash = compute_snapshot_hash(empty_dir)

        assert snapshot_hash.hash_value is not None
        assert snapshot_hash.algorithm == "sha256"
        assert snapshot_hash.files == []

    def test_compute_snapshot_hash_single_file(self, tmp_path):
        """Test hashing directory with single file."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        snapshot_hash = compute_snapshot_hash(snapshot_dir)

        assert snapshot_hash.hash_value is not None
        assert len(snapshot_hash.files) == 1
        assert "design.v" in snapshot_hash.files

    def test_compute_snapshot_hash_multiple_files(self, tmp_path):
        """Test hashing directory with multiple files."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")
        (snapshot_dir / "constraints.sdc").write_text("create_clock -period 10")
        (snapshot_dir / "config.tcl").write_text("set design_name test")

        snapshot_hash = compute_snapshot_hash(snapshot_dir)

        assert len(snapshot_hash.files) == 3
        assert "design.v" in snapshot_hash.files
        assert "constraints.sdc" in snapshot_hash.files
        assert "config.tcl" in snapshot_hash.files

    def test_compute_snapshot_hash_nested_files(self, tmp_path):
        """Test hashing directory with nested structure."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "src").mkdir()
        (snapshot_dir / "src" / "design.v").write_text("module test; endmodule")
        (snapshot_dir / "constraints").mkdir()
        (snapshot_dir / "constraints" / "timing.sdc").write_text("create_clock")

        snapshot_hash = compute_snapshot_hash(snapshot_dir)

        assert len(snapshot_hash.files) == 2
        assert "src/design.v" in snapshot_hash.files
        assert "constraints/timing.sdc" in snapshot_hash.files

    def test_compute_snapshot_hash_deterministic(self, tmp_path):
        """Test that same snapshot produces same hash."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        hash1 = compute_snapshot_hash(snapshot_dir)
        hash2 = compute_snapshot_hash(snapshot_dir)

        assert hash1.hash_value == hash2.hash_value
        assert hash1.files == hash2.files

    def test_compute_snapshot_hash_file_order_independent(self, tmp_path):
        """Test that file creation order doesn't affect hash."""
        dir1 = tmp_path / "snapshot1"
        dir2 = tmp_path / "snapshot2"
        dir1.mkdir()
        dir2.mkdir()

        # Create files in different order
        (dir1 / "a.txt").write_text("File A")
        (dir1 / "b.txt").write_text("File B")

        (dir2 / "b.txt").write_text("File B")
        (dir2 / "a.txt").write_text("File A")

        hash1 = compute_snapshot_hash(dir1)
        hash2 = compute_snapshot_hash(dir2)

        # Hash should be same because files are sorted
        assert hash1.hash_value == hash2.hash_value

    def test_compute_snapshot_hash_content_change_detected(self, tmp_path):
        """Test that content changes produce different hash."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")
        hash1 = compute_snapshot_hash(snapshot_dir)

        # Modify content
        (snapshot_dir / "design.v").write_text("module test_modified; endmodule")
        hash2 = compute_snapshot_hash(snapshot_dir)

        assert hash1.hash_value != hash2.hash_value

    def test_compute_snapshot_hash_with_patterns(self, tmp_path):
        """Test hashing with file patterns."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")
        (snapshot_dir / "timing.sdc").write_text("create_clock")
        (snapshot_dir / "script.tcl").write_text("set design test")

        # Only hash .v files
        snapshot_hash = compute_snapshot_hash(snapshot_dir, file_patterns=["*.v"])

        assert len(snapshot_hash.files) == 1
        assert "design.v" in snapshot_hash.files
        assert "timing.sdc" not in snapshot_hash.files

    def test_compute_snapshot_hash_metadata(self, tmp_path):
        """Test that metadata is populated correctly."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "file1.txt").write_text("Content 1")
        (snapshot_dir / "file2.txt").write_text("Content 2")

        snapshot_hash = compute_snapshot_hash(snapshot_dir)

        assert snapshot_hash.metadata is not None
        assert "snapshot_dir" in snapshot_hash.metadata
        assert snapshot_hash.metadata["file_count"] == 2


class TestVerifySnapshotHash:
    """Tests for verify_snapshot_hash function."""

    def test_verify_snapshot_hash_success(self, tmp_path):
        """Test verifying unchanged snapshot."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        # Compute expected hash
        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Verify should succeed
        assert verify_snapshot_hash(snapshot_dir, expected_hash) is True

    def test_verify_snapshot_hash_content_modified(self, tmp_path):
        """Test detecting modified file content."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        # Compute original hash
        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Modify content
        (snapshot_dir / "design.v").write_text("module modified; endmodule")

        # Verification should fail
        assert verify_snapshot_hash(snapshot_dir, expected_hash) is False

    def test_verify_snapshot_hash_file_added(self, tmp_path):
        """Test detecting added file."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        # Compute original hash
        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Add new file
        (snapshot_dir / "new_file.v").write_text("module new; endmodule")

        # Verification should fail
        assert verify_snapshot_hash(snapshot_dir, expected_hash) is False

    def test_verify_snapshot_hash_file_removed(self, tmp_path):
        """Test detecting removed file."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")
        (snapshot_dir / "extra.v").write_text("module extra; endmodule")

        # Compute original hash
        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Remove file
        (snapshot_dir / "extra.v").unlink()

        # Verification should fail
        assert verify_snapshot_hash(snapshot_dir, expected_hash) is False


class TestDetectSnapshotTampering:
    """Tests for detect_snapshot_tampering function."""

    def test_detect_tampering_no_changes(self, tmp_path):
        """Test detecting no tampering."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        expected_hash = compute_snapshot_hash(snapshot_dir)

        result = detect_snapshot_tampering(snapshot_dir, expected_hash)

        assert result["tampered"] is False
        assert result["expected"] == expected_hash.hash_value
        assert result["actual"] == expected_hash.hash_value
        assert "verified" in result["message"].lower()

    def test_detect_tampering_content_modified(self, tmp_path):
        """Test detecting content modification."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Tamper with content
        (snapshot_dir / "design.v").write_text("module tampered; endmodule")

        result = detect_snapshot_tampering(snapshot_dir, expected_hash)

        assert result["tampered"] is True
        assert result["expected"] == expected_hash.hash_value
        assert result["actual"] != expected_hash.hash_value
        assert "FAILED" in result["message"]

    def test_detect_tampering_file_added(self, tmp_path):
        """Test detecting added files."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Add file
        (snapshot_dir / "malicious.v").write_text("module backdoor; endmodule")

        result = detect_snapshot_tampering(snapshot_dir, expected_hash)

        assert result["tampered"] is True
        assert "added_files" in result
        assert "malicious.v" in result["added_files"]
        assert "Added files" in result["message"]

    def test_detect_tampering_file_removed(self, tmp_path):
        """Test detecting removed files."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")
        (snapshot_dir / "important.v").write_text("module important; endmodule")

        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Remove file
        (snapshot_dir / "important.v").unlink()

        result = detect_snapshot_tampering(snapshot_dir, expected_hash)

        assert result["tampered"] is True
        assert "removed_files" in result
        assert "important.v" in result["removed_files"]
        assert "Removed files" in result["message"]

    def test_detect_tampering_snapshot_missing(self, tmp_path):
        """Test detecting completely missing snapshot."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module test; endmodule")

        expected_hash = compute_snapshot_hash(snapshot_dir)

        # Delete entire snapshot
        import shutil
        shutil.rmtree(snapshot_dir)

        result = detect_snapshot_tampering(snapshot_dir, expected_hash)

        assert result["tampered"] is True
        assert result["actual"] is None
        assert "not found" in result["message"].lower()


class TestSnapshotHash:
    """Tests for SnapshotHash dataclass."""

    def test_snapshot_hash_creation(self):
        """Test creating SnapshotHash."""
        snapshot_hash = SnapshotHash(
            hash_value="abc123",
            algorithm="sha256",
            files=["design.v", "timing.sdc"],
        )

        assert snapshot_hash.hash_value == "abc123"
        assert snapshot_hash.algorithm == "sha256"
        assert len(snapshot_hash.files) == 2

    def test_snapshot_hash_to_dict(self):
        """Test converting SnapshotHash to dictionary."""
        snapshot_hash = SnapshotHash(
            hash_value="abc123",
            algorithm="sha256",
            files=["design.v"],
        )

        data = snapshot_hash.to_dict()

        assert data["hash_value"] == "abc123"
        assert data["algorithm"] == "sha256"
        assert "design.v" in data["files"]

    def test_snapshot_hash_serializable(self):
        """Test that SnapshotHash can be JSON serialized."""
        snapshot_hash = SnapshotHash(
            hash_value="abc123",
            algorithm="sha256",
            files=["design.v"],
        )

        data = snapshot_hash.to_dict()
        json_str = json.dumps(data)

        assert json_str is not None
        assert "abc123" in json_str


class TestFormatSnapshotHashSummary:
    """Tests for format_snapshot_hash_summary function."""

    def test_format_basic_summary(self):
        """Test formatting basic snapshot hash summary."""
        snapshot_hash = SnapshotHash(
            hash_value="abc123def456",
            algorithm="sha256",
            files=["design.v", "timing.sdc"],
        )

        summary = format_snapshot_hash_summary(snapshot_hash)

        assert "=== Snapshot Integrity Hash ===" in summary
        assert "Algorithm: SHA256" in summary
        assert "Hash: abc123def456" in summary
        assert "Files: 2" in summary

    def test_format_summary_with_metadata(self):
        """Test formatting summary with metadata."""
        snapshot_hash = SnapshotHash(
            hash_value="abc123",
            files=["design.v"],
            metadata={"snapshot_dir": "/path/to/snapshot"},
        )

        summary = format_snapshot_hash_summary(snapshot_hash)

        assert "Snapshot: /path/to/snapshot" in summary


class TestSnapshotIntegration:
    """Integration tests for snapshot hashing."""

    def test_snapshot_hash_in_study_config(self):
        """Test that snapshot_hash can be stored in StudyConfig."""
        from src.controller.types import StudyConfig, SafetyDomain, StageConfig, ExecutionMode

        snapshot_hash = compute_snapshot_hash(".")  # Hash current directory
        study_config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/tmp/snapshot",
            snapshot_hash=snapshot_hash.hash_value,
        )

        assert study_config.snapshot_hash == snapshot_hash.hash_value
        assert study_config.snapshot_hash is not None

    def test_end_to_end_snapshot_verification(self, tmp_path):
        """Test complete snapshot verification workflow."""
        # Step 1: Create snapshot
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        (snapshot_dir / "design.v").write_text("module counter; endmodule")
        (snapshot_dir / "constraints.sdc").write_text("create_clock -period 10")

        # Step 2: Compute hash and store
        snapshot_hash = compute_snapshot_hash(snapshot_dir)
        stored_hash_value = snapshot_hash.hash_value

        # Step 3: Before Study execution, verify integrity
        verification_result = detect_snapshot_tampering(snapshot_dir, snapshot_hash)

        assert verification_result["tampered"] is False

        # Step 4: Simulate tampering
        (snapshot_dir / "design.v").write_text("module backdoor; endmodule")

        # Step 5: Detect tampering
        tampering_result = detect_snapshot_tampering(snapshot_dir, snapshot_hash)

        assert tampering_result["tampered"] is True
        assert "FAILED" in tampering_result["message"]
