"""Study list view with formatted table presentation."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from src.controller.study_catalog import StudyMetadata, load_study_metadata


StudyStatus = Literal["running", "completed", "failed", "blocked", "unknown"]


@dataclass
class StudyListEntry:
    """
    Entry in Study list view with status and presentation metadata.

    Combines StudyMetadata with runtime status information for
    display in catalog views.
    """

    name: str
    status: StudyStatus
    creation_date: str
    tags: list[str]
    safety_domain: str
    pdk: str
    description: str | None = None
    completion_percent: float | None = None
    last_updated: str | None = None

    def format_status_symbol(self) -> str:
        """Get colored symbol for status display."""
        symbols = {
            "completed": "✓",
            "running": "▶",
            "failed": "✗",
            "blocked": "⊗",
            "unknown": "?",
        }
        return symbols.get(self.status, "?")

    def format_tags_compact(self, max_tags: int = 3) -> str:
        """Format tags compactly for table display."""
        if not self.tags:
            return "-"

        displayed = self.tags[:max_tags]
        result = ", ".join(displayed)

        if len(self.tags) > max_tags:
            result += f" (+{len(self.tags) - max_tags})"

        return result

    def format_completion(self) -> str:
        """Format completion percentage for display."""
        if self.completion_percent is None:
            return "-"
        return f"{self.completion_percent:.1f}%"


def discover_studies(telemetry_root: Path | str = "telemetry") -> list[StudyListEntry]:
    """
    Discover all Studies in telemetry directory.

    Scans telemetry directory for Study subdirectories and loads
    metadata for each Study found.

    Args:
        telemetry_root: Root directory containing Study artifacts

    Returns:
        List of StudyListEntry objects sorted by creation date (newest first)
    """
    root = Path(telemetry_root)
    if not root.exists():
        return []

    entries = []

    for study_dir in root.iterdir():
        if not study_dir.is_dir():
            continue

        # Try to load study metadata
        metadata_file = study_dir / "study_metadata.json"
        if not metadata_file.exists():
            # Study directory without metadata - treat as unknown
            entries.append(
                StudyListEntry(
                    name=study_dir.name,
                    status="unknown",
                    creation_date=_get_dir_creation_date(study_dir),
                    tags=[],
                    safety_domain="unknown",
                    pdk="unknown",
                )
            )
            continue

        try:
            metadata = load_study_metadata(study_dir)
            status = _infer_study_status(study_dir)
            completion = _compute_completion_percent(study_dir)

            entries.append(
                StudyListEntry(
                    name=metadata.name,
                    status=status,
                    creation_date=metadata.creation_date or _get_dir_creation_date(study_dir),
                    tags=metadata.tags,
                    safety_domain=metadata.safety_domain,
                    pdk=metadata.pdk,
                    description=metadata.description,
                    completion_percent=completion,
                    last_updated=_get_last_updated(study_dir),
                )
            )
        except Exception:
            # Metadata file corrupt - treat as unknown
            entries.append(
                StudyListEntry(
                    name=study_dir.name,
                    status="unknown",
                    creation_date=_get_dir_creation_date(study_dir),
                    tags=[],
                    safety_domain="unknown",
                    pdk="unknown",
                )
            )

    # Sort by creation date (newest first)
    entries.sort(key=lambda e: e.creation_date or "", reverse=True)

    return entries


def filter_studies(
    studies: list[StudyListEntry],
    status: StudyStatus | Literal["all"] = "all",
    domain: str | Literal["all"] = "all",
) -> list[StudyListEntry]:
    """
    Filter Studies by status and safety domain.

    Args:
        studies: List of StudyListEntry to filter
        status: Filter by status ("all" for no filter)
        domain: Filter by safety domain ("all" for no filter)

    Returns:
        Filtered list of StudyListEntry
    """
    filtered = studies

    if status != "all":
        filtered = [s for s in filtered if s.status == status]

    if domain != "all":
        filtered = [s for s in filtered if s.safety_domain == domain]

    return filtered


def format_study_table(
    studies: list[StudyListEntry],
    include_description: bool = False,
) -> str:
    """
    Format Studies as organized table.

    Produces professional, easy-to-scan table output with columns:
    - Status symbol
    - Name
    - Safety Domain
    - PDK
    - Creation Date
    - Tags
    - (Optional) Description

    Args:
        studies: List of StudyListEntry to format
        include_description: Include description column (wider output)

    Returns:
        Formatted table string ready for terminal display
    """
    if not studies:
        return "No Studies found."

    # Table headers
    headers = ["Status", "Name", "Domain", "PDK", "Created", "Tags"]
    if include_description:
        headers.append("Description")

    # Build rows
    rows = []
    for study in studies:
        row = [
            study.format_status_symbol(),
            study.name,
            study.safety_domain,
            study.pdk,
            _format_date(study.creation_date),
            study.format_tags_compact(),
        ]
        if include_description:
            desc = study.description or "-"
            # Truncate long descriptions
            if len(desc) > 40:
                desc = desc[:37] + "..."
            row.append(desc)
        rows.append(row)

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))

    # Build formatted table
    lines = []

    # Header
    header_line = " │ ".join(
        headers[i].ljust(col_widths[i]) for i in range(len(headers))
    )
    lines.append(header_line)

    # Separator
    separator = "─┼─".join("─" * w for w in col_widths)
    lines.append(separator)

    # Data rows
    for row in rows:
        row_line = " │ ".join(
            str(row[i]).ljust(col_widths[i]) for i in range(len(row))
        )
        lines.append(row_line)

    # Footer with count
    lines.append("")
    lines.append(f"Total: {len(studies)} {'study' if len(studies) == 1 else 'studies'}")

    return "\n".join(lines)


def _infer_study_status(study_dir: Path) -> StudyStatus:
    """
    Infer Study status from artifact directory contents.

    Heuristics:
    - Has study_summary.json with winner → completed
    - Has checkpoint files → running
    - Has error logs or abort markers → failed
    - Has blocked marker → blocked
    - Otherwise → unknown
    """
    # Check for completion markers
    if (study_dir / "study_summary.json").exists():
        return "completed"

    # Check for failure markers
    if (study_dir / "error.log").exists() or (study_dir / "abort_marker").exists():
        return "failed"

    # Check for blocked marker
    if (study_dir / "blocked_marker").exists():
        return "blocked"

    # Check for running indicators (checkpoint or recent activity)
    if (study_dir / "checkpoint.json").exists():
        return "running"

    # Check for any recent activity
    if _has_recent_activity(study_dir, hours=24):
        return "running"

    return "unknown"


def _compute_completion_percent(study_dir: Path) -> float | None:
    """
    Compute completion percentage from Study artifacts.

    Returns None if completion cannot be determined.
    """
    # Check for study summary with stage completion info
    summary_file = study_dir / "study_summary.json"
    if not summary_file.exists():
        return None

    try:
        import json
        with open(summary_file, "r") as f:
            summary = json.load(f)

        # If summary exists, assume completed
        if "winner_case" in summary or "final_stage" in summary:
            return 100.0

        # Try to infer from stage progress
        if "stages" in summary:
            total_stages = len(summary["stages"])
            completed_stages = sum(
                1 for s in summary["stages"] if s.get("status") == "completed"
            )
            return (completed_stages / total_stages) * 100.0
    except Exception:
        pass

    return None


def _get_dir_creation_date(dir_path: Path) -> str:
    """Get directory creation date as ISO string."""
    try:
        stat = dir_path.stat()
        dt = datetime.fromtimestamp(stat.st_ctime)
        return dt.isoformat()
    except Exception:
        return "unknown"


def _get_last_updated(dir_path: Path) -> str | None:
    """Get last modification time of directory contents."""
    try:
        latest = max(
            f.stat().st_mtime
            for f in dir_path.rglob("*")
            if f.is_file()
        )
        dt = datetime.fromtimestamp(latest)
        return dt.isoformat()
    except Exception:
        return None


def _has_recent_activity(dir_path: Path, hours: int = 24) -> bool:
    """Check if directory has been modified recently."""
    try:
        last_updated = _get_last_updated(dir_path)
        if not last_updated:
            return False

        last_dt = datetime.fromisoformat(last_updated)
        now = datetime.now()
        delta = now - last_dt

        return delta.total_seconds() < (hours * 3600)
    except Exception:
        return False


def _format_date(date_str: str | None) -> str:
    """Format ISO date string for compact display."""
    if not date_str or date_str == "unknown":
        return "unknown"

    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return date_str[:10] if len(date_str) >= 10 else date_str
