"""ECO risk envelope constraints for blast radius control.

This module provides:
- Risk envelope definitions (max cells, area delta, etc.)
- Envelope violation detection and classification
- Policy-driven handling of envelope violations
- Auditability for safety-critical ECO containment
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ViolationType(str, Enum):
    """Type of risk envelope violation."""

    CELLS_AFFECTED = "cells_affected"
    AREA_DELTA = "area_delta"
    WIRELENGTH_DELTA = "wirelength_delta"
    TIMING_DEGRADATION = "timing_degradation"


class ViolationSeverity(str, Enum):
    """Severity of risk envelope violation."""

    MINOR = "minor"  # < 10% over limit
    MODERATE = "moderate"  # 10-50% over limit
    MAJOR = "major"  # > 50% over limit


@dataclass
class RiskEnvelope:
    """Risk envelope constraints for an ECO.

    Defines maximum allowed blast radius for ECO execution.

    Attributes:
        max_cells_affected: Maximum number of cells that can be modified
        max_area_delta_percent: Maximum area increase/decrease (percentage)
        max_wirelength_delta_percent: Maximum wirelength change (percentage)
        max_timing_degradation_ps: Maximum WNS degradation allowed (picoseconds)
    """

    max_cells_affected: int | None = None
    max_area_delta_percent: float | None = None
    max_wirelength_delta_percent: float | None = None
    max_timing_degradation_ps: int | None = None

    def __post_init__(self) -> None:
        """Validate risk envelope constraints."""
        if self.max_cells_affected is not None and self.max_cells_affected < 0:
            raise ValueError("max_cells_affected must be non-negative")
        if self.max_area_delta_percent is not None and self.max_area_delta_percent < 0:
            raise ValueError("max_area_delta_percent must be non-negative")
        if (
            self.max_wirelength_delta_percent is not None
            and self.max_wirelength_delta_percent < 0
        ):
            raise ValueError("max_wirelength_delta_percent must be non-negative")
        if (
            self.max_timing_degradation_ps is not None
            and self.max_timing_degradation_ps < 0
        ):
            raise ValueError("max_timing_degradation_ps must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "max_cells_affected": self.max_cells_affected,
            "max_area_delta_percent": self.max_area_delta_percent,
            "max_wirelength_delta_percent": self.max_wirelength_delta_percent,
            "max_timing_degradation_ps": self.max_timing_degradation_ps,
        }


@dataclass
class ECOImpact:
    """Measured impact of an ECO execution.

    Attributes:
        cells_affected: Number of cells modified
        area_delta_um2: Absolute area change (um^2)
        area_delta_percent: Area change as percentage of baseline
        wirelength_delta_um: Absolute wirelength change (um)
        wirelength_delta_percent: Wirelength change as percentage of baseline
        wns_delta_ps: Change in WNS (negative = degradation)
    """

    cells_affected: int = 0
    area_delta_um2: float = 0.0
    area_delta_percent: float = 0.0
    wirelength_delta_um: float = 0.0
    wirelength_delta_percent: float = 0.0
    wns_delta_ps: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "cells_affected": self.cells_affected,
            "area_delta_um2": self.area_delta_um2,
            "area_delta_percent": self.area_delta_percent,
            "wirelength_delta_um": self.wirelength_delta_um,
            "wirelength_delta_percent": self.wirelength_delta_percent,
            "wns_delta_ps": self.wns_delta_ps,
        }


@dataclass
class EnvelopeViolation:
    """Record of a risk envelope violation.

    Attributes:
        violation_type: Type of constraint that was violated
        severity: Severity classification of the violation
        limit: The envelope limit that was exceeded
        actual: The actual measured value
        percent_over: How much the limit was exceeded (percentage)
        message: Human-readable violation description
    """

    violation_type: ViolationType
    severity: ViolationSeverity
    limit: float
    actual: float
    percent_over: float
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "violation_type": self.violation_type.value,
            "severity": self.severity.value,
            "limit": self.limit,
            "actual": self.actual,
            "percent_over": self.percent_over,
            "message": self.message,
        }


@dataclass
class EnvelopeCheckResult:
    """Result of checking ECO impact against risk envelope.

    Attributes:
        passed: Whether all envelope constraints were satisfied
        violations: List of detected violations
        impact: Measured ECO impact
        envelope: The risk envelope that was checked against
    """

    passed: bool
    violations: list[EnvelopeViolation] = field(default_factory=list)
    impact: ECOImpact | None = None
    envelope: RiskEnvelope | None = None

    @property
    def violation_count(self) -> int:
        """Get total number of violations."""
        return len(self.violations)

    @property
    def has_major_violations(self) -> bool:
        """Check if any violations are major severity."""
        return any(v.severity == ViolationSeverity.MAJOR for v in self.violations)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "passed": self.passed,
            "violation_count": self.violation_count,
            "has_major_violations": self.has_major_violations,
            "violations": [v.to_dict() for v in self.violations],
            "impact": self.impact.to_dict() if self.impact else None,
            "envelope": self.envelope.to_dict() if self.envelope else None,
        }


def classify_violation_severity(limit: float, actual: float) -> ViolationSeverity:
    """Classify severity of envelope violation.

    Args:
        limit: The envelope limit
        actual: The actual measured value

    Returns:
        Severity classification
    """
    if limit == 0:
        # Avoid division by zero; any violation is major
        return ViolationSeverity.MAJOR

    percent_over = ((actual - limit) / limit) * 100

    if percent_over < 10:
        return ViolationSeverity.MINOR
    elif percent_over <= 50:  # Changed from < to <=
        return ViolationSeverity.MODERATE
    else:
        return ViolationSeverity.MAJOR


def check_risk_envelope(
    impact: ECOImpact, envelope: RiskEnvelope
) -> EnvelopeCheckResult:
    """Check ECO impact against risk envelope constraints.

    Args:
        impact: Measured impact of ECO execution
        envelope: Risk envelope constraints to check against

    Returns:
        Result indicating pass/fail and any violations
    """
    violations: list[EnvelopeViolation] = []

    # Check cells affected
    if envelope.max_cells_affected is not None:
        if impact.cells_affected > envelope.max_cells_affected:
            severity = classify_violation_severity(
                envelope.max_cells_affected, impact.cells_affected
            )
            percent_over = (
                (impact.cells_affected - envelope.max_cells_affected)
                / envelope.max_cells_affected
                * 100
            )
            violations.append(
                EnvelopeViolation(
                    violation_type=ViolationType.CELLS_AFFECTED,
                    severity=severity,
                    limit=envelope.max_cells_affected,
                    actual=impact.cells_affected,
                    percent_over=percent_over,
                    message=f"Cells affected ({impact.cells_affected}) exceeds limit ({envelope.max_cells_affected}) by {percent_over:.1f}%",
                )
            )

    # Check area delta
    if envelope.max_area_delta_percent is not None:
        abs_area_delta = abs(impact.area_delta_percent)
        if abs_area_delta > envelope.max_area_delta_percent:
            severity = classify_violation_severity(
                envelope.max_area_delta_percent, abs_area_delta
            )
            percent_over = (
                (abs_area_delta - envelope.max_area_delta_percent)
                / envelope.max_area_delta_percent
                * 100
            )
            violations.append(
                EnvelopeViolation(
                    violation_type=ViolationType.AREA_DELTA,
                    severity=severity,
                    limit=envelope.max_area_delta_percent,
                    actual=abs_area_delta,
                    percent_over=percent_over,
                    message=f"Area delta ({abs_area_delta:.1f}%) exceeds limit ({envelope.max_area_delta_percent}%) by {percent_over:.1f}%",
                )
            )

    # Check wirelength delta
    if envelope.max_wirelength_delta_percent is not None:
        abs_wl_delta = abs(impact.wirelength_delta_percent)
        if abs_wl_delta > envelope.max_wirelength_delta_percent:
            severity = classify_violation_severity(
                envelope.max_wirelength_delta_percent, abs_wl_delta
            )
            percent_over = (
                (abs_wl_delta - envelope.max_wirelength_delta_percent)
                / envelope.max_wirelength_delta_percent
                * 100
            )
            violations.append(
                EnvelopeViolation(
                    violation_type=ViolationType.WIRELENGTH_DELTA,
                    severity=severity,
                    limit=envelope.max_wirelength_delta_percent,
                    actual=abs_wl_delta,
                    percent_over=percent_over,
                    message=f"Wirelength delta ({abs_wl_delta:.1f}%) exceeds limit ({envelope.max_wirelength_delta_percent}%) by {percent_over:.1f}%",
                )
            )

    # Check timing degradation (negative WNS delta = degradation)
    if envelope.max_timing_degradation_ps is not None:
        if impact.wns_delta_ps < 0:  # Degradation (negative delta)
            degradation_ps = abs(impact.wns_delta_ps)
            if degradation_ps > envelope.max_timing_degradation_ps:
                severity = classify_violation_severity(
                    envelope.max_timing_degradation_ps, degradation_ps
                )
                percent_over = (
                    (degradation_ps - envelope.max_timing_degradation_ps)
                    / envelope.max_timing_degradation_ps
                    * 100
                )
                violations.append(
                    EnvelopeViolation(
                        violation_type=ViolationType.TIMING_DEGRADATION,
                        severity=severity,
                        limit=envelope.max_timing_degradation_ps,
                        actual=degradation_ps,
                        percent_over=percent_over,
                        message=f"Timing degradation ({degradation_ps}ps) exceeds limit ({envelope.max_timing_degradation_ps}ps) by {percent_over:.1f}%",
                    )
                )

    return EnvelopeCheckResult(
        passed=len(violations) == 0,
        violations=violations,
        impact=impact,
        envelope=envelope,
    )


def should_abort_eco(check_result: EnvelopeCheckResult, policy: str = "strict") -> bool:
    """Determine if ECO should be aborted based on envelope violations.

    Args:
        check_result: Result of envelope check
        policy: Abort policy ("strict", "moderate", "lenient")

    Returns:
        True if ECO should be aborted, False otherwise
    """
    if check_result.passed:
        return False

    if policy == "strict":
        # Abort on any violation
        return check_result.violation_count > 0
    elif policy == "moderate":
        # Abort only on major violations
        return check_result.has_major_violations
    elif policy == "lenient":
        # Only abort on multiple major violations
        major_count = sum(
            1 for v in check_result.violations if v.severity == ViolationSeverity.MAJOR
        )
        return major_count >= 2
    else:
        raise ValueError(f"Unknown policy: {policy}")
