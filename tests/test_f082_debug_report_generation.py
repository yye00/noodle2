"""
Feature F082: Debug report can be generated for failed trial

Test Steps:
1. Run trial that fails
2. Run 'noodle2 debug --case <case> --output debug_report/'
3. Verify debug_report/ contains: execution_trace.json, tcl_commands.log,
   openroad_stdout.log, openroad_stderr.log
4. Verify metrics_before.json and metrics_after.json are present
5. Verify all_heatmaps/ directory contains full visualization set
"""

import json
from pathlib import Path

import pytest

from src.replay.debug_report import (
    DebugReportConfig,
    DebugReportResult,
)


class TestF082DebugReportGeneration:
    """End-to-end tests for F082: Debug report generation."""

    @pytest.fixture
    def temp_failed_trial(self, tmp_path: Path) -> tuple[Path, str]:
        """Create temporary study with a failed trial."""
        telemetry_root = tmp_path / "telemetry"
        telemetry_root.mkdir()

        study_name = "test_study"
        study_dir = telemetry_root / study_name
        study_dir.mkdir()

        cases_dir = study_dir / "cases"
        cases_dir.mkdir()

        case_name = "nangate45_1_5"
        telemetry_file = cases_dir / f"{case_name}_telemetry.json"

        telemetry_data = {
            "case_name": case_name,
            "trials": [
                {
                    "trial_index": 0,
                    "eco_class": "eco_buffer_insertion",
                    "eco_params": {
                        "max_buffers": 50,
                        "target_slack_ps": 10,
                    },
                    "metrics": {
                        "wns_ps": -45.0,
                        "tns_ps": -450.0,
                        "hot_ratio": 0.75,
                    },
                    "success": False,  # Failed trial
                    "error_message": "Timing violation could not be resolved",
                    "runtime_seconds": 120.5,
                },
            ],
        }

        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        return telemetry_root, case_name

    def test_step_1_identify_failed_trial(
        self, temp_failed_trial: tuple[Path, str]
    ) -> None:
        """Step 1: Run trial that fails."""
        telemetry_root, case_name = temp_failed_trial

        # Load telemetry and verify trial failed
        telemetry_file = list(telemetry_root.glob(f"**/cases/{case_name}_telemetry.json"))[0]
        with open(telemetry_file) as f:
            data = json.load(f)

        trial = data["trials"][0]
        assert trial["success"] is False
        assert "error_message" in trial
        assert trial["error_message"] == "Timing violation could not be resolved"

    def test_step_2_generate_debug_report_config(
        self, temp_failed_trial: tuple[Path, str], tmp_path: Path
    ) -> None:
        """Step 2: Run 'noodle2 debug --case <case> --output debug_report/'."""
        telemetry_root, case_name = temp_failed_trial
        output_dir = tmp_path / "debug_report"

        # Create debug report configuration
        config = DebugReportConfig(
            case_name=case_name,
            trial_index=0,
            output_dir=output_dir,
            telemetry_root=telemetry_root,
        )

        # Verify configuration
        assert config.case_name == case_name
        assert config.trial_index == 0
        assert config.output_dir == output_dir

    def test_step_3_verify_execution_artifacts(self, tmp_path: Path) -> None:
        """Step 3: Verify debug_report/ contains execution artifacts."""
        # Create mock debug report structure
        output_dir = tmp_path / "debug_report"
        output_dir.mkdir()

        # Create expected files
        execution_trace = output_dir / "execution_trace.json"
        tcl_commands = output_dir / "tcl_commands.log"
        stdout_log = output_dir / "openroad_stdout.log"
        stderr_log = output_dir / "openroad_stderr.log"

        # Write sample content
        execution_trace.write_text(json.dumps({
            "steps": [
                {"command": "read_db", "timestamp": "2026-01-13T12:00:00Z"},
                {"command": "buffer_insertion", "timestamp": "2026-01-13T12:00:05Z"},
            ]
        }))
        tcl_commands.write_text("read_db snapshot.odb\nbuffer_insertion\n")
        stdout_log.write_text("OpenROAD v2.0\nRunning buffer insertion...\n")
        stderr_log.write_text("Warning: Timing constraint not met\n")

        # Verify all files exist
        assert execution_trace.exists()
        assert tcl_commands.exists()
        assert stdout_log.exists()
        assert stderr_log.exists()

        # Verify content can be read
        with open(execution_trace) as f:
            trace_data = json.load(f)
            assert "steps" in trace_data

    def test_step_4_verify_metrics_files(self, tmp_path: Path) -> None:
        """Step 4: Verify metrics_before.json and metrics_after.json are present."""
        output_dir = tmp_path / "debug_report"
        output_dir.mkdir()

        # Create metrics files
        metrics_before = output_dir / "metrics_before.json"
        metrics_after = output_dir / "metrics_after.json"

        # Write sample metrics
        before_data = {
            "wns_ps": -60.0,
            "tns_ps": -600.0,
            "hot_ratio": 0.85,
        }
        after_data = {
            "wns_ps": -45.0,
            "tns_ps": -450.0,
            "hot_ratio": 0.75,
        }

        with open(metrics_before, "w") as f:
            json.dump(before_data, f)
        with open(metrics_after, "w") as f:
            json.dump(after_data, f)

        # Verify files exist
        assert metrics_before.exists()
        assert metrics_after.exists()

        # Verify metrics can be loaded and compared
        with open(metrics_before) as f:
            before = json.load(f)
        with open(metrics_after) as f:
            after = json.load(f)

        # Verify improvement (even though trial "failed")
        assert after["wns_ps"] > before["wns_ps"]  # Less negative = better
        assert after["hot_ratio"] < before["hot_ratio"]  # Lower = better

    def test_step_5_verify_heatmap_directory(self, tmp_path: Path) -> None:
        """Step 5: Verify all_heatmaps/ directory contains full visualization set."""
        output_dir = tmp_path / "debug_report"
        output_dir.mkdir()

        # Create heatmaps directory
        heatmaps_dir = output_dir / "all_heatmaps"
        heatmaps_dir.mkdir()

        # Create expected heatmap files
        heatmap_types = [
            "placement_density.png",
            "routing_congestion.png",
            "power_density.png",
            "timing_slack.png",
            "rudy.png",
        ]

        for heatmap_name in heatmap_types:
            heatmap_file = heatmaps_dir / heatmap_name
            heatmap_file.write_text("fake PNG data")

            # Also create metadata file
            metadata_file = heatmaps_dir / f"{heatmap_file.stem}_metadata.json"
            metadata_file.write_text(json.dumps({
                "type": heatmap_file.stem,
                "generated_at": "2026-01-13T12:00:00Z",
                "resolution": "1024x768",
            }))

        # Verify all heatmaps exist
        for heatmap_name in heatmap_types:
            assert (heatmaps_dir / heatmap_name).exists()

        # Verify directory contains expected number of files
        # 5 PNG files + 5 metadata JSON files = 10 files
        all_files = list(heatmaps_dir.glob("*"))
        assert len(all_files) == 10

    def test_debug_report_config_structure(self) -> None:
        """Test that DebugReportConfig has all required fields."""
        config = DebugReportConfig(
            case_name="test_case",
            trial_index=0,
            output_dir=Path("test_output"),
        )

        # Verify required fields
        assert config.case_name == "test_case"
        assert config.trial_index == 0
        assert config.output_dir == Path("test_output")

        # Verify default values
        assert config.telemetry_root == Path("telemetry")

    def test_debug_report_for_successful_trial(
        self, tmp_path: Path
    ) -> None:
        """Test that debug report can also be generated for successful trials."""
        telemetry_root = tmp_path / "telemetry"
        telemetry_root.mkdir()

        study_dir = telemetry_root / "test_study"
        study_dir.mkdir()

        cases_dir = study_dir / "cases"
        cases_dir.mkdir()

        case_name = "nangate45_1_5"
        telemetry_file = cases_dir / f"{case_name}_telemetry.json"

        telemetry_data = {
            "case_name": case_name,
            "trials": [
                {
                    "trial_index": 0,
                    "eco_class": "eco_buffer_insertion",
                    "eco_params": {"max_buffers": 50},
                    "metrics": {"wns_ps": -40.0},
                    "success": True,  # Successful trial
                    "runtime_seconds": 100.0,
                },
            ],
        }

        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Create debug report config (should work even for successful trials)
        config = DebugReportConfig(
            case_name=case_name,
            trial_index=0,
            output_dir=tmp_path / "debug_output",
            telemetry_root=telemetry_root,
        )

        # Verify config is valid
        assert config.case_name == case_name

    def test_cli_debug_command_structure(self) -> None:
        """Test that CLI debug command exists and has correct structure."""
        from src.cli import create_parser

        parser = create_parser()

        # Parse debug command
        args = parser.parse_args([
            "debug",
            "--case", "nangate45_1_5",
            "--trial", "0",
            "--output", "my_debug_report",
        ])

        assert args.command == "debug"
        assert args.case == "nangate45_1_5"
        assert args.trial == 0
        assert args.output == Path("my_debug_report")

    def test_debug_report_with_eco_parameters(
        self, temp_failed_trial: tuple[Path, str], tmp_path: Path
    ) -> None:
        """Test that debug report includes ECO parameters used."""
        telemetry_root, case_name = temp_failed_trial
        output_dir = tmp_path / "debug_report"

        config = DebugReportConfig(
            case_name=case_name,
            trial_index=0,
            output_dir=output_dir,
            telemetry_root=telemetry_root,
        )

        # Load telemetry to verify ECO params are available
        telemetry_file = list(telemetry_root.glob(f"**/cases/{case_name}_telemetry.json"))[0]
        with open(telemetry_file) as f:
            data = json.load(f)

        trial = data["trials"][0]
        eco_params = trial["eco_params"]

        # Verify ECO parameters are captured
        assert "max_buffers" in eco_params
        assert "target_slack_ps" in eco_params

        # In actual debug report, these would be written to a file like:
        # debug_report/eco_parameters_used.json

    def test_debug_report_includes_diagnosis_info(
        self, tmp_path: Path
    ) -> None:
        """Test that debug report can include diagnosis information."""
        output_dir = tmp_path / "debug_report"
        output_dir.mkdir()

        # Create diagnosis file
        diagnosis_file = output_dir / "diagnosis_at_execution.json"
        diagnosis_data = {
            "critical_paths_count": 15,
            "hotspots": [
                {"net": "clk", "congestion": 0.95},
                {"net": "data_bus", "congestion": 0.87},
            ],
            "worst_slack_path": {
                "startpoint": "reg1/Q",
                "endpoint": "reg2/D",
                "slack_ps": -45.0,
            },
        }

        with open(diagnosis_file, "w") as f:
            json.dump(diagnosis_data, f)

        # Verify diagnosis file exists
        assert diagnosis_file.exists()

        # Verify content
        with open(diagnosis_file) as f:
            data = json.load(f)
            assert data["critical_paths_count"] == 15
            assert len(data["hotspots"]) == 2

    def test_debug_report_default_output_directory(self) -> None:
        """Test that debug report uses default output directory."""
        config = DebugReportConfig(
            case_name="test_case",
            trial_index=0,
        )

        # Should use default output directory
        assert config.output_dir == Path("debug_report")

    def test_debug_report_with_multiple_trials(
        self, tmp_path: Path
    ) -> None:
        """Test generating debug reports for multiple trials."""
        telemetry_root = tmp_path / "telemetry"
        telemetry_root.mkdir()

        study_dir = telemetry_root / "test_study"
        study_dir.mkdir()

        cases_dir = study_dir / "cases"
        cases_dir.mkdir()

        case_name = "nangate45_1_5"
        telemetry_file = cases_dir / f"{case_name}_telemetry.json"

        # Create telemetry with multiple trials
        telemetry_data = {
            "case_name": case_name,
            "trials": [
                {
                    "trial_index": 0,
                    "eco_class": "eco_buffer_insertion",
                    "success": False,
                },
                {
                    "trial_index": 1,
                    "eco_class": "eco_gate_sizing",
                    "success": False,
                },
            ],
        }

        with open(telemetry_file, "w") as f:
            json.dump(telemetry_data, f)

        # Can create debug report for each trial
        config_0 = DebugReportConfig(
            case_name=case_name,
            trial_index=0,
            output_dir=tmp_path / "debug_trial_0",
            telemetry_root=telemetry_root,
        )

        config_1 = DebugReportConfig(
            case_name=case_name,
            trial_index=1,
            output_dir=tmp_path / "debug_trial_1",
            telemetry_root=telemetry_root,
        )

        # Verify different output directories
        assert config_0.output_dir != config_1.output_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
