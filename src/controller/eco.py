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
from typing import Any

from .types import ECOClass


class ECOPrior(str, Enum):
    """Prior confidence level for ECO effectiveness based on historical evidence."""

    UNKNOWN = "unknown"  # No history
    TRUSTED = "trusted"  # Consistently helpful
    MIXED = "mixed"  # Sometimes helpful, sometimes not
    SUSPICIOUS = "suspicious"  # Frequently problematic
    BLACKLISTED = "blacklisted"  # Explicitly forbidden


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

    def _update_prior(self) -> None:
        """Update prior classification based on accumulated evidence."""
        if self.total_applications < 3:
            # Not enough evidence
            self.prior = ECOPrior.UNKNOWN
            return

        success_rate = self.successful_applications / self.total_applications

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


# ECO Registry
ECO_REGISTRY: dict[str, type[ECO]] = {
    "noop": NoOpECO,
    "buffer_insertion": BufferInsertionECO,
    "placement_density": PlacementDensityECO,
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
