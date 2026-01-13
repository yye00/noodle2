"""
Feature F079: Study comparison can compare two completed studies

Test Steps:
1. Complete study A and study B
2. Run 'noodle2 compare --study1 A --study2 B'
3. Verify comparison output shows: overall metrics delta, ECO effectiveness comparison, key differences
4. Verify visualizations are generated (pareto_comparison.png, trajectory_comparison.png)
5. Verify delta percentages are calculated correctly
"""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.controller.study_comparison import (
    StudyComparisonReport,
    StudyMetricsSummary,
    compare_studies,
    format_comparison_report,
    write_comparison_report,
)
from src.controller.study_comparison_viz import generate_all_comparison_visualizations


class TestF079StudyComparisonE2E:
    """End-to-end tests for F079: Study comparison functionality."""

    @pytest.fixture
    def temp_telemetry_root(self, tmp_path: Path) -> tuple[Path, Path]:
        """Create temporary telemetry directory structure with two completed studies."""
        telemetry_root = tmp_path / "telemetry"
        telemetry_root.mkdir()

        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        # Create Study A with baseline metrics
        study_a_dir = telemetry_root / "study_a"
        study_a_dir.mkdir()

        study_a_summary = {
            "study_name": "study_a",
            "total_cases": 10,
            "final_wns_ps": -50.0,
            "final_tns_ps": -500.0,
            "final_hot_ratio": 0.8,
            "final_total_power_mw": 150.0,
            "best_case_name": "study_a_10_1",
            "total_trials": 50,
            "total_runtime_seconds": 1800.0,
            "stages_completed": 3,
        }

        with open(study_a_dir / "study_summary.json", "w") as f:
            json.dump(study_a_summary, f)

        # Create Study B with improved metrics
        study_b_dir = telemetry_root / "study_b"
        study_b_dir.mkdir()

        study_b_summary = {
            "study_name": "study_b",
            "total_cases": 12,
            "final_wns_ps": -30.0,  # Improved (less negative)
            "final_tns_ps": -300.0,  # Improved (less negative)
            "final_hot_ratio": 0.6,  # Improved (lower)
            "final_total_power_mw": 140.0,  # Improved (lower)
            "best_case_name": "study_b_12_1",
            "total_trials": 60,
            "total_runtime_seconds": 2000.0,
            "stages_completed": 3,
        }

        with open(study_b_dir / "study_summary.json", "w") as f:
            json.dump(study_b_summary, f)

        # Create ECO leaderboard data for study A (in artifacts)
        study_a_artifacts = artifacts_root / "study_a"
        study_a_artifacts.mkdir()

        eco_leaderboard_a = {
            "entries": [
                {
                    "eco_name": "eco_buffer_insertion",
                    "total_applications": 10,
                    "successful_applications": 8,
                    "success_rate": 0.8,
                    "average_wns_improvement_ps": 15.0,
                },
                {
                    "eco_name": "eco_gate_sizing",
                    "total_applications": 8,
                    "successful_applications": 6,
                    "success_rate": 0.75,
                    "average_wns_improvement_ps": 12.0,
                },
            ]
        }
        with open(study_a_artifacts / "eco_leaderboard.json", "w") as f:
            json.dump(eco_leaderboard_a, f)

        # Create ECO leaderboard data for study B (improved)
        study_b_artifacts = artifacts_root / "study_b"
        study_b_artifacts.mkdir()

        eco_leaderboard_b = {
            "entries": [
                {
                    "eco_name": "eco_buffer_insertion",
                    "total_applications": 12,
                    "successful_applications": 11,
                    "success_rate": 0.917,
                    "average_wns_improvement_ps": 18.0,
                },
                {
                    "eco_name": "eco_gate_sizing",
                    "total_applications": 10,
                    "successful_applications": 9,
                    "success_rate": 0.9,
                    "average_wns_improvement_ps": 14.0,
                },
            ]
        }
        with open(study_b_artifacts / "eco_leaderboard.json", "w") as f:
            json.dump(eco_leaderboard_b, f)

        return telemetry_root, artifacts_root

    def test_step_1_complete_study_a_and_b(self, temp_telemetry_root: tuple[Path, Path]) -> None:
        """Step 1: Complete study A and study B."""
        telemetry_root, artifacts_root = temp_telemetry_root
        # Verify both studies have been created with summary data
        study_a_summary = telemetry_root / "study_a" / "study_summary.json"
        study_b_summary = telemetry_root / "study_b" / "study_summary.json"

        assert study_a_summary.exists()
        assert study_b_summary.exists()

        # Verify summary content
        with open(study_a_summary) as f:
            data_a = json.load(f)
            assert data_a["study_name"] == "study_a"
            assert data_a["final_wns_ps"] == -50.0
            assert data_a["stages_completed"] == 3

        with open(study_b_summary) as f:
            data_b = json.load(f)
            assert data_b["study_name"] == "study_b"
            assert data_b["final_wns_ps"] == -30.0
            assert data_b["stages_completed"] == 3

    def test_step_2_run_compare_command(self, temp_telemetry_root: tuple[Path, Path]) -> None:
        """Step 2: Run 'noodle2 compare --study1 A --study2 B' (programmatic)."""
        telemetry_root, artifacts_root = temp_telemetry_root
        # Use the Python API directly for testing
        report = compare_studies(
            "study_a",
            "study_b",
            telemetry_root=telemetry_root,
            artifacts_root=artifacts_root,
        )

        # Verify report was generated
        assert isinstance(report, StudyComparisonReport)
        assert report.study1_name == "study_a"
        assert report.study2_name == "study_b"

    def test_step_3_verify_comparison_output_shows_metrics_and_eco_effectiveness(
        self, temp_telemetry_root: tuple[Path, Path]
    ) -> None:
        """Step 3: Verify comparison output shows overall metrics delta, ECO effectiveness comparison, key differences."""
        telemetry_root, artifacts_root = temp_telemetry_root
        report = compare_studies(
            "study_a",
            "study_b",
            telemetry_root=telemetry_root,
            artifacts_root=artifacts_root,
        )

        # Verify overall metrics delta
        # Find WNS comparison in metric_comparisons list
        wns_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "wns_ps"), None
        )
        assert wns_comparison is not None
        assert wns_comparison.metric_name == "wns_ps"
        assert wns_comparison.study1_value == -50.0
        assert wns_comparison.study2_value == -30.0
        assert wns_comparison.delta == 20.0  # Improvement
        assert wns_comparison.direction == "▲"
        assert wns_comparison.improved is True

        # Find hot_ratio comparison
        hot_ratio_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "hot_ratio"), None
        )
        assert hot_ratio_comparison is not None
        assert hot_ratio_comparison.metric_name == "hot_ratio"
        assert hot_ratio_comparison.study1_value == 0.8
        assert hot_ratio_comparison.study2_value == 0.6
        assert hot_ratio_comparison.delta == pytest.approx(-0.2, rel=0.01)  # Improvement (lower is better)
        assert hot_ratio_comparison.direction == "▲"
        assert hot_ratio_comparison.improved is True

        # Verify ECO effectiveness comparison
        assert len(report.eco_effectiveness_comparisons) > 0

        # Find buffer insertion ECO comparison
        buffer_eco = next(
            (
                eco
                for eco in report.eco_effectiveness_comparisons
                if eco.eco_name == "eco_buffer_insertion"
            ),
            None,
        )
        assert buffer_eco is not None
        assert buffer_eco.study1_success_rate == 0.8  # 8/10
        assert buffer_eco.study2_success_rate == pytest.approx(0.917, rel=0.01)  # 11/12

        # Verify formatted report contains key differences
        formatted_report = format_comparison_report(report)
        assert "study_a" in formatted_report.lower()
        assert "study_b" in formatted_report.lower()
        assert "wns" in formatted_report.lower()
        assert "hot_ratio" in formatted_report.lower() or "hot ratio" in formatted_report.lower()
        assert "eco" in formatted_report.lower()

    def test_step_4_verify_visualizations_are_generated(
        self, temp_telemetry_root: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """Step 4: Verify visualizations are generated (pareto_comparison.png, trajectory_comparison.png)."""
        telemetry_root, artifacts_root = temp_telemetry_root
        report = compare_studies(
            "study_a",
            "study_b",
            telemetry_root=telemetry_root,
            artifacts_root=artifacts_root,
        )

        # Generate visualizations
        viz_dir = tmp_path / "comparison_viz"
        chart_paths = generate_all_comparison_visualizations(report, viz_dir)

        # Verify required visualizations are generated
        assert "pareto" in chart_paths
        assert "trajectory" in chart_paths

        # Verify files exist
        pareto_path = chart_paths["pareto"]
        trajectory_path = chart_paths["trajectory"]

        assert pareto_path.exists()
        assert trajectory_path.exists()

        # Verify files are not empty (PNG files should have content)
        assert pareto_path.stat().st_size > 0
        assert trajectory_path.stat().st_size > 0

        # Verify file names match expected pattern
        assert pareto_path.name == "pareto_comparison.png"
        assert trajectory_path.name == "trajectory_comparison.png"

    def test_step_5_verify_delta_percentages_calculated_correctly(
        self, temp_telemetry_root: tuple[Path, Path]
    ) -> None:
        """Step 5: Verify delta percentages are calculated correctly."""
        telemetry_root, artifacts_root = temp_telemetry_root
        report = compare_studies(
            "study_a",
            "study_b",
            telemetry_root=telemetry_root,
            artifacts_root=artifacts_root,
        )

        # Test WNS delta percentage
        # study_a: -50.0, study_b: -30.0
        # delta = -30.0 - (-50.0) = 20.0
        # percent = (20.0 / 50.0) * 100 = 40.0%
        wns_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "wns_ps"), None
        )
        assert wns_comparison is not None
        assert wns_comparison.delta_percent == pytest.approx(40.0, rel=0.01)

        # Test hot_ratio delta percentage
        # study_a: 0.8, study_b: 0.6
        # delta = 0.6 - 0.8 = -0.2
        # percent = (-0.2 / 0.8) * 100 = -25.0%
        hot_ratio_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "hot_ratio"), None
        )
        assert hot_ratio_comparison is not None
        assert hot_ratio_comparison.delta_percent == pytest.approx(-25.0, rel=0.01)

        # Test TNS delta percentage
        # study_a: -500.0, study_b: -300.0
        # delta = -300.0 - (-500.0) = 200.0
        # percent = (200.0 / 500.0) * 100 = 40.0%
        tns_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "tns_ps"), None
        )
        assert tns_comparison is not None
        assert tns_comparison.delta_percent == pytest.approx(40.0, rel=0.01)

        # Test power delta percentage
        # study_a: 150.0, study_b: 140.0
        # delta = 140.0 - 150.0 = -10.0
        # percent = (-10.0 / 150.0) * 100 = -6.67%
        power_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "total_power_mw"), None
        )
        assert power_comparison is not None
        assert power_comparison.delta_percent == pytest.approx(-6.67, rel=0.01)

    def test_cli_integration_with_visualizations(
        self, temp_telemetry_root: tuple[Path, Path], tmp_path: Path
    ) -> None:
        """Integration test: Run CLI command with --visualize flag."""
        output_file = tmp_path / "comparison_report.txt"

        # Use the CLI module's cmd_compare function
        from argparse import Namespace

        from src.cli import cmd_compare

        args = Namespace(
            study1="study_a",
            study2="study_b",
            output=output_file,
            format="both",
            visualize=True,
        )

        # Unpack the telemetry paths
        telemetry_root, artifacts_root = temp_telemetry_root

        # Mock telemetry_root for compare_studies
        import src.controller.study_comparison as sc_module

        original_compare = sc_module.compare_studies

        def mock_compare(study1: str, study2: str, **kwargs):
            return original_compare(
                study1,
                study2,
                telemetry_root=telemetry_root,
                artifacts_root=artifacts_root,
                **kwargs
            )

        sc_module.compare_studies = mock_compare

        try:
            # Run command
            result = cmd_compare(args)

            # Verify command succeeded
            assert result == 0

            # Verify text report was created
            assert output_file.exists()

            # Verify JSON report was created
            json_output = output_file.with_suffix(".json")
            assert json_output.exists()

            # Verify visualizations directory was created
            viz_dir = output_file.parent / "comparison_viz"
            assert viz_dir.exists()

            # Verify visualization files exist
            assert (viz_dir / "pareto_comparison.png").exists()
            assert (viz_dir / "trajectory_comparison.png").exists()
            assert (viz_dir / "eco_effectiveness_comparison.png").exists()

        finally:
            # Restore original function
            sc_module.compare_studies = original_compare

    def test_comparison_report_serialization(self, temp_telemetry_root: tuple[Path, Path], tmp_path: Path) -> None:
        """Test that comparison report can be written to and read from JSON."""
        telemetry_root, artifacts_root = temp_telemetry_root
        report = compare_studies(
            "study_a",
            "study_b",
            telemetry_root=telemetry_root,
            artifacts_root=artifacts_root,
        )

        # Write report to JSON
        output_file = tmp_path / "comparison_report.json"
        write_comparison_report(report, output_file)

        # Verify file was created
        assert output_file.exists()

        # Read back and verify structure
        with open(output_file) as f:
            data = json.load(f)

        # Verify key fields
        assert data["study1_name"] == "study_a"
        assert data["study2_name"] == "study_b"
        assert "metric_comparisons" in data
        assert "eco_effectiveness_comparisons" in data
        assert "overall_improvement" in data

        # Verify WNS comparison structure (in metric_comparisons list)
        wns_data = next(
            (m for m in data["metric_comparisons"] if m["metric_name"] == "wns_ps"), None
        )
        assert wns_data is not None
        assert wns_data["metric_name"] == "wns_ps"
        assert wns_data["study1_value"] == -50.0
        assert wns_data["study2_value"] == -30.0
        assert wns_data["delta"] == 20.0
        assert wns_data["improved"] is True

    def test_overall_improvement_determination(self, temp_telemetry_root: tuple[Path, Path]) -> None:
        """Test that overall improvement is correctly determined from metric comparisons."""
        telemetry_root, artifacts_root = temp_telemetry_root
        report = compare_studies(
            "study_a",
            "study_b",
            telemetry_root=telemetry_root,
            artifacts_root=artifacts_root,
        )

        # Study B should show overall improvement over Study A
        # (better WNS, better hot_ratio, better TNS, better power)
        assert report.overall_improvement is True

    def test_comparison_handles_missing_metrics_gracefully(self, tmp_path: Path) -> None:
        """Test that comparison handles studies with missing metrics gracefully."""
        telemetry_root = tmp_path / "telemetry"
        telemetry_root.mkdir()

        # Create study with partial metrics
        study_c_dir = telemetry_root / "study_c"
        study_c_dir.mkdir()

        study_c_summary = {
            "study_name": "study_c",
            "total_cases": 5,
            "final_wns_ps": -40.0,
            # Missing hot_ratio, tns_ps, power
            "best_case_name": "study_c_5_1",
            "total_trials": 25,
            "total_runtime_seconds": 900.0,
            "stages_completed": 2,
        }

        with open(study_c_dir / "study_summary.json", "w") as f:
            json.dump(study_c_summary, f)

        # Create another study with different partial metrics
        study_d_dir = telemetry_root / "study_d"
        study_d_dir.mkdir()

        study_d_summary = {
            "study_name": "study_d",
            "total_cases": 6,
            # Missing wns_ps
            "final_hot_ratio": 0.7,
            "best_case_name": "study_d_6_1",
            "total_trials": 30,
            "total_runtime_seconds": 1000.0,
            "stages_completed": 2,
        }

        with open(study_d_dir / "study_summary.json", "w") as f:
            json.dump(study_d_summary, f)

        # Should not raise exception
        report = compare_studies(
            "study_c",
            "study_d",
            telemetry_root=telemetry_root,
        )

        # WNS comparison should have study1 value but not study2
        wns_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "wns_ps"), None
        )
        assert wns_comparison is not None
        assert wns_comparison.study1_value == -40.0
        assert wns_comparison.study2_value is None
        assert wns_comparison.delta is None
        assert wns_comparison.improved is None

        # Hot ratio comparison should have study2 value but not study1
        hot_ratio_comparison = next(
            (m for m in report.metric_comparisons if m.metric_name == "hot_ratio"), None
        )
        assert hot_ratio_comparison is not None
        assert hot_ratio_comparison.study1_value is None
        assert hot_ratio_comparison.study2_value == 0.7
        assert hot_ratio_comparison.delta is None
        assert hot_ratio_comparison.improved is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
