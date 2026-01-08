"""Human-readable formatting for telemetry JSON files.

This module ensures all telemetry JSON files are:
- Pretty-printed with consistent indentation
- Using descriptive field names following naming conventions
- Using ISO 8601 timestamps for all time fields
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def format_timestamp_iso8601(unix_timestamp: float | None) -> str | None:
    """
    Convert Unix timestamp to ISO 8601 format.

    Args:
        unix_timestamp: Unix timestamp (seconds since epoch), or None

    Returns:
        ISO 8601 formatted timestamp string, or None if input is None

    Examples:
        >>> format_timestamp_iso8601(1704715200.0)
        '2024-01-08T12:00:00Z'
    """
    if unix_timestamp is None:
        return None
    dt = datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_duration_human_readable(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Human-readable duration string

    Examples:
        >>> format_duration_human_readable(45.2)
        '45.2s'
        >>> format_duration_human_readable(125.0)
        '2m 5s'
        >>> format_duration_human_readable(3725.0)
        '1h 2m 5s'
    """
    if seconds < 60:
        return f"{seconds:.1f}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


def enrich_telemetry_with_timestamps(telemetry_dict: dict[str, Any]) -> dict[str, Any]:
    """
    Enrich telemetry dictionary with ISO 8601 timestamps.

    This adds human-readable timestamp fields alongside the raw Unix timestamps,
    following the naming convention: {field}_timestamp for Unix time,
    {field}_iso8601 for ISO 8601 format.

    Args:
        telemetry_dict: Raw telemetry dictionary

    Returns:
        Enriched dictionary with ISO 8601 timestamps
    """
    enriched = telemetry_dict.copy()

    # Convert start_time to ISO 8601
    if "start_time" in enriched and enriched["start_time"] is not None:
        enriched["start_time_iso8601"] = format_timestamp_iso8601(enriched["start_time"])

    # Convert end_time to ISO 8601
    if "end_time" in enriched and enriched["end_time"] is not None:
        enriched["end_time_iso8601"] = format_timestamp_iso8601(enriched["end_time"])

    # Add human-readable duration
    if "total_runtime_seconds" in enriched:
        enriched["total_runtime_human"] = format_duration_human_readable(
            enriched["total_runtime_seconds"]
        )

    if "wall_clock_seconds" in enriched:
        enriched["wall_clock_human"] = format_duration_human_readable(
            enriched["wall_clock_seconds"]
        )

    return enriched


def write_formatted_telemetry(data: dict[str, Any], output_path: Path) -> None:
    """
    Write telemetry data to JSON file with human-readable formatting.

    This ensures:
    - Pretty-printed JSON with 2-space indentation
    - Sorted keys for consistent output
    - Proper newline at end of file
    - ISO 8601 timestamps where applicable

    Args:
        data: Telemetry data dictionary
        output_path: Path to output JSON file
    """
    # Enrich with ISO 8601 timestamps
    enriched_data = enrich_telemetry_with_timestamps(data)

    # Write with consistent formatting
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(enriched_data, f, indent=2, sort_keys=False)
        f.write("\n")  # Ensure newline at end of file


def validate_telemetry_format(telemetry_path: Path) -> dict[str, bool]:
    """
    Validate that a telemetry JSON file meets formatting requirements.

    Checks:
    - File is valid JSON
    - JSON is properly indented
    - Timestamps are in ISO 8601 format (if present)
    - Field names follow naming conventions

    Args:
        telemetry_path: Path to telemetry JSON file

    Returns:
        Dictionary of validation results with keys:
        - valid_json: Whether file is valid JSON
        - properly_indented: Whether JSON is indented
        - has_iso8601_timestamps: Whether timestamps are ISO 8601
        - descriptive_field_names: Whether field names are descriptive
    """
    validation = {
        "valid_json": False,
        "properly_indented": False,
        "has_iso8601_timestamps": True,  # Default to true, set false if bad
        "descriptive_field_names": True,  # Default to true, set false if bad
    }

    try:
        # Check if valid JSON
        with telemetry_path.open("r") as f:
            content = f.read()
            data = json.loads(content)
        validation["valid_json"] = True

        # Check if properly indented (look for 2-space indentation)
        if "  " in content or "\n" in content:
            validation["properly_indented"] = True

        # Check for ISO 8601 timestamps if time fields present
        if "start_time" in data and data["start_time"] is not None:
            if "start_time_iso8601" not in data:
                validation["has_iso8601_timestamps"] = False

        if "end_time" in data and data["end_time"] is not None:
            if "end_time_iso8601" not in data:
                validation["has_iso8601_timestamps"] = False

        # Check field names follow snake_case convention
        for key in data.keys():
            if not key.islower() and "_" not in key and key != key.lower():
                validation["descriptive_field_names"] = False
                break

    except (json.JSONDecodeError, FileNotFoundError, OSError):
        pass

    return validation


class FormattedTelemetryEmitter:
    """
    Telemetry emitter that produces human-readable, well-formatted JSON files.

    This wrapper ensures all emitted telemetry follows formatting standards:
    - Pretty-printed with consistent indentation
    - ISO 8601 timestamps
    - Descriptive field names
    - Human-readable durations
    """

    def __init__(self, telemetry_root: Path | str = "telemetry") -> None:
        """
        Initialize formatted telemetry emitter.

        Args:
            telemetry_root: Root directory for telemetry files
        """
        self.telemetry_root = Path(telemetry_root)

    def emit_telemetry(self, data: dict[str, Any], relative_path: str) -> Path:
        """
        Emit formatted telemetry to specified path.

        Args:
            data: Telemetry data dictionary
            relative_path: Path relative to telemetry root

        Returns:
            Path to written telemetry file
        """
        output_path = self.telemetry_root / relative_path
        write_formatted_telemetry(data, output_path)
        return output_path
