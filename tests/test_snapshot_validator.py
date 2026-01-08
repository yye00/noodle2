"""Tests for snapshot structural integrity validation."""

import tempfile
from pathlib import Path

import pytest

from src.controller.snapshot_validator import (
    SnapshotFileType,
    SnapshotRequirement,
    SnapshotValidationResult,
    SnapshotValidator,
    validate_snapshot,
)


class TestSnapshotRequirement:
    """Tests for SnapshotRequirement dataclass."""

    def test_default_patterns_verilog(self) -> None:
        """Test default patterns for Verilog files."""
        req = SnapshotRequirement(file_type=SnapshotFileType.VERILOG)
        assert req.patterns == ["*.v", "*.sv"]
        assert req.required is True
        assert req.min_count == 1

    def test_default_patterns_sdc(self) -> None:
        """Test default patterns for SDC files."""
        req = SnapshotRequirement(file_type=SnapshotFileType.SDC)
        assert req.patterns == ["*.sdc"]

    def test_custom_patterns(self) -> None:
        """Test custom patterns override defaults."""
        req = SnapshotRequirement(
            file_type=SnapshotFileType.VERILOG,
            patterns=["design.v"],
            min_count=1,
        )
        assert req.patterns == ["design.v"]

    def test_optional_requirement(self) -> None:
        """Test optional requirement."""
        req = SnapshotRequirement(
            file_type=SnapshotFileType.LEF,
            required=False,
        )
        assert req.required is False


class TestSnapshotValidatorBasic:
    """Basic tests for SnapshotValidator."""

    def test_validator_default_requirements(self) -> None:
        """Test validator initializes with default requirements."""
        validator = SnapshotValidator()
        assert len(validator.requirements) > 0
        # Should include Verilog and SDC as required
        file_types = {req.file_type for req in validator.requirements}
        assert SnapshotFileType.VERILOG in file_types
        assert SnapshotFileType.SDC in file_types

    def test_validator_custom_requirements(self) -> None:
        """Test validator with custom requirements."""
        reqs = [
            SnapshotRequirement(file_type=SnapshotFileType.VERILOG),
        ]
        validator = SnapshotValidator(requirements=reqs)
        assert len(validator.requirements) == 1
        assert validator.requirements[0].file_type == SnapshotFileType.VERILOG

    def test_nonexistent_directory(self) -> None:
        """Test validation fails for non-existent directory."""
        validator = SnapshotValidator()
        result = validator.validate("/nonexistent/path")

        assert result.valid is False
        assert "does not exist" in result.error_message

    def test_not_a_directory(self, tmp_path: Path) -> None:
        """Test validation fails if path is not a directory."""
        # Create a file instead of directory
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("content")

        validator = SnapshotValidator()
        result = validator.validate(file_path)

        assert result.valid is False
        assert "not a directory" in result.error_message


class TestSnapshotValidation:
    """Tests for snapshot validation with various file combinations."""

    def test_valid_minimal_snapshot(self, tmp_path: Path) -> None:
        """Test validation passes for minimal valid snapshot."""
        # Create minimal valid snapshot (Verilog + SDC)
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is True
        assert len(result.missing_files) == 0
        assert len(result.invalid_files) == 0

    def test_missing_required_verilog(self, tmp_path: Path) -> None:
        """Test validation fails when required Verilog is missing."""
        # Only SDC, no Verilog
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is False
        assert len(result.missing_files) > 0
        assert any("verilog" in f.lower() for f in result.missing_files)

    def test_missing_required_sdc(self, tmp_path: Path) -> None:
        """Test validation fails when required SDC is missing."""
        # Only Verilog, no SDC
        (tmp_path / "design.v").write_text("module counter; endmodule")

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is False
        assert len(result.missing_files) > 0
        assert any("sdc" in f.lower() for f in result.missing_files)

    def test_empty_file_invalid(self, tmp_path: Path) -> None:
        """Test validation fails for empty files."""
        (tmp_path / "design.v").write_text("")  # Empty file
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is False
        assert len(result.invalid_files) > 0

    def test_unreadable_file(self, tmp_path: Path) -> None:
        """Test validation handles unreadable files gracefully."""
        verilog_path = tmp_path / "design.v"
        verilog_path.write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        # Make file unreadable (on Unix-like systems)
        import os

        try:
            os.chmod(verilog_path, 0o000)

            validator = SnapshotValidator()
            result = validator.validate(tmp_path)

            # Should either mark as invalid or fail validation
            assert result.valid is False or len(result.invalid_files) > 0
        finally:
            # Restore permissions for cleanup
            os.chmod(verilog_path, 0o644)

    def test_multiple_verilog_files(self, tmp_path: Path) -> None:
        """Test validation handles multiple Verilog files."""
        (tmp_path / "module1.v").write_text("module module1; endmodule")
        (tmp_path / "module2.v").write_text("module module2; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is True

    def test_systemverilog_extension(self, tmp_path: Path) -> None:
        """Test validation recognizes .sv files as Verilog."""
        (tmp_path / "design.sv").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is True

    def test_optional_files_warning(self, tmp_path: Path) -> None:
        """Test optional missing files generate warnings, not errors."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")
        # No TCL file (which is optional)

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is True
        # May have warnings for optional files
        # (this depends on default requirements)


class TestSnapshotHash:
    """Tests for snapshot hash computation."""

    def test_hash_computed_for_valid_snapshot(self, tmp_path: Path) -> None:
        """Test hash is computed for valid snapshot."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(compute_hash=True)
        result = validator.validate(tmp_path)

        assert result.valid is True
        assert result.snapshot_hash is not None
        assert len(result.snapshot_hash) == 64  # SHA256 hex digest

    def test_hash_not_computed_when_disabled(self, tmp_path: Path) -> None:
        """Test hash is not computed when disabled."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(compute_hash=False)
        result = validator.validate(tmp_path)

        assert result.valid is True
        assert result.snapshot_hash is None

    def test_hash_deterministic(self, tmp_path: Path) -> None:
        """Test hash is deterministic for same snapshot."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(compute_hash=True)
        result1 = validator.validate(tmp_path)
        result2 = validator.validate(tmp_path)

        assert result1.snapshot_hash == result2.snapshot_hash

    def test_hash_different_for_different_content(self, tmp_path: Path) -> None:
        """Test hash changes when snapshot content changes."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(compute_hash=True)
        result1 = validator.validate(tmp_path)

        # Modify content
        (tmp_path / "design.v").write_text("module counter_v2; endmodule")
        result2 = validator.validate(tmp_path)

        assert result1.snapshot_hash != result2.snapshot_hash

    def test_hash_includes_all_files(self, tmp_path: Path) -> None:
        """Test hash includes all files in snapshot."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(compute_hash=True)
        result1 = validator.validate(tmp_path)

        # Add another file
        (tmp_path / "extra.tcl").write_text("# TCL script")
        result2 = validator.validate(tmp_path)

        assert result1.snapshot_hash != result2.snapshot_hash


class TestCustomRequirements:
    """Tests for custom snapshot requirements."""

    def test_custom_minimum_count(self, tmp_path: Path) -> None:
        """Test custom minimum file count requirement."""
        # Require at least 2 Verilog files
        reqs = [
            SnapshotRequirement(
                file_type=SnapshotFileType.VERILOG,
                min_count=2,
            ),
            SnapshotRequirement(
                file_type=SnapshotFileType.SDC,
                min_count=1,
            ),
        ]

        # Only 1 Verilog file
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(requirements=reqs)
        result = validator.validate(tmp_path)

        assert result.valid is False
        assert len(result.missing_files) > 0

    def test_custom_pattern(self, tmp_path: Path) -> None:
        """Test custom file pattern requirement."""
        # Require specific filename
        reqs = [
            SnapshotRequirement(
                file_type=SnapshotFileType.VERILOG,
                patterns=["top.v"],
                min_count=1,
            ),
            SnapshotRequirement(
                file_type=SnapshotFileType.SDC,
                min_count=1,
            ),
        ]

        # Wrong filename
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(requirements=reqs)
        result = validator.validate(tmp_path)

        assert result.valid is False

        # Correct filename
        (tmp_path / "top.v").write_text("module top; endmodule")
        result2 = validator.validate(tmp_path)

        assert result2.valid is True

    def test_no_requirements(self, tmp_path: Path) -> None:
        """Test validator with empty requirements accepts any directory."""
        # Create a minimal valid snapshot
        (tmp_path / "design.v").write_text("module counter; endmodule")

        # Empty requirements list means no checks
        validator = SnapshotValidator(requirements=[])
        result = validator.validate(tmp_path)

        # Should pass because there are no requirements
        assert result.valid is True
        assert len(result.missing_files) == 0


class TestConvenienceFunction:
    """Tests for convenience function."""

    def test_validate_snapshot_function(self, tmp_path: Path) -> None:
        """Test validate_snapshot convenience function."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        result = validate_snapshot(tmp_path)

        assert isinstance(result, SnapshotValidationResult)
        assert result.valid is True

    def test_validate_snapshot_with_custom_requirements(
        self, tmp_path: Path
    ) -> None:
        """Test validate_snapshot with custom requirements."""
        (tmp_path / "design.v").write_text("module counter; endmodule")

        reqs = [
            SnapshotRequirement(
                file_type=SnapshotFileType.VERILOG,
                min_count=1,
            ),
        ]

        result = validate_snapshot(tmp_path, requirements=reqs)

        assert result.valid is True


class TestRealSnapshots:
    """Tests using actual project snapshots."""

    def test_nangate45_base_snapshot(self) -> None:
        """Test validation of actual Nangate45 base snapshot."""
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base snapshot not available")

        result = validate_snapshot(snapshot_path)

        # Should be valid or have clear diagnostics
        assert isinstance(result, SnapshotValidationResult)
        if not result.valid:
            print(f"Validation failed: {result.error_message}")
            print(f"Missing files: {result.missing_files}")
            print(f"Invalid files: {result.invalid_files}")

    def test_sky130_base_snapshot(self) -> None:
        """Test validation of actual Sky130 base snapshot."""
        snapshot_path = Path("studies/sky130_base")
        if not snapshot_path.exists():
            pytest.skip("Sky130 base snapshot not available")

        result = validate_snapshot(snapshot_path)

        assert isinstance(result, SnapshotValidationResult)
        if not result.valid:
            print(f"Validation failed: {result.error_message}")


class TestErrorMessages:
    """Tests for error message clarity."""

    def test_error_message_lists_missing_files(self, tmp_path: Path) -> None:
        """Test error message clearly lists missing files."""
        # Empty directory
        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is False
        assert result.error_message is not None
        assert "verilog" in result.error_message.lower() or "Missing files" in result.error_message

    def test_error_message_lists_invalid_files(self, tmp_path: Path) -> None:
        """Test error message lists invalid files."""
        (tmp_path / "design.v").write_text("")  # Empty = invalid
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator()
        result = validator.validate(tmp_path)

        assert result.valid is False
        assert result.error_message is not None
        assert "invalid" in result.error_message.lower() or "design.v" in result.error_message


class TestSubdirectories:
    """Tests for snapshots with subdirectories."""

    def test_files_in_subdirectories(self, tmp_path: Path) -> None:
        """Test validation finds files in subdirectories."""
        # Create subdirectory structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        (src_dir / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        # Default glob patterns should find files recursively
        reqs = [
            SnapshotRequirement(
                file_type=SnapshotFileType.VERILOG,
                patterns=["**/*.v"],  # Recursive pattern
                min_count=1,
            ),
            SnapshotRequirement(
                file_type=SnapshotFileType.SDC,
                patterns=["*.sdc"],
                min_count=1,
            ),
        ]

        validator = SnapshotValidator(requirements=reqs)
        result = validator.validate(tmp_path)

        assert result.valid is True

    def test_hash_includes_subdirectories(self, tmp_path: Path) -> None:
        """Test snapshot hash includes subdirectory files."""
        (tmp_path / "design.v").write_text("module counter; endmodule")
        (tmp_path / "design.sdc").write_text("create_clock -period 10")

        validator = SnapshotValidator(compute_hash=True)
        result1 = validator.validate(tmp_path)

        # Add file in subdirectory
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "extra.tcl").write_text("# Extra")

        result2 = validator.validate(tmp_path)

        assert result1.snapshot_hash != result2.snapshot_hash
