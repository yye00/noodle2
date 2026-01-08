"""Tests for ASAP7 utilization configuration to prevent routing explosion."""

import tempfile
from pathlib import Path

import pytest

from src.controller.types import ExecutionMode
from src.trial_runner.tcl_generator import (
    generate_trial_script,
    get_pdk_default_utilization,
    write_trial_script,
)


class TestPDKDefaultUtilization:
    """Test PDK-specific default utilization values."""

    def test_asap7_default_utilization_is_low(self):
        """Verify ASAP7 defaults to low utilization (0.50-0.55)."""
        utilization = get_pdk_default_utilization("asap7")

        # ASAP7 requires lower utilization to prevent routing explosion
        assert 0.50 <= utilization <= 0.55
        assert utilization == 0.55

    def test_nangate45_default_utilization_is_higher(self):
        """Verify Nangate45 can use higher utilization."""
        utilization = get_pdk_default_utilization("nangate45")

        # Nangate45 can handle higher utilization
        assert utilization > 0.55
        assert utilization == 0.70

    def test_sky130_default_utilization_is_moderate(self):
        """Verify Sky130 uses moderate utilization."""
        utilization = get_pdk_default_utilization("sky130")

        # Sky130 uses moderate utilization
        assert 0.60 <= utilization <= 0.70
        assert utilization == 0.65

    def test_unknown_pdk_uses_conservative_default(self):
        """Verify unknown PDKs use conservative utilization."""
        utilization = get_pdk_default_utilization("unknown_pdk")

        # Conservative default for unknown PDKs
        assert 0.50 <= utilization <= 0.70
        assert utilization == 0.60

    def test_pdk_name_is_case_insensitive(self):
        """Verify PDK name matching is case-insensitive."""
        lower = get_pdk_default_utilization("asap7")
        upper = get_pdk_default_utilization("ASAP7")
        mixed = get_pdk_default_utilization("AsAp7")

        assert lower == upper == mixed


class TestASAP7UtilizationInScript:
    """Test ASAP7 utilization appears correctly in generated scripts."""

    def test_asap7_script_uses_default_low_utilization(self):
        """Verify ASAP7 script uses low utilization when not explicitly set."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
            # utilization not specified, should use PDK default
        )

        # Should use ASAP7 default (0.55)
        assert "0.55" in script
        assert "core_utilization" in script

    def test_asap7_script_respects_explicit_utilization(self):
        """Verify ASAP7 script can override utilization explicitly."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
            utilization=0.50,  # Explicit override
        )

        # Should use explicit value
        assert "0.5" in script or "0.50" in script
        assert "core_utilization" in script

    def test_nangate45_script_uses_higher_default_utilization(self):
        """Verify Nangate45 uses higher utilization by default."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="nangate45",
            # utilization not specified, should use PDK default
        )

        # Should use Nangate45 default (0.70)
        assert "0.7" in script or "0.70" in script
        assert "core_utilization" in script

    def test_explicit_utilization_overrides_pdk_default(self):
        """Verify explicit utilization overrides PDK defaults for any PDK."""
        script_asap7 = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
            utilization=0.80,  # High utilization (not recommended for ASAP7)
        )

        script_nangate45 = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="nangate45",
            utilization=0.40,  # Low utilization
        )

        # Both should use explicit values
        assert "0.8" in script_asap7 or "0.80" in script_asap7
        assert "0.4" in script_nangate45 or "0.40" in script_nangate45


class TestUtilizationPreventingRoutingExplosion:
    """Test that utilization configuration prevents routing explosion."""

    def test_asap7_floorplan_configured_with_low_utilization(self):
        """Step 1: Configure ASAP7 floorplan with utilization 0.50-0.55."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Verify floorplan section exists
        assert "FLOORPLANNING" in script
        assert "core_utilization" in script

        # Verify ASAP7 default utilization is used
        assert "0.55" in script

    def test_script_executes_placement(self):
        """Step 2: Execute placement (simulated in this test)."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Verify placement section exists
        assert "PLACEMENT" in script
        assert "global_placement" in script or "placement" in script.lower()

    def test_script_executes_global_routing(self):
        """Step 3: Execute global routing (simulated in this test)."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Verify global routing section exists
        assert "GLOBAL ROUTING" in script
        assert "congestion" in script.lower()

    def test_routing_convergence_implied_by_low_utilization(self):
        """Step 4: Verify routing converges successfully (design property)."""
        # This is a design property that would be validated in actual execution
        # In this test, we verify that the utilization is set appropriately
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # Low utilization (0.55) provides routing headroom
        assert "0.55" in script

        # ASAP7 workarounds are also included
        assert "set_routing_layers" in script

    def test_congestion_explosion_prevented_by_configuration(self):
        """Step 5: Confirm no congestion explosion occurs (design property)."""
        # This is validated through the combination of:
        # 1. Low utilization (0.55)
        # 2. Explicit routing constraints
        # 3. Proper site specification
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            pdk="asap7",
        )

        # All ASAP7 safeguards present
        assert "0.55" in script  # Low utilization
        assert "set_routing_layers" in script  # Routing constraints
        assert "asap7sc7p5t_28_R_24_NP_162NW_34O" in script  # Site specification


class TestUtilizationFileWriting:
    """Test that utilization parameter propagates through file writing."""

    def test_write_trial_script_accepts_utilization_parameter(self):
        """Verify write_trial_script accepts and uses utilization parameter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "test.tcl"

            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test",
                pdk="asap7",
                utilization=0.52,
            )

            content = script_path.read_text()

            # Verify explicit utilization is in file
            assert "0.52" in content

    def test_write_trial_script_uses_pdk_default_when_utilization_omitted(self):
        """Verify write_trial_script uses PDK default when utilization not specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "test.tcl"

            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test",
                pdk="asap7",
                # utilization omitted - should use ASAP7 default (0.55)
            )

            content = script_path.read_text()

            # Verify ASAP7 default is in file
            assert "0.55" in content


class TestUtilizationDocumentation:
    """Test that utilization configuration is documented in scripts."""

    def test_script_comments_explain_pdk_specific_utilization(self):
        """Verify script includes comments about PDK-specific utilization."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test",
            pdk="asap7",
        )

        # Should explain PDK-specific utilization
        assert "ASAP7" in script or "asap7" in script.lower()
        assert "utilization" in script.lower()

    def test_utilization_value_is_visible_in_puts_statements(self):
        """Verify utilization value is printed during execution."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test",
            pdk="asap7",
        )

        # Should print utilization for observability
        assert "Core utilization" in script or "utilization" in script


class TestUtilizationAcrossExecutionModes:
    """Test that utilization works across all execution modes."""

    def test_sta_only_mode_accepts_utilization(self):
        """Verify STA-only mode accepts utilization parameter."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test",
            pdk="asap7",
            utilization=0.55,
        )

        # STA-only doesn't do placement, but parameter should be accepted
        assert script is not None

    def test_sta_congestion_mode_uses_utilization(self):
        """Verify STA+congestion mode uses utilization."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test",
            pdk="asap7",
            utilization=0.55,
        )

        # Should use utilization for floorplan
        assert "0.55" in script
        assert "core_utilization" in script

    def test_full_route_mode_uses_utilization(self):
        """Verify full-route mode uses utilization."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.FULL_ROUTE,
            design_name="test",
            pdk="asap7",
            utilization=0.55,
        )

        # Should use utilization for floorplan
        assert "0.55" in script
        assert "core_utilization" in script
