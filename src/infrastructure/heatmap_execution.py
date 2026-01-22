"""OpenROAD heatmap generation using gui::dump_heatmap in headless Xvfb mode.

This module provides functions to generate real heatmaps from OpenROAD
using the GUI commands in headless mode with Xvfb (X virtual framebuffer).
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


@dataclass
class HeatmapGenerationResult:
    """Result of generating a heatmap via OpenROAD GUI."""

    success: bool
    csv_path: Optional[Path] = None
    png_path: Optional[Path] = None
    stdout: str = ""
    stderr: str = ""
    error: Optional[str] = None


def start_xvfb_display(display_num: int = 99) -> tuple[subprocess.Popen, int]:
    """Start Xvfb virtual display server.

    Args:
        display_num: X display number to use (default: 99)

    Returns:
        Tuple of (Popen process, display_number)
    """
    # Start Xvfb on specified display
    # Resolution: 1280x1024, color depth: 24-bit
    cmd = [
        "Xvfb",
        f":{display_num}",
        "-screen",
        "0",
        "1280x1024x24",
        "-nolisten",
        "tcp",
    ]

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return process, display_num


def generate_heatmap_csv(
    odb_file: Path,
    heatmap_type: str,
    output_csv: Path,
    container: str = "openroad/orfs:latest",
    timeout: int = 120,
    xvfb_display: int = 99,
) -> HeatmapGenerationResult:
    """Generate heatmap CSV using OpenROAD GUI in headless mode.

    This function:
    1. Starts Xvfb inside the container
    2. Launches OpenROAD with -gui flag
    3. Executes gui::select_heatmap to choose heatmap type
    4. Executes gui::dump_heatmap to export CSV
    5. Captures the CSV output

    Args:
        odb_file: Path to ODB database file
        heatmap_type: Type of heatmap to generate
                     Options: 'Placement Density', 'Routing Congestion',
                     'Power Density', 'IR Drop', etc.
        output_csv: Path where CSV should be saved
        container: Docker container image
        timeout: Timeout in seconds
        xvfb_display: X display number for Xvfb

    Returns:
        HeatmapGenerationResult with success status and paths
    """
    if not odb_file.exists():
        return HeatmapGenerationResult(
            success=False,
            error=f"ODB file not found: {odb_file}",
        )

    # Mount current directory
    mount_path = Path.cwd()

    # Get relative path to ODB file
    try:
        rel_odb_path = odb_file.relative_to(mount_path)
    except ValueError:
        rel_odb_path = odb_file

    # Get relative output path
    try:
        rel_output_csv = output_csv.relative_to(mount_path)
    except ValueError:
        rel_output_csv = output_csv

    # Ensure output directory exists
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    # OpenROAD binary path in container
    openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"

    # Map user-friendly names to OpenROAD heatmap names
    heatmap_name_map = {
        "Placement Density": "Placement",
        "Placement": "Placement",
        "Routing Congestion": "Routing",
        "Routing": "Routing",
        "RUDY": "RUDY",
        "Power Density": "Power",
        "Power": "Power",
        "IR Drop": "IRDrop",
        "IRDrop": "IRDrop",
        "Pin Density": "Pin",
        "Pin": "Pin",
    }

    # Get the actual heatmap name for OpenROAD
    or_heatmap_name = heatmap_name_map.get(heatmap_type, heatmap_type)

    # Build TCL script for GUI commands
    # gui::dump_heatmap takes: heatmap_name output_file
    tcl_commands = f"""
# Read database
read_db {rel_odb_path}

# Dump heatmap to CSV
# Valid heatmap names: IRDrop, RUDY, Routing, Pin, Placement, Power
gui::dump_heatmap {or_heatmap_name} {rel_output_csv}

# Exit
exit
"""

    # Build bash script to run inside container
    # This script:
    # 1. Installs Xvfb if not available
    # 2. Starts Xvfb
    # 3. Runs OpenROAD with GUI enabled using TCL file (not stdin)
    # 4. Stops Xvfb
    bash_script = f"""
# Install Xvfb if not present
if ! command -v Xvfb &> /dev/null; then
    apt-get update -qq && apt-get install -y -qq xvfb > /dev/null 2>&1
fi

# Start Xvfb
Xvfb :{xvfb_display} -screen 0 1280x1024x24 -nolisten tcp &
XVFB_PID=$!

# Give Xvfb time to start
sleep 2

# Set DISPLAY environment variable
export DISPLAY=:{xvfb_display}

# Change to work directory
cd /work

# Write TCL commands to a temporary file
cat > /tmp/heatmap_gen.tcl << 'EOFMARKER'
{tcl_commands}
EOFMARKER

# Run OpenROAD with GUI enabled, sourcing TCL file
# Use -exit flag to ensure it exits after running the script
{openroad_bin} -gui -exit /tmp/heatmap_gen.tcl
OPENROAD_EXIT_CODE=$?

# Kill Xvfb
kill $XVFB_PID 2>/dev/null || true

# Exit with OpenROAD's exit code
exit $OPENROAD_EXIT_CODE
"""

    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{mount_path}:/work",
        container,
        "bash",
        "-c",
        bash_script,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Check if CSV was created
        csv_exists = output_csv.exists()

        if result.returncode == 0 and csv_exists:
            return HeatmapGenerationResult(
                success=True,
                csv_path=output_csv,
                stdout=result.stdout,
                stderr=result.stderr,
            )
        else:
            error_msg = f"Failed to generate heatmap CSV. Return code: {result.returncode}"
            if not csv_exists:
                error_msg += f". CSV not found at {output_csv}"
            return HeatmapGenerationResult(
                success=False,
                stdout=result.stdout,
                stderr=result.stderr,
                error=error_msg,
            )

    except subprocess.TimeoutExpired:
        return HeatmapGenerationResult(
            success=False,
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return HeatmapGenerationResult(
            success=False,
            error=f"Execution failed: {e}",
        )


def generate_heatmap_with_png(
    odb_file: Path,
    heatmap_type: str,
    output_csv: Path,
    output_png: Optional[Path] = None,
    container: str = "openroad/orfs:latest",
    timeout: int = 120,
) -> HeatmapGenerationResult:
    """Generate heatmap CSV and PNG visualization.

    This is a convenience function that:
    1. Generates CSV heatmap using OpenROAD GUI
    2. Renders PNG visualization using matplotlib

    Args:
        odb_file: Path to ODB database file
        heatmap_type: Type of heatmap to generate
        output_csv: Path where CSV should be saved
        output_png: Optional path for PNG (defaults to CSV path with .png extension)
        container: Docker container image
        timeout: Timeout in seconds

    Returns:
        HeatmapGenerationResult with both CSV and PNG paths
    """
    # Generate CSV
    result = generate_heatmap_csv(
        odb_file=odb_file,
        heatmap_type=heatmap_type,
        output_csv=output_csv,
        container=container,
        timeout=timeout,
    )

    if not result.success:
        return result

    # Determine PNG path
    if output_png is None:
        output_png = output_csv.with_suffix(".png")

    # Render PNG using heatmap_renderer
    try:
        from visualization.heatmap_renderer import render_heatmap_png

        # Convert bbox CSV to grid CSV for visualization
        grid_csv = output_csv.with_suffix(".grid.csv")
        convert_bbox_heatmap_to_grid(output_csv, grid_csv)

        # Render grid as PNG
        render_heatmap_png(
            csv_path=grid_csv,
            output_path=output_png,
            title=heatmap_type,
        )

        return HeatmapGenerationResult(
            success=True,
            csv_path=output_csv,
            png_path=output_png,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    except Exception as e:
        return HeatmapGenerationResult(
            success=False,
            csv_path=output_csv,
            error=f"PNG rendering failed: {e}",
            stdout=result.stdout,
            stderr=result.stderr,
        )


def convert_bbox_heatmap_to_grid(
    bbox_csv: Path,
    grid_csv: Path,
    grid_size: int | None = 50,
    preserve_aspect_ratio: bool = False,
) -> dict[str, Any]:
    """Convert OpenROAD bbox heatmap format to grid format.

    OpenROAD outputs heatmaps as: x0,y0,x1,y1,value (bounding boxes)
    This converts it to a regular grid for visualization.

    Args:
        bbox_csv: Path to bbox format CSV from OpenROAD
        grid_csv: Path where grid CSV should be saved
        grid_size: Size of output grid.
                   - int: Fixed grid size (e.g., 50 creates 50x50)
                   - None: Auto-calculate based on aspect ratio
                   Default: 50 for backward compatibility
        preserve_aspect_ratio: If True, use aspect-ratio-aware grid sizing
                               (ignored if grid_size is None, which always preserves ratio)

    Returns:
        Metadata dict with bounds, dimensions, and aspect ratio
    """
    import csv
    import numpy as np

    # Read bbox data
    boxes = []
    with open(bbox_csv) as f:
        reader = csv.reader(f)
        header = next(reader, None)  # Skip header
        for row in reader:
            if len(row) == 5:
                x0, y0, x1, y1, value = row
                boxes.append({
                    'x0': float(x0),
                    'y0': float(y0),
                    'x1': float(x1),
                    'y1': float(y1),
                    'value': float(value),
                })

    if not boxes:
        raise ValueError("No boxes found in heatmap CSV")

    # Determine bounds
    min_x = min(b['x0'] for b in boxes)
    max_x = max(b['x1'] for b in boxes)
    min_y = min(b['y0'] for b in boxes)
    max_y = max(b['y1'] for b in boxes)

    width_um = max_x - min_x
    height_um = max_y - min_y
    aspect_ratio = width_um / height_um if height_um > 0 else 1.0

    # Determine grid dimensions
    if grid_size is None or preserve_aspect_ratio:
        # Auto-calculate based on aspect ratio
        base_size = grid_size if grid_size is not None else 50
        if aspect_ratio >= 1.0:
            grid_x = int(base_size * aspect_ratio)
            grid_y = base_size
        else:
            grid_x = base_size
            grid_y = int(base_size / aspect_ratio)
    else:
        grid_x = grid_size
        grid_y = grid_size

    # Create grid
    grid = np.zeros((grid_y, grid_x), dtype=np.float64)

    # Map boxes to grid
    dx = width_um / grid_x if width_um > 0 else 1.0
    dy = height_um / grid_y if height_um > 0 else 1.0

    for box in boxes:
        # Find grid cells overlapped by this box
        i0 = int((box['y0'] - min_y) / dy)
        i1 = min(int((box['y1'] - min_y) / dy) + 1, grid_y)
        j0 = int((box['x0'] - min_x) / dx)
        j1 = min(int((box['x1'] - min_x) / dx) + 1, grid_x)

        # Set value in grid
        for i in range(max(0, i0), min(grid_y, i1)):
            for j in range(max(0, j0), min(grid_x, j1)):
                grid[i, j] = max(grid[i, j], box['value'])

    # Write grid CSV
    grid_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(grid_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        for row in grid:
            writer.writerow(row)

    # Return metadata
    return {
        "bounds": {
            "min_x": min_x,
            "max_x": max_x,
            "min_y": min_y,
            "max_y": max_y,
        },
        "width_um": width_um,
        "height_um": height_um,
        "aspect_ratio": aspect_ratio,
        "grid_shape": (grid_y, grid_x),
        "box_count": len(boxes),
    }


def verify_heatmap_is_real(csv_path: Path) -> bool:
    """Verify that heatmap CSV contains real data (not mocked).

    Args:
        csv_path: Path to heatmap CSV file

    Returns:
        True if heatmap appears to contain real data
    """
    if not csv_path.exists():
        return False

    # Read CSV and check properties
    try:
        import csv

        rows = []
        with open(csv_path) as f:
            reader = csv.reader(f)
            # Skip header if present
            header = next(reader, None)
            for row in reader:
                if not row:
                    continue
                rows.append(row)

        if not rows:
            return False

        # OpenROAD heatmap format: x0,y0,x1,y1,value
        # Check that we have at least 5 rows (reasonable for a real design)
        if len(rows) < 5:
            return False

        # Check that rows have 5 columns
        if len(rows[0]) != 5:
            return False

        # Extract values (last column)
        values = []
        for row in rows:
            try:
                val = float(row[4])
                values.append(val)
            except (ValueError, IndexError):
                return False

        # Real heatmaps should have:
        # 1. Some variation in values
        if len(set(values)) < 2:
            return False

        # 2. At least some non-zero values
        non_zero = [v for v in values if v != 0.0]
        if len(non_zero) == 0:
            return False

        # 3. Values in reasonable range (0-100 for percentages)
        max_val = max(values)
        if max_val < 0 or max_val > 200:
            # Outside reasonable range
            return False

        # If all checks pass, consider it real
        return True

    except Exception:
        return False
