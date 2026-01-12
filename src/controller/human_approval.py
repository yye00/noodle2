"""Human approval gate functionality for multi-stage studies."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ApprovalSummary:
    """Summary of study progress for human review."""

    study_name: str
    stages_completed: int
    total_stages: int
    current_stage_name: str
    survivors_count: int
    best_wns_ps: int | None = None
    best_hot_ratio: float | None = None
    stage_summaries: list[dict[str, Any]] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def format_for_display(self) -> str:
        """
        Format approval summary for human-readable display.

        Returns:
            Formatted string suitable for console display
        """
        lines = [
            "=" * 70,
            f"APPROVAL GATE: {self.current_stage_name}",
            "=" * 70,
            "",
            f"Study: {self.study_name}",
            f"Progress: {self.stages_completed}/{self.total_stages} stages completed",
            f"Current survivors: {self.survivors_count}",
            "",
        ]

        if self.best_wns_ps is not None:
            lines.append(f"Best WNS: {self.best_wns_ps} ps")
        if self.best_hot_ratio is not None:
            lines.append(f"Best hot_ratio: {self.best_hot_ratio:.3f}")

        if self.best_wns_ps is not None or self.best_hot_ratio is not None:
            lines.append("")

        if self.stage_summaries:
            lines.append("Stage Results:")
            lines.append("-" * 70)
            for summary in self.stage_summaries:
                stage_name = summary.get("stage_name", "unknown")
                trials = summary.get("trials_executed", 0)
                survivors = summary.get("survivors", [])
                lines.append(f"  {stage_name}: {trials} trials, {len(survivors)} survivors")
            lines.append("")

        lines.append("=" * 70)
        lines.append("Please review the results above.")
        lines.append("Continue to next stage? (yes/no)")
        lines.append("=" * 70)

        return "\n".join(lines)


@dataclass
class ApprovalDecision:
    """Human approval decision at a gate."""

    approved: bool
    approver: str
    reason: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class ApprovalGateSimulator:
    """
    Simulator for human approval gates (for testing).

    In production, this would be replaced with an actual approval mechanism
    (web UI, API, etc.), but for testing we simulate approval decisions.
    """

    def __init__(self, auto_approve: bool = False) -> None:
        """
        Initialize approval gate simulator.

        Args:
            auto_approve: If True, automatically approve all requests (for testing)
        """
        self.auto_approve = auto_approve
        self._pending_approvals: list[ApprovalSummary] = []
        self._decisions: list[ApprovalDecision] = []

    def request_approval(self, summary: ApprovalSummary) -> None:
        """
        Request approval for study progression.

        Args:
            summary: Summary of study progress for review
        """
        self._pending_approvals.append(summary)

    def get_pending_approvals(self) -> list[ApprovalSummary]:
        """
        Get list of pending approval requests.

        Returns:
            List of pending approval summaries
        """
        return self._pending_approvals.copy()

    def approve(
        self,
        summary: ApprovalSummary,
        approver: str = "test_approver",
        reason: str | None = None,
    ) -> ApprovalDecision:
        """
        Approve study progression.

        Args:
            summary: Summary to approve
            approver: Name of approver
            reason: Optional reason for approval

        Returns:
            ApprovalDecision with approved=True
        """
        decision = ApprovalDecision(
            approved=True,
            approver=approver,
            reason=reason,
        )
        self._decisions.append(decision)
        if summary in self._pending_approvals:
            self._pending_approvals.remove(summary)
        return decision

    def reject(
        self,
        summary: ApprovalSummary,
        approver: str = "test_approver",
        reason: str | None = None,
    ) -> ApprovalDecision:
        """
        Reject study progression.

        Args:
            summary: Summary to reject
            approver: Name of approver
            reason: Optional reason for rejection

        Returns:
            ApprovalDecision with approved=False
        """
        decision = ApprovalDecision(
            approved=False,
            approver=approver,
            reason=reason,
        )
        self._decisions.append(decision)
        if summary in self._pending_approvals:
            self._pending_approvals.remove(summary)
        return decision

    def simulate_approval(
        self,
        summary: ApprovalSummary,
    ) -> ApprovalDecision:
        """
        Simulate an approval decision (for testing).

        Args:
            summary: Summary to approve/reject

        Returns:
            ApprovalDecision based on auto_approve setting
        """
        if self.auto_approve:
            return self.approve(summary, approver="simulator", reason="auto-approved")
        else:
            return self.reject(summary, approver="simulator", reason="auto-rejected")

    def get_decisions(self) -> list[ApprovalDecision]:
        """
        Get all approval decisions made.

        Returns:
            List of approval decisions
        """
        return self._decisions.copy()


def generate_approval_summary(
    study_name: str,
    stages_completed: int,
    total_stages: int,
    current_stage_name: str,
    survivors_count: int,
    stage_summaries: list[dict[str, Any]],
    best_wns_ps: int | None = None,
    best_hot_ratio: float | None = None,
) -> ApprovalSummary:
    """
    Generate an approval summary for human review.

    Args:
        study_name: Name of the study
        stages_completed: Number of stages completed
        total_stages: Total number of stages
        current_stage_name: Name of the approval gate stage
        survivors_count: Number of current survivors
        stage_summaries: List of stage result summaries
        best_wns_ps: Best WNS achieved so far (optional)
        best_hot_ratio: Best hot_ratio achieved so far (optional)

    Returns:
        ApprovalSummary ready for display
    """
    return ApprovalSummary(
        study_name=study_name,
        stages_completed=stages_completed,
        total_stages=total_stages,
        current_stage_name=current_stage_name,
        survivors_count=survivors_count,
        stage_summaries=stage_summaries,
        best_wns_ps=best_wns_ps,
        best_hot_ratio=best_hot_ratio,
    )
