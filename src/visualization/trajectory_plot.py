"""Trajectory visualization for metric improvement across stages.

This module provides functions to generate charts showing how metrics like WNS
and hot_ratio improve across multi-stage studies, with best/median/worst bands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure


def plot_wns_trajectory(
    stage_data: list[dict[str, Any]],
    title: str | None = None,
    figsize: tuple[float, float] = (12, 8),
    dpi: int = 150,
) -> Figure:
    """
    Generate WNS improvement trajectory chart across stages.

    Args:
        stage_data: List of stage dictionaries with 'stage_index', 'stage_name',
                   and 'wns_values' (list of WNS values in picoseconds)
        title: Plot title (auto-generated if None)
        figsize: Figure size in inches (width, height)
        dpi: Resolution in dots per inch

    Returns:
        matplotlib Figure object

    Raises:
        ValueError: If stage_data is empty or missing required fields
    """
    if not stage_data:
        raise ValueError("stage_data cannot be empty")

    # Validate data structure
    for i, stage in enumerate(stage_data):
        if "stage_index" not in stage:
            raise ValueError(f"Stage {i} missing 'stage_index'")
        if "stage_name" not in stage:
            raise ValueError(f"Stage {i} missing 'stage_name'")
        if "wns_values" not in stage:
            raise ValueError(f"Stage {i} missing 'wns_values'")
        if not stage["wns_values"]:
            raise ValueError(f"Stage {i} has empty 'wns_values'")

    # Extract stage information
    stages = [s["stage_index"] for s in stage_data]
    stage_names = [s["stage_name"] for s in stage_data]

    # Calculate statistics per stage
    best_wns = []
    median_wns = []
    worst_wns = []

    for stage in stage_data:
        wns_vals = np.array(stage["wns_values"])
        best_wns.append(np.max(wns_vals))  # Best = highest (least negative)
        median_wns.append(np.median(wns_vals))
        worst_wns.append(np.min(wns_vals))  # Worst = lowest (most negative)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Plot best/median/worst bands
    ax.fill_between(
        stages,
        worst_wns,
        best_wns,
        alpha=0.2,
        color="blue",
        label="Best-Worst Range",
    )

    # Plot median line (primary trend)
    ax.plot(
        stages,
        median_wns,
        marker="o",
        linewidth=2.5,
        markersize=8,
        color="blue",
        label="Median WNS",
        zorder=3,
    )

    # Plot best line (upper bound)
    ax.plot(
        stages,
        best_wns,
        marker="^",
        linewidth=1.5,
        markersize=6,
        color="green",
        linestyle="--",
        label="Best WNS",
        alpha=0.7,
        zorder=2,
    )

    # Plot worst line (lower bound)
    ax.plot(
        stages,
        worst_wns,
        marker="v",
        linewidth=1.5,
        markersize=6,
        color="red",
        linestyle="--",
        label="Worst WNS",
        alpha=0.7,
        zorder=2,
    )

    # Add trend line for median
    if len(stages) >= 2:
        # Linear regression for trend
        z = np.polyfit(stages, median_wns, 1)
        p = np.poly1d(z)
        ax.plot(
            stages,
            p(stages),
            linestyle=":",
            linewidth=2,
            color="orange",
            label="Trend",
            alpha=0.8,
            zorder=1,
        )

    # Styling
    ax.set_xlabel("Stage", fontsize=12, fontweight="bold")
    ax.set_ylabel("WNS (ps)", fontsize=12, fontweight="bold")

    if title is None:
        title = "WNS Improvement Trajectory Across Stages"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    # Set x-axis to show stage names
    ax.set_xticks(stages)
    ax.set_xticklabels(stage_names, rotation=45, ha="right")

    # Add grid for readability
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    # Add legend
    ax.legend(loc="best", frameon=True, shadow=True)

    # Add zero line if WNS crosses zero
    y_min, y_max = ax.get_ylim()
    if y_min < 0 < y_max:
        ax.axhline(y=0, color="black", linestyle="-", linewidth=1, alpha=0.5)
        ax.text(
            stages[-1],
            0,
            " Target",
            verticalalignment="bottom",
            fontsize=10,
            color="black",
        )

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    return fig


def plot_hot_ratio_trajectory(
    stage_data: list[dict[str, Any]],
    title: str | None = None,
    figsize: tuple[float, float] = (12, 8),
    dpi: int = 150,
) -> Figure:
    """
    Generate hot_ratio reduction trajectory chart across stages.

    Args:
        stage_data: List of stage dictionaries with 'stage_index', 'stage_name',
                   and 'hot_ratio_values' (list of hot_ratio values)
        title: Plot title (auto-generated if None)
        figsize: Figure size in inches (width, height)
        dpi: Resolution in dots per inch

    Returns:
        matplotlib Figure object

    Raises:
        ValueError: If stage_data is empty or missing required fields
    """
    if not stage_data:
        raise ValueError("stage_data cannot be empty")

    # Validate data structure
    for i, stage in enumerate(stage_data):
        if "stage_index" not in stage:
            raise ValueError(f"Stage {i} missing 'stage_index'")
        if "stage_name" not in stage:
            raise ValueError(f"Stage {i} missing 'stage_name'")
        if "hot_ratio_values" not in stage:
            raise ValueError(f"Stage {i} missing 'hot_ratio_values'")
        if not stage["hot_ratio_values"]:
            raise ValueError(f"Stage {i} has empty 'hot_ratio_values'")

    # Extract stage information
    stages = [s["stage_index"] for s in stage_data]
    stage_names = [s["stage_name"] for s in stage_data]

    # Calculate statistics per stage
    best_hot_ratio = []
    median_hot_ratio = []
    worst_hot_ratio = []

    for stage in stage_data:
        hot_ratio_vals = np.array(stage["hot_ratio_values"])
        best_hot_ratio.append(np.min(hot_ratio_vals))  # Best = lowest
        median_hot_ratio.append(np.median(hot_ratio_vals))
        worst_hot_ratio.append(np.max(hot_ratio_vals))  # Worst = highest

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Plot best/median/worst bands
    ax.fill_between(
        stages,
        best_hot_ratio,
        worst_hot_ratio,
        alpha=0.2,
        color="orange",
        label="Best-Worst Range",
    )

    # Plot median line (primary trend)
    ax.plot(
        stages,
        median_hot_ratio,
        marker="o",
        linewidth=2.5,
        markersize=8,
        color="orange",
        label="Median Hot Ratio",
        zorder=3,
    )

    # Plot best line (lower bound for hot_ratio)
    ax.plot(
        stages,
        best_hot_ratio,
        marker="v",
        linewidth=1.5,
        markersize=6,
        color="green",
        linestyle="--",
        label="Best Hot Ratio",
        alpha=0.7,
        zorder=2,
    )

    # Plot worst line (upper bound for hot_ratio)
    ax.plot(
        stages,
        worst_hot_ratio,
        marker="^",
        linewidth=1.5,
        markersize=6,
        color="red",
        linestyle="--",
        label="Worst Hot Ratio",
        alpha=0.7,
        zorder=2,
    )

    # Add trend line for median
    if len(stages) >= 2:
        # Linear regression for trend
        z = np.polyfit(stages, median_hot_ratio, 1)
        p = np.poly1d(z)
        ax.plot(
            stages,
            p(stages),
            linestyle=":",
            linewidth=2,
            color="purple",
            label="Trend",
            alpha=0.8,
            zorder=1,
        )

    # Styling
    ax.set_xlabel("Stage", fontsize=12, fontweight="bold")
    ax.set_ylabel("Hot Ratio", fontsize=12, fontweight="bold")

    if title is None:
        title = "Hot Ratio Reduction Trajectory Across Stages"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    # Set x-axis to show stage names
    ax.set_xticks(stages)
    ax.set_xticklabels(stage_names, rotation=45, ha="right")

    # Add grid for readability
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    # Add legend
    ax.legend(loc="best", frameon=True, shadow=True)

    # Add target threshold line at 0.7 if relevant
    y_min, y_max = ax.get_ylim()
    if y_min < 0.7 < y_max:
        ax.axhline(y=0.7, color="red", linestyle="--", linewidth=1.5, alpha=0.6)
        ax.text(
            stages[-1],
            0.7,
            " Critical Threshold (0.7)",
            verticalalignment="bottom",
            fontsize=10,
            color="red",
        )

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    return fig


def save_trajectory_plot(
    fig: Figure,
    output_path: Path | str,
) -> None:
    """
    Save trajectory plot to file.

    Args:
        fig: matplotlib Figure object
        output_path: Path to save the plot (PNG format)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def generate_wns_trajectory_chart(
    stage_data: list[dict[str, Any]],
    output_dir: Path | str,
    filename: str = "improvement_trajectory.png",
) -> Path:
    """
    Generate and save WNS improvement trajectory chart.

    High-level convenience function for F231.

    Args:
        stage_data: List of stage dictionaries with WNS values
        output_dir: Directory to save the chart
        filename: Output filename (default: improvement_trajectory.png)

    Returns:
        Path to saved chart

    Raises:
        ValueError: If stage_data is invalid
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    fig = plot_wns_trajectory(stage_data)
    save_trajectory_plot(fig, output_path)

    return output_path


def generate_hot_ratio_trajectory_chart(
    stage_data: list[dict[str, Any]],
    output_dir: Path | str,
    filename: str = "hot_ratio_trajectory.png",
) -> Path:
    """
    Generate and save hot_ratio reduction trajectory chart.

    High-level convenience function for F232.

    Args:
        stage_data: List of stage dictionaries with hot_ratio values
        output_dir: Directory to save the chart
        filename: Output filename (default: hot_ratio_trajectory.png)

    Returns:
        Path to saved chart

    Raises:
        ValueError: If stage_data is invalid
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    fig = plot_hot_ratio_trajectory(stage_data)
    save_trajectory_plot(fig, output_path)

    return output_path
