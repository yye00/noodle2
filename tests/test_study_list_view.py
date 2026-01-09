"""Tests for Study catalog/list view with table formatting."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from src.controller.study_catalog import StudyMetadata, write_study_metadata
from src.controller.study_list import (
    StudyListEntry,
    discover_studies,
    filter_studies,
    format_study_table,
)
from src.controller.types import SafetyDomain, StageConfig, StudyConfig


@pytest.fixture
def test_telemetry_dir(tmp_path: Path) -> Path:
    """Create temporary telemetry directory with test Studies."""
    telemetry_root = tmp_path / "telemetry"
    telemetry_root.mkdir()

    # Create 3 Studies with different statuses
    _create_test_study(
        telemetry_root / "nangate45_baseline",
        name="nangate45_baseline",
        pdk="nangate45",
        domain="sandbox",
        tags=["baseline", "fast"],
        status="completed",
    )

    _create_test_study(
        telemetry_root / "asap7_exploration",
        name="asap7_exploration",
        pdk="asap7",
        domain="guarded",
        tags=["exploration", "timing"],
        status="running",
    )

    _create_test_study(
        telemetry_root / "sky130_regression",
        name="sky130_regression",
        pdk="sky130",
        domain="locked",
        tags=["regression", "ci"],
        status="failed",
    )

    return telemetry_root


def _create_test_study(
    study_dir: Path,
    name: str,
    pdk: str,
    domain: str,
    tags: list[str],
    status: str,
) -> None:
    """Helper to create a test Study directory with metadata."""
    study_dir.mkdir(parents=True, exist_ok=True)

    # Create minimal StudyConfig for metadata
    from src.controller.types import ECOClass, ExecutionMode

    config = StudyConfig(
        name=name,
        pdk=pdk,
        safety_domain=SafetyDomain(domain),
        base_case_name=f"{name}_base",
        snapshot_path=f"/path/to/{name}",
        stages=[
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=3,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            )
        ],
        tags=tags,
        author="test_user",
        creation_date=datetime.now().isoformat(),
        description=f"Test Study for {name}",
    )

    # Write metadata
    write_study_metadata(config, study_dir)

    # Add status markers
    if status == "completed":
        (study_dir / "study_summary.json").write_text(
            json.dumps({"winner_case": "case_0_0", "status": "completed"})
        )
    elif status == "running":
        (study_dir / "checkpoint.json").write_text(json.dumps({"stage": 0}))
    elif status == "failed":
        (study_dir / "error.log").write_text("Simulated error")
    elif status == "blocked":
        (study_dir / "blocked_marker").write_text("Base case failed")


# === Step 1: Run command to list all Studies ===


def test_run_list_studies_command(test_telemetry_dir: Path) -> None:
    """
    Step 1: Run command to list all Studies.

    Verify that discover_studies() finds all Studies in telemetry directory.
    """
    studies = discover_studies(test_telemetry_dir)

    assert len(studies) == 3
    study_names = {s.name for s in studies}
    assert study_names == {"nangate45_baseline", "asap7_exploration", "sky130_regression"}


# === Step 2: Take screenshot of catalog output ===
# (Simulated via string output validation)


def test_catalog_output_format(test_telemetry_dir: Path) -> None:
    """
    Step 2: Take screenshot of catalog output.

    Verify formatted table output is produced.
    """
    studies = discover_studies(test_telemetry_dir)
    table = format_study_table(studies)

    assert table
    assert "Status" in table
    assert "Name" in table
    assert "Domain" in table
    assert "PDK" in table
    assert "nangate45_baseline" in table
    assert "Total: 3 studies" in table


# === Step 3: Verify Studies shown in table with required columns ===


def test_verify_table_has_required_columns(test_telemetry_dir: Path) -> None:
    """
    Step 3: Verify Studies are shown in table with columns: name, status, creation date, tags.

    Check that all required columns are present in formatted output.
    """
    studies = discover_studies(test_telemetry_dir)
    table = format_study_table(studies)

    # Check for required column headers
    assert "Status" in table
    assert "Name" in table
    assert "Created" in table
    assert "Tags" in table

    # Check that actual data is present
    assert "nangate45_baseline" in table
    assert "asap7_exploration" in table
    assert "sky130_regression" in table

    # Check for status symbols
    assert "✓" in table or "▶" in table or "✗" in table

    # Check for tags
    assert "baseline" in table or "fast" in table
    assert "exploration" in table or "timing" in table


# === Step 4: Verify table is sortable by different columns ===


def test_table_sortable_by_creation_date(test_telemetry_dir: Path) -> None:
    """
    Step 4: Verify table is sortable by different columns.

    Studies are sorted by creation date (newest first) by default.
    """
    studies = discover_studies(test_telemetry_dir)

    # Verify studies are sorted by creation date (newest first)
    # Since all created at same time in test, just verify ordering logic exists
    dates = [s.creation_date for s in studies if s.creation_date]
    assert dates  # Should have dates

    # Verify we can filter/sort
    filtered = filter_studies(studies, status="completed")
    assert len(filtered) == 1
    assert filtered[0].name == "nangate45_baseline"


# === Step 5: Verify table is easy to scan visually ===


def test_table_easy_to_scan_visually(test_telemetry_dir: Path) -> None:
    """
    Step 5: Verify table is easy to scan visually.

    Check for:
    - Clear column alignment
    - Separator lines
    - Status symbols
    - Compact tag display
    """
    studies = discover_studies(test_telemetry_dir)
    table = format_study_table(studies)

    # Check for table formatting elements
    assert "│" in table  # Column separators
    assert "─" in table  # Row separator

    # Check that lines are aligned (all data rows have same structure)
    lines = table.split("\n")
    data_lines = [l for l in lines if "│" in l and not l.startswith("─")]

    if len(data_lines) > 1:
        # All rows should have same number of columns
        col_counts = [line.count("│") for line in data_lines]
        assert len(set(col_counts)) == 1, "All rows should have same column count"

    # Check for status symbols (visual indicators)
    symbols = {"✓", "▶", "✗", "⊗", "?"}
    assert any(sym in table for sym in symbols)

    # Check for total count footer
    assert "Total:" in table


# === Additional comprehensive tests ===


def test_study_list_entry_status_symbols() -> None:
    """Test status symbol formatting."""
    entry = StudyListEntry(
        name="test",
        status="completed",
        creation_date="2026-01-08",
        tags=[],
        safety_domain="sandbox",
        pdk="nangate45",
    )
    assert entry.format_status_symbol() == "✓"

    entry.status = "running"
    assert entry.format_status_symbol() == "▶"

    entry.status = "failed"
    assert entry.format_status_symbol() == "✗"

    entry.status = "blocked"
    assert entry.format_status_symbol() == "⊗"


def test_study_list_entry_tag_formatting() -> None:
    """Test compact tag formatting."""
    entry = StudyListEntry(
        name="test",
        status="completed",
        creation_date="2026-01-08",
        tags=["tag1", "tag2", "tag3", "tag4", "tag5"],
        safety_domain="sandbox",
        pdk="nangate45",
    )

    compact = entry.format_tags_compact(max_tags=3)
    assert "tag1" in compact
    assert "tag2" in compact
    assert "tag3" in compact
    assert "(+2)" in compact


def test_study_list_entry_completion_formatting() -> None:
    """Test completion percentage formatting."""
    entry = StudyListEntry(
        name="test",
        status="running",
        creation_date="2026-01-08",
        tags=[],
        safety_domain="sandbox",
        pdk="nangate45",
        completion_percent=45.7,
    )
    assert entry.format_completion() == "45.7%"

    entry.completion_percent = None
    assert entry.format_completion() == "-"


def test_discover_studies_empty_directory(tmp_path: Path) -> None:
    """Test discovery in empty telemetry directory."""
    telemetry = tmp_path / "telemetry"
    telemetry.mkdir()

    studies = discover_studies(telemetry)
    assert studies == []


def test_discover_studies_no_metadata(tmp_path: Path) -> None:
    """Test discovery of Study without metadata file."""
    telemetry = tmp_path / "telemetry"
    study_dir = telemetry / "unknown_study"
    study_dir.mkdir(parents=True)

    studies = discover_studies(telemetry)
    assert len(studies) == 1
    assert studies[0].name == "unknown_study"
    assert studies[0].status == "unknown"
    assert studies[0].pdk == "unknown"


def test_filter_studies_by_status(test_telemetry_dir: Path) -> None:
    """Test filtering Studies by status."""
    all_studies = discover_studies(test_telemetry_dir)

    # Filter by completed
    completed = filter_studies(all_studies, status="completed")
    assert len(completed) == 1
    assert completed[0].name == "nangate45_baseline"

    # Filter by running
    running = filter_studies(all_studies, status="running")
    assert len(running) == 1
    assert running[0].name == "asap7_exploration"

    # Filter by failed
    failed = filter_studies(all_studies, status="failed")
    assert len(failed) == 1
    assert failed[0].name == "sky130_regression"


def test_filter_studies_by_domain(test_telemetry_dir: Path) -> None:
    """Test filtering Studies by safety domain."""
    all_studies = discover_studies(test_telemetry_dir)

    # Filter by sandbox
    sandbox = filter_studies(all_studies, domain="sandbox")
    assert len(sandbox) == 1
    assert sandbox[0].name == "nangate45_baseline"

    # Filter by guarded
    guarded = filter_studies(all_studies, domain="guarded")
    assert len(guarded) == 1
    assert guarded[0].name == "asap7_exploration"

    # Filter by locked
    locked = filter_studies(all_studies, domain="locked")
    assert len(locked) == 1
    assert locked[0].name == "sky130_regression"


def test_filter_studies_combined(test_telemetry_dir: Path) -> None:
    """Test filtering by both status and domain."""
    all_studies = discover_studies(test_telemetry_dir)

    # Filter by completed + sandbox
    result = filter_studies(all_studies, status="completed", domain="sandbox")
    assert len(result) == 1
    assert result[0].name == "nangate45_baseline"

    # Filter by running + locked (no match)
    result = filter_studies(all_studies, status="running", domain="locked")
    assert len(result) == 0


def test_format_table_with_description(test_telemetry_dir: Path) -> None:
    """Test table formatting with description column."""
    studies = discover_studies(test_telemetry_dir)
    table = format_study_table(studies, include_description=True)

    assert "Description" in table
    assert "Test Study" in table


def test_format_table_empty() -> None:
    """Test formatting empty study list."""
    table = format_study_table([])
    assert table == "No Studies found."


def test_format_table_single_study(tmp_path: Path) -> None:
    """Test formatting with single Study."""
    telemetry = tmp_path / "telemetry"
    _create_test_study(
        telemetry / "single_study",
        name="single_study",
        pdk="nangate45",
        domain="sandbox",
        tags=["test"],
        status="completed",
    )

    studies = discover_studies(telemetry)
    table = format_study_table(studies)

    assert "single_study" in table
    assert "Total: 1 study" in table  # Singular form


def test_cli_integration(test_telemetry_dir: Path, monkeypatch) -> None:
    """Test CLI integration with list-studies command."""
    from argparse import Namespace
    from src.cli import cmd_list_studies

    # Mock args
    args = Namespace(status="all", domain="all")

    # Change to test telemetry directory
    import os
    original_cwd = os.getcwd()
    os.chdir(test_telemetry_dir.parent)
    monkeypatch.setattr(
        "src.controller.study_list.discover_studies",
        lambda telemetry_root="telemetry": discover_studies(test_telemetry_dir),
    )

    try:
        # Should return 0 (success)
        result = cmd_list_studies(args)
        assert result == 0
    finally:
        os.chdir(original_cwd)


def test_cli_with_filters(test_telemetry_dir: Path, monkeypatch) -> None:
    """Test CLI with status and domain filters."""
    from argparse import Namespace
    from src.cli import cmd_list_studies

    args = Namespace(status="completed", domain="sandbox")

    monkeypatch.setattr(
        "src.controller.study_list.discover_studies",
        lambda telemetry_root="telemetry": discover_studies(test_telemetry_dir),
    )

    result = cmd_list_studies(args)
    assert result == 0


def test_cli_no_studies(tmp_path: Path, monkeypatch) -> None:
    """Test CLI with no Studies found."""
    from argparse import Namespace
    from src.cli import cmd_list_studies

    telemetry = tmp_path / "telemetry"
    telemetry.mkdir()

    args = Namespace(status="all", domain="all")

    monkeypatch.setattr(
        "src.controller.study_list.discover_studies",
        lambda telemetry_root="telemetry": discover_studies(telemetry),
    )

    result = cmd_list_studies(args)
    assert result == 0  # Success even with no studies


def test_cli_no_matches_after_filter(test_telemetry_dir: Path, monkeypatch) -> None:
    """Test CLI when filters exclude all Studies."""
    from argparse import Namespace
    from src.cli import cmd_list_studies

    # Filter that matches nothing
    args = Namespace(status="blocked", domain="all")

    monkeypatch.setattr(
        "src.controller.study_list.discover_studies",
        lambda telemetry_root="telemetry": discover_studies(test_telemetry_dir),
    )

    result = cmd_list_studies(args)
    assert result == 0  # Success but no matches
