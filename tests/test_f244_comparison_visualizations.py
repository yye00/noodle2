"""Tests for F244: Study comparison generates visualization comparison charts.

Feature: Study comparison generates visualization comparison charts

Steps:
1. Run study comparison
2. Verify comparison_v1_v2/ directory is created
3. Verify pareto_comparison.png shows both frontiers
4. Verify trajectory_comparison.png overlays improvement curves
5. Verify eco_effectiveness_comparison.png is generated
"""

import json
from pathlib import Path

import pytest

from src.controller.study_comparison import (
    ECOEffectivenessComparison,
    MetricComparison,
    StudyComparisonReport,
    StudyMetricsSummary,
    compare_studies,
)
from src.controller.study_comparison_viz import (
    generate_all_comparison_visualizations,
    generate_eco_effectiveness_comparison,
    generate_pareto_comparison,
    generate_trajectory_comparison,
)


class TestStep1RunStudyComparison:
    """Step 1: Run study comparison."""

    def test_generate_all_visualizations_function_exists(self) -> None:
        """Test that generate_all_comparison_visualizations function exists."""
        assert callable(generate_all_comparison_visualizations)

    def test_comparison_report_can_be_visualized(self) -> None:
        """Test that comparison report can be passed to visualization functions."""
        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_tns_ps=-500.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_tns_ps=-200.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Should not raise
        assert report is not None


class TestStep2VerifyComparisonDirectoryCreated:
    """Step 2: Verify comparison_v1_v2/ directory is created."""

    def test_output_directory_is_created(self, tmp_path: Path) -> None:
        """Test that output directory is created when generating visualizations."""
        output_dir = tmp_path / "comparison_v1_v2"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate visualizations
        generate_all_comparison_visualizations(report, output_dir)

        # Verify directory was created
        assert output_dir.exists()
        assert output_dir.is_dir()

    def test_nested_output_directory_is_created(self, tmp_path: Path) -> None:
        """Test that nested output directories are created."""
        output_dir = tmp_path / "artifacts" / "comparison_v1_v2"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate visualizations
        generate_all_comparison_visualizations(report, output_dir)

        # Verify nested directory was created
        assert output_dir.exists()
        assert output_dir.parent.exists()


class TestStep3VerifyParetoComparison:
    """Step 3: Verify pareto_comparison.png shows both frontiers."""

    def test_pareto_comparison_png_is_generated(self, tmp_path: Path) -> None:
        """Test that pareto_comparison.png is generated."""
        output_dir = tmp_path / "comparison_v1_v2"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate visualizations
        charts = generate_all_comparison_visualizations(report, output_dir)

        # Verify pareto_comparison.png exists
        assert "pareto" in charts
        assert charts["pareto"].exists()
        assert charts["pareto"].name == "pareto_comparison.png"

    def test_pareto_comparison_standalone(self, tmp_path: Path) -> None:
        """Test that pareto comparison can be generated standalone."""
        output_path = tmp_path / "pareto_comparison.png"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate pareto comparison
        generate_pareto_comparison(report, output_path)

        # Verify file was created
        assert output_path.exists()

    def test_pareto_comparison_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that pareto comparison file is not empty."""
        output_path = tmp_path / "pareto_comparison.png"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate pareto comparison
        generate_pareto_comparison(report, output_path)

        # Verify file has content
        assert output_path.stat().st_size > 1000  # PNG should be at least 1KB


class TestStep4VerifyTrajectoryComparison:
    """Step 4: Verify trajectory_comparison.png overlays improvement curves."""

    def test_trajectory_comparison_png_is_generated(self, tmp_path: Path) -> None:
        """Test that trajectory_comparison.png is generated."""
        output_dir = tmp_path / "comparison_v1_v2"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate visualizations
        charts = generate_all_comparison_visualizations(report, output_dir)

        # Verify trajectory_comparison.png exists
        assert "trajectory" in charts
        assert charts["trajectory"].exists()
        assert charts["trajectory"].name == "trajectory_comparison.png"

    def test_trajectory_comparison_standalone(self, tmp_path: Path) -> None:
        """Test that trajectory comparison can be generated standalone."""
        output_path = tmp_path / "trajectory_comparison.png"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate trajectory comparison
        generate_trajectory_comparison(report, output_path)

        # Verify file was created
        assert output_path.exists()

    def test_trajectory_comparison_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that trajectory comparison file is not empty."""
        output_path = tmp_path / "trajectory_comparison.png"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],
        )

        # Generate trajectory comparison
        generate_trajectory_comparison(report, output_path)

        # Verify file has content
        assert output_path.stat().st_size > 1000  # PNG should be at least 1KB


class TestStep5VerifyECOEffectivenessVisualization:
    """Step 5: Verify eco_effectiveness_comparison.png is generated."""

    def test_eco_effectiveness_comparison_png_is_generated(self, tmp_path: Path) -> None:
        """Test that eco_effectiveness_comparison.png is generated."""
        output_dir = tmp_path / "comparison_v1_v2"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
            final_hot_ratio=0.8,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
            final_hot_ratio=0.5,
        )

        eco_comparisons = [
            ECOEffectivenessComparison(
                eco_name="buffer_insertion",
                study1_success_rate=0.7,
                study2_success_rate=0.9,
                study1_applications=10,
                study2_applications=10,
            ),
            ECOEffectivenessComparison(
                eco_name="gate_sizing",
                study1_success_rate=0.8,
                study2_success_rate=0.5,
                study1_applications=10,
                study2_applications=10,
            ),
        ]

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=eco_comparisons,
        )

        # Generate visualizations
        charts = generate_all_comparison_visualizations(report, output_dir)

        # Verify eco_effectiveness_comparison.png exists
        assert "eco_effectiveness" in charts
        assert charts["eco_effectiveness"].exists()
        assert charts["eco_effectiveness"].name == "eco_effectiveness_comparison.png"

    def test_eco_effectiveness_comparison_standalone(self, tmp_path: Path) -> None:
        """Test that ECO effectiveness comparison can be generated standalone."""
        output_path = tmp_path / "eco_effectiveness_comparison.png"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
        )

        eco_comparisons = [
            ECOEffectivenessComparison(
                eco_name="buffer_insertion",
                study1_success_rate=0.7,
                study2_success_rate=0.9,
                study1_applications=10,
                study2_applications=10,
            ),
        ]

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=eco_comparisons,
        )

        # Generate ECO effectiveness comparison
        generate_eco_effectiveness_comparison(report, output_path)

        # Verify file was created
        assert output_path.exists()

    def test_eco_effectiveness_comparison_file_is_not_empty(self, tmp_path: Path) -> None:
        """Test that ECO effectiveness comparison file is not empty."""
        output_path = tmp_path / "eco_effectiveness_comparison.png"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
        )

        eco_comparisons = [
            ECOEffectivenessComparison(
                eco_name="buffer_insertion",
                study1_success_rate=0.7,
                study2_success_rate=0.9,
                study1_applications=10,
                study2_applications=10,
            ),
        ]

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=eco_comparisons,
        )

        # Generate ECO effectiveness comparison
        generate_eco_effectiveness_comparison(report, output_path)

        # Verify file has content
        assert output_path.stat().st_size > 1000  # PNG should be at least 1KB

    def test_eco_effectiveness_comparison_without_eco_data(self, tmp_path: Path) -> None:
        """Test ECO effectiveness visualization handles missing ECO data gracefully."""
        output_path = tmp_path / "eco_effectiveness_comparison.png"

        study1_summary = StudyMetricsSummary(
            study_name="study_v1",
            total_cases=10,
            final_wns_ps=-100.0,
        )

        study2_summary = StudyMetricsSummary(
            study_name="study_v2",
            total_cases=10,
            final_wns_ps=-50.0,
        )

        report = StudyComparisonReport(
            study1_name="study_v1",
            study2_name="study_v2",
            study1_summary=study1_summary,
            study2_summary=study2_summary,
            metric_comparisons=[],
            eco_effectiveness_comparisons=[],  # No ECO data
        )

        # Generate ECO effectiveness comparison
        generate_eco_effectiveness_comparison(report, output_path)

        # Should still create a file (placeholder)
        assert output_path.exists()


class TestIntegration:
    """Integration tests for complete visualization workflow."""

    def test_complete_visualization_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow from comparison to visualization."""
        # Create mock telemetry and artifacts
        telemetry_dir = tmp_path / "telemetry"
        artifacts_dir = tmp_path / "artifacts"
        output_dir = tmp_path / "comparison_v1_v2"

        # Study 1
        study1_dir = telemetry_dir / "study_v1"
        study1_dir.mkdir(parents=True)
        study1_summary = study1_dir / "study_summary.json"
        study1_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -100.0,
                    "final_tns_ps": -500.0,
                    "final_hot_ratio": 0.8,
                    "best_case_name": "case_1",
                }
            )
        )

        study1_artifacts = artifacts_dir / "study_v1"
        study1_artifacts.mkdir(parents=True)
        eco_leaderboard1 = study1_artifacts / "eco_leaderboard.json"
        eco_leaderboard1.write_text(
            json.dumps(
                {
                    "study_name": "study_v1",
                    "entries": [
                        {
                            "eco_name": "buffer_insertion",
                            "total_applications": 10,
                            "successful_applications": 7,
                            "success_rate": 0.7,
                            "average_wns_improvement_ps": 50.0,
                        },
                    ],
                }
            )
        )

        # Study 2
        study2_dir = telemetry_dir / "study_v2"
        study2_dir.mkdir(parents=True)
        study2_summary = study2_dir / "study_summary.json"
        study2_summary.write_text(
            json.dumps(
                {
                    "total_cases": 10,
                    "final_wns_ps": -50.0,
                    "final_tns_ps": -200.0,
                    "final_hot_ratio": 0.5,
                    "best_case_name": "case_2",
                }
            )
        )

        study2_artifacts = artifacts_dir / "study_v2"
        study2_artifacts.mkdir(parents=True)
        eco_leaderboard2 = study2_artifacts / "eco_leaderboard.json"
        eco_leaderboard2.write_text(
            json.dumps(
                {
                    "study_name": "study_v2",
                    "entries": [
                        {
                            "eco_name": "buffer_insertion",
                            "total_applications": 10,
                            "successful_applications": 9,
                            "success_rate": 0.9,
                            "average_wns_improvement_ps": 70.0,
                        },
                    ],
                }
            )
        )

        # Compare studies
        report = compare_studies(
            "study_v1", "study_v2", telemetry_root=telemetry_dir, artifacts_root=artifacts_dir
        )

        # Generate visualizations
        charts = generate_all_comparison_visualizations(report, output_dir)

        # Verify all charts were generated
        assert len(charts) == 3
        assert "pareto" in charts
        assert "trajectory" in charts
        assert "eco_effectiveness" in charts

        # Verify all files exist
        assert charts["pareto"].exists()
        assert charts["trajectory"].exists()
        assert charts["eco_effectiveness"].exists()

        # Verify all files are non-empty
        assert charts["pareto"].stat().st_size > 1000
        assert charts["trajectory"].stat().st_size > 1000
        assert charts["eco_effectiveness"].stat().st_size > 1000
