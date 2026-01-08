"""Snapshot integrity verification for base case validation."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SnapshotHash:
    """
    Cryptographic hash of a design snapshot for integrity verification.

    Captures:
    - Hash value (SHA-256)
    - List of files included in hash
    - Hash algorithm used
    """

    hash_value: str
    algorithm: str = "sha256"
    files: list[str] | None = None
    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "hash_value": self.hash_value,
            "algorithm": self.algorithm,
            "files": self.files or [],
            "metadata": self.metadata or {},
        }


def compute_file_hash(file_path: str | Path, algorithm: str = "sha256") -> str:
    """
    Compute cryptographic hash of a single file.

    Args:
        file_path: Path to file
        algorithm: Hash algorithm (sha256, sha1, md5)

    Returns:
        Hex digest of file hash

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If algorithm is not supported
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    hasher = hashlib.new(algorithm)

    # Read file in chunks to handle large files
    with path.open("rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_snapshot_hash(
    snapshot_dir: str | Path,
    algorithm: str = "sha256",
    file_patterns: list[str] | None = None,
) -> SnapshotHash:
    """
    Compute cryptographic hash of design snapshot directory.

    The hash is computed by:
    1. Discovering all files matching patterns (or all files if None)
    2. Sorting files by path for determinism
    3. Computing hash of each file
    4. Combining file hashes into a single snapshot hash

    Args:
        snapshot_dir: Path to snapshot directory
        algorithm: Hash algorithm (default: sha256)
        file_patterns: List of glob patterns to include (e.g., ["*.v", "*.sdc"])
                      If None, includes all files

    Returns:
        SnapshotHash object with hash value and file list

    Raises:
        FileNotFoundError: If snapshot_dir doesn't exist
        ValueError: If algorithm is not supported
    """
    snapshot_path = Path(snapshot_dir)
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot directory not found: {snapshot_dir}")

    if not snapshot_path.is_dir():
        raise ValueError(f"Not a directory: {snapshot_dir}")

    if algorithm not in hashlib.algorithms_available:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")

    # Discover files
    if file_patterns:
        # Use specified patterns
        files = []
        for pattern in file_patterns:
            files.extend(snapshot_path.glob(pattern))
    else:
        # Include all regular files (not directories)
        files = [f for f in snapshot_path.rglob("*") if f.is_file()]

    # Sort files by relative path for determinism
    sorted_files = sorted(files, key=lambda p: p.relative_to(snapshot_path))

    # Compute combined hash
    hasher = hashlib.new(algorithm)

    file_list = []
    for file_path in sorted_files:
        # Add file path to hash (for directory structure)
        rel_path = str(file_path.relative_to(snapshot_path))
        hasher.update(rel_path.encode("utf-8"))

        # Add file content to hash
        file_hash = compute_file_hash(file_path, algorithm)
        hasher.update(file_hash.encode("utf-8"))

        file_list.append(rel_path)

    snapshot_hash = hasher.hexdigest()

    return SnapshotHash(
        hash_value=snapshot_hash,
        algorithm=algorithm,
        files=file_list,
        metadata={
            "snapshot_dir": str(snapshot_dir),
            "file_count": len(file_list),
        },
    )


def verify_snapshot_hash(
    snapshot_dir: str | Path,
    expected_hash: SnapshotHash,
) -> bool:
    """
    Verify snapshot integrity against expected hash.

    Args:
        snapshot_dir: Path to snapshot directory
        expected_hash: Expected SnapshotHash

    Returns:
        True if hashes match, False otherwise

    Raises:
        FileNotFoundError: If snapshot_dir doesn't exist
    """
    # Recompute hash with same file patterns
    file_patterns = None
    if expected_hash.files:
        # If expected hash has file list, use it to determine patterns
        # This is a simplification - in production, store patterns explicitly
        file_patterns = None  # Hash all files for now

    actual_hash = compute_snapshot_hash(
        snapshot_dir,
        algorithm=expected_hash.algorithm,
        file_patterns=file_patterns,
    )

    return actual_hash.hash_value == expected_hash.hash_value


def detect_snapshot_tampering(
    snapshot_dir: str | Path,
    expected_hash: SnapshotHash,
) -> dict[str, Any]:
    """
    Detect snapshot tampering or corruption.

    Args:
        snapshot_dir: Path to snapshot directory
        expected_hash: Expected SnapshotHash

    Returns:
        Dictionary with:
        - tampered: bool (True if hash mismatch)
        - expected: str (expected hash)
        - actual: str (actual hash)
        - message: str (human-readable explanation)

    Raises:
        FileNotFoundError: If snapshot_dir doesn't exist
    """
    try:
        actual_hash = compute_snapshot_hash(
            snapshot_dir,
            algorithm=expected_hash.algorithm,
        )

        if actual_hash.hash_value == expected_hash.hash_value:
            return {
                "tampered": False,
                "expected": expected_hash.hash_value,
                "actual": actual_hash.hash_value,
                "message": "Snapshot integrity verified",
            }
        else:
            # Detect what changed
            expected_files = set(expected_hash.files or [])
            actual_files = set(actual_hash.files or [])

            added = actual_files - expected_files
            removed = expected_files - actual_files

            message_parts = ["Snapshot integrity check FAILED"]

            if added:
                message_parts.append(f"Added files: {sorted(added)}")

            if removed:
                message_parts.append(f"Removed files: {sorted(removed)}")

            if not added and not removed:
                message_parts.append("File contents modified")

            return {
                "tampered": True,
                "expected": expected_hash.hash_value,
                "actual": actual_hash.hash_value,
                "message": ". ".join(message_parts),
                "added_files": list(added),
                "removed_files": list(removed),
            }

    except FileNotFoundError as e:
        return {
            "tampered": True,
            "expected": expected_hash.hash_value,
            "actual": None,
            "message": f"Snapshot not found: {e}",
        }


def format_snapshot_hash_summary(snapshot_hash: SnapshotHash) -> str:
    """
    Format snapshot hash as human-readable summary.

    Args:
        snapshot_hash: SnapshotHash object

    Returns:
        Human-readable summary string
    """
    lines = [
        "=== Snapshot Integrity Hash ===",
        f"Algorithm: {snapshot_hash.algorithm.upper()}",
        f"Hash: {snapshot_hash.hash_value}",
    ]

    if snapshot_hash.files:
        lines.append(f"Files: {len(snapshot_hash.files)}")

    if snapshot_hash.metadata:
        snapshot_dir = snapshot_hash.metadata.get("snapshot_dir")
        if snapshot_dir:
            lines.append(f"Snapshot: {snapshot_dir}")

    return "\n".join(lines)
