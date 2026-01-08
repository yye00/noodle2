"""OpenROAD command logging for debugging and reproducibility.

This module provides utilities to log OpenROAD commands during trial execution,
capturing command text, timing information, and return codes. This enables:
- Detailed debugging of failed trials
- Reproducible command sequences
- Performance profiling of individual commands
- Audit trail for compliance

Example usage in TCL script:
    # Initialize command logging
    proc log_command {cmd} {
        set start_time [clock milliseconds]
        set status [catch {eval $cmd} result]
        set end_time [clock milliseconds]
        set elapsed [expr {$end_time - $start_time}]

        # Log to file
        set log_fp [open "command_log.txt" a]
        puts $log_fp "[clock format [clock seconds]] | $elapsed ms | status=$status | $cmd"
        close $log_fp

        if {$status != 0} {
            error "Command failed: $cmd\\nError: $result"
        }
        return $result
    }
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class CommandLogEntry:
    """Single OpenROAD command log entry."""

    timestamp: datetime
    command: str
    duration_ms: int
    status: int  # 0 = success, non-zero = error
    output: str = ""
    error_message: str = ""


class CommandLogParser:
    """Parse OpenROAD command logs."""

    def __init__(self) -> None:
        """Initialize command log parser."""
        pass

    def parse_log_file(self, log_path: Path) -> list[CommandLogEntry]:
        """Parse command log file.

        Expected format:
        <timestamp> | <duration_ms> ms | status=<code> | <command>

        Args:
            log_path: Path to command log file

        Returns:
            List of CommandLogEntry objects

        Raises:
            FileNotFoundError: If log file doesn't exist
        """
        if not log_path.exists():
            raise FileNotFoundError(f"Command log not found: {log_path}")

        entries: list[CommandLogEntry] = []
        content = log_path.read_text()

        for line in content.split("\n"):
            line = line.strip()
            if not line:
                continue

            entry = self._parse_line(line)
            if entry:
                entries.append(entry)

        return entries

    def _parse_line(self, line: str) -> CommandLogEntry | None:
        """Parse single log line.

        Format: <timestamp> | <duration> ms | status=<code> | <command>
        """
        # Match pattern: timestamp | duration ms | status=code | command
        pattern = r"(.+?)\s*\|\s*(\d+)\s*ms\s*\|\s*status=(\d+)\s*\|\s*(.+)"
        match = re.match(pattern, line)

        if not match:
            return None

        timestamp_str, duration_str, status_str, command = match.groups()

        # Parse timestamp (format: "Wed Jan  8 12:34:56 EST 2026")
        try:
            timestamp = datetime.strptime(timestamp_str.strip(), "%a %b %d %H:%M:%S %Z %Y")
        except ValueError:
            # Try alternate format
            try:
                timestamp = datetime.fromisoformat(timestamp_str.strip())
            except ValueError:
                # If parsing fails, use current time
                timestamp = datetime.now()

        return CommandLogEntry(
            timestamp=timestamp,
            command=command.strip(),
            duration_ms=int(duration_str),
            status=int(status_str),
        )

    def find_failed_commands(self, entries: list[CommandLogEntry]) -> list[CommandLogEntry]:
        """Find all commands that failed (status != 0).

        Args:
            entries: List of command log entries

        Returns:
            List of failed command entries
        """
        return [entry for entry in entries if entry.status != 0]

    def get_slowest_commands(self, entries: list[CommandLogEntry], n: int = 10) -> list[CommandLogEntry]:
        """Get the N slowest commands by duration.

        Args:
            entries: List of command log entries
            n: Number of slowest commands to return

        Returns:
            List of slowest command entries, sorted by duration (descending)
        """
        sorted_entries = sorted(entries, key=lambda e: e.duration_ms, reverse=True)
        return sorted_entries[:n]

    def get_total_duration_ms(self, entries: list[CommandLogEntry]) -> int:
        """Calculate total duration of all commands.

        Args:
            entries: List of command log entries

        Returns:
            Total duration in milliseconds
        """
        return sum(entry.duration_ms for entry in entries)

    def group_by_command_prefix(self, entries: list[CommandLogEntry]) -> dict[str, list[CommandLogEntry]]:
        """Group commands by their prefix (first word).

        Args:
            entries: List of command log entries

        Returns:
            Dictionary mapping command prefixes to lists of entries
        """
        groups: dict[str, list[CommandLogEntry]] = {}

        for entry in entries:
            # Extract first word as prefix
            prefix = entry.command.split()[0] if entry.command else "unknown"
            if prefix not in groups:
                groups[prefix] = []
            groups[prefix].append(entry)

        return groups


def generate_tcl_logging_prologue(log_file: str = "command_log.txt") -> str:
    """Generate TCL code to set up command logging.

    This returns a TCL proc definition that can be included at the beginning
    of any OpenROAD TCL script to enable command logging.

    Args:
        log_file: Name of log file to write commands to

    Returns:
        TCL code as string
    """
    return f'''# ============================================================================
# COMMAND LOGGING SETUP (Noodle 2)
# ============================================================================

# Initialize command log file
set ::noodle_command_log "{log_file}"
set log_fp [open $::noodle_command_log w]
puts $log_fp "# Noodle 2 OpenROAD Command Log"
puts $log_fp "# Started: [clock format [clock seconds]]"
puts $log_fp ""
close $log_fp

# Command logging procedure
proc log_command {{cmd}} {{
    global ::noodle_command_log

    set start_time [clock milliseconds]
    set status [catch {{eval $cmd}} result]
    set end_time [clock milliseconds]
    set elapsed [expr {{$end_time - $start_time}}]

    # Log to file
    set log_fp [open $::noodle_command_log a]
    puts $log_fp "[clock format [clock seconds]] | $elapsed ms | status=$status | $cmd"
    close $log_fp

    # If command failed, log error details
    if {{$status != 0}} {{
        set log_fp [open $::noodle_command_log a]
        puts $log_fp "  ERROR: $result"
        close $log_fp
    }}

    # Re-throw error to maintain normal error handling
    if {{$status != 0}} {{
        error "Command failed: $cmd\\nError: $result"
    }}

    return $result
}}

# Convenience wrapper for common commands
proc log_puts {{msg}} {{
    puts $msg
}}

puts "Command logging enabled: $::noodle_command_log"
puts ""

# ============================================================================
'''


def generate_tcl_logging_epilogue() -> str:
    """Generate TCL code to finalize command logging.

    Returns:
        TCL code as string
    """
    return '''
# ============================================================================
# COMMAND LOGGING FINALIZATION
# ============================================================================

set log_fp [open $::noodle_command_log a]
puts $log_fp ""
puts $log_fp "# Completed: [clock format [clock seconds]]"
close $log_fp

puts ""
puts "Command log written: $::noodle_command_log"

# ============================================================================
'''


def format_command_summary(entries: list[CommandLogEntry]) -> str:
    """Format command log entries as human-readable summary.

    Args:
        entries: List of command log entries

    Returns:
        Formatted summary string
    """
    if not entries:
        return "No commands logged"

    lines = ["OpenROAD Command Log Summary", "=" * 80, ""]

    total_duration = sum(e.duration_ms for e in entries)
    failed_count = sum(1 for e in entries if e.status != 0)

    lines.append(f"Total commands: {len(entries)}")
    lines.append(f"Failed commands: {failed_count}")
    lines.append(f"Total duration: {total_duration} ms ({total_duration / 1000:.2f} s)")
    lines.append("")

    if failed_count > 0:
        lines.append("Failed Commands:")
        lines.append("-" * 80)
        for entry in entries:
            if entry.status != 0:
                lines.append(f"  [{entry.timestamp}] {entry.command}")
                lines.append(f"    Status: {entry.status}")
                if entry.error_message:
                    lines.append(f"    Error: {entry.error_message}")
        lines.append("")

    # Show top 5 slowest commands
    slowest = sorted(entries, key=lambda e: e.duration_ms, reverse=True)[:5]
    if slowest:
        lines.append("Slowest Commands:")
        lines.append("-" * 80)
        for entry in slowest:
            lines.append(f"  {entry.duration_ms:6d} ms | {entry.command}")
        lines.append("")

    return "\n".join(lines)


def analyze_command_log(log_path: Path) -> dict[str, Any]:
    """Analyze command log and return structured statistics.

    Args:
        log_path: Path to command log file

    Returns:
        Dictionary with analysis results:
        {
            "total_commands": int,
            "failed_commands": int,
            "total_duration_ms": int,
            "average_duration_ms": float,
            "slowest_command": CommandLogEntry,
            "failed_entries": list[CommandLogEntry],
            "command_type_breakdown": dict[str, int],
        }
    """
    parser = CommandLogParser()
    entries = parser.parse_log_file(log_path)

    if not entries:
        return {
            "total_commands": 0,
            "failed_commands": 0,
            "total_duration_ms": 0,
            "average_duration_ms": 0.0,
            "slowest_command": None,
            "failed_entries": [],
            "command_type_breakdown": {},
        }

    failed_entries = parser.find_failed_commands(entries)
    total_duration = parser.get_total_duration_ms(entries)
    groups = parser.group_by_command_prefix(entries)

    # Count commands by type
    command_type_breakdown = {prefix: len(entries_list) for prefix, entries_list in groups.items()}

    # Find slowest command
    slowest = max(entries, key=lambda e: e.duration_ms) if entries else None

    return {
        "total_commands": len(entries),
        "failed_commands": len(failed_entries),
        "total_duration_ms": total_duration,
        "average_duration_ms": total_duration / len(entries) if entries else 0.0,
        "slowest_command": slowest,
        "failed_entries": failed_entries,
        "command_type_breakdown": command_type_breakdown,
    }
