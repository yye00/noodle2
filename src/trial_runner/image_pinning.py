"""Container image pinning with SHA256 digest for reproducibility."""

import re
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass
class ImageDigest:
    """
    Container image reference with SHA256 digest pinning.

    Supports both tag-based and digest-based image references:
    - Tag-based: "efabless/openlane:ci2504-dev-amd64"
    - Digest-based: "efabless/openlane@sha256:abc123..."

    Digest-based references guarantee exact image reproducibility.
    """

    repository: str  # e.g., "efabless/openlane"
    tag: str | None = None  # e.g., "ci2504-dev-amd64"
    digest: str | None = None  # e.g., "sha256:abc123..."

    def __post_init__(self) -> None:
        """Validate that either tag or digest is specified."""
        if self.tag is None and self.digest is None:
            raise ValueError("Either tag or digest must be specified")

        if self.digest and not self.digest.startswith("sha256:"):
            raise ValueError(
                f"Digest must start with 'sha256:', got: {self.digest}"
            )

    @property
    def image_ref(self) -> str:
        """
        Get full image reference for Docker.

        Returns:
            Image reference string for Docker commands
        """
        if self.digest:
            # Digest-based reference (reproducible)
            return f"{self.repository}@{self.digest}"
        else:
            # Tag-based reference (mutable)
            return f"{self.repository}:{self.tag}"

    @property
    def is_pinned(self) -> bool:
        """Check if image is pinned with digest."""
        return self.digest is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "repository": self.repository,
            "tag": self.tag,
            "digest": self.digest,
            "image_ref": self.image_ref,
            "is_pinned": self.is_pinned,
        }

    @classmethod
    def from_string(cls, image_ref: str) -> "ImageDigest":
        """
        Parse image reference string into ImageDigest.

        Supports:
        - "repository:tag"
        - "repository@sha256:digest"

        Args:
            image_ref: Image reference string

        Returns:
            ImageDigest object
        """
        # Check for digest-based reference
        if "@sha256:" in image_ref:
            parts = image_ref.split("@")
            if len(parts) != 2:
                raise ValueError(f"Invalid digest-based reference: {image_ref}")
            repository = parts[0]
            digest = parts[1]
            return cls(repository=repository, digest=digest)

        # Tag-based reference
        if ":" in image_ref:
            parts = image_ref.rsplit(":", 1)
            repository = parts[0]
            tag = parts[1]
            return cls(repository=repository, tag=tag)

        # No tag or digest - default to 'latest'
        return cls(repository=image_ref, tag="latest")


def query_image_digest(image_ref: str) -> str | None:
    """
    Query the SHA256 digest for a container image.

    Args:
        image_ref: Image reference (tag-based or digest-based)

    Returns:
        SHA256 digest string if available, None otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format={{.Id}}", image_ref],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            # Output format: "sha256:abc123..."
            digest = result.stdout.strip()
            if digest.startswith("sha256:"):
                return digest
            # If it doesn't start with sha256:, it's the short ID, try RepoDigests
            result = subprocess.run(
                ["docker", "inspect", "--format={{index .RepoDigests 0}}", image_ref],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Extract digest from "repository@sha256:abc123..."
                repo_digest = result.stdout.strip()
                if "@sha256:" in repo_digest:
                    return repo_digest.split("@")[1]

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return None


def verify_image_digest(image_ref: str, expected_digest: str) -> bool:
    """
    Verify that a container image matches expected SHA256 digest.

    Args:
        image_ref: Image reference to verify
        expected_digest: Expected SHA256 digest (e.g., "sha256:abc123...")

    Returns:
        True if image matches expected digest, False otherwise
    """
    actual_digest = query_image_digest(image_ref)

    if actual_digest is None:
        return False

    # Normalize digests (remove "sha256:" prefix for comparison)
    expected_normalized = expected_digest.replace("sha256:", "")
    actual_normalized = actual_digest.replace("sha256:", "")

    return expected_normalized == actual_normalized


def get_image_digest_for_provenance(image_ref: str) -> str:
    """
    Get image digest for provenance metadata.

    Best-effort function to capture image digest for reproducibility.

    Args:
        image_ref: Image reference used for trial

    Returns:
        SHA256 digest if available, image_ref otherwise
    """
    digest = query_image_digest(image_ref)
    if digest:
        return digest
    return image_ref


def format_image_provenance(image_digest: ImageDigest) -> str:
    """
    Format image reference for human-readable provenance.

    Args:
        image_digest: ImageDigest object

    Returns:
        Human-readable string
    """
    lines = ["=== Container Image Provenance ==="]

    lines.append(f"Repository: {image_digest.repository}")

    if image_digest.tag:
        lines.append(f"Tag: {image_digest.tag}")

    if image_digest.digest:
        lines.append(f"Digest: {image_digest.digest}")
        lines.append("Pinned: Yes (reproducible)")
    else:
        lines.append("Pinned: No (tag-based, may change)")

    lines.append(f"Full Reference: {image_digest.image_ref}")

    return "\n".join(lines)
