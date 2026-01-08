"""Provenance tracking for trial execution reproducibility."""

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ToolProvenance:
    """
    Provenance information for tool execution.

    Captures all information needed to reproduce a trial execution:
    - Tool version (best-effort)
    - Container image and tag
    - Command-line invocation
    - Execution timestamps
    """

    # Container information
    container_image: str
    container_tag: str
    container_id: str = ""

    # Tool version (best-effort, may be None if query fails)
    tool_name: str = "openroad"
    tool_version: str | None = None

    # Command invocation
    command: str = ""
    working_directory: str = ""

    # Timestamps
    start_time: str = ""
    end_time: str = ""

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "container_image": self.container_image,
            "container_tag": self.container_tag,
            "container_id": self.container_id,
            "tool_name": self.tool_name,
            "tool_version": self.tool_version,
            "command": self.command,
            "working_directory": self.working_directory,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metadata": self.metadata,
        }


def query_openroad_version(container_image: str) -> str | None:
    """
    Query OpenROAD version from container (best-effort).

    Args:
        container_image: Full container image name

    Returns:
        Version string if available, None otherwise
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                container_image,
                "openroad",
                "-version",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            # Parse version from output
            # Expected format: "OpenROAD vX.Y.Z" or similar
            output = result.stdout + result.stderr

            # Try different version patterns
            patterns = [
                r"OpenROAD\s+v?([\d\.]+(?:-[\w\.]+)?)",
                r"version[:\s]+([\d\.]+(?:-[\w\.]+)?)",
                r"v?([\d]+\.[\d]+\.[\d]+(?:-[\w\.]+)?)",
            ]

            for pattern in patterns:
                match = re.search(pattern, output, re.IGNORECASE)
                if match:
                    return match.group(1)

            # If no pattern matches, return first line as fallback
            first_line = output.strip().split("\n")[0]
            if first_line:
                return first_line

        return None

    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        # Best-effort: return None if version query fails
        return None


def create_provenance(
    container_image: str,
    container_tag: str,
    container_id: str = "",
    command: str = "",
    working_dir: str | Path = "",
    start_time: str = "",
    end_time: str = "",
    query_version: bool = True,
) -> ToolProvenance:
    """
    Create provenance record for trial execution.

    Args:
        container_image: Container image name (without tag)
        container_tag: Container image tag
        container_id: Container ID from execution
        command: Command-line invocation
        working_dir: Working directory
        start_time: Start timestamp (ISO format)
        end_time: End timestamp (ISO format)
        query_version: Whether to query tool version (may be slow)

    Returns:
        ToolProvenance object
    """
    # Query tool version if requested
    tool_version = None
    if query_version:
        full_image = f"{container_image}:{container_tag}"
        tool_version = query_openroad_version(full_image)

    return ToolProvenance(
        container_image=container_image,
        container_tag=container_tag,
        container_id=container_id,
        tool_name="openroad",
        tool_version=tool_version,
        command=command,
        working_directory=str(working_dir) if working_dir else "",
        start_time=start_time,
        end_time=end_time,
    )


def format_provenance_summary(prov: ToolProvenance) -> str:
    """
    Format provenance as human-readable summary.

    Args:
        prov: ToolProvenance object

    Returns:
        Human-readable summary string
    """
    lines = [
        "=== Trial Execution Provenance ===",
        f"Container: {prov.container_image}:{prov.container_tag}",
        f"Container ID: {prov.container_id}",
        f"Tool: {prov.tool_name}",
    ]

    if prov.tool_version:
        lines.append(f"Version: {prov.tool_version}")
    else:
        lines.append("Version: (unavailable)")

    if prov.command:
        lines.append(f"Command: {prov.command}")

    if prov.working_directory:
        lines.append(f"Working Dir: {prov.working_directory}")

    if prov.start_time and prov.end_time:
        lines.append(f"Execution: {prov.start_time} to {prov.end_time}")

    return "\n".join(lines)
