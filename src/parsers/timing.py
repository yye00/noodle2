"""Parser for OpenROAD timing report outputs."""

import re
from pathlib import Path

from src.controller.types import TimingMetrics


def parse_timing_report(report_path: str | Path) -> TimingMetrics:
    """
    Parse OpenROAD report_checks output and extract timing metrics.

    The parser looks for lines like:
    - "wns -123.45" or "slack -123.45"
    - "tns -456.78"
    - Timing path information

    Args:
        report_path: Path to timing report file

    Returns:
        TimingMetrics object with extracted values

    Raises:
        FileNotFoundError: If report file doesn't exist
        ValueError: If report cannot be parsed
    """
    report_path = Path(report_path)
    if not report_path.exists():
        raise FileNotFoundError(f"Timing report not found: {report_path}")

    content = report_path.read_text()
    return parse_timing_report_content(content)


def parse_timing_report_content(content: str) -> TimingMetrics:
    """
    Parse timing report content string.

    Supports various OpenROAD timing report formats:
    - report_checks output
    - report_wns output
    - JSON format metrics

    Args:
        content: Report content as string

    Returns:
        TimingMetrics object

    Raises:
        ValueError: If required metrics cannot be extracted
    """
    wns_ps: int | None = None
    tns_ps: int | None = None
    failing_endpoints: int | None = None

    lines = content.split("\n")

    for line in lines:
        line = line.strip()

        # Match WNS (Worst Negative Slack)
        # Formats:
        #   "wns -123.45"
        #   "slack -123.45"
        #   "WNS: -123.45 ns"
        wns_match = re.search(r"(?:wns|slack|WNS)\s*[:\s]\s*(-?\d+\.?\d*)\s*(ns|ps)?", line, re.IGNORECASE)
        if wns_match and wns_ps is None:
            value = float(wns_match.group(1))
            unit = wns_match.group(2)

            # Convert to picoseconds
            if unit and unit.lower() == "ns":
                wns_ps = int(value * 1000)
            elif unit and unit.lower() == "ps":
                wns_ps = int(value)
            else:
                # Assume nanoseconds if no unit specified (common default)
                wns_ps = int(value * 1000)

        # Match TNS (Total Negative Slack)
        tns_match = re.search(r"(?:tns|TNS)\s*[:\s]\s*(-?\d+\.?\d*)\s*(ns|ps)?", line, re.IGNORECASE)
        if tns_match and tns_ps is None:
            value = float(tns_match.group(1))
            unit = tns_match.group(2)

            # Convert to picoseconds
            if unit and unit.lower() == "ns":
                tns_ps = int(value * 1000)
            elif unit and unit.lower() == "ps":
                tns_ps = int(value)
            else:
                tns_ps = int(value * 1000)

        # Match failing endpoints
        endpoint_match = re.search(r"failing\s+endpoints?\s*[:\s]\s*(\d+)", line, re.IGNORECASE)
        if endpoint_match and failing_endpoints is None:
            failing_endpoints = int(endpoint_match.group(1))

    # WNS is required
    if wns_ps is None:
        raise ValueError("Could not extract WNS from timing report")

    return TimingMetrics(
        wns_ps=wns_ps,
        tns_ps=tns_ps,
        failing_endpoints=failing_endpoints,
    )


def parse_openroad_metrics_json(content: str) -> TimingMetrics:
    """
    Parse OpenROAD metrics in JSON format.

    Some OpenROAD flows emit metrics.json files with timing data.

    Args:
        content: JSON content as string

    Returns:
        TimingMetrics object
    """
    import json

    data = json.loads(content)

    # Extract timing metrics from JSON
    # Common keys: "wns", "tns", "worst_slack", "wns_ps", "tns_ps", etc.
    wns = data.get("wns") or data.get("worst_slack") or data.get("wns_ps")
    tns = data.get("tns") or data.get("total_negative_slack") or data.get("tns_ps")

    if wns is None:
        raise ValueError("Could not extract WNS from metrics JSON")

    # Values might be in ns or ps
    # If the key is "wns_ps" or "tns_ps", values are already in picoseconds
    # Otherwise, assume nanoseconds and convert
    if "wns_ps" in data:
        wns_ps = int(float(wns))
    else:
        # Convert from ns to ps, or assume ps if value is already large
        wns_ps = int(float(wns) * 1000) if abs(float(wns)) < 10000 else int(float(wns))

    if tns is not None:
        if "tns_ps" in data:
            tns_ps = int(float(tns))
        else:
            tns_ps = int(float(tns) * 1000) if abs(float(tns)) < 10000 else int(float(tns))
    else:
        tns_ps = None

    return TimingMetrics(
        wns_ps=wns_ps,
        tns_ps=tns_ps,
        failing_endpoints=data.get("failing_endpoints"),
    )
