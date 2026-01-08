"""Case metrics diff report generation.

This module provides functionality to:
- Compare derived Case metrics against baseline Case
- Compute metric deltas (WNS, TNS, congestion, etc.)
- Generate diff reports showing improvements/regressions
- Support survivor ranking based on diff metrics
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .types import TrialMetrics, TimingMetrics, CongestionMetrics


@dataclass
class MetricDelta:
    """Delta between baseline and derived metrics for a single metric."""

    metric_name: str
    baseline_value: float | int | None
    derived_value: float | int | None
    delta: float | int | None = None  # derived - baseline
    delta_percent: float | None = None  # (delta / baseline) * 100
    improved: bool | None = None  # True if delta is improvement, False if regression

    def __post_init__(self) -> None:
        """Compute delta and improvement after initialization."""
        if self.baseline_value is not None and self.derived_value is not None:
            # Compute absolute delta
            if isinstance(self.baseline_value, int) and isinstance(self.derived_value, int):
                self.delta = self.derived_value - self.baseline_value
            else:
                self.delta = float(self.derived_value) - float(self.baseline_value)

            # Compute percent change (handle division by zero)
            if self.baseline_value != 0:
                self.delta_percent = (float(self.delta) / abs(float(self.baseline_value))) * 100.0
            else:
                # If baseline is 0 and derived is non-zero, treat as infinite change
                self.delta_percent = None if self.derived_value == 0 else float('inf')

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metric_name": self.metric_name,
            "baseline_value": self.baseline_value,
            "derived_value": self.derived_value,
            "delta": self.delta,
            "delta_percent": self.delta_percent,
            "improved": self.improved,
        }


@dataclass
class CaseDiffReport:
    """Complete diff report comparing derived Case metrics vs baseline Case."""

    baseline_case_id: str
    derived_case_id: str
    eco_name: str

    # Timing deltas
    wns_delta: MetricDelta | None = None
    tns_delta: MetricDelta | None = None
    failing_endpoints_delta: MetricDelta | None = None

    # Congestion deltas
    hot_ratio_delta: MetricDelta | None = None
    bins_hot_delta: MetricDelta | None = None
    max_overflow_delta: MetricDelta | None = None

    # Overall assessment
    overall_improvement: bool = False  # True if net improvement
    improvement_summary: str = ""  # Human-readable summary

    # All metric deltas for comprehensive analysis
    all_deltas: dict[str, MetricDelta] = field(default_factory=dict)

    def compute_improvement_summary(self) -> None:
        """Compute overall improvement assessment and summary.

        Improvement is determined by:
        - WNS improvement is most important (less negative = better)
        - Congestion reduction is secondary (lower hot_ratio = better)
        - Failing endpoints reduction is tertiary
        """
        improvements = []
        regressions = []

        # Timing improvements (for WNS, higher/less negative is better)
        if self.wns_delta and self.wns_delta.delta is not None:
            if self.wns_delta.delta > 0:  # Less negative WNS
                improvements.append(f"WNS improved by {self.wns_delta.delta} ps")
                self.wns_delta.improved = True
            elif self.wns_delta.delta < 0:  # More negative WNS
                regressions.append(f"WNS degraded by {abs(self.wns_delta.delta)} ps")
                self.wns_delta.improved = False
            else:
                self.wns_delta.improved = None  # Neutral

        if self.tns_delta and self.tns_delta.delta is not None:
            if self.tns_delta.delta > 0:  # Less negative TNS
                improvements.append(f"TNS improved by {self.tns_delta.delta} ps")
                self.tns_delta.improved = True
            elif self.tns_delta.delta < 0:
                regressions.append(f"TNS degraded by {abs(self.tns_delta.delta)} ps")
                self.tns_delta.improved = False
            else:
                self.tns_delta.improved = None

        if self.failing_endpoints_delta and self.failing_endpoints_delta.delta is not None:
            if self.failing_endpoints_delta.delta < 0:  # Fewer failing endpoints is better
                improvements.append(f"Failing endpoints reduced by {abs(self.failing_endpoints_delta.delta)}")
                self.failing_endpoints_delta.improved = True
            elif self.failing_endpoints_delta.delta > 0:
                regressions.append(f"Failing endpoints increased by {self.failing_endpoints_delta.delta}")
                self.failing_endpoints_delta.improved = False
            else:
                self.failing_endpoints_delta.improved = None

        # Congestion improvements (lower is better)
        if self.hot_ratio_delta and self.hot_ratio_delta.delta is not None:
            if self.hot_ratio_delta.delta < 0:  # Lower hot_ratio is better
                improvements.append(f"Hot ratio reduced by {abs(self.hot_ratio_delta.delta):.4f}")
                self.hot_ratio_delta.improved = True
            elif self.hot_ratio_delta.delta > 0:
                regressions.append(f"Hot ratio increased by {self.hot_ratio_delta.delta:.4f}")
                self.hot_ratio_delta.improved = False
            else:
                self.hot_ratio_delta.improved = None

        if self.bins_hot_delta and self.bins_hot_delta.delta is not None:
            if self.bins_hot_delta.delta < 0:  # Fewer hot bins is better
                improvements.append(f"Hot bins reduced by {abs(self.bins_hot_delta.delta)}")
                self.bins_hot_delta.improved = True
            elif self.bins_hot_delta.delta > 0:
                regressions.append(f"Hot bins increased by {self.bins_hot_delta.delta}")
                self.bins_hot_delta.improved = False
            else:
                self.bins_hot_delta.improved = None

        if self.max_overflow_delta and self.max_overflow_delta.delta is not None:
            if self.max_overflow_delta.delta < 0:  # Lower overflow is better
                improvements.append(f"Max overflow reduced by {abs(self.max_overflow_delta.delta)}")
                self.max_overflow_delta.improved = True
            elif self.max_overflow_delta.delta > 0:
                regressions.append(f"Max overflow increased by {self.max_overflow_delta.delta}")
                self.max_overflow_delta.improved = False
            else:
                self.max_overflow_delta.improved = None

        # Overall improvement: WNS improvement OR (no WNS regression AND congestion improvement)
        wns_improved = self.wns_delta and self.wns_delta.improved is True
        wns_neutral = self.wns_delta is None or self.wns_delta.improved is None
        congestion_improved = self.hot_ratio_delta and self.hot_ratio_delta.improved is True

        # Only mark as overall improvement if there's actual improvement, not neutral
        if wns_improved or (wns_neutral and congestion_improved):
            self.overall_improvement = True
        else:
            self.overall_improvement = False

        # Build summary
        if improvements:
            self.improvement_summary = "Improvements: " + "; ".join(improvements)
        if regressions:
            if self.improvement_summary:
                self.improvement_summary += " | Regressions: " + "; ".join(regressions)
            else:
                self.improvement_summary = "Regressions: " + "; ".join(regressions)
        if not self.improvement_summary:
            self.improvement_summary = "No significant changes detected"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "baseline_case_id": self.baseline_case_id,
            "derived_case_id": self.derived_case_id,
            "eco_name": self.eco_name,
            "timing_deltas": {
                "wns": self.wns_delta.to_dict() if self.wns_delta else None,
                "tns": self.tns_delta.to_dict() if self.tns_delta else None,
                "failing_endpoints": self.failing_endpoints_delta.to_dict() if self.failing_endpoints_delta else None,
            },
            "congestion_deltas": {
                "hot_ratio": self.hot_ratio_delta.to_dict() if self.hot_ratio_delta else None,
                "bins_hot": self.bins_hot_delta.to_dict() if self.bins_hot_delta else None,
                "max_overflow": self.max_overflow_delta.to_dict() if self.max_overflow_delta else None,
            },
            "overall_improvement": self.overall_improvement,
            "improvement_summary": self.improvement_summary,
            "all_deltas": {k: v.to_dict() for k, v in self.all_deltas.items()},
        }

    def to_text(self) -> str:
        """Generate human-readable text report."""
        lines = []
        lines.append("=" * 80)
        lines.append("CASE DIFF REPORT")
        lines.append("=" * 80)
        lines.append(f"Baseline Case: {self.baseline_case_id}")
        lines.append(f"Derived Case:  {self.derived_case_id}")
        lines.append(f"ECO Applied:   {self.eco_name}")
        lines.append("")
        lines.append("-" * 80)
        lines.append("TIMING METRICS")
        lines.append("-" * 80)

        if self.wns_delta:
            symbol = "✓" if self.wns_delta.improved else ("✗" if self.wns_delta.improved is False else "•")
            lines.append(f"  {symbol} WNS:")
            lines.append(f"      Baseline: {self.wns_delta.baseline_value} ps")
            lines.append(f"      Derived:  {self.wns_delta.derived_value} ps")
            lines.append(f"      Delta:    {self.wns_delta.delta:+} ps")
            if self.wns_delta.delta_percent is not None and self.wns_delta.delta_percent != float('inf'):
                lines.append(f"      Change:   {self.wns_delta.delta_percent:+.2f}%")

        if self.tns_delta:
            symbol = "✓" if self.tns_delta.improved else ("✗" if self.tns_delta.improved is False else "•")
            lines.append(f"  {symbol} TNS:")
            lines.append(f"      Baseline: {self.tns_delta.baseline_value} ps")
            lines.append(f"      Derived:  {self.tns_delta.derived_value} ps")
            lines.append(f"      Delta:    {self.tns_delta.delta:+} ps")

        if self.failing_endpoints_delta:
            symbol = "✓" if self.failing_endpoints_delta.improved else ("✗" if self.failing_endpoints_delta.improved is False else "•")
            lines.append(f"  {symbol} Failing Endpoints:")
            lines.append(f"      Baseline: {self.failing_endpoints_delta.baseline_value}")
            lines.append(f"      Derived:  {self.failing_endpoints_delta.derived_value}")
            lines.append(f"      Delta:    {self.failing_endpoints_delta.delta:+}")

        if self.hot_ratio_delta or self.bins_hot_delta or self.max_overflow_delta:
            lines.append("")
            lines.append("-" * 80)
            lines.append("CONGESTION METRICS")
            lines.append("-" * 80)

            if self.hot_ratio_delta:
                symbol = "✓" if self.hot_ratio_delta.improved else ("✗" if self.hot_ratio_delta.improved is False else "•")
                lines.append(f"  {symbol} Hot Ratio:")
                lines.append(f"      Baseline: {self.hot_ratio_delta.baseline_value:.4f}")
                lines.append(f"      Derived:  {self.hot_ratio_delta.derived_value:.4f}")
                lines.append(f"      Delta:    {self.hot_ratio_delta.delta:+.4f}")

            if self.bins_hot_delta:
                symbol = "✓" if self.bins_hot_delta.improved else ("✗" if self.bins_hot_delta.improved is False else "•")
                lines.append(f"  {symbol} Hot Bins:")
                lines.append(f"      Baseline: {self.bins_hot_delta.baseline_value}")
                lines.append(f"      Derived:  {self.bins_hot_delta.derived_value}")
                lines.append(f"      Delta:    {self.bins_hot_delta.delta:+}")

            if self.max_overflow_delta:
                symbol = "✓" if self.max_overflow_delta.improved else ("✗" if self.max_overflow_delta.improved is False else "•")
                lines.append(f"  {symbol} Max Overflow:")
                lines.append(f"      Baseline: {self.max_overflow_delta.baseline_value}")
                lines.append(f"      Derived:  {self.max_overflow_delta.derived_value}")
                lines.append(f"      Delta:    {self.max_overflow_delta.delta:+}")

        lines.append("")
        lines.append("-" * 80)
        lines.append("OVERALL ASSESSMENT")
        lines.append("-" * 80)
        lines.append(f"  Overall Improvement: {'YES' if self.overall_improvement else 'NO'}")
        lines.append(f"  Summary: {self.improvement_summary}")
        lines.append("=" * 80)

        return "\n".join(lines)


def generate_diff_report(
    baseline_case_id: str,
    derived_case_id: str,
    eco_name: str,
    baseline_metrics: TrialMetrics,
    derived_metrics: TrialMetrics,
) -> CaseDiffReport:
    """Generate diff report comparing derived Case metrics vs baseline.

    Args:
        baseline_case_id: Identifier for baseline Case
        derived_case_id: Identifier for derived Case (with ECO applied)
        eco_name: Name of ECO that was applied
        baseline_metrics: Metrics from baseline Case trial
        derived_metrics: Metrics from derived Case trial

    Returns:
        Complete diff report with metric deltas and improvement assessment
    """
    report = CaseDiffReport(
        baseline_case_id=baseline_case_id,
        derived_case_id=derived_case_id,
        eco_name=eco_name,
    )

    # Timing deltas
    if baseline_metrics.timing and derived_metrics.timing:
        baseline_timing = baseline_metrics.timing
        derived_timing = derived_metrics.timing

        # WNS delta
        report.wns_delta = MetricDelta(
            metric_name="wns_ps",
            baseline_value=baseline_timing.wns_ps,
            derived_value=derived_timing.wns_ps,
        )
        report.all_deltas["wns_ps"] = report.wns_delta

        # TNS delta
        if baseline_timing.tns_ps is not None and derived_timing.tns_ps is not None:
            report.tns_delta = MetricDelta(
                metric_name="tns_ps",
                baseline_value=baseline_timing.tns_ps,
                derived_value=derived_timing.tns_ps,
            )
            report.all_deltas["tns_ps"] = report.tns_delta

        # Failing endpoints delta
        if baseline_timing.failing_endpoints is not None and derived_timing.failing_endpoints is not None:
            report.failing_endpoints_delta = MetricDelta(
                metric_name="failing_endpoints",
                baseline_value=baseline_timing.failing_endpoints,
                derived_value=derived_timing.failing_endpoints,
            )
            report.all_deltas["failing_endpoints"] = report.failing_endpoints_delta

    # Congestion deltas
    if baseline_metrics.congestion and derived_metrics.congestion:
        baseline_congestion = baseline_metrics.congestion
        derived_congestion = derived_metrics.congestion

        # Hot ratio delta
        report.hot_ratio_delta = MetricDelta(
            metric_name="hot_ratio",
            baseline_value=baseline_congestion.hot_ratio,
            derived_value=derived_congestion.hot_ratio,
        )
        report.all_deltas["hot_ratio"] = report.hot_ratio_delta

        # Hot bins delta
        report.bins_hot_delta = MetricDelta(
            metric_name="bins_hot",
            baseline_value=baseline_congestion.bins_hot,
            derived_value=derived_congestion.bins_hot,
        )
        report.all_deltas["bins_hot"] = report.bins_hot_delta

        # Max overflow delta
        if baseline_congestion.max_overflow is not None and derived_congestion.max_overflow is not None:
            report.max_overflow_delta = MetricDelta(
                metric_name="max_overflow",
                baseline_value=baseline_congestion.max_overflow,
                derived_value=derived_congestion.max_overflow,
            )
            report.all_deltas["max_overflow"] = report.max_overflow_delta

    # Compute overall improvement assessment
    report.compute_improvement_summary()

    return report


def save_diff_report(report: CaseDiffReport, output_dir: Path) -> None:
    """Save diff report to disk in both JSON and text formats.

    Args:
        report: Diff report to save
        output_dir: Directory to save reports (typically Case artifact directory)
    """
    import json

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save JSON format
    json_path = output_dir / "diff_report.json"
    with open(json_path, "w") as f:
        json.dump(report.to_dict(), f, indent=2)

    # Save text format
    text_path = output_dir / "diff_report.txt"
    with open(text_path, "w") as f:
        f.write(report.to_text())
