"""Study-to-study comparison functionality.

This module provides functionality to:
- Compare two completed Studies
- Generate comparison reports showing overall improvements/regressions
- Calculate deltas for key metrics (WNS, TNS, hot_ratio, etc.)
- Provide delta percentages and direction indicators (▲/▼)
- Compare ECO effectiveness between studies
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
class ECOEffectivenessData:
    """ECO effectiveness metrics for a single ECO in one study."""

    eco_name: str
    total_applications: int = 0
    successful_applications: int = 0
    success_rate: float = 0.0
    average_wns_improvement_ps: float = 0.0


@dataclass
class ECOEffectivenessComparison:
    """Comparison of ECO effectiveness between two studies."""

    eco_name: str
    study1_success_rate: float | None
    study2_success_rate: float | None
    study1_applications: int | None
    study2_applications: int | None
    success_rate_delta: float | None = None
    direction: str = ""  # "▲" for improvement, "▼" for regression, "=" for no change
    improved: bool | None = None

    def __post_init__(self) -> None:
        """Calculate delta and direction for success rate."""
        if self.study1_success_rate is not None and self.study2_success_rate is not None:
            # Calculate delta (study2 - study1)
            self.success_rate_delta = self.study2_success_rate - self.study1_success_rate

            # For success rate: higher is better
            if self.success_rate_delta > 0.01:  # 1% threshold
                self.direction = "▲"
                self.improved = True
            elif self.success_rate_delta < -0.01:
                self.direction = "▼"
                self.improved = False
            else:
                self.direction = "="
                self.improved = None
        else:
            self.success_rate_delta = None
            self.direction = "N/A"
            self.improved = None


@dataclass
class ConfigurationDifference:
    """A single configuration difference between two studies."""

    category: str  # e.g., "warm_start", "survivor_selection", "diagnosis"
    description: str  # Human-readable description of the difference
    study1_value: str | None  # Configuration value in study 1
    study2_value: str | None  # Configuration value in study 2


@dataclass
class StudyComparisonReport:
    """Comprehensive comparison report between two studies."""

    study1_name: str
    study2_name: str
    study1_summary: StudyMetricsSummary
    study2_summary: StudyMetricsSummary
    metric_comparisons: list[MetricComparison] = field(default_factory=list)
    eco_effectiveness_comparisons: list[ECOEffectivenessComparison] = field(default_factory=list)
    configuration_differences: list[ConfigurationDifference] = field(default_factory=list)
    overall_improvement: bool | None = None
    comparison_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def load_eco_effectiveness_data(
    study_name: str,
    artifacts_root: Path = Path("artifacts"),
) -> dict[str, ECOEffectivenessData]:
    """
    Load ECO effectiveness data from a completed Study.

    Args:
        study_name: Name of the Study
        artifacts_root: Root directory for artifacts

    Returns:
        Dictionary mapping ECO name to effectiveness data
    """
    eco_map: dict[str, ECOEffectivenessData] = {}

    # Look for eco_leaderboard.json
    leaderboard_file = artifacts_root / study_name / "eco_leaderboard.json"

    if not leaderboard_file.exists():
        # No ECO leaderboard data available
        return eco_map

    with open(leaderboard_file) as f:
        leaderboard_data = json.load(f)

    # Extract ECO effectiveness from leaderboard entries
    for entry in leaderboard_data.get("entries", []):
        eco_name = entry.get("eco_name", "unknown")
        eco_map[eco_name] = ECOEffectivenessData(
            eco_name=eco_name,
            total_applications=entry.get("total_applications", 0),
            successful_applications=entry.get("successful_applications", 0),
            success_rate=entry.get("success_rate", 0.0),
            average_wns_improvement_ps=entry.get("average_wns_improvement_ps", 0.0),
        )

    return eco_map


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


def compare_study_configurations(
    study1_summary: StudyMetricsSummary,
    study2_summary: StudyMetricsSummary,
) -> list[ConfigurationDifference]:
    """
    Compare configuration differences between two studies.

    Args:
        study1_summary: Summary for first study
        study2_summary: Summary for second study

    Returns:
        List of configuration differences
    """
    differences = []

    # Extract configuration from metadata
    study1_config = study1_summary.metadata
    study2_config = study2_summary.metadata

    # Check warm_start usage
    study1_warm_start = study1_config.get("warm_start", {})
    study2_warm_start = study2_config.get("warm_start", {})

    study1_ws_enabled = study1_warm_start.get("enabled", False)
    study2_ws_enabled = study2_warm_start.get("enabled", False)

    if study1_ws_enabled != study2_ws_enabled:
        differences.append(
            ConfigurationDifference(
                category="warm_start",
                description="Warm-start configuration",
                study1_value="enabled" if study1_ws_enabled else "disabled",
                study2_value="enabled" if study2_ws_enabled else "disabled",
            )
        )
    elif study1_ws_enabled and study2_ws_enabled:
        # Both enabled, check if source study differs
        study1_source = study1_warm_start.get("source_study", "")
        study2_source = study2_warm_start.get("source_study", "")
        if study1_source != study2_source:
            differences.append(
                ConfigurationDifference(
                    category="warm_start",
                    description="Warm-start source study",
                    study1_value=study1_source or "none",
                    study2_value=study2_source or "none",
                )
            )

    # Check survivor selection method
    study1_selection = study1_config.get("survivor_selection_method", "top_n")
    study2_selection = study2_config.get("survivor_selection_method", "top_n")

    if study1_selection != study2_selection:
        differences.append(
            ConfigurationDifference(
                category="survivor_selection",
                description="Survivor selection method",
                study1_value=study1_selection,
                study2_value=study2_selection,
            )
        )

    # Check auto-diagnosis enablement
    study1_diagnosis = study1_config.get("auto_diagnosis_enabled", True)
    study2_diagnosis = study2_config.get("auto_diagnosis_enabled", True)

    if study1_diagnosis != study2_diagnosis:
        differences.append(
            ConfigurationDifference(
                category="diagnosis",
                description="Auto-diagnosis",
                study1_value="enabled" if study1_diagnosis else "disabled",
                study2_value="enabled" if study2_diagnosis else "disabled",
            )
        )

    return differences


def compare_studies(
    study1_name: str,
    study2_name: str,
    telemetry_root: Path = Path("telemetry"),
    artifacts_root: Path = Path("artifacts"),
) -> StudyComparisonReport:
    """
    Compare two completed Studies and generate comparison report.

    Args:
        study1_name: Name of first Study
        study2_name: Name of second Study
        telemetry_root: Root directory for telemetry data
        artifacts_root: Root directory for artifacts (for ECO leaderboard data)

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

    # Load ECO effectiveness data for both studies
    study1_eco_data = load_eco_effectiveness_data(study1_name, artifacts_root)
    study2_eco_data = load_eco_effectiveness_data(study2_name, artifacts_root)

    # Create ECO effectiveness comparisons
    eco_comparisons = []

    # Get all unique ECO names from both studies
    all_eco_names = set(study1_eco_data.keys()) | set(study2_eco_data.keys())

    for eco_name in sorted(all_eco_names):
        study1_eco = study1_eco_data.get(eco_name)
        study2_eco = study2_eco_data.get(eco_name)

        eco_comparisons.append(
            ECOEffectivenessComparison(
                eco_name=eco_name,
                study1_success_rate=study1_eco.success_rate if study1_eco else None,
                study2_success_rate=study2_eco.success_rate if study2_eco else None,
                study1_applications=study1_eco.total_applications if study1_eco else None,
                study2_applications=study2_eco.total_applications if study2_eco else None,
            )
        )

    # Compare configurations
    config_differences = compare_study_configurations(study1_summary, study2_summary)

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
        eco_effectiveness_comparisons=eco_comparisons,
        configuration_differences=config_differences,
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

    # Key differences section
    if report.configuration_differences:
        lines.append("KEY DIFFERENCES")
        lines.append("-" * 80)
        for diff in report.configuration_differences:
            lines.append(f"{diff.description}:")
            lines.append(f"  Study 1: {diff.study1_value or 'N/A'}")
            lines.append(f"  Study 2: {diff.study2_value or 'N/A'}")
            lines.append("")
        lines.append("-" * 80)
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

    # ECO effectiveness comparison table
    if report.eco_effectiveness_comparisons:
        lines.append("ECO EFFECTIVENESS COMPARISON")
        lines.append("-" * 80)
        lines.append(
            f"{'ECO Name':<30} {'V1 Rate':<12} {'V2 Rate':<12} {'Delta':<12} {'Dir':>5}"
        )
        lines.append("-" * 80)

        for eco_comp in report.eco_effectiveness_comparisons:
            eco_name = eco_comp.eco_name[:29]
            v1_rate = (
                f"{eco_comp.study1_success_rate * 100:.1f}%"
                if eco_comp.study1_success_rate is not None
                else "N/A"
            )
            v2_rate = (
                f"{eco_comp.study2_success_rate * 100:.1f}%"
                if eco_comp.study2_success_rate is not None
                else "N/A"
            )
            delta = (
                f"{eco_comp.success_rate_delta * 100:+.1f}%"
                if eco_comp.success_rate_delta is not None
                else "N/A"
            )
            direction = eco_comp.direction

            lines.append(
                f"{eco_name:<30} {v1_rate:<12} {v2_rate:<12} {delta:<12} {direction:>5}"
            )

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
        "eco_effectiveness_comparisons": [
            {
                "eco_name": e.eco_name,
                "study1_success_rate": e.study1_success_rate,
                "study2_success_rate": e.study2_success_rate,
                "study1_applications": e.study1_applications,
                "study2_applications": e.study2_applications,
                "success_rate_delta": e.success_rate_delta,
                "direction": e.direction,
                "improved": e.improved,
            }
            for e in report.eco_effectiveness_comparisons
        ],
        "configuration_differences": [
            {
                "category": d.category,
                "description": d.description,
                "study1_value": d.study1_value,
                "study2_value": d.study2_value,
            }
            for d in report.configuration_differences
        ],
        "overall_improvement": report.overall_improvement,
        "comparison_timestamp": report.comparison_timestamp,
    }

    with open(output_file, "w") as f:
        json.dump(report_data, f, indent=2)
