"""Study-to-study comparison functionality.

This module provides functionality to:
- Compare two completed Studies
- Generate comparison reports showing overall improvements/regressions
- Calculate deltas for key metrics (WNS, TNS, hot_ratio, etc.)
- Provide delta percentages and direction indicators (▲/▼)
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class StudyMetricsSummary:
    """Summary metrics from a completed Study."""

    study_name: str
    total_cases: int
    final_wns_ps: float | None = None
    final_tns_ps: float | None = None
    final_hot_ratio: float | None = None
    final_total_power_mw: float | None = None
    best_case_name: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricComparison:
    """Comparison of a single metric between two studies."""

    metric_name: str
    study1_value: float | None
    study2_value: float | None
    delta: float | None = None
    delta_percent: float | None = None
    direction: str = ""  # "▲" for improvement, "▼" for regression, "=" for no change
    improved: bool | None = None

    def __post_init__(self) -> None:
        """Calculate delta, percent change, and direction."""
        if self.study1_value is not None and self.study2_value is not None:
            # Calculate delta (study2 - study1)
            self.delta = self.study2_value - self.study1_value

            # Calculate percent change
            if self.study1_value != 0:
                self.delta_percent = (self.delta / abs(self.study1_value)) * 100.0
            else:
                self.delta_percent = None

            # Determine direction and improvement
            # For WNS/TNS: higher is better (less negative)
            # For hot_ratio: lower is better
            # For power: lower is better
            if self.metric_name in ["wns_ps", "tns_ps"]:
                # Higher (less negative) is better
                if self.delta > 0:
                    self.direction = "▲"
                    self.improved = True
                elif self.delta < 0:
                    self.direction = "▼"
                    self.improved = False
                else:
                    self.direction = "="
                    self.improved = None
            elif self.metric_name in ["hot_ratio", "total_power_mw"]:
                # Lower is better
                if self.delta < 0:
                    self.direction = "▲"
                    self.improved = True
                elif self.delta > 0:
                    self.direction = "▼"
                    self.improved = False
                else:
                    self.direction = "="
                    self.improved = None
        else:
            self.delta = None
            self.delta_percent = None
            self.direction = "N/A"
            self.improved = None


@dataclass
class StudyComparisonReport:
    """Comprehensive comparison report between two studies."""

    study1_name: str
    study2_name: str
    study1_summary: StudyMetricsSummary
    study2_summary: StudyMetricsSummary
    metric_comparisons: list[MetricComparison] = field(default_factory=list)
    overall_improvement: bool | None = None
    comparison_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def load_study_summary(study_name: str, telemetry_root: Path = Path("telemetry")) -> StudyMetricsSummary:
    """
    Load summary metrics from a completed Study.

    Args:
        study_name: Name of the Study
        telemetry_root: Root directory for telemetry data

    Returns:
        StudyMetricsSummary with final metrics

    Raises:
        FileNotFoundError: If Study telemetry not found
    """
    study_dir = telemetry_root / study_name

    if not study_dir.exists():
        raise FileNotFoundError(f"Study '{study_name}' not found in {telemetry_root}")

    # Look for summary file or aggregate from cases
    summary_file = study_dir / "study_summary.json"
    if summary_file.exists():
        with open(summary_file) as f:
            summary_data = json.load(f)

        return StudyMetricsSummary(
            study_name=study_name,
            total_cases=summary_data.get("total_cases", 0),
            final_wns_ps=summary_data.get("final_wns_ps"),
            final_tns_ps=summary_data.get("final_tns_ps"),
            final_hot_ratio=summary_data.get("final_hot_ratio"),
            final_total_power_mw=summary_data.get("final_total_power_mw"),
            best_case_name=summary_data.get("best_case_name"),
            metadata=summary_data.get("metadata", {}),
        )

    # If no summary file, aggregate from cases
    cases_dir = study_dir / "cases"
    if not cases_dir.exists():
        raise FileNotFoundError(f"No cases directory found for Study '{study_name}'")

    # Find all case telemetry files
    telemetry_files = list(cases_dir.glob("*_telemetry.json"))
    if not telemetry_files:
        raise FileNotFoundError(f"No telemetry files found for Study '{study_name}'")

    # Find the best case (highest WNS)
    best_wns = float("-inf")
    best_case = None
    best_metrics = {}

    for telemetry_file in telemetry_files:
        with open(telemetry_file) as f:
            telemetry_data = json.load(f)

        # Get trials data
        trials = telemetry_data.get("trials", [])
        if not trials:
            continue

        # Use first trial's metrics
        trial = trials[0]
        metrics = trial.get("metrics", {})

        wns = metrics.get("wns_ps", float("-inf"))
        if wns > best_wns:
            best_wns = wns
            best_case = telemetry_data.get("case_id", "unknown")
            best_metrics = metrics

    return StudyMetricsSummary(
        study_name=study_name,
        total_cases=len(telemetry_files),
        final_wns_ps=best_metrics.get("wns_ps"),
        final_tns_ps=best_metrics.get("tns_ps"),
        final_hot_ratio=best_metrics.get("hot_ratio"),
        final_total_power_mw=best_metrics.get("total_power_mw"),
        best_case_name=best_case,
    )


def compare_studies(
    study1_name: str,
    study2_name: str,
    telemetry_root: Path = Path("telemetry"),
) -> StudyComparisonReport:
    """
    Compare two completed Studies and generate comparison report.

    Args:
        study1_name: Name of first Study
        study2_name: Name of second Study
        telemetry_root: Root directory for telemetry data

    Returns:
        StudyComparisonReport with detailed comparison
    """
    # Load summaries for both studies
    study1_summary = load_study_summary(study1_name, telemetry_root)
    study2_summary = load_study_summary(study2_name, telemetry_root)

    # Create metric comparisons
    comparisons = []

    # WNS comparison
    comparisons.append(
        MetricComparison(
            metric_name="wns_ps",
            study1_value=study1_summary.final_wns_ps,
            study2_value=study2_summary.final_wns_ps,
        )
    )

    # TNS comparison
    comparisons.append(
        MetricComparison(
            metric_name="tns_ps",
            study1_value=study1_summary.final_tns_ps,
            study2_value=study2_summary.final_tns_ps,
        )
    )

    # Hot ratio comparison
    comparisons.append(
        MetricComparison(
            metric_name="hot_ratio",
            study1_value=study1_summary.final_hot_ratio,
            study2_value=study2_summary.final_hot_ratio,
        )
    )

    # Power comparison
    comparisons.append(
        MetricComparison(
            metric_name="total_power_mw",
            study1_value=study1_summary.final_total_power_mw,
            study2_value=study2_summary.final_total_power_mw,
        )
    )

    # Determine overall improvement
    # Study improved if majority of metrics improved
    improvements = [c.improved for c in comparisons if c.improved is not None]
    if improvements:
        overall_improvement = sum(improvements) > len(improvements) / 2
    else:
        overall_improvement = None

    return StudyComparisonReport(
        study1_name=study1_name,
        study2_name=study2_name,
        study1_summary=study1_summary,
        study2_summary=study2_summary,
        metric_comparisons=comparisons,
        overall_improvement=overall_improvement,
    )


def format_comparison_report(report: StudyComparisonReport) -> str:
    """
    Format comparison report as human-readable text.

    Args:
        report: StudyComparisonReport to format

    Returns:
        Formatted report string
    """
    lines = []

    # Header
    lines.append("=" * 80)
    lines.append("STUDY COMPARISON REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"Study 1: {report.study1_name}")
    lines.append(f"  Cases: {report.study1_summary.total_cases}")
    lines.append(f"  Best Case: {report.study1_summary.best_case_name or 'N/A'}")
    lines.append("")
    lines.append(f"Study 2: {report.study2_name}")
    lines.append(f"  Cases: {report.study2_summary.total_cases}")
    lines.append(f"  Best Case: {report.study2_summary.best_case_name or 'N/A'}")
    lines.append("")

    # Overall assessment
    if report.overall_improvement is not None:
        if report.overall_improvement:
            lines.append("Overall: Study 2 shows IMPROVEMENT over Study 1 ✓")
        else:
            lines.append("Overall: Study 2 shows REGRESSION from Study 1 ✗")
    else:
        lines.append("Overall: Insufficient data for overall assessment")
    lines.append("")

    # Metrics comparison table
    lines.append("METRICS COMPARISON")
    lines.append("-" * 80)
    lines.append(
        f"{'Metric':<20} {'Study 1':<15} {'Study 2':<15} {'Delta':<15} {'Δ%':<10} {'Dir':>5}"
    )
    lines.append("-" * 80)

    for comparison in report.metric_comparisons:
        metric = comparison.metric_name
        v1 = f"{comparison.study1_value:.2f}" if comparison.study1_value is not None else "N/A"
        v2 = f"{comparison.study2_value:.2f}" if comparison.study2_value is not None else "N/A"
        delta = f"{comparison.delta:.2f}" if comparison.delta is not None else "N/A"
        delta_pct = (
            f"{comparison.delta_percent:+.1f}%"
            if comparison.delta_percent is not None
            else "N/A"
        )
        direction = comparison.direction

        lines.append(f"{metric:<20} {v1:<15} {v2:<15} {delta:<15} {delta_pct:<10} {direction:>5}")

    lines.append("-" * 80)
    lines.append("")
    lines.append(f"Generated: {report.comparison_timestamp}")
    lines.append("")

    return "\n".join(lines)


def write_comparison_report(
    report: StudyComparisonReport,
    output_file: Path,
) -> None:
    """
    Write comparison report to file in JSON format.

    Args:
        report: StudyComparisonReport to write
        output_file: Path to output file
    """
    output_file.parent.mkdir(parents=True, exist_ok=True)

    report_data = {
        "study1_name": report.study1_name,
        "study2_name": report.study2_name,
        "study1_summary": {
            "study_name": report.study1_summary.study_name,
            "total_cases": report.study1_summary.total_cases,
            "final_wns_ps": report.study1_summary.final_wns_ps,
            "final_tns_ps": report.study1_summary.final_tns_ps,
            "final_hot_ratio": report.study1_summary.final_hot_ratio,
            "final_total_power_mw": report.study1_summary.final_total_power_mw,
            "best_case_name": report.study1_summary.best_case_name,
        },
        "study2_summary": {
            "study_name": report.study2_summary.study_name,
            "total_cases": report.study2_summary.total_cases,
            "final_wns_ps": report.study2_summary.final_wns_ps,
            "final_tns_ps": report.study2_summary.final_tns_ps,
            "final_hot_ratio": report.study2_summary.final_hot_ratio,
            "final_total_power_mw": report.study2_summary.final_total_power_mw,
            "best_case_name": report.study2_summary.best_case_name,
        },
        "metric_comparisons": [
            {
                "metric_name": c.metric_name,
                "study1_value": c.study1_value,
                "study2_value": c.study2_value,
                "delta": c.delta,
                "delta_percent": c.delta_percent,
                "direction": c.direction,
                "improved": c.improved,
            }
            for c in report.metric_comparisons
        ],
        "overall_improvement": report.overall_improvement,
        "comparison_timestamp": report.comparison_timestamp,
    }

    with open(output_file, "w") as f:
        json.dump(report_data, f, indent=2)
