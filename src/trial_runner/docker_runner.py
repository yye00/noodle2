"""Docker-based trial execution for OpenROAD workloads."""

import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import docker
import requests.exceptions
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
    gui_mode: bool = False  # Enable GUI mode with X11 passthrough
    readonly_snapshot: bool = True  # Mount snapshot as read-only (recommended for safety)


@dataclass
class TrialExecutionResult:
    """Result of executing a trial in Docker."""

    return_code: int
    stdout: str
    stderr: str
    runtime_seconds: float
    success: bool
    container_id: str = ""
    timed_out: bool = False  # True if trial exceeded hard timeout limit
    soft_timed_out: bool = False  # True if trial exceeded soft timeout threshold
    # Resource utilization metrics
    cpu_time_seconds: float | None = None  # Total CPU time consumed
    peak_memory_mb: float | None = None  # Peak memory usage in MB


class DockerTrialRunner:
    """
    Execute OpenROAD trials inside Docker containers.

    Each trial runs in an isolated container with:
    - Snapshot mounted (read-only by default for safety)
    - Dedicated working directory for outputs
    - Resource limits (memory, CPU, timeout)
    - Captured stdout/stderr
    - Configurable snapshot write protection
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
        soft_timeout_seconds: int | None = None,
    ) -> TrialExecutionResult:
        """
        Execute a trial script inside a Docker container.

        Args:
            script_path: Path to TCL script to execute
            working_dir: Host directory for trial outputs (mounted at /work)
            snapshot_dir: Optional snapshot directory (mounted at /snapshot).
                         Mount mode controlled by config.readonly_snapshot (default: read-only)
            timeout_seconds: Optional hard timeout override (kills container)
            soft_timeout_seconds: Optional soft timeout (logs warning, continues execution)

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
                # Mount snapshot with appropriate mode (read-only by default for safety)
                snapshot_mode = "ro" if self.config.readonly_snapshot else "rw"
                volumes[str(snapshot_dir.absolute())] = {"bind": "/snapshot", "mode": snapshot_mode}

        # Add X11 socket for GUI mode
        if self.config.gui_mode:
            # Mount X11 unix socket for display passthrough
            volumes["/tmp/.X11-unix"] = {"bind": "/tmp/.X11-unix", "mode": "rw"}

        # Build command
        script_name = script_path.name
        if self.config.gui_mode:
            # GUI mode: use openroad -gui (requires X11)
            command = f"openroad -gui -exit /scripts/{script_name}"
        else:
            # Non-GUI mode: standard batch execution
            command = f"openroad -exit /scripts/{script_name}"

        # Merge environment variables
        env = self.config.environment or {}

        # Add DISPLAY for GUI mode
        if self.config.gui_mode:
            # Use host DISPLAY or default to :0
            env["DISPLAY"] = os.environ.get("DISPLAY", ":0")

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

            # Wait for completion with timeout monitoring
            timed_out = False
            soft_timed_out = False
            soft_timeout_logged = False

            # If soft timeout is configured, use polling approach
            if soft_timeout_seconds is not None:
                poll_interval = 5  # Check every 5 seconds
                elapsed = 0.0

                while elapsed < timeout:
                    # Sleep for poll interval or remaining time
                    sleep_time = min(poll_interval, timeout - elapsed)
                    time.sleep(sleep_time)
                    elapsed = time.time() - start_time

                    # Check soft timeout
                    if not soft_timeout_logged and elapsed >= soft_timeout_seconds:
                        soft_timed_out = True
                        soft_timeout_logged = True
                        print(f"[SOFT_TIMEOUT_WARNING] Trial exceeded soft timeout of {soft_timeout_seconds}s at {elapsed:.1f}s, allowing to continue...")

                    # Check if container has finished
                    container.reload()
                    if container.status != 'running':
                        result = container.wait(timeout=1)
                        return_code = result["StatusCode"]
                        break
                else:
                    # Hard timeout exceeded
                    timed_out = True
                    container.kill()
                    return_code = 124  # Standard timeout exit code
            else:
                # No soft timeout - use simple wait with hard timeout
                try:
                    result = container.wait(timeout=timeout)
                    return_code = result["StatusCode"]
                except requests.exceptions.ReadTimeout:
                    # Timeout exceeded - kill container
                    timed_out = True
                    container.kill()
                    return_code = 124  # Standard timeout exit code
                except Exception:
                    # Other error - kill container
                    container.kill()
                    return_code = -1

            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            # Add timeout messages to stderr
            if timed_out:
                timeout_msg = f"\n[HARD_TIMEOUT] Trial exceeded hard timeout limit of {timeout} seconds\n"
                if soft_timed_out:
                    timeout_msg = f"\n[SOFT_TIMEOUT] Trial exceeded soft timeout of {soft_timeout_seconds}s\n" + timeout_msg
                stderr = timeout_msg + stderr
            elif soft_timed_out:
                soft_msg = f"\n[SOFT_TIMEOUT] Trial exceeded soft timeout of {soft_timeout_seconds}s but completed before hard timeout\n"
                stderr = soft_msg + stderr

            # Calculate runtime
            runtime_seconds = time.time() - start_time

            # Get resource utilization stats (best-effort)
            cpu_time_seconds, peak_memory_mb = self._get_container_resource_stats(container)

            # Cleanup container
            container.remove(force=True)

            return TrialExecutionResult(
                return_code=return_code,
                stdout=stdout,
                stderr=stderr,
                runtime_seconds=runtime_seconds,
                success=(return_code == 0),
                container_id=container.id[:12],
                timed_out=timed_out,
                soft_timed_out=soft_timed_out,
                cpu_time_seconds=cpu_time_seconds,
                peak_memory_mb=peak_memory_mb,
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

    def check_gui_available(self) -> bool:
        """
        Check if GUI mode is available (X11 socket exists and DISPLAY is set).

        Returns:
            True if GUI mode prerequisites are met
        """
        import os
        from pathlib import Path

        # Check if X11 socket exists
        x11_socket = Path("/tmp/.X11-unix")
        if not x11_socket.exists():
            return False

        # Check if DISPLAY is set
        if "DISPLAY" not in os.environ:
            return False

        return True

    def _get_container_resource_stats(self, container: Container) -> tuple[float | None, float | None]:
        """
        Extract resource utilization from container stats.

        Args:
            container: Docker container object

        Returns:
            Tuple of (cpu_time_seconds, peak_memory_mb), or (None, None) if unavailable
        """
        try:
            # Get container stats (non-streaming)
            stats = container.stats(stream=False)

            # Extract CPU time (total CPU usage in nanoseconds)
            cpu_time_seconds = None
            cpu_stats = stats.get("cpu_stats", {})
            cpu_usage = cpu_stats.get("cpu_usage", {})
            if "total_usage" in cpu_usage:
                # Convert nanoseconds to seconds
                cpu_time_seconds = cpu_usage["total_usage"] / 1_000_000_000.0

            # Extract peak memory usage
            peak_memory_mb = None
            memory_stats = stats.get("memory_stats", {})
            if "max_usage" in memory_stats:
                # Convert bytes to MB
                peak_memory_mb = memory_stats["max_usage"] / (1024 * 1024)
            elif "usage" in memory_stats:
                # Fall back to current usage if max_usage not available
                peak_memory_mb = memory_stats["usage"] / (1024 * 1024)

            return cpu_time_seconds, peak_memory_mb

        except Exception:
            # Resource stats are best-effort; don't fail trial if unavailable
            return None, None
