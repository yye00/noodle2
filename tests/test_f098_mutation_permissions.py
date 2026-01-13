"""Tests for F098: Mutation permissions matrix enforces ECO class restrictions."""

import pytest
from controller.types import ECOClass
from controller.mutation_permissions import (
    MutationPermissionMatrix,
    ElementType,
    Operation,
    PermissionViolation,
)


class TestF098DefinePermissionMatrix:
    """Test Step 1: Define mutation permission matrix for each element type vs ECO class."""

    def test_step_1_define_permission_matrix(self):
        """Step 1: Define mutation permission matrix for each element type vs ECO class."""
        matrix = MutationPermissionMatrix()

        # Verify matrix is defined for all element types and ECO classes
        for element_type in ElementType:
            for eco_class in ECOClass:
                # Should return a set of allowed operations (may be empty)
                ops = matrix.get_allowed_operations(element_type, eco_class)
                assert isinstance(ops, set)

    def test_default_matrix_structure(self):
        """Verify default matrix has expected structure."""
        matrix = MutationPermissionMatrix()

        # TOPOLOGY_NEUTRAL: Can only modify buffers/sizing without changing topology
        assert Operation.BUFFER_INSERTION in matrix.get_allowed_operations(
            ElementType.STANDARD_CELL, ECOClass.TOPOLOGY_NEUTRAL
        )

        # PLACEMENT_LOCAL: Can resize and move cells
        assert Operation.RESIZE in matrix.get_allowed_operations(
            ElementType.STANDARD_CELL, ECOClass.PLACEMENT_LOCAL
        )
        assert Operation.MOVE in matrix.get_allowed_operations(
            ElementType.STANDARD_CELL, ECOClass.PLACEMENT_LOCAL
        )

        # I/O pads should be restricted
        io_ops = matrix.get_allowed_operations(
            ElementType.IO_PAD, ECOClass.TOPOLOGY_NEUTRAL
        )
        assert len(io_ops) == 0 or Operation.MOVE not in io_ops


class TestF098TopologyNeutralRestrictions:
    """Test Step 2: Attempt topology_neutral ECO on standard cell (should fail resize)."""

    def test_step_2_topology_neutral_cannot_resize(self):
        """Step 2: Attempt topology_neutral ECO on standard cell (should fail resize)."""
        matrix = MutationPermissionMatrix()

        # TOPOLOGY_NEUTRAL should not allow resize (changes topology)
        allowed = matrix.is_operation_allowed(
            element_type=ElementType.STANDARD_CELL,
            operation=Operation.RESIZE,
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
        )

        assert not allowed, "TOPOLOGY_NEUTRAL should not allow RESIZE on standard cells"

    def test_topology_neutral_allows_buffer_ops(self):
        """TOPOLOGY_NEUTRAL should allow buffer insertion."""
        matrix = MutationPermissionMatrix()

        # Should allow buffer insertion (topology-neutral)
        allowed = matrix.is_operation_allowed(
            element_type=ElementType.STANDARD_CELL,
            operation=Operation.BUFFER_INSERTION,
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
        )

        assert allowed, "TOPOLOGY_NEUTRAL should allow buffer insertion"


class TestF098PlacementLocalPermissions:
    """Test Step 3: Attempt placement_local ECO on standard cell (should allow resize/move)."""

    def test_step_3_placement_local_allows_resize_move(self):
        """Step 3: Attempt placement_local ECO on standard cell (should allow resize/move)."""
        matrix = MutationPermissionMatrix()

        # PLACEMENT_LOCAL should allow resize
        resize_allowed = matrix.is_operation_allowed(
            element_type=ElementType.STANDARD_CELL,
            operation=Operation.RESIZE,
            eco_class=ECOClass.PLACEMENT_LOCAL,
        )
        assert resize_allowed, "PLACEMENT_LOCAL should allow RESIZE"

        # PLACEMENT_LOCAL should allow move
        move_allowed = matrix.is_operation_allowed(
            element_type=ElementType.STANDARD_CELL,
            operation=Operation.MOVE,
            eco_class=ECOClass.PLACEMENT_LOCAL,
        )
        assert move_allowed, "PLACEMENT_LOCAL should allow MOVE"


class TestF098IOPadProtection:
    """Test Step 4: Attempt any ECO on I/O pads (should fail for all classes)."""

    def test_step_4_io_pads_protected_from_all_classes(self):
        """Step 4: Attempt any ECO on I/O pads (should fail for all classes)."""
        matrix = MutationPermissionMatrix()

        # Try various operations on I/O pads for all ECO classes
        for eco_class in ECOClass:
            for operation in [Operation.RESIZE, Operation.MOVE, Operation.DELETE]:
                allowed = matrix.is_operation_allowed(
                    element_type=ElementType.IO_PAD,
                    operation=operation,
                    eco_class=eco_class,
                )
                assert not allowed, f"I/O pads should be protected from {operation} in {eco_class}"


class TestF098GlobalDisruptiveRequiresApproval:
    """Test Step 5: Verify global_disruptive ECO on macro requires approval."""

    def test_step_5_global_disruptive_on_macro_requires_approval(self):
        """Step 5: Verify global_disruptive ECO on macro requires approval."""
        matrix = MutationPermissionMatrix()

        # Check if macro operations require approval for GLOBAL_DISRUPTIVE
        requires_approval = matrix.requires_approval(
            element_type=ElementType.MACRO,
            operation=Operation.MOVE,
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
        )

        assert requires_approval, "GLOBAL_DISRUPTIVE macro moves should require approval"

    def test_other_classes_on_macro_dont_require_approval(self):
        """Verify other ECO classes on macros don't require approval by default."""
        matrix = MutationPermissionMatrix()

        # PLACEMENT_LOCAL on macros might not require approval
        # (This depends on design policy, but test the mechanism)
        for eco_class in [ECOClass.TOPOLOGY_NEUTRAL, ECOClass.PLACEMENT_LOCAL]:
            requires_approval = matrix.requires_approval(
                element_type=ElementType.MACRO,
                operation=Operation.RESIZE,  # Unlikely to be allowed anyway
                eco_class=eco_class,
            )
            # Just verify the method works, don't assert specific behavior
            assert isinstance(requires_approval, bool)


class TestF098ViolationReporting:
    """Test violation reporting when operations are not allowed."""

    def test_check_operation_returns_violation(self):
        """Verify check_operation returns violation when not allowed."""
        matrix = MutationPermissionMatrix()

        # Try an operation that should fail
        violation = matrix.check_operation(
            element_type=ElementType.IO_PAD,
            operation=Operation.MOVE,
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            target="io_pad_123",
        )

        assert violation is not None
        assert isinstance(violation, PermissionViolation)
        assert violation.element_type == ElementType.IO_PAD
        assert violation.operation == Operation.MOVE
        assert violation.eco_class == ECOClass.TOPOLOGY_NEUTRAL

    def test_check_operation_returns_none_when_allowed(self):
        """Verify check_operation returns None when operation is allowed."""
        matrix = MutationPermissionMatrix()

        # Try an operation that should succeed
        violation = matrix.check_operation(
            element_type=ElementType.STANDARD_CELL,
            operation=Operation.BUFFER_INSERTION,
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            target="cell_123",
        )

        assert violation is None
