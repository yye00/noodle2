"""
Doom detection - identifies hopeless cases for intelligent termination.

Doom detection prevents wasted compute on cases that cannot succeed:
- Metric-hopeless: WNS/TNS/hot_ratio beyond recovery thresholds
- Trajectory-doomed: Stagnation across multiple stages (< 2% improvement)
- ECO-exhausted: All applicable ECOs have failed or are suspicious

This is SAFETY-CRITICAL: false positives terminate potentially viable cases.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from src.controller.case import Case
    from src.controller.eco import ECOPrior, ECOOutcome


class DoomType(str, Enum):
    """Type of doom detected."""

    METRIC_HOPELESS = "metric_hopeless"
    TRAJECTORY_DOOM = "trajectory_doom"
    ECO_EXHAUSTION = "eco_exhaustion"
    STATISTICAL_DOOM = "statistical_doom"


@dataclass
class DoomConfig:
    """Configuration for doom detection."""

    enabled: bool = True

    # Metric thresholds - beyond these values, recovery is considered impossible
    wns_ps_hopeless: float = -10000  # WNS worse than -10ns
    hot_ratio_hopeless: float = 0.8  # hot_ratio > 0.8
    tns_ps_hopeless: float = -500000  # TNS worse than -500ns

    # Trajectory analysis
    trajectory_enabled: bool = True
    min_stages_for_trajectory: int = 2
    regression_threshold: float = 0.1  # 10% regression triggers check
    stagnation_threshold: float = 0.02  # <2% improvement is stagnation
    consecutive_stagnation: int = 3  # 3 stagnant stages = doomed

    # ECO exhaustion
    eco_exhaustion_enabled: bool = True

    # Statistical doom (for multi-trial studies)
    statistical_doom_enabled: bool = True
    min_trials_for_statistical: int = 10
    success_rate_threshold: float = 0.1  # <10% success rate

    def validate(self) -> None:
        """Validate doom configuration."""
        if self.min_stages_for_trajectory < 1:
            raise ValueError("min_stages_for_trajectory must be >= 1")
        if not (0.0 < self.stagnation_threshold < 1.0):
            raise ValueError("stagnation_threshold must be in (0, 1)")
        if self.consecutive_stagnation < 1:
            raise ValueError("consecutive_stagnation must be >= 1")


@dataclass
class DoomClassification:
    """Result of doom detection analysis."""

    is_doomed: bool
    doom_type: DoomType | None
    trigger: str  # What triggered the doom detection
    reason: str  # Human-readable explanation
    confidence: float  # 0.0 to 1.0, how certain we are
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "is_doomed": self.is_doomed,
            "doom_type": self.doom_type.value if self.doom_type else None,
            "trigger": self.trigger,
            "reason": self.reason,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


class DoomDetector:
    """Detects hopeless cases for intelligent termination."""

    def __init__(self, config: DoomConfig):
        """Initialize doom detector."""
        self.config = config
        config.validate()

    def check_doom(
        self,
        case: "Case",
        metrics: dict[str, Any],
        stage_history: list[dict[str, Any]] | None = None,
        eco_priors: list["ECOPrior"] | None = None,
    ) -> DoomClassification:
        """
        Check if a case is doomed and should be terminated.

        Args:
            case: The case being evaluated
            metrics: Current metrics for the case
            stage_history: Historical metrics from previous stages (optional)
            eco_priors: ECO prior knowledge for exhaustion check (optional)

        Returns:
            DoomClassification with doom status and reasoning
        """
        if not self.config.enabled:
            return DoomClassification(
                is_doomed=False,
                doom_type=None,
                trigger="doom_detection_disabled",
                reason="Doom detection is disabled",
                confidence=1.0,
            )

        # Check 1: Metric-hopeless
        metric_doom = self._check_metric_hopeless(metrics)
        if metric_doom.is_doomed:
            return metric_doom

        # Check 2: Trajectory-doomed (requires history)
        if stage_history and self.config.trajectory_enabled:
            trajectory_doom = self._check_trajectory_doom(metrics, stage_history)
            if trajectory_doom.is_doomed:
                return trajectory_doom

        # Check 3: ECO exhaustion (requires priors)
        if eco_priors and self.config.eco_exhaustion_enabled:
            eco_doom = self._check_eco_exhaustion(eco_priors)
            if eco_doom.is_doomed:
                return eco_doom

        # Not doomed
        return DoomClassification(
            is_doomed=False,
            doom_type=None,
            trigger="no_doom_detected",
            reason="Case metrics and trajectory are within acceptable bounds",
            confidence=1.0,
        )

    def _check_metric_hopeless(self, metrics: dict[str, Any]) -> DoomClassification:
        """Check if metrics are beyond recovery thresholds."""
        wns_ps = metrics.get("wns_ps")
        hot_ratio = metrics.get("hot_ratio")
        tns_ps = metrics.get("tns_ps")

        # Check WNS hopeless threshold
        if wns_ps is not None and wns_ps < self.config.wns_ps_hopeless:
            return DoomClassification(
                is_doomed=True,
                doom_type=DoomType.METRIC_HOPELESS,
                trigger=f"wns_ps={wns_ps} < threshold={self.config.wns_ps_hopeless}",
                reason=f"WNS of {wns_ps}ps is beyond recovery threshold (-10ns). "
                f"This indicates fundamental design issues that ECOs cannot fix.",
                confidence=0.95,
                metadata={
                    "wns_ps": wns_ps,
                    "threshold": self.config.wns_ps_hopeless,
                    "metric_type": "wns_ps",
                },
            )

        # Check hot_ratio hopeless threshold
        if hot_ratio is not None and hot_ratio > self.config.hot_ratio_hopeless:
            return DoomClassification(
                is_doomed=True,
                doom_type=DoomType.METRIC_HOPELESS,
                trigger=f"hot_ratio={hot_ratio:.3f} > threshold={self.config.hot_ratio_hopeless}",
                reason=f"Hot ratio of {hot_ratio:.3f} indicates >80% of design is timing-critical. "
                f"ECOs cannot provide sufficient improvement with such widespread violations.",
                confidence=0.90,
                metadata={
                    "hot_ratio": hot_ratio,
                    "threshold": self.config.hot_ratio_hopeless,
                    "metric_type": "hot_ratio",
                },
            )

        # Check TNS hopeless threshold
        if tns_ps is not None and tns_ps < self.config.tns_ps_hopeless:
            return DoomClassification(
                is_doomed=True,
                doom_type=DoomType.METRIC_HOPELESS,
                trigger=f"tns_ps={tns_ps} < threshold={self.config.tns_ps_hopeless}",
                reason=f"TNS of {tns_ps}ps indicates pervasive timing violations "
                f"that cannot be resolved with localized ECOs.",
                confidence=0.90,
                metadata={
                    "tns_ps": tns_ps,
                    "threshold": self.config.tns_ps_hopeless,
                    "metric_type": "tns_ps",
                },
            )

        # Metrics are not hopeless
        return DoomClassification(
            is_doomed=False,
            doom_type=None,
            trigger="metrics_acceptable",
            reason="All metrics are within recovery bounds",
            confidence=1.0,
        )

    def _check_trajectory_doom(
        self, current_metrics: dict[str, Any], stage_history: list[dict[str, Any]]
    ) -> DoomClassification:
        """
        Check if case trajectory shows stagnation (< 2% improvement over multiple stages).

        Args:
            current_metrics: Current stage metrics
            stage_history: List of metrics from previous stages (chronological order)

        Returns:
            DoomClassification indicating if trajectory is doomed
        """
        if len(stage_history) < self.config.min_stages_for_trajectory:
            return DoomClassification(
                is_doomed=False,
                doom_type=None,
                trigger="insufficient_history",
                reason=f"Only {len(stage_history)} stages completed, need {self.config.min_stages_for_trajectory} for trajectory analysis",
                confidence=1.0,
            )

        # Extract WNS from history (primary metric for trajectory)
        wns_history = []
        for stage_metrics in stage_history:
            if "wns_ps" in stage_metrics:
                wns_history.append(stage_metrics["wns_ps"])

        if len(wns_history) < self.config.min_stages_for_trajectory:
            return DoomClassification(
                is_doomed=False,
                doom_type=None,
                trigger="insufficient_wns_history",
                reason="Not enough WNS data points for trajectory analysis",
                confidence=1.0,
            )

        # Check for consecutive stagnation
        stagnation_count = 0
        improvement_percentages = []

        for i in range(1, len(wns_history)):
            prev_wns = wns_history[i - 1]
            curr_wns = wns_history[i]

            # Calculate improvement percentage
            # For WNS: less negative is better, so improvement is (curr - prev) / |prev|
            if prev_wns < 0:  # Negative WNS (violations)
                improvement_pct = (curr_wns - prev_wns) / abs(prev_wns)
            else:  # Positive WNS (slack)
                # Shouldn't happen in extreme cases, but handle it
                improvement_pct = 0.0

            improvement_percentages.append(improvement_pct)

            # Check if this stage showed stagnation
            if improvement_pct < self.config.stagnation_threshold:
                stagnation_count += 1
            else:
                # Reset stagnation counter on any significant improvement
                stagnation_count = 0

        # Check for regression (getting worse)
        if improvement_percentages:
            latest_improvement = improvement_percentages[-1]
            if latest_improvement < -self.config.regression_threshold:
                return DoomClassification(
                    is_doomed=True,
                    doom_type=DoomType.TRAJECTORY_DOOM,
                    trigger=f"regression_detected: {latest_improvement:.1%}",
                    reason=f"Latest stage shows {abs(latest_improvement):.1%} regression. "
                    f"Trajectory is moving away from solution.",
                    confidence=0.85,
                    metadata={
                        "wns_history": wns_history,
                        "improvement_percentages": improvement_percentages,
                        "latest_improvement": latest_improvement,
                    },
                )

        # Check for consecutive stagnation
        if stagnation_count >= self.config.consecutive_stagnation:
            avg_stagnation = sum(improvement_percentages[-stagnation_count:]) / stagnation_count
            return DoomClassification(
                is_doomed=True,
                doom_type=DoomType.TRAJECTORY_DOOM,
                trigger=f"consecutive_stagnation: {stagnation_count} stages",
                reason=f"No meaningful progress in {stagnation_count} consecutive stages "
                f"(avg improvement: {avg_stagnation:.1%}). "
                f"Current trajectory cannot reach timing closure.",
                confidence=0.80,
                metadata={
                    "wns_history": wns_history,
                    "improvement_percentages": improvement_percentages,
                    "stagnation_count": stagnation_count,
                    "avg_improvement": avg_stagnation,
                },
            )

        # Trajectory is healthy
        return DoomClassification(
            is_doomed=False,
            doom_type=None,
            trigger="trajectory_healthy",
            reason="Case is showing acceptable improvement trajectory",
            confidence=1.0,
            metadata={
                "improvement_percentages": improvement_percentages,
            },
        )

    def _check_eco_exhaustion(self, eco_priors: list["ECOPrior"]) -> DoomClassification:
        """
        Check if all applicable ECOs have failed or are suspicious.

        Args:
            eco_priors: List of ECO priors with outcomes

        Returns:
            DoomClassification indicating if ECOs are exhausted
        """
        if not eco_priors:
            return DoomClassification(
                is_doomed=False,
                doom_type=None,
                trigger="no_eco_priors",
                reason="No ECO priors available for exhaustion check",
                confidence=1.0,
            )

        # Count ECO outcomes
        successful_count = 0
        failed_count = 0
        suspicious_count = 0
        uncertain_count = 0

        for prior in eco_priors:
            if hasattr(prior, 'outcome'):
                outcome = prior.outcome
                if outcome == "successful":
                    successful_count += 1
                elif outcome == "failed":
                    failed_count += 1
                elif outcome == "suspicious":
                    suspicious_count += 1
                elif outcome == "uncertain":
                    uncertain_count += 1

        total_with_outcomes = successful_count + failed_count + suspicious_count + uncertain_count

        if total_with_outcomes == 0:
            return DoomClassification(
                is_doomed=False,
                doom_type=None,
                trigger="no_eco_outcomes",
                reason="No ECO outcomes recorded yet",
                confidence=1.0,
            )

        # Check if all ECOs failed
        if failed_count == total_with_outcomes and total_with_outcomes >= 3:
            return DoomClassification(
                is_doomed=True,
                doom_type=DoomType.ECO_EXHAUSTION,
                trigger=f"all_ecos_failed: {failed_count}/{total_with_outcomes}",
                reason=f"All {failed_count} applicable ECOs have failed. "
                f"No viable ECO options remain for this case.",
                confidence=0.90,
                metadata={
                    "total_ecos": total_with_outcomes,
                    "failed_count": failed_count,
                },
            )

        # Check if all ECOs are suspicious or failed
        doomed_count = failed_count + suspicious_count
        if doomed_count == total_with_outcomes and total_with_outcomes >= 3:
            return DoomClassification(
                is_doomed=True,
                doom_type=DoomType.ECO_EXHAUSTION,
                trigger=f"all_ecos_suspicious_or_failed: {doomed_count}/{total_with_outcomes}",
                reason=f"All ECOs are either failed ({failed_count}) or suspicious ({suspicious_count}). "
                f"No reliable ECO options remain.",
                confidence=0.85,
                metadata={
                    "total_ecos": total_with_outcomes,
                    "failed_count": failed_count,
                    "suspicious_count": suspicious_count,
                },
            )

        # ECOs not exhausted
        return DoomClassification(
            is_doomed=False,
            doom_type=None,
            trigger="ecos_available",
            reason=f"ECO inventory not exhausted: {successful_count} successful, "
            f"{uncertain_count} uncertain, {suspicious_count} suspicious, "
            f"{failed_count} failed",
            confidence=1.0,
            metadata={
                "successful": successful_count,
                "uncertain": uncertain_count,
                "suspicious": suspicious_count,
                "failed": failed_count,
            },
        )


def format_doom_report(doom: DoomClassification) -> str:
    """
    Format doom classification as a human-readable report.

    Args:
        doom: DoomClassification to format

    Returns:
        Formatted report string
    """
    if not doom.is_doomed:
        return f"✓ Case is viable\n  {doom.reason}"

    report_lines = [
        "⚠ DOOM DETECTED - Case Termination Recommended",
        f"  Type: {doom.doom_type.value if doom.doom_type else 'unknown'}",
        f"  Confidence: {doom.confidence:.0%}",
        f"  Trigger: {doom.trigger}",
        "",
        "Reason:",
        f"  {doom.reason}",
    ]

    if doom.metadata:
        report_lines.append("")
        report_lines.append("Details:")
        for key, value in doom.metadata.items():
            if isinstance(value, float):
                report_lines.append(f"  {key}: {value:.2f}")
            elif isinstance(value, list) and len(value) <= 5:
                report_lines.append(f"  {key}: {value}")
            elif isinstance(value, list):
                report_lines.append(f"  {key}: [{len(value)} items]")
            else:
                report_lines.append(f"  {key}: {value}")

    return "\n".join(report_lines)
