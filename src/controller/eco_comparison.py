"""ECO effectiveness comparison across multiple Cases in a Study.

This module provides functionality to:
- Compare ECO performance across different Cases
- Generate comparative reports ranking ECO effectiveness
- Identify best-performing ECO classes
- Support data-driven ECO selection
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .eco import ECOEffectiveness
from .types import ECOClass


@dataclass
class ECOComparisonMetrics:
    """Aggregated metrics for comparing a specific ECO across multiple Cases."""

    eco_name: str
    eco_class: ECOClass | None = None

    # Aggregated statistics across all Cases
    total_cases: int = 0  # Number of Cases where this ECO was applied
    total_applications: int = 0  # Total number of applications across all Cases
    successful_applications: int = 0
    failed_applications: int = 0

    # WNS improvement metrics
    average_wns_improvement_ps: float = 0.0  # Average across all applications
    best_wns_improvement_ps: float = float("-inf")  # Best improvement seen
    worst_wns_degradation_ps: float = 0.0  # Worst degradation seen

    # Case-level statistics
    cases_improved: int = 0  # Number of Cases where ECO improved WNS
    cases_degraded: int = 0  # Number of Cases where ECO degraded WNS
    cases_neutral: int = 0  # Number of Cases where ECO had minimal impact

    # Per-case effectiveness tracking
    per_case_effectiveness: dict[str, float] = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        """Calculate overall success rate across all applications."""
        if self.total_applications == 0:
            return 0.0
        return self.successful_applications / self.total_applications

    @property
    def improvement_rate(self) -> float:
        """Calculate rate of Cases where ECO improved WNS."""
        if self.total_cases == 0:
            return 0.0
        return self.cases_improved / self.total_cases

    def add_case_data(
        self,
        case_id: str,
        effectiveness: ECOEffectiveness
    ) -> None:
        """Add effectiveness data from a specific Case.

        Args:
            case_id: Identifier for the Case
            effectiveness: ECO effectiveness tracking from that Case
        """
        if effectiveness.total_applications == 0:
            return

        self.total_cases += 1
        self.total_applications += effectiveness.total_applications
        self.successful_applications += effectiveness.successful_applications
        self.failed_applications += effectiveness.failed_applications

        # Track WNS improvement
        wns_improvement = effectiveness.average_wns_improvement_ps
        self.per_case_effectiveness[case_id] = wns_improvement

        # Update aggregated WNS metrics
        # Recalculate average across all applications
        total_apps = self.total_applications
        self.average_wns_improvement_ps = (
            (self.average_wns_improvement_ps * (total_apps - effectiveness.total_applications)
             + wns_improvement * effectiveness.total_applications)
            / total_apps
        )

        # Update best/worst
        if effectiveness.best_wns_improvement_ps > self.best_wns_improvement_ps:
            self.best_wns_improvement_ps = effectiveness.best_wns_improvement_ps
        if effectiveness.worst_wns_degradation_ps < self.worst_wns_degradation_ps:
            self.worst_wns_degradation_ps = effectiveness.worst_wns_degradation_ps

        # Classify case impact
        IMPROVEMENT_THRESHOLD_PS = 100  # 100 ps minimum to count as improvement
        DEGRADATION_THRESHOLD_PS = -100  # -100 ps minimum to count as degradation

        if wns_improvement > IMPROVEMENT_THRESHOLD_PS:
            self.cases_improved += 1
        elif wns_improvement < DEGRADATION_THRESHOLD_PS:
            self.cases_degraded += 1
        else:
            self.cases_neutral += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_name": self.eco_name,
            "eco_class": self.eco_class.value if self.eco_class else None,
            "total_cases": self.total_cases,
            "total_applications": self.total_applications,
            "successful_applications": self.successful_applications,
            "failed_applications": self.failed_applications,
            "success_rate": self.success_rate,
            "average_wns_improvement_ps": self.average_wns_improvement_ps,
            "best_wns_improvement_ps": self.best_wns_improvement_ps,
            "worst_wns_degradation_ps": self.worst_wns_degradation_ps,
            "cases_improved": self.cases_improved,
            "cases_degraded": self.cases_degraded,
            "cases_neutral": self.cases_neutral,
            "improvement_rate": self.improvement_rate,
            "per_case_effectiveness": self.per_case_effectiveness,
        }


@dataclass
class ECOClassComparison:
    """Aggregated comparison of all ECOs within an ECO class."""

    eco_class: ECOClass
    eco_count: int = 0  # Number of distinct ECOs in this class
    total_applications: int = 0
    successful_applications: int = 0
    average_wns_improvement_ps: float = 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate for this ECO class."""
        if self.total_applications == 0:
            return 0.0
        return self.successful_applications / self.total_applications

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_class": self.eco_class.value,
            "eco_count": self.eco_count,
            "total_applications": self.total_applications,
            "successful_applications": self.successful_applications,
            "success_rate": self.success_rate,
            "average_wns_improvement_ps": self.average_wns_improvement_ps,
        }


class ECOComparator:
    """Compares ECO effectiveness across multiple Cases in a Study.

    This class aggregates ECO effectiveness data from multiple Cases and
    provides ranking and comparison functionality.
    """

    def __init__(self) -> None:
        """Initialize ECO comparator."""
        self.eco_metrics: dict[str, ECOComparisonMetrics] = {}
        self.eco_class_map: dict[str, ECOClass] = {}

    def add_case_eco_data(
        self,
        case_id: str,
        eco_effectiveness_map: dict[str, ECOEffectiveness],
        eco_class_map: dict[str, ECOClass] | None = None,
    ) -> None:
        """Add ECO effectiveness data from a Case.

        Args:
            case_id: Identifier for the Case
            eco_effectiveness_map: Map of ECO name to effectiveness tracking
            eco_class_map: Optional map of ECO name to ECO class
        """
        for eco_name, effectiveness in eco_effectiveness_map.items():
            if eco_name not in self.eco_metrics:
                self.eco_metrics[eco_name] = ECOComparisonMetrics(eco_name=eco_name)

            self.eco_metrics[eco_name].add_case_data(case_id, effectiveness)

            # Track ECO class if provided
            if eco_class_map and eco_name in eco_class_map:
                self.eco_class_map[eco_name] = eco_class_map[eco_name]
                if self.eco_metrics[eco_name].eco_class is None:
                    self.eco_metrics[eco_name].eco_class = eco_class_map[eco_name]

    def get_ranked_ecos(
        self,
        sort_by: str = "average_wns_improvement",
        min_applications: int = 1,
    ) -> list[ECOComparisonMetrics]:
        """Get ECOs ranked by effectiveness.

        Args:
            sort_by: Metric to sort by:
                - "average_wns_improvement": Sort by average WNS improvement (default)
                - "success_rate": Sort by application success rate
                - "improvement_rate": Sort by rate of Cases improved
                - "total_applications": Sort by total number of applications
            min_applications: Minimum applications required to be included

        Returns:
            List of ECO metrics sorted by specified criterion
        """
        # Filter by minimum applications
        filtered_ecos = [
            metrics for metrics in self.eco_metrics.values()
            if metrics.total_applications >= min_applications
        ]

        # Sort by requested criterion
        if sort_by == "average_wns_improvement":
            return sorted(
                filtered_ecos,
                key=lambda m: m.average_wns_improvement_ps,
                reverse=True
            )
        elif sort_by == "success_rate":
            return sorted(
                filtered_ecos,
                key=lambda m: m.success_rate,
                reverse=True
            )
        elif sort_by == "improvement_rate":
            return sorted(
                filtered_ecos,
                key=lambda m: m.improvement_rate,
                reverse=True
            )
        elif sort_by == "total_applications":
            return sorted(
                filtered_ecos,
                key=lambda m: m.total_applications,
                reverse=True
            )
        else:
            raise ValueError(f"Unknown sort criterion: {sort_by}")

    def get_eco_class_comparison(self) -> list[ECOClassComparison]:
        """Get aggregated comparison by ECO class.

        Returns:
            List of ECO class comparisons sorted by average WNS improvement
        """
        class_data: dict[ECOClass, ECOClassComparison] = {}

        for eco_name, metrics in self.eco_metrics.items():
            eco_class = self.eco_class_map.get(eco_name)
            if eco_class is None:
                continue

            if eco_class not in class_data:
                class_data[eco_class] = ECOClassComparison(eco_class=eco_class)

            comp = class_data[eco_class]
            comp.eco_count += 1
            comp.total_applications += metrics.total_applications
            comp.successful_applications += metrics.successful_applications

            # Update weighted average WNS improvement
            total_apps = comp.total_applications
            if total_apps > 0:
                comp.average_wns_improvement_ps = (
                    (comp.average_wns_improvement_ps * (total_apps - metrics.total_applications)
                     + metrics.average_wns_improvement_ps * metrics.total_applications)
                    / total_apps
                )

        # Return sorted by average WNS improvement
        return sorted(
            class_data.values(),
            key=lambda c: c.average_wns_improvement_ps,
            reverse=True
        )

    def generate_comparison_report(self, top_n: int = 10) -> str:
        """Generate human-readable comparison report.

        Args:
            top_n: Number of top ECOs to include in report

        Returns:
            Formatted text report
        """
        lines: list[str] = []

        # Header
        lines.append("=" * 80)
        lines.append("ECO EFFECTIVENESS COMPARISON REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Summary statistics
        total_ecos = len(self.eco_metrics)
        total_applications = sum(m.total_applications for m in self.eco_metrics.values())

        lines.append("SUMMARY")
        lines.append("-" * 80)
        lines.append(f"Total ECOs Analyzed:        {total_ecos}")
        lines.append(f"Total ECO Applications:     {total_applications}")
        lines.append("")

        # Top ECOs by WNS improvement
        lines.append(f"TOP {top_n} ECOs BY WNS IMPROVEMENT")
        lines.append("=" * 80)

        ranked_ecos = self.get_ranked_ecos(
            sort_by="average_wns_improvement",
            min_applications=1
        )

        for i, metrics in enumerate(ranked_ecos[:top_n], 1):
            lines.append("")
            lines.append(f"{i}. {metrics.eco_name}")
            lines.append(f"   ECO Class:              {metrics.eco_class.value if metrics.eco_class else 'unknown'}")
            lines.append(f"   Cases Applied:          {metrics.total_cases}")
            lines.append(f"   Total Applications:     {metrics.total_applications}")
            lines.append(f"   Success Rate:           {metrics.success_rate * 100:.1f}%")
            lines.append(f"   Avg WNS Improvement:    {metrics.average_wns_improvement_ps:,.0f} ps")
            lines.append(f"   Best Improvement:       {metrics.best_wns_improvement_ps:,.0f} ps")
            lines.append(f"   Worst Degradation:      {metrics.worst_wns_degradation_ps:,.0f} ps")
            lines.append(f"   Cases Improved:         {metrics.cases_improved}")
            lines.append(f"   Cases Degraded:         {metrics.cases_degraded}")
            lines.append(f"   Cases Neutral:          {metrics.cases_neutral}")
            lines.append(f"   Improvement Rate:       {metrics.improvement_rate * 100:.1f}%")

        lines.append("")
        lines.append("")

        # ECO class comparison
        lines.append("ECO CLASS COMPARISON")
        lines.append("=" * 80)

        class_comparisons = self.get_eco_class_comparison()

        for comp in class_comparisons:
            lines.append("")
            lines.append(f"Class: {comp.eco_class.value}")
            lines.append(f"   ECO Count:              {comp.eco_count}")
            lines.append(f"   Total Applications:     {comp.total_applications}")
            lines.append(f"   Success Rate:           {comp.success_rate * 100:.1f}%")
            lines.append(f"   Avg WNS Improvement:    {comp.average_wns_improvement_ps:,.0f} ps")

        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)

    def write_comparison_report(
        self,
        report_path: Path,
        top_n: int = 10
    ) -> Path:
        """Write comparison report to file.

        Args:
            report_path: Path where report should be written
            top_n: Number of top ECOs to include

        Returns:
            Path to written report
        """
        report_content = self.generate_comparison_report(top_n=top_n)

        # Ensure parent directory exists
        report_path.parent.mkdir(parents=True, exist_ok=True)

        # Write report
        with report_path.open("w") as f:
            f.write(report_content)

        return report_path

    def to_dict(self) -> dict[str, Any]:
        """Convert entire comparison to dictionary for JSON export.

        Returns:
            Dictionary with all comparison data
        """
        return {
            "eco_metrics": {
                name: metrics.to_dict()
                for name, metrics in self.eco_metrics.items()
            },
            "eco_class_comparison": [
                comp.to_dict()
                for comp in self.get_eco_class_comparison()
            ],
            "ranked_ecos": [
                metrics.to_dict()
                for metrics in self.get_ranked_ecos()
            ],
        }
