"""Export structured Study results for integration with external analysis tools."""

import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from ..controller.case import Case, CaseGraph
from ..controller.types import StudyConfig, TrialMetrics, TimingMetrics, CongestionMetrics


@dataclass
class CaseMetricsSummary:
    """Summary of metrics for a single Case."""

    case_id: str
    stage_index: int
    derived_index: int
    parent_case_id: str | None
    eco_applied: str | None
    is_base_case: bool

    # Timing metrics
    wns_ps: int | None = None
    tns_ps: int | None = None
    failing_endpoints: int | None = None
    critical_path_delay_ps: int | None = None

    # Timing violation breakdown
    setup_violations: int | None = None
    hold_violations: int | None = None
    worst_setup_slack_ps: int | None = None
    worst_hold_slack_ps: int | None = None

    # Congestion metrics
    bins_total: int | None = None
    bins_hot: int | None = None
    hot_ratio: float | None = None
    max_overflow: int | None = None

    # Resource metrics
    runtime_seconds: float | None = None
    memory_mb: float | None = None
    cpu_time_seconds: float | None = None
    peak_memory_mb: float | None = None

    # Rankings and scores (optional, added by ranking system)
    rank: int | None = None
    score: float | None = None

    @classmethod
    def from_case(
        cls,
        case: Case,
        metrics: TrialMetrics | None = None,
        rank: int | None = None,
        score: float | None = None,
        cpu_time: float | None = None,
        peak_memory: float | None = None,
    ) -> "CaseMetricsSummary":
        """
        Create summary from Case and optional metrics.

        Args:
            case: Case instance
            metrics: Trial metrics (if available)
            rank: Case rank in survivor selection
            score: Case score from ranking
            cpu_time: CPU time in seconds
            peak_memory: Peak memory in MB

        Returns:
            CaseMetricsSummary instance
        """
        summary = cls(
            case_id=case.case_id,
            stage_index=case.stage_index,
            derived_index=case.identifier.derived_index,
            parent_case_id=case.parent_id,
            eco_applied=case.eco_applied,
            is_base_case=case.is_base_case,
            rank=rank,
            score=score,
            cpu_time_seconds=cpu_time,
            peak_memory_mb=peak_memory,
        )

        # Extract metrics if available
        if metrics:
            summary._populate_from_metrics(metrics)

        return summary

    def _populate_from_metrics(self, metrics: TrialMetrics) -> None:
        """Populate fields from TrialMetrics."""
        # Timing metrics
        self.wns_ps = metrics.timing.wns_ps
        self.tns_ps = metrics.timing.tns_ps
        self.failing_endpoints = metrics.timing.failing_endpoints
        self.critical_path_delay_ps = metrics.timing.critical_path_delay_ps

        # Violation breakdown
        if metrics.timing.violation_breakdown:
            vb = metrics.timing.violation_breakdown
            self.setup_violations = vb.setup_violations
            self.hold_violations = vb.hold_violations
            self.worst_setup_slack_ps = vb.worst_setup_slack_ps
            self.worst_hold_slack_ps = vb.worst_hold_slack_ps

        # Congestion metrics
        if metrics.congestion:
            self.bins_total = metrics.congestion.bins_total
            self.bins_hot = metrics.congestion.bins_hot
            self.hot_ratio = metrics.congestion.hot_ratio
            self.max_overflow = metrics.congestion.max_overflow

        # Resource metrics
        self.runtime_seconds = metrics.runtime_seconds
        self.memory_mb = metrics.memory_mb


@dataclass
class StudyExport:
    """
    Complete export of Study results.

    Includes:
    - Study configuration
    - Case lineage graph (DAG)
    - Per-Case metrics and rankings
    - Stage summaries
    - Export metadata (timestamp, version)
    """

    study_name: str
    study_config: dict[str, Any]
    case_dag: dict[str, Any]  # From CaseGraph.export_dag()
    case_metrics: list[dict[str, Any]]  # List of CaseMetricsSummary dicts
    stage_summaries: list[dict[str, Any]]  # Per-stage aggregates
    export_metadata: dict[str, Any]

    def to_json(self, indent: int = 2) -> str:
        """
        Export to JSON format.

        Args:
            indent: JSON indentation level (default: 2)

        Returns:
            JSON string
        """
        export_dict = {
            "study_name": self.study_name,
            "study_config": self.study_config,
            "case_dag": self.case_dag,
            "case_metrics": self.case_metrics,
            "stage_summaries": self.stage_summaries,
            "export_metadata": self.export_metadata,
        }
        return json.dumps(export_dict, indent=indent)

    def to_csv(self) -> str:
        """
        Export case metrics to CSV format.

        Returns CSV with one row per Case, including all metrics
        and lineage information.

        Returns:
            CSV string
        """
        if not self.case_metrics:
            return ""

        # Get fieldnames from first case (all cases have same structure)
        fieldnames = list(self.case_metrics[0].keys())

        # Build CSV
        lines = []

        # Header
        lines.append(",".join(fieldnames))

        # Rows
        for case_dict in self.case_metrics:
            row_values = []
            for field in fieldnames:
                value = case_dict.get(field)
                # Handle None and boolean values
                if value is None:
                    row_values.append("")
                elif isinstance(value, bool):
                    row_values.append(str(value))
                else:
                    row_values.append(str(value))
            lines.append(",".join(row_values))

        return "\n".join(lines)

    def write_json(self, output_path: Path | str) -> None:
        """
        Write JSON export to file.

        Args:
            output_path: Output file path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(self.to_json())

    def write_csv(self, output_path: Path | str) -> None:
        """
        Write CSV export to file.

        Args:
            output_path: Output file path
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(self.to_csv())

    def write_all(self, output_dir: Path | str, base_name: str | None = None) -> dict[str, Path]:
        """
        Write both JSON and CSV exports to directory.

        Args:
            output_dir: Output directory
            base_name: Base filename (default: study_name)

        Returns:
            Dictionary mapping format to output path
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if base_name is None:
            base_name = self.study_name

        json_path = output_dir / f"{base_name}_export.json"
        csv_path = output_dir / f"{base_name}_export.csv"

        self.write_json(json_path)
        self.write_csv(csv_path)

        return {
            "json": json_path,
            "csv": csv_path,
        }


class StudyExporter:
    """
    Generates structured exports of Study results.

    Supports export to:
    - JSON: Complete Study data with full fidelity
    - CSV: Flattened case metrics for Excel/Jupyter

    Export includes:
    - Study configuration
    - Case lineage (DAG)
    - Per-Case metrics
    - Stage summaries
    - Export metadata (timestamp, version)
    """

    def __init__(self, study_config: StudyConfig, case_graph: CaseGraph):
        """
        Initialize exporter.

        Args:
            study_config: Study configuration
            case_graph: Case graph with lineage
        """
        self.study_config = study_config
        self.case_graph = case_graph
        self.case_metrics_map: dict[str, CaseMetricsSummary] = {}
        self.stage_summaries: list[dict[str, Any]] = []

    def add_case_metrics(
        self,
        case_id: str,
        metrics: TrialMetrics | None = None,
        rank: int | None = None,
        score: float | None = None,
        cpu_time: float | None = None,
        peak_memory: float | None = None,
    ) -> None:
        """
        Add metrics for a Case.

        Args:
            case_id: Case identifier
            metrics: Trial metrics
            rank: Case rank
            score: Case score
            cpu_time: CPU time in seconds
            peak_memory: Peak memory in MB
        """
        case = self.case_graph.get_case(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found in graph")

        summary = CaseMetricsSummary.from_case(
            case=case,
            metrics=metrics,
            rank=rank,
            score=score,
            cpu_time=cpu_time,
            peak_memory=peak_memory,
        )

        self.case_metrics_map[case_id] = summary

    def add_stage_summary(
        self,
        stage_index: int,
        trials_executed: int,
        trials_succeeded: int,
        survivors_selected: int,
        best_wns_ps: int | None = None,
        avg_runtime_seconds: float | None = None,
        total_cpu_time_seconds: float | None = None,
        throughput_trials_per_sec: float | None = None,
    ) -> None:
        """
        Add summary for a Stage.

        Args:
            stage_index: Stage index
            trials_executed: Number of trials executed
            trials_succeeded: Number of successful trials
            survivors_selected: Number of survivors selected
            best_wns_ps: Best WNS achieved in stage
            avg_runtime_seconds: Average runtime per trial
            total_cpu_time_seconds: Total CPU time for stage
            throughput_trials_per_sec: Throughput in trials/sec
        """
        if stage_index >= len(self.study_config.stages):
            raise ValueError(f"Invalid stage index: {stage_index}")

        stage_config = self.study_config.stages[stage_index]

        summary = {
            "stage_index": stage_index,
            "stage_name": stage_config.name,
            "execution_mode": stage_config.execution_mode.value,
            "trial_budget": stage_config.trial_budget,
            "survivor_count": stage_config.survivor_count,
            "trials_executed": trials_executed,
            "trials_succeeded": trials_succeeded,
            "success_rate": trials_succeeded / trials_executed if trials_executed > 0 else 0.0,
            "survivors_selected": survivors_selected,
            "best_wns_ps": best_wns_ps,
            "avg_runtime_seconds": avg_runtime_seconds,
            "total_cpu_time_seconds": total_cpu_time_seconds,
            "throughput_trials_per_sec": throughput_trials_per_sec,
        }

        self.stage_summaries.append(summary)

    def export(self) -> StudyExport:
        """
        Generate complete Study export.

        Returns:
            StudyExport with all collected data
        """
        # Export Study config
        config_dict = {
            "name": self.study_config.name,
            "safety_domain": self.study_config.safety_domain.value,
            "base_case_name": self.study_config.base_case_name,
            "pdk": self.study_config.pdk,
            "snapshot_path": self.study_config.snapshot_path,
            "snapshot_hash": self.study_config.snapshot_hash,
            "author": self.study_config.author,
            "creation_date": self.study_config.creation_date,
            "description": self.study_config.description,
            "num_stages": len(self.study_config.stages),
            "stages": [
                {
                    "name": stage.name,
                    "execution_mode": stage.execution_mode.value,
                    "trial_budget": stage.trial_budget,
                    "survivor_count": stage.survivor_count,
                    "allowed_eco_classes": [cls.value for cls in stage.allowed_eco_classes],
                    "abort_threshold_wns_ps": stage.abort_threshold_wns_ps,
                    "visualization_enabled": stage.visualization_enabled,
                    "timeout_seconds": stage.timeout_seconds,
                }
                for stage in self.study_config.stages
            ],
        }

        # Export case DAG
        case_dag = self.case_graph.export_dag()

        # Export case metrics
        case_metrics = [
            asdict(summary)
            for summary in self.case_metrics_map.values()
        ]

        # Sort by case_id for consistent ordering
        case_metrics.sort(key=lambda x: x["case_id"])

        # Export metadata
        from datetime import timezone
        export_metadata = {
            "export_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "noodle2_version": "2.0.0",
            "total_cases": len(case_metrics),
            "total_stages": len(self.stage_summaries),
            "dag_depth": self.case_graph.get_dag_depth(),
        }

        return StudyExport(
            study_name=self.study_config.name,
            study_config=config_dict,
            case_dag=case_dag,
            case_metrics=case_metrics,
            stage_summaries=self.stage_summaries,
            export_metadata=export_metadata,
        )


def export_study_results(
    study_config: StudyConfig,
    case_graph: CaseGraph,
    case_metrics: dict[str, tuple[TrialMetrics | None, int | None, float | None]],
    stage_summaries: list[dict[str, Any]],
    output_dir: Path | str,
) -> dict[str, Path]:
    """
    Convenience function to export Study results.

    Args:
        study_config: Study configuration
        case_graph: Case graph with lineage
        case_metrics: Map of case_id to (metrics, rank, score)
        stage_summaries: List of per-stage summaries
        output_dir: Output directory

    Returns:
        Dictionary mapping format to output path
    """
    exporter = StudyExporter(study_config, case_graph)

    # Add case metrics
    for case_id, (metrics, rank, score) in case_metrics.items():
        exporter.add_case_metrics(case_id, metrics, rank, score)

    # Add stage summaries
    for summary in stage_summaries:
        exporter.add_stage_summary(**summary)

    # Generate export
    export = exporter.export()

    # Write to files
    return export.write_all(output_dir)
