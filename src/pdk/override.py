"""PDK override support for bind-mounted versioned PDKs."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class PDKOverride:
    """Configuration for bind-mounted PDK override.

    Allows Studies to specify a custom versioned PDK directory
    that will be mounted into the container at execution time.
    """

    host_path: str  # Path to PDK directory on host machine
    container_path: str  # Path where PDK will be mounted in container
    pdk_version: str  # Version identifier for provenance tracking
    metadata: dict[str, Any] = field(default_factory=dict)  # Additional PDK metadata

    def validate(self) -> tuple[bool, list[str]]:
        """Validate PDK override configuration.

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors: list[str] = []

        # Check host path exists
        host_path_obj = Path(self.host_path)
        if not host_path_obj.exists():
            errors.append(f"PDK host path does not exist: {self.host_path}")
        elif not host_path_obj.is_dir():
            errors.append(f"PDK host path is not a directory: {self.host_path}")

        # Check container path is absolute
        container_path_obj = Path(self.container_path)
        if not container_path_obj.is_absolute():
            errors.append(f"PDK container path must be absolute: {self.container_path}")

        # Check version is non-empty
        if not self.pdk_version or not self.pdk_version.strip():
            errors.append("PDK version must be non-empty")

        return (len(errors) == 0, errors)

    def to_docker_mount(self) -> str:
        """Convert to Docker volume mount format.

        Returns:
            Docker mount string in format: host_path:container_path:ro
        """
        # Mount as read-only for safety
        return f"{self.host_path}:{self.container_path}:ro"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "host_path": self.host_path,
            "container_path": self.container_path,
            "pdk_version": self.pdk_version,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PDKOverride":
        """Create PDKOverride from dictionary."""
        return cls(
            host_path=data["host_path"],
            container_path=data["container_path"],
            pdk_version=data["pdk_version"],
            metadata=data.get("metadata", {}),
        )


def create_pdk_override(
    host_path: str,
    container_path: str,
    pdk_version: str,
    **metadata: Any,
) -> PDKOverride:
    """Convenience function to create PDKOverride with validation.

    Args:
        host_path: Path to PDK directory on host
        container_path: Path where PDK will be mounted in container
        pdk_version: Version identifier
        **metadata: Additional metadata fields

    Returns:
        PDKOverride instance

    Raises:
        ValueError: If validation fails
    """
    override = PDKOverride(
        host_path=host_path,
        container_path=container_path,
        pdk_version=pdk_version,
        metadata=dict(metadata),
    )

    is_valid, errors = override.validate()
    if not is_valid:
        error_msg = "PDK override validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)

    return override


def verify_pdk_accessibility(
    container_path: str,
    expected_files: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """Verify PDK is accessible at the specified path.

    This function can be called within a container to verify
    the PDK was successfully mounted.

    Args:
        container_path: Path where PDK should be mounted
        expected_files: Optional list of files that should exist

    Returns:
        Tuple of (is_accessible, missing_files)
    """
    missing_files: list[str] = []

    pdk_path = Path(container_path)
    if not pdk_path.exists():
        return (False, ["PDK directory does not exist"])

    if not pdk_path.is_dir():
        return (False, ["PDK path is not a directory"])

    # Check for expected files if provided
    if expected_files:
        for file_name in expected_files:
            file_path = pdk_path / file_name
            if not file_path.exists():
                missing_files.append(file_name)

    return (len(missing_files) == 0, missing_files)


def document_pdk_override_in_provenance(
    override: PDKOverride,
    study_name: str,
) -> dict[str, Any]:
    """Generate provenance record for PDK override.

    Args:
        override: PDK override configuration
        study_name: Name of the Study using this override

    Returns:
        Dictionary containing PDK override provenance information
    """
    return {
        "pdk_override": {
            "enabled": True,
            "pdk_version": override.pdk_version,
            "container_path": override.container_path,
            "host_path_hash": hash(override.host_path),  # Don't expose full host path
            "metadata": override.metadata,
        },
        "study_name": study_name,
        "override_type": "bind_mount",
        "mount_mode": "read_only",
    }
