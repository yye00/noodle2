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


def compute_improvement_summary(
    diff_array: np.ndarray,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Compute improvement summary statistics from differential heatmap.

    Quantifies the spatial impact of an ECO by analyzing the differential heatmap.
    Positive values indicate improvement (reduced congestion/density).
    Negative values indicate worsening (increased congestion/density).

    Args:
        diff_array: Differential heatmap array (baseline - comparison)
        metadata: Metadata from compute_heatmap_diff

    Returns:
        Dictionary with improvement summary statistics including:
        - improved_bins: Count of bins with positive diff (improvement)
        - worsened_bins: Count of bins with negative diff (degradation)
        - unchanged_bins: Count of bins with zero diff
        - net_improvement_pct: Percentage of bins improved minus worsened
        - max_improvement_value: Largest improvement value
        - max_improvement_location: (row, col) of max improvement
        - total_bins: Total number of bins in heatmap
    """
    # Count bins by impact type
    improved_bins = int(np.sum(diff_array > 0))
    worsened_bins = int(np.sum(diff_array < 0))
    unchanged_bins = int(np.sum(diff_array == 0))
    total_bins = int(diff_array.size)

    # Compute net improvement percentage
    # (improved - worsened) / total * 100
    net_improvement_pct = (
        ((improved_bins - worsened_bins) / total_bins * 100) if total_bins > 0 else 0.0
    )

    # Find maximum improvement location
    max_improvement_value = float(np.max(diff_array))
    max_improvement_idx = np.unravel_index(np.argmax(diff_array), diff_array.shape)
    max_improvement_location = {
        "row": int(max_improvement_idx[0]),
        "col": int(max_improvement_idx[1]),
    }

    # Find maximum degradation location (for completeness)
    max_degradation_value = float(np.min(diff_array))
    max_degradation_idx = np.unravel_index(np.argmin(diff_array), diff_array.shape)
    max_degradation_location = {
        "row": int(max_degradation_idx[0]),
        "col": int(max_degradation_idx[1]),
    }

    return {
        "improved_bins": improved_bins,
        "worsened_bins": worsened_bins,
        "unchanged_bins": unchanged_bins,
        "total_bins": total_bins,
        "net_improvement_pct": net_improvement_pct,
        "max_improvement_value": max_improvement_value,
        "max_improvement_location": max_improvement_location,
        "max_degradation_value": max_degradation_value,
        "max_degradation_location": max_degradation_location,
        "mean_diff": metadata.get("mean_diff", 0.0),
        "total_improvement": metadata.get("total_improvement", 0.0),
        "total_degradation": metadata.get("total_degradation", 0.0),
    }


def generate_improvement_summary_json(
    baseline_csv: str | Path,
    comparison_csv: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """
    Generate improvement summary JSON from differential heatmap analysis.

    Computes differential heatmap and exports quantified improvement metrics
    as a JSON file for programmatic consumption and dashboard integration.

    Args:
        baseline_csv: Path to baseline heatmap CSV (before ECO)
        comparison_csv: Path to comparison heatmap CSV (after ECO)
        output_path: Path where improvement_summary.json should be saved

    Returns:
        Improvement summary dictionary with all metrics

    Raises:
        FileNotFoundError: If either CSV file doesn't exist
        ValueError: If CSV formats are invalid or dimensions don't match
    """
    import json

    baseline_csv = Path(baseline_csv)
    comparison_csv = Path(comparison_csv)
    output_path = Path(output_path)

    # Compute differential heatmap
    diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)

    # Compute improvement summary
    summary = compute_improvement_summary(diff, metadata)

    # Add file paths to summary
    summary["baseline_csv"] = str(baseline_csv)
    summary["comparison_csv"] = str(comparison_csv)
    summary["heatmap_shape"] = list(diff.shape)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


def track_hotspot_resolution(
    baseline_diagnosis: dict[str, Any],
    comparison_diagnosis: dict[str, Any],
    diff_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Track hotspot resolution between baseline and comparison diagnoses.

    Identifies which hotspots were resolved, which persist, and which are new
    after applying an ECO. Hotspots are matched by their bounding box locations.

    Args:
        baseline_diagnosis: Congestion diagnosis dict from before ECO (must have 'hotspots' key)
        comparison_diagnosis: Congestion diagnosis dict from after ECO (must have 'hotspots' key)
        diff_metadata: Optional differential heatmap metadata for cross-referencing

    Returns:
        Dictionary with hotspot resolution tracking:
        - resolved_hotspots: List of hotspot IDs that no longer appear
        - persisting_hotspots: List of hotspot IDs that still appear (may have reduced severity)
        - new_hotspots: List of new hotspot IDs that appeared after ECO
        - resolution_rate: Percentage of baseline hotspots that were resolved
        - severity_changes: Dict mapping hotspot ID to severity change (improved/same/worsened)
    """
    baseline_hotspots = baseline_diagnosis.get("hotspots", [])
    comparison_hotspots = comparison_diagnosis.get("hotspots", [])

    # Create mapping of hotspot bounding boxes to IDs for matching
    def bbox_key(hotspot: dict[str, Any]) -> tuple[int, int, int, int]:
        """Extract bounding box as hashable key."""
        bbox = hotspot.get("bbox", {})
        return (
            bbox.get("x1", 0),
            bbox.get("y1", 0),
            bbox.get("x2", 0),
            bbox.get("y2", 0),
        )

    # Build lookup maps
    baseline_by_bbox = {bbox_key(h): h for h in baseline_hotspots}
    comparison_by_bbox = {bbox_key(h): h for h in comparison_hotspots}

    # Track hotspot changes
    resolved_hotspots: list[int] = []
    persisting_hotspots: list[int] = []
    new_hotspots: list[int] = []
    severity_changes: dict[int, str] = {}

    # Define severity ordering for comparison
    severity_order = {"minor": 1, "moderate": 2, "critical": 3}

    # Check baseline hotspots
    for bbox, baseline_hs in baseline_by_bbox.items():
        baseline_id = baseline_hs.get("id", -1)

        if bbox in comparison_by_bbox:
            # Hotspot persists (may have changed severity)
            persisting_hotspots.append(baseline_id)

            # Check severity change
            baseline_sev = baseline_hs.get("severity", "unknown")
            comparison_sev = comparison_by_bbox[bbox].get("severity", "unknown")

            baseline_level = severity_order.get(baseline_sev, 0)
            comparison_level = severity_order.get(comparison_sev, 0)

            if comparison_level < baseline_level:
                severity_changes[baseline_id] = "improved"
            elif comparison_level > baseline_level:
                severity_changes[baseline_id] = "worsened"
            else:
                severity_changes[baseline_id] = "same"
        else:
            # Hotspot resolved
            resolved_hotspots.append(baseline_id)

    # Check for new hotspots
    for bbox, comparison_hs in comparison_by_bbox.items():
        if bbox not in baseline_by_bbox:
            new_hotspots.append(comparison_hs.get("id", -1))

    # Calculate resolution rate
    total_baseline = len(baseline_hotspots)
    resolution_rate = (
        (len(resolved_hotspots) / total_baseline * 100) if total_baseline > 0 else 0.0
    )

    return {
        "resolved_hotspots": resolved_hotspots,
        "persisting_hotspots": persisting_hotspots,
        "new_hotspots": new_hotspots,
        "resolution_rate": resolution_rate,
        "severity_changes": severity_changes,
        "baseline_hotspot_count": total_baseline,
        "comparison_hotspot_count": len(comparison_hotspots),
        "net_hotspot_reduction": total_baseline - len(comparison_hotspots),
    }


def generate_improvement_summary_with_hotspots(
    baseline_csv: str | Path,
    comparison_csv: str | Path,
    baseline_diagnosis: dict[str, Any],
    comparison_diagnosis: dict[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    """
    Generate improvement summary with hotspot resolution tracking.

    Extends the basic improvement summary with congestion hotspot tracking,
    identifying which specific hotspots were resolved by the ECO.

    Args:
        baseline_csv: Path to baseline heatmap CSV
        comparison_csv: Path to comparison heatmap CSV
        baseline_diagnosis: Baseline congestion diagnosis dict
        comparison_diagnosis: Comparison congestion diagnosis dict
        output_path: Path where improvement_summary.json should be saved

    Returns:
        Improvement summary dictionary with hotspot tracking added
    """
    import json

    baseline_csv = Path(baseline_csv)
    comparison_csv = Path(comparison_csv)
    output_path = Path(output_path)

    # Compute basic improvement summary
    diff, metadata = compute_heatmap_diff(baseline_csv, comparison_csv)
    summary = compute_improvement_summary(diff, metadata)

    # Add hotspot resolution tracking
    hotspot_tracking = track_hotspot_resolution(
        baseline_diagnosis, comparison_diagnosis, metadata
    )

    # Merge tracking into summary
    summary["hotspot_resolution"] = hotspot_tracking

    # Add file paths
    summary["baseline_csv"] = str(baseline_csv)
    summary["comparison_csv"] = str(comparison_csv)
    summary["heatmap_shape"] = list(diff.shape)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write JSON
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2)

    return summary


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


def generate_differential_heatmaps_safe(
    current_case_heatmaps_dir: str | Path,
    parent_case_heatmaps_dir: str | Path | None,
    output_dir: str | Path,
    has_parent: bool = True,
) -> dict[str, Any]:
    """
    Generate differential heatmaps with graceful fallback when no parent exists.

    For base cases (no parent), differential generation is skipped gracefully
    without raising errors. Absolute heatmaps are still generated, and the
    artifact index indicates that differential heatmaps are unavailable.

    Args:
        current_case_heatmaps_dir: Directory containing current case heatmaps
        parent_case_heatmaps_dir: Directory containing parent case heatmaps (None for base case)
        output_dir: Directory where diff heatmaps should be saved
        has_parent: Whether the case has a parent (default: True)

    Returns:
        Dictionary with generation results:
        - differential_generated: bool indicating if differentials were created
        - differential_count: Number of differential heatmaps generated
        - skip_reason: Reason for skipping (if not generated)
        - results: List of metadata dictionaries for each generated diff heatmap

    Raises:
        Never raises for missing parent - gracefully skips instead
    """
    import logging

    logger = logging.getLogger(__name__)

    current_dir = Path(current_case_heatmaps_dir)
    output_dir = Path(output_dir)

    # Check if this is a base case (no parent)
    if not has_parent or parent_case_heatmaps_dir is None:
        logger.info(
            "Skipping differential heatmap generation: case has no parent (base case)"
        )
        return {
            "differential_generated": False,
            "differential_count": 0,
            "skip_reason": "no_parent",
            "results": [],
            "message": "Base case has no parent - differential heatmaps unavailable",
        }

    parent_dir = Path(parent_case_heatmaps_dir)

    # Check if parent directory exists
    if not parent_dir.exists():
        logger.warning(
            f"Parent heatmap directory not found: {parent_dir} - skipping differential generation"
        )
        return {
            "differential_generated": False,
            "differential_count": 0,
            "skip_reason": "parent_directory_not_found",
            "results": [],
            "message": f"Parent directory not found: {parent_dir}",
        }

    # Check if current directory exists
    if not current_dir.exists():
        logger.warning(
            f"Current case heatmap directory not found: {current_dir} - skipping differential generation"
        )
        return {
            "differential_generated": False,
            "differential_count": 0,
            "skip_reason": "current_directory_not_found",
            "results": [],
            "message": f"Current directory not found: {current_dir}",
        }

    # Generate differential heatmaps
    try:
        results = generate_eco_impact_heatmaps(
            baseline_heatmaps_dir=parent_dir,
            comparison_heatmaps_dir=current_dir,
            output_dir=output_dir,
        )

        logger.info(f"Generated {len(results)} differential heatmaps")

        return {
            "differential_generated": True,
            "differential_count": len(results),
            "skip_reason": None,
            "results": results,
            "message": f"Successfully generated {len(results)} differential heatmaps",
        }

    except Exception as e:
        logger.error(f"Failed to generate differential heatmaps: {e}")
        return {
            "differential_generated": False,
            "differential_count": 0,
            "skip_reason": "generation_error",
            "results": [],
            "message": f"Error during generation: {str(e)}",
        }


def render_heatmap_with_hotspot_annotations(
    csv_path: str | Path,
    output_path: str | Path,
    hotspots: list[dict[str, Any]],
    title: str | None = None,
    colormap: str = "hot",
    dpi: int = 150,
    figsize: tuple[int, int] = (10, 8),
) -> dict[str, Any]:
    """
    Render congestion heatmap with hotspot annotations (IDs and severity values).

    Hotspots are annotated with:
    - Hotspot ID labels like [HS-1], [HS-2], etc.
    - Severity values displayed as percentages (e.g., 0.92, 0.78)
    - Annotations positioned near hotspot bounding box regions

    Args:
        csv_path: Path to congestion heatmap CSV file
        output_path: Path where annotated PNG should be saved
        hotspots: List of hotspot dictionaries with 'id', 'bbox', and 'severity' keys
                  Each hotspot should have: {'id': int, 'bbox': {'x1', 'y1', 'x2', 'y2'},
                  'severity': str or float}
        title: Optional title for the plot
        colormap: Matplotlib colormap name (default: 'hot' for congestion)
        dpi: Resolution in dots per inch (default: 150)
        figsize: Figure size in inches (width, height)

    Returns:
        Metadata dictionary with rendering information including hotspot count

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid or hotspots are malformed

    Example:
        >>> hotspots = [
        ...     {
        ...         'id': 1,
        ...         'bbox': {'x1': 10, 'y1': 20, 'x2': 30, 'y2': 40},
        ...         'severity': 'critical',  # or 0.92
        ...     }
        ... ]
        >>> render_heatmap_with_hotspot_annotations(
        ...     'routing_congestion.csv',
        ...     'hotspots.png',
        ...     hotspots
        ... )
    """
    csv_path = Path(csv_path)
    output_path = Path(output_path)

    # Parse CSV
    data, metadata = parse_heatmap_csv(csv_path)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Render base heatmap
    im = ax.imshow(data, cmap=colormap, interpolation="nearest", aspect="auto")

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Congestion Value", rotation=270, labelpad=20)

    # Map severity strings to numeric values for display
    severity_map = {
        "critical": 0.95,
        "moderate": 0.75,
        "minor": 0.50,
        "low": 0.30,
    }

    # Annotate each hotspot
    for hotspot in hotspots:
        hotspot_id = hotspot.get("id", -1)
        bbox = hotspot.get("bbox", {})

        # Extract bounding box coordinates
        x1 = bbox.get("x1", 0)
        y1 = bbox.get("y1", 0)
        x2 = bbox.get("x2", 0)
        y2 = bbox.get("y2", 0)

        # Calculate center position for annotation
        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0

        # Get severity value (handle both string and numeric formats)
        severity_raw = hotspot.get("severity", "unknown")
        if isinstance(severity_raw, str):
            severity_value = severity_map.get(severity_raw.lower(), 0.50)
        else:
            severity_value = float(severity_raw)

        # Create annotation text with ID and severity
        annotation_text = f"[HS-{hotspot_id}]\n{severity_value:.2f}"

        # Add text annotation near hotspot center
        ax.text(
            center_x,
            center_y,
            annotation_text,
            color="white",
            fontsize=10,
            fontweight="bold",
            ha="center",
            va="center",
            bbox=dict(
                boxstyle="round,pad=0.3",
                facecolor="black",
                alpha=0.7,
                edgecolor="yellow",
                linewidth=1.5,
            ),
        )

        # Draw bounding box outline
        rect_width = x2 - x1
        rect_height = y2 - y1
        rect = plt.Rectangle(
            (x1, y1),
            rect_width,
            rect_height,
            linewidth=2,
            edgecolor="yellow",
            facecolor="none",
            linestyle="--",
            alpha=0.8,
        )
        ax.add_patch(rect)

    # Set title
    if title:
        ax.set_title(title)
    else:
        ax.set_title(f"Congestion Heatmap with Hotspots: {csv_path.stem}")

    # Add axis labels
    ax.set_xlabel("X Bin")
    ax.set_ylabel("Y Bin")

    # Add grid for clarity
    ax.grid(True, alpha=0.2, linestyle="--", linewidth=0.5)

    # Add hotspot count to plot
    info_text = f"Hotspots: {len(hotspots)}"
    ax.text(
        0.02,
        0.98,
        info_text,
        transform=ax.transAxes,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        fontsize=9,
    )

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
        "hotspots_annotated": len(hotspots),
        "hotspot_ids": [h.get("id", -1) for h in hotspots],
    }


def render_heatmap_with_critical_path_overlay(
    csv_path: str | Path,
    output_path: str | Path,
    critical_paths: list[dict[str, Any]],
    title: str | None = None,
    colormap: str = "viridis",
    dpi: int = 150,
    figsize: tuple[int, int] = (8, 6),
    path_count: int = 10,
    color_by: str = "slack",
    show_endpoints: bool = False,
    show_slack_labels: bool = False,
) -> dict[str, Any]:
    """
    Render heatmap with critical paths overlaid as lines.

    Critical paths are drawn as distinct colored lines on top of the heatmap
    to show their spatial routing through the design. This helps identify
    correlation between congestion hotspots and timing-critical paths.

    Args:
        csv_path: Path to heatmap CSV file (typically placement_density)
        output_path: Path where PNG should be saved
        critical_paths: List of critical path dictionaries with 'points' key
                        Each path should have: {'slack_ps': int, 'startpoint': str,
                        'endpoint': str, 'points': [(x1, y1), (x2, y2), ...],
                        'wire_delay_pct': float (optional), 'cell_delay_pct': float (optional)}
        title: Optional title for the plot
        colormap: Matplotlib colormap name for heatmap (default: 'viridis')
        dpi: Resolution in dots per inch (default: 150)
        figsize: Figure size in inches (width, height)
        path_count: Number of paths to overlay (default: 10, uses top N paths)
        color_by: Color mode for paths: 'slack' (red=worst, yellow=moderate),
                  'wire_delay' (by wire delay percentage), or 'cell_delay' (by cell delay percentage)
        show_endpoints: If True, mark path endpoints with visible symbols (stars)
        show_slack_labels: If True, display slack values labeled on paths

    Returns:
        Metadata dictionary with rendering information including path count

    Raises:
        FileNotFoundError: If CSV file doesn't exist
        ValueError: If CSV format is invalid or critical_paths is malformed

    Example:
        >>> critical_paths = [
        ...     {
        ...         'slack_ps': -2150,
        ...         'startpoint': 'input_A',
        ...         'endpoint': 'reg_data[31]',
        ...         'points': [(0, 0), (5, 5), (10, 10)]
        ...     }
        ... ]
        >>> render_heatmap_with_critical_path_overlay(
        ...     'placement_density.csv',
        ...     'critical_paths.png',
        ...     critical_paths,
        ...     path_count=10
        ... )
    """
    csv_path = Path(csv_path)
    output_path = Path(output_path)

    # Parse CSV
    data, metadata = parse_heatmap_csv(csv_path)

    # Create figure
    fig, ax = plt.subplots(figsize=figsize, dpi=dpi)

    # Render base heatmap
    im = ax.imshow(data, cmap=colormap, interpolation="nearest", aspect="auto")

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Value", rotation=270, labelpad=20)

    # Limit to top N paths
    paths_to_draw = critical_paths[:path_count]

    # Validate color_by parameter
    valid_color_modes = ["slack", "wire_delay", "cell_delay"]
    if color_by not in valid_color_modes:
        raise ValueError(
            f"Invalid color_by '{color_by}'. Must be one of: {valid_color_modes}"
        )

    # Determine colors based on color_by mode
    if color_by == "slack":
        # Color by slack: red=worst (most negative), yellow=moderate
        # Extract slack values
        slack_values = [path.get("slack_ps", 0) for path in paths_to_draw]
        if slack_values:
            min_slack = min(slack_values)
            max_slack = max(slack_values)
            slack_range = max_slack - min_slack if max_slack != min_slack else 1.0

            # Normalize to 0-1, where 0=worst (most negative), 1=best
            normalized = [
                (slack - min_slack) / slack_range for slack in slack_values
            ]
            # Use RdYlGn_r (reversed Red-Yellow-Green) for red=worst, yellow/green=better
            path_colors = plt.cm.RdYlGn(normalized)
        else:
            path_colors = plt.cm.Reds(np.linspace(0.5, 1.0, len(paths_to_draw)))

    elif color_by == "wire_delay":
        # Color by wire delay percentage
        wire_delays = [path.get("wire_delay_pct", 50.0) for path in paths_to_draw]
        if wire_delays:
            min_delay = min(wire_delays)
            max_delay = max(wire_delays)
            delay_range = max_delay - min_delay if max_delay != min_delay else 1.0

            # Normalize to 0-1
            normalized = [(delay - min_delay) / delay_range for delay in wire_delays]
            # Use plasma colormap for wire delay
            path_colors = plt.cm.plasma(normalized)
        else:
            path_colors = plt.cm.Reds(np.linspace(0.5, 1.0, len(paths_to_draw)))

    elif color_by == "cell_delay":
        # Color by cell delay percentage
        cell_delays = [path.get("cell_delay_pct", 50.0) for path in paths_to_draw]
        if cell_delays:
            min_delay = min(cell_delays)
            max_delay = max(cell_delays)
            delay_range = max_delay - min_delay if max_delay != min_delay else 1.0

            # Normalize to 0-1
            normalized = [(delay - min_delay) / delay_range for delay in cell_delays]
            # Use viridis colormap for cell delay
            path_colors = plt.cm.viridis(normalized)
        else:
            path_colors = plt.cm.Reds(np.linspace(0.5, 1.0, len(paths_to_draw)))

    for i, path in enumerate(paths_to_draw):
        if "points" not in path:
            continue

        points = path["points"]
        if len(points) < 2:
            continue

        # Extract x and y coordinates
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]

        # Create label based on color_by mode
        if color_by == "slack":
            label_text = f"Path {i+1}: {path.get('slack_ps', 0)}ps"
        elif color_by == "wire_delay":
            label_text = f"Path {i+1}: {path.get('wire_delay_pct', 0):.1f}% wire"
        elif color_by == "cell_delay":
            label_text = f"Path {i+1}: {path.get('cell_delay_pct', 0):.1f}% cell"
        else:
            label_text = f"Path {i+1}"

        # Draw path as line with distinctive styling
        ax.plot(
            xs,
            ys,
            color=path_colors[i],
            linewidth=2.0,
            alpha=0.8,
            marker="o",
            markersize=4,
            label=label_text,
        )

        # Add endpoint markers if requested
        if show_endpoints and len(points) >= 2:
            # Mark startpoint with star
            ax.plot(
                xs[0],
                ys[0],
                marker="*",
                markersize=12,
                color="lime",
                markeredgecolor="black",
                markeredgewidth=1.0,
                zorder=10,
            )
            # Mark endpoint with star
            ax.plot(
                xs[-1],
                ys[-1],
                marker="*",
                markersize=12,
                color="red",
                markeredgecolor="black",
                markeredgewidth=1.0,
                zorder=10,
            )

        # Add slack labels if requested
        if show_slack_labels and len(points) >= 2:
            # Get slack value for label
            slack_ps = path.get("slack_ps", 0)
            slack_label = f"{slack_ps}ps"

            # Position label at midpoint of path (or slightly offset to avoid overlap)
            mid_idx = len(points) // 2
            label_x = xs[mid_idx]
            label_y = ys[mid_idx]

            # Add text annotation with background
            ax.text(
                label_x,
                label_y,
                slack_label,
                color="white",
                fontsize=9,
                fontweight="bold",
                ha="center",
                va="center",
                bbox=dict(
                    boxstyle="round,pad=0.4",
                    facecolor="black",
                    alpha=0.7,
                    edgecolor=path_colors[i],
                    linewidth=1.5,
                ),
                zorder=11,
            )

    # Add legend if paths were drawn
    if paths_to_draw:
        ax.legend(
            loc="upper right",
            fontsize=8,
            framealpha=0.9,
            bbox_to_anchor=(1.0, 1.0),
        )

    # Set title
    if title:
        ax.set_title(title)
    else:
        ax.set_title(f"Heatmap with Critical Paths: {csv_path.stem}")

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
        "paths_drawn": len(paths_to_draw),
        "path_count_limit": path_count,
        "total_paths_available": len(critical_paths),
        "color_by": color_by,
        "show_endpoints": show_endpoints,
        "show_slack_labels": show_slack_labels,
    }
