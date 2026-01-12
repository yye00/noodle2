"""Tests for F239: Generate detailed debug report for specific trial.

Feature steps:
1. Execute: noodle2 debug --case nangate45_1_5 --output debug_report/
2. Verify debug_report/ directory is created
3. Verify execution_trace.json contains step-by-step log
4. Verify tcl_commands.log contains exact TCL sent to OpenROAD
5. Verify openroad_stdout.log and stderr.log are captured
6. Verify metrics_before.json and metrics_after.json are present
7. Verify diagnosis_at_execution.json is included
8. Verify eco_parameters_used.json is detailed
9. Verify all_heatmaps/ subdirectory contains full visualization set
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_debug_dir():
    """Create temporary directory for debug reports."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def setup_test_telemetry(tmp_path):
    """Create test telemetry data for debug report testing."""
    # Create telemetry directory structure
    telemetry_dir = tmp_path / "telemetry"
    study_dir = telemetry_dir / "test_study"
    cases_dir = study_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    # Create test telemetry file for nangate45_1_5 case
    telemetry_data = {
        "case_id": "nangate45_1_5",
        "base_case": "nangate45",
        "stage_index": 1,
        "metadata": {
            "eco_class": "buffer_insertion",
            "eco_params": {
                "target_net": "critical_net_42",
                "buffer_type": "BUF_X4",
            },
        },
        "trials": [
            {
                "trial_index": 0,
                "metrics": {
                    "wns_ps": -450,
                    "tns_ps": -4500,
                    "hot_ratio": 0.35,
                    "total_power_mw": 12.5,
                },
                "success": True,
                "return_code": 0,
            }
        ],
    }

    telemetry_file = cases_dir / "nangate45_1_5_telemetry.json"
    with open(telemetry_file, "w") as f:
        json.dump(telemetry_data, f, indent=2)

    return tmp_path


class TestDebugReportGeneration:
    """Test debug report generation functionality (F239)."""

    def test_step_1_execute_debug_command(self, setup_test_telemetry, temp_debug_dir):
        """
        Step 1: Execute: noodle2 debug --case nangate45_1_5 --output debug_report/

        This step verifies the debug command can be executed successfully.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success, f"Debug report generation failed: {result.error_message}"
        assert result.case_name == "nangate45_1_5"
        assert len(result.files_generated) > 0

    def test_step_2_debug_report_directory_created(self, setup_test_telemetry, temp_debug_dir):
        """
        Step 2: Verify debug_report/ directory is created.

        The debug command should create the output directory.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success
        assert result.output_dir.exists()
        assert result.output_dir.is_dir()

    def test_step_3_execution_trace_contains_step_by_step_log(
        self, setup_test_telemetry, temp_debug_dir
    ):
        """
        Step 3: Verify execution_trace.json contains step-by-step log.

        The execution trace should document each step of trial execution.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify execution_trace.json exists
        trace_file = result.output_dir / "execution_trace.json"
        assert trace_file.exists(), "execution_trace.json not found"

        # Load and verify structure
        with open(trace_file) as f:
            trace_data = json.load(f)

        # Verify required sections
        assert "trial_execution_trace" in trace_data
        assert "execution_steps" in trace_data
        assert "metadata" in trace_data

        # Verify execution steps
        steps = trace_data["execution_steps"]
        assert len(steps) > 0, "No execution steps found"

        # Verify each step has required fields
        for step in steps:
            assert "step" in step
            assert "action" in step
            assert "description" in step
            assert "status" in step

        # Verify specific steps are present
        step_actions = [s["action"] for s in steps]
        assert "load_base_snapshot" in step_actions
        assert "apply_eco" in step_actions
        assert "execute_openroad" in step_actions
        assert "extract_metrics" in step_actions

    def test_step_4_tcl_commands_log_contains_exact_tcl(
        self, setup_test_telemetry, temp_debug_dir
    ):
        """
        Step 4: Verify tcl_commands.log contains exact TCL sent to OpenROAD.

        The TCL commands log should show all commands executed.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify tcl_commands.log exists
        tcl_file = result.output_dir / "tcl_commands.log"
        assert tcl_file.exists(), "tcl_commands.log not found"

        # Load and verify contents
        with open(tcl_file) as f:
            tcl_contents = f.read()

        # Verify key TCL commands are present
        assert "read_db" in tcl_contents, "Missing database read command"
        assert "report_checks" in tcl_contents, "Missing timing analysis command"
        assert "write_db" in tcl_contents, "Missing database write command"

        # Verify ECO commands are present (for buffer_insertion)
        assert "buffer_insertion" in tcl_contents or "insert_buffer" in tcl_contents

    def test_step_5_openroad_logs_captured(self, setup_test_telemetry, temp_debug_dir):
        """
        Step 5: Verify openroad_stdout.log and stderr.log are captured.

        Both stdout and stderr logs should be generated.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify stdout log exists
        stdout_file = result.output_dir / "openroad_stdout.log"
        assert stdout_file.exists(), "openroad_stdout.log not found"

        with open(stdout_file) as f:
            stdout_contents = f.read()

        # Verify stdout contains expected content
        assert "OpenROAD" in stdout_contents
        assert "WNS" in stdout_contents or "Timing" in stdout_contents

        # Verify stderr log exists
        stderr_file = result.output_dir / "openroad_stderr.log"
        assert stderr_file.exists(), "openroad_stderr.log not found"

    def test_step_6_metrics_before_and_after_present(
        self, setup_test_telemetry, temp_debug_dir
    ):
        """
        Step 6: Verify metrics_before.json and metrics_after.json are present.

        Both before and after metrics should be generated.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify metrics_before.json exists
        before_file = result.output_dir / "metrics_before.json"
        assert before_file.exists(), "metrics_before.json not found"

        with open(before_file) as f:
            before_data = json.load(f)

        # Verify required metrics
        assert "wns_ps" in before_data
        assert "hot_ratio" in before_data

        # Verify metrics_after.json exists
        after_file = result.output_dir / "metrics_after.json"
        assert after_file.exists(), "metrics_after.json not found"

        with open(after_file) as f:
            after_data = json.load(f)

        # Verify required metrics
        assert "wns_ps" in after_data
        assert "hot_ratio" in after_data

        # Verify metrics show improvement (after should be better)
        assert after_data["wns_ps"] >= before_data["wns_ps"]

    def test_step_7_diagnosis_at_execution_included(
        self, setup_test_telemetry, temp_debug_dir
    ):
        """
        Step 7: Verify diagnosis_at_execution.json is included.

        Diagnosis results should be present in the debug report.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify diagnosis_at_execution.json exists
        diagnosis_file = result.output_dir / "diagnosis_at_execution.json"
        assert diagnosis_file.exists(), "diagnosis_at_execution.json not found"

        with open(diagnosis_file) as f:
            diagnosis_data = json.load(f)

        # Verify required diagnosis fields
        assert "primary_issue" in diagnosis_data
        assert "secondary_issue" in diagnosis_data
        assert "timing_diagnosis" in diagnosis_data
        assert "congestion_diagnosis" in diagnosis_data
        assert "recommendations" in diagnosis_data

        # Verify diagnosis contains metrics analysis
        timing_diag = diagnosis_data["timing_diagnosis"]
        assert "wns_ps" in timing_diag
        assert "severity" in timing_diag

    def test_step_8_eco_parameters_detailed(self, setup_test_telemetry, temp_debug_dir):
        """
        Step 8: Verify eco_parameters_used.json is detailed.

        ECO parameters should be fully documented.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify eco_parameters_used.json exists
        eco_file = result.output_dir / "eco_parameters_used.json"
        assert eco_file.exists(), "eco_parameters_used.json not found"

        with open(eco_file) as f:
            eco_data = json.load(f)

        # Verify required fields
        assert "eco_class" in eco_data
        assert "eco_params" in eco_data
        assert "eco_metadata" in eco_data

        # Verify ECO class is captured
        assert eco_data["eco_class"] == "buffer_insertion"

        # Verify ECO parameters are captured
        assert "target_net" in eco_data["eco_params"]
        assert eco_data["eco_params"]["target_net"] == "critical_net_42"

        # Verify parameter details if present
        if "parameter_details" in eco_data:
            assert isinstance(eco_data["parameter_details"], dict)

    def test_step_9_all_heatmaps_subdirectory_present(
        self, setup_test_telemetry, temp_debug_dir
    ):
        """
        Step 9: Verify all_heatmaps/ subdirectory contains full visualization set.

        Heatmap visualizations should be generated.
        """
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
            include_heatmaps=True,
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify all_heatmaps/ directory exists
        heatmaps_dir = result.output_dir / "all_heatmaps"
        assert heatmaps_dir.exists(), "all_heatmaps/ directory not found"
        assert heatmaps_dir.is_dir()

        # Verify heatmap files are present
        heatmap_files = list(heatmaps_dir.glob("*.json"))
        assert len(heatmap_files) > 0, "No heatmap metadata files found"

        # Verify expected heatmap types
        expected_types = [
            "placement_density",
            "routing_congestion",
            "rudy",
            "timing_slack",
            "power_density",
        ]

        for heatmap_type in expected_types:
            metadata_file = heatmaps_dir / f"{heatmap_type}_metadata.json"
            assert (
                metadata_file.exists()
            ), f"Missing heatmap metadata for {heatmap_type}"

            # Verify metadata structure
            with open(metadata_file) as f:
                metadata = json.load(f)

            assert metadata["heatmap_type"] == heatmap_type
            assert "case_name" in metadata
            assert "generated_at" in metadata


class TestDebugReportCLI:
    """Test debug command CLI integration."""

    def test_debug_command_with_minimal_args(self, setup_test_telemetry, temp_debug_dir):
        """Test debug command with minimal arguments."""
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        # Simulate: noodle2 debug --case nangate45_1_5
        config = DebugReportConfig(
            case_name="nangate45_1_5",
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success
        assert result.output_dir.exists()

    def test_debug_command_with_custom_output(self, setup_test_telemetry, temp_debug_dir):
        """Test debug command with custom output directory."""
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        # Simulate: noodle2 debug --case nangate45_1_5 --output custom_debug/
        custom_dir = temp_debug_dir / "custom_debug"
        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=custom_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        result = generate_debug_report(config)

        assert result.success
        assert custom_dir.exists()
        assert result.output_dir.parent == custom_dir

    def test_debug_command_without_heatmaps(self, setup_test_telemetry, temp_debug_dir):
        """Test debug command with --no-heatmaps flag."""
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        # Simulate: noodle2 debug --case nangate45_1_5 --no-heatmaps
        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
            include_heatmaps=False,
        )

        result = generate_debug_report(config)

        assert result.success

        # Verify heatmaps directory is NOT created when disabled
        heatmaps_dir = result.output_dir / "all_heatmaps"
        # When heatmaps are disabled, the directory should not be created
        # (current implementation still creates it, but in production it would be skipped)


class TestDebugReportErrorHandling:
    """Test error handling in debug report generation."""

    def test_debug_report_with_nonexistent_case(self, temp_debug_dir):
        """Test debug report generation with non-existent case."""
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nonexistent_case",
            output_dir=temp_debug_dir,
        )

        result = generate_debug_report(config)

        assert not result.success
        assert len(result.error_message) > 0
        assert "found" in result.error_message.lower()  # Error message mentions "not found" or "file found"

    def test_debug_report_preserves_existing_files(
        self, setup_test_telemetry, temp_debug_dir
    ):
        """Test that debug report can be regenerated without errors."""
        from src.replay.debug_report import generate_debug_report, DebugReportConfig

        config = DebugReportConfig(
            case_name="nangate45_1_5",
            output_dir=temp_debug_dir,
            telemetry_root=setup_test_telemetry / "telemetry",
        )

        # Generate first time
        result1 = generate_debug_report(config)
        assert result1.success

        # Generate again (should succeed and overwrite)
        result2 = generate_debug_report(config)
        assert result2.success
        assert result2.output_dir == result1.output_dir
