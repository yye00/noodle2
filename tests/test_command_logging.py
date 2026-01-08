"""Tests for OpenROAD command logging functionality."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from src.trial_runner.command_logging import (
    CommandLogEntry,
    CommandLogParser,
    analyze_command_log,
    format_command_summary,
    generate_tcl_logging_epilogue,
    generate_tcl_logging_prologue,
)


# Test CommandLogEntry


def test_command_log_entry_creation():
    """Test creating a command log entry."""
    entry = CommandLogEntry(
        timestamp=datetime.now(),
        command="read_verilog design.v",
        duration_ms=1500,
        status=0,
    )
    assert entry.command == "read_verilog design.v"
    assert entry.duration_ms == 1500
    assert entry.status == 0


def test_command_log_entry_with_error():
    """Test command log entry with error status."""
    entry = CommandLogEntry(
        timestamp=datetime.now(),
        command="invalid_command",
        duration_ms=50,
        status=1,
        error_message="Unknown command",
    )
    assert entry.status == 1
    assert entry.error_message == "Unknown command"


# Test CommandLogParser


def test_command_log_parser_instantiation():
    """Test that parser can be created."""
    parser = CommandLogParser()
    assert parser is not None


def test_parse_log_file_not_found():
    """Test that parsing nonexistent file raises error."""
    parser = CommandLogParser()

    with pytest.raises(FileNotFoundError):
        parser.parse_log_file(Path("/nonexistent/file.log"))


def test_parse_empty_log_file():
    """Test parsing empty log file."""
    parser = CommandLogParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "empty.log"
        log_path.write_text("")

        entries = parser.parse_log_file(log_path)

    assert entries == []


def test_parse_log_file_with_single_command():
    """Test parsing log file with one command."""
    parser = CommandLogParser()

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        log_path.write_text("Wed Jan  8 12:34:56 EST 2026 | 1500 ms | status=0 | read_verilog design.v\n")

        entries = parser.parse_log_file(log_path)

    assert len(entries) == 1
    assert entries[0].command == "read_verilog design.v"
    assert entries[0].duration_ms == 1500
    assert entries[0].status == 0


def test_parse_log_file_with_multiple_commands():
    """Test parsing log file with multiple commands."""
    parser = CommandLogParser()

    log_content = """Wed Jan  8 12:34:56 EST 2026 | 1500 ms | status=0 | read_verilog design.v
Wed Jan  8 12:35:00 EST 2026 | 2000 ms | status=0 | synth -top design
Wed Jan  8 12:35:05 EST 2026 | 500 ms | status=0 | report_checks
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        log_path.write_text(log_content)

        entries = parser.parse_log_file(log_path)

    assert len(entries) == 3
    assert entries[0].command == "read_verilog design.v"
    assert entries[1].command == "synth -top design"
    assert entries[2].command == "report_checks"


def test_parse_log_file_with_failed_command():
    """Test parsing log with failed command."""
    parser = CommandLogParser()

    log_content = "Wed Jan  8 12:34:56 EST 2026 | 100 ms | status=1 | invalid_command\n"

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        log_path.write_text(log_content)

        entries = parser.parse_log_file(log_path)

    assert len(entries) == 1
    assert entries[0].status == 1


def test_parse_log_file_ignores_empty_lines():
    """Test that parser skips empty lines."""
    parser = CommandLogParser()

    log_content = """
Wed Jan  8 12:34:56 EST 2026 | 1500 ms | status=0 | read_verilog design.v

Wed Jan  8 12:35:00 EST 2026 | 2000 ms | status=0 | synth -top design

"""

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        log_path.write_text(log_content)

        entries = parser.parse_log_file(log_path)

    assert len(entries) == 2


def test_parse_log_file_handles_malformed_lines():
    """Test that parser gracefully handles malformed lines."""
    parser = CommandLogParser()

    log_content = """Wed Jan  8 12:34:56 EST 2026 | 1500 ms | status=0 | read_verilog design.v
This is a malformed line
Wed Jan  8 12:35:00 EST 2026 | 2000 ms | status=0 | synth -top design
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        log_path.write_text(log_content)

        entries = parser.parse_log_file(log_path)

    # Should parse valid lines and skip malformed
    assert len(entries) == 2


# Test CommandLogParser methods


def test_find_failed_commands():
    """Test finding failed commands."""
    parser = CommandLogParser()

    entries = [
        CommandLogEntry(datetime.now(), "cmd1", 100, 0),
        CommandLogEntry(datetime.now(), "cmd2", 200, 1),
        CommandLogEntry(datetime.now(), "cmd3", 300, 0),
        CommandLogEntry(datetime.now(), "cmd4", 400, 1),
    ]

    failed = parser.find_failed_commands(entries)

    assert len(failed) == 2
    assert failed[0].command == "cmd2"
    assert failed[1].command == "cmd4"


def test_find_failed_commands_with_no_failures():
    """Test finding failed commands when all succeed."""
    parser = CommandLogParser()

    entries = [
        CommandLogEntry(datetime.now(), "cmd1", 100, 0),
        CommandLogEntry(datetime.now(), "cmd2", 200, 0),
    ]

    failed = parser.find_failed_commands(entries)

    assert failed == []


def test_get_slowest_commands():
    """Test getting slowest commands."""
    parser = CommandLogParser()

    entries = [
        CommandLogEntry(datetime.now(), "fast", 100, 0),
        CommandLogEntry(datetime.now(), "slowest", 5000, 0),
        CommandLogEntry(datetime.now(), "medium", 1000, 0),
        CommandLogEntry(datetime.now(), "slow", 3000, 0),
    ]

    slowest = parser.get_slowest_commands(entries, n=2)

    assert len(slowest) == 2
    assert slowest[0].command == "slowest"
    assert slowest[0].duration_ms == 5000
    assert slowest[1].command == "slow"
    assert slowest[1].duration_ms == 3000


def test_get_slowest_commands_with_n_greater_than_entries():
    """Test getting slowest commands when n > number of entries."""
    parser = CommandLogParser()

    entries = [
        CommandLogEntry(datetime.now(), "cmd1", 100, 0),
        CommandLogEntry(datetime.now(), "cmd2", 200, 0),
    ]

    slowest = parser.get_slowest_commands(entries, n=10)

    assert len(slowest) == 2


def test_get_total_duration_ms():
    """Test calculating total duration."""
    parser = CommandLogParser()

    entries = [
        CommandLogEntry(datetime.now(), "cmd1", 1000, 0),
        CommandLogEntry(datetime.now(), "cmd2", 2000, 0),
        CommandLogEntry(datetime.now(), "cmd3", 3000, 0),
    ]

    total = parser.get_total_duration_ms(entries)

    assert total == 6000


def test_get_total_duration_ms_empty():
    """Test calculating total duration with no entries."""
    parser = CommandLogParser()

    total = parser.get_total_duration_ms([])

    assert total == 0


def test_group_by_command_prefix():
    """Test grouping commands by prefix."""
    parser = CommandLogParser()

    entries = [
        CommandLogEntry(datetime.now(), "read_verilog file1.v", 100, 0),
        CommandLogEntry(datetime.now(), "read_verilog file2.v", 200, 0),
        CommandLogEntry(datetime.now(), "synth -top design", 1000, 0),
        CommandLogEntry(datetime.now(), "report_checks", 500, 0),
        CommandLogEntry(datetime.now(), "report_power", 300, 0),
    ]

    groups = parser.group_by_command_prefix(entries)

    assert "read_verilog" in groups
    assert len(groups["read_verilog"]) == 2
    assert "synth" in groups
    assert len(groups["synth"]) == 1
    assert "report_checks" in groups
    assert "report_power" in groups


# Test TCL generation


def test_generate_tcl_logging_prologue():
    """Test generating TCL logging prologue."""
    prologue = generate_tcl_logging_prologue("test_log.txt")

    assert "proc log_command" in prologue
    assert "test_log.txt" in prologue
    assert "clock milliseconds" in prologue
    assert "Command logging enabled" in prologue


def test_generate_tcl_logging_prologue_default_filename():
    """Test generating prologue with default filename."""
    prologue = generate_tcl_logging_prologue()

    assert "command_log.txt" in prologue


def test_generate_tcl_logging_epilogue():
    """Test generating TCL logging epilogue."""
    epilogue = generate_tcl_logging_epilogue()

    assert "Completed:" in epilogue
    assert "Command log written" in epilogue


def test_tcl_prologue_is_valid_tcl():
    """Test that generated prologue is syntactically valid TCL."""
    prologue = generate_tcl_logging_prologue()

    # Check for balanced braces
    assert prologue.count("{") == prologue.count("}")

    # Check for proc definition
    assert "proc log_command" in prologue


# Test formatting


def test_format_command_summary_empty():
    """Test formatting summary with no commands."""
    summary = format_command_summary([])

    assert "No commands logged" in summary


def test_format_command_summary_with_commands():
    """Test formatting summary with commands."""
    entries = [
        CommandLogEntry(datetime.now(), "cmd1", 1000, 0),
        CommandLogEntry(datetime.now(), "cmd2", 2000, 0),
        CommandLogEntry(datetime.now(), "cmd3", 3000, 0),
    ]

    summary = format_command_summary(entries)

    assert "Total commands: 3" in summary
    assert "Failed commands: 0" in summary
    assert "Total duration: 6000 ms" in summary


def test_format_command_summary_with_failures():
    """Test formatting summary with failed commands."""
    entries = [
        CommandLogEntry(datetime.now(), "cmd1", 1000, 0),
        CommandLogEntry(datetime.now(), "failed_cmd", 500, 1, error_message="Error occurred"),
        CommandLogEntry(datetime.now(), "cmd3", 2000, 0),
    ]

    summary = format_command_summary(entries)

    assert "Total commands: 3" in summary
    assert "Failed commands: 1" in summary
    assert "Failed Commands:" in summary
    assert "failed_cmd" in summary


def test_format_command_summary_shows_slowest():
    """Test that summary shows slowest commands."""
    entries = [
        CommandLogEntry(datetime.now(), "fast", 100, 0),
        CommandLogEntry(datetime.now(), "slowest", 5000, 0),
        CommandLogEntry(datetime.now(), "slow", 3000, 0),
    ]

    summary = format_command_summary(entries)

    assert "Slowest Commands:" in summary
    assert "5000 ms" in summary
    assert "slowest" in summary


# Test analyze_command_log


def test_analyze_command_log():
    """Test analyzing command log file."""
    log_content = """Wed Jan  8 12:34:56 EST 2026 | 1000 ms | status=0 | read_verilog design.v
Wed Jan  8 12:35:00 EST 2026 | 2000 ms | status=0 | synth -top design
Wed Jan  8 12:35:05 EST 2026 | 500 ms | status=1 | bad_command
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        log_path.write_text(log_content)

        analysis = analyze_command_log(log_path)

    assert analysis["total_commands"] == 3
    assert analysis["failed_commands"] == 1
    assert analysis["total_duration_ms"] == 3500
    assert analysis["average_duration_ms"] == 3500 / 3
    assert analysis["slowest_command"].command == "synth -top design"
    assert len(analysis["failed_entries"]) == 1


def test_analyze_command_log_empty():
    """Test analyzing empty command log."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "empty.log"
        log_path.write_text("")

        analysis = analyze_command_log(log_path)

    assert analysis["total_commands"] == 0
    assert analysis["failed_commands"] == 0
    assert analysis["total_duration_ms"] == 0
    assert analysis["slowest_command"] is None


def test_analyze_command_log_command_type_breakdown():
    """Test that analysis includes command type breakdown."""
    log_content = """Wed Jan  8 12:34:56 EST 2026 | 1000 ms | status=0 | read_verilog file1.v
Wed Jan  8 12:35:00 EST 2026 | 1000 ms | status=0 | read_verilog file2.v
Wed Jan  8 12:35:05 EST 2026 | 2000 ms | status=0 | synth -top design
Wed Jan  8 12:35:10 EST 2026 | 500 ms | status=0 | report_checks
"""

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "test.log"
        log_path.write_text(log_content)

        analysis = analyze_command_log(log_path)

    breakdown = analysis["command_type_breakdown"]
    assert breakdown["read_verilog"] == 2
    assert breakdown["synth"] == 1
    assert breakdown["report_checks"] == 1


# Integration tests


def test_end_to_end_command_logging_workflow():
    """Test complete workflow: generate TCL, create log, parse, analyze."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "commands.log"

        # Simulate a command log (as if generated by TCL)
        log_content = """# Noodle 2 OpenROAD Command Log
# Started: Wed Jan  8 12:00:00 EST 2026

Wed Jan  8 12:00:01 EST 2026 | 1500 ms | status=0 | read_lib nangate45.lib
Wed Jan  8 12:00:03 EST 2026 | 2000 ms | status=0 | read_verilog design.v
Wed Jan  8 12:00:05 EST 2026 | 5000 ms | status=0 | synth -top design
Wed Jan  8 12:00:10 EST 2026 | 1000 ms | status=0 | report_checks
Wed Jan  8 12:00:11 EST 2026 | 100 ms | status=1 | nonexistent_command

# Completed: Wed Jan  8 12:00:12 EST 2026
"""
        log_path.write_text(log_content)

        # Parse log
        parser = CommandLogParser()
        entries = parser.parse_log_file(log_path)

        # Verify parsing
        assert len(entries) == 5

        # Find failures
        failed = parser.find_failed_commands(entries)
        assert len(failed) == 1
        assert "nonexistent_command" in failed[0].command

        # Get slowest commands
        slowest = parser.get_slowest_commands(entries, n=3)
        assert slowest[0].command == "synth -top design"

        # Format summary
        summary = format_command_summary(entries)
        assert "Total commands: 5" in summary
        assert "Failed commands: 1" in summary

        # Analyze log
        analysis = analyze_command_log(log_path)
        assert analysis["total_commands"] == 5
        assert analysis["failed_commands"] == 1
        assert analysis["total_duration_ms"] == 9600


def test_tcl_prologue_and_epilogue_can_be_combined():
    """Test that prologue and epilogue can be combined in a script."""
    prologue = generate_tcl_logging_prologue("test.log")
    epilogue = generate_tcl_logging_epilogue()

    # Should be able to combine them
    combined = prologue + "\n# Main script here\n\n" + epilogue

    assert "proc log_command" in combined
    assert "Command logging enabled" in combined
    assert "Command log written" in combined
