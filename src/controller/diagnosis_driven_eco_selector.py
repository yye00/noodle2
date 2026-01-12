"""Diagnosis-driven ECO selection using priority queue from auto-diagnosis.

This module implements F209: Combined diagnosis drives ECO selection with priority queue.

The ECO selector uses the diagnosis summary to:
1. Select ECOs in priority order from the diagnosis-generated queue
2. Ensure ECOs address the primary and secondary issues identified
3. Track ECO effectiveness against diagnosis predictions
"""

from dataclasses import dataclass, field
from typing import Any

from src.analysis.diagnosis import CompleteDiagnosisReport, DiagnosisSummary, ECOSuggestion


@dataclass
class ECOApplication:
    """Record of an ECO application attempt."""

    eco_name: str
    priority: int
    addresses: str  # "timing" or "congestion"
    applied: bool
    success: bool
    addresses_primary_issue: bool
    effectiveness_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_name": self.eco_name,
            "priority": self.priority,
            "addresses": self.addresses,
            "applied": self.applied,
            "success": self.success,
            "addresses_primary_issue": self.addresses_primary_issue,
            "effectiveness_notes": self.effectiveness_notes,
        }


@dataclass
class DiagnosisDrivenECOSelection:
    """Result of diagnosis-driven ECO selection process."""

    diagnosis_summary: DiagnosisSummary
    eco_applications: list[ECOApplication] = field(default_factory=list)
    selection_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "diagnosis_summary": self.diagnosis_summary.to_dict(),
            "eco_applications": [app.to_dict() for app in self.eco_applications],
            "selection_notes": self.selection_notes,
        }


class DiagnosisDrivenECOSelector:
    """
    Selects ECOs based on diagnosis priority queue.

    This selector uses the auto-diagnosis output to drive ECO selection,
    ensuring that ECOs are applied in priority order and address the
    identified issues (timing vs congestion).
    """

    def __init__(self, diagnosis_report: CompleteDiagnosisReport) -> None:
        """
        Initialize the ECO selector with a diagnosis report.

        Args:
            diagnosis_report: Complete diagnosis report with priority queue
        """
        if diagnosis_report.diagnosis_summary is None:
            raise ValueError("Diagnosis report must contain a diagnosis_summary")

        self.diagnosis_report = diagnosis_report
        self.diagnosis_summary = diagnosis_report.diagnosis_summary

    def select_next_eco(self, applied_ecos: list[str] | None = None) -> ECOSuggestion | None:
        """
        Select the next ECO from the priority queue.

        Args:
            applied_ecos: List of ECO names that have already been applied

        Returns:
            Next ECO suggestion to apply, or None if queue is exhausted
        """
        if applied_ecos is None:
            applied_ecos = []

        # Find first ECO in priority queue that hasn't been applied
        for eco in self.diagnosis_summary.eco_priority_queue:
            if eco.eco not in applied_ecos:
                return eco

        return None

    def get_eco_by_priority(self, priority: int) -> ECOSuggestion | None:
        """
        Get ECO with specific priority level.

        Args:
            priority: Priority level to search for

        Returns:
            ECO suggestion with that priority, or None if not found
        """
        for eco in self.diagnosis_summary.eco_priority_queue:
            if eco.priority == priority:
                return eco
        return None

    def get_ecos_for_issue(self, issue_type: str) -> list[ECOSuggestion]:
        """
        Get all ECOs that address a specific issue type.

        Args:
            issue_type: "timing" or "congestion"

        Returns:
            List of ECO suggestions for that issue type
        """
        return [
            eco
            for eco in self.diagnosis_summary.eco_priority_queue
            if eco.addresses == issue_type
        ]

    def verify_eco_addresses_primary_issue(self, eco: ECOSuggestion) -> bool:
        """
        Verify that an ECO addresses the primary issue identified by diagnosis.

        Args:
            eco: ECO suggestion to verify

        Returns:
            True if ECO addresses primary issue, False otherwise
        """
        primary_issue = self.diagnosis_summary.primary_issue.value

        # Map primary issue type to expected ECO addresses field
        if primary_issue == "timing":
            return eco.addresses == "timing"
        elif primary_issue == "congestion":
            return eco.addresses == "congestion"
        elif primary_issue == "both":
            # For "both", ECO can address either
            return eco.addresses in ["timing", "congestion"]
        else:
            # "none" - any ECO is acceptable for refinement
            return True

    def create_eco_application_record(
        self,
        eco: ECOSuggestion,
        applied: bool,
        success: bool,
        effectiveness_notes: str = "",
    ) -> ECOApplication:
        """
        Create a record of an ECO application attempt.

        Args:
            eco: ECO that was attempted
            applied: Whether the ECO was actually applied
            success: Whether the application succeeded
            effectiveness_notes: Notes about effectiveness

        Returns:
            ECOApplication record
        """
        addresses_primary = self.verify_eco_addresses_primary_issue(eco)

        return ECOApplication(
            eco_name=eco.eco,
            priority=eco.priority,
            addresses=eco.addresses,
            applied=applied,
            success=success,
            addresses_primary_issue=addresses_primary,
            effectiveness_notes=effectiveness_notes,
        )

    def generate_selection_report(
        self,
        eco_applications: list[ECOApplication],
    ) -> DiagnosisDrivenECOSelection:
        """
        Generate a report of the ECO selection process.

        Args:
            eco_applications: List of ECO application records

        Returns:
            Complete selection report
        """
        # Generate selection notes
        applied_count = sum(1 for app in eco_applications if app.applied)
        successful_count = sum(1 for app in eco_applications if app.success)
        primary_count = sum(1 for app in eco_applications if app.addresses_primary_issue)

        selection_notes = (
            f"ECO Selection Summary:\n"
            f"- Total ECOs in priority queue: {len(self.diagnosis_summary.eco_priority_queue)}\n"
            f"- ECOs attempted: {len(eco_applications)}\n"
            f"- ECOs successfully applied: {successful_count}\n"
            f"- ECOs addressing primary issue: {primary_count}\n"
            f"- Primary issue: {self.diagnosis_summary.primary_issue.value}\n"
            f"- Recommended strategy: {self.diagnosis_summary.recommended_strategy}"
        )

        return DiagnosisDrivenECOSelection(
            diagnosis_summary=self.diagnosis_summary,
            eco_applications=eco_applications,
            selection_notes=selection_notes,
        )


def select_ecos_from_diagnosis(
    diagnosis_report: CompleteDiagnosisReport,
    max_ecos: int = 5,
) -> list[ECOSuggestion]:
    """
    Select ECOs from diagnosis report in priority order.

    This is a convenience function that extracts the top ECOs from
    the diagnosis priority queue.

    Args:
        diagnosis_report: Complete diagnosis report
        max_ecos: Maximum number of ECOs to select

    Returns:
        List of ECO suggestions in priority order (up to max_ecos)
    """
    if diagnosis_report.diagnosis_summary is None:
        return []

    eco_queue = diagnosis_report.diagnosis_summary.eco_priority_queue
    return eco_queue[:max_ecos]
