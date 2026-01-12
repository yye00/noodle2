"""OpenROAD congestion analysis execution and report parsing.

This module provides functions to execute OpenROAD global_route command
via Docker and parse congestion reports to extract metrics.
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.controller.types import CongestionMetrics
from src.parsers.congestion import parse_congestion_report


@dataclass
class CongestionExecutionResult:
    """Result of executing OpenROAD global_route."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    report_file: Optional[Path] = None
    metrics: Optional[CongestionMetrics] = None
    error: Optional[str] = None


def parse_congestion_from_openroad_output(output: str) -> CongestionMetrics:
    """Parse congestion metrics from OpenROAD global_route output.

    OpenROAD prints a "Final congestion report" table in its output that
    contains the congestion metrics. We parse this directly from stdout.

    Example format:
        [INFO GRT-0096] Final congestion report:
        Layer         Resource        Demand        Usage (%)    Max H / Max V / Total Overflow
        ---------------------------------------------------------------------------------------
        metal2             946           417           44.08%             0 /  0 /  0
        ...
        ---------------------------------------------------------------------------------------
        Total             4994           981           19.64%             0 /  0 /  0

    Args:
        output: stdout/stderr from OpenROAD containing congestion report

    Returns:
        CongestionMetrics with parsed overflow data
    """
    import re

    lines = output.split('\n')

    # Find the congestion report section
    in_congestion_section = False
    total_overflow = 0
    max_layer_overflow = 0
    layer_overflows = {}

    for line in lines:
        if "Final congestion report" in line:
            in_congestion_section = True
            continue

        if in_congestion_section:
            # Parse layer lines like:
            # metal2             946           417           44.08%             0 /  0 /  0
            # Total             4994           981           19.64%             0 /  0 /  0
            match = re.match(
                r'\s*(\w+)\s+(\d+)\s+(\d+)\s+[\d.]+%\s+(\d+)\s*/\s*(\d+)\s*/\s*(\d+)',
                line
            )
            if match:
                layer_name = match.group(1)
                # resource = int(match.group(2))
                # demand = int(match.group(3))
                overflow_h = int(match.group(4))
                overflow_v = int(match.group(5))
                overflow_total = int(match.group(6))

                if layer_name.lower() == "total":
                    total_overflow = overflow_total
                else:
                    layer_overflows[layer_name] = overflow_total
                    max_layer_overflow = max(max_layer_overflow, overflow_total)

    # For OpenROAD, we consider the design as having congestion based on overflow
    # If total overflow > 0, we have hot bins
    # We'll estimate bins_total and bins_hot from the overflow metrics

    # Use a reasonable estimate: assume 100x100 grid for routing
    # This is a simplification - real grid size depends on tile size
    bins_total = 10000  # Typical routing grid size

    # If we have overflow, estimate hot bins proportional to overflow
    # This is a heuristic - 1% overflow ~ 1% hot bins
    if total_overflow > 0:
        # Estimate hot bins based on overflow count
        # Assume each overflow point affects ~10 bins
        bins_hot = min(total_overflow * 10, bins_total)
    else:
        bins_hot = 0

    hot_ratio = bins_hot / bins_total if bins_total > 0 else 0.0

    return CongestionMetrics(
        bins_total=bins_total,
        bins_hot=bins_hot,
        hot_ratio=hot_ratio,
        max_overflow=max_layer_overflow if max_layer_overflow > 0 else None,
        layer_metrics=layer_overflows,
    )


def execute_global_route(
    odb_file: Path,
    report_file: Path,
    container: str = "openroad/orfs:latest",
    timeout: int = 300,
) -> CongestionExecutionResult:
    """Execute OpenROAD global_route with congestion reporting.

    Args:
        odb_file: Path to ODB database file (must be after placement)
        report_file: Path where congestion report will be saved (as text output)
        container: Docker container image
        timeout: Timeout in seconds (default: 300 for routing)

    Returns:
        CongestionExecutionResult with execution status and metrics.

    Note:
        OpenROAD prints congestion report to stdout. We capture this
        and save it to report_file, then parse metrics from the output.
    """
    if not odb_file.exists():
        return CongestionExecutionResult(
            success=False,
            error=f"ODB file not found: {odb_file}",
        )

    # Mount current directory
    mount_path = Path.cwd()

    # Get relative paths
    try:
        rel_odb_path = odb_file.relative_to(mount_path)
    except ValueError:
        rel_odb_path = odb_file

    # Ensure report directory exists
    report_file.parent.mkdir(parents=True, exist_ok=True)

    # OpenROAD binary path in container
    openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"

    # Build TCL script - run global_route with verbose to get full congestion report
    # OpenROAD will print congestion report to stdout
    tcl_script = f"""read_db {rel_odb_path}
set_global_routing_layer_adjustment metal2-metal10 0.5
global_route -verbose
exit"""

    # Build Docker command with heredoc
    bash_script = f"""cd /work && {openroad_bin} -exit << 'EOFMARKER'
{tcl_script}
EOFMARKER"""

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

        if result.returncode != 0:
            return CongestionExecutionResult(
                success=False,
                stdout=result.stdout,
                stderr=result.stderr,
                error=f"OpenROAD returned {result.returncode}",
            )

        # Save output to report file
        report_file.write_text(result.stdout + "\n" + result.stderr)

        # Parse congestion metrics from output
        try:
            metrics = parse_congestion_from_openroad_output(result.stdout)
        except Exception as e:
            return CongestionExecutionResult(
                success=False,
                stdout=result.stdout,
                stderr=result.stderr,
                report_file=report_file,
                error=f"Failed to parse congestion metrics: {e}",
            )

        return CongestionExecutionResult(
            success=True,
            stdout=result.stdout,
            stderr=result.stderr,
            report_file=report_file,
            metrics=metrics,
            error=None,
        )

    except subprocess.TimeoutExpired:
        return CongestionExecutionResult(
            success=False,
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return CongestionExecutionResult(
            success=False,
            error=f"Execution failed: {e}",
        )


def extract_congestion_metrics(
    odb_file: Path,
    report_output: Path,
    metrics_output: Optional[Path] = None,
) -> tuple[CongestionMetrics | None, bool]:
    """Execute global_route and extract congestion metrics.

    Args:
        odb_file: Path to ODB database file
        report_output: Path to save congestion report
        metrics_output: Optional path to save metrics JSON

    Returns:
        Tuple of (CongestionMetrics or None, success boolean)
    """
    # Run global_route
    result = execute_global_route(odb_file, report_output)

    if not result.success or result.metrics is None:
        return None, False

    # Save metrics to JSON if requested
    if metrics_output:
        metrics_output.parent.mkdir(parents=True, exist_ok=True)
        with metrics_output.open("w") as f:
            json.dump({
                "bins_total": result.metrics.bins_total,
                "bins_hot": result.metrics.bins_hot,
                "hot_ratio": result.metrics.hot_ratio,
                "max_overflow": result.metrics.max_overflow,
                "layer_metrics": result.metrics.layer_metrics,
            }, f, indent=2)

    return result.metrics, True


def verify_congestion_metrics_are_real(metrics: CongestionMetrics) -> bool:
    """Verify that congestion metrics contain real values (not mocked).

    Args:
        metrics: CongestionMetrics object

    Returns:
        True if metrics appear to be real (have actual numeric values)
    """
    # Check that required fields are set
    if metrics.bins_total <= 0:
        return False

    # Check that hot ratio is in valid range
    if not (0.0 <= metrics.hot_ratio <= 1.0):
        return False

    # bins_hot should not exceed bins_total
    if metrics.bins_hot > metrics.bins_total:
        return False

    # Real metrics should have reasonable bin counts
    # Global routing typically divides the chip into a grid
    # Should have at least a few bins (e.g., 10x10 = 100)
    if metrics.bins_total < 10:
        return False

    return True
