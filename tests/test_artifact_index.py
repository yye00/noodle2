"""Tests for artifact indexing and cataloging."""

import json
import tempfile
from pathlib import Path

import pytest

from src.trial_runner.artifact_index import (
    ArtifactEntry,
    StageArtifactSummary,
    TrialArtifactIndex,
    generate_trial_artifact_index,
    infer_content_type,
)


class TestArtifactEntry:
    """Test ArtifactEntry dataclass."""

    def test_create_artifact_entry(self):
        """Test creating an artifact entry."""
        entry = ArtifactEntry(
            path=Path("timing_report.txt"),
            label="Timing Analysis Report",
            content_type="text/plain",
            size_bytes=1024,
        )

        assert entry.path == Path("timing_report.txt")
        assert entry.label == "Timing Analysis Report"
        assert entry.content_type == "text/plain"
        assert entry.size_bytes == 1024

    def test_artifact_entry_to_dict(self):
        """Test converting artifact entry to dictionary."""
        entry = ArtifactEntry(
            path=Path("congestion_report.txt"),
            label="Congestion Report",
            content_type="text/plain",
            size_bytes=2048,
        )

        entry_dict = entry.to_dict()

        assert entry_dict["path"] == "congestion_report.txt"
        assert entry_dict["label"] == "Congestion Report"
        assert entry_dict["content_type"] == "text/plain"
        assert entry_dict["size_bytes"] == 2048


class TestTrialArtifactIndex:
    """Test TrialArtifactIndex for trial-level artifact indexing."""

    def test_create_trial_artifact_index(self, tmp_path):
        """Test creating a trial artifact index."""
        index = TrialArtifactIndex(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            trial_root=tmp_path,
        )

        assert index.study_name == "test_study"
        assert index.case_name == "test_case"
        assert index.stage_index == 0
        assert index.trial_index == 0
        assert index.trial_root == tmp_path
        assert len(index.entries) == 0

    def test_add_artifact_to_index(self, tmp_path):
        """Test adding artifacts to index."""
        index = TrialArtifactIndex(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            trial_root=tmp_path,
        )

        # Create a test file
        test_file = tmp_path / "timing_report.txt"
        test_file.write_text("WNS: -100 ps")

        # Add artifact
        index.add_artifact(
            path=test_file,
            label="Timing Analysis Report",
            content_type="text/plain",
        )

        assert len(index.entries) == 1
        assert index.entries[0].path == Path("timing_report.txt")
        assert index.entries[0].label == "Timing Analysis Report"
        assert index.entries[0].size_bytes > 0

    def test_trial_artifact_index_to_dict(self, tmp_path):
        """Test converting trial artifact index to dictionary."""
        index = TrialArtifactIndex(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            trial_root=tmp_path,
        )

        test_file = tmp_path / "metrics.json"
        test_file.write_text("{}")

        index.add_artifact(
            path=test_file,
            label="Trial Metrics",
            content_type="application/json",
        )

        index_dict = index.to_dict()

        assert index_dict["study_name"] == "test_study"
        assert index_dict["case_name"] == "test_case"
        assert index_dict["stage_index"] == 0
        assert index_dict["trial_index"] == 0
        assert len(index_dict["entries"]) == 1
        assert index_dict["entries"][0]["label"] == "Trial Metrics"

    def test_write_artifact_index_to_file(self, tmp_path):
        """
        Test writing artifact index to JSON file.

        Step 1: Create trial artifact index
        Step 2: Add artifacts to index
        Step 3: Write index to file
        Step 4: Verify file exists
        Step 5: Verify JSON content is valid
        """
        index = TrialArtifactIndex(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            trial_root=tmp_path,
        )

        test_file = tmp_path / "timing_report.txt"
        test_file.write_text("WNS: -100 ps")

        index.add_artifact(
            path=test_file,
            label="Timing Report",
            content_type="text/plain",
        )

        # Write to default location
        output_path = index.write_to_file()

        assert output_path.exists()
        assert output_path.name == "artifact_index.json"

        # Verify JSON is valid
        with output_path.open() as f:
            data = json.load(f)

        assert data["study_name"] == "test_study"
        assert len(data["entries"]) == 1

    def test_artifact_index_with_metadata(self, tmp_path):
        """Test artifact index with custom metadata."""
        index = TrialArtifactIndex(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            trial_root=tmp_path,
        )

        index.metadata["eco_names"] = ["buffer_insertion", "placement_density"]
        index.metadata["timestamp"] = "2026-01-07T12:00:00Z"

        index_dict = index.to_dict()

        assert index_dict["metadata"]["eco_names"] == [
            "buffer_insertion",
            "placement_density",
        ]
        assert "timestamp" in index_dict["metadata"]


class TestStageArtifactSummary:
    """Test StageArtifactSummary for stage-level aggregation."""

    def test_create_stage_artifact_summary(self, tmp_path):
        """Test creating a stage artifact summary."""
        summary = StageArtifactSummary(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            stage_root=tmp_path,
        )

        assert summary.study_name == "test_study"
        assert summary.case_name == "test_case"
        assert summary.stage_index == 0
        assert summary.trial_count == 0
        assert summary.success_count == 0
        assert summary.failure_count == 0

    def test_add_trial_to_stage_summary(self, tmp_path):
        """
        Test adding trials to stage summary.

        Step 1: Create stage summary
        Step 2: Add successful trial
        Step 3: Add failed trial
        Step 4: Verify counts are correct
        Step 5: Verify trial indexes are tracked
        """
        summary = StageArtifactSummary(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            stage_root=tmp_path,
        )

        # Add successful trial
        trial_0_index = tmp_path / "trial_0" / "artifact_index.json"
        summary.add_trial(
            trial_index=0,
            success=True,
            artifact_index_path=trial_0_index,
            metrics={"wns_ps": -100},
        )

        # Add failed trial
        trial_1_index = tmp_path / "trial_1" / "artifact_index.json"
        summary.add_trial(
            trial_index=1,
            success=False,
            artifact_index_path=trial_1_index,
        )

        assert summary.trial_count == 2
        assert summary.success_count == 1
        assert summary.failure_count == 1
        assert len(summary.trial_indexes) == 2

    def test_stage_summary_metrics_aggregation(self, tmp_path):
        """Test metrics aggregation in stage summary."""
        summary = StageArtifactSummary(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            stage_root=tmp_path,
        )

        # Add multiple trials with metrics
        for i in range(3):
            trial_index = tmp_path / f"trial_{i}" / "artifact_index.json"
            summary.add_trial(
                trial_index=i,
                success=True,
                artifact_index_path=trial_index,
                metrics={"wns_ps": -100 - i * 10},
            )

        # Verify metrics are aggregated
        assert "wns_ps" in summary.metrics_summary
        assert len(summary.metrics_summary["wns_ps"]) == 3
        assert summary.metrics_summary["wns_ps"] == [-100, -110, -120]

    def test_write_stage_summary_to_file(self, tmp_path):
        """
        Test writing stage summary to JSON file.

        Step 1: Create stage summary
        Step 2: Add trial data
        Step 3: Write summary to file
        Step 4: Verify file exists with correct name
        Step 5: Verify JSON content is valid
        """
        summary = StageArtifactSummary(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            stage_root=tmp_path,
        )

        trial_index = tmp_path / "trial_0" / "artifact_index.json"
        summary.add_trial(
            trial_index=0,
            success=True,
            artifact_index_path=trial_index,
            metrics={"wns_ps": -100},
        )

        # Write to default location
        output_path = summary.write_to_file()

        assert output_path.exists()
        assert output_path.name == "stage_artifact_summary.json"

        # Verify JSON is valid
        with output_path.open() as f:
            data = json.load(f)

        assert data["study_name"] == "test_study"
        assert data["trial_count"] == 1
        assert data["success_count"] == 1


class TestContentTypeInference:
    """Test content type inference from file extensions."""

    def test_infer_content_type_text(self):
        """Test inferring content type for text files."""
        assert infer_content_type(Path("report.txt")) == "text/plain"
        assert infer_content_type(Path("output.log")) == "text/plain"
        assert infer_content_type(Path("timing.rpt")) == "text/plain"

    def test_infer_content_type_json(self):
        """Test inferring content type for JSON files."""
        assert infer_content_type(Path("metrics.json")) == "application/json"

    def test_infer_content_type_csv(self):
        """Test inferring content type for CSV files."""
        assert infer_content_type(Path("heatmap.csv")) == "text/csv"

    def test_infer_content_type_verilog(self):
        """Test inferring content type for Verilog files."""
        assert infer_content_type(Path("netlist.v")) == "text/x-verilog"
        assert infer_content_type(Path("netlist_gl.vg")) == "text/x-verilog"

    def test_infer_content_type_images(self):
        """Test inferring content type for image files."""
        assert infer_content_type(Path("heatmap.png")) == "image/png"
        assert infer_content_type(Path("photo.jpg")) == "image/jpeg"
        assert infer_content_type(Path("diagram.svg")) == "image/svg+xml"

    def test_infer_content_type_eda_formats(self):
        """Test inferring content type for EDA file formats."""
        assert infer_content_type(Path("design.def")) == "text/x-def"
        assert infer_content_type(Path("technology.lef")) == "text/x-lef"
        assert infer_content_type(Path("constraints.sdc")) == "text/x-sdc"
        assert infer_content_type(Path("parasitics.spef")) == "text/x-spef"

    def test_infer_content_type_unknown(self):
        """Test inferring content type for unknown extensions."""
        assert (
            infer_content_type(Path("unknown.xyz")) == "application/octet-stream"
        )


class TestGenerateTrialArtifactIndex:
    """Test automatic trial artifact index generation."""

    def test_generate_artifact_index_for_trial(self, tmp_path):
        """
        Test generating artifact index by scanning trial directory.

        Step 1: Create trial directory with artifacts
        Step 2: Generate artifact index
        Step 3: Verify index contains all expected files
        Step 4: Verify high-level labels are correct
        Step 5: Verify content-type hints are present
        """
        # Create trial directory structure
        trial_dir = tmp_path / "test_study" / "test_case" / "stage_0" / "trial_0"
        trial_dir.mkdir(parents=True)

        # Create artifacts
        (trial_dir / "timing_report.txt").write_text("WNS: -100 ps")
        (trial_dir / "congestion_report.txt").write_text("Hot bins: 5")
        (trial_dir / "metrics.json").write_text('{"wns_ps": -100}')
        (trial_dir / "netlist.v").write_text("module test();")

        # Create logs directory
        logs_dir = trial_dir / "logs"
        logs_dir.mkdir()
        (logs_dir / "stdout.txt").write_text("OpenROAD output")
        (logs_dir / "stderr.txt").write_text("")

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        assert index.study_name == "test_study"
        assert index.case_name == "test_case"
        assert len(index.entries) >= 6  # At least 6 artifacts

        # Verify specific artifacts are indexed
        paths = [entry.path for entry in index.entries]
        assert Path("timing_report.txt") in paths
        assert Path("congestion_report.txt") in paths
        assert Path("metrics.json") in paths
        assert Path("netlist.v") in paths

        # Verify content types
        json_entry = next(e for e in index.entries if e.path.suffix == ".json")
        assert json_entry.content_type == "application/json"

    def test_generate_index_with_eco_metadata(self, tmp_path):
        """Test generating index with ECO metadata."""
        trial_dir = tmp_path / "trial_0"
        trial_dir.mkdir(parents=True)

        (trial_dir / "timing_report.txt").write_text("WNS: -100 ps")

        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            eco_names=["buffer_insertion", "placement_density"],
        )

        assert "eco_names" in index.metadata
        assert index.metadata["eco_names"] == [
            "buffer_insertion",
            "placement_density",
        ]

    def test_generate_index_with_heatmaps(self, tmp_path):
        """Test generating index with heatmap CSV files."""
        trial_dir = tmp_path / "trial_0"
        trial_dir.mkdir(parents=True)

        # Create heatmaps directory
        heatmaps_dir = trial_dir / "heatmaps"
        heatmaps_dir.mkdir()

        (heatmaps_dir / "placement_density.csv").write_text("x,y,density\n")
        (heatmaps_dir / "routing_congestion.csv").write_text("x,y,congestion\n")

        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Verify heatmaps are indexed
        heatmap_entries = [
            e for e in index.entries if "heatmap" in str(e.path).lower()
        ]
        assert len(heatmap_entries) == 2

        # Verify content types
        for entry in heatmap_entries:
            assert entry.content_type == "text/csv"
            assert "Heatmap" in entry.label


class TestArtifactIndexFormatting:
    """Test artifact index JSON formatting and UX requirements."""

    def test_artifact_index_json_is_well_formatted(self, tmp_path):
        """
        Test artifact_index.json is well-formatted and includes helpful descriptions.

        This validates the UX requirement that artifact index JSON files are:
        - Properly indented and readable
        - Include descriptive labels for each artifact
        - Include content-type hints
        - Use relative, portable paths

        Steps:
            Step 1: Generate artifact_index.json
            Step 2: Open in JSON viewer/editor (verify it's valid JSON)
            Step 3: Take screenshot (manual step)
            Step 4: Verify JSON is properly indented and readable
            Step 5: Verify each artifact entry includes description and content-type
            Step 6: Verify paths are relative and portable
        """
        # Step 1: Generate artifact_index.json
        trial_dir = tmp_path / "test_study" / "base_case" / "stage_0" / "trial_0"
        trial_dir.mkdir(parents=True)

        # Create sample artifacts
        (trial_dir / "timing_report.txt").write_text("WNS: -100 ps\nTNS: -500 ps")
        (trial_dir / "congestion_report.txt").write_text("Hot bins: 5")
        (trial_dir / "metrics.json").write_text('{"wns_ps": -100, "tns_ps": -500}')
        (trial_dir / "design.v").write_text("module top();")

        logs_dir = trial_dir / "logs"
        logs_dir.mkdir()
        (logs_dir / "stdout.txt").write_text("OpenROAD output...")
        (logs_dir / "stderr.txt").write_text("")

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="base_case",
            stage_index=0,
            trial_index=0,
            eco_names=["buffer_insertion"],
        )

        # Write to file
        output_path = index.write_to_file()
        assert output_path.exists()

        # Step 2: Verify JSON is valid and can be loaded
        with output_path.open() as f:
            data = json.load(f)

        # Step 4: Verify JSON is properly indented and readable
        with output_path.open() as f:
            raw_content = f.read()

        # Check for proper indentation (2 spaces)
        assert "  " in raw_content, "JSON should be indented"

        # Check for newlines (pretty-printed, not compact)
        assert "\n" in raw_content, "JSON should be multi-line"

        # Verify the file ends with a newline (POSIX standard)
        assert raw_content.endswith("\n"), "JSON should end with newline"

        # Check that objects are not on single lines
        # (pretty print should have opening brace, then newline)
        assert "{\n" in raw_content, "Objects should be pretty-printed"

        # Step 5: Verify each artifact entry includes description and content-type
        assert "entries" in data
        assert len(data["entries"]) > 0, "Should have at least one artifact"

        for entry in data["entries"]:
            # Every entry must have a label (description)
            assert "label" in entry, f"Entry missing 'label': {entry}"
            assert isinstance(entry["label"], str), "Label must be a string"
            assert len(entry["label"]) > 0, "Label must not be empty"

            # Every entry must have a content_type
            assert "content_type" in entry, f"Entry missing 'content_type': {entry}"
            assert isinstance(entry["content_type"], str), "Content type must be string"
            assert len(entry["content_type"]) > 0, "Content type must not be empty"

            # Verify content type follows standard format (e.g., "text/plain")
            assert "/" in entry["content_type"] or entry[
                "content_type"
            ].startswith("text/x-"), (
                f"Content type should follow MIME type format: {entry['content_type']}"
            )

            # Every entry must have a path
            assert "path" in entry, f"Entry missing 'path': {entry}"
            assert isinstance(entry["path"], str), "Path must be a string"

            # Every entry should have size information
            assert "size_bytes" in entry, f"Entry missing 'size_bytes': {entry}"
            assert isinstance(entry["size_bytes"], int), "Size must be an integer"

        # Step 6: Verify paths are relative and portable
        for entry in data["entries"]:
            path = entry["path"]

            # Paths should not be absolute
            assert not path.startswith("/"), f"Path should be relative: {path}"

            # Paths should not contain Windows drive letters
            assert ":" not in path or path.count(":") == path.count(
                "::"
            ), f"Path should not contain drive letters: {path}"

            # Paths should use forward slashes (portable)
            # (Python's Path automatically uses forward slashes in JSON)
            if "\\" in path:
                assert False, f"Path should use forward slashes: {path}"

        # Verify high-level structure is present
        assert "study_name" in data
        assert "case_name" in data
        assert "stage_index" in data
        assert "trial_index" in data

        # Verify metadata is present (for ECO traceability)
        assert "metadata" in data
        if "eco_names" in index.metadata:
            assert "eco_names" in data["metadata"]

    def test_stage_summary_json_is_well_formatted(self, tmp_path):
        """
        Test stage_artifact_summary.json is well-formatted.

        Stage summaries should follow the same formatting standards:
        - Properly indented
        - Includes descriptive metadata
        - Uses relative, portable paths
        """
        summary = StageArtifactSummary(
            study_name="test_study",
            case_name="base_case",
            stage_index=0,
            stage_root=tmp_path,
        )

        # Add trial data
        for i in range(3):
            trial_index_path = tmp_path / f"trial_{i}" / "artifact_index.json"
            summary.add_trial(
                trial_index=i,
                success=(i < 2),  # First 2 succeed, last one fails
                artifact_index_path=trial_index_path,
                metrics={"wns_ps": -100 - i * 10, "tns_ps": -500 - i * 50},
            )

        # Write to file
        output_path = summary.write_to_file()
        assert output_path.exists()

        # Verify JSON is valid
        with output_path.open() as f:
            data = json.load(f)

        # Verify proper indentation
        with output_path.open() as f:
            raw_content = f.read()

        assert "  " in raw_content, "JSON should be indented"
        assert "\n" in raw_content, "JSON should be multi-line"
        assert raw_content.endswith("\n"), "JSON should end with newline"

        # Verify required fields
        assert data["study_name"] == "test_study"
        assert data["trial_count"] == 3
        assert data["success_count"] == 2
        assert data["failure_count"] == 1

        # Verify metrics summary is present
        assert "metrics_summary" in data
        assert "wns_ps" in data["metrics_summary"]
        assert len(data["metrics_summary"]["wns_ps"]) == 3

        # Verify trial_indexes uses relative paths
        for trial_path in data["trial_indexes"]:
            # Should be relative paths
            assert not trial_path.startswith(
                "/"
            ), f"Trial path should be relative: {trial_path}"
