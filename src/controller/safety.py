"""Safety model and legality checking for Noodle 2."""

from dataclasses import dataclass, field
from typing import Any, Optional

from .study import StudyConfig
from .types import ECOClass, RailsConfig, SafetyDomain, StageConfig


# Safety policy: which ECO classes are allowed in each safety domain
SAFETY_POLICY: dict[SafetyDomain, list[ECOClass]] = {
    SafetyDomain.SANDBOX: [
        # Exploratory, permissive - all ECO classes allowed
        ECOClass.TOPOLOGY_NEUTRAL,
        ECOClass.PLACEMENT_LOCAL,
        ECOClass.ROUTING_AFFECTING,
        ECOClass.GLOBAL_DISRUPTIVE,
    ],
    SafetyDomain.GUARDED: [
        # Default, production-like - no global disruption
        ECOClass.TOPOLOGY_NEUTRAL,
        ECOClass.PLACEMENT_LOCAL,
        ECOClass.ROUTING_AFFECTING,
    ],
    SafetyDomain.LOCKED: [
        # Conservative, regression-only - only safe changes
        ECOClass.TOPOLOGY_NEUTRAL,
        ECOClass.PLACEMENT_LOCAL,
    ],
}


@dataclass
class SafetyViolation:
    """A specific safety violation in a Study configuration."""

    stage_index: int
    stage_name: str
    eco_class: ECOClass
    reason: str
    severity: str = "error"  # "error" or "warning"


@dataclass
class LegalityCheckResult:
    """Result of checking Study legality."""

    is_legal: bool
    safety_domain: SafetyDomain
    violations: list[SafetyViolation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_violations(self) -> bool:
        """Check if there are any violations."""
        return len(self.violations) > 0

    @property
    def violation_count(self) -> int:
        """Count total violations."""
        return len(self.violations)


class LegalityChecker:
    """
    Validates Study configurations against safety policies.

    Ensures that proposed ECO classes are legal for the declared
    safety domain before consuming compute.
    """

    def __init__(self, study: StudyConfig):
        """
        Initialize legality checker.

        Args:
            study: Study configuration to validate
        """
        self.study = study
        self.safety_domain = study.safety_domain

    def check_legality(self) -> LegalityCheckResult:
        """
        Check if Study configuration is legal.

        Returns:
            LegalityCheckResult with violations if illegal
        """
        allowed_classes = SAFETY_POLICY.get(
            self.safety_domain,
            []
        )

        violations = []
        warnings = []

        # Check each stage's allowed ECO classes
        for stage_idx, stage in enumerate(self.study.stages):
            for eco_class in stage.allowed_eco_classes:
                if eco_class not in allowed_classes:
                    violations.append(
                        SafetyViolation(
                            stage_index=stage_idx,
                            stage_name=stage.name,
                            eco_class=eco_class,
                            reason=(
                                f"ECO class '{eco_class.value}' is not allowed "
                                f"in safety domain '{self.safety_domain.value}'"
                            ),
                            severity="error",
                        )
                    )

            # Add warnings for risky configurations
            if (
                ECOClass.GLOBAL_DISRUPTIVE in stage.allowed_eco_classes
                and self.safety_domain == SafetyDomain.SANDBOX
            ):
                warnings.append(
                    f"Stage {stage_idx} ({stage.name}): GLOBAL_DISRUPTIVE ECO class "
                    f"enabled in SANDBOX mode - use with caution"
                )

        is_legal = len(violations) == 0

        return LegalityCheckResult(
            is_legal=is_legal,
            safety_domain=self.safety_domain,
            violations=violations,
            warnings=warnings,
        )

    def get_allowed_eco_classes(self) -> list[ECOClass]:
        """Get list of ECO classes allowed for this safety domain."""
        return SAFETY_POLICY.get(self.safety_domain, [])


@dataclass
class RunLegalityReport:
    """
    Human-readable legality report for a Study.

    This report is generated before Study execution and serves as
    an audit record of the safety policy check.
    """

    study_name: str
    safety_domain: SafetyDomain
    is_legal: bool
    allowed_eco_classes: list[ECOClass]
    violations: list[SafetyViolation]
    warnings: list[str]
    stage_count: int
    total_trial_budget: int
    rails: Optional[RailsConfig] = None
    timestamp: Optional[str] = None

    def __str__(self) -> str:
        """Generate human-readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append("RUN LEGALITY REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Study info
        lines.append(f"Study: {self.study_name}")
        if self.timestamp:
            lines.append(f"Timestamp: {self.timestamp}")
        lines.append("")

        # Safety domain
        lines.append("SAFETY DOMAIN")
        lines.append(f"  Domain: {self.safety_domain.value}")
        lines.append("")

        # Allowed ECO classes
        lines.append("ALLOWED ECO CLASSES")
        for eco_class in self.allowed_eco_classes:
            lines.append(f"  ✓ {eco_class.value}")
        lines.append("")

        # Violations
        lines.append("VIOLATIONS")
        if not self.violations:
            lines.append("  None - configuration is legal")
        else:
            for violation in self.violations:
                lines.append(
                    f"  ✗ Stage {violation.stage_index} ({violation.stage_name}): "
                    f"{violation.eco_class.value}"
                )
                lines.append(f"    Reason: {violation.reason}")
        lines.append("")

        # Warnings
        if self.warnings:
            lines.append("WARNINGS")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        # Rails (abort criteria)
        if self.rails:
            lines.append("ABORT CRITERIA (RAILS)")
            lines.append("  Abort Rail (trial-level):")
            if self.rails.abort.wns_ps is not None:
                lines.append(f"    - WNS threshold: {self.rails.abort.wns_ps} ps")
            if self.rails.abort.timeout_seconds is not None:
                lines.append(f"    - Timeout: {self.rails.abort.timeout_seconds} seconds")
            if self.rails.abort.wns_ps is None and self.rails.abort.timeout_seconds is None:
                lines.append("    - None configured")

            lines.append("  Stage Rail (stage-level):")
            if self.rails.stage.failure_rate is not None:
                lines.append(f"    - Max failure rate: {self.rails.stage.failure_rate * 100:.1f}%")
            else:
                lines.append("    - None configured")

            lines.append("  Study Rail (study-level):")
            if self.rails.study.catastrophic_failures is not None:
                lines.append(f"    - Max catastrophic failures: {self.rails.study.catastrophic_failures}")
            if self.rails.study.max_runtime_hours is not None:
                lines.append(f"    - Max runtime: {self.rails.study.max_runtime_hours} hours")
            if (self.rails.study.catastrophic_failures is None and
                self.rails.study.max_runtime_hours is None):
                lines.append("    - None configured")
            lines.append("")

        # Study summary
        lines.append("STUDY SUMMARY")
        lines.append(f"  Stages: {self.stage_count}")
        lines.append(f"  Total trial budget: {self.total_trial_budget}")
        lines.append("")

        # Final verdict
        lines.append("VERDICT")
        if self.is_legal:
            lines.append("  ✓ LEGAL - Study may proceed")
        else:
            lines.append("  ✗ ILLEGAL - Study execution BLOCKED")
            lines.append(f"  Violations: {len(self.violations)}")
        lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "study_name": self.study_name,
            "safety_domain": self.safety_domain.value,
            "is_legal": self.is_legal,
            "allowed_eco_classes": [ec.value for ec in self.allowed_eco_classes],
            "violations": [
                {
                    "stage_index": v.stage_index,
                    "stage_name": v.stage_name,
                    "eco_class": v.eco_class.value,
                    "reason": v.reason,
                    "severity": v.severity,
                }
                for v in self.violations
            ],
            "warnings": self.warnings,
            "stage_count": self.stage_count,
            "total_trial_budget": self.total_trial_budget,
            "timestamp": self.timestamp,
        }

        # Add rails if configured
        if self.rails:
            result["rails"] = {
                "abort": {
                    "wns_ps": self.rails.abort.wns_ps,
                    "timeout_seconds": self.rails.abort.timeout_seconds,
                },
                "stage": {
                    "failure_rate": self.rails.stage.failure_rate,
                },
                "study": {
                    "catastrophic_failures": self.rails.study.catastrophic_failures,
                    "max_runtime_hours": self.rails.study.max_runtime_hours,
                },
            }

        return result


def generate_legality_report(
    study: StudyConfig,
    timestamp: Optional[str] = None,
) -> RunLegalityReport:
    """
    Generate a Run Legality Report for a Study.

    Args:
        study: Study configuration to check
        timestamp: Optional timestamp string

    Returns:
        RunLegalityReport
    """
    checker = LegalityChecker(study)
    result = checker.check_legality()

    total_budget = sum(stage.trial_budget for stage in study.stages)

    return RunLegalityReport(
        study_name=study.name,
        safety_domain=study.safety_domain,
        is_legal=result.is_legal,
        allowed_eco_classes=checker.get_allowed_eco_classes(),
        violations=result.violations,
        warnings=result.warnings,
        stage_count=len(study.stages),
        total_trial_budget=total_budget,
        rails=study.rails,
        timestamp=timestamp,
    )


def check_study_legality(study: StudyConfig) -> LegalityCheckResult:
    """
    Check if a Study configuration is legal.

    Convenience function for quick legality checks.

    Args:
        study: Study configuration to check

    Returns:
        LegalityCheckResult

    Raises:
        ValueError: If Study is illegal (has violations)
    """
    checker = LegalityChecker(study)
    result = checker.check_legality()

    if not result.is_legal:
        violation_summary = "\n".join(
            f"  - Stage {v.stage_index} ({v.stage_name}): {v.reason}"
            for v in result.violations
        )
        raise ValueError(
            f"Study '{study.name}' is ILLEGAL:\n{violation_summary}"
        )

    return result
