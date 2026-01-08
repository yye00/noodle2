"""Pareto frontier visualization for multi-objective optimization.

This module provides functions to generate publication-quality plots showing
the Pareto frontier and dominated trials across two objectives.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure

from src.controller.pareto import ObjectiveSpec, ParetoFrontier, ParetoTrial


def plot_pareto_frontier_2d(
    pareto_frontier: ParetoFrontier,
    objective_x: str,
    objective_y: str,
    title: str | None = None,
    figsize: tuple[float, float] = (10, 8),
    dpi: int = 150,
) -> Figure:
    """
    Generate 2D Pareto frontier plot for two objectives.

    Args:
        pareto_frontier: Computed Pareto frontier
        objective_x: Name of objective for x-axis
        objective_y: Name of objective for y-axis
        title: Plot title (auto-generated if None)
        figsize: Figure size in inches (width, height)
        dpi: Resolution in dots per inch

    Returns:
        matplotlib Figure object

    Raises:
        ValueError: If objectives not found or if fewer than 2 trials
    """
    # Validate objectives exist
    obj_names = {obj.name for obj in pareto_frontier.objectives}
    if objective_x not in obj_names:
        raise ValueError(f"Objective '{objective_x}' not found in frontier")
    if objective_y not in obj_names:
        raise ValueError(f"Objective '{objective_y}' not found in frontier")

    if len(pareto_frontier.all_trials) < 2:
        raise ValueError("Need at least 2 trials to generate Pareto plot")

    # Get objective specs for axis labels
    obj_x_spec = next(obj for obj in pareto_frontier.objectives if obj.name == objective_x)
    obj_y_spec = next(obj for obj in pareto_frontier.objectives if obj.name == objective_y)

    # Extract data points
    pareto_x = []
    pareto_y = []
    pareto_labels = []
    for trial in pareto_frontier.pareto_optimal_trials:
        pareto_x.append(trial.objective_values[objective_x])
        pareto_y.append(trial.objective_values[objective_y])
        pareto_labels.append(trial.case_name)

    dominated_x = []
    dominated_y = []
    dominated_labels = []
    for trial in pareto_frontier.dominated_trials:
        dominated_x.append(trial.objective_values[objective_x])
        dominated_y.append(trial.objective_values[objective_y])
        dominated_labels.append(trial.case_name)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Plot dominated trials (smaller, gray)
    if dominated_x:
        ax.scatter(
            dominated_x,
            dominated_y,
            s=80,
            c="gray",
            alpha=0.5,
            marker="o",
            label="Dominated",
            zorder=2,
        )

    # Plot Pareto-optimal trials (larger, highlighted)
    if pareto_x:
        ax.scatter(
            pareto_x,
            pareto_y,
            s=150,
            c="red",
            alpha=0.8,
            marker="*",
            edgecolors="darkred",
            linewidths=1.5,
            label="Pareto-Optimal",
            zorder=3,
        )

        # Connect Pareto points with a line (if 2D)
        if len(pareto_x) >= 2:
            # Sort points for proper line drawing
            pareto_points = sorted(zip(pareto_x, pareto_y))
            sorted_x, sorted_y = zip(*pareto_points)
            ax.plot(
                sorted_x,
                sorted_y,
                "r--",
                alpha=0.4,
                linewidth=1.5,
                label="Pareto Frontier",
                zorder=1,
            )

    # Add axis labels with units
    x_label = _format_axis_label(objective_x, obj_x_spec)
    y_label = _format_axis_label(objective_y, obj_y_spec)
    ax.set_xlabel(x_label, fontsize=12, fontweight="bold")
    ax.set_ylabel(y_label, fontsize=12, fontweight="bold")

    # Set title
    if title is None:
        title = f"Pareto Frontier: {objective_x} vs {objective_y}"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    # Add grid
    ax.grid(True, alpha=0.3, linestyle="--", linewidth=0.5)

    # Add legend
    legend = ax.legend(loc="best", fontsize=10, framealpha=0.9)
    legend.set_zorder(10)

    # Add summary statistics text box
    summary_text = _generate_summary_text(pareto_frontier)
    ax.text(
        0.02,
        0.98,
        summary_text,
        transform=ax.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.3),
        family="monospace",
    )

    # Tight layout to prevent label cutoff
    fig.tight_layout()

    return fig


def _format_axis_label(objective_name: str, obj_spec: ObjectiveSpec) -> str:
    """
    Format axis label with objective name and optimization direction.

    Args:
        objective_name: Name of the objective
        obj_spec: Objective specification

    Returns:
        Formatted axis label string
    """
    # Infer units from objective name
    units = _infer_units(objective_name)

    # Add optimization direction indicator
    direction = "↓" if obj_spec.minimize else "↑"

    if units:
        return f"{objective_name} ({units}) {direction}"
    else:
        return f"{objective_name} {direction}"


def _infer_units(objective_name: str) -> str:
    """
    Infer units from objective name.

    Args:
        objective_name: Name of the objective

    Returns:
        Unit string or empty string if unknown
    """
    units_map = {
        "wns_ps": "ps",
        "tns_ps": "ps",
        "slack_ps": "ps",
        "hot_ratio": "ratio",
        "area_um2": "µm²",
        "total_area_um2": "µm²",
        "total_power_mw": "mW",
        "power_mw": "mW",
        "wirelength_um": "µm",
        "cpu_time_seconds": "s",
        "peak_memory_mb": "MB",
    }

    # Try exact match first
    if objective_name in units_map:
        return units_map[objective_name]

    # Try partial matches
    for key, unit in units_map.items():
        if key in objective_name.lower():
            return unit

    return ""


def _generate_summary_text(pareto_frontier: ParetoFrontier) -> str:
    """
    Generate summary statistics text for plot.

    Args:
        pareto_frontier: Pareto frontier data

    Returns:
        Formatted summary text
    """
    total = len(pareto_frontier.all_trials)
    pareto_count = len(pareto_frontier.pareto_optimal_trials)
    dominated_count = len(pareto_frontier.dominated_trials)
    pareto_pct = (pareto_count / total * 100) if total > 0 else 0

    return (
        f"Total Trials: {total}\n"
        f"Pareto-Optimal: {pareto_count} ({pareto_pct:.1f}%)\n"
        f"Dominated: {dominated_count}"
    )


def save_pareto_plot(
    fig: Figure,
    output_path: Path,
    format: str = "png",
    bbox_inches: str = "tight",
    pad_inches: float = 0.1,
) -> None:
    """
    Save Pareto frontier plot to file.

    Args:
        fig: matplotlib Figure to save
        output_path: Path to output file
        format: Image format (png, pdf, svg, etc.)
        bbox_inches: Bounding box setting (tight recommended)
        pad_inches: Padding around figure
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(
        output_path,
        format=format,
        bbox_inches=bbox_inches,
        pad_inches=pad_inches,
        dpi=fig.dpi,
    )


def plot_pareto_frontier_from_file(
    pareto_json_path: Path,
    objective_x: str,
    objective_y: str,
    output_path: Path | None = None,
    **plot_kwargs: Any,
) -> Figure:
    """
    Convenience function to plot Pareto frontier from JSON file.

    Args:
        pareto_json_path: Path to Pareto frontier JSON file
        objective_x: Name of objective for x-axis
        objective_y: Name of objective for y-axis
        output_path: Optional path to save plot (if None, plot not saved)
        **plot_kwargs: Additional arguments passed to plot_pareto_frontier_2d

    Returns:
        matplotlib Figure object
    """
    import json

    from src.controller.pareto import compute_pareto_frontier
    from src.trial_runner.trial import TrialResult

    # Load Pareto data
    with open(pareto_json_path) as f:
        data = json.load(f)

    # Reconstruct ParetoFrontier from dict
    # This is a simplified loader - in practice, may need full deserialization
    objectives = [
        ObjectiveSpec(
            name=obj["name"],
            metric_path=obj["metric_path"],
            minimize=obj["minimize"],
            weight=obj.get("weight", 1.0),
        )
        for obj in data["objectives"]
    ]

    # Note: This function expects the full ParetoFrontier object
    # For now, we'll require passing the ParetoFrontier object directly
    raise NotImplementedError(
        "Loading from JSON not yet implemented. "
        "Pass ParetoFrontier object directly to plot_pareto_frontier_2d()"
    )


def generate_pareto_visualization(
    pareto_frontier: ParetoFrontier,
    output_dir: Path,
    objective_pairs: list[tuple[str, str]] | None = None,
) -> list[Path]:
    """
    Generate all Pareto frontier visualizations for a Study.

    Args:
        pareto_frontier: Computed Pareto frontier
        output_dir: Directory to save plots
        objective_pairs: List of (x, y) objective pairs to plot
                        If None, plots all 2-objective combinations

    Returns:
        List of paths to generated plot files
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # If no pairs specified, generate all 2-objective combinations
    if objective_pairs is None:
        obj_names = [obj.name for obj in pareto_frontier.objectives]
        if len(obj_names) < 2:
            raise ValueError("Need at least 2 objectives for visualization")

        objective_pairs = []
        for i, obj_x in enumerate(obj_names):
            for obj_y in obj_names[i + 1 :]:
                objective_pairs.append((obj_x, obj_y))

    generated_plots = []
    for obj_x, obj_y in objective_pairs:
        # Generate plot
        fig = plot_pareto_frontier_2d(pareto_frontier, obj_x, obj_y)

        # Save plot
        plot_filename = f"pareto_{obj_x}_vs_{obj_y}.png"
        plot_path = output_dir / plot_filename
        save_pareto_plot(fig, plot_path)
        generated_plots.append(plot_path)

        # Close figure to free memory
        plt.close(fig)

    return generated_plots
