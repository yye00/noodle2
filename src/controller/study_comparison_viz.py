"""Visualization generation for study comparisons.

This module provides visualization functions for comparing two studies:
- Pareto frontier comparison
- Trajectory comparison (improvement curves over time)
- ECO effectiveness comparison
"""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from .study_comparison import StudyComparisonReport


def generate_pareto_comparison(
    report: StudyComparisonReport,
    output_path: Path,
) -> None:
    """
    Generate Pareto frontier comparison chart.

    Args:
        report: Study comparison report
        output_path: Path to save the chart

    Note:
        For now, this creates a placeholder chart.
        Full Pareto frontier visualization requires case-level data.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Extract final metrics for both studies
    study1 = report.study1_summary
    study2 = report.study2_summary

    # Plot both studies as single points (best case from each)
    if study1.final_wns_ps is not None and study1.final_hot_ratio is not None:
        ax.scatter(
            [study1.final_wns_ps],
            [study1.final_hot_ratio],
            s=100,
            alpha=0.7,
            label=f"{study1.study_name} (best)",
            marker="o",
        )

    if study2.final_wns_ps is not None and study2.final_hot_ratio is not None:
        ax.scatter(
            [study2.final_wns_ps],
            [study2.final_hot_ratio],
            s=100,
            alpha=0.7,
            label=f"{study2.study_name} (best)",
            marker="s",
        )

    ax.set_xlabel("WNS (ps)")
    ax.set_ylabel("Hot Ratio")
    ax.set_title(f"Pareto Comparison: {study1.study_name} vs {study2.study_name}")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Save figure
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def generate_trajectory_comparison(
    report: StudyComparisonReport,
    output_path: Path,
) -> None:
    """
    Generate trajectory comparison chart showing improvement curves.

    Args:
        report: Study comparison report
        output_path: Path to save the chart

    Note:
        For now, this creates a placeholder chart showing final metrics.
        Full trajectory visualization requires stage-by-stage data.
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Extract metrics
    study1 = report.study1_summary
    study2 = report.study2_summary

    # WNS trajectory (placeholder - showing final values only)
    if study1.final_wns_ps is not None and study2.final_wns_ps is not None:
        ax1.bar(
            [study1.study_name, study2.study_name],
            [study1.final_wns_ps, study2.final_wns_ps],
            alpha=0.7,
        )
        ax1.set_ylabel("WNS (ps)")
        ax1.set_title("WNS Comparison")
        ax1.grid(True, alpha=0.3, axis="y")

    # Hot ratio trajectory (placeholder - showing final values only)
    if study1.final_hot_ratio is not None and study2.final_hot_ratio is not None:
        ax2.bar(
            [study1.study_name, study2.study_name],
            [study1.final_hot_ratio, study2.final_hot_ratio],
            alpha=0.7,
            color=["orange", "green"],
        )
        ax2.set_ylabel("Hot Ratio")
        ax2.set_title("Hot Ratio Comparison")
        ax2.grid(True, alpha=0.3, axis="y")

    plt.suptitle(f"Trajectory Comparison: {study1.study_name} vs {study2.study_name}")
    plt.tight_layout()

    # Save figure
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def generate_eco_effectiveness_comparison(
    report: StudyComparisonReport,
    output_path: Path,
) -> None:
    """
    Generate ECO effectiveness comparison chart.

    Args:
        report: Study comparison report
        output_path: Path to save the chart
    """
    if not report.eco_effectiveness_comparisons:
        # No ECO data available, create empty placeholder
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.text(
            0.5,
            0.5,
            "No ECO effectiveness data available",
            ha="center",
            va="center",
            fontsize=14,
        )
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        return

    # Extract ECO names and success rates
    eco_names = []
    study1_rates = []
    study2_rates = []

    for eco_comp in report.eco_effectiveness_comparisons:
        eco_names.append(eco_comp.eco_name)
        study1_rates.append(
            eco_comp.study1_success_rate * 100 if eco_comp.study1_success_rate is not None else 0
        )
        study2_rates.append(
            eco_comp.study2_success_rate * 100 if eco_comp.study2_success_rate is not None else 0
        )

    # Create grouped bar chart
    fig, ax = plt.subplots(figsize=(12, 6))

    x = range(len(eco_names))
    width = 0.35

    bars1 = ax.bar(
        [i - width / 2 for i in x],
        study1_rates,
        width,
        label=report.study1_name,
        alpha=0.8,
    )
    bars2 = ax.bar(
        [i + width / 2 for i in x],
        study2_rates,
        width,
        label=report.study2_name,
        alpha=0.8,
    )

    # Add value labels on bars
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height,
                f"{height:.1f}%",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    ax.set_xlabel("ECO Name")
    ax.set_ylabel("Success Rate (%)")
    ax.set_title(
        f"ECO Effectiveness Comparison: {report.study1_name} vs {report.study2_name}"
    )
    ax.set_xticks(x)
    ax.set_xticklabels(eco_names, rotation=45, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")
    ax.set_ylim(0, 105)  # 0-100% with some headroom for labels

    plt.tight_layout()

    # Save figure
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def generate_all_comparison_visualizations(
    report: StudyComparisonReport,
    output_dir: Path,
) -> dict[str, Path]:
    """
    Generate all comparison visualization charts.

    Args:
        report: Study comparison report
        output_dir: Directory to save all charts

    Returns:
        Dictionary mapping chart type to output path
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    charts: dict[str, Path] = {}

    # Generate Pareto comparison
    pareto_path = output_dir / "pareto_comparison.png"
    generate_pareto_comparison(report, pareto_path)
    charts["pareto"] = pareto_path

    # Generate trajectory comparison
    trajectory_path = output_dir / "trajectory_comparison.png"
    generate_trajectory_comparison(report, trajectory_path)
    charts["trajectory"] = trajectory_path

    # Generate ECO effectiveness comparison
    eco_path = output_dir / "eco_effectiveness_comparison.png"
    generate_eco_effectiveness_comparison(report, eco_path)
    charts["eco_effectiveness"] = eco_path

    return charts
