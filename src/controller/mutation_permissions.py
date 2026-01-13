"""Mutation permission matrix for controlling ECO operations based on element type and ECO class.

This module defines what operations are allowed on different element types (standard cells,
macros, I/O pads) based on the ECO class. This provides fine-grained control over what
changes ECOs can make to the design.
"""

from dataclasses import dataclass
from enum import Enum

from .types import ECOClass


class ElementType(str, Enum):
    """Types of design elements that can be targeted by ECOs."""

    STANDARD_CELL = "standard_cell"
    MACRO = "macro"
    IO_PAD = "io_pad"
    NET = "net"
    BUFFER = "buffer"


class Operation(str, Enum):
    """Operations that can be performed by ECOs."""

    RESIZE = "resize"  # Change cell size/drive strength
    MOVE = "move"  # Change placement location
    DELETE = "delete"  # Remove element
    INSERT = "insert"  # Add new element
    BUFFER_INSERTION = "buffer_insertion"  # Insert buffer on net
    BUFFER_REMOVAL = "buffer_removal"  # Remove buffer from net
    REWIRE = "rewire"  # Change net connectivity
    CLONE = "clone"  # Duplicate element


@dataclass
class PermissionViolation:
    """Represents a violation of mutation permissions."""

    element_type: ElementType
    operation: Operation
    eco_class: ECOClass
    target: str
    reason: str

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "element_type": self.element_type.value,
            "operation": self.operation.value,
            "eco_class": self.eco_class.value,
            "target": self.target,
            "reason": self.reason,
        }


class MutationPermissionMatrix:
    """Matrix defining what operations are allowed for each element type and ECO class.

    The permission matrix controls what mutations ECOs can make based on their
    blast radius classification. More conservative ECO classes have fewer allowed
    operations.
    """

    def __init__(self):
        """Initialize the permission matrix with default rules."""
        self._matrix: dict[tuple[ElementType, ECOClass], set[Operation]] = {}
        self._approval_required: dict[tuple[ElementType, ECOClass, Operation], bool] = {}
        self._initialize_default_matrix()

    def _initialize_default_matrix(self) -> None:
        """Initialize default permission matrix."""
        # TOPOLOGY_NEUTRAL: Can only perform non-topology-changing operations
        self._matrix[(ElementType.STANDARD_CELL, ECOClass.TOPOLOGY_NEUTRAL)] = {
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
        }
        self._matrix[(ElementType.NET, ECOClass.TOPOLOGY_NEUTRAL)] = {
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
        }
        self._matrix[(ElementType.BUFFER, ECOClass.TOPOLOGY_NEUTRAL)] = {
            Operation.INSERT,
            Operation.DELETE,
            Operation.MOVE,
        }
        # No operations allowed on macros or I/O pads for TOPOLOGY_NEUTRAL
        self._matrix[(ElementType.MACRO, ECOClass.TOPOLOGY_NEUTRAL)] = set()
        self._matrix[(ElementType.IO_PAD, ECOClass.TOPOLOGY_NEUTRAL)] = set()

        # PLACEMENT_LOCAL: Can resize and move cells locally
        self._matrix[(ElementType.STANDARD_CELL, ECOClass.PLACEMENT_LOCAL)] = {
            Operation.RESIZE,
            Operation.MOVE,
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
            Operation.INSERT,
            Operation.DELETE,
        }
        self._matrix[(ElementType.NET, ECOClass.PLACEMENT_LOCAL)] = {
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
            Operation.REWIRE,
        }
        self._matrix[(ElementType.BUFFER, ECOClass.PLACEMENT_LOCAL)] = {
            Operation.INSERT,
            Operation.DELETE,
            Operation.MOVE,
            Operation.RESIZE,
        }
        # Limited macro operations
        self._matrix[(ElementType.MACRO, ECOClass.PLACEMENT_LOCAL)] = {
            Operation.BUFFER_INSERTION,  # Can buffer near macros
        }
        # No operations on I/O pads
        self._matrix[(ElementType.IO_PAD, ECOClass.PLACEMENT_LOCAL)] = set()

        # ROUTING_AFFECTING: Can rewire nets and affect routing
        self._matrix[(ElementType.STANDARD_CELL, ECOClass.ROUTING_AFFECTING)] = {
            Operation.RESIZE,
            Operation.MOVE,
            Operation.DELETE,
            Operation.INSERT,
            Operation.CLONE,
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
        }
        self._matrix[(ElementType.NET, ECOClass.ROUTING_AFFECTING)] = {
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
            Operation.REWIRE,
        }
        self._matrix[(ElementType.BUFFER, ECOClass.ROUTING_AFFECTING)] = {
            Operation.INSERT,
            Operation.DELETE,
            Operation.MOVE,
            Operation.RESIZE,
        }
        self._matrix[(ElementType.MACRO, ECOClass.ROUTING_AFFECTING)] = {
            Operation.BUFFER_INSERTION,
            Operation.REWIRE,  # Can rewire connections to macros
        }
        # Still no operations on I/O pads
        self._matrix[(ElementType.IO_PAD, ECOClass.ROUTING_AFFECTING)] = set()

        # GLOBAL_DISRUPTIVE: Can do almost anything, but requires approval for sensitive ops
        self._matrix[(ElementType.STANDARD_CELL, ECOClass.GLOBAL_DISRUPTIVE)] = {
            Operation.RESIZE,
            Operation.MOVE,
            Operation.DELETE,
            Operation.INSERT,
            Operation.CLONE,
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
            Operation.REWIRE,
        }
        self._matrix[(ElementType.NET, ECOClass.GLOBAL_DISRUPTIVE)] = {
            Operation.BUFFER_INSERTION,
            Operation.BUFFER_REMOVAL,
            Operation.REWIRE,
        }
        self._matrix[(ElementType.BUFFER, ECOClass.GLOBAL_DISRUPTIVE)] = {
            Operation.INSERT,
            Operation.DELETE,
            Operation.MOVE,
            Operation.RESIZE,
        }
        self._matrix[(ElementType.MACRO, ECOClass.GLOBAL_DISRUPTIVE)] = {
            Operation.MOVE,  # Requires approval
            Operation.REWIRE,  # Requires approval
            Operation.BUFFER_INSERTION,
        }
        # I/O pads still protected
        self._matrix[(ElementType.IO_PAD, ECOClass.GLOBAL_DISRUPTIVE)] = set()

        # Configure approval requirements for GLOBAL_DISRUPTIVE
        self._approval_required[(ElementType.MACRO, ECOClass.GLOBAL_DISRUPTIVE, Operation.MOVE)] = True
        self._approval_required[(ElementType.MACRO, ECOClass.GLOBAL_DISRUPTIVE, Operation.REWIRE)] = True

    def get_allowed_operations(
        self,
        element_type: ElementType,
        eco_class: ECOClass
    ) -> set[Operation]:
        """Get the set of allowed operations for an element type and ECO class.

        Args:
            element_type: Type of design element
            eco_class: ECO classification

        Returns:
            Set of allowed operations (may be empty)
        """
        return self._matrix.get((element_type, eco_class), set()).copy()

    def is_operation_allowed(
        self,
        element_type: ElementType,
        operation: Operation,
        eco_class: ECOClass
    ) -> bool:
        """Check if an operation is allowed for a given element type and ECO class.

        Args:
            element_type: Type of design element
            operation: Operation to check
            eco_class: ECO classification

        Returns:
            True if operation is allowed, False otherwise
        """
        allowed_ops = self.get_allowed_operations(element_type, eco_class)
        return operation in allowed_ops

    def requires_approval(
        self,
        element_type: ElementType,
        operation: Operation,
        eco_class: ECOClass
    ) -> bool:
        """Check if an operation requires human approval.

        Args:
            element_type: Type of design element
            operation: Operation to check
            eco_class: ECO classification

        Returns:
            True if approval is required, False otherwise
        """
        # First check if operation is even allowed
        if not self.is_operation_allowed(element_type, operation, eco_class):
            return False  # Not allowed, so approval question is moot

        # Check if approval is explicitly required
        key = (element_type, eco_class, operation)
        return self._approval_required.get(key, False)

    def check_operation(
        self,
        element_type: ElementType,
        operation: Operation,
        eco_class: ECOClass,
        target: str
    ) -> PermissionViolation | None:
        """Check if an operation is allowed and return violation if not.

        Args:
            element_type: Type of design element
            operation: Operation to perform
            eco_class: ECO classification
            target: Target element identifier

        Returns:
            PermissionViolation if not allowed, None if allowed
        """
        if not self.is_operation_allowed(element_type, operation, eco_class):
            reason = (
                f"{operation.value} operation on {element_type.value} "
                f"not allowed for {eco_class.value} ECO class"
            )
            return PermissionViolation(
                element_type=element_type,
                operation=operation,
                eco_class=eco_class,
                target=target,
                reason=reason,
            )
        return None

    def set_allowed_operations(
        self,
        element_type: ElementType,
        eco_class: ECOClass,
        operations: set[Operation]
    ) -> None:
        """Set the allowed operations for an element type and ECO class.

        This allows customization of the permission matrix beyond the defaults.

        Args:
            element_type: Type of design element
            eco_class: ECO classification
            operations: Set of allowed operations
        """
        self._matrix[(element_type, eco_class)] = operations.copy()

    def set_requires_approval(
        self,
        element_type: ElementType,
        eco_class: ECOClass,
        operation: Operation,
        requires: bool
    ) -> None:
        """Set whether an operation requires approval.

        Args:
            element_type: Type of design element
            eco_class: ECO classification
            operation: Operation
            requires: Whether approval is required
        """
        key = (element_type, eco_class, operation)
        self._approval_required[key] = requires
