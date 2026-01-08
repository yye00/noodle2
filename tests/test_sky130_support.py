"""
Tests for Sky130 (sky130A) PDK support in Noodle 2.

Validates that Sky130 base case execution is properly supported, including:
- Sky130 PDK library paths
- Sky130-specific TCL generation
- Sky130 standard cell references in SDC files
- Cross-target parity with Nangate45 (same telemetry schema)
"""

import pytest
from pathlib import Path
from src.trial_runner.tcl_generator import (
    generate_trial_script,
    generate_pdk_library_paths,
    generate_pdk_specific_commands,
)
from src.controller.types import ExecutionMode


class TestSky130PDKLibraryPaths:
    """Test Sky130 PDK library path generation."""

    def test_sky130_library_paths_generated(self):
        """Verify Sky130 library paths are correctly generated."""
        paths = generate_pdk_library_paths("sky130")

        assert "Sky130A" in paths or "sky130A" in paths
        assert "sky130_fd_sc_hd" in paths
        assert "liberty_file" in paths
        assert "tech_lef" in paths
        assert "std_cell_lef" in paths

    def test_sky130_uses_sky130a_variant(self):
        """Verify Sky130 uses sky130A variant as per spec."""
        paths = generate_pdk_library_paths("sky130")

        # App spec specifies sky130A (not sky130B or other variants)
        assert "sky130A" in paths
        assert "/pdk/sky130A/" in paths

    def test_sky130_uses_hd_library(self):
        """Verify Sky130 uses high density (HD) standard cell library."""
        paths = generate_pdk_library_paths("sky130")

        # HD (high density) is the standard library
        assert "sky130_fd_sc_hd" in paths

    def test_sky130_liberty_file_path(self):
        """Verify Sky130 liberty file path is correct."""
        paths = generate_pdk_library_paths("sky130")

        assert ".lib" in paths
        # Typical corner: tt_025C_1v80 (typical temp, typical voltage)
        assert "tt_025C_1v80" in paths or ".lib" in paths

    def test_sky130_tech_lef_path(self):
        """Verify Sky130 technology LEF path is correct."""
        paths = generate_pdk_library_paths("sky130")

        assert "techlef" in paths
        assert ".tlef" in paths or ".lef" in paths

    def test_sky130_std_cell_lef_path(self):
        """Verify Sky130 standard cell LEF path is correct."""
        paths = generate_pdk_library_paths("sky130")

        assert "lef" in paths
        assert "sky130_fd_sc_hd" in paths

    def test_sky130_paths_inside_container(self):
        """Verify Sky130 paths reference container filesystem."""
        paths = generate_pdk_library_paths("sky130")

        # All PDK paths should be inside /pdk directory
        assert "/pdk/sky130A/" in paths


class TestSky130SpecialCommands:
    """Test Sky130 does not require special workarounds like ASAP7."""

    def test_sky130_no_special_workarounds(self):
        """Verify Sky130 does not generate special routing/floorplan workarounds."""
        commands = generate_pdk_specific_commands("sky130")

        # Sky130 should not require ASAP7-style workarounds
        assert "set_routing_layers" not in commands
        assert "initialize_floorplan" not in commands
        assert "place_pins" not in commands
        # Should be empty or minimal
        assert len(commands.strip()) == 0

    def test_sky130_case_insensitive(self):
        """Verify Sky130 PDK name is case-insensitive."""
        paths_lower = generate_pdk_library_paths("sky130")
        paths_upper = generate_pdk_library_paths("Sky130")
        paths_mixed = generate_pdk_library_paths("SKY130")

        # All should produce equivalent paths (case-normalized)
        # After lowercasing, "sky130A" becomes "sky130a"
        assert "sky130a" in paths_lower.lower()
        assert "sky130a" in paths_upper.lower()
        assert "sky130a" in paths_mixed.lower()


class TestSky130TCLGeneration:
    """Test TCL script generation for Sky130 PDK."""

    def test_generate_sky130_sta_congestion_script(self):
        """Verify STA+congestion script is generated for Sky130."""
        script = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
        )

        assert script is not None
        assert len(script) > 0
        assert "sky130" in script.lower() or "SKY130" in script

    def test_sky130_script_includes_library_setup(self):
        """Verify Sky130 script includes library and technology setup."""
        script = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
        )

        # Should reference Sky130 library paths
        assert "liberty_file" in script
        assert "tech_lef" in script
        assert "std_cell_lef" in script
        assert "sky130A" in script or "sky130" in script.lower()

    def test_sky130_script_includes_pdk_header(self):
        """Verify Sky130 script documents PDK in library setup section."""
        script = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
        )

        # Library setup section should mention Sky130
        # Look for the section that sets up library paths
        assert "LIBRARY AND TECHNOLOGY SETUP" in script
        assert ("SKY130" in script or "sky130" in script.lower())

    def test_sky130_different_from_nangate45(self):
        """Verify Sky130 script is different from Nangate45 script."""
        script_sky130 = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
        )

        script_nangate45 = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="nangate45",
        )

        # Scripts should be different (different PDK paths)
        assert script_sky130 != script_nangate45
        assert "sky130" in script_sky130.lower()
        assert "nangate45" in script_nangate45.lower()

    def test_sky130_uses_correct_liberty_path(self):
        """Verify Sky130 script uses correct liberty file path."""
        script = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
        )

        # Should use Sky130A HD library
        assert "/pdk/sky130A/" in script
        assert "sky130_fd_sc_hd" in script
        assert ".lib" in script


class TestSky130BaseCase:
    """Test Sky130 base case directory structure and files."""

    def test_sky130_base_case_directory_exists(self):
        """Verify Sky130 base case directory was created."""
        sky130_base = Path("studies/sky130_base")
        assert sky130_base.exists()
        assert sky130_base.is_dir()

    def test_sky130_counter_design_exists(self):
        """Verify counter.v design file exists for Sky130."""
        counter_v = Path("studies/sky130_base/counter.v")
        assert counter_v.exists()
        assert counter_v.is_file()

    def test_sky130_sdc_file_exists(self):
        """Verify counter.sdc timing constraints file exists."""
        counter_sdc = Path("studies/sky130_base/counter.sdc")
        assert counter_sdc.exists()
        assert counter_sdc.is_file()

    def test_sky130_sdc_uses_sky130_cells(self):
        """Verify SDC file references Sky130 standard cells."""
        counter_sdc = Path("studies/sky130_base/counter.sdc")
        content = counter_sdc.read_text()

        # Should reference Sky130 cells (not Nangate45 cells like BUF_X1)
        assert "sky130_fd_sc_hd" in content
        # Sky130 buffer cell naming convention
        assert "sky130_fd_sc_hd__buf" in content

    def test_sky130_design_is_synthesizable(self):
        """Verify counter.v design is valid Verilog."""
        counter_v = Path("studies/sky130_base/counter.v")
        content = counter_v.read_text()

        # Basic Verilog validation
        assert "module counter" in content
        assert "input" in content
        assert "output" in content
        assert "endmodule" in content

    def test_sky130_sdc_defines_clock(self):
        """Verify SDC file defines clock constraints."""
        counter_sdc = Path("studies/sky130_base/counter.sdc")
        content = counter_sdc.read_text()

        assert "create_clock" in content
        assert "clk" in content
        # Should have reasonable clock period (e.g., 10ns)
        assert "10.0" in content or "period" in content


class TestSky130CrossTargetParity:
    """Test Sky130 maintains cross-target parity with Nangate45/ASAP7."""

    def test_sky130_generates_same_script_structure_as_nangate45(self):
        """Verify Sky130 scripts have same structure as Nangate45."""
        script_sky130 = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
        )

        script_nangate45 = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="nangate45",
        )

        # Both should have same major sections
        for section in ["LIBRARY AND TECHNOLOGY SETUP", "SYNTHESIS", "TIMING ANALYSIS"]:
            assert section in script_sky130
            assert section in script_nangate45

    def test_sky130_supports_all_execution_modes(self):
        """Verify Sky130 supports all execution modes like other PDKs."""
        # STA_ONLY
        script_sta = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_ONLY,
            clock_period_ns=10.0,
            pdk="sky130",
        )
        assert len(script_sta) > 0

        # STA_CONGESTION
        script_congestion = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
        )
        assert len(script_congestion) > 0

        # FULL_ROUTE
        script_full = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.FULL_ROUTE,
            clock_period_ns=10.0,
            pdk="sky130",
        )
        assert len(script_full) > 0

    def test_sky130_script_supports_fixed_seed(self):
        """Verify Sky130 supports deterministic fixed seeds."""
        script = generate_trial_script(
            design_name="counter",
            output_dir="/tmp/test",
            execution_mode=ExecutionMode.STA_CONGESTION,
            clock_period_ns=10.0,
            pdk="sky130",
            openroad_seed=42,
        )

        # Should include seed command
        assert "set_random_seed 42" in script
        assert "42" in script


class TestSky130ContainerPDKIntegration:
    """Test Sky130 PDK integration with efabless/openlane container."""

    def test_sky130_paths_reference_container_pdk_directory(self):
        """Verify Sky130 paths reference /pdk directory in container."""
        paths = generate_pdk_library_paths("sky130")

        # All paths should start with /pdk
        for line in paths.split("\n"):
            if "set " in line and "/" in line:
                assert "/pdk/" in line

    def test_sky130_paths_are_absolute(self):
        """Verify Sky130 paths are absolute (not relative)."""
        paths = generate_pdk_library_paths("sky130")

        # All paths should be absolute (start with /)
        for line in paths.split("\n"):
            if ".lib" in line or ".lef" in line:
                assert line.strip().startswith("set ") or "/" in line
                if '"' in line:
                    # Extract path from quotes
                    import re
                    matches = re.findall(r'"([^"]+)"', line)
                    if matches:
                        path = matches[0]
                        assert path.startswith("/"), f"Path {path} is not absolute"

    def test_sky130_no_host_filesystem_references(self):
        """Verify Sky130 does not reference host filesystem."""
        paths = generate_pdk_library_paths("sky130")

        # Should not reference common host paths
        assert "/home/" not in paths
        assert "/usr/local/" not in paths
        assert "./pdk/" not in paths
        assert "../pdk/" not in paths
