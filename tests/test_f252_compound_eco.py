"""Tests for F252: Support compound ECOs with sequential component application.

Feature steps:
1. Define compound ECO with 3 components
2. Set apply_order: sequential
3. Apply compound ECO
4. Verify component ECOs are applied in order
5. Verify each component completion is logged
6. Verify final metrics reflect all components
"""

import pytest

from src.controller.eco import (
    BufferInsertionECO,
    CompoundECO,
    NoOpECO,
    PlacementDensityECO,
)
from src.controller.types import ECOClass


class TestCompoundECODefinition:
    """Test defining compound ECOs."""

    def test_step_1_define_compound_eco_with_3_components(self) -> None:
        """Step 1: Define compound ECO with 3 components."""
        # Create 3 component ECOs
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.15, buffer_cell="BUF_X2")
        component3 = PlacementDensityECO(target_density=0.75)

        # Create compound ECO
        compound = CompoundECO(
            name="timing_rescue_combo",
            description="Combined aggressive timing fix",
            components=[component1, component2, component3],
        )

        # Verify compound ECO is created
        assert compound.name == "timing_rescue_combo"
        assert len(compound.components) == 3
        assert compound.components[0].name == "noop"
        assert compound.components[1].name == "buffer_insertion"
        assert compound.components[2].name == "placement_density"

    def test_compound_eco_requires_components(self) -> None:
        """Verify compound ECO requires at least one component."""
        with pytest.raises(ValueError, match="requires at least one component"):
            CompoundECO(
                name="empty_compound",
                description="This should fail",
                components=[],
            )

    def test_compound_eco_determines_class_from_components(self) -> None:
        """Verify compound ECO class is determined from most restrictive component."""
        # All TOPOLOGY_NEUTRAL
        compound1 = CompoundECO(
            name="neutral_compound",
            description="All neutral",
            components=[NoOpECO(), NoOpECO()],
        )
        assert compound1.eco_class == ECOClass.TOPOLOGY_NEUTRAL

        # Mix of TOPOLOGY_NEUTRAL and PLACEMENT_LOCAL
        compound2 = CompoundECO(
            name="local_compound",
            description="Contains placement local",
            components=[NoOpECO(), BufferInsertionECO()],
        )
        assert compound2.eco_class == ECOClass.PLACEMENT_LOCAL

        # Mix including ROUTING_AFFECTING
        compound3 = CompoundECO(
            name="routing_compound",
            description="Contains routing affecting",
            components=[NoOpECO(), BufferInsertionECO(), PlacementDensityECO()],
        )
        assert compound3.eco_class == ECOClass.ROUTING_AFFECTING


class TestCompoundECOApplyOrder:
    """Test apply_order configuration."""

    def test_step_2_set_apply_order_sequential(self) -> None:
        """Step 2: Set apply_order: sequential."""
        compound = CompoundECO(
            name="sequential_compound",
            description="Sequential application",
            components=[NoOpECO(), BufferInsertionECO()],
            apply_order="sequential",
        )

        assert compound.metadata.parameters["apply_order"] == "sequential"

    def test_apply_order_defaults_to_sequential(self) -> None:
        """Verify apply_order defaults to sequential."""
        compound = CompoundECO(
            name="default_compound",
            description="Default apply order",
            components=[NoOpECO()],
        )

        assert compound.metadata.parameters["apply_order"] == "sequential"

    def test_invalid_apply_order_raises_error(self) -> None:
        """Verify invalid apply_order raises error."""
        with pytest.raises(ValueError, match="Unsupported apply_order"):
            CompoundECO(
                name="invalid_compound",
                description="Invalid order",
                components=[NoOpECO()],
                apply_order="parallel",  # Not supported yet
            )


class TestCompoundECOApplication:
    """Test applying compound ECOs."""

    def test_step_3_apply_compound_eco(self) -> None:
        """Step 3: Apply compound ECO (generate TCL)."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.2)
        component3 = PlacementDensityECO(target_density=0.7)

        compound = CompoundECO(
            name="test_compound",
            description="Test compound application",
            components=[component1, component2, component3],
        )

        # Generate TCL
        tcl = compound.generate_tcl()

        # Verify TCL is generated
        assert tcl is not None
        assert len(tcl) > 0
        assert "Compound ECO: test_compound" in tcl

    def test_step_4_verify_component_ecos_applied_in_order(self) -> None:
        """Step 4: Verify component ECOs are applied in order."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.2)
        component3 = PlacementDensityECO(target_density=0.7)

        compound = CompoundECO(
            name="ordered_compound",
            description="Test ordering",
            components=[component1, component2, component3],
        )

        tcl = compound.generate_tcl()

        # Find positions of each component in TCL
        noop_pos = tcl.find("# No-op ECO")
        buffer_pos = tcl.find("# Buffer Insertion ECO")
        density_pos = tcl.find("# Placement Density ECO")

        # Verify they appear in order
        assert noop_pos < buffer_pos, "NoOp should come before BufferInsertion"
        assert buffer_pos < density_pos, "BufferInsertion should come before PlacementDensity"

    def test_step_5_verify_each_component_completion_logged(self) -> None:
        """Step 5: Verify each component completion is logged."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = PlacementDensityECO()

        compound = CompoundECO(
            name="logged_compound",
            description="Test logging",
            components=[component1, component2, component3],
        )

        tcl = compound.generate_tcl()

        # Verify starting messages for each component
        assert 'puts "Starting component 1/3: noop"' in tcl
        assert 'puts "Starting component 2/3: buffer_insertion"' in tcl
        assert 'puts "Starting component 3/3: placement_density"' in tcl

        # Verify completion messages for each component
        assert 'puts "Completed component 1/3: noop"' in tcl
        assert 'puts "Completed component 2/3: buffer_insertion"' in tcl
        assert 'puts "Completed component 3/3: placement_density"' in tcl

        # Verify final completion message
        assert "Compound ECO 'logged_compound' complete - all 3 components applied" in tcl

    def test_step_6_verify_final_metrics_reflect_all_components(self) -> None:
        """Step 6: Verify final metrics reflect all components."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.15, buffer_cell="BUF_X2")
        component3 = PlacementDensityECO(target_density=0.75)

        compound = CompoundECO(
            name="metrics_compound",
            description="Test metrics",
            components=[component1, component2, component3],
        )

        # Verify compound tracks all component information
        assert compound.metadata.parameters["component_count"] == 3

        # Verify component names are accessible
        component_names = compound.get_component_names()
        assert component_names == ["noop", "buffer_insertion", "placement_density"]

        # Verify serialization includes all components
        compound_dict = compound.to_dict()
        assert "components" in compound_dict
        assert len(compound_dict["components"]) == 3
        assert compound_dict["component_names"] == ["noop", "buffer_insertion", "placement_density"]


class TestCompoundECOValidation:
    """Test compound ECO validation."""

    def test_validate_parameters_validates_all_components(self) -> None:
        """Verify validate_parameters checks all components."""
        # Valid compound
        compound1 = CompoundECO(
            name="valid_compound",
            description="All valid components",
            components=[NoOpECO(), BufferInsertionECO()],
        )
        assert compound1.validate_parameters() is True

        # Invalid component (bad buffer cell)
        bad_buffer = BufferInsertionECO(max_capacitance=-1.0)  # Invalid negative capacitance
        compound2 = CompoundECO(
            name="invalid_compound",
            description="Contains invalid component",
            components=[NoOpECO(), bad_buffer],
        )
        assert compound2.validate_parameters() is False

    def test_rollback_on_failure_parameter(self) -> None:
        """Test rollback_on_failure parameter."""
        # Valid rollback strategies
        for strategy in ["all", "partial", "none"]:
            compound = CompoundECO(
                name=f"rollback_{strategy}",
                description="Test rollback",
                components=[NoOpECO()],
                rollback_on_failure=strategy,
            )
            assert compound.metadata.parameters["rollback_on_failure"] == strategy
            assert compound.validate_parameters() is True

        # Invalid rollback strategy
        with pytest.raises(ValueError, match="Invalid rollback_on_failure"):
            CompoundECO(
                name="invalid_rollback",
                description="Invalid",
                components=[NoOpECO()],
                rollback_on_failure="invalid",
            )


class TestCompoundECOSerialization:
    """Test compound ECO serialization."""

    def test_to_dict_includes_all_information(self) -> None:
        """Verify to_dict includes complete compound ECO information."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.2, buffer_cell="BUF_X4")

        compound = CompoundECO(
            name="serialized_compound",
            description="Test serialization",
            components=[component1, component2],
            apply_order="sequential",
            rollback_on_failure="all",
        )

        compound_dict = compound.to_dict()

        # Verify base ECO fields
        assert compound_dict["name"] == "serialized_compound"
        assert compound_dict["description"] == "Test serialization"
        assert compound_dict["eco_class"] == ECOClass.PLACEMENT_LOCAL.value

        # Verify compound-specific fields
        assert "components" in compound_dict
        assert len(compound_dict["components"]) == 2
        assert compound_dict["components"][0]["name"] == "noop"
        assert compound_dict["components"][1]["name"] == "buffer_insertion"

        # Verify component names
        assert compound_dict["component_names"] == ["noop", "buffer_insertion"]

        # Verify parameters
        assert compound_dict["parameters"]["apply_order"] == "sequential"
        assert compound_dict["parameters"]["rollback_on_failure"] == "all"
        assert compound_dict["parameters"]["component_count"] == 2


class TestCompoundECOEdgeCases:
    """Test edge cases for compound ECOs."""

    def test_single_component_compound(self) -> None:
        """Test compound ECO with single component."""
        compound = CompoundECO(
            name="single_component",
            description="Single component compound",
            components=[NoOpECO()],
        )

        assert len(compound.components) == 1
        assert compound.validate_parameters() is True

        tcl = compound.generate_tcl()
        assert 'puts "Starting component 1/1: noop"' in tcl
        assert 'puts "Completed component 1/1: noop"' in tcl

    def test_many_components_compound(self) -> None:
        """Test compound ECO with many components."""
        components = [NoOpECO() for _ in range(10)]

        compound = CompoundECO(
            name="many_components",
            description="Many component compound",
            components=components,
        )

        assert len(compound.components) == 10
        assert compound.metadata.parameters["component_count"] == 10

        tcl = compound.generate_tcl()
        assert 'puts "Starting component 1/10: noop"' in tcl
        assert 'puts "Starting component 10/10: noop"' in tcl

    def test_nested_compound_not_supported(self) -> None:
        """Test that compound ECOs cannot contain other compound ECOs (for now)."""
        # This is a design decision - we don't support nested compounds yet
        # This test documents the current behavior
        inner_compound = CompoundECO(
            name="inner",
            description="Inner compound",
            components=[NoOpECO()],
        )

        # This should work (no restriction yet), but TCL generation might be confusing
        outer_compound = CompoundECO(
            name="outer",
            description="Outer compound",
            components=[NoOpECO(), inner_compound],
        )

        # Verify it works for now
        assert len(outer_compound.components) == 2
        tcl = outer_compound.generate_tcl()
        assert "Compound ECO: inner" in tcl  # Inner compound's TCL is included


class TestCompoundECOIntegration:
    """Integration tests for compound ECOs."""

    def test_complete_compound_eco_workflow(self) -> None:
        """Test complete workflow: define, validate, generate TCL."""
        # Step 1: Define components
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.2, buffer_cell="BUF_X2")
        component3 = PlacementDensityECO(target_density=0.75)

        # Step 2: Create compound ECO
        compound = CompoundECO(
            name="complete_workflow",
            description="Complete workflow test",
            components=[component1, component2, component3],
            apply_order="sequential",
            rollback_on_failure="all",
        )

        # Step 3: Validate
        assert compound.validate_parameters() is True

        # Step 4: Generate TCL
        tcl = compound.generate_tcl()

        # Verify TCL structure
        assert "Compound ECO: complete_workflow" in tcl
        assert "Component 1: noop" in tcl
        assert "Component 2: buffer_insertion" in tcl
        assert "Component 3: placement_density" in tcl

        # Verify ordering
        lines = tcl.split("\n")
        component_starts = [
            i for i, line in enumerate(lines) if "Starting component" in line
        ]
        assert len(component_starts) == 3
        assert component_starts[0] < component_starts[1] < component_starts[2]

        # Step 5: Serialize
        compound_dict = compound.to_dict()
        assert compound_dict["name"] == "complete_workflow"
        assert len(compound_dict["components"]) == 3
