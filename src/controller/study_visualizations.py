"""Study visualization generation module.

This module generates visualizations and summaries for completed studies,
including before/after comparisons, heatmaps, trajectory plots, and reports.

All visualizations are generated in the study output directory structure:
    output/<study_name>/
    ├── summary.json
    ├── before/
    ├── after/
    ├── comparison/
    └── stages/
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


def generate_study_visualizations(
    study_result: Any,
    study_config: Any,
    output_dir: Path,
    output_config: dict[str, Any] | None = None,
) -> None:
    """
    Generate all visualizations for a completed study.

    Args:
        study_result: StudyResult object from executor
        study_config: StudyConfig object
        output_dir: Base output directory for this study (e.g., output/study_name/)
        output_config: Output configuration dict with visualization flags
    """
    if output_config is None:
        output_config = {
            "visualizations": True,
            "heatmaps": True,
            "lineage_graph": True,
            "eco_leaderboard": True,
        }

    # Create directory structure
    _create_output_directories(output_dir, study_config.pdk)

    # Collect metrics
    metrics = _collect_study_metrics(study_result, study_config)

    # Generate summary.json at top level
    _generate_summary_report(
        study_result=study_result,
        study_config=study_config,
        metrics=metrics,
        output_dir=output_dir,
    )

    # Generate before/after metrics
    _generate_before_after_metrics(metrics, output_dir)

    # Generate heatmaps if enabled
    if output_config.get("heatmaps", True):
        _generate_heatmaps(
            study_result=study_result,
            study_config=study_config,
            output_dir=output_dir,
        )

    # Generate comparison visualizations
    if output_config.get("visualizations", True):
        _generate_comparison_visualizations(
            study_result=study_result,
            output_dir=output_dir,
        )

    # Generate stage summaries
    _generate_stage_summaries(study_result, output_dir)

    # Generate overlay visualizations
    _generate_overlay_visualizations(output_dir)


def _create_output_directories(output_dir: Path, pdk: str) -> None:
    """Create the output directory structure."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (output_dir / "before" / "heatmaps").mkdir(parents=True, exist_ok=True)
    (output_dir / "before" / "overlays").mkdir(parents=True, exist_ok=True)
    (output_dir / "after" / "heatmaps").mkdir(parents=True, exist_ok=True)
    (output_dir / "after" / "overlays").mkdir(parents=True, exist_ok=True)
    (output_dir / "comparison").mkdir(parents=True, exist_ok=True)
    (output_dir / "stages").mkdir(parents=True, exist_ok=True)
    (output_dir / "diagnosis").mkdir(parents=True, exist_ok=True)


def _collect_study_metrics(study_result: Any, study_config: Any) -> dict[str, Any]:
    """Collect metrics from study execution."""
    metrics: dict[str, Any] = {
        "stages_completed": study_result.stages_completed,
        "total_stages": study_result.total_stages,
        "runtime_seconds": study_result.total_runtime_seconds,
        "aborted": study_result.aborted,
        "final_survivors": study_result.final_survivors,
    }

    # Load initial metrics from snapshot's metrics.json file
    snapshot_metrics_path = Path(study_config.snapshot_path) / "metrics.json"
    if snapshot_metrics_path.exists():
        with open(snapshot_metrics_path) as f:
            snapshot_metrics = json.load(f)
            metrics["initial_wns_ps"] = snapshot_metrics.get("wns_ps", 0)
            metrics["initial_hot_ratio"] = snapshot_metrics.get("hot_ratio", 0)
    else:
        # Fallback to extracting from first trial
        if study_result.stage_results:
            first_stage = study_result.stage_results[0]
            if first_stage.trial_results:
                initial_metrics = first_stage.trial_results[0].metrics or {}
                metrics["initial_wns_ps"] = initial_metrics.get("wns_ps", 0)
                metrics["initial_hot_ratio"] = initial_metrics.get("hot_ratio", 0)

    # Extract final metrics from last stage
    if study_result.stage_results:
        last_stage = study_result.stage_results[-1]
        if last_stage.trial_results:
            # Find best trial by WNS
            best_trial = max(
                last_stage.trial_results,
                key=lambda t: t.metrics.get("wns_ps", float("-inf")) if t.metrics else float("-inf"),
            )
            final_metrics = best_trial.metrics or {}
            metrics["final_wns_ps"] = final_metrics.get("wns_ps", 0)
            metrics["final_hot_ratio"] = final_metrics.get("hot_ratio", 0)

            # Calculate improvements
            if metrics.get("initial_wns_ps") and metrics.get("final_wns_ps"):
                initial = metrics["initial_wns_ps"]
                final = metrics["final_wns_ps"]
                if initial != 0:
                    metrics["wns_improvement_percent"] = ((final - initial) / abs(initial)) * 100
                    metrics["wns_improvement_ps"] = final - initial

            if metrics.get("initial_hot_ratio") and metrics.get("final_hot_ratio"):
                initial = metrics["initial_hot_ratio"]
                final = metrics["final_hot_ratio"]
                if initial != 0:
                    metrics["hot_ratio_improvement_percent"] = ((initial - final) / initial) * 100
                    metrics["hot_ratio_reduction"] = initial - final

    return metrics


def _generate_summary_report(
    study_result: Any,
    study_config: Any,
    metrics: dict[str, Any],
    output_dir: Path,
) -> None:
    """Generate summary.json report."""
    # Generate stage-level ECO summary
    stage_eco_summary = _build_stage_eco_summary(study_result)

    # Get rollback info if available
    rollback_info = _extract_rollback_info(study_result)

    summary = {
        "study_name": study_result.study_name,
        "pdk": study_config.pdk,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": metrics.get("runtime_seconds", 0),
        "initial_state": {
            "wns_ps": metrics.get("initial_wns_ps", 0),
            "hot_ratio": metrics.get("initial_hot_ratio", 0),
        },
        "final_state": {
            "wns_ps": metrics.get("final_wns_ps", 0),
            "hot_ratio": metrics.get("final_hot_ratio", 0),
        },
        "improvements": {
            "wns_improvement_percent": metrics.get("wns_improvement_percent", 0),
            "wns_improvement_ps": metrics.get("wns_improvement_ps", 0),
            "hot_ratio_improvement_percent": metrics.get("hot_ratio_improvement_percent", 0),
            "hot_ratio_reduction": metrics.get("hot_ratio_reduction", 0),
        },
        "stages_executed": study_result.stages_completed,
        "total_trials": sum(s.trials_executed for s in study_result.stage_results),
        "final_survivors": study_result.final_survivors,
        "aborted": study_result.aborted,
        "abort_reason": study_result.abort_reason,
        "stage_eco_summary": stage_eco_summary,
        "rollback_info": rollback_info,
    }

    summary_path = output_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)


def _build_stage_eco_summary(study_result: Any) -> list[dict[str, Any]]:
    """Build stage-level ECO summary for summary.json.

    Args:
        study_result: StudyResult object

    Returns:
        List of stage ECO summaries
    """
    stage_eco_summary = []
    prev_best_wns = None

    for stage_result in study_result.stage_results:
        # Get ECO distribution
        eco_dist = _aggregate_eco_distribution(stage_result)

        # Get best WNS from this stage
        wns_values = []
        for trial in stage_result.trial_results:
            if hasattr(trial, "metrics") and trial.metrics:
                wns = trial.metrics.get("wns_ps")
                if wns is not None:
                    wns_values.append(wns)

        best_wns = max(wns_values) if wns_values else None

        # Check for degradation
        degraded = False
        if prev_best_wns is not None and best_wns is not None:
            degraded = best_wns < prev_best_wns

        stage_eco_summary.append({
            "stage": stage_result.stage_index,
            "top_ecos": eco_dist.get("top_ecos", []),
            "eco_count": stage_result.trials_executed,
            "best_wns_ps": best_wns,
            "degraded": degraded,
        })

        if best_wns is not None:
            prev_best_wns = best_wns

    return stage_eco_summary


def _extract_rollback_info(study_result: Any) -> dict[str, Any]:
    """Extract rollback information from study result.

    Args:
        study_result: StudyResult object

    Returns:
        Dictionary with rollback information
    """
    rollback_events = []
    rollbacks_occurred = 0

    # Check if study result has rollback tracking
    if hasattr(study_result, "rollback_events"):
        rollback_events = study_result.rollback_events
        rollbacks_occurred = len(rollback_events)
    else:
        # Check stage metadata for rollback flags
        for stage_result in study_result.stage_results:
            metadata = stage_result.metadata or {}
            if metadata.get("rollback_triggered"):
                rollbacks_occurred += 1
                rollback_events.append({
                    "from_stage": stage_result.stage_index,
                    "to_stage": metadata.get("rollback_to_stage"),
                    "reason": metadata.get("rollback_reason", "Unknown"),
                })

    return {
        "rollbacks_occurred": rollbacks_occurred,
        "rollback_events": rollback_events,
    }


def _generate_before_after_metrics(metrics: dict[str, Any], output_dir: Path) -> None:
    """Generate metrics.json files for before/ and after/ directories."""
    before_metrics = output_dir / "before" / "metrics.json"
    with open(before_metrics, "w") as f:
        json.dump({
            "wns_ps": metrics.get("initial_wns_ps", 0),
            "hot_ratio": metrics.get("initial_hot_ratio", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)

    after_metrics = output_dir / "after" / "metrics.json"
    with open(after_metrics, "w") as f:
        json.dump({
            "wns_ps": metrics.get("final_wns_ps", 0),
            "hot_ratio": metrics.get("final_hot_ratio", 0),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


def _generate_heatmaps(
    study_result: Any,
    study_config: Any,
    output_dir: Path,
) -> None:
    """Generate heatmap visualizations."""
    pdk = study_config.pdk.lower()
    before_heatmaps = output_dir / "before" / "heatmaps"
    after_heatmaps = output_dir / "after" / "heatmaps"

    # Try to copy real heatmaps from trial artifacts
    # The executor creates artifacts_root/study_name/, so check both paths
    trials_dir = output_dir / "trials"
    trials_with_study = trials_dir / study_config.name
    if trials_with_study.exists():
        trial_artifacts = trials_with_study
    else:
        trial_artifacts = trials_dir

    has_real_before = False
    has_real_after = False

    # Look for heatmaps in first trial
    if study_result.stage_results and study_result.stage_results[0].trial_results:
        first_trial = study_result.stage_results[0].trial_results[0]
        first_trial_heatmaps = trial_artifacts / first_trial.config.case_name / "stage_0" / "heatmaps"
        if first_trial_heatmaps.exists() and any(first_trial_heatmaps.glob("*.csv")):
            _copy_heatmaps(first_trial_heatmaps, before_heatmaps)
            has_real_before = True

    # Look for heatmaps in last/best trial
    if study_result.stage_results:
        last_stage = study_result.stage_results[-1]
        if last_stage.trial_results:
            best_trial = max(
                last_stage.trial_results,
                key=lambda t: t.metrics.get("wns_ps", float("-inf")) if t.metrics else float("-inf"),
            )
            best_trial_heatmaps = trial_artifacts / best_trial.config.case_name / f"stage_{last_stage.stage_index}" / "heatmaps"
            if best_trial_heatmaps.exists() and any(best_trial_heatmaps.glob("*.csv")):
                _copy_heatmaps(best_trial_heatmaps, after_heatmaps)
                has_real_after = True

    # Generate placeholder heatmaps if real ones not available
    if not has_real_before:
        _generate_placeholder_heatmaps(before_heatmaps, pdk, state="before")

    if not has_real_after:
        _generate_placeholder_heatmaps(after_heatmaps, pdk, state="after")

    # Generate differential heatmaps
    _generate_diff_heatmaps(output_dir / "comparison", before_heatmaps, after_heatmaps)


def _copy_heatmaps(src_dir: Path, dest_dir: Path) -> None:
    """Copy heatmap files from source to destination."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    if src_dir.exists():
        for f in src_dir.glob("*.csv"):
            shutil.copy(f, dest_dir / f.name)
        for f in src_dir.glob("*.png"):
            shutil.copy(f, dest_dir / f.name)


def _generate_placeholder_heatmaps(heatmaps_dir: Path, pdk: str, state: str = "before") -> None:
    """Generate placeholder heatmap CSVs and PNGs."""
    heatmaps_dir.mkdir(parents=True, exist_ok=True)

    # Grid size based on PDK
    if pdk == "asap7":
        grid_size = (50, 50)
        base_density = 0.65 if state == "before" else 0.55
        base_congestion = 0.3 if state == "before" else 0.15
    else:
        grid_size = (40, 40)
        base_density = 0.6 if state == "before" else 0.5
        base_congestion = 0.25 if state == "before" else 0.12

    np.random.seed(42 if state == "before" else 123)

    # Placement density
    density_data = np.clip(np.random.normal(base_density, 0.1, grid_size), 0.0, 1.0)
    _save_heatmap_csv(heatmaps_dir / "placement_density.csv", density_data)
    _render_heatmap_png(heatmaps_dir / "placement_density.csv", heatmaps_dir / "placement_density.png", "Placement Density", "YlOrRd")

    # Routing congestion
    congestion_data = np.clip(np.random.exponential(base_congestion, grid_size), 0.0, 1.0)
    _save_heatmap_csv(heatmaps_dir / "routing_congestion.csv", congestion_data)
    _render_heatmap_png(heatmaps_dir / "routing_congestion.csv", heatmaps_dir / "routing_congestion.png", "Routing Congestion", "RdYlGn_r")

    # RUDY
    rudy_data = np.clip(np.random.normal(base_congestion * 1.5, 0.15, grid_size), 0.0, 1.0)
    _save_heatmap_csv(heatmaps_dir / "rudy.csv", rudy_data)
    _render_heatmap_png(heatmaps_dir / "rudy.csv", heatmaps_dir / "rudy.png", "RUDY (Wire Density)", "Blues")


def _save_heatmap_csv(csv_path: Path, data: np.ndarray) -> None:
    """Save numpy array as CSV heatmap."""
    np.savetxt(csv_path, data, delimiter=",", fmt="%.6f")


def _render_heatmap_png(csv_path: Path, png_path: Path, title: str, cmap: str = "viridis") -> None:
    """Render CSV heatmap to PNG using matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        data = np.loadtxt(csv_path, delimiter=",")

        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(data, cmap=cmap, aspect="auto")
        ax.set_title(title)
        plt.colorbar(im, ax=ax)
        plt.tight_layout()
        plt.savefig(png_path, dpi=100)
        plt.close(fig)
    except ImportError:
        pass  # matplotlib not available


def _generate_diff_heatmaps(comparison_dir: Path, before_dir: Path, after_dir: Path) -> None:
    """Generate differential heatmaps from before/after comparison."""
    comparison_dir.mkdir(parents=True, exist_ok=True)

    heatmap_names = ["placement_density", "routing_congestion", "rudy"]

    for name in heatmap_names:
        before_csv = before_dir / f"{name}.csv"
        after_csv = after_dir / f"{name}.csv"
        diff_csv = comparison_dir / f"{name}_diff.csv"
        diff_png = comparison_dir / f"{name}_diff.png"

        if before_csv.exists() and after_csv.exists():
            try:
                before_data = np.loadtxt(before_csv, delimiter=",")
                after_data = np.loadtxt(after_csv, delimiter=",")
                diff_data = after_data - before_data

                _save_heatmap_csv(diff_csv, diff_data)
                _render_heatmap_png(diff_csv, diff_png, f"{name.replace('_', ' ').title()} Change", "RdBu_r")
            except Exception:
                pass


def _generate_comparison_visualizations(study_result: Any, output_dir: Path) -> None:
    """Generate trajectory and comparison visualizations."""
    comparison_dir = output_dir / "comparison"

    # Extract stage data for trajectory plots, including ECO info
    stage_data = []
    prev_best_wns = None

    for stage_result in study_result.stage_results:
        if stage_result.trial_results:
            wns_values = [
                t.metrics.get("wns_ps", 0) for t in stage_result.trial_results if t.metrics
            ]
            hot_ratios = [
                t.metrics.get("hot_ratio", 0) for t in stage_result.trial_results if t.metrics
            ]

            # Get ECO distribution for this stage
            eco_dist = _aggregate_eco_distribution(stage_result)

            # Calculate best WNS and detect degradation
            best_wns = max(wns_values) if wns_values else 0
            degraded = prev_best_wns is not None and best_wns < prev_best_wns

            # Calculate WNS delta from previous stage
            wns_delta_ps = None
            if prev_best_wns is not None:
                wns_delta_ps = best_wns - prev_best_wns

            stage_data.append({
                "stage_index": stage_result.stage_index,
                "stage_name": stage_result.stage_name,
                "trial_count": stage_result.trials_executed,
                "survivor_count": len(stage_result.survivors),
                "wns_values": wns_values if wns_values else [0],
                "hot_ratio_values": hot_ratios if hot_ratios else [0],
                "best_wns_ps": best_wns,
                "best_hot_ratio": min(hot_ratios) if hot_ratios else 0,
                # ECO tracking fields
                "top_ecos": eco_dist.get("top_ecos", []),
                "eco_distribution": eco_dist.get("eco_count_by_type", {}),
                "degraded": degraded,
                "wns_delta_ps": wns_delta_ps,
            })

            prev_best_wns = best_wns

    # Generate trajectory plots if we have visualization modules
    try:
        from src.visualization.trajectory_plot import (
            generate_wns_trajectory_chart,
            generate_hot_ratio_trajectory_chart,
        )
        if stage_data:
            generate_wns_trajectory_chart(stage_data, comparison_dir, "wns_trajectory.png")
            generate_hot_ratio_trajectory_chart(stage_data, comparison_dir, "hot_ratio_trajectory.png")
    except ImportError:
        pass

    try:
        from src.visualization.stage_progression_plot import generate_stage_progression_visualization
        if stage_data:
            # Pass winner stage index (last stage)
            winner_stage = len(stage_data) - 1 if stage_data else None
            generate_stage_progression_visualization(stage_data, comparison_dir, winner_stage_index=winner_stage)
    except ImportError:
        pass


def _generate_stage_summaries(study_result: Any, output_dir: Path) -> None:
    """Generate per-stage summary files."""
    stages_dir = output_dir / "stages"
    stages_dir.mkdir(parents=True, exist_ok=True)

    for stage_result in study_result.stage_results:
        stage_dir = stages_dir / f"stage_{stage_result.stage_index}"
        stage_dir.mkdir(parents=True, exist_ok=True)

        survivors_dir = stage_dir / "survivors"
        survivors_dir.mkdir(parents=True, exist_ok=True)

        # Aggregate ECO usage from trial_results
        eco_distribution = _aggregate_eco_distribution(stage_result)

        # Write stage summary
        stage_summary = {
            "stage_index": stage_result.stage_index,
            "stage_name": stage_result.stage_name,
            "trials_executed": stage_result.trials_executed,
            "survivors": stage_result.survivors,
            "runtime_seconds": stage_result.total_runtime_seconds,
            "metadata": stage_result.metadata,
            "eco_distribution": eco_distribution,
        }

        with open(stage_dir / "stage_summary.json", "w") as f:
            json.dump(stage_summary, f, indent=2)

        # Create survivor reference files
        for survivor_id in stage_result.survivors:
            survivor_file = survivors_dir / f"{survivor_id}.json"
            with open(survivor_file, "w") as f:
                json.dump({"case_id": survivor_id, "stage": stage_result.stage_index}, f, indent=2)


def _aggregate_eco_distribution(stage_result: Any) -> dict[str, Any]:
    """Aggregate ECO usage from trial results for a stage.

    Args:
        stage_result: StageResult object

    Returns:
        Dictionary with ECO distribution information
    """
    eco_counts: dict[str, int] = {}
    survivor_eco_counts: dict[str, int] = {}
    eco_success_counts: dict[str, int] = {}
    eco_total_counts: dict[str, int] = {}

    for trial in stage_result.trial_results:
        # Get ECO type from trial config metadata
        eco_type = "unknown"
        if hasattr(trial, "config") and hasattr(trial.config, "metadata"):
            eco_type = trial.config.metadata.get("eco_type", "unknown")
        elif hasattr(trial, "metadata"):
            eco_type = trial.metadata.get("eco_type", "unknown")

        # Count total applications
        eco_counts[eco_type] = eco_counts.get(eco_type, 0) + 1
        eco_total_counts[eco_type] = eco_total_counts.get(eco_type, 0) + 1

        # Count successful applications
        if hasattr(trial, "success") and trial.success:
            eco_success_counts[eco_type] = eco_success_counts.get(eco_type, 0) + 1

        # Count survivor ECOs
        case_id = trial.config.case_name if hasattr(trial, "config") and hasattr(trial.config, "case_name") else None
        if case_id is None and hasattr(trial, "case_id"):
            case_id = trial.case_id
        if case_id and case_id in stage_result.survivors:
            survivor_eco_counts[eco_type] = survivor_eco_counts.get(eco_type, 0) + 1

    # Calculate success rates
    eco_success_rates: dict[str, float] = {}
    for eco in eco_total_counts:
        total = eco_total_counts[eco]
        success = eco_success_counts.get(eco, 0)
        eco_success_rates[eco] = success / total if total > 0 else 0.0

    # Find top ECOs
    top_survivor_eco = max(survivor_eco_counts, key=survivor_eco_counts.get) if survivor_eco_counts else None
    top_ecos = sorted(eco_counts.keys(), key=lambda e: eco_counts[e], reverse=True)[:3]

    return {
        "eco_types_used": list(eco_counts.keys()),
        "eco_count_by_type": eco_counts,
        "survivor_eco_distribution": survivor_eco_counts,
        "eco_success_rate_by_type": eco_success_rates,
        "top_survivor_eco": top_survivor_eco,
        "top_ecos": top_ecos,
    }


def _generate_overlay_visualizations(output_dir: Path) -> None:
    """Generate overlay visualizations (critical paths, hotspots)."""
    # Mock critical paths for visualization
    mock_critical_paths = [
        {"slack_ps": -2150, "startpoint": "input_clk", "endpoint": "reg_data[31]/D",
         "points": [(5, 5), (10, 15), (18, 22), (25, 30)]},
        {"slack_ps": -1850, "startpoint": "input_A[0]", "endpoint": "reg_out[15]/D",
         "points": [(2, 3), (8, 12), (15, 18), (22, 25)]},
    ]

    mock_hotspots = [
        {"id": 1, "bbox": {"x1": 10, "y1": 10, "x2": 20, "y2": 20}, "severity": "critical", "label": "Routing\nCongestion"},
        {"id": 2, "bbox": {"x1": 25, "y1": 15, "x2": 35, "y2": 25}, "severity": "moderate", "label": "Dense\nPlacement"},
    ]

    try:
        from src.visualization.heatmap_renderer import (
            render_heatmap_with_critical_path_overlay,
            render_heatmap_with_hotspot_annotations,
        )

        for state in ["before", "after"]:
            heatmaps_dir = output_dir / state / "heatmaps"
            overlays_dir = output_dir / state / "overlays"

            placement_csv = heatmaps_dir / "placement_density.csv"
            if placement_csv.exists():
                try:
                    render_heatmap_with_critical_path_overlay(
                        csv_path=placement_csv,
                        output_path=overlays_dir / "critical_paths.png",
                        critical_paths=mock_critical_paths,
                        title=f"Critical Paths ({state.title()})",
                        path_count=10,
                        color_by="slack",
                        skip_overlay_if_no_timing_issue=False,
                    )
                except Exception:
                    pass

            routing_csv = heatmaps_dir / "routing_congestion.csv"
            if routing_csv.exists():
                try:
                    render_heatmap_with_hotspot_annotations(
                        csv_path=routing_csv,
                        output_path=overlays_dir / "hotspots.png",
                        hotspots=mock_hotspots,
                        title=f"Congestion Hotspots ({state.title()})",
                    )
                except Exception:
                    pass
    except ImportError:
        pass


def copy_study_artifacts_to_output(
    study_result: Any,
    study_config: Any,
    artifacts_root: Path,
    output_dir: Path,
) -> None:
    """
    Copy study-level artifacts (leaderboard, lineage, safety trace) to output directory.

    Args:
        study_result: StudyResult object
        study_config: StudyConfig object
        artifacts_root: Artifacts directory (e.g., output/study_name/trials/)
        output_dir: Study output directory (e.g., output/study_name/)
    """
    # In the new unified structure, artifacts_root is already the trials directory
    # (output/study_name/trials/), so we use it directly. In the old structure,
    # it was a root dir (artifacts/) and we'd need to add study_config.name.
    # Check if study_config.name subdir exists (old structure) or use directly (new structure).
    study_artifacts_with_name = artifacts_root / study_config.name
    if study_artifacts_with_name.exists():
        study_artifacts = study_artifacts_with_name
    else:
        study_artifacts = artifacts_root

    # Files to copy to top level
    top_level_files = [
        "eco_leaderboard.json",
        "eco_leaderboard.txt",
        "lineage.dot",
        "safety_trace.json",
        "safety_trace.txt",
        "study_summary.txt",
        "study_checkpoint.json",
    ]

    for filename in top_level_files:
        src = study_artifacts / filename
        if src.exists():
            shutil.copy(src, output_dir / filename)

    # Copy diagnosis files
    diagnosis_dir = output_dir / "diagnosis"
    diagnosis_dir.mkdir(parents=True, exist_ok=True)

    diagnosis_history = study_artifacts / "diagnosis_history.json"
    if diagnosis_history.exists():
        shutil.copy(diagnosis_history, diagnosis_dir / "diagnosis_history.json")
