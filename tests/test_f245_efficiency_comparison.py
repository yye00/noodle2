"""Tests for F245: Study comparison quantifies total trials and runtime efficiency.

Feature: Study comparison quantifies total trials and runtime efficiency

Steps:
1. Run study comparison
2. Verify total trials comparison (v1 vs v2)
3. Verify runtime comparison in minutes
4. Verify stages_to_converge comparison
5. Verify efficiency improvements are highlighted (fewer trials, less runtime)
"""

import json
from pathlib import Path

import pytest

from controller.study_comparison import (
    StudyComparisonReport,
    StudyMetricsSummary,
    compare_studies,
    format_comparison_report,
    load_study_summary,
    write_comparison_report,
)


@pytest.fixture
def temp_telemetry_dir(tmp_path: Path) -> Path:
    """Create temporary telemetry directory with study data."""
    telemetry_root = tmp_path / "telemetry"

    # Create Study 1: less efficient (more trials, more runtime)
    study1_dir = telemetry_root / "study_v1"
    study1_dir.mkdir(parents=True)

    study1_summary = {
        "total_cases": 10,
        "final_wns_ps": -100.0,
        "final_tns_ps": -500.0,
        "final_hot_ratio": 0.8,
        "final_total_power_mw": 120.0,
        "best_case_name": "case_001",
        "total_trials": 150,
        "total_runtime_seconds": 3600.0,  # 60 minutes
        "stages_completed": 5,
        "metadata": {
            "warm_start": {"enabled": False},
            "survivor_selection_method": "top_n",
            "auto_diagnosis_enabled": True,
        },
    }

    with open(study1_dir / "study_summary.json", "w") as f:
        json.dump(study1_summary, f)

    # Create Study 2: more efficient (fewer trials, less runtime)
    study2_dir = telemetry_root / "study_v2"
    study2_dir.mkdir(parents=True)

    study2_summary = {
        "total_cases": 10,
        "final_wns_ps": -80.0,  # Better WNS
        "final_tns_ps": -400.0,  # Better TNS
        "final_hot_ratio": 0.6,  # Better hot_ratio
        "final_total_power_mw": 110.0,  # Better power
        "best_case_name": "case_005",
        "total_trials": 100,  # 50 fewer trials
        "total_runtime_seconds": 2400.0,  # 40 minutes (20 minutes faster)
        "stages_completed": 4,  # Converged in fewer stages
        "metadata": {
            "warm_start": {"enabled": True, "source_study": "baseline"},
            "survivor_selection_method": "diversity",
            "auto_diagnosis_enabled": True,
        },
    }

    with open(study2_dir / "study_summary.json", "w") as f:
        json.dump(study2_summary, f)

    return telemetry_root


class TestStep1RunComparison:
    """Step 1: Run study comparison."""

    def test_load_study_with_efficiency_metrics(self, temp_telemetry_dir: Path) -> None:
        """Verify we can load study summary with efficiency metrics."""
        summary = load_study_summary("study_v1", temp_telemetry_dir)

        assert summary.study_name == "study_v1"
        assert summary.total_trials == 150
        assert summary.total_runtime_seconds == 3600.0
        assert summary.stages_completed == 5

    def test_compare_studies_includes_efficiency_data(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify compare_studies includes efficiency data in report."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        assert report.study1_summary.total_trials == 150
        assert report.study1_summary.total_runtime_seconds == 3600.0
        assert report.study1_summary.stages_completed == 5

        assert report.study2_summary.total_trials == 100
        assert report.study2_summary.total_runtime_seconds == 2400.0
        assert report.study2_summary.stages_completed == 4


class TestStep2TotalTrialsComparison:
    """Step 2: Verify total trials comparison (v1 vs v2)."""

    def test_report_includes_total_trials_for_both_studies(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify report includes total_trials for both studies."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        # Verify study summaries have trials data
        assert report.study1_summary.total_trials == 150
        assert report.study2_summary.total_trials == 100

    def test_formatted_report_shows_trials_comparison(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify formatted report shows trials comparison."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        formatted = format_comparison_report(report)

        # Check for EFFICIENCY COMPARISON section
        assert "EFFICIENCY COMPARISON" in formatted
        assert "Total Trials" in formatted
        assert "150" in formatted  # Study 1 trials
        assert "100" in formatted  # Study 2 trials
        assert "50" in formatted or "-50" in formatted  # Delta


class TestStep3RuntimeComparison:
    """Step 3: Verify runtime comparison in minutes."""

    def test_report_includes_runtime_in_minutes(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify report converts runtime to minutes."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        # Raw data in seconds
        assert report.study1_summary.total_runtime_seconds == 3600.0
        assert report.study2_summary.total_runtime_seconds == 2400.0

    def test_formatted_report_shows_runtime_in_minutes(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify formatted report shows runtime in minutes."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        formatted = format_comparison_report(report)

        # Check for runtime in minutes
        assert "Runtime (min)" in formatted
        assert "60.0" in formatted  # Study 1: 3600s = 60 min
        assert "40.0" in formatted  # Study 2: 2400s = 40 min
        assert "20.0" in formatted or "-20.0" in formatted  # Delta: 20 minutes saved


class TestStep4StagesToConvergeComparison:
    """Step 4: Verify stages_to_converge comparison."""

    def test_report_includes_stages_completed(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify report includes stages_completed for both studies."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        assert report.study1_summary.stages_completed == 5
        assert report.study2_summary.stages_completed == 4

    def test_formatted_report_shows_stages_comparison(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify formatted report shows stages comparison."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        formatted = format_comparison_report(report)

        # Check for stages comparison
        assert "Stages to Converge" in formatted or "Stages Completed" in formatted
        assert "5" in formatted  # Study 1 stages
        assert "4" in formatted  # Study 2 stages


class TestStep5EfficiencyImprovementsHighlighted:
    """Step 5: Verify efficiency improvements are highlighted."""

    def test_efficiency_improvements_shown_with_direction_indicators(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify efficiency improvements use direction indicators (▲/▼)."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        formatted = format_comparison_report(report)

        # Study 2 should show efficiency improvements
        # Fewer trials = improvement (▲)
        # Less runtime = improvement (▲)
        # Fewer stages = improvement (▲)

        # Check for improvement indicators in efficiency section
        assert "▲" in formatted or "improvement" in formatted.lower()

    def test_efficiency_summary_highlights_gains(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify efficiency summary highlights specific gains."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        formatted = format_comparison_report(report)

        # Should mention:
        # - Trial reduction (50 fewer trials)
        # - Runtime savings (20 minutes faster)
        # - Faster convergence (1 fewer stage)

        # Check that deltas are present
        lines = formatted.split("\n")
        efficiency_section = []
        in_efficiency = False
        dash_count = 0
        for line in lines:
            if "EFFICIENCY" in line:
                in_efficiency = True
            elif in_efficiency and "---" in line:
                dash_count += 1
                # Continue collecting lines after second dash (the data rows)
            elif in_efficiency:
                if dash_count >= 2:  # We've passed both header dashes, collect data
                    if not line.strip():  # Stop at empty line (end of section)
                        break
                    efficiency_section.append(line)
                # Skip the header line between the dashes

        efficiency_text = "\n".join(efficiency_section)

        # Verify we have the delta values
        assert "-50" in efficiency_text or "50 fewer" in efficiency_text.lower()
        assert "-20" in efficiency_text or "20.0" in efficiency_text


class TestEfficiencyComparisonWithNoImprovement:
    """Test efficiency comparison when study 2 is less efficient."""

    def test_regression_in_efficiency_is_highlighted(self, tmp_path: Path) -> None:
        """Verify that regressions in efficiency are also highlighted."""
        telemetry_root = tmp_path / "telemetry"

        # Create Study 1: efficient
        study1_dir = telemetry_root / "efficient_study"
        study1_dir.mkdir(parents=True)

        study1_summary = {
            "total_cases": 5,
            "final_wns_ps": -80.0,
            "final_tns_ps": -400.0,
            "final_hot_ratio": 0.6,
            "best_case_name": "case_001",
            "total_trials": 50,
            "total_runtime_seconds": 1200.0,  # 20 minutes
            "stages_completed": 3,
            "metadata": {},
        }

        with open(study1_dir / "study_summary.json", "w") as f:
            json.dump(study1_summary, f)

        # Create Study 2: less efficient (regression)
        study2_dir = telemetry_root / "inefficient_study"
        study2_dir.mkdir(parents=True)

        study2_summary = {
            "total_cases": 5,
            "final_wns_ps": -85.0,  # Slightly worse
            "final_tns_ps": -420.0,
            "final_hot_ratio": 0.65,
            "best_case_name": "case_003",
            "total_trials": 80,  # More trials (regression)
            "total_runtime_seconds": 1800.0,  # 30 minutes (regression)
            "stages_completed": 4,  # More stages (regression)
            "metadata": {},
        }

        with open(study2_dir / "study_summary.json", "w") as f:
            json.dump(study2_summary, f)

        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "efficient_study",
            "inefficient_study",
            telemetry_root=telemetry_root,
            artifacts_root=artifacts_root,
        )

        formatted = format_comparison_report(report)

        # Should indicate regressions
        assert "▼" in formatted or "regression" in formatted.lower()
        assert "+30" in formatted or "30 more" in formatted.lower()  # 30 more trials


class TestJSONOutputWithEfficiencyData:
    """Test that JSON output includes efficiency data."""

    def test_json_report_includes_efficiency_metrics(
        self, temp_telemetry_dir: Path, tmp_path: Path
    ) -> None:
        """Verify JSON output includes efficiency metrics."""
        artifacts_root = tmp_path / "artifacts"
        artifacts_root.mkdir()

        report = compare_studies(
            "study_v1",
            "study_v2",
            telemetry_root=temp_telemetry_dir,
            artifacts_root=artifacts_root,
        )

        output_file = tmp_path / "comparison_report.json"
        write_comparison_report(report, output_file)

        with open(output_file) as f:
            data = json.load(f)

        # Verify efficiency data is in JSON
        assert data["study1_summary"]["total_trials"] == 150
        assert data["study1_summary"]["total_runtime_seconds"] == 3600.0
        assert data["study1_summary"]["stages_completed"] == 5

        assert data["study2_summary"]["total_trials"] == 100
        assert data["study2_summary"]["total_runtime_seconds"] == 2400.0
        assert data["study2_summary"]["stages_completed"] == 4
