"""
Progress report generation for feature tracking.

This module provides functionality to generate human-readable progress reports
showing feature implementation status.
"""

from dataclasses import dataclass
from typing import TextIO
import sys

from .feature_loader import FeatureDefinition


@dataclass
class ProgressReport:
    """
    Progress report showing feature implementation status.

    Attributes:
        total_features: Total number of features
        passing_features: Number of features passing tests
        failing_features: Number of features failing tests
        completion_percentage: Percentage of features passing (0-100)
        functional_passing: Number of functional features passing
        functional_total: Total number of functional features
        style_passing: Number of style features passing
        style_total: Total number of style features
    """

    total_features: int
    passing_features: int
    failing_features: int
    completion_percentage: float
    functional_passing: int
    functional_total: int
    style_passing: int
    style_total: int

    @property
    def functional_percentage(self) -> float:
        """Percentage of functional features passing."""
        if self.functional_total == 0:
            return 0.0
        return (self.functional_passing / self.functional_total) * 100

    @property
    def style_percentage(self) -> float:
        """Percentage of style features passing."""
        if self.style_total == 0:
            return 0.0
        return (self.style_passing / self.style_total) * 100

    def format_report(self, detailed: bool = False) -> str:
        """
        Format progress report as human-readable string.

        Args:
            detailed: If True, include detailed breakdown by category

        Returns:
            Formatted report string
        """
        lines = []
        lines.append("=" * 70)
        lines.append("Noodle 2 - Feature Implementation Progress Report")
        lines.append("=" * 70)
        lines.append("")

        # Overall progress
        lines.append(f"Overall Progress: {self.passing_features}/{self.total_features} features")
        lines.append(f"Completion: {self.completion_percentage:.1f}%")
        lines.append("")

        # Progress bar
        bar_width = 50
        filled = int(bar_width * self.completion_percentage / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        lines.append(f"[{bar}] {self.completion_percentage:.1f}%")
        lines.append("")

        if detailed:
            # Breakdown by category
            lines.append("Breakdown by Category:")
            lines.append("-" * 70)
            lines.append("")

            # Functional features
            lines.append(f"Functional Features: {self.functional_passing}/{self.functional_total}")
            lines.append(f"  Completion: {self.functional_percentage:.1f}%")
            func_filled = int(bar_width * self.functional_percentage / 100)
            func_bar = "█" * func_filled + "░" * (bar_width - func_filled)
            lines.append(f"  [{func_bar}]")
            lines.append("")

            # Style features
            lines.append(f"Style Features: {self.style_passing}/{self.style_total}")
            lines.append(f"  Completion: {self.style_percentage:.1f}%")
            style_filled = int(bar_width * self.style_percentage / 100)
            style_bar = "█" * style_filled + "░" * (bar_width - style_filled)
            lines.append(f"  [{style_bar}]")
            lines.append("")

        lines.append("=" * 70)

        return "\n".join(lines)

    def print_report(self, detailed: bool = False, file: TextIO | None = None) -> None:
        """
        Print progress report to file or stdout.

        Args:
            detailed: If True, include detailed breakdown by category
            file: Output file (defaults to sys.stdout)
        """
        if file is None:
            file = sys.stdout
        print(self.format_report(detailed=detailed), file=file)

    def to_dict(self) -> dict[str, int | float]:
        """Convert to dictionary format for JSON serialization."""
        return {
            "total_features": self.total_features,
            "passing_features": self.passing_features,
            "failing_features": self.failing_features,
            "completion_percentage": self.completion_percentage,
            "functional_passing": self.functional_passing,
            "functional_total": self.functional_total,
            "functional_percentage": self.functional_percentage,
            "style_passing": self.style_passing,
            "style_total": self.style_total,
            "style_percentage": self.style_percentage,
        }


def generate_progress_report(features: list[FeatureDefinition]) -> ProgressReport:
    """
    Generate progress report from feature list.

    Args:
        features: List of FeatureDefinition objects

    Returns:
        ProgressReport object with completion statistics
    """
    total_features = len(features)
    passing_features = sum(1 for f in features if f.passes)
    failing_features = total_features - passing_features

    functional_features = [f for f in features if f.category == "functional"]
    functional_total = len(functional_features)
    functional_passing = sum(1 for f in functional_features if f.passes)

    style_features = [f for f in features if f.category == "style"]
    style_total = len(style_features)
    style_passing = sum(1 for f in style_features if f.passes)

    completion_percentage = (passing_features / total_features * 100) if total_features > 0 else 0.0

    return ProgressReport(
        total_features=total_features,
        passing_features=passing_features,
        failing_features=failing_features,
        completion_percentage=completion_percentage,
        functional_passing=functional_passing,
        functional_total=functional_total,
        style_passing=style_passing,
        style_total=style_total,
    )
