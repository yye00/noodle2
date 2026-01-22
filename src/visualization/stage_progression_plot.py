"""Stage progression visualization for multi-stage studies.

This module provides functions to generate flow diagrams showing how trials
progress through stages, with survivor counts, metric deltas, ECO information,
and winner highlighting.

Uses a multi-row GridSpec layout for better readability with many stages (20+).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure


def plot_stage_progression(
    stage_data: list[dict[str, Any]],
    winner_stage_index: int | None = None,
    title: str | None = None,
    figsize: tuple[float, float] | None = None,
    dpi: int = 150,
    stages_per_row: int = 5,
) -> Figure:
    """
    Generate stage progression visualization showing trial flow through stages.

    Uses a multi-row GridSpec layout for better readability with many stages.

    Args:
        stage_data: List of stage dictionaries with:
            - stage_index: int
            - stage_name: str
            - trial_count: int (number of trials executed)
            - survivor_count: int (number of survivors to next stage)
            - wns_delta_ps: float (WNS improvement from previous stage, optional)
            - hot_ratio_delta: float (hot_ratio reduction from previous stage, optional)
            - top_ecos: list[str] (top ECOs used in this stage, optional)
            - degraded: bool (True if WNS worse than previous stage, optional)
        winner_stage_index: Index of final stage containing winner (for highlighting)
        title: Plot title (auto-generated if None)
        figsize: Figure size in inches (width, height). Auto-calculated if None.
        dpi: Resolution in dots per inch
        stages_per_row: Number of stages per row (default: 5)

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

    # Calculate layout
    num_stages = len(stage_data)
    num_rows = (num_stages + stages_per_row - 1) // stages_per_row

    # Auto-calculate figure size if not specified
    if figsize is None:
        width = min(stages_per_row, num_stages) * 3.5 + 1
        height = num_rows * 3.5 + 1.5
        figsize = (width, height)

    # Create figure with GridSpec
    fig = plt.figure(figsize=figsize, dpi=dpi)

    # Add title
    if title is None:
        title = "Stage Progression Summary"
    fig.suptitle(title, fontsize=14, fontweight="bold", y=0.98)

    # Create GridSpec for stage boxes
    gs = fig.add_gridspec(
        num_rows, stages_per_row,
        hspace=0.5,
        wspace=0.3,
        left=0.05,
        right=0.95,
        top=0.90,
        bottom=0.10,
    )

    # Draw stage boxes
    axes_list: list[Axes] = []
    for i, stage in enumerate(stage_data):
        row = i // stages_per_row
        col = i % stages_per_row
        ax = fig.add_subplot(gs[row, col])
        axes_list.append(ax)

        is_winner = winner_stage_index is not None and i == winner_stage_index
        _draw_stage_box(ax, stage, is_winner=is_winner)

    # Draw flow arrows
    _draw_flow_arrows(fig, axes_list, num_stages, stages_per_row)

    # Add legend
    _add_legend(fig)

    return fig


def _draw_stage_box(ax: Axes, stage: dict[str, Any], is_winner: bool = False) -> None:
    """Draw a single stage box with all its information.

    Args:
        ax: matplotlib Axes object
        stage: Stage data dictionary
        is_winner: Whether this is the winner stage
    """
    # Colors
    winner_color = "#50C878"  # Green
    degraded_color = "#FFCCCC"  # Light red
    normal_color = "#CCE5FF"  # Light blue
    border_degraded = "#E74C3C"  # Red
    border_normal = "#4A90E2"  # Blue

    # Determine box color
    degraded = stage.get("degraded", False)
    if is_winner:
        box_color = winner_color
        border_color = "#228B22"  # Dark green
    elif degraded:
        box_color = degraded_color
        border_color = border_degraded
    else:
        box_color = normal_color
        border_color = border_normal

    # Draw rounded rectangle as background
    box = mpatches.FancyBboxPatch(
        (0.05, 0.05),
        0.9,
        0.9,
        boxstyle="round,pad=0.02",
        facecolor=box_color,
        edgecolor=border_color,
        linewidth=3 if is_winner else 2,
        alpha=0.9,
    )
    ax.add_patch(box)

    # Stage name (top)
    stage_name = stage.get("stage_name", f"Stage {stage['stage_index']}")
    # Shorten stage name for display
    display_name = stage_name.replace("stage_", "S")
    ax.text(
        0.5, 0.88,
        display_name,
        ha="center", va="top",
        fontsize=11, fontweight="bold",
        transform=ax.transAxes,
    )

    # Trial/Survivor counts
    ax.text(
        0.5, 0.70,
        f"Trials: {stage['trial_count']}",
        ha="center", va="center",
        fontsize=9,
        transform=ax.transAxes,
    )
    ax.text(
        0.5, 0.56,
        f"Survivors: {stage['survivor_count']}",
        ha="center", va="center",
        fontsize=9,
        transform=ax.transAxes,
    )

    # WNS delta (if available)
    wns_delta = stage.get("wns_delta_ps")
    if wns_delta is not None:
        delta_color = "#228B22" if wns_delta >= 0 else "#E74C3C"
        sign = "+" if wns_delta >= 0 else ""
        ax.text(
            0.5, 0.42,
            f"\u0394WNS: {sign}{wns_delta:.0f}ps",
            ha="center", va="center",
            fontsize=9, fontweight="bold",
            color=delta_color,
            transform=ax.transAxes,
        )

    # ECO badges (bottom)
    top_ecos = stage.get("top_ecos", [])
    if top_ecos:
        # Show top 2 ECOs, shortened
        eco_display = []
        for eco in top_ecos[:2]:
            # Shorten ECO names for display
            short = eco.replace("_", "")[:8]
            eco_display.append(short)
        eco_text = " | ".join(eco_display)
        ax.text(
            0.5, 0.18,
            eco_text,
            ha="center", va="center",
            fontsize=7, style="italic",
            color="#555555",
            transform=ax.transAxes,
        )

    # Degradation warning icon
    if degraded:
        ax.text(
            0.88, 0.88,
            "\u26A0",  # Warning symbol
            ha="center", va="top",
            fontsize=12,
            color="#E74C3C",
            transform=ax.transAxes,
        )

    # Winner badge
    if is_winner:
        ax.text(
            0.5, 0.04,
            "\u2605 WINNER \u2605",
            ha="center", va="bottom",
            fontsize=8, fontweight="bold",
            color="#228B22",
            transform=ax.transAxes,
        )

    # Configure axes
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")


def _draw_flow_arrows(
    fig: Figure,
    axes_list: list[Axes],
    num_stages: int,
    stages_per_row: int,
) -> None:
    """Draw flow arrows connecting stages.

    Args:
        fig: matplotlib Figure object
        axes_list: List of Axes objects for each stage
        num_stages: Total number of stages
        stages_per_row: Number of stages per row
    """
    for i in range(num_stages - 1):
        # Get positions of current and next box
        ax_from = axes_list[i]
        ax_to = axes_list[i + 1]

        # Get bounding boxes in figure coordinates
        bbox_from = ax_from.get_position()
        bbox_to = ax_to.get_position()

        # Determine if arrow is horizontal or wrapping to next row
        current_row = i // stages_per_row
        next_row = (i + 1) // stages_per_row

        if current_row == next_row:
            # Horizontal arrow (same row)
            x_start = bbox_from.x1
            y_start = bbox_from.y0 + bbox_from.height / 2
            x_end = bbox_to.x0
            y_end = bbox_to.y0 + bbox_to.height / 2

            # Draw simple arrow
            fig.patches.append(
                mpatches.FancyArrowPatch(
                    (x_start, y_start),
                    (x_end, y_end),
                    arrowstyle="->",
                    mutation_scale=15,
                    lw=2,
                    color="#555555",
                    transform=fig.transFigure,
                    zorder=1,
                )
            )
        else:
            # Wrapping arrow (end of row to start of next row)
            # Draw a curved arrow that goes down and left
            x_start = bbox_from.x0 + bbox_from.width / 2
            y_start = bbox_from.y0
            x_end = bbox_to.x0 + bbox_to.width / 2
            y_end = bbox_to.y1

            # Calculate midpoint for the curved arrow
            mid_y = (y_start + y_end) / 2

            # Create path for curved arrow
            from matplotlib.patches import FancyArrowPatch
            from matplotlib.path import Path
            import matplotlib.patches as mpatches_path

            # Simple two-segment arrow: down from current, then to next
            arrow = FancyArrowPatch(
                (x_start, y_start - 0.02),
                (x_end, y_end + 0.02),
                arrowstyle="->",
                mutation_scale=15,
                lw=2,
                color="#555555",
                connectionstyle="arc3,rad=0.2",
                transform=fig.transFigure,
                zorder=1,
            )
            fig.patches.append(arrow)


def _add_legend(fig: Figure) -> None:
    """Add legend to the figure.

    Args:
        fig: matplotlib Figure object
    """
    legend_elements = [
        mpatches.Patch(facecolor="#CCE5FF", edgecolor="#4A90E2", linewidth=2, label="Normal Stage"),
        mpatches.Patch(facecolor="#50C878", edgecolor="#228B22", linewidth=3, label="Winner Stage"),
        mpatches.Patch(facecolor="#FFCCCC", edgecolor="#E74C3C", linewidth=2, label="Degradation Stage"),
    ]

    fig.legend(
        handles=legend_elements,
        loc="lower center",
        ncol=3,
        frameon=True,
        fontsize=9,
        bbox_to_anchor=(0.5, 0.01),
    )


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
    stages_per_row: int = 5,
) -> Path:
    """
    Generate and save stage progression visualization.

    High-level convenience function for F234.

    Args:
        stage_data: List of stage dictionaries with trial/survivor counts and deltas
        output_dir: Directory to save the visualization
        winner_stage_index: Index of final stage containing winner (optional)
        filename: Output filename (default: stage_progression.png)
        stages_per_row: Number of stages per row (default: 5)

    Returns:
        Path to saved visualization

    Raises:
        ValueError: If stage_data is invalid
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / filename

    fig = plot_stage_progression(
        stage_data,
        winner_stage_index=winner_stage_index,
        stages_per_row=stages_per_row,
    )
    save_stage_progression_plot(fig, output_path)

    return output_path
