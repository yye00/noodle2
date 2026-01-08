"""Tests for telemetry JSON formatting."""

import json
import time
from pathlib import Path

import pytest

from src.controller.telemetry_formatting import (
    FormattedTelemetryEmitter,
    enrich_telemetry_with_timestamps,
    format_duration_human_readable,
    format_timestamp_iso8601,
    validate_telemetry_format,
    write_formatted_telemetry,
)


class TestTimestampFormatting:
    """Test ISO 8601 timestamp formatting."""

    def test_format_timestamp_returns_iso8601(self) -> None:
        """Test that Unix timestamp is converted to ISO 8601 format."""
        # January 8, 2024, 12:00:00 UTC
        unix_time = 1704715200.0
        result = format_timestamp_iso8601(unix_time)

        assert result is not None
        assert "2024-01-08" in result
        assert "T" in result
        assert result.endswith("Z")

    def test_format_timestamp_handles_none(self) -> None:
        """Test that None input returns None."""
        result = format_timestamp_iso8601(None)
        assert result is None

    def test_format_timestamp_is_utc(self) -> None:
        """Test that timestamp is in UTC (ends with Z)."""
        unix_time = time.time()
        result = format_timestamp_iso8601(unix_time)

        assert result is not None
        assert result.endswith("Z")

    def test_format_timestamp_has_required_components(self) -> None:
        """Test that ISO 8601 timestamp has date, time, and timezone."""
        unix_time = 1704715200.0
        result = format_timestamp_iso8601(unix_time)

        assert result is not None
        # Should have date part (YYYY-MM-DD)
        assert result[0:10].count("-") == 2
        # Should have time separator
        assert "T" in result
        # Should have time part (HH:MM:SS)
        assert result[11:19].count(":") == 2


class TestDurationFormatting:
    """Test human-readable duration formatting."""

    def test_format_duration_seconds_only(self) -> None:
        """Test formatting for durations under 1 minute."""
        result = format_duration_human_readable(45.2)
        assert result == "45.2s"

    def test_format_duration_minutes_and_seconds(self) -> None:
        """Test formatting for durations under 1 hour."""
        result = format_duration_human_readable(125.0)
        assert "m" in result
        assert "s" in result
        assert "2m 5s" == result

    def test_format_duration_hours_minutes_seconds(self) -> None:
        """Test formatting for durations over 1 hour."""
        result = format_duration_human_readable(3725.0)
        assert "h" in result
        assert "m" in result
        assert "s" in result
        assert "1h 2m 5s" == result

    def test_format_duration_zero(self) -> None:
        """Test formatting for zero duration."""
        result = format_duration_human_readable(0.0)
        assert result == "0.0s"

    def test_format_duration_very_small(self) -> None:
        """Test formatting for very small durations."""
        result = format_duration_human_readable(0.123)
        assert "0.1s" == result


class TestTelemetryEnrichment:
    """Test telemetry enrichment with timestamps and durations."""

    def test_enrichment_adds_iso8601_start_time(self) -> None:
        """Test that start_time gets ISO 8601 variant."""
        data = {"start_time": 1704715200.0, "study_name": "test"}
        enriched = enrich_telemetry_with_timestamps(data)

        assert "start_time_iso8601" in enriched
        assert enriched["start_time_iso8601"] is not None
        assert "2024-01-08" in enriched["start_time_iso8601"]

    def test_enrichment_adds_iso8601_end_time(self) -> None:
        """Test that end_time gets ISO 8601 variant."""
        data = {"end_time": 1704715200.0, "study_name": "test"}
        enriched = enrich_telemetry_with_timestamps(data)

        assert "end_time_iso8601" in enriched
        assert enriched["end_time_iso8601"] is not None

    def test_enrichment_handles_none_timestamps(self) -> None:
        """Test that None timestamps are handled gracefully."""
        data = {"start_time": None, "end_time": None}
        enriched = enrich_telemetry_with_timestamps(data)

        # Should not add ISO 8601 fields for None values
        assert enriched["start_time"] is None
        assert enriched["end_time"] is None

    def test_enrichment_adds_human_readable_runtime(self) -> None:
        """Test that runtime gets human-readable variant."""
        data = {"total_runtime_seconds": 125.0}
        enriched = enrich_telemetry_with_timestamps(data)

        assert "total_runtime_human" in enriched
        assert "m" in enriched["total_runtime_human"]

    def test_enrichment_adds_human_readable_wall_clock(self) -> None:
        """Test that wall clock time gets human-readable variant."""
        data = {"wall_clock_seconds": 3725.0}
        enriched = enrich_telemetry_with_timestamps(data)

        assert "wall_clock_human" in enriched
        assert "h" in enriched["wall_clock_human"]

    def test_enrichment_preserves_original_data(self) -> None:
        """Test that enrichment doesn't remove original fields."""
        data = {
            "start_time": 1704715200.0,
            "end_time": 1704718800.0,
            "total_runtime_seconds": 125.0,
            "study_name": "test",
        }
        enriched = enrich_telemetry_with_timestamps(data)

        assert enriched["start_time"] == data["start_time"]
        assert enriched["end_time"] == data["end_time"]
        assert enriched["total_runtime_seconds"] == data["total_runtime_seconds"]
        assert enriched["study_name"] == data["study_name"]


class TestFormattedTelemetryWriting:
    """Test writing formatted telemetry to disk."""

    def test_write_creates_properly_indented_json(self, tmp_path: Path) -> None:
        """Test that written JSON is properly indented."""
        data = {"study_name": "test", "total_trials": 10}
        output_path = tmp_path / "telemetry.json"

        write_formatted_telemetry(data, output_path)

        with output_path.open("r") as f:
            content = f.read()

        # Should have indentation
        assert "  " in content
        # Should have newlines
        assert "\n" in content

    def test_write_includes_iso8601_timestamps(self, tmp_path: Path) -> None:
        """Test that written JSON includes ISO 8601 timestamps."""
        data = {"start_time": 1704715200.0, "end_time": 1704718800.0}
        output_path = tmp_path / "telemetry.json"

        write_formatted_telemetry(data, output_path)

        with output_path.open("r") as f:
            written_data = json.load(f)

        assert "start_time_iso8601" in written_data
        assert "end_time_iso8601" in written_data

    def test_write_creates_parent_directories(self, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        output_path = tmp_path / "nested" / "dir" / "telemetry.json"
        data = {"study_name": "test"}

        write_formatted_telemetry(data, output_path)

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_write_adds_newline_at_end(self, tmp_path: Path) -> None:
        """Test that file ends with newline."""
        data = {"study_name": "test"}
        output_path = tmp_path / "telemetry.json"

        write_formatted_telemetry(data, output_path)

        with output_path.open("r") as f:
            content = f.read()

        assert content.endswith("\n")

    def test_write_is_valid_json(self, tmp_path: Path) -> None:
        """Test that written file is valid JSON."""
        data = {
            "study_name": "test",
            "stages_completed": 2,
            "total_trials": 50,
            "metadata": {"key": "value"},
        }
        output_path = tmp_path / "telemetry.json"

        write_formatted_telemetry(data, output_path)

        # Should be able to load without error
        with output_path.open("r") as f:
            loaded = json.load(f)

        assert loaded["study_name"] == "test"
        assert loaded["stages_completed"] == 2


class TestTelemetryValidation:
    """Test telemetry format validation."""

    def test_validate_detects_valid_json(self, tmp_path: Path) -> None:
        """Test validation detects valid JSON."""
        data = {"study_name": "test"}
        output_path = tmp_path / "telemetry.json"
        write_formatted_telemetry(data, output_path)

        validation = validate_telemetry_format(output_path)

        assert validation["valid_json"] is True

    def test_validate_detects_indentation(self, tmp_path: Path) -> None:
        """Test validation detects proper indentation."""
        data = {"study_name": "test", "trials": 10}
        output_path = tmp_path / "telemetry.json"
        write_formatted_telemetry(data, output_path)

        validation = validate_telemetry_format(output_path)

        assert validation["properly_indented"] is True

    def test_validate_checks_iso8601_timestamps(self, tmp_path: Path) -> None:
        """Test validation checks for ISO 8601 timestamps."""
        data = {"start_time": 1704715200.0}
        output_path = tmp_path / "telemetry.json"
        write_formatted_telemetry(data, output_path)

        validation = validate_telemetry_format(output_path)

        assert validation["has_iso8601_timestamps"] is True

    def test_validate_detects_missing_iso8601(self, tmp_path: Path) -> None:
        """Test validation detects missing ISO 8601 timestamps."""
        data = {"start_time": 1704715200.0}
        output_path = tmp_path / "telemetry.json"

        # Write without enrichment
        with output_path.open("w") as f:
            json.dump(data, f)

        validation = validate_telemetry_format(output_path)

        assert validation["has_iso8601_timestamps"] is False

    def test_validate_handles_missing_file(self, tmp_path: Path) -> None:
        """Test validation handles missing files gracefully."""
        output_path = tmp_path / "nonexistent.json"

        validation = validate_telemetry_format(output_path)

        assert validation["valid_json"] is False


class TestFormattedTelemetryEmitter:
    """Test the formatted telemetry emitter."""

    def test_emitter_creates_formatted_file(self, tmp_path: Path) -> None:
        """Test emitter creates properly formatted telemetry file."""
        emitter = FormattedTelemetryEmitter(tmp_path)
        data = {"study_name": "test", "total_trials": 10}

        output_path = emitter.emit_telemetry(data, "study/test.json")

        assert output_path.exists()
        validation = validate_telemetry_format(output_path)
        assert validation["valid_json"] is True
        assert validation["properly_indented"] is True

    def test_emitter_respects_telemetry_root(self, tmp_path: Path) -> None:
        """Test emitter respects telemetry root directory."""
        root = tmp_path / "custom_telemetry"
        emitter = FormattedTelemetryEmitter(root)
        data = {"study_name": "test"}

        output_path = emitter.emit_telemetry(data, "test.json")

        assert str(root) in str(output_path)
        assert output_path.exists()

    def test_emitter_handles_nested_paths(self, tmp_path: Path) -> None:
        """Test emitter handles nested relative paths."""
        emitter = FormattedTelemetryEmitter(tmp_path)
        data = {"case_id": "test_0_1"}

        output_path = emitter.emit_telemetry(
            data, "study/cases/test_0_1_telemetry.json"
        )

        assert output_path.exists()
        assert "cases" in str(output_path)


class TestEndToEndFormatting:
    """Test end-to-end telemetry formatting."""

    def test_complete_study_telemetry_formatting(self, tmp_path: Path) -> None:
        """Test complete study telemetry is properly formatted."""
        study_data = {
            "study_name": "nangate45_baseline",
            "safety_domain": "sandbox",
            "total_stages": 2,
            "stages_completed": 2,
            "total_trials": 50,
            "successful_trials": 45,
            "failed_trials": 5,
            "total_runtime_seconds": 3725.5,
            "start_time": 1704715200.0,
            "end_time": 1704718925.5,
            "wall_clock_seconds": 3725.5,
        }

        output_path = tmp_path / "study_telemetry.json"
        write_formatted_telemetry(study_data, output_path)

        # Load and verify
        with output_path.open("r") as f:
            loaded = json.load(f)

        # Check ISO 8601 timestamps
        assert "start_time_iso8601" in loaded
        assert "2024-01-08" in loaded["start_time_iso8601"]
        assert loaded["start_time_iso8601"].endswith("Z")

        assert "end_time_iso8601" in loaded
        assert loaded["end_time_iso8601"].endswith("Z")

        # Check human-readable durations
        assert "total_runtime_human" in loaded
        assert "h" in loaded["total_runtime_human"]

        assert "wall_clock_human" in loaded

        # Verify formatting
        validation = validate_telemetry_format(output_path)
        assert validation["valid_json"] is True
        assert validation["properly_indented"] is True
        assert validation["has_iso8601_timestamps"] is True

    def test_stage_telemetry_formatting(self, tmp_path: Path) -> None:
        """Test stage telemetry is properly formatted."""
        stage_data = {
            "stage_index": 0,
            "stage_name": "sta_baseline",
            "trial_budget": 25,
            "survivor_count": 10,
            "trials_executed": 25,
            "successful_trials": 23,
            "failed_trials": 2,
            "total_runtime_seconds": 1825.3,
        }

        output_path = tmp_path / "stage_0_telemetry.json"
        write_formatted_telemetry(stage_data, output_path)

        # Verify formatting
        validation = validate_telemetry_format(output_path)
        assert validation["valid_json"] is True
        assert validation["properly_indented"] is True

        # Check human-readable duration
        with output_path.open("r") as f:
            loaded = json.load(f)
        assert "total_runtime_human" in loaded

    def test_case_telemetry_formatting(self, tmp_path: Path) -> None:
        """Test case telemetry is properly formatted."""
        case_data = {
            "case_id": "nangate45_0_1",
            "base_case": "nangate45",
            "stage_index": 0,
            "derived_index": 1,
            "total_trials": 5,
            "successful_trials": 4,
            "failed_trials": 1,
            "total_runtime_seconds": 145.7,
        }

        output_path = tmp_path / "case_telemetry.json"
        write_formatted_telemetry(case_data, output_path)

        # Verify formatting
        validation = validate_telemetry_format(output_path)
        assert validation["valid_json"] is True
        assert validation["properly_indented"] is True

        # Check human-readable duration
        with output_path.open("r") as f:
            loaded = json.load(f)
        assert "total_runtime_human" in loaded
