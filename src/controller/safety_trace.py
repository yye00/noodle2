"""Safety trace generation for auditable safety-gate evaluations.

The SafetyTrace records all safety checks performed during Study execution,
providing a chronological audit trail of policy decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from .types import ECOClass, SafetyDomain


class SafetyGateType(Enum):
    """Types of safety gates that can be evaluated."""

    LEGALITY_CHECK = "legality_check"
    BASE_CASE_VERIFICATION = "base_case_verification"
    ECO_CLASS_FILTER = "eco_class_filter"
    STAGE_ABORT_CHECK = "stage_abort_check"
    WNS_THRESHOLD_CHECK = "wns_threshold_check"
    CATASTROPHIC_FAILURE_CHECK = "catastrophic_failure_check"


class SafetyGateStatus(Enum):
    """Status of a safety gate evaluation."""

    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    BLOCKED = "blocked"


@dataclass
class SafetyGateEvaluation:
    """
    Record of a single safety gate evaluation.

    Captures:
    - What gate was evaluated
    - When it was evaluated
    - Pass/fail status
    - Rationale for the decision
    - Context (stage, case, trial, etc.)
    """

    gate_type: SafetyGateType
    status: SafetyGateStatus
    rationale: str
    timestamp: str
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "gate_type": self.gate_type.value,
            "status": self.status.value,
            "rationale": self.rationale,
            "timestamp": self.timestamp,
            "context": self.context,
        }


@dataclass
class SafetyTrace:
    """
    Complete safety trace for a Study execution.

    Records all safety-gate evaluations in chronological order,
    providing an audit trail for policy decisions.
    """

    study_name: str
    safety_domain: SafetyDomain
    evaluations: list[SafetyGateEvaluation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def record_legality_check(
        self,
        is_legal: bool,
        violations: list[dict[str, Any]],
        warnings: list[str],
    ) -> None:
        """
        Record a Study legality check.

        Args:
            is_legal: Whether the Study configuration is legal
            violations: List of safety violations
            warnings: List of warnings
        """
        status = SafetyGateStatus.PASS if is_legal else SafetyGateStatus.FAIL
        rationale = "Study configuration is legal" if is_legal else (
            f"Study configuration has {len(violations)} violation(s)"
        )

        evaluation = SafetyGateEvaluation(
            gate_type=SafetyGateType.LEGALITY_CHECK,
            status=status,
            rationale=rationale,
            timestamp=self._get_timestamp(),
            context={
                "is_legal": is_legal,
                "violation_count": len(violations),
                "warning_count": len(warnings),
                "violations": violations,
                "warnings": warnings,
            },
        )
        self.evaluations.append(evaluation)

    def record_base_case_verification(
        self,
        is_valid: bool,
        failure_message: str = "",
    ) -> None:
        """
        Record base case verification result.

        Args:
            is_valid: Whether base case passed verification
            failure_message: Failure details if verification failed
        """
        status = SafetyGateStatus.PASS if is_valid else SafetyGateStatus.FAIL
        rationale = (
            "Base case is structurally runnable"
            if is_valid
            else f"Base case verification failed: {failure_message}"
        )

        evaluation = SafetyGateEvaluation(
            gate_type=SafetyGateType.BASE_CASE_VERIFICATION,
            status=status,
            rationale=rationale,
            timestamp=self._get_timestamp(),
            context={
                "is_valid": is_valid,
                "failure_message": failure_message,
            },
        )
        self.evaluations.append(evaluation)

    def record_eco_class_filter(
        self,
        eco_class: ECOClass,
        stage_index: int,
        is_allowed: bool,
        reason: str = "",
    ) -> None:
        """
        Record ECO class filtering decision.

        Args:
            eco_class: ECO class being checked
            stage_index: Stage where ECO class is being used
            is_allowed: Whether ECO class is allowed
            reason: Reason for allow/deny decision
        """
        status = SafetyGateStatus.PASS if is_allowed else SafetyGateStatus.BLOCKED
        rationale = (
            f"ECO class '{eco_class.value}' allowed in stage {stage_index}"
            if is_allowed
            else f"ECO class '{eco_class.value}' blocked in stage {stage_index}: {reason}"
        )

        evaluation = SafetyGateEvaluation(
            gate_type=SafetyGateType.ECO_CLASS_FILTER,
            status=status,
            rationale=rationale,
            timestamp=self._get_timestamp(),
            context={
                "eco_class": eco_class.value,
                "stage_index": stage_index,
                "is_allowed": is_allowed,
                "reason": reason,
            },
        )
        self.evaluations.append(evaluation)

    def record_stage_abort_check(
        self,
        stage_index: int,
        stage_name: str,
        should_abort: bool,
        abort_reason: str | None = None,
        details: str = "",
    ) -> None:
        """
        Record stage abort decision.

        Args:
            stage_index: Stage being checked
            stage_name: Stage name
            should_abort: Whether stage should be aborted
            abort_reason: Reason for abort (if applicable)
            details: Additional details
        """
        status = SafetyGateStatus.FAIL if should_abort else SafetyGateStatus.PASS
        rationale = (
            f"Stage {stage_index} ({stage_name}) proceeding normally"
            if not should_abort
            else f"Stage {stage_index} ({stage_name}) ABORTED: {abort_reason}"
        )

        evaluation = SafetyGateEvaluation(
            gate_type=SafetyGateType.STAGE_ABORT_CHECK,
            status=status,
            rationale=rationale,
            timestamp=self._get_timestamp(),
            context={
                "stage_index": stage_index,
                "stage_name": stage_name,
                "should_abort": should_abort,
                "abort_reason": abort_reason,
                "details": details,
            },
        )
        self.evaluations.append(evaluation)

    def record_wns_threshold_check(
        self,
        stage_index: int,
        threshold_ps: int | None,
        worst_wns_ps: int | None,
        violating_trials: list[str],
    ) -> None:
        """
        Record WNS threshold check.

        Args:
            stage_index: Stage being checked
            threshold_ps: WNS threshold in picoseconds
            worst_wns_ps: Worst WNS observed in stage
            violating_trials: Trials that violated threshold
        """
        if threshold_ps is None:
            status = SafetyGateStatus.PASS
            rationale = f"No WNS threshold configured for stage {stage_index}"
        elif len(violating_trials) > 0:
            status = SafetyGateStatus.FAIL
            rationale = (
                f"Stage {stage_index}: {len(violating_trials)} trial(s) violated "
                f"WNS threshold ({threshold_ps} ps). Worst WNS: {worst_wns_ps} ps"
            )
        else:
            status = SafetyGateStatus.PASS
            rationale = f"Stage {stage_index}: All trials within WNS threshold ({threshold_ps} ps)"

        evaluation = SafetyGateEvaluation(
            gate_type=SafetyGateType.WNS_THRESHOLD_CHECK,
            status=status,
            rationale=rationale,
            timestamp=self._get_timestamp(),
            context={
                "stage_index": stage_index,
                "threshold_ps": threshold_ps,
                "worst_wns_ps": worst_wns_ps,
                "violating_trials": violating_trials,
                "violation_count": len(violating_trials),
            },
        )
        self.evaluations.append(evaluation)

    def record_catastrophic_failure_check(
        self,
        stage_index: int,
        catastrophic_count: int,
        total_trials: int,
        failure_rate: float,
        threshold: float | None,
    ) -> None:
        """
        Record catastrophic failure rate check.

        Args:
            stage_index: Stage being checked
            catastrophic_count: Number of catastrophic failures
            total_trials: Total trials executed
            failure_rate: Observed failure rate (0.0 to 1.0)
            threshold: Failure rate threshold for abort
        """
        if threshold is None:
            status = SafetyGateStatus.PASS
            rationale = f"No catastrophic failure threshold configured for stage {stage_index}"
        elif failure_rate > threshold:
            status = SafetyGateStatus.FAIL
            rationale = (
                f"Stage {stage_index}: Catastrophic failure rate {failure_rate:.1%} "
                f"exceeds threshold {threshold:.1%} ({catastrophic_count}/{total_trials})"
            )
        else:
            status = SafetyGateStatus.PASS
            rationale = (
                f"Stage {stage_index}: Catastrophic failure rate {failure_rate:.1%} "
                f"within threshold {threshold:.1%} ({catastrophic_count}/{total_trials})"
            )

        evaluation = SafetyGateEvaluation(
            gate_type=SafetyGateType.CATASTROPHIC_FAILURE_CHECK,
            status=status,
            rationale=rationale,
            timestamp=self._get_timestamp(),
            context={
                "stage_index": stage_index,
                "catastrophic_count": catastrophic_count,
                "total_trials": total_trials,
                "failure_rate": failure_rate,
                "threshold": threshold,
            },
        )
        self.evaluations.append(evaluation)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "study_name": self.study_name,
            "safety_domain": self.safety_domain.value,
            "evaluations": [eval.to_dict() for eval in self.evaluations],
            "metadata": self.metadata,
            "summary": self._generate_summary(),
        }

    def _generate_summary(self) -> dict[str, Any]:
        """Generate summary statistics for the safety trace."""
        total_checks = len(self.evaluations)
        passed = sum(1 for e in self.evaluations if e.status == SafetyGateStatus.PASS)
        failed = sum(1 for e in self.evaluations if e.status == SafetyGateStatus.FAIL)
        warnings = sum(1 for e in self.evaluations if e.status == SafetyGateStatus.WARNING)
        blocked = sum(1 for e in self.evaluations if e.status == SafetyGateStatus.BLOCKED)

        # Count by gate type
        by_gate_type: dict[str, int] = {}
        for eval in self.evaluations:
            gate_type_str = eval.gate_type.value
            by_gate_type[gate_type_str] = by_gate_type.get(gate_type_str, 0) + 1

        return {
            "total_checks": total_checks,
            "passed": passed,
            "failed": failed,
            "warnings": warnings,
            "blocked": blocked,
            "by_gate_type": by_gate_type,
        }

    def __str__(self) -> str:
        """Generate human-readable safety trace report."""
        lines = []
        lines.append("=" * 70)
        lines.append("SAFETY TRACE REPORT")
        lines.append("=" * 70)
        lines.append("")

        # Header
        lines.append(f"Study: {self.study_name}")
        lines.append(f"Safety Domain: {self.safety_domain.value}")
        lines.append("")

        # Summary
        summary = self._generate_summary()
        lines.append("SUMMARY")
        lines.append(f"  Total safety checks: {summary['total_checks']}")
        lines.append(f"  Passed: {summary['passed']}")
        lines.append(f"  Failed: {summary['failed']}")
        lines.append(f"  Warnings: {summary['warnings']}")
        lines.append(f"  Blocked: {summary['blocked']}")
        lines.append("")

        # Checks by type
        lines.append("CHECKS BY TYPE")
        for gate_type, count in summary['by_gate_type'].items():
            lines.append(f"  {gate_type}: {count}")
        lines.append("")

        # Chronological evaluation log
        lines.append("CHRONOLOGICAL EVALUATION LOG")
        lines.append("")
        for i, eval in enumerate(self.evaluations, 1):
            status_symbol = {
                SafetyGateStatus.PASS: "✓",
                SafetyGateStatus.FAIL: "✗",
                SafetyGateStatus.WARNING: "⚠",
                SafetyGateStatus.BLOCKED: "🚫",
            }.get(eval.status, "?")

            lines.append(f"{i}. [{status_symbol}] {eval.gate_type.value.upper()}")
            lines.append(f"   Status: {eval.status.value}")
            lines.append(f"   Time: {eval.timestamp}")
            lines.append(f"   Rationale: {eval.rationale}")
            if eval.context:
                lines.append(f"   Context: {eval.context}")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    def save_to_file(self, filepath: str | Path) -> None:
        """
        Save safety trace to file.

        Args:
            filepath: Path to save the trace (supports .txt and .json)
        """
        import json

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if filepath.suffix == ".json":
            # Save as JSON
            with open(filepath, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        else:
            # Save as human-readable text
            with open(filepath, "w") as f:
                f.write(str(self))

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()
