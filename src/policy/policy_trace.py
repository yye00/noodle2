"""Policy trace generation for auditable policy rule evaluations.

The PolicyTrace records all policy decisions made during Study execution,
providing a chronological audit trail of ranking, selection, and filtering decisions.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class PolicyRuleType(Enum):
    """Types of policy rules that can be evaluated."""

    SURVIVOR_RANKING = "survivor_ranking"  # Trial ranking and survivor selection
    ECO_SELECTION = "eco_selection"  # ECO selection for trials
    TRIAL_FILTERING = "trial_filtering"  # Trial filtering (blacklist/whitelist)
    ECO_PRIOR_UPDATE = "eco_prior_update"  # ECO prior confidence updates
    METRIC_WEIGHTING = "metric_weighting"  # Multi-objective metric weighting
    BUDGET_ALLOCATION = "budget_allocation"  # Trial budget allocation decisions


class PolicyRuleOutcome(Enum):
    """Outcome of a policy rule evaluation."""

    APPLIED = "applied"  # Rule was applied successfully
    SKIPPED = "skipped"  # Rule was not applicable
    FAILED = "failed"  # Rule evaluation failed
    OVERRIDDEN = "overridden"  # Rule was overridden by higher-priority rule


@dataclass
class PolicyRuleEvaluation:
    """
    Record of a single policy rule evaluation.

    Captures:
    - What rule was evaluated
    - When it was evaluated
    - Input data to the rule
    - Logic/parameters used
    - Outcome of the evaluation
    - Result (e.g., selected survivors, filtered trials)
    """

    rule_type: PolicyRuleType
    outcome: PolicyRuleOutcome
    timestamp: str
    inputs: dict[str, Any] = field(default_factory=dict)
    logic: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rule_type": self.rule_type.value,
            "outcome": self.outcome.value,
            "timestamp": self.timestamp,
            "inputs": self.inputs,
            "logic": self.logic,
            "result": self.result,
            "rationale": self.rationale,
        }


@dataclass
class PolicyTrace:
    """
    Complete policy trace for a Study execution.

    Records all policy rule evaluations in chronological order,
    providing an audit trail for decision-making logic.
    """

    study_name: str
    evaluations: list[PolicyRuleEvaluation] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def record_survivor_ranking(
        self,
        stage_index: int,
        policy_name: str,
        trial_count: int,
        survivor_count: int,
        selected_cases: list[str],
        baseline_metrics: dict[str, Any],
        weights: dict[str, float] | None = None,
    ) -> None:
        """
        Record a survivor ranking decision.

        Args:
            stage_index: Stage index where ranking occurred
            policy_name: Name of ranking policy (e.g., "wns_delta", "multi_objective")
            trial_count: Total number of trials evaluated
            survivor_count: Number of survivors requested
            selected_cases: List of selected case IDs
            baseline_metrics: Baseline metrics used for ranking
            weights: Weighting parameters (for multi-objective)
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        logic = {
            "policy_name": policy_name,
            "survivor_count": survivor_count,
            "baseline_metrics": baseline_metrics,
        }
        if weights:
            logic["weights"] = weights

        evaluation = PolicyRuleEvaluation(
            rule_type=PolicyRuleType.SURVIVOR_RANKING,
            outcome=PolicyRuleOutcome.APPLIED,
            timestamp=timestamp,
            inputs={
                "stage_index": stage_index,
                "trial_count": trial_count,
            },
            logic=logic,
            result={
                "selected_cases": selected_cases,
                "selected_count": len(selected_cases),
            },
            rationale=f"Ranked {trial_count} trials using '{policy_name}' policy, selected {len(selected_cases)}/{survivor_count} survivors",
        )

        self.evaluations.append(evaluation)

    def record_eco_selection(
        self,
        stage_index: int,
        case_name: str,
        available_ecos: list[str],
        selected_eco: str,
        selection_reason: str,
        eco_priors: dict[str, str] | None = None,
    ) -> None:
        """
        Record an ECO selection decision.

        Args:
            stage_index: Stage index where ECO was selected
            case_name: Case name for which ECO was selected
            available_ecos: List of available ECO names
            selected_eco: Selected ECO name
            selection_reason: Reason for selection (e.g., "highest prior", "round-robin")
            eco_priors: ECO prior confidence levels (trusted/mixed/suspicious/unknown)
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        logic = {
            "selection_strategy": selection_reason,
        }
        if eco_priors:
            logic["eco_priors"] = eco_priors

        evaluation = PolicyRuleEvaluation(
            rule_type=PolicyRuleType.ECO_SELECTION,
            outcome=PolicyRuleOutcome.APPLIED,
            timestamp=timestamp,
            inputs={
                "stage_index": stage_index,
                "case_name": case_name,
                "available_ecos": available_ecos,
            },
            logic=logic,
            result={
                "selected_eco": selected_eco,
            },
            rationale=f"Selected ECO '{selected_eco}' from {len(available_ecos)} available ECOs for case '{case_name}' ({selection_reason})",
        )

        self.evaluations.append(evaluation)

    def record_trial_filtering(
        self,
        stage_index: int,
        filter_type: str,
        trials_before: int,
        trials_after: int,
        filter_criteria: dict[str, Any],
        filtered_items: list[str],
    ) -> None:
        """
        Record a trial filtering decision.

        Args:
            stage_index: Stage index where filtering occurred
            filter_type: Type of filter (e.g., "blacklist", "whitelist", "failure_rate")
            trials_before: Number of trials before filtering
            trials_after: Number of trials after filtering
            filter_criteria: Criteria used for filtering
            filtered_items: Items that were filtered out
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        evaluation = PolicyRuleEvaluation(
            rule_type=PolicyRuleType.TRIAL_FILTERING,
            outcome=PolicyRuleOutcome.APPLIED,
            timestamp=timestamp,
            inputs={
                "stage_index": stage_index,
                "trials_before": trials_before,
            },
            logic={
                "filter_type": filter_type,
                "filter_criteria": filter_criteria,
            },
            result={
                "trials_after": trials_after,
                "filtered_count": trials_before - trials_after,
                "filtered_items": filtered_items,
            },
            rationale=f"Applied {filter_type} filter: {trials_before} → {trials_after} trials ({trials_before - trials_after} filtered)",
        )

        self.evaluations.append(evaluation)

    def record_eco_prior_update(
        self,
        stage_index: int,
        eco_name: str,
        old_prior: str,
        new_prior: str,
        update_reason: str,
        evidence: dict[str, Any],
    ) -> None:
        """
        Record an ECO prior confidence update.

        Args:
            stage_index: Stage index where update occurred
            eco_name: ECO name
            old_prior: Previous prior confidence (trusted/mixed/suspicious/unknown)
            new_prior: New prior confidence
            update_reason: Reason for update (e.g., "success_rate_improved", "catastrophic_failure")
            evidence: Evidence for the update (e.g., success/failure counts)
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        evaluation = PolicyRuleEvaluation(
            rule_type=PolicyRuleType.ECO_PRIOR_UPDATE,
            outcome=PolicyRuleOutcome.APPLIED,
            timestamp=timestamp,
            inputs={
                "stage_index": stage_index,
                "eco_name": eco_name,
                "old_prior": old_prior,
            },
            logic={
                "update_reason": update_reason,
                "evidence": evidence,
            },
            result={
                "new_prior": new_prior,
            },
            rationale=f"Updated ECO '{eco_name}' prior: {old_prior} → {new_prior} ({update_reason})",
        )

        self.evaluations.append(evaluation)

    def record_metric_weighting(
        self,
        stage_index: int,
        weights: dict[str, float],
        weight_source: str,
    ) -> None:
        """
        Record metric weighting configuration.

        Args:
            stage_index: Stage index where weighting was applied
            weights: Metric weights (e.g., {"timing": 0.6, "congestion": 0.4})
            weight_source: Source of weights (e.g., "stage_config", "adaptive", "user_override")
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        evaluation = PolicyRuleEvaluation(
            rule_type=PolicyRuleType.METRIC_WEIGHTING,
            outcome=PolicyRuleOutcome.APPLIED,
            timestamp=timestamp,
            inputs={
                "stage_index": stage_index,
            },
            logic={
                "weights": weights,
                "weight_source": weight_source,
            },
            result={
                "applied_weights": weights,
            },
            rationale=f"Applied metric weights from '{weight_source}': {weights}",
        )

        self.evaluations.append(evaluation)

    def record_budget_allocation(
        self,
        stage_index: int,
        total_budget: int,
        allocated_trials: int,
        allocation_strategy: str,
        allocation_details: dict[str, Any],
    ) -> None:
        """
        Record trial budget allocation decision.

        Args:
            stage_index: Stage index where allocation occurred
            total_budget: Total trial budget for stage
            allocated_trials: Number of trials actually allocated
            allocation_strategy: Strategy used (e.g., "uniform", "eco_class_weighted", "prior_weighted")
            allocation_details: Details of allocation (e.g., per-ECO counts)
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        evaluation = PolicyRuleEvaluation(
            rule_type=PolicyRuleType.BUDGET_ALLOCATION,
            outcome=PolicyRuleOutcome.APPLIED,
            timestamp=timestamp,
            inputs={
                "stage_index": stage_index,
                "total_budget": total_budget,
            },
            logic={
                "allocation_strategy": allocation_strategy,
                "allocation_details": allocation_details,
            },
            result={
                "allocated_trials": allocated_trials,
            },
            rationale=f"Allocated {allocated_trials}/{total_budget} trials using '{allocation_strategy}' strategy",
        )

        self.evaluations.append(evaluation)

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary statistics for the policy trace.

        Returns:
            Dictionary with counts by rule type and outcome
        """
        total_evaluations = len(self.evaluations)

        # Count by outcome
        outcome_counts = {outcome.value: 0 for outcome in PolicyRuleOutcome}
        for evaluation in self.evaluations:
            outcome_counts[evaluation.outcome.value] += 1

        # Count by rule type
        rule_type_counts = {rule_type.value: 0 for rule_type in PolicyRuleType}
        for evaluation in self.evaluations:
            rule_type_counts[evaluation.rule_type.value] += 1

        return {
            "total_evaluations": total_evaluations,
            "by_outcome": outcome_counts,
            "by_rule_type": rule_type_counts,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "study_name": self.study_name,
            "metadata": self.metadata,
            "summary": self.get_summary(),
            "evaluations": [e.to_dict() for e in self.evaluations],
        }

    def save_json(self, output_path: Path) -> None:
        """
        Save policy trace to JSON file.

        Args:
            output_path: Path to output JSON file
        """
        import json

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    def save_txt(self, output_path: Path) -> None:
        """
        Save policy trace to human-readable text file.

        Args:
            output_path: Path to output text file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            f.write(str(self))

    def __str__(self) -> str:
        """Generate human-readable policy trace report."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append("POLICY TRACE REPORT")
        lines.append("=" * 80)
        lines.append(f"Study: {self.study_name}")
        lines.append("")

        # Summary
        summary = self.get_summary()
        lines.append("Summary:")
        lines.append(f"  Total Evaluations: {summary['total_evaluations']}")
        lines.append("")
        lines.append("  By Outcome:")
        for outcome, count in summary["by_outcome"].items():
            if count > 0:
                lines.append(f"    {outcome}: {count}")
        lines.append("")
        lines.append("  By Rule Type:")
        for rule_type, count in summary["by_rule_type"].items():
            if count > 0:
                lines.append(f"    {rule_type}: {count}")
        lines.append("")

        # Evaluations by type
        lines.append("=" * 80)
        lines.append("POLICY RULE EVALUATIONS")
        lines.append("=" * 80)

        for rule_type in PolicyRuleType:
            type_evaluations = [
                e for e in self.evaluations if e.rule_type == rule_type
            ]
            if type_evaluations:
                lines.append("")
                lines.append(f"{rule_type.value.upper()}")
                lines.append("-" * 80)
                for evaluation in type_evaluations:
                    outcome_symbol = {
                        PolicyRuleOutcome.APPLIED: "✓",
                        PolicyRuleOutcome.SKIPPED: "-",
                        PolicyRuleOutcome.FAILED: "✗",
                        PolicyRuleOutcome.OVERRIDDEN: "⚠",
                    }[evaluation.outcome]
                    lines.append(f"  [{outcome_symbol}] {evaluation.timestamp}")
                    lines.append(f"      {evaluation.rationale}")

        # Chronological log
        lines.append("")
        lines.append("=" * 80)
        lines.append("CHRONOLOGICAL LOG")
        lines.append("=" * 80)

        for evaluation in self.evaluations:
            outcome_symbol = {
                PolicyRuleOutcome.APPLIED: "✓",
                PolicyRuleOutcome.SKIPPED: "-",
                PolicyRuleOutcome.FAILED: "✗",
                PolicyRuleOutcome.OVERRIDDEN: "⚠",
            }[evaluation.outcome]
            lines.append("")
            lines.append(
                f"[{outcome_symbol}] {evaluation.timestamp} | {evaluation.rule_type.value}"
            )
            lines.append(f"    {evaluation.rationale}")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)
