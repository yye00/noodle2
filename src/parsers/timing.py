"""Parser for OpenROAD timing report outputs."""

import re
from pathlib import Path

from src.controller.types import TimingMetrics, TimingPath


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


def parse_timing_paths(content: str, max_paths: int = 10) -> list[TimingPath]:
    """
    Parse detailed timing path information from report_checks output.

    Extracts path details including startpoint, endpoint, path group, type, and slack.

    Args:
        content: Report content as string
        max_paths: Maximum number of paths to extract (default: 10)

    Returns:
        List of TimingPath objects
    """
    paths: list[TimingPath] = []
    lines = content.split("\n")

    i = 0
    while i < len(lines) and len(paths) < max_paths:
        line = lines[i].strip()

        # Look for path header - starts with "Startpoint:"
        if line.startswith("Startpoint:"):
            # Extract startpoint
            startpoint_match = re.search(r"Startpoint:\s+(.+?)(?:\s+\(|$)", line)
            startpoint = startpoint_match.group(1).strip() if startpoint_match else "unknown"

            # Look for endpoint on next line
            endpoint = "unknown"
            path_group = None
            path_type = None
            slack_ps = None

            j = i + 1
            while j < len(lines) and j < i + 100:  # Look ahead up to 100 lines for slack
                next_line = lines[j].strip()

                # Extract endpoint
                if next_line.startswith("Endpoint:"):
                    endpoint_match = re.search(r"Endpoint:\s+(.+?)(?:\s+\(|$)", next_line)
                    endpoint = endpoint_match.group(1).strip() if endpoint_match else "unknown"

                # Extract path group
                elif next_line.startswith("Path Group:"):
                    group_match = re.search(r"Path Group:\s+(.+)", next_line)
                    path_group = group_match.group(1).strip() if group_match else None

                # Extract path type
                elif next_line.startswith("Path Type:"):
                    type_match = re.search(r"Path Type:\s+(.+)", next_line)
                    path_type = type_match.group(1).strip() if type_match else None

                # Extract slack from the slack line
                # Format: "           4.50   slack (MET)" or "          -5.50   slack (VIOLATED)"
                elif "slack" in next_line.lower():
                    slack_match = re.search(r"(-?\d+\.?\d*)\s+slack", next_line, re.IGNORECASE)
                    if slack_match:
                        slack_value = float(slack_match.group(1))
                        # Assume nanoseconds, convert to picoseconds
                        slack_ps = int(slack_value * 1000)
                        break  # Found slack, this path is complete

                # Stop if we hit the next path's startpoint
                elif next_line.startswith("Startpoint:"):
                    break

                j += 1

            # Only add path if we found slack
            if slack_ps is not None:
                paths.append(TimingPath(
                    slack_ps=slack_ps,
                    startpoint=startpoint,
                    endpoint=endpoint,
                    path_group=path_group,
                    path_type=path_type,
                ))

            # Move to next potential path
            i = j + 1
        else:
            i += 1

    return paths


def parse_timing_report_content(content: str, extract_paths: bool = True, max_paths: int = 10) -> TimingMetrics:
    """
    Parse timing report content string.

    Supports various OpenROAD timing report formats:
    - report_checks output
    - report_wns output
    - JSON format metrics

    Args:
        content: Report content as string
        extract_paths: Whether to extract detailed path information (default: True)
        max_paths: Maximum number of paths to extract if extract_paths is True (default: 10)

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

    # Extract detailed paths if requested
    top_paths = []
    if extract_paths:
        top_paths = parse_timing_paths(content, max_paths=max_paths)

    return TimingMetrics(
        wns_ps=wns_ps,
        tns_ps=tns_ps,
        failing_endpoints=failing_endpoints,
        top_paths=top_paths,
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
        top_paths=[],  # JSON format typically doesn't include detailed path info
    )
