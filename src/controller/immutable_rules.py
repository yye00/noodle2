"""Immutable design rules to protect critical structures from ECO modification.

This module provides rule-based protection for design elements that should not
be modified during ECO execution, such as macro placements, clock nets, and
specific cell instances.
"""

from dataclasses import dataclass, field
from enum import Enum
from fnmatch import fnmatch
from typing import Any


class ViolationSeverity(Enum):
    """Severity level for immutability violations."""

    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"


@dataclass
class ImmutableViolation:
    """Represents a violation of immutability rules."""

    rule_type: str
    target: str
    reason: str
    severity: ViolationSeverity = ViolationSeverity.CRITICAL

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rule_type": self.rule_type,
            "target": self.target,
            "reason": self.reason,
            "severity": self.severity.value,
        }


@dataclass
class StructuralRules:
    """Structural immutability rules."""

    macro_locations: bool = False
    io_pin_positions: bool = False
    power_grid: bool = False
    clock_tree_topology: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StructuralRules":
        """Create from dictionary."""
        return cls(
            macro_locations=data.get("macro_locations", False),
            io_pin_positions=data.get("io_pin_positions", False),
            power_grid=data.get("power_grid", False),
            clock_tree_topology=data.get("clock_tree_topology", False),
        )


@dataclass
class TimingRules:
    """Timing immutability rules."""

    clock_definitions: bool = False
    false_paths: bool = False
    multicycle_paths: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TimingRules":
        """Create from dictionary."""
        return cls(
            clock_definitions=data.get("clock_definitions", False),
            false_paths=data.get("false_paths", False),
            multicycle_paths=data.get("multicycle_paths", False),
        )


@dataclass
class NetRules:
    """Net-level immutability rules."""

    protected_nets: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NetRules":
        """Create from dictionary."""
        return cls(
            protected_nets=data.get("protected_nets", []),
        )

    def is_net_protected(self, net_name: str) -> bool:
        """Check if a net is protected by pattern matching.

        Args:
            net_name: Name of the net to check

        Returns:
            True if net matches any protected pattern
        """
        for pattern in self.protected_nets:
            if fnmatch(net_name, pattern):
                return True
        return False


@dataclass
class CellProtectionPattern:
    """Pattern for protecting cells."""

    pattern: str | None = None
    instance: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CellProtectionPattern":
        """Create from dictionary."""
        return cls(
            pattern=data.get("pattern"),
            instance=data.get("instance"),
        )

    def matches(self, cell_name: str) -> bool:
        """Check if cell matches this protection pattern.

        Args:
            cell_name: Name of the cell to check

        Returns:
            True if cell matches pattern or instance name
        """
        if self.instance and cell_name == self.instance:
            return True
        if self.pattern and fnmatch(cell_name, self.pattern):
            return True
        return False


@dataclass
class CellRules:
    """Cell-level immutability rules."""

    protected_cells: list[CellProtectionPattern] = field(default_factory=list)
    size_locked: list[CellProtectionPattern] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CellRules":
        """Create from dictionary."""
        protected_cells = []
        for item in data.get("protected_cells", []):
            if isinstance(item, str):
                # Simple pattern string
                protected_cells.append(CellProtectionPattern(pattern=item))
            elif isinstance(item, dict):
                protected_cells.append(CellProtectionPattern.from_dict(item))

        size_locked = []
        for item in data.get("size_locked", []):
            if isinstance(item, str):
                size_locked.append(CellProtectionPattern(pattern=item))
            elif isinstance(item, dict):
                size_locked.append(CellProtectionPattern.from_dict(item))

        return cls(
            protected_cells=protected_cells,
            size_locked=size_locked,
        )

    def is_cell_protected(self, cell_name: str) -> bool:
        """Check if a cell is protected from modification.

        Args:
            cell_name: Name of the cell to check

        Returns:
            True if cell matches any protection pattern
        """
        for protection in self.protected_cells:
            if protection.matches(cell_name):
                return True
        return False

    def is_cell_size_locked(self, cell_name: str) -> bool:
        """Check if a cell's size is locked.

        Args:
            cell_name: Name of the cell to check

        Returns:
            True if cell size is locked
        """
        for protection in self.size_locked:
            if protection.matches(cell_name):
                return True
        return False


@dataclass
class ImmutableRules:
    """Complete set of immutability rules for a design."""

    structural: StructuralRules = field(default_factory=StructuralRules)
    timing: TimingRules = field(default_factory=TimingRules)
    nets: NetRules = field(default_factory=NetRules)
    cells: CellRules = field(default_factory=CellRules)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ImmutableRules":
        """Create from dictionary (typically from YAML config).

        Args:
            data: Dictionary with immutable rules configuration

        Returns:
            ImmutableRules instance
        """
        return cls(
            structural=StructuralRules.from_dict(data.get("structural", {})),
            timing=TimingRules.from_dict(data.get("timing", {})),
            nets=NetRules.from_dict(data.get("nets", {})),
            cells=CellRules.from_dict(data.get("cells", {})),
        )

    @classmethod
    def disabled(cls) -> "ImmutableRules":
        """Create a disabled (permissive) rule set."""
        return cls()


class ImmutabilityChecker:
    """Checks ECO operations against immutability rules."""

    def __init__(self, rules: ImmutableRules):
        """Initialize checker with rules.

        Args:
            rules: Immutability rules to enforce
        """
        self.rules = rules

    def check_macro_move(self, macro_name: str) -> ImmutableViolation | None:
        """Check if macro movement is allowed.

        Args:
            macro_name: Name of the macro

        Returns:
            Violation if macro locations are protected, None otherwise
        """
        if self.rules.structural.macro_locations:
            return ImmutableViolation(
                rule_type="structural.macro_locations",
                target=macro_name,
                reason=f"Macro locations are immutable. Cannot move {macro_name}.",
                severity=ViolationSeverity.CRITICAL,
            )
        return None

    def check_net_modification(self, net_name: str) -> ImmutableViolation | None:
        """Check if net modification is allowed.

        Args:
            net_name: Name of the net

        Returns:
            Violation if net is protected, None otherwise
        """
        if self.rules.nets.is_net_protected(net_name):
            return ImmutableViolation(
                rule_type="nets.protected_nets",
                target=net_name,
                reason=f"Net {net_name} matches protected pattern. Cannot modify.",
                severity=ViolationSeverity.CRITICAL,
            )
        return None

    def check_cell_modification(
        self, cell_name: str, modification_type: str = "general"
    ) -> ImmutableViolation | None:
        """Check if cell modification is allowed.

        Args:
            cell_name: Name of the cell
            modification_type: Type of modification ("general", "resize", etc.)

        Returns:
            Violation if cell is protected, None otherwise
        """
        if self.rules.cells.is_cell_protected(cell_name):
            return ImmutableViolation(
                rule_type="cells.protected_cells",
                target=cell_name,
                reason=f"Cell {cell_name} is protected. Cannot {modification_type}.",
                severity=ViolationSeverity.CRITICAL,
            )

        if (
            modification_type == "resize"
            and self.rules.cells.is_cell_size_locked(cell_name)
        ):
            return ImmutableViolation(
                rule_type="cells.size_locked",
                target=cell_name,
                reason=f"Cell {cell_name} size is locked. Cannot resize.",
                severity=ViolationSeverity.CRITICAL,
            )

        return None

    def check_clock_definition_change(
        self, clock_name: str
    ) -> ImmutableViolation | None:
        """Check if clock definition change is allowed.

        Args:
            clock_name: Name of the clock

        Returns:
            Violation if clock definitions are protected, None otherwise
        """
        if self.rules.timing.clock_definitions:
            return ImmutableViolation(
                rule_type="timing.clock_definitions",
                target=clock_name,
                reason=f"Clock definitions are immutable. Cannot modify {clock_name}.",
                severity=ViolationSeverity.CRITICAL,
            )
        return None

    def check_io_pin_move(self, pin_name: str) -> ImmutableViolation | None:
        """Check if I/O pin movement is allowed.

        Args:
            pin_name: Name of the pin

        Returns:
            Violation if I/O pin positions are protected, None otherwise
        """
        if self.rules.structural.io_pin_positions:
            return ImmutableViolation(
                rule_type="structural.io_pin_positions",
                target=pin_name,
                reason=f"I/O pin positions are immutable. Cannot move {pin_name}.",
                severity=ViolationSeverity.CRITICAL,
            )
        return None


def load_immutable_rules_from_config(config_dict: dict[str, Any]) -> ImmutableRules:
    """Load immutable rules from Study configuration.

    Args:
        config_dict: Study configuration dictionary

    Returns:
        ImmutableRules instance
    """
    if "immutable_rules" in config_dict:
        return ImmutableRules.from_dict(config_dict["immutable_rules"])
    return ImmutableRules.disabled()
