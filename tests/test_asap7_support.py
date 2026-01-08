"""Tests for ASAP7 PDK-specific support."""

import tempfile
from pathlib import Path

import pytest

from src.controller.types import ExecutionMode
from src.trial_runner.tcl_generator import (
    generate_asap7_floorplan_site,
    generate_asap7_pin_placement_constraints,
    generate_asap7_routing_constraints,
    generate_pdk_specific_commands,
    generate_trial_script,
    write_trial_script,
)


class TestASAP7RoutingConstraints:
    """Test ASAP7-specific routing layer constraints."""

    def test_asap7_routing_constraints_generated(self):
        """Verify ASAP7 routing constraints are generated."""
        script = generate_asap7_routing_constraints()

        # Verify routing layer constraints are present
        assert "set_routing_layers" in script
        assert "metal2-metal9" in script
        assert "metal6-metal9" in script

    def test_asap7_routing_constraints_include_signal_and_clock(self):
        """Verify ASAP7 routing constraints specify both signal and clock layers."""
        script = generate_asap7_routing_constraints()

        # Verify signal and clock routing layers
        assert "-signal" in script
        assert "-clock" in script

    def test_asap7_routing_constraints_documented(self):
        """Verify ASAP7 routing constraints are documented."""
        script = generate_asap7_routing_constraints()

        # Should include documentation of why constraints are needed
        assert "ASAP7" in script
        assert "routing" in script.lower()


class TestASAP7FloorplanSite:
    """Test ASAP7-specific floorplan site specification."""

    def test_asap7_site_specification_generated(self):
        """Verify ASAP7 site specification is generated."""
        script = generate_asap7_floorplan_site()

        # Verify site name is present
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in script

    def test_asap7_site_assigned_to_variable(self):
        """Verify ASAP7 site is assigned to a variable for reuse."""
        script = generate_asap7_floorplan_site()

        # Verify site is stored in variable
        assert "asap7_site" in script or "site" in script.lower()

    def test_asap7_site_documented(self):
        """Verify ASAP7 site specification is documented."""
        script = generate_asap7_floorplan_site()

        # Should explain why explicit site is needed
        assert "ASAP7" in script
        assert "site" in script.lower()


class TestASAP7PinPlacementConstraints:
    """Test ASAP7-specific pin placement constraints."""

    def test_asap7_pin_constraints_generated(self):
        """Verify ASAP7 pin placement constraints are generated."""
        script = generate_asap7_pin_placement_constraints()

        # Verify pin placement mentions metal4 and metal5
        assert "metal4" in script
        assert "metal5" in script

    def test_asap7_pin_constraints_specify_layers(self):
        """Verify ASAP7 pin constraints specify horizontal and vertical layers."""
        script = generate_asap7_pin_placement_constraints()

        # Verify horizontal and vertical layers specified
        assert "hor_layers" in script or "horizontal" in script.lower()
        assert "ver_layers" in script or "vertical" in script.lower()

    def test_asap7_pin_constraints_documented(self):
        """Verify ASAP7 pin placement constraints are documented."""
        script = generate_asap7_pin_placement_constraints()

        # Should explain pin placement restriction
        assert "ASAP7" in script
        assert "pin" in script.lower()


class TestPDKSpecificCommands:
    """Test PDK-specific command generation."""

    def test_asap7_generates_specific_commands(self):
        """Verify ASAP7 PDK generates all required workarounds."""
        script = generate_pdk_specific_commands("asap7")

        # Verify all ASAP7 workarounds are included
        assert "set_routing_layers" in script
        assert "metal2-metal9" in script
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in script
        assert "metal4" in script
        assert "metal5" in script

    def test_nangate45_generates_no_special_commands(self):
        """Verify Nangate45 PDK does not generate special commands."""
        script = generate_pdk_specific_commands("nangate45")

        # Nangate45 should not require special workarounds
        assert script == "" or script.strip() == ""

    def test_sky130_generates_no_special_commands(self):
        """Verify Sky130 PDK does not generate special commands."""
        script = generate_pdk_specific_commands("sky130")

        # Sky130 should not require special workarounds (currently)
        assert script == "" or script.strip() == ""

    def test_pdk_name_is_case_insensitive(self):
        """Verify PDK name matching is case-insensitive."""
        script_lower = generate_pdk_specific_commands("asap7")
        script_upper = generate_pdk_specific_commands("ASAP7")
        script_mixed = generate_pdk_specific_commands("AsAp7")

        # All should generate the same result
        assert script_lower == script_upper == script_mixed
        assert "set_routing_layers" in script_lower


class TestASAP7ScriptGeneration:
    """Test complete script generation with ASAP7 PDK."""

    def test_asap7_script_includes_routing_constraints(self):
        """Verify ASAP7 script includes routing layer constraints."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Verify ASAP7 routing constraints are present
        assert "set_routing_layers" in script
        assert "metal2-metal9" in script

    def test_asap7_script_includes_site_specification(self):
        """Verify ASAP7 script includes site specification."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Verify ASAP7 site specification is present
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in script

    def test_asap7_script_includes_pin_constraints(self):
        """Verify ASAP7 script includes pin placement constraints."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Verify ASAP7 pin placement constraints are present
        assert "metal4" in script
        assert "metal5" in script

    def test_asap7_script_has_workarounds_section(self):
        """Verify ASAP7 script has dedicated workarounds section."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Verify dedicated ASAP7 workarounds section
        assert "ASAP7" in script
        assert "WORKAROUNDS" in script or "workaround" in script.lower()

    def test_nangate45_script_has_no_asap7_commands(self):
        """Verify Nangate45 script does not include ASAP7-specific commands."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="nangate45",
        )

        # Should NOT have ASAP7-specific site name
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" not in script

    def test_asap7_script_works_with_sta_only_mode(self):
        """Verify ASAP7 constraints work with STA-only mode."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            pdk="asap7",
        )

        # ASAP7 constraints are placement/routing related, so STA-only mode
        # doesn't need them, but shouldn't break either
        assert "test_design" in script

    def test_asap7_script_works_with_fixed_seed(self):
        """Verify ASAP7 constraints work with fixed OpenROAD seed."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
            openroad_seed=42,
        )

        # Both ASAP7 constraints and fixed seed should be present
        assert "set_routing_layers" in script
        assert "set_random_seed 42" in script or "42" in script

    def test_asap7_script_writes_to_file(self):
        """Verify ASAP7 script can be written to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "asap7_test.tcl"

            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test_design",
                pdk="asap7",
            )

            assert script_path.exists()
            content = script_path.read_text()

            # Verify ASAP7 content is in file
            assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in content
            assert "set_routing_layers" in content


class TestASAP7WorkaroundDocumentation:
    """Test that ASAP7 workarounds are properly documented."""

    def test_routing_constraints_explain_purpose(self):
        """Verify routing constraints explain why they're needed."""
        script = generate_asap7_routing_constraints()

        # Should explain the consequence of omitting constraints
        assert "routing" in script.lower()

    def test_site_specification_explains_purpose(self):
        """Verify site specification explains why it's needed."""
        script = generate_asap7_floorplan_site()

        # Should explain site alignment issues
        assert "site" in script.lower()

    def test_pin_constraints_explain_purpose(self):
        """Verify pin constraints explain why they're needed."""
        script = generate_asap7_pin_placement_constraints()

        # Should explain pin access issues
        assert "pin" in script.lower()

    def test_all_asap7_workarounds_are_commented(self):
        """Verify all ASAP7 workarounds include explanatory comments."""
        script = generate_pdk_specific_commands("asap7")

        # Count comment lines (lines starting with #)
        comment_lines = [line for line in script.split("\n") if line.strip().startswith("#")]

        # Should have meaningful comments
        assert len(comment_lines) >= 5, "ASAP7 workarounds should be well-commented"


class TestPDKParameterPropagation:
    """Test that PDK parameter is properly propagated through all functions."""

    def test_generate_trial_script_accepts_pdk_parameter(self):
        """Verify generate_trial_script accepts pdk parameter."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test",
            pdk="asap7",
        )

        assert "set_routing_layers" in script

    def test_write_trial_script_accepts_pdk_parameter(self):
        """Verify write_trial_script accepts pdk parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "test.tcl"

            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test",
                pdk="asap7",
            )

            content = script_path.read_text()
            assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in content

    def test_default_pdk_is_nangate45(self):
        """Verify default PDK is Nangate45 (no special constraints)."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test",
            # pdk parameter omitted, should default to nangate45
        )

        # Should NOT have ASAP7-specific commands
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" not in script
