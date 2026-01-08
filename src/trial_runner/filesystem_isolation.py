"""Filesystem isolation verification for trial execution."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class IsolationViolation:
    """Record of a filesystem isolation violation."""

    path: str  # Path that was accessed outside working directory
    operation: str  # Type of operation (write, create, delete)
    description: str  # Human-readable description


@dataclass
class IsolationVerificationResult:
    """Result of filesystem isolation verification."""

    isolated: bool  # True if trial stayed within bounds
    violations: list[IsolationViolation]  # List of violations detected
    working_dir: str  # Expected working directory
    files_created: list[str]  # Files created in working directory
    files_modified: list[str]  # Files modified in working directory
    error_message: Optional[str] = None  # Error if verification failed


class FilesystemIsolationVerifier:
    """
    Verifies that a trial execution stayed within its designated working directory.

    This verifier:
    - Takes snapshots of filesystem state before/after execution
    - Detects files created/modified outside the working directory
    - Identifies isolation violations
    """

    def __init__(self, working_dir: Path | str, allowed_dirs: Optional[list[Path | str]] = None) -> None:
        """
        Initialize filesystem isolation verifier.

        Args:
            working_dir: The trial's designated working directory
            allowed_dirs: Additional directories where writes are permitted (e.g., /tmp)
        """
        self.working_dir = Path(working_dir).resolve()
        self.allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [])]
        self.allowed_dirs.append(self.working_dir)

        # State tracking
        self._before_state: dict[Path, float] = {}
        self._after_state: dict[Path, float] = {}

    def capture_before_state(self, scan_paths: Optional[list[Path | str]] = None) -> None:
        """
        Capture filesystem state before trial execution.

        Args:
            scan_paths: Paths to scan (defaults to working_dir and allowed_dirs)
        """
        if scan_paths is None:
            scan_paths = self.allowed_dirs
        else:
            scan_paths = [Path(p).resolve() for p in scan_paths]

        self._before_state = {}
        for scan_path in scan_paths:
            if not scan_path.exists():
                continue
            self._scan_directory(scan_path, self._before_state)

    def capture_after_state(self, scan_paths: Optional[list[Path | str]] = None) -> None:
        """
        Capture filesystem state after trial execution.

        Args:
            scan_paths: Paths to scan (defaults to working_dir and allowed_dirs)
        """
        if scan_paths is None:
            scan_paths = self.allowed_dirs
        else:
            scan_paths = [Path(p).resolve() for p in scan_paths]

        self._after_state = {}
        for scan_path in scan_paths:
            if not scan_path.exists():
                continue
            self._scan_directory(scan_path, self._after_state)

    def verify_isolation(self) -> IsolationVerificationResult:
        """
        Verify that trial execution stayed within isolation boundaries.

        Returns:
            IsolationVerificationResult with violation details
        """
        violations: list[IsolationViolation] = []
        files_created: list[str] = []
        files_modified: list[str] = []

        # Find files created
        for path, mtime in self._after_state.items():
            if path not in self._before_state:
                # File was created
                if self._is_within_allowed_dirs(path):
                    # Try to make path relative to working_dir, or use absolute path
                    try:
                        rel_path = str(path.relative_to(self.working_dir))
                    except ValueError:
                        # File is in an allowed dir but not working_dir
                        rel_path = str(path)
                    files_created.append(rel_path)
                else:
                    violations.append(
                        IsolationViolation(
                            path=str(path),
                            operation="create",
                            description=f"File created outside working directory: {path}",
                        )
                    )

        # Find files modified
        for path, mtime in self._after_state.items():
            if path in self._before_state:
                if mtime > self._before_state[path]:
                    # File was modified
                    if self._is_within_allowed_dirs(path):
                        # Try to make path relative to working_dir, or use absolute path
                        try:
                            rel_path = str(path.relative_to(self.working_dir))
                        except ValueError:
                            # File is in an allowed dir but not working_dir
                            rel_path = str(path)
                        files_modified.append(rel_path)
                    else:
                        violations.append(
                            IsolationViolation(
                                path=str(path),
                                operation="modify",
                                description=f"File modified outside working directory: {path}",
                            )
                        )

        # Determine if isolated
        isolated = len(violations) == 0

        error_message = None
        if not isolated:
            error_message = f"Detected {len(violations)} isolation violation(s)"

        return IsolationVerificationResult(
            isolated=isolated,
            violations=violations,
            working_dir=str(self.working_dir),
            files_created=files_created,
            files_modified=files_modified,
            error_message=error_message,
        )

    def _scan_directory(self, path: Path, state_dict: dict[Path, float]) -> None:
        """
        Recursively scan directory and record file modification times.

        Args:
            path: Directory to scan
            state_dict: Dictionary to populate with {file_path: mtime}
        """
        try:
            if path.is_file():
                state_dict[path] = path.stat().st_mtime
            elif path.is_dir():
                for item in path.rglob("*"):
                    if item.is_file():
                        try:
                            state_dict[item] = item.stat().st_mtime
                        except (OSError, PermissionError):
                            # Skip files we can't read
                            pass
        except (OSError, PermissionError):
            # Skip directories we can't access
            pass

    def _is_within_allowed_dirs(self, path: Path) -> bool:
        """Check if path is within any allowed directory."""
        path = path.resolve()
        for allowed_dir in self.allowed_dirs:
            try:
                path.relative_to(allowed_dir)
                return True
            except ValueError:
                continue
        return False


def verify_trial_isolation(
    working_dir: Path | str,
    before_scan: Optional[list[Path | str]] = None,
    after_scan: Optional[list[Path | str]] = None,
) -> IsolationVerificationResult:
    """
    Convenience function to verify trial isolation with before/after snapshots.

    Note: This requires the before state to already be captured.
    Use FilesystemIsolationVerifier directly for more control.

    Args:
        working_dir: Trial's working directory
        before_scan: Paths to scan before (defaults to working_dir)
        after_scan: Paths to scan after (defaults to working_dir)

    Returns:
        IsolationVerificationResult
    """
    verifier = FilesystemIsolationVerifier(working_dir)
    verifier.capture_after_state(after_scan)

    # Without before state, we can only verify files in working directory exist
    result = verifier.verify_isolation()
    return result


def check_working_directory_isolation(
    working_dir: Path | str,
) -> IsolationVerificationResult:
    """
    Simple check that working directory exists and is writable.

    Args:
        working_dir: Path to working directory

    Returns:
        IsolationVerificationResult
    """
    working_dir = Path(working_dir)

    if not working_dir.exists():
        return IsolationVerificationResult(
            isolated=False,
            violations=[
                IsolationViolation(
                    path=str(working_dir),
                    operation="access",
                    description=f"Working directory does not exist: {working_dir}",
                )
            ],
            working_dir=str(working_dir),
            files_created=[],
            files_modified=[],
            error_message="Working directory does not exist",
        )

    if not os.access(working_dir, os.W_OK):
        return IsolationVerificationResult(
            isolated=False,
            violations=[
                IsolationViolation(
                    path=str(working_dir),
                    operation="write",
                    description=f"Working directory is not writable: {working_dir}",
                )
            ],
            working_dir=str(working_dir),
            files_created=[],
            files_modified=[],
            error_message="Working directory is not writable",
        )

    return IsolationVerificationResult(
        isolated=True,
        violations=[],
        working_dir=str(working_dir),
        files_created=[],
        files_modified=[],
    )
