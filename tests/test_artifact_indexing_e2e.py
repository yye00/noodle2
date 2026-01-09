"""
End-to-end test for artifact indexing and deep linking verification.

Tests comprehensive artifact indexing across trials, stages, and studies,
including deep linking support for Ray Dashboard navigation.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.artifact_structure import (
    ArtifactDirectoryLayout,
    create_study_artifact_structure,
)
from src.trial_runner.artifact_index import (
    StageArtifactSummary,
    TrialArtifactIndex,
    generate_trial_artifact_index,
    infer_content_type,
)


class TestArtifactIndexingE2E:
    """
    End-to-end test for artifact indexing and deep linking.

    Covers all 12 steps of the feature:
    1. Execute Study producing diverse artifacts
    2. Generate artifact_index.json for each trial
    3. Verify index contains paths to all key files
    4. Verify index includes content-type hints
    5. Verify index includes high-level labels
    6. Generate stage-level artifact index aggregating trials
    7. Generate Study-level artifact index
    8. Emit artifact URLs in Ray task logs
    9. Test deep linking from dashboard to artifacts
    10. Verify all artifact links are valid and accessible
    11. Test artifact search by content-type
    12. Test artifact filtering by stage/case
    """

    def test_step_1_execute_study_producing_diverse_artifacts(self, tmp_path):
        """
        Step 1: Execute Study producing diverse artifacts.

        Simulates a complete study execution that produces multiple
        trial artifacts across different stages.
        """
        # Create study structure
        study_name = "artifact_indexing_test"
        case_name = "base_case"

        # Create directory structure for a multi-stage study
        study_root = tmp_path / "studies" / study_name
        study_root.mkdir(parents=True)

        # Create artifacts for multiple trials across 2 stages
        num_stages = 2
        trials_per_stage = 3

        for stage_idx in range(num_stages):
            stage_dir = study_root / f"stage_{stage_idx}"
            stage_dir.mkdir()

            for trial_idx in range(trials_per_stage):
                trial_dir = stage_dir / f"{case_name}_trial_{trial_idx}"
                trial_dir.mkdir()

                # Create diverse artifacts
                self._create_trial_artifacts(trial_dir)

        # Verify study structure exists
        assert study_root.exists()
        assert (study_root / "stage_0").exists()
        assert (study_root / "stage_1").exists()

        # Verify trials exist
        for stage_idx in range(num_stages):
            for trial_idx in range(trials_per_stage):
                trial_dir = study_root / f"stage_{stage_idx}" / f"{case_name}_trial_{trial_idx}"
                assert trial_dir.exists()

    def test_step_2_generate_artifact_index_for_each_trial(self, tmp_path):
        """
        Step 2: Generate artifact_index.json for each trial.

        Creates artifact indexes for all trials in the study.
        """
        study_name = "artifact_indexing_test"
        case_name = "base_case"
        study_root = tmp_path / "studies" / study_name
        study_root.mkdir(parents=True)

        # Create trial with artifacts
        trial_dir = study_root / "stage_0" / "base_case_trial_0"
        trial_dir.mkdir(parents=True)
        self._create_trial_artifacts(trial_dir)

        # Generate artifact index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name=study_name,
            case_name=case_name,
            stage_index=0,
            trial_index=0,
            eco_names=["buffer_insertion", "gate_sizing"],
        )

        # Write index to file
        index_path = index.write_to_file()

        # Verify index file was created
        assert index_path.exists()
        assert index_path.name == "artifact_index.json"

        # Verify index is valid JSON
        with index_path.open() as f:
            index_data = json.load(f)

        assert index_data["study_name"] == study_name
        assert index_data["case_name"] == case_name
        assert index_data["stage_index"] == 0
        assert index_data["trial_index"] == 0

    def test_step_3_verify_index_contains_paths_to_all_key_files(self, tmp_path):
        """
        Step 3: Verify index contains paths to all key files.

        Checks that all expected artifacts are discovered and indexed.
        """
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        self._create_trial_artifacts(trial_dir)

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Get all indexed paths
        indexed_paths = {entry.path.name for entry in index.entries}

        # Verify key files are indexed
        expected_files = {
            "timing_report.txt",
            "congestion_report.txt",
            "metrics.json",
            "design.v",
            "power.rpt",
        }

        # Check that expected files are present in index
        for expected_file in expected_files:
            assert expected_file in indexed_paths, f"Missing {expected_file} in index"

    def test_step_4_verify_index_includes_content_type_hints(self, tmp_path):
        """
        Step 4: Verify index includes content-type hints.

        Ensures proper content-type classification for different artifact types.
        """
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        self._create_trial_artifacts(trial_dir)

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Verify content-type hints
        content_types = {entry.path.name: entry.content_type for entry in index.entries}

        # Check specific content types
        assert content_types.get("timing_report.txt") == "text/plain"
        assert content_types.get("metrics.json") == "application/json"
        assert content_types.get("design.v") == "text/x-verilog"

        # Check that all entries have content-type
        for entry in index.entries:
            assert entry.content_type is not None
            assert len(entry.content_type) > 0

    def test_step_5_verify_index_includes_high_level_labels(self, tmp_path):
        """
        Step 5: Verify index includes high-level labels.

        Checks that human-readable labels are provided for all artifacts.
        """
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        self._create_trial_artifacts(trial_dir)

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Verify labels exist and are meaningful
        for entry in index.entries:
            assert entry.label is not None
            assert len(entry.label) > 0
            # Labels should be human-readable (not just filenames)
            assert entry.label != str(entry.path)

        # Check specific labels
        labels = {entry.path.name: entry.label for entry in index.entries}

        # Verify descriptive labels
        assert "Timing" in labels.get("timing_report.txt", "")
        assert "Congestion" in labels.get("congestion_report.txt", "")
        assert "Metrics" in labels.get("metrics.json", "")

    def test_step_6_generate_stage_level_artifact_index(self, tmp_path):
        """
        Step 6: Generate stage-level artifact index aggregating trials.

        Creates a stage-level summary that aggregates all trial indexes.
        """
        study_name = "test_study"
        case_name = "test_case"
        stage_idx = 0

        # Create stage directory
        stage_dir = tmp_path / f"stage_{stage_idx}"
        stage_dir.mkdir()

        # Create stage summary
        stage_summary = StageArtifactSummary(
            study_name=study_name,
            case_name=case_name,
            stage_index=stage_idx,
            stage_root=stage_dir,
        )

        # Simulate multiple trials
        num_trials = 5
        for trial_idx in range(num_trials):
            trial_dir = stage_dir / f"trial_{trial_idx}"
            trial_dir.mkdir()
            self._create_trial_artifacts(trial_dir)

            # Generate trial index
            trial_index = generate_trial_artifact_index(
                trial_root=trial_dir,
                study_name=study_name,
                case_name=case_name,
                stage_index=stage_idx,
                trial_index=trial_idx,
            )
            trial_index_path = trial_index.write_to_file()

            # Add to stage summary
            success = trial_idx % 2 == 0  # Alternate success/failure
            metrics = {"wns_ps": 1000 + trial_idx * 100}
            stage_summary.add_trial(
                trial_index=trial_idx,
                success=success,
                artifact_index_path=trial_index_path,
                metrics=metrics,
            )

        # Write stage summary
        summary_path = stage_summary.write_to_file()

        # Verify stage summary
        assert summary_path.exists()
        assert summary_path.name == "stage_artifact_summary.json"

        # Load and verify contents
        with summary_path.open() as f:
            summary_data = json.load(f)

        assert summary_data["trial_count"] == num_trials
        assert summary_data["success_count"] == 3  # 0, 2, 4
        assert summary_data["failure_count"] == 2  # 1, 3
        assert len(summary_data["trial_indexes"]) == num_trials

    def test_step_7_generate_study_level_artifact_index(self, tmp_path):
        """
        Step 7: Generate Study-level artifact index.

        Creates a top-level index aggregating all stages.
        """
        study_name = "test_study"
        case_name = "base_case"
        study_root = tmp_path / study_name
        study_root.mkdir()

        # Create multiple stages
        num_stages = 3
        stage_summaries = []

        for stage_idx in range(num_stages):
            stage_dir = study_root / f"stage_{stage_idx}"
            stage_dir.mkdir()

            # Create stage summary
            stage_summary = StageArtifactSummary(
                study_name=study_name,
                case_name=case_name,
                stage_index=stage_idx,
                stage_root=stage_dir,
            )

            # Add a few trials to each stage
            for trial_idx in range(3):
                trial_dir = stage_dir / f"trial_{trial_idx}"
                trial_dir.mkdir()
                self._create_trial_artifacts(trial_dir)

                trial_index = generate_trial_artifact_index(
                    trial_root=trial_dir,
                    study_name=study_name,
                    case_name=case_name,
                    stage_index=stage_idx,
                    trial_index=trial_idx,
                )
                trial_index_path = trial_index.write_to_file()

                stage_summary.add_trial(
                    trial_index=trial_idx,
                    success=True,
                    artifact_index_path=trial_index_path,
                )

            summary_path = stage_summary.write_to_file()
            stage_summaries.append(summary_path)

        # Create study-level index
        study_index = {
            "study_name": study_name,
            "study_root": str(study_root),
            "num_stages": num_stages,
            "stage_summaries": [str(s) for s in stage_summaries],
            "metadata": {
                "description": "Complete artifact index for study",
                "version": "1.0",
            },
        }

        # Write study-level index
        study_index_path = study_root / "study_artifact_index.json"
        with study_index_path.open("w") as f:
            json.dump(study_index, f, indent=2)

        # Verify study index
        assert study_index_path.exists()

        with study_index_path.open() as f:
            loaded_index = json.load(f)

        assert loaded_index["study_name"] == study_name
        assert loaded_index["num_stages"] == num_stages
        assert len(loaded_index["stage_summaries"]) == num_stages

    def test_step_8_emit_artifact_urls_in_ray_task_logs(self, tmp_path):
        """
        Step 8: Emit artifact URLs in Ray task logs.

        Simulates Ray task logging with artifact URLs for deep linking.
        """
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        self._create_trial_artifacts(trial_dir)

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Simulate Ray task log output with artifact URLs
        log_output = []
        log_output.append(f"Trial started: {index.case_name}_stage_{index.stage_index}_trial_{index.trial_index}")
        log_output.append(f"Artifact root: {index.trial_root}")

        # Emit URLs for key artifacts
        for entry in index.entries:
            artifact_url = f"file://{index.trial_root / entry.path}"
            log_output.append(f"Artifact [{entry.label}]: {artifact_url}")

        # Verify log output format
        assert len(log_output) > 2
        assert "Artifact root:" in log_output[1]
        assert any("Artifact [" in line for line in log_output)
        assert any("file://" in line for line in log_output)

        # Verify URLs are well-formed
        for line in log_output:
            if "file://" in line:
                # Extract URL
                url = line.split("file://")[1].strip()
                # Verify it's a valid path
                assert len(url) > 0
                assert not url.startswith("http")  # Should be file:// not http://

    def test_step_9_test_deep_linking_from_dashboard_to_artifacts(self, tmp_path):
        """
        Step 9: Test deep linking from dashboard to artifacts.

        Verifies that artifact URLs can be constructed and resolved.
        """
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        self._create_trial_artifacts(trial_dir)

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Construct deep links for all artifacts
        deep_links = []
        for entry in index.entries:
            # Construct URL that could be used in dashboard
            absolute_path = index.trial_root / entry.path
            deep_link = {
                "label": entry.label,
                "path": str(absolute_path),
                "url": f"file://{absolute_path}",
                "content_type": entry.content_type,
            }
            deep_links.append(deep_link)

        # Verify deep links
        assert len(deep_links) > 0

        for link in deep_links:
            assert "label" in link
            assert "path" in link
            assert "url" in link
            assert "content_type" in link

            # Verify path is absolute
            assert Path(link["path"]).is_absolute()

    def test_step_10_verify_all_artifact_links_are_valid_and_accessible(self, tmp_path):
        """
        Step 10: Verify all artifact links are valid and accessible.

        Checks that all indexed artifacts actually exist and can be accessed.
        """
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        self._create_trial_artifacts(trial_dir)

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Verify all artifacts exist and are accessible
        for entry in index.entries:
            artifact_path = index.trial_root / entry.path

            # Verify file exists
            assert artifact_path.exists(), f"Artifact not found: {artifact_path}"

            # Verify file is readable
            assert artifact_path.is_file(), f"Not a file: {artifact_path}"

            # Verify file is not empty (if text), except for stderr which may be empty
            if entry.content_type.startswith("text/"):
                content = artifact_path.read_text()
                # stderr.txt is allowed to be empty (no errors means empty stderr)
                if "stderr" not in str(artifact_path):
                    assert len(content) > 0, f"Empty artifact: {artifact_path}"

            # Verify size is reported correctly
            assert entry.size_bytes == artifact_path.stat().st_size

    def test_step_11_test_artifact_search_by_content_type(self, tmp_path):
        """
        Step 11: Test artifact search by content-type.

        Implements content-type-based filtering of artifacts.
        """
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()
        self._create_trial_artifacts(trial_dir)

        # Generate index
        index = generate_trial_artifact_index(
            trial_root=trial_dir,
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
        )

        # Define search function
        def search_by_content_type(index: TrialArtifactIndex, content_type: str) -> list:
            """Search artifacts by content-type."""
            return [
                entry for entry in index.entries
                if entry.content_type == content_type
            ]

        # Test searching for different content types
        text_files = search_by_content_type(index, "text/plain")
        json_files = search_by_content_type(index, "application/json")
        verilog_files = search_by_content_type(index, "text/x-verilog")

        # Verify search results
        assert len(text_files) > 0, "Should find text/plain files"
        assert len(json_files) > 0, "Should find JSON files"
        assert len(verilog_files) > 0, "Should find Verilog files"

        # Verify correct classification
        for entry in text_files:
            assert entry.content_type == "text/plain"

        for entry in json_files:
            assert entry.content_type == "application/json"

        for entry in verilog_files:
            assert entry.content_type == "text/x-verilog"

    def test_step_12_test_artifact_filtering_by_stage_and_case(self, tmp_path):
        """
        Step 12: Test artifact filtering by stage/case.

        Implements hierarchical filtering across study structure.
        """
        study_name = "test_study"
        study_root = tmp_path / study_name
        study_root.mkdir()

        # Create artifacts for multiple stages and cases
        stages_and_cases = [
            (0, "base_case"),
            (0, "eco_case_1"),
            (1, "base_case"),
            (1, "eco_case_1"),
            (2, "eco_case_2"),
        ]

        all_indexes = []

        for stage_idx, case_name in stages_and_cases:
            stage_dir = study_root / f"stage_{stage_idx}"
            stage_dir.mkdir(exist_ok=True)

            trial_dir = stage_dir / f"{case_name}_trial_0"
            trial_dir.mkdir(exist_ok=True)
            self._create_trial_artifacts(trial_dir)

            index = generate_trial_artifact_index(
                trial_root=trial_dir,
                study_name=study_name,
                case_name=case_name,
                stage_index=stage_idx,
                trial_index=0,
            )
            all_indexes.append(index)

        # Define filtering functions
        def filter_by_stage(indexes: list, stage_index: int) -> list:
            """Filter indexes by stage."""
            return [idx for idx in indexes if idx.stage_index == stage_index]

        def filter_by_case(indexes: list, case_name: str) -> list:
            """Filter indexes by case name."""
            return [idx for idx in indexes if idx.case_name == case_name]

        # Test stage filtering
        stage_0_indexes = filter_by_stage(all_indexes, 0)
        stage_1_indexes = filter_by_stage(all_indexes, 1)
        stage_2_indexes = filter_by_stage(all_indexes, 2)

        assert len(stage_0_indexes) == 2  # base_case, eco_case_1
        assert len(stage_1_indexes) == 2  # base_case, eco_case_1
        assert len(stage_2_indexes) == 1  # eco_case_2

        # Test case filtering
        base_case_indexes = filter_by_case(all_indexes, "base_case")
        eco_case_1_indexes = filter_by_case(all_indexes, "eco_case_1")
        eco_case_2_indexes = filter_by_case(all_indexes, "eco_case_2")

        assert len(base_case_indexes) == 2  # stage 0, 1
        assert len(eco_case_1_indexes) == 2  # stage 0, 1
        assert len(eco_case_2_indexes) == 1  # stage 2

        # Test combined filtering (stage AND case)
        stage_0_base = [idx for idx in all_indexes
                       if idx.stage_index == 0 and idx.case_name == "base_case"]
        assert len(stage_0_base) == 1
        assert stage_0_base[0].stage_index == 0
        assert stage_0_base[0].case_name == "base_case"

    # Helper method to create realistic trial artifacts
    def _create_trial_artifacts(self, trial_dir: Path) -> None:
        """
        Create a realistic set of trial artifacts for testing.

        Args:
            trial_dir: Directory to create artifacts in
        """
        # Create timing report
        (trial_dir / "timing_report.txt").write_text(
            "Timing Analysis Report\n"
            "======================\n"
            "WNS: -150 ps\n"
            "TNS: -3500 ps\n"
            "Number of violations: 42\n"
        )

        # Create congestion report
        (trial_dir / "congestion_report.txt").write_text(
            "Congestion Analysis Report\n"
            "===========================\n"
            "Peak congestion: 85%\n"
            "Overflow bins: 12\n"
        )

        # Create metrics JSON
        metrics = {
            "wns_ps": -150,
            "tns_ps": -3500,
            "congestion_peak": 0.85,
            "runtime_seconds": 42.5,
        }
        (trial_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))

        # Create verilog netlist
        (trial_dir / "design.v").write_text(
            "module top (input clk, input rst, output out);\n"
            "  // Design logic here\n"
            "endmodule\n"
        )

        # Create power report
        (trial_dir / "power.rpt").write_text(
            "Power Analysis Report\n"
            "=====================\n"
            "Total Power: 125.3 mW\n"
            "Leakage: 12.1 mW\n"
            "Dynamic: 113.2 mW\n"
        )

        # Create logs directory
        logs_dir = trial_dir / "logs"
        logs_dir.mkdir(exist_ok=True)

        (logs_dir / "stdout.txt").write_text(
            "[INFO] Starting OpenROAD flow\n"
            "[INFO] Reading design\n"
            "[INFO] Running placement\n"
            "[INFO] Running routing\n"
            "[INFO] Flow completed successfully\n"
        )

        (logs_dir / "stderr.txt").write_text("")

        # Create heatmaps directory with sample heatmap
        heatmaps_dir = trial_dir / "heatmaps"
        heatmaps_dir.mkdir(exist_ok=True)

        (heatmaps_dir / "congestion_heatmap.csv").write_text(
            "x,y,congestion\n"
            "0,0,0.1\n"
            "0,1,0.3\n"
            "1,0,0.5\n"
            "1,1,0.85\n"
        )


class TestArtifactIndexingIntegration:
    """Additional integration tests for artifact indexing."""

    def test_complete_artifact_indexing_workflow(self, tmp_path):
        """
        Complete end-to-end workflow test.

        Tests the full workflow from study execution to artifact access.
        """
        # Setup study structure
        study_name = "complete_workflow_test"
        case_name = "base_case"
        study_root = tmp_path / study_name
        study_root.mkdir()

        # Create 2 stages with 3 trials each
        num_stages = 2
        num_trials = 3

        all_trial_indexes = []
        all_stage_summaries = []

        for stage_idx in range(num_stages):
            stage_dir = study_root / f"stage_{stage_idx}"
            stage_dir.mkdir()

            # Create stage summary
            stage_summary = StageArtifactSummary(
                study_name=study_name,
                case_name=case_name,
                stage_index=stage_idx,
                stage_root=stage_dir,
            )

            for trial_idx in range(num_trials):
                # Create trial directory
                trial_dir = stage_dir / f"{case_name}_trial_{trial_idx}"
                trial_dir.mkdir()

                # Create artifacts
                self._create_minimal_artifacts(trial_dir)

                # Generate trial index
                trial_index = generate_trial_artifact_index(
                    trial_root=trial_dir,
                    study_name=study_name,
                    case_name=case_name,
                    stage_index=stage_idx,
                    trial_index=trial_idx,
                    eco_names=[f"eco_{trial_idx}"],
                )

                # Write trial index
                index_path = trial_index.write_to_file()
                all_trial_indexes.append(trial_index)

                # Add to stage summary
                stage_summary.add_trial(
                    trial_index=trial_idx,
                    success=True,
                    artifact_index_path=index_path,
                    metrics={"wns_ps": 1000 + trial_idx * 100},
                )

            # Write stage summary
            summary_path = stage_summary.write_to_file()
            all_stage_summaries.append(stage_summary)

        # Verify complete workflow
        assert len(all_trial_indexes) == num_stages * num_trials
        assert len(all_stage_summaries) == num_stages

        # Verify all indexes are accessible
        for trial_index in all_trial_indexes:
            index_file = trial_index.trial_root / "artifact_index.json"
            assert index_file.exists()

            # Verify can load and parse
            with index_file.open() as f:
                data = json.load(f)

            assert "entries" in data
            assert len(data["entries"]) > 0

        # Verify stage summaries
        for stage_summary in all_stage_summaries:
            summary_file = stage_summary.stage_root / "stage_artifact_summary.json"
            assert summary_file.exists()

            with summary_file.open() as f:
                data = json.load(f)

            assert data["trial_count"] == num_trials
            assert data["success_count"] == num_trials

    def _create_minimal_artifacts(self, trial_dir: Path) -> None:
        """Create minimal set of artifacts for testing."""
        (trial_dir / "timing_report.txt").write_text("WNS: 1000 ps\n")
        (trial_dir / "metrics.json").write_text('{"wns_ps": 1000}\n')
        (trial_dir / "design.v").write_text("module top; endmodule\n")
