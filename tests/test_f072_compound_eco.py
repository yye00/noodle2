"""Tests for F072: Compound ECO can combine multiple ECOs into single unit.

Feature steps:
1. Define compound ECO with 2+ component ECOs
2. Set apply_order: sequential
3. Generate TCL
4. Verify TCL contains all component ECOs in correct order
5. Verify eco_class is inherited from most restrictive component
"""

import pytest

from src.controller.eco import (
    BufferInsertionECO,
    CellResizeECO,
    CompoundECO,
    NoOpECO,
    PlacementDensityECO,
)
from src.controller.types import ECOClass


class TestF072CompoundECO:
    """Test F072: Compound ECO can combine multiple ECOs into single unit."""

    def test_step_1_define_compound_eco_with_2_plus_component_ecos(self) -> None:
        """Step 1: Define compound ECO with 2+ component ECOs."""
        # Create 2 component ECOs (minimum required)
        component1 = BufferInsertionECO(max_capacitance=0.2, buffer_cell="BUF_X4")
        component2 = CellResizeECO(size_multiplier=1.5, max_paths=50)

        # Create compound ECO
        compound = CompoundECO(
            name="timing_rescue_combo",
            description="Combined aggressive timing fix",
            components=[component1, component2],
        )

        # Verify compound ECO is created with 2+ components
        assert compound.name == "timing_rescue_combo"
        assert len(compound.components) >= 2
        assert compound.components[0].name == "buffer_insertion"
        assert compound.components[1].name == "cell_resize"

    def test_step_1_define_compound_eco_with_3_components(self) -> None:
        """Step 1: Define compound ECO with 3 component ECOs."""
        # Create 3 component ECOs
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.15)
        component3 = PlacementDensityECO(target_density=0.7)

        # Create compound ECO
        compound = CompoundECO(
            name="three_component_combo",
            description="Three component timing and congestion fix",
            components=[component1, component2, component3],
        )

        # Verify compound ECO is created
        assert len(compound.components) == 3
        assert compound.components[0].name == "noop"
        assert compound.components[1].name == "buffer_insertion"
        assert compound.components[2].name == "placement_density"

    def test_step_2_set_apply_order_sequential(self) -> None:
        """Step 2: Set apply_order: sequential."""
        component1 = BufferInsertionECO()
        component2 = CellResizeECO()

        compound = CompoundECO(
            name="sequential_compound",
            description="Sequential application of ECOs",
            components=[component1, component2],
            apply_order="sequential",
        )

        # Verify apply_order is set to sequential
        assert compound.metadata.parameters["apply_order"] == "sequential"

    def test_step_3_generate_tcl(self) -> None:
        """Step 3: Generate TCL."""
        component1 = BufferInsertionECO(max_capacitance=0.2, buffer_cell="BUF_X4")
        component2 = CellResizeECO(size_multiplier=1.3, max_paths=20)

        compound = CompoundECO(
            name="test_compound",
            description="Test TCL generation",
            components=[component1, component2],
            apply_order="sequential",
        )

        # Generate TCL
        tcl = compound.generate_tcl()

        # Verify TCL is generated
        assert tcl is not None
        assert isinstance(tcl, str)
        assert len(tcl) > 0
        assert "Compound ECO: test_compound" in tcl

    def test_step_4_verify_tcl_contains_all_component_ecos_in_correct_order(self) -> None:
        """Step 4: Verify TCL contains all component ECOs in correct order."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.2)
        component3 = PlacementDensityECO(target_density=0.7)

        compound = CompoundECO(
            name="ordered_compound",
            description="Test ordering",
            components=[component1, component2, component3],
            apply_order="sequential",
        )

        tcl = compound.generate_tcl()

        # Verify TCL contains all components
        assert "# No-op ECO" in tcl
        assert "# Buffer Insertion ECO" in tcl
        assert "# Placement Density ECO" in tcl

        # Verify components appear in correct order
        noop_pos = tcl.find("# No-op ECO")
        buffer_pos = tcl.find("# Buffer Insertion ECO")
        density_pos = tcl.find("# Placement Density ECO")

        assert noop_pos < buffer_pos, "NoOp ECO should come before Buffer Insertion ECO"
        assert buffer_pos < density_pos, "Buffer Insertion ECO should come before Placement Density ECO"

        # Verify component start/completion logging
        assert 'puts "Starting component 1/3: noop"' in tcl
        assert 'puts "Starting component 2/3: buffer_insertion"' in tcl
        assert 'puts "Starting component 3/3: placement_density"' in tcl
        assert 'puts "Completed component 1/3: noop"' in tcl
        assert 'puts "Completed component 2/3: buffer_insertion"' in tcl
        assert 'puts "Completed component 3/3: placement_density"' in tcl

    def test_step_5_verify_eco_class_inherited_from_most_restrictive_component(self) -> None:
        """Step 5: Verify eco_class is inherited from most restrictive component."""
        # Test 1: All TOPOLOGY_NEUTRAL -> Result should be TOPOLOGY_NEUTRAL
        compound1 = CompoundECO(
            name="all_neutral",
            description="All neutral components",
            components=[NoOpECO(), NoOpECO()],
        )
        assert compound1.eco_class == ECOClass.TOPOLOGY_NEUTRAL

        # Test 2: TOPOLOGY_NEUTRAL + PLACEMENT_LOCAL -> Result should be PLACEMENT_LOCAL
        compound2 = CompoundECO(
            name="with_placement_local",
            description="Contains placement local",
            components=[NoOpECO(), BufferInsertionECO()],
        )
        assert compound2.eco_class == ECOClass.PLACEMENT_LOCAL

        # Test 3: TOPOLOGY_NEUTRAL + PLACEMENT_LOCAL + ROUTING_AFFECTING -> Result should be ROUTING_AFFECTING
        compound3 = CompoundECO(
            name="with_routing_affecting",
            description="Contains routing affecting",
            components=[NoOpECO(), BufferInsertionECO(), PlacementDensityECO()],
        )
        assert compound3.eco_class == ECOClass.ROUTING_AFFECTING

        # Test 4: Order should not matter - most restrictive should win
        compound4 = CompoundECO(
            name="routing_first",
            description="Routing affecting first",
            components=[PlacementDensityECO(), NoOpECO(), BufferInsertionECO()],
        )
        assert compound4.eco_class == ECOClass.ROUTING_AFFECTING

        # Test 5: Multiple PLACEMENT_LOCAL -> Result should be PLACEMENT_LOCAL
        compound5 = CompoundECO(
            name="multiple_placement",
            description="Multiple placement local",
            components=[BufferInsertionECO(), CellResizeECO()],
        )
        assert compound5.eco_class == ECOClass.PLACEMENT_LOCAL


class TestF072CompoundECOValidation:
    """Additional validation tests for F072."""

    def test_compound_eco_requires_at_least_one_component(self) -> None:
        """Verify compound ECO requires at least one component."""
        with pytest.raises(ValueError, match="requires at least one component"):
            CompoundECO(
                name="empty_compound",
                description="Should fail",
                components=[],
            )

    def test_compound_eco_validates_apply_order(self) -> None:
        """Verify compound ECO validates apply_order parameter."""
        # Valid: sequential
        compound = CompoundECO(
            name="valid_order",
            description="Valid",
            components=[NoOpECO()],
            apply_order="sequential",
        )
        assert compound.validate_parameters() is True

        # Invalid: unsupported order
        with pytest.raises(ValueError, match="Unsupported apply_order"):
            CompoundECO(
                name="invalid_order",
                description="Invalid",
                components=[NoOpECO()],
                apply_order="parallel",
            )

    def test_compound_eco_validate_parameters_checks_all_components(self) -> None:
        """Verify validate_parameters checks all component ECOs."""
        # Valid compound with valid components
        compound1 = CompoundECO(
            name="valid_compound",
            description="All components valid",
            components=[NoOpECO(), BufferInsertionECO(max_capacitance=0.2)],
        )
        assert compound1.validate_parameters() is True

        # Invalid compound with invalid component
        bad_buffer = BufferInsertionECO(max_capacitance=-1.0)  # Invalid: negative capacitance
        compound2 = CompoundECO(
            name="invalid_compound",
            description="Contains invalid component",
            components=[NoOpECO(), bad_buffer],
        )
        assert compound2.validate_parameters() is False


class TestF072CompoundECOIntegration:
    """Integration tests for F072."""

    def test_complete_compound_eco_workflow(self) -> None:
        """Test complete workflow: define, validate, generate TCL, verify."""
        # Step 1: Define compound ECO with 2+ components
        component1 = BufferInsertionECO(max_capacitance=0.2, buffer_cell="BUF_X4")
        component2 = CellResizeECO(size_multiplier=1.3, max_paths=20)

        compound = CompoundECO(
            name="timing_rescue_combo",
            description="Combined aggressive timing fix",
            components=[component1, component2],
        )

        # Verify at least 2 components
        assert len(compound.components) >= 2

        # Step 2: Set apply_order: sequential
        assert compound.metadata.parameters["apply_order"] == "sequential"

        # Validate
        assert compound.validate_parameters() is True

        # Step 3: Generate TCL
        tcl = compound.generate_tcl()
        assert tcl is not None
        assert len(tcl) > 0

        # Step 4: Verify TCL contains all component ECOs in correct order
        assert "# Buffer Insertion ECO" in tcl
        assert "# Cell Resize ECO" in tcl

        buffer_pos = tcl.find("# Buffer Insertion ECO")
        resize_pos = tcl.find("# Cell Resize ECO")
        assert buffer_pos < resize_pos

        # Step 5: Verify eco_class is inherited from most restrictive component
        # Both components are PLACEMENT_LOCAL, so compound should be PLACEMENT_LOCAL
        assert compound.eco_class == ECOClass.PLACEMENT_LOCAL

    def test_compound_eco_serialization(self) -> None:
        """Test compound ECO can be serialized to dict."""
        component1 = BufferInsertionECO()
        component2 = CellResizeECO()

        compound = CompoundECO(
            name="serializable_compound",
            description="Test serialization",
            components=[component1, component2],
        )

        compound_dict = compound.to_dict()

        # Verify base fields
        assert compound_dict["name"] == "serializable_compound"
        assert compound_dict["description"] == "Test serialization"
        assert compound_dict["eco_class"] == ECOClass.PLACEMENT_LOCAL.value

        # Verify compound-specific fields
        assert "components" in compound_dict
        assert len(compound_dict["components"]) == 2
        assert compound_dict["component_names"] == ["buffer_insertion", "cell_resize"]
        assert compound_dict["parameters"]["apply_order"] == "sequential"
        assert compound_dict["parameters"]["component_count"] == 2

    def test_compound_eco_with_many_components(self) -> None:
        """Test compound ECO with many components."""
        components = [
            NoOpECO(),
            BufferInsertionECO(max_capacitance=0.2),
            CellResizeECO(size_multiplier=1.5),
            PlacementDensityECO(target_density=0.7),
            BufferInsertionECO(max_capacitance=0.15),
        ]

        compound = CompoundECO(
            name="many_component_compound",
            description="Many components",
            components=components,
        )

        # Verify all components are present
        assert len(compound.components) == 5
        assert compound.metadata.parameters["component_count"] == 5

        # Generate TCL and verify all components are present
        tcl = compound.generate_tcl()
        assert 'puts "Starting component 1/5: noop"' in tcl
        assert 'puts "Starting component 2/5: buffer_insertion"' in tcl
        assert 'puts "Starting component 3/5: cell_resize"' in tcl
        assert 'puts "Starting component 4/5: placement_density"' in tcl
        assert 'puts "Starting component 5/5: buffer_insertion"' in tcl

        # Verify eco_class is ROUTING_AFFECTING (most restrictive)
        assert compound.eco_class == ECOClass.ROUTING_AFFECTING
