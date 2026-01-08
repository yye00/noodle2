"""Tests for global routing with congestion report generation."""

import tempfile
from pathlib import Path

import pytest

from src.controller.types import ExecutionMode
from src.trial_runner.tcl_generator import generate_trial_script, write_trial_script


class TestGlobalRoutingCongestionReport:
    """Test global routing command generation in TCL scripts."""

    def test_sta_congestion_script_contains_global_route_command(self):
        """Verify STA+congestion script mentions global_route command."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify script mentions global_route command
        assert "global_route" in script
        assert "-congestion_report_file" in script or "congestion_report_file" in script

    def test_sta_congestion_script_contains_congestion_report_path(self):
        """Verify STA+congestion script defines congestion report path."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify congestion report path is defined
        assert "congestion_report" in script
        assert "congestion_report.txt" in script

    def test_sta_congestion_script_describes_global_routing_section(self):
        """Verify STA+congestion script has global routing section."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify script has a dedicated global routing section
        assert "GLOBAL ROUTING" in script
        assert "CONGESTION" in script

    def test_sta_congestion_script_has_flow_stages(self):
        """Verify STA+congestion script includes complete flow stages."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="counter",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify script includes all expected flow stages
        assert "SYNTHESIS" in script or "synthesis" in script.lower()
        assert "FLOORPLAN" in script or "floorplan" in script.lower()
        assert "PLACEMENT" in script or "placement" in script.lower()
        assert "GLOBAL ROUTING" in script or "global routing" in script.lower()
        assert "TIMING ANALYSIS" in script or "timing" in script.lower()

    def test_sta_congestion_script_generates_realistic_congestion_data(self):
        """Verify STA+congestion script generates congestion metrics."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify script generates congestion metrics
        assert "Total bins:" in script or "bins_total" in script
        assert "Overflow bins:" in script or "bins_hot" in script

    def test_sta_congestion_script_writes_to_file(self):
        """Verify STA+congestion script can be written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "test_script.tcl"

            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test_design",
                output_dir="/work",
                clock_period_ns=10.0,
            )

            assert script_path.exists()
            content = script_path.read_text()

            # Verify written file contains global routing content
            assert "global_route" in content
            assert "congestion" in content.lower()

    def test_sta_only_script_does_not_contain_global_route(self):
        """Verify STA-only script does NOT contain global routing."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # STA-only should NOT have global routing
        assert "global_route" not in script
        # STA-only should skip congestion analysis
        assert "skip" in script.lower() and "congestion" in script.lower()

    def test_congestion_report_format_matches_parser(self):
        """Verify generated congestion report format matches parser expectations."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify the report format includes fields the parser expects
        # The parser looks for: "Total bins:", "Overflow bins:", "Max overflow:"
        assert "Total bins:" in script
        assert "Overflow bins:" in script or "overflow bins" in script.lower()
        assert "Max overflow:" in script or "max overflow" in script.lower()

    def test_layer_metrics_in_congestion_report(self):
        """Verify congestion report includes per-layer metrics."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify layer-wise congestion metrics are included
        assert "Layer" in script or "layer" in script.lower()
        assert "metal" in script.lower()

    def test_script_documents_global_route_command(self):
        """Verify script documents the global_route command being used."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Script should explicitly mention the command for auditability
        assert "global_route" in script
        assert "congestion_report_file" in script

    def test_script_with_seed_includes_global_route(self):
        """Verify script with fixed seed still includes global routing."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
            openroad_seed=42,
        )

        # Even with fixed seed, global routing should be present
        assert "global_route" in script
        assert "congestion_report" in script

    def test_metrics_json_includes_congestion_fields(self):
        """Verify metrics JSON includes congestion metrics fields."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Verify JSON includes congestion fields
        assert "bins_total" in script
        assert "bins_hot" in script
        assert "hot_ratio" in script
        assert "max_overflow" in script


class TestGlobalRoutingIntegration:
    """Integration tests for global routing flow."""

    def test_complete_flow_documented_in_script(self):
        """Verify complete PD flow is documented in script comments."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="counter",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # The script should document the expected flow
        # Even if commands are commented out, the flow should be clear
        flow_stages = ["synthesis", "floorplan", "placement", "routing", "timing"]

        for stage in flow_stages:
            assert stage in script.lower(), f"Flow stage '{stage}' not documented in script"

    def test_script_handles_die_area_configuration(self):
        """Verify script includes die area configuration."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Script should define die area for floorplanning
        assert "die_area" in script.lower() or "floorplan" in script.lower()

    def test_script_includes_utilization_target(self):
        """Verify script includes utilization target for placement."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Script should specify utilization for placement
        assert "utilization" in script.lower()
