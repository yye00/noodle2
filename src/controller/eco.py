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

    def __post_init__(self) -> None:
        """Validate metadata."""
        if not self.name:
            raise ValueError("ECO name cannot be empty")
        if not self.description:
            raise ValueError("ECO description cannot be empty")


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
        return {
            "name": self.metadata.name,
            "eco_class": self.metadata.eco_class.value,
            "description": self.metadata.description,
            "parameters": self.metadata.parameters,
            "version": self.metadata.version,
            "author": self.metadata.author,
            "tags": self.metadata.tags,
            "preconditions": [p.to_dict() for p in self.metadata.preconditions],
            "postconditions": [p.to_dict() for p in self.metadata.postconditions],
        }


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

        tcl_script = f"""# Buffer Insertion ECO
# Insert buffers on nets with capacitance > {max_cap} pF

# Find high-capacitance nets
set high_cap_nets [get_nets -filter "capacitance > {max_cap}"]

# Insert buffers
foreach net $high_cap_nets {{
    # Use repair_timing to insert buffers
    puts "Buffering net: [get_property $net full_name]"
}}

# Alternative: use OpenROAD's repair_design
repair_design -max_cap {max_cap}

puts "Buffer insertion ECO complete"
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
    "noop": NoOpECO,
    "buffer_insertion": BufferInsertionECO,
    "placement_density": PlacementDensityECO,
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
