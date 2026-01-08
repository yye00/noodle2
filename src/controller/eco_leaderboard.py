"""ECO effectiveness leaderboard generation for Noodle 2.

Aggregates ECO effectiveness across all trials in a Study and generates
ranked leaderboards showing which ECOs are most effective at improving
design metrics.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .eco import ECOEffectiveness


@dataclass
class ECOLeaderboardEntry:
    """Single entry in the ECO effectiveness leaderboard."""

    rank: int
    eco_name: str
    eco_class: str | None
    total_applications: int
    successful_applications: int
    success_rate: float
    average_wns_improvement_ps: float
    best_wns_improvement_ps: float
    worst_wns_degradation_ps: float
    prior: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "rank": self.rank,
            "eco_name": self.eco_name,
            "eco_class": self.eco_class,
            "total_applications": self.total_applications,
            "successful_applications": self.successful_applications,
            "success_rate": self.success_rate,
            "average_wns_improvement_ps": self.average_wns_improvement_ps,
            "best_wns_improvement_ps": self.best_wns_improvement_ps,
            "worst_wns_degradation_ps": self.worst_wns_degradation_ps,
            "prior": self.prior,
        }


@dataclass
class ECOLeaderboard:
    """ECO effectiveness leaderboard."""

    study_name: str
    entries: list[ECOLeaderboardEntry] = field(default_factory=list)
    total_ecos: int = 0
    total_applications: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "study_name": self.study_name,
            "total_ecos": self.total_ecos,
            "total_applications": self.total_applications,
            "entries": [entry.to_dict() for entry in self.entries],
            "metadata": self.metadata,
        }

    def to_text(self) -> str:
        """Generate human-readable text representation."""
        lines: list[str] = []

        # Header
        lines.append("=" * 100)
        lines.append(f"ECO EFFECTIVENESS LEADERBOARD: {self.study_name}")
        lines.append("=" * 100)
        lines.append("")

        # Summary
        lines.append(f"Total ECO Types:        {self.total_ecos}")
        lines.append(f"Total Applications:     {self.total_applications}")
        lines.append("")

        if not self.entries:
            lines.append("No ECO data available.")
            lines.append("")
            lines.append("=" * 100)
            return "\n".join(lines)

        # Table header
        lines.append(
            f"{'Rank':<6} {'ECO Name':<30} {'Apps':<6} {'Succ':<6} {'Rate':<7} "
            f"{'Avg Δ WNS':<12} {'Best Δ':<12} {'Worst Δ':<12} {'Prior':<12}"
        )
        lines.append("-" * 100)

        # Table rows
        for entry in self.entries:
            # Format success rate as percentage
            rate_str = f"{entry.success_rate * 100:.1f}%"

            # Format WNS improvements with sign indicators
            avg_str = _format_wns_delta(entry.average_wns_improvement_ps)
            best_str = _format_wns_delta(entry.best_wns_improvement_ps)
            worst_str = _format_wns_delta(entry.worst_wns_degradation_ps)

            lines.append(
                f"{entry.rank:<6} {entry.eco_name[:29]:<30} "
                f"{entry.total_applications:<6} {entry.successful_applications:<6} "
                f"{rate_str:<7} {avg_str:<12} {best_str:<12} {worst_str:<12} "
                f"{entry.prior:<12}"
            )

        lines.append("")
        lines.append("=" * 100)
        lines.append("")
        lines.append("LEGEND:")
        lines.append("  Rank:      Effectiveness ranking (lower is better)")
        lines.append("  Apps:      Total applications across all trials")
        lines.append("  Succ:      Successful applications")
        lines.append("  Rate:      Success rate (successful / total)")
        lines.append("  Avg Δ WNS: Average WNS improvement in picoseconds (higher is better)")
        lines.append("  Best Δ:    Best single WNS improvement achieved")
        lines.append("  Worst Δ:   Worst WNS degradation observed")
        lines.append("  Prior:     Confidence level (trusted, mixed, suspicious, unknown)")
        lines.append("")

        return "\n".join(lines)


def _format_wns_delta(delta_ps: float) -> str:
    """Format WNS delta with sign indicator."""
    if delta_ps > 0:
        return f"+{delta_ps:.1f} ps"
    elif delta_ps < 0:
        return f"{delta_ps:.1f} ps"
    else:
        return "0.0 ps"


class ECOLeaderboardGenerator:
    """
    Generates ECO effectiveness leaderboards from Study trial data.

    Aggregates ECO effectiveness metrics across all trials and ranks
    ECOs by their average WNS improvement.
    """

    def __init__(self) -> None:
        """Initialize ECO leaderboard generator."""
        pass

    def generate_leaderboard(
        self,
        study_name: str,
        eco_effectiveness_map: dict[str, ECOEffectiveness],
        eco_class_map: dict[str, str] | None = None,
    ) -> ECOLeaderboard:
        """
        Generate ECO effectiveness leaderboard.

        Args:
            study_name: Name of the Study
            eco_effectiveness_map: Map of ECO name to effectiveness tracking
            eco_class_map: Optional map of ECO name to ECO class

        Returns:
            ECOLeaderboard with ranked entries
        """
        eco_class_map = eco_class_map or {}

        # Convert effectiveness map to entries
        entries: list[ECOLeaderboardEntry] = []

        for eco_name, effectiveness in eco_effectiveness_map.items():
            if effectiveness.total_applications == 0:
                # Skip ECOs that were never applied
                continue

            success_rate = (
                effectiveness.successful_applications / effectiveness.total_applications
                if effectiveness.total_applications > 0
                else 0.0
            )

            entry = ECOLeaderboardEntry(
                rank=0,  # Will be assigned after sorting
                eco_name=eco_name,
                eco_class=eco_class_map.get(eco_name),
                total_applications=effectiveness.total_applications,
                successful_applications=effectiveness.successful_applications,
                success_rate=success_rate,
                average_wns_improvement_ps=effectiveness.average_wns_improvement_ps,
                best_wns_improvement_ps=effectiveness.best_wns_improvement_ps,
                worst_wns_degradation_ps=effectiveness.worst_wns_degradation_ps,
                prior=effectiveness.prior.value,
            )
            entries.append(entry)

        # Sort by average WNS improvement (descending - higher is better)
        entries.sort(key=lambda e: e.average_wns_improvement_ps, reverse=True)

        # Assign ranks
        for i, entry in enumerate(entries, start=1):
            entry.rank = i

        # Calculate totals
        total_ecos = len(entries)
        total_applications = sum(e.total_applications for e in entries)

        return ECOLeaderboard(
            study_name=study_name,
            entries=entries,
            total_ecos=total_ecos,
            total_applications=total_applications,
        )

    def save_leaderboard(
        self, leaderboard: ECOLeaderboard, artifacts_dir: Path
    ) -> tuple[Path, Path]:
        """
        Save leaderboard to JSON and text files.

        Args:
            leaderboard: ECO leaderboard to save
            artifacts_dir: Directory to save artifacts

        Returns:
            Tuple of (json_path, text_path)
        """
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Save JSON
        json_path = artifacts_dir / "eco_leaderboard.json"
        import json

        with json_path.open("w") as f:
            json.dump(leaderboard.to_dict(), f, indent=2)

        # Save text
        text_path = artifacts_dir / "eco_leaderboard.txt"
        with text_path.open("w") as f:
            f.write(leaderboard.to_text())

        return json_path, text_path
