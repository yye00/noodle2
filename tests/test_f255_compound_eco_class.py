"""Tests for F255: Compound ECO inherits most restrictive component ECO class.

Feature steps:
1. Define compound ECO with components of different classes
2. Include one routing_affecting component
3. Verify compound ECO class is routing_affecting
4. Apply in locked safety domain
5. Verify compound ECO is rejected (routing_affecting not allowed in locked)
"""

import pytest

from src.controller.eco import (
    BufferInsertionECO,
    CompoundECO,
    NoOpECO,
    PlacementDensityECO,
)
from src.controller.safety import SAFETY_POLICY
from src.controller.types import ECOClass, SafetyDomain


def is_eco_class_allowed(safety_domain: SafetyDomain, eco_class: ECOClass) -> bool:
    """Check if ECO class is allowed in safety domain."""
    allowed_classes = SAFETY_POLICY.get(safety_domain, [])
    return eco_class in allowed_classes


class TestCompoundECOClassInheritance:
    """Test compound ECO class inheritance from components."""

    def test_step_1_define_compound_eco_with_different_classes(self) -> None:
        """Step 1: Define compound ECO with components of different classes."""
        # Create components with different ECO classes
        component1 = NoOpECO()  # TOPOLOGY_NEUTRAL
        component2 = BufferInsertionECO()  # PLACEMENT_LOCAL
        component3 = PlacementDensityECO()  # ROUTING_AFFECTING

        # Verify different classes
        assert component1.eco_class == ECOClass.TOPOLOGY_NEUTRAL
        assert component2.eco_class == ECOClass.PLACEMENT_LOCAL
        assert component3.eco_class == ECOClass.ROUTING_AFFECTING

        # Create compound ECO
        compound = CompoundECO(
            name="mixed_class_compound",
            description="Mix of different ECO classes",
            components=[component1, component2, component3],
        )

        # Verify compound is created
        assert compound is not None
        assert len(compound.components) == 3

    def test_step_2_include_routing_affecting_component(self) -> None:
        """Step 2: Include one routing_affecting component."""
        # Create compound with one routing_affecting component
        component1 = NoOpECO()  # TOPOLOGY_NEUTRAL
        component2 = BufferInsertionECO()  # PLACEMENT_LOCAL
        component3 = PlacementDensityECO()  # ROUTING_AFFECTING

        compound = CompoundECO(
            name="routing_affecting_compound",
            description="Contains routing affecting component",
            components=[component1, component2, component3],
        )

        # Verify one component is routing_affecting
        eco_classes = [c.eco_class for c in compound.components]
        assert ECOClass.ROUTING_AFFECTING in eco_classes

    def test_step_3_verify_compound_class_is_routing_affecting(self) -> None:
        """Step 3: Verify compound ECO class is routing_affecting."""
        # Create compound with routing_affecting component
        component1 = NoOpECO()  # TOPOLOGY_NEUTRAL
        component2 = BufferInsertionECO()  # PLACEMENT_LOCAL
        component3 = PlacementDensityECO()  # ROUTING_AFFECTING

        compound = CompoundECO(
            name="routing_compound",
            description="Should inherit routing_affecting",
            components=[component1, component2, component3],
        )

        # Verify compound ECO class is routing_affecting (most restrictive)
        assert compound.eco_class == ECOClass.ROUTING_AFFECTING

    def test_compound_inherits_most_restrictive_class(self) -> None:
        """Verify compound always inherits most restrictive class."""
        # Test 1: All TOPOLOGY_NEUTRAL -> TOPOLOGY_NEUTRAL
        compound1 = CompoundECO(
            name="all_neutral",
            description="All topology neutral",
            components=[NoOpECO(), NoOpECO()],
        )
        assert compound1.eco_class == ECOClass.TOPOLOGY_NEUTRAL

        # Test 2: TOPOLOGY_NEUTRAL + PLACEMENT_LOCAL -> PLACEMENT_LOCAL
        compound2 = CompoundECO(
            name="neutral_and_local",
            description="Neutral and local",
            components=[NoOpECO(), BufferInsertionECO()],
        )
        assert compound2.eco_class == ECOClass.PLACEMENT_LOCAL

        # Test 3: TOPOLOGY_NEUTRAL + PLACEMENT_LOCAL + ROUTING_AFFECTING -> ROUTING_AFFECTING
        compound3 = CompoundECO(
            name="mixed_restrictive",
            description="Mixed with routing affecting",
            components=[NoOpECO(), BufferInsertionECO(), PlacementDensityECO()],
        )
        assert compound3.eco_class == ECOClass.ROUTING_AFFECTING

        # Test 4: Order doesn't matter
        compound4 = CompoundECO(
            name="reverse_order",
            description="Reverse order",
            components=[PlacementDensityECO(), BufferInsertionECO(), NoOpECO()],
        )
        assert compound4.eco_class == ECOClass.ROUTING_AFFECTING


class TestCompoundECOSafetyDomain:
    """Test compound ECO safety domain validation."""

    def test_step_4_and_5_routing_affecting_rejected_in_locked(self) -> None:
        """Steps 4-5: Apply in locked domain, verify routing_affecting rejected."""
        # Create compound with routing_affecting class
        component1 = NoOpECO()  # TOPOLOGY_NEUTRAL
        component2 = BufferInsertionECO()  # PLACEMENT_LOCAL
        component3 = PlacementDensityECO()  # ROUTING_AFFECTING

        compound = CompoundECO(
            name="routing_compound",
            description="Routing affecting compound",
            components=[component1, component2, component3],
        )

        # Verify compound is routing_affecting
        assert compound.eco_class == ECOClass.ROUTING_AFFECTING

        # Check if allowed in LOCKED domain
        allowed_in_locked = is_eco_class_allowed(
            SafetyDomain.LOCKED,
            compound.eco_class
        )

        # Verify routing_affecting is NOT allowed in locked domain
        assert allowed_in_locked is False

    def test_routing_affecting_allowed_in_other_domains(self) -> None:
        """Verify routing_affecting is allowed in SANDBOX and GUARDED."""
        compound = CompoundECO(
            name="routing_compound",
            description="Routing affecting compound",
            components=[NoOpECO(), BufferInsertionECO(), PlacementDensityECO()],
        )

        assert compound.eco_class == ECOClass.ROUTING_AFFECTING

        # Should be allowed in SANDBOX
        assert is_eco_class_allowed(SafetyDomain.SANDBOX, compound.eco_class) is True

        # Should be allowed in GUARDED
        assert is_eco_class_allowed(SafetyDomain.GUARDED, compound.eco_class) is True

        # Should NOT be allowed in LOCKED
        assert is_eco_class_allowed(SafetyDomain.LOCKED, compound.eco_class) is False

    def test_less_restrictive_compound_allowed_in_locked(self) -> None:
        """Verify compound with only neutral/local components allowed in locked."""
        # Compound with only TOPOLOGY_NEUTRAL and PLACEMENT_LOCAL
        compound = CompoundECO(
            name="safe_compound",
            description="Only safe components",
            components=[NoOpECO(), BufferInsertionECO()],
        )

        # Should inherit PLACEMENT_LOCAL (most restrictive of the two)
        assert compound.eco_class == ECOClass.PLACEMENT_LOCAL

        # Should be allowed in LOCKED domain
        assert is_eco_class_allowed(SafetyDomain.LOCKED, compound.eco_class) is True

    def test_topology_neutral_compound_allowed_everywhere(self) -> None:
        """Verify all-neutral compound allowed in all domains."""
        compound = CompoundECO(
            name="neutral_compound",
            description="All topology neutral",
            components=[NoOpECO(), NoOpECO()],
        )

        assert compound.eco_class == ECOClass.TOPOLOGY_NEUTRAL

        # Should be allowed in all domains
        assert is_eco_class_allowed(SafetyDomain.SANDBOX, compound.eco_class) is True
        assert is_eco_class_allowed(SafetyDomain.GUARDED, compound.eco_class) is True
        assert is_eco_class_allowed(SafetyDomain.LOCKED, compound.eco_class) is True


class TestCompoundECOClassHierarchy:
    """Test ECO class hierarchy for compound ECOs."""

    def test_eco_class_hierarchy(self) -> None:
        """Verify ECO class hierarchy: GLOBAL > ROUTING > PLACEMENT > TOPOLOGY."""
        # Note: We don't have GLOBAL_DISRUPTIVE ECOs in the standard set,
        # but the hierarchy should still be tested

        # Test progression from least to most restrictive
        neutral = NoOpECO()
        assert neutral.eco_class == ECOClass.TOPOLOGY_NEUTRAL

        local = BufferInsertionECO()
        assert local.eco_class == ECOClass.PLACEMENT_LOCAL

        routing = PlacementDensityECO()
        assert routing.eco_class == ECOClass.ROUTING_AFFECTING

        # Compound should always pick the most restrictive
        compound1 = CompoundECO(
            name="test1",
            description="Test",
            components=[neutral, local],
        )
        assert compound1.eco_class == ECOClass.PLACEMENT_LOCAL

        compound2 = CompoundECO(
            name="test2",
            description="Test",
            components=[neutral, routing],
        )
        assert compound2.eco_class == ECOClass.ROUTING_AFFECTING

        compound3 = CompoundECO(
            name="test3",
            description="Test",
            components=[local, routing],
        )
        assert compound3.eco_class == ECOClass.ROUTING_AFFECTING

    def test_multiple_routing_affecting_components(self) -> None:
        """Verify multiple routing_affecting components still results in routing_affecting."""
        compound = CompoundECO(
            name="multi_routing",
            description="Multiple routing affecting",
            components=[
                PlacementDensityECO(target_density=0.7),
                PlacementDensityECO(target_density=0.8),
                PlacementDensityECO(target_density=0.9),
            ],
        )

        assert compound.eco_class == ECOClass.ROUTING_AFFECTING

    def test_single_component_compound_inherits_class(self) -> None:
        """Verify single-component compound inherits that component's class."""
        # Single neutral component
        compound1 = CompoundECO(
            name="single_neutral",
            description="Single neutral",
            components=[NoOpECO()],
        )
        assert compound1.eco_class == ECOClass.TOPOLOGY_NEUTRAL

        # Single local component
        compound2 = CompoundECO(
            name="single_local",
            description="Single local",
            components=[BufferInsertionECO()],
        )
        assert compound2.eco_class == ECOClass.PLACEMENT_LOCAL

        # Single routing component
        compound3 = CompoundECO(
            name="single_routing",
            description="Single routing",
            components=[PlacementDensityECO()],
        )
        assert compound3.eco_class == ECOClass.ROUTING_AFFECTING


class TestCompoundECOClassSerialization:
    """Test compound ECO class is properly serialized."""

    def test_compound_eco_class_in_dict(self) -> None:
        """Verify compound ECO class is included in to_dict()."""
        compound = CompoundECO(
            name="test_compound",
            description="Test serialization",
            components=[NoOpECO(), BufferInsertionECO(), PlacementDensityECO()],
        )

        compound_dict = compound.to_dict()

        # Verify eco_class is in the dict
        assert "eco_class" in compound_dict
        assert compound_dict["eco_class"] == ECOClass.ROUTING_AFFECTING.value

    def test_compound_eco_class_matches_metadata(self) -> None:
        """Verify compound ECO class matches metadata.eco_class."""
        compound = CompoundECO(
            name="test_compound",
            description="Test metadata",
            components=[NoOpECO(), PlacementDensityECO()],
        )

        # Should match
        assert compound.eco_class == compound.metadata.eco_class
        assert compound.eco_class == ECOClass.ROUTING_AFFECTING
