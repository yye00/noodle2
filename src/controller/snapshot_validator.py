"""Snapshot structural integrity validation."""

import hashlib
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional


class SnapshotFileType(Enum):
    """Expected file types in a snapshot."""

    VERILOG = "verilog"  # .v files
    SDC = "sdc"  # .sdc timing constraints
    LEF = "lef"  # .lef library files
    DEF = "def"  # .def design files
    LIB = "lib"  # .lib liberty files
    TCL = "tcl"  # .tcl scripts


@dataclass
class SnapshotRequirement:
    """Requirement for a snapshot file."""

    file_type: SnapshotFileType
    required: bool = True
    patterns: list[str] = None  # Glob patterns, e.g., ["*.v", "*.sv"]
    min_count: int = 1  # Minimum number of files matching pattern

    def __post_init__(self) -> None:
        """Initialize default patterns if not provided."""
        if self.patterns is None:
            # Default patterns based on file type
            pattern_map = {
                SnapshotFileType.VERILOG: ["*.v", "*.sv"],
                SnapshotFileType.SDC: ["*.sdc"],
                SnapshotFileType.LEF: ["*.lef"],
                SnapshotFileType.DEF: ["*.def"],
                SnapshotFileType.LIB: ["*.lib"],
                SnapshotFileType.TCL: ["*.tcl"],
            }
            self.patterns = pattern_map.get(self.file_type, [])


@dataclass
class SnapshotValidationResult:
    """Result of snapshot structural validation."""

    valid: bool
    missing_files: list[str]  # Required files that are missing
    invalid_files: list[str]  # Files that failed format validation
    warnings: list[str]  # Non-fatal issues
    snapshot_hash: Optional[str] = None  # Hash of snapshot contents
    error_message: Optional[str] = None  # Overall error summary


class SnapshotValidator:
    """
    Validates snapshot structural integrity before Study execution.

    Ensures that:
    - Required files are present
    - Files are readable and parseable (basic checks)
    - Snapshot hash can be computed for provenance
    """

    def __init__(
        self,
        requirements: Optional[list[SnapshotRequirement]] = None,
        compute_hash: bool = True,
    ) -> None:
        """
        Initialize snapshot validator.

        Args:
            requirements: List of file requirements (uses defaults if None)
            compute_hash: Whether to compute snapshot hash
        """
        self.requirements = (
            self._get_default_requirements() if requirements is None else requirements
        )
        self.compute_hash = compute_hash

    @staticmethod
    def _get_default_requirements() -> list[SnapshotRequirement]:
        """Get default snapshot requirements for typical PD snapshots."""
        return [
            SnapshotRequirement(
                file_type=SnapshotFileType.VERILOG,
                required=True,
                min_count=1,
            ),
            SnapshotRequirement(
                file_type=SnapshotFileType.SDC,
                required=True,
                min_count=1,
            ),
            SnapshotRequirement(
                file_type=SnapshotFileType.TCL,
                required=False,  # Optional, but useful
                min_count=1,
            ),
            # LEF/DEF/LIB are PDK-specific and may not be in snapshot
            # (they may be provided by PDK installation)
            SnapshotRequirement(
                file_type=SnapshotFileType.LEF,
                required=False,
                min_count=0,
            ),
            SnapshotRequirement(
                file_type=SnapshotFileType.DEF,
                required=False,
                min_count=0,
            ),
        ]

    def validate(self, snapshot_path: Path | str) -> SnapshotValidationResult:
        """
        Validate snapshot structural integrity.

        Args:
            snapshot_path: Path to snapshot directory

        Returns:
            SnapshotValidationResult with validation outcomes
        """
        snapshot_path = Path(snapshot_path)

        # Check if snapshot directory exists
        if not snapshot_path.exists():
            return SnapshotValidationResult(
                valid=False,
                missing_files=[],
                invalid_files=[],
                warnings=[],
                error_message=f"Snapshot directory does not exist: {snapshot_path}",
            )

        if not snapshot_path.is_dir():
            return SnapshotValidationResult(
                valid=False,
                missing_files=[],
                invalid_files=[],
                warnings=[],
                error_message=f"Snapshot path is not a directory: {snapshot_path}",
            )

        missing_files: list[str] = []
        invalid_files: list[str] = []
        warnings: list[str] = []

        # Check each requirement
        for req in self.requirements:
            found_files = self._find_files(snapshot_path, req.patterns)

            if len(found_files) < req.min_count:
                if req.required:
                    missing_files.append(
                        f"{req.file_type.value}: expected {req.min_count}, found {len(found_files)}"
                    )
                else:
                    warnings.append(
                        f"{req.file_type.value}: expected {req.min_count}, found {len(found_files)} (optional)"
                    )

            # Validate file formats (basic check: readable and non-empty)
            for file_path in found_files:
                if not self._validate_file_format(file_path):
                    invalid_files.append(str(file_path.relative_to(snapshot_path)))

        # Compute snapshot hash if requested
        snapshot_hash = None
        if self.compute_hash and not missing_files:
            snapshot_hash = self._compute_snapshot_hash(snapshot_path)

        # Determine overall validity
        valid = len(missing_files) == 0 and len(invalid_files) == 0

        error_message = None
        if not valid:
            error_parts = []
            if missing_files:
                error_parts.append(f"Missing files: {', '.join(missing_files)}")
            if invalid_files:
                error_parts.append(f"Invalid files: {', '.join(invalid_files)}")
            error_message = "; ".join(error_parts)

        return SnapshotValidationResult(
            valid=valid,
            missing_files=missing_files,
            invalid_files=invalid_files,
            warnings=warnings,
            snapshot_hash=snapshot_hash,
            error_message=error_message,
        )

    @staticmethod
    def _find_files(snapshot_path: Path, patterns: list[str]) -> list[Path]:
        """Find files matching any of the given glob patterns."""
        found = []
        for pattern in patterns:
            found.extend(snapshot_path.glob(pattern))
        return found

    @staticmethod
    def _validate_file_format(file_path: Path) -> bool:
        """
        Validate file format (basic check: readable and non-empty).

        More sophisticated format validation (e.g., parsing Verilog syntax)
        is deferred to tool execution.
        """
        try:
            # Check if file is readable
            if not file_path.is_file():
                return False

            # Check if file is non-empty
            stat = file_path.stat()
            if stat.st_size == 0:
                return False

            # Try to read first few bytes to ensure it's readable
            with open(file_path, "rb") as f:
                f.read(1024)

            return True
        except (OSError, IOError):
            return False

    @staticmethod
    def _compute_snapshot_hash(snapshot_path: Path) -> str:
        """
        Compute deterministic hash of snapshot contents.

        This hashes all files in sorted order for reproducibility.
        """
        hasher = hashlib.sha256()

        # Get all files in snapshot (recursively)
        all_files = sorted(snapshot_path.rglob("*"))

        for file_path in all_files:
            if not file_path.is_file():
                continue

            # Hash relative path
            rel_path = file_path.relative_to(snapshot_path)
            hasher.update(str(rel_path).encode("utf-8"))

            # Hash file contents
            try:
                with open(file_path, "rb") as f:
                    while chunk := f.read(8192):
                        hasher.update(chunk)
            except (OSError, IOError):
                # Skip files that can't be read
                pass

        return hasher.hexdigest()


def validate_snapshot(
    snapshot_path: Path | str,
    requirements: Optional[list[SnapshotRequirement]] = None,
) -> SnapshotValidationResult:
    """
    Convenience function to validate a snapshot.

    Args:
        snapshot_path: Path to snapshot directory
        requirements: Optional custom requirements

    Returns:
        SnapshotValidationResult
    """
    validator = SnapshotValidator(requirements=requirements)
    return validator.validate(snapshot_path)
