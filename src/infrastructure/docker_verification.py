"""Docker and OpenROAD container verification utilities.

This module provides functions to verify that:
1. Docker is available on the system
2. The openroad/orfs:latest container is available
3. OpenROAD is accessible within the container
4. The OpenROAD version can be retrieved
"""

import subprocess
from dataclasses import dataclass
from typing import Optional


# Container configuration
OPENROAD_CONTAINER_IMAGE = "openroad/orfs:latest"
OPENROAD_BINARY_PATH = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"


@dataclass
class DockerVerificationResult:
    """Result of Docker verification check."""

    available: bool
    version: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ContainerVerificationResult:
    """Result of container availability check."""

    available: bool
    image_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class OpenROADVerificationResult:
    """Result of OpenROAD verification in container."""

    available: bool
    version: Optional[str] = None
    binary_path: Optional[str] = None
    error: Optional[str] = None


@dataclass
class InfrastructureVerificationResult:
    """Complete infrastructure verification result."""

    docker_available: bool
    container_available: bool
    openroad_available: bool
    openroad_version: Optional[str] = None
    errors: list[str] = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    @property
    def all_checks_passed(self) -> bool:
        """Check if all verification checks passed."""
        return (
            self.docker_available
            and self.container_available
            and self.openroad_available
        )


def check_docker_available() -> DockerVerificationResult:
    """Check if Docker is available on the system.

    Returns:
        DockerVerificationResult with availability status and version.
    """
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            return DockerVerificationResult(available=True, version=version)
        else:
            return DockerVerificationResult(
                available=False, error=f"Docker command failed: {result.stderr}"
            )

    except FileNotFoundError:
        return DockerVerificationResult(
            available=False, error="Docker command not found"
        )
    except subprocess.TimeoutExpired:
        return DockerVerificationResult(
            available=False, error="Docker command timed out"
        )
    except Exception as e:
        return DockerVerificationResult(available=False, error=str(e))


def check_openroad_container_available(
    image: str = OPENROAD_CONTAINER_IMAGE,
) -> ContainerVerificationResult:
    """Check if the OpenROAD container is available locally.

    Args:
        image: Docker image name (default: openroad/orfs:latest)

    Returns:
        ContainerVerificationResult with availability status.
    """
    try:
        result = subprocess.run(
            ["docker", "images", "-q", image],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

        if result.returncode == 0:
            image_id = result.stdout.strip()
            if image_id:
                return ContainerVerificationResult(
                    available=True, image_id=image_id
                )
            else:
                return ContainerVerificationResult(
                    available=False,
                    error=f"Container image {image} not found locally",
                )
        else:
            return ContainerVerificationResult(
                available=False, error=f"Docker images command failed: {result.stderr}"
            )

    except subprocess.TimeoutExpired:
        return ContainerVerificationResult(
            available=False, error="Docker images command timed out"
        )
    except Exception as e:
        return ContainerVerificationResult(available=False, error=str(e))


def verify_openroad_in_container(
    image: str = OPENROAD_CONTAINER_IMAGE,
    binary_path: str = OPENROAD_BINARY_PATH,
) -> OpenROADVerificationResult:
    """Verify that OpenROAD is accessible in the container.

    Args:
        image: Docker image name (default: openroad/orfs:latest)
        binary_path: Path to OpenROAD binary in container

    Returns:
        OpenROADVerificationResult with availability and version.
    """
    try:
        # Try to get OpenROAD version
        result = subprocess.run(
            ["docker", "run", "--rm", image, binary_path, "-version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        if result.returncode == 0:
            version = result.stdout.strip()
            return OpenROADVerificationResult(
                available=True, version=version, binary_path=binary_path
            )
        else:
            return OpenROADVerificationResult(
                available=False,
                error=f"OpenROAD command failed: {result.stderr}",
            )

    except subprocess.TimeoutExpired:
        return OpenROADVerificationResult(
            available=False, error="OpenROAD command timed out"
        )
    except Exception as e:
        return OpenROADVerificationResult(available=False, error=str(e))


def get_openroad_version(
    image: str = OPENROAD_CONTAINER_IMAGE,
    binary_path: str = OPENROAD_BINARY_PATH,
) -> Optional[str]:
    """Get the OpenROAD version from the container.

    Args:
        image: Docker image name (default: openroad/orfs:latest)
        binary_path: Path to OpenROAD binary in container

    Returns:
        Version string or None if unavailable.
    """
    result = verify_openroad_in_container(image, binary_path)
    return result.version if result.available else None


def verify_openroad_infrastructure() -> InfrastructureVerificationResult:
    """Perform complete verification of OpenROAD infrastructure.

    This function checks:
    1. Docker is available
    2. OpenROAD container is available
    3. OpenROAD is accessible in the container
    4. OpenROAD version can be retrieved

    Returns:
        InfrastructureVerificationResult with complete status.
    """
    errors = []

    # Check Docker
    docker_result = check_docker_available()
    if not docker_result.available:
        errors.append(f"Docker not available: {docker_result.error}")

    # Check container (only if Docker is available)
    container_available = False
    if docker_result.available:
        container_result = check_openroad_container_available()
        container_available = container_result.available
        if not container_result.available:
            errors.append(f"Container not available: {container_result.error}")

    # Check OpenROAD (only if container is available)
    openroad_available = False
    openroad_version = None
    if container_available:
        openroad_result = verify_openroad_in_container()
        openroad_available = openroad_result.available
        openroad_version = openroad_result.version
        if not openroad_result.available:
            errors.append(f"OpenROAD not available: {openroad_result.error}")

    return InfrastructureVerificationResult(
        docker_available=docker_result.available,
        container_available=container_available,
        openroad_available=openroad_available,
        openroad_version=openroad_version,
        errors=errors,
    )
