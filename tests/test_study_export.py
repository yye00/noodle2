"""Tests for Study export functionality."""

import json
import csv
from pathlib import Path
from io import StringIO

import pytest

from src.telemetry.study_export import (
    CaseMetricsSummary,
    StudyExport,
    StudyExporter,
    export_study_results,
)
from src.controller.case import Case, CaseGraph
from src.controller.types import (
    StudyConfig,
    StageConfig,
    SafetyDomain,
    ExecutionMode,
    ECOClass,
    TrialMetrics,
    TimingMetrics,
    CongestionMetrics,
    TimingViolationBreakdown,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_study_config() -> StudyConfig:
    """Create a sample Study configuration."""
    return StudyConfig(
        name="test_study",
        safety_domain=SafetyDomain.GUARDED,
        base_case_name="nangate45_base",
        pdk="Nangate45",
        snapshot_path="/path/to/snapshot",
        snapshot_hash="abc123",
        author="Test Author",
        creation_date="2024-01-01T00:00:00Z",
        description="Test study for export",
        stages=[
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_CONGESTION,
                trial_budget=5,
                survivor_count=3,
                allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
            ),
        ],
    )


@pytest.fixture
def sample_case_graph() -> CaseGraph:
    """Create a sample case graph with base + 2 derived cases."""
    graph = CaseGraph()

    # Base case
    base_case = Case.create_base_case(
        base_name="nangate45_base",
        snapshot_path="/path/to/base",
    )
    graph.add_case(base_case)

    # Derived case 1 (stage 0)
    derived1 = base_case.derive(
        eco_name="buffer_insertion",
        new_stage_index=0,
        derived_index=1,
        snapshot_path="/path/to/derived1",
    )
    graph.add_case(derived1)

    # Derived case 2 (stage 0)
    derived2 = base_case.derive(
        eco_name="cell_sizing",
        new_stage_index=0,
        derived_index=2,
        snapshot_path="/path/to/derived2",
    )
    graph.add_case(derived2)

    return graph


@pytest.fixture
def sample_trial_metrics() -> TrialMetrics:
    """Create sample trial metrics."""
    return TrialMetrics(
        timing=TimingMetrics(
            wns_ps=-1500,
            tns_ps=-25000,
            failing_endpoints=10,
            critical_path_delay_ps=5000,
            violation_breakdown=TimingViolationBreakdown(
                setup_violations=8,
                hold_violations=2,
                total_violations=10,
                worst_setup_slack_ps=-1500,
                worst_hold_slack_ps=-200,
            ),
        ),
        congestion=CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=0.05,
            max_overflow=10,
        ),
        runtime_seconds=45.2,
        memory_mb=512.0,
    )


# ============================================================================
# Step 1: Execute Study to completion (simulated via fixtures)
# ============================================================================


def test_execute_study_to_completion(sample_study_config, sample_case_graph):
    """
    Step 1: Execute Study to completion.

    Verify we can represent a completed Study with config and case graph.
    """
    # Verify Study config is complete
    assert sample_study_config.name == "test_study"
    assert len(sample_study_config.stages) == 2

    # Verify case graph has cases
    assert sample_case_graph.count_cases() == 3
    assert sample_case_graph.get_base_case() is not None


# ============================================================================
# Step 2: Export results in standard format (JSON, CSV)
# ============================================================================


def test_export_to_json_format(sample_study_config, sample_case_graph):
    """
    Step 2: Export results in standard JSON format.

    Verify JSON export contains all Study data.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Export
    export = exporter.export()

    # Convert to JSON
    json_str = export.to_json()

    # Parse JSON to verify structure
    data = json.loads(json_str)

    assert data["study_name"] == "test_study"
    assert "study_config" in data
    assert "case_dag" in data
    assert "case_metrics" in data
    assert "stage_summaries" in data
    assert "export_metadata" in data


def test_export_to_csv_format(sample_study_config, sample_case_graph, sample_trial_metrics):
    """
    Step 2: Export results in standard CSV format.

    Verify CSV export contains case metrics in tabular format.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add metrics for all cases
    for case in sample_case_graph.cases.values():
        exporter.add_case_metrics(case.case_id, sample_trial_metrics)

    # Export
    export = exporter.export()

    # Convert to CSV
    csv_str = export.to_csv()

    # Parse CSV
    reader = csv.DictReader(StringIO(csv_str))
    rows = list(reader)

    # Should have 3 rows (3 cases)
    assert len(rows) == 3

    # Verify headers include key fields
    assert "case_id" in rows[0]
    assert "wns_ps" in rows[0]
    assert "eco_applied" in rows[0]


# ============================================================================
# Step 3: Include all Case metrics, rankings, and lineage
# ============================================================================


def test_include_case_metrics_and_rankings(sample_study_config, sample_case_graph, sample_trial_metrics):
    """
    Step 3: Include all Case metrics, rankings, and lineage.

    Verify export includes:
    - Case metrics (timing, congestion)
    - Rankings and scores
    - Lineage information (parent, ECO)
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add metrics with rankings
    cases = list(sample_case_graph.cases.values())
    exporter.add_case_metrics(cases[0].case_id, sample_trial_metrics, rank=1, score=0.95)
    exporter.add_case_metrics(cases[1].case_id, sample_trial_metrics, rank=2, score=0.80)
    exporter.add_case_metrics(cases[2].case_id, sample_trial_metrics, rank=3, score=0.70)

    # Export
    export = exporter.export()

    # Verify case metrics include all data
    assert len(export.case_metrics) == 3

    # Check first case
    case0 = export.case_metrics[0]
    assert "case_id" in case0
    assert "wns_ps" in case0
    assert "rank" in case0
    assert "score" in case0
    assert "parent_case_id" in case0
    assert "eco_applied" in case0

    # Verify lineage is captured
    assert case0["is_base_case"] or case0["parent_case_id"] is not None


def test_include_case_lineage_in_dag(sample_study_config, sample_case_graph):
    """
    Step 3: Include case lineage in DAG export.

    Verify DAG includes nodes and edges representing lineage.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)
    export = exporter.export()

    # DAG should have nodes and edges
    dag = export.case_dag
    assert "nodes" in dag
    assert "edges" in dag
    assert "statistics" in dag

    # Should have 3 nodes (3 cases)
    assert len(dag["nodes"]) == 3

    # Should have 2 edges (2 derivations from base)
    assert len(dag["edges"]) == 2

    # Verify edges include ECO information
    for edge in dag["edges"]:
        assert "source" in edge
        assert "target" in edge
        assert "eco" in edge


# ============================================================================
# Step 4: Write export file to Study artifacts
# ============================================================================


def test_write_export_to_study_artifacts(tmp_path, sample_study_config, sample_case_graph, sample_trial_metrics):
    """
    Step 4: Write export files to Study artifacts directory.

    Verify both JSON and CSV files are written correctly.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add some metrics
    for case in sample_case_graph.cases.values():
        exporter.add_case_metrics(case.case_id, sample_trial_metrics)

    # Export
    export = exporter.export()

    # Write to tmp directory
    output_paths = export.write_all(tmp_path, "test_export")

    # Verify files exist
    assert output_paths["json"].exists()
    assert output_paths["csv"].exists()

    # Verify JSON file has content
    with open(output_paths["json"]) as f:
        data = json.load(f)
        assert data["study_name"] == "test_study"

    # Verify CSV file has content
    with open(output_paths["csv"]) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 3


# ============================================================================
# Step 5: Validate export can be imported by external tool
# ============================================================================


def test_validate_json_is_valid_for_external_tools(tmp_path, sample_study_config, sample_case_graph, sample_trial_metrics):
    """
    Step 5: Validate export can be imported by external tools.

    Verify JSON is valid and can be re-loaded.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add metrics
    for case in sample_case_graph.cases.values():
        exporter.add_case_metrics(case.case_id, sample_trial_metrics)

    # Export and write
    export = exporter.export()
    json_path = tmp_path / "export.json"
    export.write_json(json_path)

    # Re-load JSON (simulating external tool)
    with open(json_path) as f:
        reloaded = json.load(f)

    # Verify structure is intact
    assert reloaded["study_name"] == "test_study"
    assert len(reloaded["case_metrics"]) == 3
    assert "export_metadata" in reloaded
    assert "export_timestamp" in reloaded["export_metadata"]


def test_validate_csv_is_valid_for_pandas_excel(tmp_path, sample_study_config, sample_case_graph, sample_trial_metrics):
    """
    Step 5: Validate CSV can be imported by Pandas/Excel.

    Verify CSV has proper format with headers and data rows.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add metrics
    for case in sample_case_graph.cases.values():
        exporter.add_case_metrics(case.case_id, sample_trial_metrics)

    # Export and write
    export = exporter.export()
    csv_path = tmp_path / "export.csv"
    export.write_csv(csv_path)

    # Read CSV (simulating Pandas/Excel)
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Verify we have data
    assert len(rows) == 3

    # Verify all key fields are present
    first_row = rows[0]
    assert "case_id" in first_row
    assert "wns_ps" in first_row
    assert "tns_ps" in first_row
    assert "rank" in first_row


# ============================================================================
# Step 6: Enable integration with Jupyter, Excel, etc
# ============================================================================


def test_enable_jupyter_integration(tmp_path, sample_study_config, sample_case_graph, sample_trial_metrics):
    """
    Step 6: Enable integration with Jupyter notebooks.

    Verify JSON export has structured data suitable for analysis.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add metrics with rankings
    cases = list(sample_case_graph.cases.values())
    for i, case in enumerate(cases):
        exporter.add_case_metrics(case.case_id, sample_trial_metrics, rank=i+1, score=0.9-i*0.1)

    # Export
    export = exporter.export()
    json_path = tmp_path / "jupyter_export.json"
    export.write_json(json_path)

    # Load in "Jupyter" (simulated)
    with open(json_path) as f:
        study_data = json.load(f)

    # Verify we can easily access structured data
    case_metrics = study_data["case_metrics"]

    # Example analysis: find best WNS
    best_wns = min(m["wns_ps"] for m in case_metrics if m["wns_ps"] is not None)
    assert best_wns == -1500

    # Example: extract ECO effectiveness
    eco_wns_map = {m["eco_applied"]: m["wns_ps"] for m in case_metrics if m["eco_applied"]}
    assert "buffer_insertion" in eco_wns_map or "cell_sizing" in eco_wns_map


def test_enable_excel_integration(tmp_path, sample_study_config, sample_case_graph, sample_trial_metrics):
    """
    Step 6: Enable integration with Excel.

    Verify CSV export is compatible with Excel data analysis.
    """
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add metrics
    cases = list(sample_case_graph.cases.values())
    for i, case in enumerate(cases):
        exporter.add_case_metrics(
            case.case_id,
            sample_trial_metrics,
            rank=i+1,
            score=0.9-i*0.1,
            cpu_time=30.0+i*10.0,
            peak_memory=400.0+i*50.0,
        )

    # Export
    export = exporter.export()
    csv_path = tmp_path / "excel_export.csv"
    export.write_csv(csv_path)

    # Read CSV (simulating Excel)
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Verify numeric fields can be parsed
    first_row = rows[0]
    wns_ps = int(first_row["wns_ps"])
    assert wns_ps == -1500

    cpu_time = float(first_row["cpu_time_seconds"])
    assert cpu_time >= 30.0

    # Verify all rows have consistent structure
    for row in rows:
        assert "case_id" in row
        assert "wns_ps" in row
        assert "rank" in row


# ============================================================================
# Additional tests for robustness
# ============================================================================


def test_case_metrics_summary_from_case_with_metrics(sample_trial_metrics):
    """Test CaseMetricsSummary.from_case() with full metrics."""
    case = Case.create_base_case("test_base", "/path/to/snapshot")

    summary = CaseMetricsSummary.from_case(
        case=case,
        metrics=sample_trial_metrics,
        rank=1,
        score=0.95,
        cpu_time=42.5,
        peak_memory=512.0,
    )

    # Verify all fields populated
    assert summary.case_id == case.case_id
    assert summary.wns_ps == -1500
    assert summary.tns_ps == -25000
    assert summary.setup_violations == 8
    assert summary.hold_violations == 2
    assert summary.bins_hot == 50
    assert summary.rank == 1
    assert summary.score == 0.95
    assert summary.cpu_time_seconds == 42.5
    assert summary.peak_memory_mb == 512.0


def test_case_metrics_summary_from_case_without_metrics():
    """Test CaseMetricsSummary.from_case() without metrics."""
    case = Case.create_base_case("test_base", "/path/to/snapshot")

    summary = CaseMetricsSummary.from_case(case=case)

    # Verify basic fields populated
    assert summary.case_id == case.case_id
    assert summary.is_base_case is True
    assert summary.parent_case_id is None
    assert summary.eco_applied is None

    # Verify metric fields are None
    assert summary.wns_ps is None
    assert summary.rank is None


def test_export_with_stage_summaries(sample_study_config, sample_case_graph):
    """Test export includes stage summaries."""
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add stage summaries
    exporter.add_stage_summary(
        stage_index=0,
        trials_executed=10,
        trials_succeeded=8,
        survivors_selected=5,
        best_wns_ps=-1000,
        avg_runtime_seconds=45.0,
        total_cpu_time_seconds=450.0,
        throughput_trials_per_sec=0.22,
    )

    # Export
    export = exporter.export()

    # Verify stage summary included
    assert len(export.stage_summaries) == 1
    summary = export.stage_summaries[0]
    assert summary["stage_index"] == 0
    assert summary["trials_executed"] == 10
    assert summary["success_rate"] == 0.8


def test_export_metadata_includes_timestamp(sample_study_config, sample_case_graph):
    """Test export metadata includes timestamp and version."""
    exporter = StudyExporter(sample_study_config, sample_case_graph)
    export = exporter.export()

    metadata = export.export_metadata
    assert "export_timestamp" in metadata
    assert "noodle2_version" in metadata
    assert "total_cases" in metadata
    assert "dag_depth" in metadata


def test_convenience_function_export_study_results(tmp_path, sample_study_config, sample_case_graph, sample_trial_metrics):
    """Test convenience function for complete export."""
    # Prepare data
    case_metrics = {}
    for case in sample_case_graph.cases.values():
        case_metrics[case.case_id] = (sample_trial_metrics, 1, 0.9)

    stage_summaries = [
        {
            "stage_index": 0,
            "trials_executed": 10,
            "trials_succeeded": 8,
            "survivors_selected": 5,
        }
    ]

    # Export using convenience function
    output_paths = export_study_results(
        study_config=sample_study_config,
        case_graph=sample_case_graph,
        case_metrics=case_metrics,
        stage_summaries=stage_summaries,
        output_dir=tmp_path,
    )

    # Verify files created
    assert output_paths["json"].exists()
    assert output_paths["csv"].exists()


def test_export_handles_empty_case_metrics(sample_study_config, sample_case_graph):
    """Test export works with no case metrics."""
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Export without adding any metrics
    export = exporter.export()

    # Should still have valid structure
    assert export.study_name == "test_study"
    assert len(export.case_metrics) == 0
    assert export.case_dag["statistics"]["total_cases"] == 3


def test_csv_export_handles_none_values(sample_study_config, sample_case_graph):
    """Test CSV export properly handles None values."""
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add case without metrics (will have None values)
    case = list(sample_case_graph.cases.values())[0]
    exporter.add_case_metrics(case.case_id)

    # Export to CSV
    export = exporter.export()
    csv_str = export.to_csv()

    # Parse CSV
    reader = csv.DictReader(StringIO(csv_str))
    rows = list(reader)

    # Verify None values are represented as empty strings
    assert rows[0]["wns_ps"] == ""
    assert rows[0]["rank"] == ""


def test_export_includes_study_config_details(sample_study_config, sample_case_graph):
    """Test export includes complete Study configuration."""
    exporter = StudyExporter(sample_study_config, sample_case_graph)
    export = exporter.export()

    config = export.study_config
    assert config["name"] == "test_study"
    assert config["safety_domain"] == "guarded"
    assert config["pdk"] == "Nangate45"
    assert config["author"] == "Test Author"
    assert config["num_stages"] == 2
    assert len(config["stages"]) == 2


def test_export_sorts_cases_by_id(sample_study_config, sample_case_graph, sample_trial_metrics):
    """Test case metrics are sorted by case_id for consistency."""
    exporter = StudyExporter(sample_study_config, sample_case_graph)

    # Add metrics in random order
    cases = list(sample_case_graph.cases.values())
    for case in reversed(cases):
        exporter.add_case_metrics(case.case_id, sample_trial_metrics)

    # Export
    export = exporter.export()

    # Verify sorted by case_id
    case_ids = [m["case_id"] for m in export.case_metrics]
    assert case_ids == sorted(case_ids)
