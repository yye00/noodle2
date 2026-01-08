"""Docker-based trial execution for OpenROAD workloads."""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker
from docker.models.containers import Container


@dataclass
class DockerRunConfig:
    """Configuration for Docker trial execution."""

    image: str = "efabless/openlane:ci2504-dev-amd64"
    working_dir: str = "/work"
    timeout_seconds: int = 3600
    memory_limit: str = "8g"
    cpu_count: int | None = None
    environment: dict[str, str] | None = None


@dataclass
class TrialExecutionResult:
    """Result of executing a trial in Docker."""

    return_code: int
    stdout: str
    stderr: str
    runtime_seconds: float
    success: bool
    container_id: str = ""


class DockerTrialRunner:
    """
    Execute OpenROAD trials inside Docker containers.

    Each trial runs in an isolated container with:
    - Immutable snapshot mounted read-only
    - Dedicated working directory for outputs
    - Resource limits (memory, CPU, timeout)
    - Captured stdout/stderr
    """

    def __init__(self, config: DockerRunConfig | None = None) -> None:
        """
        Initialize Docker trial runner.

        Args:
            config: Docker run configuration (uses defaults if None)
        """
        self.config = config or DockerRunConfig()
        self.client = docker.from_env()

        # Verify image is available
        self._ensure_image_available()

    def _ensure_image_available(self) -> None:
        """Ensure Docker image is pulled and available."""
        try:
            self.client.images.get(self.config.image)
        except docker.errors.ImageNotFound:
            # Image not found, try to pull it
            print(f"Pulling Docker image: {self.config.image}")
            self.client.images.pull(self.config.image)

    def execute_trial(
        self,
        script_path: str | Path,
        working_dir: str | Path,
        snapshot_dir: str | Path | None = None,
        timeout_seconds: int | None = None,
    ) -> TrialExecutionResult:
        """
        Execute a trial script inside a Docker container.

        Args:
            script_path: Path to TCL script to execute
            working_dir: Host directory for trial outputs (mounted at /work)
            snapshot_dir: Optional snapshot directory (mounted read-only at /snapshot)
            timeout_seconds: Optional timeout override

        Returns:
            TrialExecutionResult with execution details

        Raises:
            FileNotFoundError: If script or directories don't exist
            docker.errors.DockerException: On Docker errors
        """
        script_path = Path(script_path)
        working_dir = Path(working_dir)

        if not script_path.exists():
            raise FileNotFoundError(f"Script not found: {script_path}")

        # Create working directory if needed
        working_dir.mkdir(parents=True, exist_ok=True)

        # Build volume mounts
        volumes = {
            str(working_dir.absolute()): {"bind": "/work", "mode": "rw"},
            str(script_path.parent.absolute()): {"bind": "/scripts", "mode": "ro"},
        }

        if snapshot_dir:
            snapshot_dir = Path(snapshot_dir)
            if snapshot_dir.exists():
                volumes[str(snapshot_dir.absolute())] = {"bind": "/snapshot", "mode": "ro"}

        # Build command
        script_name = script_path.name
        command = f"openroad -exit /scripts/{script_name}"

        # Merge environment variables
        env = self.config.environment or {}

        # Set timeout
        timeout = timeout_seconds or self.config.timeout_seconds

        # Execute container
        start_time = time.time()

        try:
            container: Container = self.client.containers.run(
                image=self.config.image,
                command=command,
                volumes=volumes,
                working_dir="/work",
                mem_limit=self.config.memory_limit,
                cpu_count=self.config.cpu_count,
                environment=env,
                detach=True,
                remove=False,  # Keep container for log retrieval
            )

            # Wait for completion with timeout
            try:
                result = container.wait(timeout=timeout)
                return_code = result["StatusCode"]
            except Exception:
                # Timeout or other error - kill container
                container.kill()
                return_code = -1

            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            # Calculate runtime
            runtime_seconds = time.time() - start_time

            # Cleanup container
            container.remove(force=True)

            return TrialExecutionResult(
                return_code=return_code,
                stdout=stdout,
                stderr=stderr,
                runtime_seconds=runtime_seconds,
                success=(return_code == 0),
                container_id=container.id[:12],
            )

        except docker.errors.ContainerError as e:
            runtime_seconds = time.time() - start_time
            return TrialExecutionResult(
                return_code=e.exit_status,
                stdout=e.stdout.decode("utf-8", errors="replace") if e.stdout else "",
                stderr=e.stderr.decode("utf-8", errors="replace") if e.stderr else str(e),
                runtime_seconds=runtime_seconds,
                success=False,
            )

    def verify_openroad_available(self) -> bool:
        """
        Verify OpenROAD is available inside the container.

        Returns:
            True if OpenROAD is on PATH and executable
        """
        try:
            result = self.client.containers.run(
                image=self.config.image,
                command="which openroad",
                remove=True,
            )
            return b"/openroad" in result or b"openroad" in result
        except Exception:
            return False

    def verify_pdk_available(self, pdk_name: str) -> bool:
        """
        Verify a specific PDK is pre-installed in the container.

        Args:
            pdk_name: PDK name to check (e.g., "Nangate45", "ASAP7", "sky130A")

        Returns:
            True if PDK appears to be available
        """
        # Common PDK locations in OpenLane container
        pdk_paths = [
            f"/openLANE_flow/designs/{pdk_name}",
            f"/pdk/{pdk_name}",
            f"$PDK_ROOT/{pdk_name}",
        ]

        try:
            # Check if any standard PDK location exists
            command = " || ".join([f"test -d {path}" for path in pdk_paths])
            self.client.containers.run(
                image=self.config.image,
                command=f"sh -c '{command}'",
                remove=True,
            )
            return True
        except docker.errors.ContainerError:
            return False

    def get_container_info(self) -> dict[str, Any]:
        """Get information about the Docker image."""
        try:
            image = self.client.images.get(self.config.image)
            return {
                "id": image.id[:12],
                "tags": image.tags,
                "created": image.attrs.get("Created"),
                "size_mb": image.attrs.get("Size", 0) / (1024 * 1024),
            }
        except docker.errors.ImageNotFound:
            return {}
