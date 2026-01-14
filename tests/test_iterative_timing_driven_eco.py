"""Tests for IterativeTimingDrivenECO."""

import pytest
from src.controller.eco import (
    IterativeTimingDrivenECO,
    ECOMetadata,
    create_eco,
)
from src.controller.types import ECOClass


class TestIterativeTimingDrivenECO:
    """Test suite for IterativeTimingDrivenECO."""

    def test_create_iterative_timing_driven_eco(self) -> None:
        """Test creating an IterativeTimingDrivenECO instance."""
        eco = IterativeTimingDrivenECO(
            target_density=0.70,
            keep_overflow=0.1,
            max_iterations=10,
            convergence_threshold=0.02,
        )
        
        assert eco.metadata.name == "iterative_timing_driven"
        assert eco.metadata.eco_class == ECOClass.GLOBAL_DISRUPTIVE
        assert eco.metadata.parameters["target_density"] == 0.70
        assert eco.metadata.parameters["keep_overflow"] == 0.1
        assert eco.metadata.parameters["max_iterations"] == 10
        assert eco.metadata.parameters["convergence_threshold"] == 0.02

    def test_iterative_timing_driven_default_parameters(self) -> None:
        """Test default parameter values."""
        eco = IterativeTimingDrivenECO()
        
        assert eco.metadata.parameters["target_density"] == 0.70
        assert eco.metadata.parameters["keep_overflow"] == 0.1
        assert eco.metadata.parameters["max_iterations"] == 10
        assert eco.metadata.parameters["convergence_threshold"] == 0.02

    def test_iterative_timing_driven_generate_tcl(self) -> None:
        """Test Tcl script generation."""
        eco = IterativeTimingDrivenECO(
            target_density=0.65,
            keep_overflow=0.15,
            max_iterations=8,
            convergence_threshold=0.03,
        )
        
        tcl_script = eco.generate_tcl()
        
        # Check key elements are present
        assert "# Iterative Timing-Driven ECO" in tcl_script
        assert "set_wire_rc -signal -layer metal3" in tcl_script
        assert "remove_buffers" in tcl_script
        assert "global_placement -timing_driven -density 0.65" in tcl_script
        assert "detailed_placement" in tcl_script
        assert "estimate_parasitics -placement" in tcl_script
        assert "repair_timing -setup -setup_margin" in tcl_script
        assert "while {" in tcl_script  # Iterative loop
        assert "set converged false" in tcl_script
        assert "Max iterations: 8" in tcl_script
        assert "Convergence threshold: 3.0%" in tcl_script

    def test_iterative_timing_driven_validate_parameters(self) -> None:
        """Test parameter validation."""
        # Valid parameters
        eco = IterativeTimingDrivenECO(
            target_density=0.70,
            keep_overflow=0.1,
            max_iterations=10,
            convergence_threshold=0.02,
        )
        assert eco.validate_parameters() is True
        
        # Invalid density (too high)
        eco_invalid = IterativeTimingDrivenECO(target_density=1.5)
        assert eco_invalid.validate_parameters() is False
        
        # Invalid density (too low)
        eco_invalid = IterativeTimingDrivenECO(target_density=0.0)
        assert eco_invalid.validate_parameters() is False
        
        # Invalid keep_overflow (negative)
        eco_invalid = IterativeTimingDrivenECO(keep_overflow=-0.1)
        assert eco_invalid.validate_parameters() is False
        
        # Invalid max_iterations (too high)
        eco_invalid = IterativeTimingDrivenECO(max_iterations=25)
        assert eco_invalid.validate_parameters() is False
        
        # Invalid convergence_threshold (too high)
        eco_invalid = IterativeTimingDrivenECO(convergence_threshold=0.6)
        assert eco_invalid.validate_parameters() is False

    def test_iterative_timing_driven_tags(self) -> None:
        """Test ECO metadata tags."""
        eco = IterativeTimingDrivenECO()
        
        assert "timing_optimization" in eco.metadata.tags
        assert "placement" in eco.metadata.tags
        assert "timing_driven" in eco.metadata.tags
        assert "iterative" in eco.metadata.tags
        assert "ultra_aggressive" in eco.metadata.tags

    def test_iterative_timing_driven_factory(self) -> None:
        """Test creating via factory function."""
        eco = create_eco(
            "iterative_timing_driven",
            target_density=0.75,
            max_iterations=12,
        )
        
        assert isinstance(eco, IterativeTimingDrivenECO)
        assert eco.metadata.parameters["target_density"] == 0.75
        assert eco.metadata.parameters["max_iterations"] == 12

    def test_iterative_timing_driven_convergence_logic(self) -> None:
        """Test that Tcl script includes proper convergence checking."""
        eco = IterativeTimingDrivenECO(
            max_iterations=5,
            convergence_threshold=0.01,
        )
        
        tcl_script = eco.generate_tcl()
        
        # Verify convergence logic elements
        assert "set prev_wns" in tcl_script
        assert "set curr_wns" in tcl_script
        assert "set improvement_pct" in tcl_script
        assert "if {$improvement_pct < 0.01}" in tcl_script
        assert "Converged" in tcl_script

    def test_iterative_timing_driven_margin_scheduling(self) -> None:
        """Test that repair_timing margins decrease over iterations."""
        eco = IterativeTimingDrivenECO(max_iterations=10)
        
        tcl_script = eco.generate_tcl()
        
        # Verify margin scheduling formula is present
        assert "set margin [expr 0.30 - ($iteration * 0.30 / 10)]" in tcl_script
        assert "repair_timing -setup -setup_margin $margin" in tcl_script
