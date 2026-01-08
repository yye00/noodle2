"""Tests for trial execution provenance tracking."""

import json
from pathlib import Path

import pytest

from src.trial_runner.provenance import (
    ToolProvenance,
    create_provenance,
    format_provenance_summary,
)


class TestToolProvenance:
    """Tests for ToolProvenance dataclass."""

    def test_tool_provenance_creation(self):
        """Test creating ToolProvenance with all fields."""
        prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
            tool_name="openroad",
            tool_version="2.0.0",
            command="openroad test.tcl",
            working_directory="/work",
            start_time="2026-01-08T00:00:00Z",
            end_time="2026-01-08T00:05:00Z",
        )

        assert prov.container_image == "efabless/openlane"
        assert prov.container_tag == "ci2504-dev-amd64"
        assert prov.container_id == "abc123"
        assert prov.tool_name == "openroad"
        assert prov.tool_version == "2.0.0"
        assert prov.command == "openroad test.tcl"
        assert prov.working_directory == "/work"
        assert prov.start_time == "2026-01-08T00:00:00Z"
        assert prov.end_time == "2026-01-08T00:05:00Z"

    def test_tool_provenance_defaults(self):
        """Test ToolProvenance default values."""
        prov = ToolProvenance(
            container_image="openroad/flow",
            container_tag="latest",
        )

        assert prov.container_id == ""
        assert prov.tool_name == "openroad"
        assert prov.tool_version is None
        assert prov.command == ""
        assert prov.working_directory == ""
        assert prov.start_time == ""
        assert prov.end_time == ""
        assert prov.metadata == {}

    def test_tool_provenance_to_dict(self):
        """Test converting ToolProvenance to dictionary."""
        prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
            tool_version="2.0.0",
            command="openroad test.tcl",
        )

        data = prov.to_dict()

        assert data["container_image"] == "efabless/openlane"
        assert data["container_tag"] == "ci2504-dev-amd64"
        assert data["container_id"] == "abc123"
        assert data["tool_name"] == "openroad"
        assert data["tool_version"] == "2.0.0"
        assert data["command"] == "openroad test.tcl"

    def test_tool_provenance_serializable(self):
        """Test that ToolProvenance can be JSON serialized."""
        prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
            tool_version="2.0.0",
        )

        data = prov.to_dict()
        json_str = json.dumps(data)

        # Should not raise
        assert json_str is not None
        assert "efabless/openlane" in json_str


class TestCreateProvenance:
    """Tests for create_provenance function."""

    def test_create_provenance_basic(self):
        """Test creating provenance with basic parameters."""
        prov = create_provenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
            query_version=False,
        )

        assert prov.container_image == "efabless/openlane"
        assert prov.container_tag == "ci2504-dev-amd64"
        assert prov.container_id == "abc123"
        assert prov.tool_version is None  # Version query disabled

    def test_create_provenance_with_command(self):
        """Test creating provenance with command-line invocation."""
        prov = create_provenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            command="openroad -no_init test.tcl",
            working_dir="/work/trial_0",
            query_version=False,
        )

        assert prov.command == "openroad -no_init test.tcl"
        assert prov.working_directory == "/work/trial_0"

    def test_create_provenance_with_timestamps(self):
        """Test creating provenance with execution timestamps."""
        prov = create_provenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            start_time="2026-01-08T00:00:00Z",
            end_time="2026-01-08T00:05:00Z",
            query_version=False,
        )

        assert prov.start_time == "2026-01-08T00:00:00Z"
        assert prov.end_time == "2026-01-08T00:05:00Z"

    def test_create_provenance_with_path_object(self):
        """Test creating provenance with Path object for working_dir."""
        working_path = Path("/work/artifacts/trial_0")

        prov = create_provenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            working_dir=working_path,
            query_version=False,
        )

        assert prov.working_directory == str(working_path)

    def test_create_provenance_skip_version_query(self):
        """Test that version query can be skipped for performance."""
        prov = create_provenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            query_version=False,
        )

        # Version should be None when query is skipped
        assert prov.tool_version is None


class TestFormatProvenanceSummary:
    """Tests for format_provenance_summary function."""

    def test_format_basic_provenance(self):
        """Test formatting basic provenance summary."""
        prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
        )

        summary = format_provenance_summary(prov)

        assert "=== Trial Execution Provenance ===" in summary
        assert "Container: efabless/openlane:ci2504-dev-amd64" in summary
        assert "Container ID: abc123" in summary
        assert "Tool: openroad" in summary
        assert "Version: (unavailable)" in summary

    def test_format_provenance_with_version(self):
        """Test formatting provenance with tool version."""
        prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
            tool_version="2.0.0",
        )

        summary = format_provenance_summary(prov)

        assert "Version: 2.0.0" in summary
        assert "Version: (unavailable)" not in summary

    def test_format_provenance_with_command(self):
        """Test formatting provenance with command."""
        prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            command="openroad test.tcl",
            working_directory="/work",
        )

        summary = format_provenance_summary(prov)

        assert "Command: openroad test.tcl" in summary
        assert "Working Dir: /work" in summary

    def test_format_provenance_with_timestamps(self):
        """Test formatting provenance with timestamps."""
        prov = ToolProvenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            start_time="2026-01-08T00:00:00Z",
            end_time="2026-01-08T00:05:00Z",
        )

        summary = format_provenance_summary(prov)

        assert "Execution: 2026-01-08T00:00:00Z to 2026-01-08T00:05:00Z" in summary


class TestProvenanceReproducibility:
    """Tests for reproducibility contract of provenance."""

    def test_provenance_contains_reproducibility_info(self):
        """Test that provenance contains sufficient info for reproducibility."""
        prov = create_provenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
            command="openroad test.tcl",
            working_dir="/work",
            start_time="2026-01-08T00:00:00Z",
            end_time="2026-01-08T00:05:00Z",
            query_version=False,
        )

        # Container image and tag are required for reproducibility
        assert prov.container_image
        assert prov.container_tag

        # Command is helpful for reproducibility
        assert prov.command

        # Timestamps help track execution order
        assert prov.start_time
        assert prov.end_time

    def test_provenance_is_deterministic(self):
        """Test that provenance generation is deterministic given same inputs."""
        args = {
            "container_image": "efabless/openlane",
            "container_tag": "ci2504-dev-amd64",
            "container_id": "abc123",
            "command": "openroad test.tcl",
            "query_version": False,
        }

        prov1 = create_provenance(**args)
        prov2 = create_provenance(**args)

        # All fields should be identical
        assert prov1.to_dict() == prov2.to_dict()


class TestProvenanceIntegration:
    """Integration tests for provenance tracking."""

    def test_provenance_in_trial_result_serialization(self):
        """Test that provenance is included in trial result JSON."""
        from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts

        config = TrialConfig(
            study_name="test_study",
            case_name="base",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        artifacts = TrialArtifacts(trial_dir=Path("/tmp/trial_0"))

        prov = create_provenance(
            container_image="efabless/openlane",
            container_tag="ci2504-dev-amd64",
            container_id="abc123",
            query_version=False,
        )

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=5.0,
            artifacts=artifacts,
            provenance=prov,
        )

        data = result.to_dict()

        # Provenance should be in serialized output
        assert "provenance" in data
        assert data["provenance"]["container_image"] == "efabless/openlane"
        assert data["provenance"]["container_tag"] == "ci2504-dev-amd64"
        assert data["provenance"]["container_id"] == "abc123"

    def test_provenance_optional_in_trial_result(self):
        """Test that provenance is optional in TrialResult."""
        from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts

        config = TrialConfig(
            study_name="test_study",
            case_name="base",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        artifacts = TrialArtifacts(trial_dir=Path("/tmp/trial_0"))

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=5.0,
            artifacts=artifacts,
            provenance=None,  # No provenance
        )

        data = result.to_dict()

        # Should not crash, and provenance field should be absent
        assert "provenance" not in data or data.get("provenance") is None
