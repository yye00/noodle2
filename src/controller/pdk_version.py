"""PDK version tracking and mismatch detection."""

from dataclasses import dataclass
from typing import Any


@dataclass
class PDKVersion:
    """
    PDK version information for snapshot and runtime tracking.

    Captures:
    - PDK name (e.g., "nangate45", "asap7", "sky130")
    - Version string (e.g., "1.0", "r1p7", "fd-sc-hd")
    - Optional variant/configuration (e.g., "sky130A", "7t")
    - Source/provenance information
    """

    pdk_name: str
    version: str | None = None
    variant: str | None = None
    source: str | None = None  # e.g., "container", "snapshot", "user-specified"
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        """Validate and normalize PDK name."""
        # Normalize PDK name to lowercase for comparison
        self.pdk_name = self.pdk_name.lower()

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "pdk_name": self.pdk_name,
            "version": self.version,
            "variant": self.variant,
            "source": self.source,
            "metadata": self.metadata or {},
        }

    def __str__(self) -> str:
        """Human-readable PDK version string."""
        parts = [self.pdk_name]
        if self.variant:
            parts.append(self.variant)
        if self.version:
            parts.append(f"v{self.version}")
        return " ".join(parts)


@dataclass
class PDKVersionMismatch:
    """
    Detected PDK version mismatch between snapshot and runtime.

    Used for early-failure classification when snapshot expects a different
    PDK version than what's available in the container/runtime environment.
    """

    snapshot_pdk: PDKVersion
    runtime_pdk: PDKVersion
    severity: str = "error"  # "warning" or "error"
    message: str = ""

    def __post_init__(self) -> None:
        """Generate default message if not provided."""
        if not self.message:
            self.message = (
                f"PDK version mismatch detected: snapshot expects "
                f"{self.snapshot_pdk}, but runtime has {self.runtime_pdk}"
            )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "snapshot_pdk": self.snapshot_pdk.to_dict(),
            "runtime_pdk": self.runtime_pdk.to_dict(),
            "severity": self.severity,
            "message": self.message,
        }


def compare_pdk_versions(
    snapshot_pdk: PDKVersion,
    runtime_pdk: PDKVersion,
) -> tuple[bool, str | None]:
    """
    Compare snapshot PDK version with runtime PDK version.

    Args:
        snapshot_pdk: PDK version recorded in snapshot metadata
        runtime_pdk: PDK version detected in runtime environment

    Returns:
        Tuple of (compatible, warning_message):
        - compatible: True if PDKs are compatible (same name/version/variant)
        - warning_message: Human-readable warning if incompatible, None otherwise
    """
    # Check PDK name match (case-insensitive)
    if snapshot_pdk.pdk_name.lower() != runtime_pdk.pdk_name.lower():
        return (
            False,
            f"PDK name mismatch: snapshot expects '{snapshot_pdk.pdk_name}', "
            f"but runtime has '{runtime_pdk.pdk_name}'",
        )

    # Check variant match if both specify variant
    if snapshot_pdk.variant and runtime_pdk.variant:
        if snapshot_pdk.variant.lower() != runtime_pdk.variant.lower():
            return (
                False,
                f"PDK variant mismatch: snapshot expects '{snapshot_pdk.variant}', "
                f"but runtime has '{runtime_pdk.variant}'",
            )

    # Check version match if both specify version
    if snapshot_pdk.version and runtime_pdk.version:
        if snapshot_pdk.version != runtime_pdk.version:
            # Version mismatch - may be warning or error depending on severity
            return (
                False,
                f"PDK version mismatch: snapshot expects version '{snapshot_pdk.version}', "
                f"but runtime has version '{runtime_pdk.version}'",
            )

    # Compatible (all specified fields match)
    return (True, None)


def detect_pdk_version_mismatch(
    snapshot_pdk: PDKVersion | None,
    runtime_pdk: PDKVersion | None,
) -> PDKVersionMismatch | None:
    """
    Detect PDK version mismatch and create mismatch report if needed.

    Args:
        snapshot_pdk: PDK version from snapshot metadata (None if not recorded)
        runtime_pdk: PDK version from runtime environment (None if not detected)

    Returns:
        PDKVersionMismatch object if mismatch detected, None if compatible or
        if version information is unavailable
    """
    # If either PDK version is unknown, cannot detect mismatch
    # This is not an error - just means version tracking is not enabled
    if snapshot_pdk is None or runtime_pdk is None:
        return None

    # Compare versions
    compatible, warning_message = compare_pdk_versions(snapshot_pdk, runtime_pdk)

    if not compatible:
        return PDKVersionMismatch(
            snapshot_pdk=snapshot_pdk,
            runtime_pdk=runtime_pdk,
            severity="error",
            message=warning_message or "PDK version incompatibility detected",
        )

    # No mismatch
    return None


def format_pdk_version_mismatch_warning(mismatch: PDKVersionMismatch) -> str:
    """
    Format PDK version mismatch as human-readable warning message.

    Args:
        mismatch: PDKVersionMismatch object

    Returns:
        Formatted warning message suitable for logs and reports
    """
    lines = [
        "=" * 80,
        "PDK VERSION MISMATCH DETECTED",
        "=" * 80,
        "",
        mismatch.message,
        "",
        "Snapshot PDK:",
        f"  Name: {mismatch.snapshot_pdk.pdk_name}",
    ]

    if mismatch.snapshot_pdk.variant:
        lines.append(f"  Variant: {mismatch.snapshot_pdk.variant}")
    if mismatch.snapshot_pdk.version:
        lines.append(f"  Version: {mismatch.snapshot_pdk.version}")
    if mismatch.snapshot_pdk.source:
        lines.append(f"  Source: {mismatch.snapshot_pdk.source}")

    lines.extend(
        [
            "",
            "Runtime PDK:",
            f"  Name: {mismatch.runtime_pdk.pdk_name}",
        ]
    )

    if mismatch.runtime_pdk.variant:
        lines.append(f"  Variant: {mismatch.runtime_pdk.variant}")
    if mismatch.runtime_pdk.version:
        lines.append(f"  Version: {mismatch.runtime_pdk.version}")
    if mismatch.runtime_pdk.source:
        lines.append(f"  Source: {mismatch.runtime_pdk.source}")

    lines.extend(
        [
            "",
            "RECOMMENDATION:",
            "  - Rebuild snapshot with correct PDK version, OR",
            "  - Use container with matching PDK version, OR",
            "  - Override PDK version in Study configuration if intentional",
            "",
            "=" * 80,
        ]
    )

    return "\n".join(lines)
