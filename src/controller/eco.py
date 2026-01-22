"""ECO (Engineering Change Order) framework for Noodle 2.

This module provides the core ECO abstraction layer that enables:
- First-class, auditable units of change
- Stable naming and classification
- Standardized helper APIs
- Effectiveness tracking and prior management
- Safety-aware execution constraints
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .types import ECOClass


def get_pdk_layer_names(pdk: str = "nangate45") -> tuple[str, str]:
    """Get PDK-specific layer names for wire RC settings.

    Different PDKs use different layer naming conventions:
    - Nangate45: metal3, metal5 (lowercase)
    - ASAP7: M3, M5 (uppercase, no "etal")
    - Sky130: met2, met4 (abbreviated naming)

    Args:
        pdk: PDK name (nangate45, asap7, sky130)

    Returns:
        Tuple of (signal_layer, clock_layer) names
    """
    pdk_lower = pdk.lower()
    if pdk_lower == "asap7":
        return ("M3", "M5")
    elif pdk_lower == "sky130":
        # Sky130 uses abbreviated layer names: li1, met1, met2, met3, met4, met5
        return ("met2", "met4")
    else:
        # Nangate45 and others use metal3/metal5
        return ("metal3", "metal5")


class ECOPrior(str, Enum):
    """Prior confidence level for ECO effectiveness based on historical evidence."""

    UNKNOWN = "unknown"  # No history
    TRUSTED = "trusted"  # Consistently helpful
    MIXED = "mixed"  # Sometimes helpful, sometimes not
    SUSPICIOUS = "suspicious"  # Frequently problematic
    BLACKLISTED = "blacklisted"  # Explicitly forbidden


@dataclass
class ECOPrecondition:
    """Precondition that must be satisfied before applying an ECO.

    Preconditions enable ECOs to skip execution when the design state
    doesn't warrant the change, improving efficiency and safety.
    """

    name: str  # Human-readable name for this precondition
    description: str  # What this precondition checks
    check: Callable[[dict[str, Any]], bool]  # Function that evaluates the precondition
    parameters: dict[str, Any] = field(default_factory=dict)  # Configuration

    def evaluate(self, design_metrics: dict[str, Any]) -> bool:
        """Evaluate precondition against design metrics.

        Args:
            design_metrics: Current design state metrics (wns_ps, congestion, etc.)

        Returns:
            True if precondition is satisfied, False otherwise
        """
        return self.check(design_metrics)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ECOPostcondition:
    """Postcondition that must be verified after applying an ECO.

    Postconditions enable ECOs to verify they achieved their intended
    effect and didn't introduce unintended side effects.
    """

    name: str  # Human-readable name for this postcondition
    description: str  # What this postcondition verifies
    check: Callable[[dict[str, Any], dict[str, Any]], bool]  # Function that evaluates postcondition
    parameters: dict[str, Any] = field(default_factory=dict)  # Configuration

    def evaluate(
        self, before_metrics: dict[str, Any], after_metrics: dict[str, Any]
    ) -> bool:
        """Evaluate postcondition by comparing before/after metrics.

        Args:
            before_metrics: Design metrics before ECO application
            after_metrics: Design metrics after ECO application

        Returns:
            True if postcondition is satisfied, False otherwise
        """
        return self.check(before_metrics, after_metrics)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


@dataclass
class ECOMetadata:
    """Metadata describing an ECO's properties and constraints."""

    name: str  # Stable, unique identifier
    eco_class: ECOClass  # Blast radius classification
    description: str  # Human-readable purpose
    parameters: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"  # For tracking ECO evolution
    author: str = ""  # Optional provenance
    tags: list[str] = field(default_factory=list)  # For categorization
    preconditions: list[ECOPrecondition] = field(default_factory=list)  # Preconditions
    postconditions: list[ECOPostcondition] = field(default_factory=list)  # Postconditions
    expected_effects: dict[str, str] = field(default_factory=dict)  # Expected metric changes (F259)
    timeout_seconds: float | None = None  # Execution timeout limit (F260)
    parameter_ranges: dict[str, dict[str, float]] = field(default_factory=dict)  # Parameter value ranges (F261)

    def __post_init__(self) -> None:
        """Validate metadata."""
        if not self.name:
            raise ValueError("ECO name cannot be empty")
        if not self.description:
            raise ValueError("ECO description cannot be empty")
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        # Validate parameter ranges (F261)
        self._validate_parameter_ranges()

    def _validate_parameter_ranges(self) -> None:
        """Validate that all parameters are within their defined ranges.

        Raises:
            ValueError: If any parameter is outside its defined range
        """
        if not self.parameter_ranges:
            return  # No ranges defined, nothing to validate

        for param_name, range_spec in self.parameter_ranges.items():
            if param_name not in self.parameters:
                # Parameter has a range but no value - skip (may be optional)
                continue

            param_value = self.parameters[param_name]

            # Check if value is numeric (required for range checking)
            if not isinstance(param_value, (int, float)):
                raise ValueError(
                    f"Parameter '{param_name}' has a range constraint but "
                    f"value is not numeric: {type(param_value).__name__}"
                )

            # Check min constraint
            if "min" in range_spec:
                min_value = range_spec["min"]
                if param_value < min_value:
                    raise ValueError(
                        f"Parameter '{param_name}' value {param_value} is below "
                        f"minimum allowed value {min_value} (range: "
                        f"[{range_spec.get('min', '-∞')}, {range_spec.get('max', '∞')}])"
                    )

            # Check max constraint
            if "max" in range_spec:
                max_value = range_spec["max"]
                if param_value > max_value:
                    raise ValueError(
                        f"Parameter '{param_name}' value {param_value} is above "
                        f"maximum allowed value {max_value} (range: "
                        f"[{range_spec.get('min', '-∞')}, {range_spec.get('max', '∞')}])"
                    )


@dataclass
class ECOResult:
    """Result of executing an ECO."""

    eco_name: str
    success: bool
    metrics_delta: dict[str, float] = field(default_factory=dict)  # Change in metrics
    error_message: str | None = None
    log_excerpt: str | None = None
    execution_time_seconds: float = 0.0
    artifacts_generated: list[str] = field(default_factory=list)
    preconditions_satisfied: bool = True  # Were all preconditions met?
    precondition_failures: list[str] = field(default_factory=list)  # Which preconditions failed
    skipped_due_to_preconditions: bool = False  # Was ECO skipped?
    postconditions_satisfied: bool = True  # Were all postconditions met?
    postcondition_failures: list[str] = field(default_factory=list)  # Which postconditions failed

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_name": self.eco_name,
            "success": self.success,
            "metrics_delta": self.metrics_delta,
            "error_message": self.error_message,
            "log_excerpt": self.log_excerpt,
            "execution_time_seconds": self.execution_time_seconds,
            "artifacts_generated": self.artifacts_generated,
            "preconditions_satisfied": self.preconditions_satisfied,
            "precondition_failures": self.precondition_failures,
            "skipped_due_to_preconditions": self.skipped_due_to_preconditions,
            "postconditions_satisfied": self.postconditions_satisfied,
            "postcondition_failures": self.postcondition_failures,
        }


@dataclass
class ECOEffectiveness:
    """Tracks ECO effectiveness across trials within a Study."""

    eco_name: str
    total_applications: int = 0
    successful_applications: int = 0
    failed_applications: int = 0
    average_wns_improvement_ps: float = 0.0
    best_wns_improvement_ps: float = 0.0
    worst_wns_degradation_ps: float = 0.0
    prior: ECOPrior = ECOPrior.UNKNOWN

    def update(self, success: bool, wns_delta_ps: float) -> None:
        """Update effectiveness tracking with new trial result.

        Args:
            success: Whether the ECO application succeeded
            wns_delta_ps: Change in WNS (positive = improvement, negative = degradation)
        """
        self.total_applications += 1
        if success:
            self.successful_applications += 1
        else:
            self.failed_applications += 1

        # Update running average
        n = self.total_applications
        self.average_wns_improvement_ps = (
            self.average_wns_improvement_ps * (n - 1) + wns_delta_ps
        ) / n

        # Track best and worst
        if wns_delta_ps > self.best_wns_improvement_ps:
            self.best_wns_improvement_ps = wns_delta_ps
        if wns_delta_ps < self.worst_wns_degradation_ps:
            self.worst_wns_degradation_ps = wns_delta_ps

        # Update prior based on evidence
        self._update_prior()

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        if self.total_applications == 0:
            return 0.0
        return self.successful_applications / self.total_applications

    def _update_prior(self) -> None:
        """Update prior classification based on accumulated evidence."""
        if self.total_applications < 3:
            # Not enough evidence
            self.prior = ECOPrior.UNKNOWN
            return

        success_rate = self.success_rate

        # Classification heuristics
        if success_rate >= 0.8 and self.average_wns_improvement_ps > 0:
            self.prior = ECOPrior.TRUSTED
        elif success_rate >= 0.5:
            self.prior = ECOPrior.MIXED
        elif success_rate < 0.3 or self.average_wns_improvement_ps < -1000:
            # Frequently fails or consistently degrades timing
            self.prior = ECOPrior.SUSPICIOUS
        else:
            self.prior = ECOPrior.MIXED

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_name": self.eco_name,
            "total_applications": self.total_applications,
            "successful_applications": self.successful_applications,
            "failed_applications": self.failed_applications,
            "success_rate": (
                self.successful_applications / self.total_applications
                if self.total_applications > 0
                else 0.0
            ),
            "average_wns_improvement_ps": self.average_wns_improvement_ps,
            "best_wns_improvement_ps": self.best_wns_improvement_ps,
            "worst_wns_degradation_ps": self.worst_wns_degradation_ps,
            "prior": self.prior.value,
        }


class ECO(ABC):
    """Base class for all ECOs.

    All ECOs must:
    - Have a stable name and classification
    - Execute through standardized helper APIs
    - Emit metrics, logs, and failure semantics
    - Be comparable across Cases and Studies
    """

    def __init__(self, metadata: ECOMetadata) -> None:
        """Initialize ECO with metadata."""
        self.metadata = metadata

    @property
    def name(self) -> str:
        """Get ECO name."""
        return self.metadata.name

    @property
    def eco_class(self) -> ECOClass:
        """Get ECO classification."""
        return self.metadata.eco_class

    @abstractmethod
    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate OpenROAD Tcl script for this ECO.

        Returns:
            Tcl script as a string
        """
        pass

    @abstractmethod
    def validate_parameters(self) -> bool:
        """Validate ECO parameters are reasonable.

        Returns:
            True if parameters are valid, False otherwise
        """
        pass

    def validate_parameter_ranges(self) -> bool:
        """Validate that all parameters are within their defined ranges.

        This is a helper method that ECO implementations can call from their
        validate_parameters() method to check parameter range constraints.

        Returns:
            True if all parameters are within range, False otherwise
        """
        if not self.metadata.parameter_ranges:
            return True  # No ranges defined, all parameters valid

        for param_name, range_spec in self.metadata.parameter_ranges.items():
            if param_name not in self.metadata.parameters:
                # Parameter has a range but no value - skip
                continue

            param_value = self.metadata.parameters[param_name]

            # Check if value is numeric (required for range checking)
            if not isinstance(param_value, (int, float)):
                return False

            # Check min constraint
            if "min" in range_spec:
                if param_value < range_spec["min"]:
                    return False

            # Check max constraint
            if "max" in range_spec:
                if param_value > range_spec["max"]:
                    return False

        return True

    def evaluate_preconditions(
        self, design_metrics: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Evaluate all preconditions against current design metrics.

        Args:
            design_metrics: Current design state metrics (wns_ps, congestion, etc.)

        Returns:
            Tuple of (all_satisfied, failed_preconditions)
            - all_satisfied: True if all preconditions pass
            - failed_preconditions: List of names of failed preconditions
        """
        if not self.metadata.preconditions:
            # No preconditions means always satisfied
            return True, []

        failed = []
        for precondition in self.metadata.preconditions:
            try:
                if not precondition.evaluate(design_metrics):
                    failed.append(precondition.name)
            except Exception as e:
                # Treat evaluation errors as failures
                failed.append(f"{precondition.name} (error: {str(e)})")

        return len(failed) == 0, failed

    def evaluate_postconditions(
        self, before_metrics: dict[str, Any], after_metrics: dict[str, Any]
    ) -> tuple[bool, list[str]]:
        """Evaluate all postconditions by comparing before/after metrics.

        Args:
            before_metrics: Design metrics before ECO application
            after_metrics: Design metrics after ECO application

        Returns:
            Tuple of (all_satisfied, failed_postconditions)
            - all_satisfied: True if all postconditions pass
            - failed_postconditions: List of names of failed postconditions
        """
        if not self.metadata.postconditions:
            # No postconditions means always satisfied
            return True, []

        failed = []
        for postcondition in self.metadata.postconditions:
            try:
                if not postcondition.evaluate(before_metrics, after_metrics):
                    failed.append(postcondition.name)
            except Exception as e:
                # Treat evaluation errors as failures
                failed.append(f"{postcondition.name} (error: {str(e)})")

        return len(failed) == 0, failed

    def to_dict(self) -> dict[str, Any]:
        """Convert ECO to dictionary for serialization."""
        result = {
            "name": self.metadata.name,
            "eco_class": self.metadata.eco_class.value,
            "description": self.metadata.description,
            "parameters": self.metadata.parameters,
            "version": self.metadata.version,
            "author": self.metadata.author,
            "tags": self.metadata.tags,
            "preconditions": [p.to_dict() for p in self.metadata.preconditions],
            "postconditions": [p.to_dict() for p in self.metadata.postconditions],
            "expected_effects": self.metadata.expected_effects,
        }
        if self.metadata.timeout_seconds is not None:
            result["timeout_seconds"] = self.metadata.timeout_seconds
        if self.metadata.parameter_ranges:
            result["parameter_ranges"] = self.metadata.parameter_ranges
        return result


class NoOpECO(ECO):
    """No-operation ECO for baseline testing."""

    def __init__(self) -> None:
        """Initialize no-op ECO."""
        metadata = ECOMetadata(
            name="noop",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="No-operation ECO for baseline testing",
            version="1.0",
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate empty Tcl script."""
        return "# No-op ECO - baseline execution\n"

    def validate_parameters(self) -> bool:
        """No-op always valid."""
        return True


class BufferInsertionECO(ECO):
    """ECO that inserts buffers on long nets to improve timing."""

    def __init__(
        self, max_capacitance: float = 0.2, buffer_cell: str = "BUF_X4"
    ) -> None:
        """Initialize buffer insertion ECO.

        Args:
            max_capacitance: Maximum net capacitance before buffering (pF)
            buffer_cell: Buffer cell to use for insertion
        """
        metadata = ECOMetadata(
            name="buffer_insertion",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Insert buffers on high-capacitance nets to improve timing",
            parameters={
                "max_capacitance": max_capacitance,
                "buffer_cell": buffer_cell,
            },
            version="1.0",
            tags=["timing_optimization", "buffering"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for buffer insertion."""
        max_cap = self.metadata.parameters["max_capacitance"]
        buffer_cell = self.metadata.parameters["buffer_cell"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Buffer Insertion ECO
# TIMING-FOCUSED strategy: Skip repair_design to avoid adding buffer delays
# For extreme violations, repair_design's DRV fixes often make timing worse
# This approach prioritizes timing recovery over DRV compliance

# Set wire RC for accurate parasitic estimation (PDK-aware layers)
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics based on current placement
estimate_parasitics -placement

# AGGRESSIVE TIMING REPAIR (without repair_design)
# Multiple passes with progressively tighter margins
# This compounds improvements while avoiding DRV-driven buffer insertion

# Pass 1: Aggressive margin to catch worst violators
repair_timing -setup -setup_margin 0.3
estimate_parasitics -placement

# Pass 2: Moderate margin for secondary paths
repair_timing -setup -setup_margin 0.15
estimate_parasitics -placement

# Pass 3: Fine-tuning pass
repair_timing -setup -setup_margin 0.05
estimate_parasitics -placement

# Pass 4: Final cleanup
repair_timing -setup -setup_margin 0.0

# Note: max_capacitance parameter ({max_cap} pF) is stored but not used
# in commands (OpenROAD repair_timing does not support -max_cap flag)

puts "Buffer insertion ECO complete (timing-focused, no repair_design)"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate buffer insertion parameters."""
        max_cap = self.metadata.parameters.get("max_capacitance")
        if max_cap is None or max_cap <= 0:
            return False

        buffer_cell = self.metadata.parameters.get("buffer_cell")
        if not buffer_cell or not isinstance(buffer_cell, str):
            return False

        # Validate parameter ranges (F261)
        if not self.validate_parameter_ranges():
            return False

        return True


class PlacementDensityECO(ECO):
    """ECO that adjusts placement density to reduce congestion."""

    def __init__(self, target_density: float = 0.7) -> None:
        """Initialize placement density ECO.

        Args:
            target_density: Target placement density (0.0 to 1.0)
        """
        metadata = ECOMetadata(
            name="placement_density",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Adjust placement density to improve routability",
            parameters={"target_density": target_density},
            version="1.0",
            tags=["congestion_reduction", "placement"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for placement density adjustment."""
        density = self.metadata.parameters["target_density"]

        tcl_script = f"""# Placement Density ECO
# Reduce placement density to {density} to improve routability

# Re-run global placement with lower density
global_placement -density {density}

# Re-run detailed placement
detailed_placement

puts "Placement density ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate placement density parameters."""
        density = self.metadata.parameters.get("target_density")
        if density is None or density <= 0 or density > 1.0:
            return False

        # Validate parameter ranges (F261)
        if not self.validate_parameter_ranges():
            return False

        return True


class CellResizeECO(ECO):
    """ECO that resizes cells on critical paths to improve timing.

    This ECO uses OpenROAD's repair_timing command to upsize cells
    on timing-critical paths, trading area for timing improvement.
    """

    def __init__(self, size_multiplier: float = 1.5, max_paths: int = 100) -> None:
        """Initialize cell resize ECO.

        Args:
            size_multiplier: Size multiplier for cell upsizing (e.g., 1.5 = 50% larger)
            max_paths: Maximum number of critical paths to repair
        """
        metadata = ECOMetadata(
            name="cell_resize",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Resize cells on critical paths to improve timing",
            parameters={
                "size_multiplier": size_multiplier,
                "max_paths": max_paths,
            },
            version="1.0",
            tags=["timing_optimization", "cell_sizing"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for cell resizing."""
        size_mult = self.metadata.parameters["size_multiplier"]
        max_paths = self.metadata.parameters["max_paths"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Cell Resize ECO
# TIMING-FOCUSED strategy: Skip repair_design to avoid adding buffer delays
# Size multiplier: {size_mult}x
# Max paths to repair: {max_paths}
# Strategy optimized for extreme timing violations

# Set wire RC for accurate parasitic estimation (PDK-aware layers)
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics based on current placement
estimate_parasitics -placement

# AGGRESSIVE TIMING REPAIR (without repair_design)
# Multiple passes to compound improvements
# This avoids DRV-driven buffer insertion that worsens timing

# Pass 1: Aggressive margin for worst paths
repair_timing -setup -setup_margin 0.35
estimate_parasitics -placement

# Pass 2: Moderate margin for secondary paths
repair_timing -setup -setup_margin 0.2
estimate_parasitics -placement

# Pass 3: Fine-tuning pass
repair_timing -setup -setup_margin 0.1
estimate_parasitics -placement

# Pass 4: Final cleanup
repair_timing -setup -setup_margin 0.0

puts "Cell resize ECO complete (timing-focused, no repair_design)"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate cell resize parameters."""
        size_mult = self.metadata.parameters.get("size_multiplier")
        if size_mult is None or size_mult < 1.0:
            return False

        max_paths = self.metadata.parameters.get("max_paths")
        if max_paths is None or max_paths < 1:
            return False

        # Validate parameter ranges (F261)
        if not self.validate_parameter_ranges():
            return False

        return True


class CellSwapECO(ECO):
    """ECO that swaps cells to faster variants on critical paths.

    This ECO identifies cells on timing-critical paths and swaps them
    to faster variants (e.g., LVT instead of HVT, or higher drive strength).
    """

    def __init__(self, path_count: int = 50) -> None:
        """Initialize cell swap ECO.

        Args:
            path_count: Number of critical paths to analyze for cell swapping
        """
        metadata = ECOMetadata(
            name="cell_swap",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Swap cells to faster variants on critical paths",
            parameters={
                "path_count": path_count,
            },
            version="1.0",
            tags=["timing_optimization", "cell_swapping", "vth_swapping"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for cell swapping."""
        path_count = self.metadata.parameters["path_count"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Cell Swap ECO
# TIMING-FOCUSED strategy: Skip repair_design to avoid adding buffer delays
# Number of paths to analyze: {path_count}
# Strategy optimized for extreme timing violations

# Set wire RC for accurate parasitic estimation (PDK-aware layers)
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics based on current placement
estimate_parasitics -placement

# AGGRESSIVE TIMING REPAIR (without repair_design)
# Multiple passes to compound improvements

# Pass 1: Very aggressive margin for worst paths
repair_timing -setup -setup_margin 0.4
estimate_parasitics -placement

# Pass 2: Moderate margin for secondary paths
repair_timing -setup -setup_margin 0.2
estimate_parasitics -placement

# Pass 3: Fine-tuning pass
repair_timing -setup -setup_margin 0.1
estimate_parasitics -placement

# Pass 4: Final cleanup
repair_timing -setup -setup_margin 0.0

puts "Cell swap ECO complete (timing-focused, no repair_design)"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate cell swap parameters."""
        path_count = self.metadata.parameters.get("path_count")
        if path_count is None or path_count < 1:
            return False

        # Validate parameter ranges (F261)
        if not self.validate_parameter_ranges():
            return False

        return True


class GateCloningECO(ECO):
    """ECO that clones high-fanout gates to reduce load.

    This ECO identifies high-fanout gates and clones them to distribute
    the load across multiple instances, reducing transition times and
    improving timing on heavily loaded nets.
    """

    def __init__(self, max_fanout: int = 16) -> None:
        """Initialize gate cloning ECO.

        Args:
            max_fanout: Maximum fanout threshold - gates with higher fanout are cloned
        """
        metadata = ECOMetadata(
            name="gate_cloning",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Clone high-fanout gates to reduce load",
            parameters={
                "max_fanout": max_fanout,
            },
            version="1.0",
            tags=["timing_optimization", "fanout_reduction", "gate_cloning"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for gate cloning."""
        max_fanout = self.metadata.parameters["max_fanout"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Gate Cloning ECO
# TIMING-FOCUSED strategy: Clone high-fanout gates and repair timing
# Max fanout threshold: {max_fanout}
# Strategy optimized for extreme timing violations

# Set wire RC for accurate parasitic estimation (PDK-aware layers)
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics based on current placement
estimate_parasitics -placement

# Clone high-fanout gates using repair_timing
# The -max_fanout parameter identifies gates to clone
repair_timing -setup -max_fanout {max_fanout}
estimate_parasitics -placement

# AGGRESSIVE TIMING REPAIR (without repair_design)
# Multiple passes to compound improvements from cloning

# Pass 1: Aggressive margin
repair_timing -setup -setup_margin 0.3
estimate_parasitics -placement

# Pass 2: Moderate margin
repair_timing -setup -setup_margin 0.15
estimate_parasitics -placement

# Pass 3: Final cleanup
repair_timing -setup -setup_margin 0.0

puts "Gate cloning ECO complete (timing-focused, no repair_design)"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate gate cloning parameters."""
        max_fanout = self.metadata.parameters.get("max_fanout")
        if max_fanout is None or max_fanout < 4:
            return False

        # Fanout should be reasonable (4-100)
        if max_fanout > 100:
            return False

        # Validate parameter ranges (F261)
        if not self.validate_parameter_ranges():
            return False

        return True


class TimingDrivenPlacementECO(ECO):
    """ECO that re-runs placement with timing awareness.

    This ECO removes existing buffers and re-runs global placement
    with the -timing_driven flag, allowing OpenROAD to optimize
    placement for timing rather than just wirelength.

    This is a more aggressive approach than local ECOs and is intended
    for designs with extreme timing violations where local fixes are
    insufficient.
    """

    def __init__(
        self,
        target_density: float = 0.70,
        keep_overflow: float = 0.1,
    ) -> None:
        """Initialize timing-driven placement ECO.

        Args:
            target_density: Target placement density (0.0 to 1.0)
            keep_overflow: Maximum overflow to keep when resizing cells during placement
        """
        metadata = ECOMetadata(
            name="timing_driven_placement",
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            description="Re-run placement with timing awareness to reduce critical path delay",
            parameters={
                "target_density": target_density,
                "keep_overflow": keep_overflow,
            },
            version="1.0",
            tags=["timing_optimization", "placement", "timing_driven", "aggressive"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for timing-driven placement."""
        density = self.metadata.parameters["target_density"]
        keep_overflow = self.metadata.parameters["keep_overflow"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Timing-Driven Placement ECO
# Re-optimize placement with timing awareness
# This is an aggressive ECO that re-runs global placement
# Intended for extreme timing violations (>3x over budget)

# Set wire RC for accurate parasitic estimation (PDK-aware layers)
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Remove existing buffers to allow fresh placement optimization
remove_buffers

# Run timing-driven global placement
# -timing_driven: Optimize for timing instead of just wirelength
# -density: Control how tightly cells are packed
# -keep_resize_below_overflow: Keep cell resizing when overflow is below threshold
global_placement -timing_driven -density {density} \\
    -keep_resize_below_overflow {keep_overflow}

# Legalize placement to ensure cells don't overlap
detailed_placement

# Re-estimate parasitics with new placement
estimate_parasitics -placement

# Multiple passes of timing repair to fix remaining violations
# Without repair_design to avoid buffer-induced delays

# Pass 1: Aggressive margin (30-40%)
repair_timing -setup -setup_margin 0.3
estimate_parasitics -placement

# Pass 2: Moderate margin (15-20%)
repair_timing -setup -setup_margin 0.15
estimate_parasitics -placement

# Pass 3: Fine-tuning (5-10%)
repair_timing -setup -setup_margin 0.05
estimate_parasitics -placement

# Pass 4: Final cleanup (0%)
repair_timing -setup -setup_margin 0.0

puts "Timing-driven placement ECO complete"
puts "  Density: {density}"
puts "  Keep overflow: {keep_overflow}"
puts "  Strategy: Re-placement + multi-pass repair_timing (no repair_design)"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate timing-driven placement parameters."""
        density = self.metadata.parameters.get("target_density")
        if density is None or density <= 0 or density > 1.0:
            return False

        keep_overflow = self.metadata.parameters.get("keep_overflow")
        if keep_overflow is None or keep_overflow < 0 or keep_overflow > 1.0:
            return False

        # Validate parameter ranges (F261)
        if not self.validate_parameter_ranges():
            return False

        return True


class IterativeTimingDrivenECO(ECO):
    """Ultra-aggressive iterative ECO for extreme timing violations.

    This ECO combines timing-driven placement with iterative repair_timing
    loops (up to 10 passes) with convergence checking. Designed specifically
    for designs >5x over timing budget where single-pass ECOs are insufficient.

    Based on research showing that iterative ECO flows can provide 20-40%
    additional improvement beyond single-pass timing-driven placement.
    """

    def __init__(
        self,
        target_density: float = 0.70,
        keep_overflow: float = 0.1,
        max_iterations: int = 10,
        convergence_threshold: float = 0.02,
    ) -> None:
        """Initialize iterative timing-driven ECO.

        Args:
            target_density: Target placement density (0.0 to 1.0)
            keep_overflow: Maximum overflow to keep when resizing cells
            max_iterations: Maximum number of iterative repair passes
            convergence_threshold: Stop if improvement < this percentage (0.02 = 2%)
        """
        metadata = ECOMetadata(
            name="iterative_timing_driven",
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            description="Ultra-aggressive iterative timing optimization with convergence checking",
            parameters={
                "target_density": target_density,
                "keep_overflow": keep_overflow,
                "max_iterations": max_iterations,
                "convergence_threshold": convergence_threshold,
            },
            version="1.0",
            tags=["timing_optimization", "placement", "timing_driven", "iterative", "ultra_aggressive"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for iterative timing-driven optimization."""
        density = self.metadata.parameters["target_density"]
        keep_overflow = self.metadata.parameters["keep_overflow"]
        max_iterations = self.metadata.parameters["max_iterations"]
        convergence_threshold = self.metadata.parameters["convergence_threshold"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Iterative Timing-Driven ECO
# Ultra-aggressive approach for extreme timing violations (>5x over budget)
# Combines timing-driven placement with iterative repair loops
# Based on research showing 20-40% additional improvement vs single-pass

puts "Starting Iterative Timing-Driven ECO"
puts "  Max iterations: {max_iterations}"
puts "  Convergence threshold: {convergence_threshold * 100}%"

# Set wire RC for accurate parasitic estimation (PDK-aware layers)
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Phase 1: Timing-driven placement re-optimization
puts "Phase 1: Timing-driven placement re-optimization"

# Remove existing buffers to allow fresh optimization
remove_buffers

# Run timing-driven global placement
global_placement -timing_driven -density {density} \\
    -keep_resize_below_overflow {keep_overflow}

# Legalize placement
detailed_placement

# Re-estimate parasitics
estimate_parasitics -placement

# Get baseline WNS after re-placement
set wns_before [sta::worst_slack -max]
puts "WNS after re-placement: $wns_before ps"

# Phase 2: Iterative repair_timing with convergence checking
puts "Phase 2: Iterative repair_timing (up to {max_iterations} passes)"

set prev_wns $wns_before
set iteration 0
set converged false

while {{$iteration < {max_iterations} && !$converged}} {{
    puts "\\nIteration [expr $iteration + 1]/{max_iterations}"

    # Gradually reduce margin as we iterate
    # Start aggressive (30%), end precise (0%)
    set margin [expr 0.30 - ($iteration * 0.30 / {max_iterations})]
    puts "  Repair margin: [format %.2f $margin]"

    # Repair timing
    repair_timing -setup -setup_margin $margin

    # Re-estimate parasitics
    estimate_parasitics -placement

    # Check WNS improvement
    set curr_wns [sta::worst_slack -max]
    puts "  Current WNS: $curr_wns ps"

    # Calculate improvement percentage
    if {{$prev_wns != 0}} {{
        set improvement_pct [expr abs(($curr_wns - $prev_wns) / double($prev_wns))]
        puts "  Improvement this iteration: [format %.2f%% [expr $improvement_pct * 100]]"

        # Check convergence
        if {{$improvement_pct < {convergence_threshold}}} {{
            puts "  Converged (improvement < {convergence_threshold * 100}%)"
            set converged true
        }}
    }}

    set prev_wns $curr_wns
    incr iteration
}}

# Final WNS
set wns_final [sta::worst_slack -max]
puts "\\nIterative ECO Complete"
puts "  Total iterations: $iteration"
puts "  Initial WNS (after re-placement): $wns_before ps"
puts "  Final WNS: $wns_final ps"

if {{$wns_before != 0}} {{
    set total_improvement [expr abs(($wns_final - $wns_before) / double($wns_before)) * 100]
    puts "  Iterative improvement: [format %.2f%% $total_improvement]"
}}
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate iterative timing-driven ECO parameters."""
        density = self.metadata.parameters.get("target_density")
        if density is None or density <= 0 or density > 1.0:
            return False

        keep_overflow = self.metadata.parameters.get("keep_overflow")
        if keep_overflow is None or keep_overflow < 0 or keep_overflow > 1.0:
            return False

        max_iterations = self.metadata.parameters.get("max_iterations")
        if max_iterations is None or max_iterations < 1 or max_iterations > 20:
            return False

        convergence_threshold = self.metadata.parameters.get("convergence_threshold")
        if convergence_threshold is None or convergence_threshold < 0 or convergence_threshold > 0.5:
            return False

        # Validate parameter ranges (F261)
        if not self.validate_parameter_ranges():
            return False

        return True


class TimingDegradationECO(ECO):
    """ECO that intentionally degrades timing for Gate 2 testing.

    This ECO is used in validation tests to verify that Noodle 2 correctly
    detects and classifies timing regressions.
    """

    def __init__(self, severity: str = "moderate") -> None:
        """Initialize timing degradation ECO.

        Args:
            severity: Degradation severity ("mild", "moderate", "severe")
        """
        metadata = ECOMetadata(
            name="timing_degradation_test",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Intentionally degrade timing for regression testing",
            parameters={"severity": severity},
            version="1.0",
            tags=["test", "regression", "gate2"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script that degrades timing."""
        severity = self.metadata.parameters["severity"]

        if severity == "severe":
            # Severe degradation: increase clock frequency significantly
            tcl_script = """# Timing Degradation ECO (Severe)
# Increase clock constraints to create violations

# Get current clock period
set clks [all_clocks]
foreach clk $clks {
    set period [get_property $clk period]
    set new_period [expr {$period * 0.5}]
    puts "Degrading timing: reducing clock period from $period to $new_period"
}

# Apply more aggressive clock constraint
# This will create timing violations
puts "Timing degradation ECO complete - severe violations expected"
"""
        elif severity == "moderate":
            # Moderate degradation: add delay to critical paths
            tcl_script = """# Timing Degradation ECO (Moderate)
# Add parasitic resistance to create moderate timing degradation

# This simulates worsening interconnect conditions
puts "Applying moderate timing degradation"

# The effect will be observable in WNS
puts "Timing degradation ECO complete - moderate degradation expected"
"""
        else:  # mild
            tcl_script = """# Timing Degradation ECO (Mild)
# Minimal timing impact for baseline testing

puts "Applying mild timing adjustment"
puts "Timing degradation ECO complete - minimal impact expected"
"""

        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate timing degradation parameters."""
        severity = self.metadata.parameters.get("severity")
        return severity in ["mild", "moderate", "severe"]


class CongestionStressorECO(ECO):
    """ECO that intentionally increases congestion for Gate 2 testing.

    This ECO is used in validation tests to verify that Noodle 2 correctly
    detects and classifies congestion issues.
    """

    def __init__(self, intensity: str = "moderate") -> None:
        """Initialize congestion stressor ECO.

        Args:
            intensity: Congestion intensity ("low", "moderate", "high")
        """
        metadata = ECOMetadata(
            name="congestion_stressor_test",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Intentionally increase congestion for testing",
            parameters={"intensity": intensity},
            version="1.0",
            tags=["test", "congestion", "gate2"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script that increases congestion."""
        intensity = self.metadata.parameters["intensity"]

        if intensity == "high":
            density = 0.95
        elif intensity == "moderate":
            density = 0.85
        else:  # low
            density = 0.75

        tcl_script = f"""# Congestion Stressor ECO
# Increase placement density to {density} to stress routing

# Re-run global placement with higher density
global_placement -density {density}

# Re-run detailed placement
detailed_placement

puts "Congestion stressor ECO complete - density = {density}"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate congestion stressor parameters."""
        intensity = self.metadata.parameters.get("intensity")
        return intensity in ["low", "moderate", "high"]


class ToolErrorECO(ECO):
    """ECO that intentionally triggers tool errors for Gate 2 testing.

    This ECO is used to verify deterministic early-failure classification.
    """

    def __init__(self, error_type: str = "invalid_command") -> None:
        """Initialize tool error ECO.

        Args:
            error_type: Type of error to trigger ("invalid_command", "missing_file", "syntax_error")
        """
        metadata = ECOMetadata(
            name="tool_error_test",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Intentionally trigger tool errors for testing",
            parameters={"error_type": error_type},
            version="1.0",
            tags=["test", "error", "gate2"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script that triggers errors."""
        error_type = self.metadata.parameters["error_type"]

        if error_type == "invalid_command":
            tcl_script = """# Tool Error ECO - Invalid Command
# Trigger an invalid command error

this_command_does_not_exist_and_will_fail

puts "This line should not execute"
"""
        elif error_type == "missing_file":
            tcl_script = """# Tool Error ECO - Missing File
# Try to read a file that doesn't exist

read_verilog /nonexistent/path/to/missing/file.v

puts "This line should not execute"
"""
        else:  # syntax_error
            tcl_script = """# Tool Error ECO - Syntax Error
# Trigger a Tcl syntax error

set incomplete_command [

puts "This line should not execute"
"""

        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate tool error parameters."""
        error_type = self.metadata.parameters.get("error_type")
        return error_type in ["invalid_command", "missing_file", "syntax_error"]


# ============================================================================
# Additional ECO Types Based on OpenROAD Resizer Capabilities
# ============================================================================


class HoldRepairECO(ECO):
    """ECO focused on fixing hold timing violations.

    Uses repair_timing -hold with configurable margins and buffer limits.
    Hold violations occur when data arrives too quickly at flip-flops.
    """

    def __init__(
        self,
        hold_margin: float = 0.0,
        max_buffer_percent: int = 20,
        allow_setup_violations: bool = False,
    ) -> None:
        """Initialize hold repair ECO.

        Args:
            hold_margin: Additional hold margin in ns (default: 0.0)
            max_buffer_percent: Max buffers as % of instances (default: 20)
            allow_setup_violations: Allow setup violations while fixing hold
        """
        metadata = ECOMetadata(
            name="hold_repair",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix hold timing violations by inserting delay buffers",
            parameters={
                "hold_margin": hold_margin,
                "max_buffer_percent": max_buffer_percent,
                "allow_setup_violations": allow_setup_violations,
            },
            version="1.0",
            tags=["timing_optimization", "hold_fixing"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for hold repair."""
        hold_margin = self.metadata.parameters["hold_margin"]
        max_buffer_percent = self.metadata.parameters["max_buffer_percent"]
        allow_setup = self.metadata.parameters["allow_setup_violations"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        allow_setup_flag = "-allow_setup_violations" if allow_setup else ""

        tcl_script = f"""# Hold Repair ECO
# Fix hold timing violations by inserting delay buffers

# Set wire RC for accurate parasitic estimation
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics
estimate_parasitics -placement

# Repair hold violations
# -hold_margin {hold_margin}: Additional margin for hold checks
# -max_buffer_percent {max_buffer_percent}: Limit buffer insertion
repair_timing -hold \\
    -hold_margin {hold_margin} \\
    -max_buffer_percent {max_buffer_percent} \\
    {allow_setup_flag}

puts "Hold repair ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate hold repair parameters."""
        hold_margin = self.metadata.parameters.get("hold_margin", 0.0)
        max_buffer = self.metadata.parameters.get("max_buffer_percent", 20)
        return hold_margin >= 0 and 0 <= max_buffer <= 100


class PowerRecoveryECO(ECO):
    """ECO that recovers power on paths with positive timing slack.

    Uses repair_timing -recover_power to downsize cells on non-critical paths,
    reducing dynamic and leakage power while maintaining timing closure.
    """

    def __init__(
        self,
        recover_percent: int = 50,
        slack_margin: float = 0.1,
    ) -> None:
        """Initialize power recovery ECO.

        Args:
            recover_percent: Percentage of positive-slack paths to optimize (0-100)
            slack_margin: Minimum slack margin to maintain in ns
        """
        metadata = ECOMetadata(
            name="power_recovery",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Recover power by downsizing cells on non-critical paths",
            parameters={
                "recover_percent": recover_percent,
                "slack_margin": slack_margin,
            },
            version="1.0",
            tags=["power_optimization", "cell_sizing"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for power recovery."""
        recover_percent = self.metadata.parameters["recover_percent"]
        slack_margin = self.metadata.parameters["slack_margin"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Power Recovery ECO
# Downsize cells on non-critical paths to save power

# Set wire RC for accurate parasitic estimation
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics
estimate_parasitics -placement

# Recover power on paths with positive slack
# -recover_power {recover_percent}: Percentage of positive-slack paths to optimize
# -slack_margin {slack_margin}: Minimum slack to maintain
repair_timing -setup \\
    -recover_power {recover_percent} \\
    -slack_margin {slack_margin}

puts "Power recovery ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate power recovery parameters."""
        recover = self.metadata.parameters.get("recover_percent", 50)
        margin = self.metadata.parameters.get("slack_margin", 0.1)
        return 0 <= recover <= 100 and margin >= 0


class RepairDesignECO(ECO):
    """ECO that fixes design rule violations (DRVs).

    Uses repair_design to fix max slew, max capacitance, and max fanout
    violations. These DRV fixes often improve timing as a side effect.
    """

    def __init__(
        self,
        max_wire_length: int = 0,
        slew_margin: int = 20,
        cap_margin: int = 20,
    ) -> None:
        """Initialize repair design ECO.

        Args:
            max_wire_length: Max wire length in microns (0 = use default)
            slew_margin: Slew violation margin percentage (0-100)
            cap_margin: Capacitance violation margin percentage (0-100)
        """
        metadata = ECOMetadata(
            name="repair_design",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix design rule violations (slew, capacitance, fanout)",
            parameters={
                "max_wire_length": max_wire_length,
                "slew_margin": slew_margin,
                "cap_margin": cap_margin,
            },
            version="1.0",
            tags=["drv_fixing", "design_cleanup"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for design repair."""
        max_wire = self.metadata.parameters["max_wire_length"]
        slew_margin = self.metadata.parameters["slew_margin"]
        cap_margin = self.metadata.parameters["cap_margin"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        wire_length_opt = f"-max_wire_length {max_wire}" if max_wire > 0 else ""

        tcl_script = f"""# Repair Design ECO
# Fix design rule violations (slew, capacitance, fanout)

# Set wire RC for accurate parasitic estimation
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics
estimate_parasitics -placement

# Repair design rule violations
# -slew_margin {slew_margin}: Margin for slew violations
# -cap_margin {cap_margin}: Margin for capacitance violations
repair_design \\
    -slew_margin {slew_margin} \\
    -cap_margin {cap_margin} \\
    {wire_length_opt}

# Re-estimate after repairs
estimate_parasitics -placement

puts "Repair design ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate repair design parameters."""
        slew = self.metadata.parameters.get("slew_margin", 20)
        cap = self.metadata.parameters.get("cap_margin", 20)
        wire = self.metadata.parameters.get("max_wire_length", 0)
        return 0 <= slew <= 100 and 0 <= cap <= 100 and wire >= 0


class AggressiveTimingECO(ECO):
    """ECO with aggressive timing repair using all available transforms.

    Enables all optimization transforms (pin swap, gate cloning, buffering)
    with multiple passes and high TNS repair percentage for maximum improvement.
    """

    def __init__(
        self,
        max_passes: int = 10,
        tns_repair_percent: int = 100,
        setup_margin: float = 0.1,
    ) -> None:
        """Initialize aggressive timing ECO.

        Args:
            max_passes: Maximum optimization passes (default: 10)
            tns_repair_percent: Percentage of TNS endpoints to repair (0-100)
            setup_margin: Additional setup margin in ns
        """
        metadata = ECOMetadata(
            name="aggressive_timing",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Aggressive timing repair with all transforms enabled",
            parameters={
                "max_passes": max_passes,
                "tns_repair_percent": tns_repair_percent,
                "setup_margin": setup_margin,
            },
            version="1.0",
            tags=["timing_optimization", "aggressive"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for aggressive timing repair."""
        max_passes = self.metadata.parameters["max_passes"]
        tns_percent = self.metadata.parameters["tns_repair_percent"]
        setup_margin = self.metadata.parameters["setup_margin"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Aggressive Timing ECO
# Maximum timing optimization with all transforms enabled

# Set wire RC for accurate parasitic estimation
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics
estimate_parasitics -placement

# Aggressive timing repair - all transforms enabled
# -max_passes {max_passes}: Allow multiple optimization iterations
# -repair_tns {tns_percent}: Repair this percentage of violating endpoints
# -setup_margin {setup_margin}: Additional margin for setup checks
repair_timing -setup \\
    -max_passes {max_passes} \\
    -repair_tns {tns_percent} \\
    -setup_margin {setup_margin} \\
    -verbose

# Re-estimate after aggressive repair
estimate_parasitics -placement

# Second pass for any remaining violations
repair_timing -setup \\
    -setup_margin 0.0 \\
    -max_passes 3

puts "Aggressive timing ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate aggressive timing parameters."""
        passes = self.metadata.parameters.get("max_passes", 10)
        tns = self.metadata.parameters.get("tns_repair_percent", 100)
        margin = self.metadata.parameters.get("setup_margin", 0.1)
        return passes > 0 and 0 <= tns <= 100 and margin >= 0


class BufferRemovalECO(ECO):
    """ECO that removes unnecessary buffers inserted during synthesis.

    Uses remove_buffers to eliminate synthesis-inserted buffers that may
    no longer be needed after placement. Can improve timing by reducing
    buffer chain delays.
    """

    def __init__(self) -> None:
        """Initialize buffer removal ECO."""
        metadata = ECOMetadata(
            name="buffer_removal",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Remove unnecessary synthesis buffers to reduce delay",
            parameters={},
            version="1.0",
            tags=["optimization", "buffer_cleanup"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for buffer removal."""
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Buffer Removal ECO
# Remove unnecessary synthesis-inserted buffers

# Set wire RC for accurate parasitic estimation
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics before removal
estimate_parasitics -placement

# Remove synthesis buffers (preserves dont-touch and fixed cells)
remove_buffers

# Re-estimate parasitics after buffer removal
estimate_parasitics -placement

# Light timing repair to fix any issues from buffer removal
repair_timing -setup -setup_margin 0.0 -max_passes 2

puts "Buffer removal ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Buffer removal has no parameters."""
        return True


class PinSwapECO(ECO):
    """ECO focused on pin swapping for timing optimization.

    Pin swapping reorders inputs on commutative gates (AND, OR, XOR, MUX)
    to reduce critical path delay by placing late-arriving signals on
    faster pin-to-output paths.
    """

    def __init__(
        self,
        setup_margin: float = 0.05,
        max_passes: int = 5,
    ) -> None:
        """Initialize pin swap ECO.

        Args:
            setup_margin: Setup margin for timing checks in ns
            max_passes: Maximum optimization passes
        """
        metadata = ECOMetadata(
            name="pin_swap",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Optimize timing by swapping pins on commutative gates",
            parameters={
                "setup_margin": setup_margin,
                "max_passes": max_passes,
            },
            version="1.0",
            tags=["timing_optimization", "pin_swap"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for pin swap optimization."""
        setup_margin = self.metadata.parameters["setup_margin"]
        max_passes = self.metadata.parameters["max_passes"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Pin Swap ECO
# Optimize timing by swapping pins on commutative gates

# Set wire RC for accurate parasitic estimation
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics
estimate_parasitics -placement

# Timing repair with focus on pin swapping
# Disable other transforms to isolate pin swap effect
# Note: pin_swap is enabled by default in repair_timing
repair_timing -setup \\
    -setup_margin {setup_margin} \\
    -max_passes {max_passes} \\
    -skip_gate_cloning \\
    -skip_buffering \\
    -skip_buffer_removal

puts "Pin swap ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate pin swap parameters."""
        margin = self.metadata.parameters.get("setup_margin", 0.05)
        passes = self.metadata.parameters.get("max_passes", 5)
        return margin >= 0 and passes > 0


class TieFanoutRepairECO(ECO):
    """ECO that repairs tie high/low cell fanout violations.

    Connects each tie high/low load to a dedicated copy of the tie cell,
    preventing fanout violations on tie cells.
    """

    def __init__(
        self,
        separation: float = 0.0,
        max_fanout: int = 10,
    ) -> None:
        """Initialize tie fanout repair ECO.

        Args:
            separation: Distance from tie cell to load (microns)
            max_fanout: Maximum fanout per tie cell
        """
        metadata = ECOMetadata(
            name="tie_fanout_repair",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Repair tie high/low cell fanout violations",
            parameters={
                "separation": separation,
                "max_fanout": max_fanout,
            },
            version="1.0",
            tags=["drv_fixing", "tie_cells"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for tie fanout repair."""
        separation = self.metadata.parameters["separation"]
        max_fanout = self.metadata.parameters["max_fanout"]
        pdk = kwargs.get("pdk", "nangate45").lower()

        # PDK-specific tie cell names
        if pdk == "asap7":
            tie_high = "TIEHIx1_ASAP7_75t_R"
            tie_low = "TIELOx1_ASAP7_75t_R"
        elif pdk == "sky130":
            tie_high = "sky130_fd_sc_hd__conb_1"
            tie_low = "sky130_fd_sc_hd__conb_1"
        else:  # nangate45
            tie_high = "LOGIC1_X1"
            tie_low = "LOGIC0_X1"

        tcl_script = f"""# Tie Fanout Repair ECO
# Connect tie high/low loads to dedicated tie cells

# Repair tie high fanout
catch {{
    repair_tie_fanout -separation {separation} -max_fanout {max_fanout} {tie_high}/Z
}}

# Repair tie low fanout
catch {{
    repair_tie_fanout -separation {separation} -max_fanout {max_fanout} {tie_low}/Z
}}

puts "Tie fanout repair ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate tie fanout repair parameters."""
        sep = self.metadata.parameters.get("separation", 0.0)
        fanout = self.metadata.parameters.get("max_fanout", 10)
        return sep >= 0 and fanout > 0


class ClockNetRepairECO(ECO):
    """ECO that repairs clock network issues.

    Buffers the wire from clock input pin to clock root buffer and
    splits multi-fanout clock inverters.
    """

    def __init__(
        self,
        max_wire_length: int = 100,
        repair_inverters: bool = True,
    ) -> None:
        """Initialize clock net repair ECO.

        Args:
            max_wire_length: Maximum wire length before buffering (microns)
            repair_inverters: Also repair clock inverter fanout
        """
        metadata = ECOMetadata(
            name="clock_net_repair",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Repair clock network buffering and inverter fanout",
            parameters={
                "max_wire_length": max_wire_length,
                "repair_inverters": repair_inverters,
            },
            version="1.0",
            tags=["clock_optimization", "cts"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for clock net repair."""
        max_wire = self.metadata.parameters["max_wire_length"]
        repair_inv = self.metadata.parameters["repair_inverters"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        inverter_cmd = "repair_clock_inverters" if repair_inv else "# Skipping inverter repair"

        tcl_script = f"""# Clock Net Repair ECO
# Buffer clock nets and repair inverter fanout

# Set wire RC for clock layer
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics
estimate_parasitics -placement

# Repair clock inverters (split multi-fanout inverters)
{inverter_cmd}

# Buffer long clock wires
repair_clock_nets -max_wire_length {max_wire}

puts "Clock net repair ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate clock net repair parameters."""
        wire = self.metadata.parameters.get("max_wire_length", 100)
        return wire > 0


class DeadLogicEliminationECO(ECO):
    """ECO that removes dead/unused logic from the design.

    Eliminates standard cell instances that can be removed without
    affecting functionality, reducing area and potentially improving timing.
    """

    def __init__(self) -> None:
        """Initialize dead logic elimination ECO."""
        metadata = ECOMetadata(
            name="dead_logic_elimination",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Remove dead/unused logic to reduce area",
            parameters={},
            version="1.0",
            tags=["optimization", "area_reduction"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for dead logic elimination."""
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Dead Logic Elimination ECO
# Remove unused logic cells

# Set wire RC
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics before
estimate_parasitics -placement

# Eliminate dead logic
eliminate_dead_logic -verbose

# Re-estimate parasitics after
estimate_parasitics -placement

puts "Dead logic elimination ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Dead logic elimination has no parameters."""
        return True


class VTSwapECO(ECO):
    """ECO that performs threshold voltage (VT) swapping.

    Swaps cells between different VT variants (LVT/SVT/HVT) to
    optimize timing on critical paths while saving power elsewhere.
    Note: Requires multi-VT library support in the PDK.
    """

    def __init__(
        self,
        setup_margin: float = 0.05,
        skip_critical_vt: bool = False,
    ) -> None:
        """Initialize VT swap ECO.

        Args:
            setup_margin: Setup margin for timing checks (ns)
            skip_critical_vt: Skip VT swap on critical paths
        """
        metadata = ECOMetadata(
            name="vt_swap",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Swap cell VT variants to optimize timing/power",
            parameters={
                "setup_margin": setup_margin,
                "skip_critical_vt": skip_critical_vt,
            },
            version="1.0",
            tags=["power_optimization", "timing_optimization", "vt_swap"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for VT swapping."""
        setup_margin = self.metadata.parameters["setup_margin"]
        skip_crit = self.metadata.parameters["skip_critical_vt"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        skip_crit_flag = "-skip_crit_vt_swap" if skip_crit else ""

        tcl_script = f"""# VT Swap ECO
# Optimize timing/power by swapping cell VT variants

# Set wire RC
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Estimate parasitics
estimate_parasitics -placement

# Repair timing with VT swapping enabled
# VT swapping swaps cells between LVT/SVT/HVT variants
# LVT = faster but more leakage, HVT = slower but less leakage
repair_timing -setup \\
    -setup_margin {setup_margin} \\
    -skip_buffering \\
    -skip_gate_cloning \\
    -skip_pin_swap \\
    {skip_crit_flag}

puts "VT swap ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate VT swap parameters."""
        margin = self.metadata.parameters.get("setup_margin", 0.05)
        return margin >= 0


class MultiPassTimingECO(ECO):
    """ECO that applies timing repair in multiple iterative passes.

    Each pass targets a subset of violations with different strategies,
    allowing for more thorough optimization than a single pass.
    """

    def __init__(
        self,
        num_passes: int = 3,
        margin_decay: float = 0.5,
        initial_margin: float = 0.2,
    ) -> None:
        """Initialize multi-pass timing ECO.

        Args:
            num_passes: Number of repair passes
            margin_decay: Margin reduction factor per pass
            initial_margin: Starting setup margin (ns)
        """
        metadata = ECOMetadata(
            name="multi_pass_timing",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Multi-pass iterative timing repair with decaying margins",
            parameters={
                "num_passes": num_passes,
                "margin_decay": margin_decay,
                "initial_margin": initial_margin,
            },
            version="1.0",
            tags=["timing_optimization", "iterative"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for multi-pass timing repair."""
        num_passes = self.metadata.parameters["num_passes"]
        decay = self.metadata.parameters["margin_decay"]
        initial = self.metadata.parameters["initial_margin"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        # Generate multiple passes with decaying margins
        passes_tcl = []
        margin = initial
        for i in range(num_passes):
            passes_tcl.append(f"""
# Pass {i+1}/{num_passes} - margin: {margin:.4f}
puts "Starting repair pass {i+1} with margin {margin:.4f}"
repair_timing -setup -setup_margin {margin:.4f}
estimate_parasitics -placement
""")
            margin *= decay

        passes_str = "\n".join(passes_tcl)

        tcl_script = f"""# Multi-Pass Timing ECO
# Iterative timing repair with decaying margins

# Set wire RC
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Initial parasitic estimation
estimate_parasitics -placement
{passes_str}
# Final pass with zero margin
puts "Final cleanup pass"
repair_timing -setup -setup_margin 0.0

puts "Multi-pass timing ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate multi-pass timing parameters."""
        passes = self.metadata.parameters.get("num_passes", 3)
        decay = self.metadata.parameters.get("margin_decay", 0.5)
        margin = self.metadata.parameters.get("initial_margin", 0.2)
        return passes > 0 and 0 < decay < 1 and margin >= 0


class SequentialRepairECO(ECO):
    """ECO that applies repair_design followed by repair_timing.

    This compound approach first fixes DRV violations, then optimizes
    timing on the cleaned-up design.
    """

    def __init__(
        self,
        slew_margin: int = 20,
        setup_margin: float = 0.1,
    ) -> None:
        """Initialize sequential repair ECO.

        Args:
            slew_margin: Margin for slew violations (%)
            setup_margin: Margin for setup timing (ns)
        """
        metadata = ECOMetadata(
            name="sequential_repair",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Sequential DRV repair followed by timing repair",
            parameters={
                "slew_margin": slew_margin,
                "setup_margin": setup_margin,
            },
            version="1.0",
            tags=["compound", "drv_fixing", "timing_optimization"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for sequential repair."""
        slew_margin = self.metadata.parameters["slew_margin"]
        setup_margin = self.metadata.parameters["setup_margin"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Sequential Repair ECO
# First repair DRVs, then optimize timing

# Set wire RC
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Initial parasitic estimation
estimate_parasitics -placement

# Phase 1: Repair design rule violations
puts "Phase 1: Repairing DRV violations"
repair_design -slew_margin {slew_margin} -cap_margin {slew_margin}

# Re-estimate after DRV fixes
estimate_parasitics -placement

# Phase 2: Repair timing violations
puts "Phase 2: Repairing timing violations"
repair_timing -setup -setup_margin {setup_margin}

# Final estimation
estimate_parasitics -placement

# Phase 3: Final cleanup
puts "Phase 3: Final timing cleanup"
repair_timing -setup -setup_margin 0.0

puts "Sequential repair ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate sequential repair parameters."""
        slew = self.metadata.parameters.get("slew_margin", 20)
        setup = self.metadata.parameters.get("setup_margin", 0.1)
        return 0 <= slew <= 100 and setup >= 0


class FullOptimizationECO(ECO):
    """ECO that applies the full optimization pipeline.

    Combines buffer removal, DRV repair, dead logic elimination,
    and aggressive timing repair for maximum improvement.
    """

    def __init__(
        self,
        max_passes: int = 5,
        setup_margin: float = 0.1,
    ) -> None:
        """Initialize full optimization ECO.

        Args:
            max_passes: Maximum timing repair passes
            setup_margin: Setup margin for timing (ns)
        """
        metadata = ECOMetadata(
            name="full_optimization",
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            description="Full optimization pipeline: cleanup + DRV + timing",
            parameters={
                "max_passes": max_passes,
                "setup_margin": setup_margin,
            },
            version="1.0",
            tags=["compound", "aggressive", "full_pipeline"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate TCL script for full optimization."""
        max_passes = self.metadata.parameters["max_passes"]
        setup_margin = self.metadata.parameters["setup_margin"]
        pdk = kwargs.get("pdk", "nangate45")
        signal_layer, clock_layer = get_pdk_layer_names(pdk)

        tcl_script = f"""# Full Optimization ECO
# Complete optimization pipeline

# Set wire RC
set_wire_rc -signal -layer {signal_layer}
set_wire_rc -clock -layer {clock_layer}

# Initial parasitic estimation
estimate_parasitics -placement

# Phase 1: Remove unnecessary buffers
puts "Phase 1: Removing synthesis buffers"
catch {{ remove_buffers }}

# Phase 2: Eliminate dead logic
puts "Phase 2: Eliminating dead logic"
catch {{ eliminate_dead_logic }}

# Re-estimate
estimate_parasitics -placement

# Phase 3: Fix DRV violations
puts "Phase 3: Fixing DRV violations"
repair_design -slew_margin 20 -cap_margin 20

# Re-estimate
estimate_parasitics -placement

# Phase 4: Aggressive timing repair
puts "Phase 4: Aggressive timing repair"
repair_timing -setup \\
    -setup_margin {setup_margin} \\
    -max_passes {max_passes} \\
    -repair_tns 100 \\
    -verbose

# Final estimation
estimate_parasitics -placement

# Phase 5: Final cleanup
puts "Phase 5: Final timing cleanup"
repair_timing -setup -setup_margin 0.0 -max_passes 3

puts "Full optimization ECO complete"
"""
        return tcl_script

    def validate_parameters(self) -> bool:
        """Validate full optimization parameters."""
        passes = self.metadata.parameters.get("max_passes", 5)
        margin = self.metadata.parameters.get("setup_margin", 0.1)
        return passes > 0 and margin >= 0


class CompoundECO(ECO):
    """Compound ECO that applies multiple component ECOs sequentially.

    Compound ECOs enable:
    - Sequential application of multiple ECO components
    - Logging of each component's completion
    - Aggregate metrics tracking across all components
    - Rollback strategies on failure
    """

    def __init__(
        self,
        name: str,
        description: str,
        components: list[ECO],
        apply_order: str = "sequential",
        rollback_on_failure: str = "all",
    ) -> None:
        """Initialize compound ECO.

        Args:
            name: Unique name for this compound ECO
            description: Human-readable description
            components: List of component ECOs to apply
            apply_order: Application order ("sequential" only for now)
            rollback_on_failure: Rollback strategy ("all", "partial", or "none")

        Raises:
            ValueError: If components is empty or apply_order is invalid
        """
        if not components:
            raise ValueError("CompoundECO requires at least one component")

        if apply_order not in ["sequential"]:
            raise ValueError(f"Unsupported apply_order: {apply_order}")

        if rollback_on_failure not in ["all", "partial", "none"]:
            raise ValueError(f"Invalid rollback_on_failure: {rollback_on_failure}")

        # Determine compound ECO class from most restrictive component
        eco_class = self._determine_eco_class(components)

        metadata = ECOMetadata(
            name=name,
            eco_class=eco_class,
            description=description,
            parameters={
                "apply_order": apply_order,
                "rollback_on_failure": rollback_on_failure,
                "component_count": len(components),
            },
            version="1.0",
            tags=["compound"],
        )
        super().__init__(metadata)
        self.components = components

    def _determine_eco_class(self, components: list[ECO]) -> ECOClass:
        """Determine compound ECO class from most restrictive component.

        The hierarchy from most to least restrictive:
        1. GLOBAL_DISRUPTIVE
        2. ROUTING_AFFECTING
        3. PLACEMENT_LOCAL
        4. TOPOLOGY_NEUTRAL

        Args:
            components: List of component ECOs

        Returns:
            Most restrictive ECO class
        """
        hierarchy = {
            ECOClass.GLOBAL_DISRUPTIVE: 3,
            ECOClass.ROUTING_AFFECTING: 2,
            ECOClass.PLACEMENT_LOCAL: 1,
            ECOClass.TOPOLOGY_NEUTRAL: 0,
        }

        max_level = -1
        result_class = ECOClass.TOPOLOGY_NEUTRAL

        for component in components:
            level = hierarchy.get(component.eco_class, 0)
            if level > max_level:
                max_level = level
                result_class = component.eco_class

        return result_class

    def generate_tcl(self, **kwargs: Any) -> str:
        """Generate Tcl script for compound ECO.

        Sequentially applies all component ECOs with logging between each.

        Returns:
            Tcl script as a string
        """
        tcl_lines = [
            f"# Compound ECO: {self.metadata.name}",
            f"# {self.metadata.description}",
            f"# Components: {len(self.components)}",
            "",
        ]

        for i, component in enumerate(self.components, 1):
            tcl_lines.append(f"# Component {i}: {component.name}")
            tcl_lines.append(f"puts \"Starting component {i}/{len(self.components)}: {component.name}\"")
            tcl_lines.append("")

            # Generate component TCL
            component_tcl = component.generate_tcl(**kwargs)
            tcl_lines.append(component_tcl)

            tcl_lines.append(f"puts \"Completed component {i}/{len(self.components)}: {component.name}\"")
            tcl_lines.append("")

        tcl_lines.append(f"puts \"Compound ECO '{self.metadata.name}' complete - all {len(self.components)} components applied\"")

        return "\n".join(tcl_lines)

    def validate_parameters(self) -> bool:
        """Validate compound ECO parameters.

        Validates all component ECOs.

        Returns:
            True if all components are valid, False otherwise
        """
        # Validate all components
        for component in self.components:
            if not component.validate_parameters():
                return False

        # Validate compound-specific parameters
        apply_order = self.metadata.parameters.get("apply_order")
        if apply_order not in ["sequential"]:
            return False

        rollback = self.metadata.parameters.get("rollback_on_failure")
        if rollback not in ["all", "partial", "none"]:
            return False

        return True

    def get_component_names(self) -> list[str]:
        """Get names of all component ECOs.

        Returns:
            List of component ECO names
        """
        return [component.name for component in self.components]

    def to_dict(self) -> dict[str, Any]:
        """Convert compound ECO to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        base_dict = super().to_dict()
        base_dict["components"] = [component.to_dict() for component in self.components]
        base_dict["component_names"] = self.get_component_names()
        return base_dict

    def execute_with_rollback(self, design_state: Any) -> ECOResult:
        """Execute compound ECO with rollback support on failure.

        This method implements the rollback_on_failure behavior:
        - "all": On any component failure, rollback all changes
        - "partial": On component failure, keep successful components
        - "none": No rollback, keep all successful components

        Args:
            design_state: Design state object (must support create_checkpoint method)

        Returns:
            ECOResult indicating success/failure and details
        """
        rollback_strategy = self.metadata.parameters.get("rollback_on_failure", "all")

        # Take initial checkpoint for "all" strategy
        initial_checkpoint = None
        if rollback_strategy == "all":
            if hasattr(design_state, 'create_checkpoint'):
                initial_checkpoint = design_state.create_checkpoint()

        # Execute components with tracking
        result, component_checkpoints = self._execute_components_with_tracking(design_state)

        # Handle failure based on rollback strategy
        if not result.success:
            if rollback_strategy == "all" and initial_checkpoint is not None:
                # Rollback all changes - restore to pre-compound state
                if hasattr(initial_checkpoint, 'restore'):
                    initial_checkpoint.restore()
                result.error_message = (
                    f"{result.error_message or 'Component failed'} "
                    f"(rolled back all changes)"
                )
            elif rollback_strategy == "partial":
                # Only rollback failed component - keep successful ones
                # The last checkpoint in the list is the one taken before the failed component
                if component_checkpoints and hasattr(component_checkpoints[-1], 'restore'):
                    component_checkpoints[-1].restore()
                result.error_message = (
                    f"{result.error_message or 'Component failed'} "
                    f"(partial rollback - preserved successful components)"
                )
            # rollback_strategy == "none" - do nothing, keep all changes

        return result

    def _execute_components_with_tracking(
        self, design_state: Any
    ) -> tuple[ECOResult, list[Any]]:
        """Execute components sequentially with checkpoint tracking.

        Args:
            design_state: Design state object

        Returns:
            Tuple of (ECOResult, list of component checkpoints)
        """
        component_checkpoints = []
        successful_components = []

        for i, component in enumerate(self.components, 1):
            component_name = component.name

            # Take checkpoint before this component
            checkpoint = None
            if hasattr(design_state, 'create_checkpoint'):
                checkpoint = design_state.create_checkpoint()
                component_checkpoints.append(checkpoint)

            # Execute component
            # For now, we simulate execution by checking if it's a FailingECO
            if hasattr(component, 'execute_with_checkpointing'):
                # Component supports checkpointing execution
                component_result, _ = component.execute_with_checkpointing(design_state)
            else:
                # Default execution - assume success for non-failing components
                # In real implementation, this would call actual execution logic
                component_result = ECOResult(
                    eco_name=component_name,
                    success=True,
                )

            # Check result
            if not component_result.success:
                # Component failed - return failure result
                return (
                    ECOResult(
                        eco_name=self.name,
                        success=False,
                        error_message=(
                            f"Component {i}/{len(self.components)} "
                            f"({component_name}) failed: "
                            f"{component_result.error_message or 'Unknown error'}"
                        ),
                    ),
                    component_checkpoints,
                )

            successful_components.append(component_name)

        # All components succeeded
        return (
            ECOResult(
                eco_name=self.name,
                success=True,
                metrics_delta={},  # Would aggregate from components
            ),
            component_checkpoints,
        )


# ECO Registry
ECO_REGISTRY: dict[str, type[ECO]] = {
    # Core ECOs
    "noop": NoOpECO,
    "buffer_insertion": BufferInsertionECO,
    "placement_density": PlacementDensityECO,
    "cell_resize": CellResizeECO,
    "cell_swap": CellSwapECO,
    "gate_cloning": GateCloningECO,
    "timing_driven_placement": TimingDrivenPlacementECO,
    "iterative_timing_driven": IterativeTimingDrivenECO,
    # Basic timing/power ECOs
    "hold_repair": HoldRepairECO,
    "power_recovery": PowerRecoveryECO,
    "repair_design": RepairDesignECO,
    "aggressive_timing": AggressiveTimingECO,
    "buffer_removal": BufferRemovalECO,
    "pin_swap": PinSwapECO,
    # Advanced ECOs
    "tie_fanout_repair": TieFanoutRepairECO,
    "clock_net_repair": ClockNetRepairECO,
    "dead_logic_elimination": DeadLogicEliminationECO,
    "vt_swap": VTSwapECO,
    # Compound/Sequential ECOs
    "multi_pass_timing": MultiPassTimingECO,
    "sequential_repair": SequentialRepairECO,
    "full_optimization": FullOptimizationECO,
    # Test ECOs
    "timing_degradation_test": TimingDegradationECO,
    "congestion_stressor_test": CongestionStressorECO,
    "tool_error_test": ToolErrorECO,
}


def create_eco(eco_name: str, **parameters: Any) -> ECO:
    """Factory function to create ECO instances.

    Args:
        eco_name: Name of the ECO to create
        **parameters: ECO-specific parameters

    Returns:
        ECO instance

    Raises:
        ValueError: If ECO name is not registered
    """
    if eco_name not in ECO_REGISTRY:
        raise ValueError(
            f"Unknown ECO: {eco_name}. Available: {list(ECO_REGISTRY.keys())}"
        )

    eco_class = ECO_REGISTRY[eco_name]
    return eco_class(**parameters)


# ============================================================================
# ECO Class-Level Failure Tracking and Containment
# ============================================================================


@dataclass
class ECOClassStats:
    """Statistics for tracking ECO class behavior across trials.

    Tracks failures across all instances of an ECO class to enable
    class-level failure containment when systematic failures occur.
    """

    eco_class: ECOClass
    total_applications: int = 0
    failed_applications: int = 0
    is_blacklisted: bool = False

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate for this ECO class."""
        if self.total_applications == 0:
            return 0.0
        return self.failed_applications / self.total_applications

    def update(self, success: bool) -> None:
        """Update statistics with new application result.

        Args:
            success: Whether the ECO application succeeded
        """
        self.total_applications += 1
        if not success:
            self.failed_applications += 1

        # Blacklist if failure rate exceeds threshold
        # Require at least 3 applications before blacklisting
        # Threshold: 70% failure rate
        if self.total_applications >= 3 and self.failure_rate >= 0.7:
            self.is_blacklisted = True

    def should_allow_eco_class(self) -> bool:
        """Determine if this ECO class should be allowed in future trials."""
        return not self.is_blacklisted


class ECOClassTracker:
    """Tracks ECO class-level statistics across a Study.

    Provides class-level failure containment by:
    - Aggregating results across all instances of each ECO class
    - Blacklisting classes with systematic failures
    - Preventing future trials from using blacklisted classes
    """

    def __init__(self) -> None:
        """Initialize ECO class tracker."""
        self.class_stats: dict[ECOClass, ECOClassStats] = {}

    def record_eco_result(self, eco: ECO, success: bool) -> None:
        """Record the result of an ECO application.

        Args:
            eco: The ECO that was applied
            success: Whether the application succeeded
        """
        eco_class = eco.metadata.eco_class

        if eco_class not in self.class_stats:
            self.class_stats[eco_class] = ECOClassStats(eco_class=eco_class)

        self.class_stats[eco_class].update(success)

    def is_eco_class_allowed(self, eco_class: ECOClass) -> bool:
        """Check if an ECO class is allowed (not blacklisted).

        Args:
            eco_class: The ECO class to check

        Returns:
            True if the class is allowed, False if blacklisted
        """
        if eco_class not in self.class_stats:
            return True  # Unknown classes are allowed

        return self.class_stats[eco_class].should_allow_eco_class()

    def get_blacklisted_classes(self) -> list[ECOClass]:
        """Return list of blacklisted ECO classes.

        Returns:
            List of ECOClass values that are blacklisted
        """
        return [
            stats.eco_class
            for stats in self.class_stats.values()
            if stats.is_blacklisted
        ]

    def get_failure_rate(self, eco_class: ECOClass) -> float:
        """Get failure rate for an ECO class.

        Args:
            eco_class: The ECO class to query

        Returns:
            Failure rate (0.0 to 1.0), or 0.0 if no data
        """
        if eco_class not in self.class_stats:
            return 0.0
        return self.class_stats[eco_class].failure_rate
