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
