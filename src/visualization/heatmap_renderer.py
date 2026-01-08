"""Heatmap rendering for spatial visualization of placement and congestion."""

import csv
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap


# Use non-interactive backend for server environments
matplotlib.use("Agg")


def parse_heatmap_csv(csv_path: str | Path) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Parse heatmap CSV file exported by OpenROAD gui::dump_heatmap.

    Args:
        csv_path: Path to CSV file

    Returns:
        Tuple of (data_array, metadata) where data_array is 2D numpy array
        and metadata contains grid dimensions and value ranges

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Heatmap CSV not found: {csv_path}")

    # Read CSV data
    rows: list[list[float]] = []
    with open(csv_path) as f:
        reader = csv.reader(f)
        for row in reader:
            # Skip empty rows
            if not row:
                continue
            # Convert to floats, handling empty cells as 0
            float_row = [float(val) if val.strip() else 0.0 for val in row]
            rows.append(float_row)

    if not rows:
        raise ValueError(f"Empty CSV file: {csv_path}")

    # Convert to numpy array
    data = np.array(rows, dtype=np.float64)

    # Extract metadata
    metadata = {
        "shape": data.shape,
        "min_value": float(np.min(data)),
        "max_value": float(np.max(data)),
        "mean_value": float(np.mean(data)),
        "nonzero_count": int(np.count_nonzero(data)),
    }

    return data, metadata


def render_heatmap_png(
    csv_path: str | Path,
    output_path: str | Path,
    title: str | None = None,
    colormap: str = "hot",
    dpi: int = 150,
    figsize: tuple[int, int] = (8, 6),
) -> dict[str, Any]:
    """
    Render heatmap CSV as PNG image.

    Args:
        csv_path: Path to heatmap CSV file
        output_path: Path where PNG should be saved
        title: Optional title for the plot
        colormap: Matplotlib colormap name (default: 'hot')
        dpi: Resolution in dots per inch (default: 150)
        figsize: Figure size in inches (width, height)

    Returns:
        Metadata dictionary with rendering information

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid
    """
    csv_path = Path(csv_path)
    output_path = Path(output_path)

    # Parse CSV
    data, metadata = parse_heatmap_csv(csv_path)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Render heatmap
    im = ax.imshow(data, cmap=colormap, interpolation="nearest", aspect="auto")

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Value", rotation=270, labelpad=20)

    # Set title
    if title:
        ax.set_title(title)
    else:
        ax.set_title(f"Heatmap: {csv_path.stem}")

    # Add axis labels
    ax.set_xlabel("X Bin")
    ax.set_ylabel("Y Bin")

    # Add grid for clarity
    ax.grid(True, alpha=0.2, linestyle="--", linewidth=0.5)

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save figure
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # Return metadata
    return {
        "csv_path": str(csv_path),
        "png_path": str(output_path),
        "data_shape": metadata["shape"],
        "value_range": [metadata["min_value"], metadata["max_value"]],
        "colormap": colormap,
        "dpi": dpi,
        "figsize": figsize,
    }


def render_all_heatmaps(
    heatmaps_dir: str | Path,
    output_dir: str | Path | None = None,
    colormap: str = "hot",
) -> list[dict[str, Any]]:
    """
    Render all heatmap CSVs in a directory as PNG images.

    Args:
        heatmaps_dir: Directory containing heatmap CSV files
        output_dir: Optional output directory (defaults to same as heatmaps_dir)
        colormap: Matplotlib colormap name

    Returns:
        List of metadata dictionaries for each rendered heatmap

    Raises:
        FileNotFoundError: If heatmaps directory doesn't exist
    """
    heatmaps_dir = Path(heatmaps_dir)
    if not heatmaps_dir.exists():
        raise FileNotFoundError(f"Heatmaps directory not found: {heatmaps_dir}")

    output_dir = Path(output_dir) if output_dir else heatmaps_dir

    results = []

    # Find all CSV files
    csv_files = list(heatmaps_dir.glob("*.csv"))

    for csv_path in csv_files:
        # Generate PNG filename
        png_path = output_dir / f"{csv_path.stem}.png"

        # Determine title from filename
        title = csv_path.stem.replace("_", " ").title()

        # Render heatmap
        try:
            metadata = render_heatmap_png(
                csv_path=csv_path,
                output_path=png_path,
                title=title,
                colormap=colormap,
            )
            results.append(metadata)
        except Exception as e:
            # Log error but continue processing other files
            print(f"Warning: Failed to render {csv_path}: {e}")

    return results


def get_recommended_colormap(heatmap_type: str) -> str:
    """
    Get recommended colormap for a specific heatmap type.

    Args:
        heatmap_type: Type of heatmap (e.g., 'placement_density', 'rudy', 'routing_congestion')

    Returns:
        Matplotlib colormap name
    """
    colormap_map = {
        "placement_density": "viridis",  # Sequential, perceptually uniform
        "rudy": "plasma",  # Sequential, highlights hot spots
        "routing_congestion": "hot",  # Traditional congestion visualization
        "routing": "hot",
        "congestion": "hot",
    }

    # Normalize type to lowercase
    heatmap_type_lower = heatmap_type.lower()

    # Try exact match first
    if heatmap_type_lower in colormap_map:
        return colormap_map[heatmap_type_lower]

    # Try partial match
    for key, cmap in colormap_map.items():
        if key in heatmap_type_lower or heatmap_type_lower in key:
            return cmap

    # Default fallback
    return "hot"


def compute_heatmap_diff(
    baseline_csv: str | Path,
    comparison_csv: str | Path,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Compute spatial difference between two heatmaps (comparison - baseline).

    Positive values indicate improvement areas (lower congestion/density in comparison).
    Negative values indicate degradation areas (higher congestion/density in comparison).

    Args:
        baseline_csv: Path to baseline heatmap CSV (before ECO)
        comparison_csv: Path to comparison heatmap CSV (after ECO)

    Returns:
        Tuple of (diff_array, metadata) where diff_array is the spatial difference
        and metadata contains statistics about the change

    Raises:
        FileNotFoundError: If either CSV file doesn't exist
        ValueError: If CSV formats are invalid or dimensions don't match
    """
    # Parse both heatmaps
    baseline_data, baseline_meta = parse_heatmap_csv(baseline_csv)
    comparison_data, comparison_meta = parse_heatmap_csv(comparison_csv)

    # Validate shapes match
    if baseline_data.shape != comparison_data.shape:
        raise ValueError(
            f"Heatmap dimensions don't match: baseline {baseline_data.shape} "
            f"vs comparison {comparison_data.shape}"
        )

    # Compute difference (comparison - baseline)
    # For congestion: positive diff = congestion reduced (good)
    # For density: positive diff = density reduced (good for over-dense regions)
    diff = baseline_data - comparison_data

    # Compute statistics
    metadata = {
        "baseline_path": str(baseline_csv),
        "comparison_path": str(comparison_csv),
        "shape": diff.shape,
        "min_diff": float(np.min(diff)),
        "max_diff": float(np.max(diff)),
        "mean_diff": float(np.mean(diff)),
        "std_diff": float(np.std(diff)),
        # Count bins by impact
        "improved_bins": int(np.sum(diff > 0)),  # Positive diff = improvement
        "degraded_bins": int(np.sum(diff < 0)),  # Negative diff = degradation
        "unchanged_bins": int(np.sum(diff == 0)),
        # Magnitude statistics
        "total_improvement": float(np.sum(diff[diff > 0])),
        "total_degradation": float(np.abs(np.sum(diff[diff < 0]))),
    }

    return diff, metadata


def render_diff_heatmap(
    baseline_csv: str | Path,
    comparison_csv: str | Path,
    output_path: str | Path,
    title: str | None = None,
    dpi: int = 150,
    figsize: tuple[int, int] = (10, 6),
) -> dict[str, Any]:
    """
    Render comparative heatmap showing before/after ECO spatial impact.

    Green/positive areas show improvement (reduced congestion/density).
    Red/negative areas show degradation (increased congestion/density).

    Args:
        baseline_csv: Path to baseline heatmap CSV (before ECO)
        comparison_csv: Path to comparison heatmap CSV (after ECO)
        output_path: Path where diff heatmap PNG should be saved
        title: Optional title for the plot
        dpi: Resolution in dots per inch (default: 150)
        figsize: Figure size in inches (width, height)

    Returns:
        Metadata dictionary with rendering information and impact statistics

    Raises:
        FileNotFoundError: If either CSV file doesn't exist
        ValueError: If CSV formats are invalid or dimensions don't match
    """
    baseline_csv = Path(baseline_csv)
    comparison_csv = Path(comparison_csv)
    output_path = Path(output_path)

    # Compute difference
    diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

    # Create diverging colormap (red = degradation, white = neutral, green = improvement)
    cmap = LinearSegmentedColormap.from_list(
        "impact",
        ["#d62728", "#ffffff", "#2ca02c"],  # Red -> White -> Green
        N=256,
    )

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Determine symmetric color limits for diverging scale
    vmax = max(abs(metadata["min_diff"]), abs(metadata["max_diff"]))
    vmin = -vmax

    # Render diff heatmap
    im = ax.imshow(
        diff,
        cmap=cmap,
        interpolation="nearest",
        aspect="auto",
        vmin=vmin,
        vmax=vmax,
    )

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Impact (positive = improvement)", rotation=270, labelpad=20)

    # Set title
    if title:
        ax.set_title(title)
    else:
        ax.set_title(
            f"Spatial Impact: {baseline_csv.stem} → {comparison_csv.stem}"
        )

    # Add axis labels
    ax.set_xlabel("X Bin")
    ax.set_ylabel("Y Bin")

    # Add grid for clarity
    ax.grid(True, alpha=0.2, linestyle="--", linewidth=0.5)

    # Add statistics text box
    stats_text = (
        f"Improved bins: {metadata['improved_bins']} "
        f"({100 * metadata['improved_bins'] / diff.size:.1f}%)\n"
        f"Degraded bins: {metadata['degraded_bins']} "
        f"({100 * metadata['degraded_bins'] / diff.size:.1f}%)\n"
        f"Mean impact: {metadata['mean_diff']:.2f}"
    )
    ax.text(
        0.02,
        0.98,
        stats_text,
        transform=ax.transAxes,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        fontsize=8,
    )

    # Tight layout to prevent label cutoff
    plt.tight_layout()

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save figure
    plt.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)

    # Return metadata with rendering info
    return {
        "baseline_csv": str(baseline_csv),
        "comparison_csv": str(comparison_csv),
        "diff_png": str(output_path),
        "data_shape": metadata["shape"],
        "diff_range": [metadata["min_diff"], metadata["max_diff"]],
        "mean_diff": metadata["mean_diff"],
        "improved_bins": metadata["improved_bins"],
        "degraded_bins": metadata["degraded_bins"],
        "unchanged_bins": metadata["unchanged_bins"],
        "total_improvement": metadata["total_improvement"],
        "total_degradation": metadata["total_degradation"],
        "dpi": dpi,
        "figsize": figsize,
    }


def generate_eco_impact_heatmaps(
    baseline_heatmaps_dir: str | Path,
    comparison_heatmaps_dir: str | Path,
    output_dir: str | Path,
) -> list[dict[str, Any]]:
    """
    Generate comparative heatmaps for all matching heatmap types.

    For each heatmap type found in both directories (e.g., placement_density,
    routing_congestion), generates a diff heatmap showing the spatial impact.

    Args:
        baseline_heatmaps_dir: Directory containing baseline heatmaps (before ECO)
        comparison_heatmaps_dir: Directory containing comparison heatmaps (after ECO)
        output_dir: Directory where diff heatmaps should be saved

    Returns:
        List of metadata dictionaries for each generated diff heatmap

    Raises:
        FileNotFoundError: If either heatmaps directory doesn't exist
    """
    baseline_dir = Path(baseline_heatmaps_dir)
    comparison_dir = Path(comparison_heatmaps_dir)
    output_dir = Path(output_dir)

    if not baseline_dir.exists():
        raise FileNotFoundError(f"Baseline heatmaps directory not found: {baseline_dir}")
    if not comparison_dir.exists():
        raise FileNotFoundError(
            f"Comparison heatmaps directory not found: {comparison_dir}"
        )

    results = []

    # Find all CSV files in baseline directory
    baseline_csvs = {csv.stem: csv for csv in baseline_dir.glob("*.csv")}

    # Process each baseline heatmap
    for heatmap_name, baseline_csv in baseline_csvs.items():
        # Look for matching comparison heatmap
        comparison_csv = comparison_dir / f"{heatmap_name}.csv"

        if not comparison_csv.exists():
            print(
                f"Warning: No matching comparison heatmap for {heatmap_name}, skipping"
            )
            continue

        # Generate diff heatmap
        diff_png = output_dir / f"{heatmap_name}_diff.png"
        title = f"{heatmap_name.replace('_', ' ').title()} - ECO Impact"

        try:
            metadata = render_diff_heatmap(
                baseline_csv=baseline_csv,
                comparison_csv=comparison_csv,
                output_path=diff_png,
                title=title,
            )
            results.append(metadata)
        except Exception as e:
            print(f"Warning: Failed to generate diff for {heatmap_name}: {e}")

    return results
