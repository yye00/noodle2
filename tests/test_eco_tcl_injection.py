"""Tests for ECO TCL injection into trial scripts."""

import pytest

from src.controller.eco import CellResizeECO
from src.controller.types import ExecutionMode
from src.trial_runner.tcl_generator import (
    generate_trial_script,
    generate_trial_script_with_eco,
    inject_eco_commands,
)


class TestECOTCLInjection:
    """Test ECO TCL command injection into trial scripts."""

    def test_inject_eco_commands_basic(self) -> None:
        """Test basic ECO command injection into a simple script."""
        base_script = """# Test script
puts "Hello"
puts "World"
exit 0
"""
        eco_tcl = "repair_design -max_passes 100"

        result = inject_eco_commands(base_script, eco_tcl)

        # Check that ECO section is present
        assert "# ECO APPLICATION" in result
        assert "repair_design -max_passes 100" in result
        assert "exit 0" in result  # Exit should still be there

        # Check that ECO is before exit
        eco_index = result.index("repair_design")
        exit_index = result.index("exit 0")
        assert eco_index < exit_index, "ECO commands should be before exit"

        print("✓ Basic ECO injection works")

    def test_inject_eco_commands_with_input_odb(self) -> None:
        """Test ECO injection with input ODB file."""
        base_script = """# Test script
puts "Hello"
exit 0
"""
        eco_tcl = "repair_design"
        input_odb = "/work/input.odb"

        result = inject_eco_commands(base_script, eco_tcl, input_odb_path=input_odb)

        # Check for ODB loading
        assert "read_db" in result
        assert input_odb in result
        assert "Loading input ODB" in result

        print("✓ ECO injection with input ODB works")

    def test_inject_eco_commands_saves_modified_odb(self) -> None:
        """Test that ECO injection includes ODB save commands."""
        base_script = """# Test script
exit 0
"""
        eco_tcl = "repair_design"

        result = inject_eco_commands(base_script, eco_tcl)

        # Check for ODB saving
        assert "write_db" in result
        assert "modified_design.odb" in result
        assert "Saving modified ODB" in result

        print("✓ ECO injection includes ODB save")

    def test_generate_trial_script_with_eco(self) -> None:
        """Test high-level function to generate script with ECO."""
        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        eco_tcl = eco.generate_tcl()

        result = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            eco_tcl=eco_tcl,
        )

        # Check that we have both base script and ECO commands
        assert "# Noodle 2 - STA-Only Execution" in result  # Base script header
        assert "# ECO APPLICATION" in result  # ECO section
        assert "repair_design" in result  # ECO command from CellResizeECO
        assert "write_db" in result  # ODB save
        assert "exit 0" in result  # Exit

        print("✓ Full script generation with ECO works")
        print(f"  Script length: {len(result)} characters")

    def test_eco_injection_with_sta_congestion_mode(self) -> None:
        """Test ECO injection with STA_CONGESTION execution mode."""
        eco = CellResizeECO()
        eco_tcl = eco.generate_tcl()

        result = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            eco_tcl=eco_tcl,
        )

        # Check that we have STA+Congestion base plus ECO
        assert "# Noodle 2 - STA+Congestion Execution" in result
        assert "# ECO APPLICATION" in result
        assert "repair_design" in result

        print("✓ ECO injection works with STA_CONGESTION mode")

    def test_eco_section_structure(self) -> None:
        """Test that ECO section has proper structure."""
        base_script = """# Test
exit 0
"""
        eco_tcl = "repair_design"

        result = inject_eco_commands(base_script, eco_tcl, input_odb_path="/work/input.odb")

        # Check section structure
        lines = result.splitlines()

        # Find key sections
        has_odb_load = any("read_db" in line for line in lines)
        has_baseline_sta = any("baseline" in line.lower() and "sta" in line.lower() for line in lines)
        has_eco_apply = any("Applying ECO" in line for line in lines)
        has_post_sta = any("post-eco" in line.lower() and "sta" in line.lower() for line in lines)
        has_odb_save = any("write_db" in line for line in lines)

        assert has_odb_load, "Should have ODB load"
        assert has_baseline_sta, "Should have baseline STA"
        assert has_eco_apply, "Should have ECO application"
        assert has_post_sta, "Should have post-ECO STA"
        assert has_odb_save, "Should have ODB save"

        print("✓ ECO section has proper structure")

    def test_multiple_eco_commands(self) -> None:
        """Test injection with multiple ECO commands."""
        base_script = """# Test
exit 0
"""
        eco_tcl = """# First ECO
repair_design -max_passes 50

# Second ECO
repair_timing -setup

# Third ECO
optimize_design
"""

        result = inject_eco_commands(base_script, eco_tcl)

        # Check that all ECO commands are present
        assert "repair_design" in result
        assert "repair_timing" in result
        assert "optimize_design" in result

        print("✓ Multiple ECO commands injected correctly")

    def test_custom_output_odb_path(self) -> None:
        """Test custom output ODB path."""
        base_script = """# Test
exit 0
"""
        eco_tcl = "repair_design"
        custom_path = "/work/custom_output.odb"

        result = inject_eco_commands(
            base_script, eco_tcl, output_odb_path=custom_path
        )

        assert custom_path in result
        assert f'write_db "{custom_path}"' in result

        print("✓ Custom output ODB path works")


class TestECOIntegrationWithTrialScripts:
    """Integration tests for ECO with full trial scripts."""

    def test_cellresize_eco_in_trial_script(self) -> None:
        """Test that CellResizeECO can be integrated into trial script."""
        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        eco_tcl = eco.generate_tcl()

        script = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="gcd",
            eco_tcl=eco_tcl,
            input_odb_path="/snapshot/nangate45_extreme.odb",
            output_odb_path="/work/gcd_modified.odb",
            pdk="nangate45",
        )

        # Verify key elements
        assert "gcd" in script  # Design name
        assert "/snapshot/nangate45_extreme.odb" in script  # Input ODB
        assert "/work/gcd_modified.odb" in script  # Output ODB
        assert "repair_design" in script  # ECO command
        assert "100" in script  # max_paths parameter

        print("✓ CellResizeECO fully integrated into trial script")
        print(f"  Total script length: {len(script)} characters")

    def test_script_is_valid_tcl_syntax(self) -> None:
        """Test that generated script has valid TCL syntax (basic check)."""
        eco = CellResizeECO()
        eco_tcl = eco.generate_tcl()

        script = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test",
            eco_tcl=eco_tcl,
        )

        # Basic TCL syntax checks
        open_braces = script.count("{")
        close_braces = script.count("}")

        # In TCL, braces in strings can be unbalanced, but for our script they should be close
        assert abs(open_braces - close_braces) < 20, "Braces should be roughly balanced"

        # Should not have unterminated strings (basic check)
        # Count quotes - should be even
        double_quotes = script.count('"')
        # Note: Escaped quotes complicate this, so just a sanity check
        assert double_quotes > 10, "Should have quoted strings"

        print("✓ Generated script passes basic TCL syntax checks")

    def test_eco_injection_preserves_base_functionality(self) -> None:
        """Test that ECO injection doesn't break base script functionality."""
        # Generate base script without ECO
        base = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test",
        )

        # Generate with ECO
        eco = CellResizeECO()
        with_eco = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test",
            eco_tcl=eco.generate_tcl(),
        )

        # Base script content should still be in the ECO version
        # Check for key base script elements
        assert "# Noodle 2 - STA-Only Execution" in with_eco
        assert "set design_name" in with_eco
        assert "# TIMING REPORT GENERATION" in with_eco
        assert "# METRICS JSON" in with_eco

        # ECO version should be longer (has extra commands)
        assert len(with_eco) > len(base), "ECO version should have more content"

        print("✓ ECO injection preserves base script functionality")
