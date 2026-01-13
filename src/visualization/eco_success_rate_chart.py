"""ECO success rate visualization for comparing ECO effectiveness.

This module provides functions to generate bar charts showing the success rate
of different ECOs, helping identify which ECOs are most effective.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
from matplotlib.figure import Figure

from src.controller.eco import ECOEffectiveness


def plot_eco_success_rate_chart(
    eco_effectiveness_list: list[ECOEffectiveness],
    title: str | None = None,
    figsize: tuple[float, float] = (12, 8),
    dpi: int = 150,
    min_applications: int = 1,
) -> Figure:
    """
    Generate ECO success rate bar chart.

    Args:
        eco_effectiveness_list: List of ECOEffectiveness objects to visualize
        title: Plot title (auto-generated if None)
        figsize: Figure size in inches (width, height)
        dpi: Resolution in dots per inch
        min_applications: Minimum number of applications required to include ECO

    Returns:
        matplotlib Figure object

    Raises:
        ValueError: If eco_effectiveness_list is empty or no ECOs meet min_applications
    """
    if not eco_effectiveness_list:
        raise ValueError("eco_effectiveness_list cannot be empty")

    # Filter ECOs by minimum applications and sort by success rate (descending)
    filtered_ecos = [
        eco for eco in eco_effectiveness_list
        if eco.total_applications >= min_applications
    ]

    if not filtered_ecos:
        raise ValueError(
            f"No ECOs have at least {min_applications} applications. "
            f"Available ECOs have: {[e.total_applications for e in eco_effectiveness_list]}"
        )

    # Sort by success rate (descending) for better visualization
    sorted_ecos = sorted(
        filtered_ecos,
        key=lambda e: e.success_rate,
        reverse=True
    )

    # Extract data for plotting
    eco_names = [eco.eco_name for eco in sorted_ecos]
    success_rates = [eco.success_rate * 100 for eco in sorted_ecos]  # Convert to percentage
    total_apps = [eco.total_applications for eco in sorted_ecos]

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Create bar chart with color coding based on success rate
    colors = []
    for rate in success_rates:
        if rate >= 80:
            colors.append("#2ecc71")  # Green for high success
        elif rate >= 50:
            colors.append("#f39c12")  # Orange for medium success
        else:
            colors.append("#e74c3c")  # Red for low success

    bars = ax.bar(
        eco_names,
        success_rates,
        color=colors,
        alpha=0.8,
        edgecolor="black",
        linewidth=1.2,
    )

    # Add value labels on top of bars
    for i, (bar, rate, apps) in enumerate(zip(bars, success_rates, total_apps)):
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            height + 1,
            f"{rate:.1f}%\n(n={apps})",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
        )

    # Add reference line at 50% success rate
    ax.axhline(
        y=50,
        color="gray",
        linestyle="--",
        linewidth=1.5,
        alpha=0.7,
        label="50% Threshold",
    )

    # Styling
    ax.set_xlabel("ECO Type", fontsize=12, fontweight="bold")
    ax.set_ylabel("Success Rate (%)", fontsize=12, fontweight="bold")
    ax.set_ylim(0, 105)  # Add some headroom for labels

    if title is None:
        title = "ECO Success Rate Comparison"
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)

    # Rotate x-axis labels for better readability
    ax.set_xticks(range(len(eco_names)))
    ax.set_xticklabels(eco_names, rotation=45, ha="right")

    # Add grid for readability (horizontal only)
    ax.grid(True, axis="y", alpha=0.3, linestyle="--", linewidth=0.5)

    # Add legend
    ax.legend(loc="upper right", fontsize=10)

    # Tight layout to prevent label cutoff
    fig.tight_layout()

    return fig


def save_eco_success_rate_chart(
    fig: Figure,
    output_path: Path,
) -> None:
    """
    Save ECO success rate chart to PNG file.

    Args:
        fig: matplotlib Figure object to save
        output_path: Path where PNG should be written

    Raises:
        ValueError: If output_path doesn't end in .png
    """
    if not str(output_path).endswith(".png"):
        raise ValueError(f"output_path must end in .png, got: {output_path}")

    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save figure
    fig.savefig(output_path, dpi=fig.dpi, bbox_inches="tight")
    plt.close(fig)


def generate_eco_success_rate_chart(
    eco_effectiveness_map: dict[str, ECOEffectiveness],
    output_path: Path,
    title: str | None = None,
    min_applications: int = 1,
) -> Figure:
    """
    Generate and save ECO success rate chart from effectiveness map.

    This is a convenience function that combines plotting and saving.

    Args:
        eco_effectiveness_map: Dictionary mapping ECO names to effectiveness data
        output_path: Path where PNG should be written
        title: Optional plot title
        min_applications: Minimum number of applications required to include ECO

    Returns:
        matplotlib Figure object (already saved to disk)

    Raises:
        ValueError: If eco_effectiveness_map is empty or invalid
    """
    if not eco_effectiveness_map:
        raise ValueError("eco_effectiveness_map cannot be empty")

    # Convert dict to list
    eco_list = list(eco_effectiveness_map.values())

    # Generate plot
    fig = plot_eco_success_rate_chart(
        eco_list,
        title=title,
        min_applications=min_applications,
    )

    # Save to file
    save_eco_success_rate_chart(fig, output_path)

    return fig
