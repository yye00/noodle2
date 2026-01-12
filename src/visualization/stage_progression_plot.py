"""Stage progression visualization for multi-stage studies.

This module provides functions to generate flow diagrams showing how trials
progress through stages, with survivor counts, metric deltas, and winner highlighting.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.figure import Figure


def plot_stage_progression(
    stage_data: list[dict[str, Any]],
    winner_stage_index: int | None = None,
    title: str | None = None,
    figsize: tuple[float, float] = (14, 8),
    dpi: int = 150,
) -> Figure:
    """
    Generate stage progression visualization showing trial flow through stages.

    Args:
        stage_data: List of stage dictionaries with:
            - stage_index: int
            - stage_name: str
            - trial_count: int (number of trials executed)
            - survivor_count: int (number of survivors to next stage)
            - wns_delta_ps: float (WNS improvement from previous stage, optional)
            - hot_ratio_delta: float (hot_ratio reduction from previous stage, optional)
        winner_stage_index: Index of final stage containing winner (for highlighting)
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
        if "trial_count" not in stage:
            raise ValueError(f"Stage {i} missing 'trial_count'")
        if "survivor_count" not in stage:
            raise ValueError(f"Stage {i} missing 'survivor_count'")

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Calculate layout
    num_stages = len(stage_data)
    stage_width = 0.8 / num_stages  # Leave margins
    stage_height = 0.3
    y_center = 0.5

    # Colors
    stage_color = "#4A90E2"  # Blue
    winner_color = "#50C878"  # Green
    arrow_color = "#333333"  # Dark gray
    delta_positive_color = "#50C878"  # Green (improvement)
    delta_negative_color = "#E74C3C"  # Red (degradation)

    for i, stage in enumerate(stage_data):
        # Calculate position
        x_pos = 0.1 + i * (0.8 / num_stages)

        # Determine if this is the winner stage
        is_winner = winner_stage_index is not None and i == winner_stage_index

        # Draw stage box
        box_color = winner_color if is_winner else stage_color
        box = mpatches.FancyBboxPatch(
            (x_pos, y_center - stage_height / 2),
            stage_width * 0.8,
            stage_height,
            boxstyle="round,pad=0.01",
            facecolor=box_color,
            edgecolor="black",
            linewidth=2 if is_winner else 1,
            alpha=0.8,
        )
        ax.add_patch(box)

        # Add stage name
        ax.text(
            x_pos + stage_width * 0.4,
            y_center + stage_height / 2 + 0.05,
            stage["stage_name"],
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )

        # Add trial count
        ax.text(
            x_pos + stage_width * 0.4,
            y_center + 0.05,
            f"Trials: {stage['trial_count']}",
            ha="center",
            va="center",
            fontsize=9,
        )

        # Add survivor count
        ax.text(
            x_pos + stage_width * 0.4,
            y_center - 0.05,
            f"Survivors: {stage['survivor_count']}",
            ha="center",
            va="center",
            fontsize=9,
        )

        # Add winner label if this is the winner stage
        if is_winner:
            ax.text(
                x_pos + stage_width * 0.4,
                y_center - stage_height / 2 - 0.08,
                "★ WINNER ★",
                ha="center",
                va="top",
                fontsize=10,
                fontweight="bold",
                color=winner_color,
            )

        # Draw arrow to next stage
        if i < num_stages - 1:
            arrow_x_start = x_pos + stage_width * 0.8
            arrow_x_end = x_pos + 0.8 / num_stages
            arrow_y = y_center

            ax.annotate(
                "",
                xy=(arrow_x_end, arrow_y),
                xytext=(arrow_x_start, arrow_y),
                arrowprops=dict(
                    arrowstyle="->",
                    lw=2,
                    color=arrow_color,
                ),
            )

            # Add delta metrics above arrow
            delta_y = y_center + stage_height / 2 + 0.15
            delta_x = (arrow_x_start + arrow_x_end) / 2

            # WNS delta
            if "wns_delta_ps" in stage_data[i + 1]:
                wns_delta = stage_data[i + 1]["wns_delta_ps"]
                wns_color = delta_positive_color if wns_delta > 0 else delta_negative_color
                wns_sign = "+" if wns_delta > 0 else ""
                ax.text(
                    delta_x,
                    delta_y,
                    f"ΔWNS: {wns_sign}{wns_delta:.0f}ps",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=wns_color,
                    fontweight="bold",
                )

            # hot_ratio delta
            if "hot_ratio_delta" in stage_data[i + 1]:
                hot_ratio_delta = stage_data[i + 1]["hot_ratio_delta"]
                # For hot_ratio, negative is good (reduction)
                hr_color = delta_positive_color if hot_ratio_delta < 0 else delta_negative_color
                hr_sign = "" if hot_ratio_delta < 0 else "+"
                ax.text(
                    delta_x,
                    delta_y - 0.05,
                    f"ΔHot: {hr_sign}{hot_ratio_delta:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                    color=hr_color,
                    fontweight="bold",
                )

    # Set axis properties
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Add title
    if title is None:
        title = "Stage Progression Summary"
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.95)

    # Add legend
    legend_elements = [
        mpatches.Patch(facecolor=stage_color, edgecolor="black", label="Stage"),
        mpatches.Patch(
            facecolor=winner_color, edgecolor="black", linewidth=2, label="Winner Stage"
        ),
        mpatches.Patch(facecolor=delta_positive_color, label="Improvement"),
        mpatches.Patch(facecolor=delta_negative_color, label="Degradation"),
    ]
    ax.legend(
        handles=legend_elements,
        loc="upper right",
        frameon=True,
        shadow=True,
        fontsize=9,
    )

    plt.tight_layout()

    return fig


def save_stage_progression_plot(
    fig: Figure,
    output_path: Path | str,
) -> None:
    """
    Save stage progression plot to file.

    Args:
        fig: matplotlib Figure object
        output_path: Path to save the plot (PNG format)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def generate_stage_progression_visualization(
    stage_data: list[dict[str, Any]],
    output_dir: Path | str,
    winner_stage_index: int | None = None,
    filename: str = "stage_progression.png",
) -> Path:
    """
    Generate and save stage progression visualization.

    High-level convenience function for F234.

    Args:
        stage_data: List of stage dictionaries with trial/survivor counts and deltas
        output_dir: Directory to save the visualization
        winner_stage_index: Index of final stage containing winner (optional)
        filename: Output filename (default: stage_progression.png)

    Returns:
        Path to saved visualization

    Raises:
        ValueError: If stage_data is invalid
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    fig = plot_stage_progression(stage_data, winner_stage_index=winner_stage_index)
    save_stage_progression_plot(fig, output_path)

    return output_path
