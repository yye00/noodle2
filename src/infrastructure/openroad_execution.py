"""OpenROAD command execution and timing report parsing.

This module provides functions to execute OpenROAD commands via Docker
and parse timing reports to extract metrics like WNS and TNS.
"""

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class TimingMetrics:
    """Parsed timing metrics from OpenROAD report_checks."""

    wns_ps: Optional[float] = None  # Worst Negative Slack in picoseconds
    tns_ps: Optional[float] = None  # Total Negative Slack in picoseconds
    whs_ps: Optional[float] = None  # Worst Hold Slack in picoseconds
    ths_ps: Optional[float] = None  # Total Hold Slack in picoseconds
    clock_period_ps: Optional[float] = None
    setup_violation_count: int = 0
    hold_violation_count: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "wns_ps": self.wns_ps,
            "tns_ps": self.tns_ps,
            "whs_ps": self.whs_ps,
            "ths_ps": self.ths_ps,
            "clock_period_ps": self.clock_period_ps,
            "setup_violation_count": self.setup_violation_count,
            "hold_violation_count": self.hold_violation_count,
        }


@dataclass
class OpenROADExecutionResult:
    """Result of executing an OpenROAD command."""

    success: bool
    stdout: str = ""
    stderr: str = ""
    output_file: Optional[Path] = None
    error: Optional[str] = None


def execute_openroad_command(
    odb_file: Path,
    tcl_commands: list[str],
    output_file: Optional[Path] = None,
    container: str = "openroad/orfs:latest",
    timeout: int = 60,
) -> OpenROADExecutionResult:
    """Execute OpenROAD commands on an ODB file.

    Args:
        odb_file: Path to ODB database file
        tcl_commands: List of TCL commands to execute
        output_file: Optional path to save output
        container: Docker container image
        timeout: Timeout in seconds

    Returns:
        OpenROADExecutionResult with execution status and output.
    """
    if not odb_file.exists():
        return OpenROADExecutionResult(
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

    # OpenROAD binary path in container
    openroad_bin = "/OpenROAD-flow-scripts/tools/install/OpenROAD/bin/openroad"

    # Build TCL script as a multiline string
    tcl_lines = [f"read_db {rel_odb_path}"]
    tcl_lines.extend(tcl_commands)
    tcl_lines.append("exit")

    # Create the heredoc content
    tcl_script = "\n".join(tcl_lines)

    # Build Docker command with properly escaped heredoc
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

        # Save output to file if requested
        if output_file and result.stdout:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            output_file.write_text(result.stdout)

        return OpenROADExecutionResult(
            success=result.returncode == 0,
            stdout=result.stdout,
            stderr=result.stderr,
            output_file=output_file if output_file and output_file.exists() else None,
            error=None if result.returncode == 0 else f"OpenROAD returned {result.returncode}",
        )

    except subprocess.TimeoutExpired:
        return OpenROADExecutionResult(
            success=False,
            error=f"Timeout after {timeout}s",
        )
    except Exception as e:
        return OpenROADExecutionResult(
            success=False,
            error=f"Execution failed: {e}",
        )


def run_report_checks(
    odb_file: Path,
    output_file: Optional[Path] = None,
    platform: str = "nangate45",
    design: str = "gcd",
    container: str = "openroad/orfs:latest",
) -> OpenROADExecutionResult:
    """Run OpenROAD report_checks command on an ODB file.

    This loads the necessary liberty libraries and timing constraints
    before running timing analysis.

    Args:
        odb_file: Path to ODB database file
        output_file: Optional path to save timing report
        platform: Platform name for finding liberty files (default: nangate45)
        design: Design name for finding constraints (default: gcd)
        container: Docker container image

    Returns:
        OpenROADExecutionResult with timing report in stdout.
    """
    # Paths inside the container for platform files
    lib_path = f"/OpenROAD-flow-scripts/flow/platforms/{platform}/lib"
    sdc_path = f"/OpenROAD-flow-scripts/flow/designs/{platform}/{design}/constraint.sdc"

    # Commands to set up timing analysis
    commands = [
        # Load liberty library for standard cells
        f"read_liberty {lib_path}/NangateOpenCellLibrary_typical.lib",
        # Read timing constraints
        f"read_sdc {sdc_path}",
        # Run timing report
        "report_checks -path_delay min_max -format full_clock_expanded -fields {capacitance slew input_pins} -digits 3",
    ]

    return execute_openroad_command(
        odb_file=odb_file,
        tcl_commands=commands,
        output_file=output_file,
        container=container,
        timeout=120,
    )


def parse_timing_report(report_text: str) -> TimingMetrics:
    """Parse OpenROAD timing report to extract WNS and TNS.

    Args:
        report_text: Text output from report_checks command

    Returns:
        TimingMetrics with parsed values.
    """
    metrics = TimingMetrics()

    # Parse slack values from timing report
    # OpenROAD format: "    slack (MET)" or "    slack (VIOLATED)"
    # Followed by actual slack value
    # Pattern: whitespace + slack value + either (MET) or (VIOLATED)
    slack_pattern = r"^\s+(-?\d+\.?\d+)\s+slack\s+\((MET|VIOLATED)\)"

    setup_slacks = []
    hold_slacks = []

    # Split report into path sections
    lines = report_text.split('\n')
    current_path_type = None

    for i, line in enumerate(lines):
        # Detect path type
        if "Path Type: max" in line:
            current_path_type = "setup"
        elif "Path Type: min" in line:
            current_path_type = "hold"

        # Parse slack values
        match = re.match(slack_pattern, line)
        if match:
            slack_value = float(match.group(1))
            met_or_violated = match.group(2)

            # Slack is reported as positive value with MET or VIOLATED indicator
            # Convert to signed: VIOLATED means negative slack
            if met_or_violated == "VIOLATED":
                slack_value = -abs(slack_value)

            if current_path_type == "setup":
                setup_slacks.append(slack_value)
            elif current_path_type == "hold":
                hold_slacks.append(slack_value)

    # Calculate WNS (worst negative slack) for setup
    if setup_slacks:
        wns = min(setup_slacks)  # Most negative is worst
        metrics.wns_ps = wns * 1000.0  # ns to ps

        # Calculate TNS (total negative slack)
        negative_slacks = [s for s in setup_slacks if s < 0]
        if negative_slacks:
            metrics.tns_ps = sum(negative_slacks) * 1000.0
            metrics.setup_violation_count = len(negative_slacks)

    # Calculate WHS (worst hold slack)
    if hold_slacks:
        whs = min(hold_slacks)
        metrics.whs_ps = whs * 1000.0

        # Calculate THS (total hold slack)
        hold_violations = [s for s in hold_slacks if s < 0]
        if hold_violations:
            metrics.ths_ps = sum(hold_violations) * 1000.0
            metrics.hold_violation_count = len(hold_violations)

    # Parse clock period from timing constraints
    period_pattern = r"clock\s+\w+\s+.*?period\s+(-?\d+\.?\d+)"
    period_match = re.search(period_pattern, report_text, re.IGNORECASE)
    if period_match:
        metrics.clock_period_ps = float(period_match.group(1)) * 1000.0

    return metrics


def extract_timing_metrics(
    odb_file: Path,
    metrics_output: Optional[Path] = None,
    report_output: Optional[Path] = None,
) -> tuple[TimingMetrics, bool]:
    """Execute report_checks and extract timing metrics.

    Args:
        odb_file: Path to ODB database file
        metrics_output: Optional path to save metrics JSON
        report_output: Optional path to save full timing report

    Returns:
        Tuple of (TimingMetrics, success boolean)
    """
    # Run report_checks
    result = run_report_checks(odb_file, report_output)

    if not result.success:
        return TimingMetrics(), False

    # Parse timing report
    metrics = parse_timing_report(result.stdout)

    # Save metrics to JSON if requested
    if metrics_output:
        metrics_output.parent.mkdir(parents=True, exist_ok=True)
        with metrics_output.open("w") as f:
            json.dump(metrics.to_dict(), f, indent=2)

    return metrics, True


def verify_metrics_are_real(metrics: TimingMetrics) -> bool:
    """Verify that timing metrics contain real values (not mocked).

    Args:
        metrics: TimingMetrics object

    Returns:
        True if metrics appear to be real (have actual numeric values)
    """
    # Check that at least WNS is set
    if metrics.wns_ps is None:
        return False

    # Real metrics should have reasonable magnitudes
    # WNS for a real design should be in a reasonable range
    # (not exactly 0 or suspiciously round numbers)
    if metrics.wns_ps == 0.0:
        # Suspicious - real designs rarely have exactly 0 slack
        return False

    # If we have real metrics, at least one should be set
    has_values = (
        metrics.wns_ps is not None
        or metrics.tns_ps is not None
        or metrics.whs_ps is not None
    )

    return has_values
