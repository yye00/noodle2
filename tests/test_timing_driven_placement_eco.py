"""Tests for TimingDrivenPlacementECO."""

import pytest

from src.controller.eco import TimingDrivenPlacementECO
from src.controller.types import ECOClass


class TestTimingDrivenPlacementECO:
    """Tests for Timing-Driven Placement ECO."""

    def test_create_timing_driven_placement_eco(self) -> None:
        """Test creating timing-driven placement ECO."""
        eco = TimingDrivenPlacementECO(target_density=0.75, keep_overflow=0.15)
        assert eco.name == "timing_driven_placement"
        assert eco.eco_class == ECOClass.GLOBAL_DISRUPTIVE
        assert eco.metadata.parameters["target_density"] == 0.75
        assert eco.metadata.parameters["keep_overflow"] == 0.15

    def test_timing_driven_placement_default_parameters(self) -> None:
        """Test timing-driven placement with default parameters."""
        eco = TimingDrivenPlacementECO()
        assert eco.metadata.parameters["target_density"] == 0.70
        assert eco.metadata.parameters["keep_overflow"] == 0.1

    def test_timing_driven_placement_generate_tcl(self) -> None:
        """Test timing-driven placement generates valid Tcl."""
        eco = TimingDrivenPlacementECO(target_density=0.65, keep_overflow=0.12)
        tcl = eco.generate_tcl()

        # Check for key components
        assert "Timing-Driven Placement ECO" in tcl
        assert "remove_buffers" in tcl
        assert "global_placement" in tcl
        assert "-timing_driven" in tcl
        assert "-density 0.65" in tcl
        assert "-keep_resize_below_overflow 0.12" in tcl
        assert "detailed_placement" in tcl
        assert "repair_timing" in tcl
        assert "estimate_parasitics" in tcl

        # Verify multi-pass repair_timing
        assert "setup_margin 0.3" in tcl
        assert "setup_margin 0.15" in tcl
        assert "setup_margin 0.05" in tcl
        assert "setup_margin 0.0" in tcl

        # Verify it doesn't call repair_design as a command (timing-focused approach)
        # Check that repair_design is never called (excluding comments and puts statements)
        tcl_commands = [line.strip() for line in tcl.split('\n')
                       if line.strip() and not line.strip().startswith('#') and not line.strip().startswith('puts')]
        repair_design_commands = [line for line in tcl_commands if line.startswith('repair_design')]
        assert len(repair_design_commands) == 0, f"Found repair_design commands: {repair_design_commands}"

    def test_timing_driven_placement_validate_parameters(self) -> None:
        """Test timing-driven placement parameter validation."""
        eco = TimingDrivenPlacementECO(target_density=0.7, keep_overflow=0.1)
        assert eco.validate_parameters() is True

    def test_timing_driven_placement_validate_invalid_density(self) -> None:
        """Test validation rejects invalid density values."""
        # Density too low
        eco = TimingDrivenPlacementECO(target_density=0.0)
        assert eco.validate_parameters() is False

        # Density too high
        eco = TimingDrivenPlacementECO(target_density=1.5)
        assert eco.validate_parameters() is False

        # Negative density
        eco = TimingDrivenPlacementECO(target_density=-0.5)
        assert eco.validate_parameters() is False

    def test_timing_driven_placement_validate_invalid_overflow(self) -> None:
        """Test validation rejects invalid overflow values."""
        # Negative overflow
        eco = TimingDrivenPlacementECO(keep_overflow=-0.1)
        assert eco.validate_parameters() is False

        # Overflow too high
        eco = TimingDrivenPlacementECO(keep_overflow=1.5)
        assert eco.validate_parameters() is False

    def test_timing_driven_placement_tags(self) -> None:
        """Test timing-driven placement has correct tags."""
        eco = TimingDrivenPlacementECO()
        assert "timing_optimization" in eco.metadata.tags
        assert "placement" in eco.metadata.tags
        assert "timing_driven" in eco.metadata.tags
        assert "aggressive" in eco.metadata.tags

    def test_timing_driven_placement_description(self) -> None:
        """Test timing-driven placement has correct description."""
        eco = TimingDrivenPlacementECO()
        assert "timing awareness" in eco.metadata.description.lower()
        assert "critical path" in eco.metadata.description.lower()

    def test_timing_driven_placement_eco_class(self) -> None:
        """Test timing-driven placement has correct ECO class."""
        eco = TimingDrivenPlacementECO()
        assert eco.eco_class == ECOClass.GLOBAL_DISRUPTIVE
        assert eco.metadata.eco_class == ECOClass.GLOBAL_DISRUPTIVE

    def test_timing_driven_placement_version(self) -> None:
        """Test timing-driven placement has version."""
        eco = TimingDrivenPlacementECO()
        assert eco.metadata.version == "1.0"

    def test_timing_driven_placement_tcl_structure(self) -> None:
        """Test generated Tcl has proper structure."""
        eco = TimingDrivenPlacementECO()
        tcl = eco.generate_tcl()

        # Verify structure: wire RC → remove buffers → global_placement → detailed → repair
        lines = [line.strip() for line in tcl.split('\n') if line.strip() and not line.strip().startswith('#')]

        # Check that key commands appear in order
        wire_rc_idx = next(i for i, line in enumerate(lines) if 'set_wire_rc' in line)
        remove_buffers_idx = next(i for i, line in enumerate(lines) if 'remove_buffers' in line)
        global_place_idx = next(i for i, line in enumerate(lines) if 'global_placement' in line)
        detailed_place_idx = next(i for i, line in enumerate(lines) if 'detailed_placement' in line)

        assert wire_rc_idx < remove_buffers_idx
        assert remove_buffers_idx < global_place_idx
        assert global_place_idx < detailed_place_idx

    def test_timing_driven_placement_density_range(self) -> None:
        """Test various valid density values."""
        # Low density (more space, better routability)
        eco_low = TimingDrivenPlacementECO(target_density=0.5)
        assert eco_low.validate_parameters() is True
        tcl_low = eco_low.generate_tcl()
        assert "-density 0.5" in tcl_low

        # Medium density (balanced)
        eco_med = TimingDrivenPlacementECO(target_density=0.7)
        assert eco_med.validate_parameters() is True

        # High density (tighter packing)
        eco_high = TimingDrivenPlacementECO(target_density=0.9)
        assert eco_high.validate_parameters() is True
        tcl_high = eco_high.generate_tcl()
        assert "-density 0.9" in tcl_high

    def test_timing_driven_placement_for_extreme_violations(self) -> None:
        """Test that ECO is suitable for extreme timing violations."""
        eco = TimingDrivenPlacementECO()

        # Verify it's tagged as aggressive
        assert "aggressive" in eco.metadata.tags

        # Verify TCL includes re-placement (not just local fixes)
        tcl = eco.generate_tcl()
        assert "remove_buffers" in tcl
        assert "global_placement" in tcl

        # Verify comments mention extreme violations
        assert "extreme" in tcl.lower()
