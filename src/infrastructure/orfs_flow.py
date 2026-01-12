"""OpenROAD-flow-scripts (ORFS) flow execution utilities.

This module provides functions to run ORFS flows and create design snapshots.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# Default ORFS installation path
DEFAULT_ORFS_PATH = Path("./orfs")


@dataclass
class ORFSFlowResult:
    """Result of running an ORFS flow stage."""

    stage: str  # e.g., "synth", "floorplan", "place"
    success: bool
    odb_file: Optional[Path] = None  # Path to generated .odb file
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


@dataclass
class SnapshotCreationResult:
    """Result of creating a design snapshot."""

    success: bool
    snapshot_path: Optional[Path] = None
    odb_file: Optional[Path] = None
    platform: str = ""
    design: str = ""
    error: Optional[str] = None


def run_orfs_stage(
    stage: str,
    platform: str,
    design: str,
    orfs_path: Path = DEFAULT_ORFS_PATH,
    timeout: int = 600,
    container: str = "openroad/orfs:latest",
) -> ORFSFlowResult:
    """Run a single ORFS flow stage using Docker.

    This runs the flow in the container's built-in ORFS installation,
    then copies the result ODB file to the host's ORFS directory.

    Args:
        stage: Stage name (e.g., "synth", "floorplan", "place")
        platform: Platform name (e.g., "nangate45")
        design: Design name (e.g., "gcd")
        orfs_path: Path to ORFS installation for storing results (default: ./orfs)
        timeout: Timeout in seconds (default: 600)
        container: Docker container image (default: openroad/orfs:latest)

    Returns:
        ORFSFlowResult with execution status and output.
    """
    # Get absolute paths
    orfs_abs = orfs_path.resolve()
    results_dir = orfs_abs / "flow" / "results" / platform / design / "base"
    results_dir.mkdir(parents=True, exist_ok=True)

    config_path = f"./designs/{platform}/{design}/config.mk"

    # Determine ODB file paths
    odb_mapping = {
        "synth": "1_synth.odb",
        "floorplan": "2_floorplan.odb",
        "place": "3_place.odb",
        "cts": "4_cts.odb",
        "route": "5_route.odb",
    }

    odb_filename = odb_mapping.get(stage)
    if not odb_filename:
        return ORFSFlowResult(
            stage=stage,
            success=False,
            error=f"Unknown stage: {stage}",
        )

    container_odb_path = f"/OpenROAD-flow-scripts/flow/results/{platform}/{design}/base/{odb_filename}"
    host_odb_path = results_dir / odb_filename

    # Build Docker command to run make inside container and copy results out
    # We'll use docker create + docker cp to extract the ODB file
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v", f"{results_dir}:/output",
        "-w", "/OpenROAD-flow-scripts/flow",
        container,
        "bash",
        "-c",
        f"make DESIGN_CONFIG={config_path} {stage} && cp {container_odb_path} /output/ || exit 1",
    ]

    try:
        # Run Docker command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Check if ODB file was copied successfully
        odb_file = None
        if host_odb_path.exists():
            odb_file = host_odb_path

        success = result.returncode == 0 and odb_file is not None

        return ORFSFlowResult(
            stage=stage,
            success=success,
            odb_file=odb_file,
            stdout=result.stdout,
            stderr=result.stderr,
            error=None if success else f"Make returned {result.returncode}",
        )

    except subprocess.TimeoutExpired:
        return ORFSFlowResult(
            stage=stage,
            success=False,
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return ORFSFlowResult(
            stage=stage,
            success=False,
            error=f"Execution failed: {e}",
        )


def run_orfs_flow_through_placement(
    platform: str,
    design: str,
    orfs_path: Path = DEFAULT_ORFS_PATH,
) -> tuple[list[ORFSFlowResult], Optional[Path]]:
    """Run complete ORFS flow through placement.

    This runs: synth -> floorplan -> place

    Args:
        platform: Platform name (e.g., "nangate45")
        design: Design name (e.g., "gcd")
        orfs_path: Path to ORFS installation (default: ./orfs)

    Returns:
        Tuple of (list of stage results, final ODB path or None)
    """
    stages = ["synth", "floorplan", "place"]
    results = []
    final_odb = None

    for stage in stages:
        result = run_orfs_stage(stage, platform, design, orfs_path)
        results.append(result)

        if not result.success:
            break

        if result.odb_file:
            final_odb = result.odb_file

    return results, final_odb


def create_design_snapshot(
    platform: str,
    design: str,
    snapshot_dir: Path,
    orfs_path: Path = DEFAULT_ORFS_PATH,
) -> SnapshotCreationResult:
    """Create a design snapshot by running ORFS flow and copying ODB.

    Args:
        platform: Platform name (e.g., "nangate45")
        design: Design name (e.g., "gcd")
        snapshot_dir: Directory to store snapshot (will be created if needed)
        orfs_path: Path to ORFS installation (default: ./orfs)

    Returns:
        SnapshotCreationResult with success status and paths.
    """
    # Run ORFS flow through placement
    results, odb_file = run_orfs_flow_through_placement(platform, design, orfs_path)

    # Check if all stages succeeded
    if odb_file is None:
        failed_stages = [r.stage for r in results if not r.success]
        return SnapshotCreationResult(
            success=False,
            platform=platform,
            design=design,
            error=f"Flow failed at stages: {failed_stages}",
        )

    # Create snapshot directory
    snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    # Copy ODB file to snapshot directory
    import shutil

    snapshot_odb = snapshot_dir / f"{design}_placed.odb"
    shutil.copy2(odb_file, snapshot_odb)

    # Verify snapshot was created
    if not snapshot_odb.exists():
        return SnapshotCreationResult(
            success=False,
            platform=platform,
            design=design,
            error="Failed to copy ODB file to snapshot directory",
        )

    return SnapshotCreationResult(
        success=True,
        snapshot_path=snapshot_dir,
        odb_file=snapshot_odb,
        platform=platform,
        design=design,
    )


def verify_snapshot_loadable(
    snapshot_odb: Path,
    container: str = "openroad/orfs:latest",
) -> bool:
    """Verify that a snapshot ODB file can be loaded by OpenROAD.

    Args:
        snapshot_odb: Path to ODB file
        container: Docker container image

    Returns:
        True if ODB can be loaded, False otherwise.
    """
    if not snapshot_odb.exists():
        return False

    # Mount current directory in Docker
    mount_path = Path.cwd()

    # Get relative path from cwd to odb file
    try:
        rel_odb_path = snapshot_odb.relative_to(mount_path)
    except ValueError:
        # ODB is outside current directory, use absolute path
        rel_odb_path = snapshot_odb

    # Full path to OpenROAD binary in container
    openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"

    # Run OpenROAD with simple read_db command
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{mount_path}:/work",
        container,
        "bash",
        "-c",
        f'cd /work && {openroad_bin} -exit <<EOF\nread_db {rel_odb_path}\nexit\nEOF',
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False
