"""Tests for F241: Compare two studies and generate comparison report.

Feature steps:
1. Complete two studies: nangate45_v1 and nangate45_v2
2. Execute: noodle2 compare --study1 nangate45_v1 --study2 nangate45_v2
3. Verify comparison report is generated
4. Verify overall metrics comparison table is present
5. Verify final WNS, TNS, hot_ratio deltas are calculated
6. Verify delta percentages and direction indicators (▲/▼)
"""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def setup_test_studies(tmp_path):
    """Create test telemetry data for two studies."""
    telemetry_dir = tmp_path / "telemetry"

    # Create Study 1 telemetry
    study1_dir = telemetry_dir / "nangate45_v1"
    cases1_dir = study1_dir / "cases"
    cases1_dir.mkdir(parents=True, exist_ok=True)

    # Create case telemetry for study1
    case1_telemetry = {
        "case_id": "nangate45_v1_base",
        "base_case": "nangate45",
        "stage_index": 0,
        "metadata": {},
        "trials": [
            {
                "trial_index": 0,
                "metrics": {
                    "wns_ps": -500.0,
                    "tns_ps": -5000.0,
                    "hot_ratio": 0.45,
                    "total_power_mw": 15.0,
                },
                "success": True,
            }
        ],
    }

    with open(cases1_dir / "nangate45_v1_base_telemetry.json", "w") as f:
        json.dump(case1_telemetry, f, indent=2)

    # Create Study 2 telemetry (with improvements)
    study2_dir = telemetry_dir / "nangate45_v2"
    cases2_dir = study2_dir / "cases"
    cases2_dir.mkdir(parents=True, exist_ok=True)

    # Create case telemetry for study2 (improved metrics)
    case2_telemetry = {
        "case_id": "nangate45_v2_base",
        "base_case": "nangate45",
        "stage_index": 0,
        "metadata": {},
        "trials": [
            {
                "trial_index": 0,
                "metrics": {
                    "wns_ps": -300.0,  # Improved (less negative)
                    "tns_ps": -3000.0,  # Improved (less negative)
                    "hot_ratio": 0.30,  # Improved (lower)
                    "total_power_mw": 12.0,  # Improved (lower)
                },
                "success": True,
            }
        ],
    }

    with open(cases2_dir / "nangate45_v2_base_telemetry.json", "w") as f:
        json.dump(case2_telemetry, f, indent=2)

    return tmp_path


class TestStudyComparisonFunctionality:
    """Test study comparison functionality (F241)."""

    def test_step_1_complete_two_studies(self, setup_test_studies):
        """
        Step 1: Complete two studies: nangate45_v1 and nangate45_v2

        This step verifies that we can load telemetry from two completed studies.
        """
        from src.controller.study_comparison import load_study_summary

        telemetry_root = setup_test_studies / "telemetry"

        # Load study 1
        study1_summary = load_study_summary("nangate45_v1", telemetry_root)
        assert study1_summary.study_name == "nangate45_v1"
        assert study1_summary.total_cases == 1
        assert study1_summary.final_wns_ps == -500.0

        # Load study 2
        study2_summary = load_study_summary("nangate45_v2", telemetry_root)
        assert study2_summary.study_name == "nangate45_v2"
        assert study2_summary.total_cases == 1
        assert study2_summary.final_wns_ps == -300.0

    def test_step_2_execute_compare_command(self, setup_test_studies):
        """
        Step 2: Execute: noodle2 compare --study1 nangate45_v1 --study2 nangate45_v2

        This step verifies the compare command can be executed successfully.
        """
        from src.controller.study_comparison import compare_studies

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)

        assert report.study1_name == "nangate45_v1"
        assert report.study2_name == "nangate45_v2"
        assert len(report.metric_comparisons) > 0

    def test_step_3_verify_comparison_report_generated(self, setup_test_studies):
        """
        Step 3: Verify comparison report is generated.

        The comparison report should contain all necessary components.
        """
        from src.controller.study_comparison import compare_studies

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)

        # Verify report structure
        assert report.study1_summary is not None
        assert report.study2_summary is not None
        assert report.metric_comparisons is not None
        assert report.comparison_timestamp is not None

    def test_step_4_verify_overall_metrics_comparison_table(self, setup_test_studies):
        """
        Step 4: Verify overall metrics comparison table is present.

        The report should include comparisons for all key metrics.
        """
        from src.controller.study_comparison import compare_studies

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)

        # Verify we have comparisons for key metrics
        metric_names = [c.metric_name for c in report.metric_comparisons]

        assert "wns_ps" in metric_names
        assert "tns_ps" in metric_names
        assert "hot_ratio" in metric_names
        assert "total_power_mw" in metric_names

    def test_step_5_verify_deltas_calculated(self, setup_test_studies):
        """
        Step 5: Verify final WNS, TNS, hot_ratio deltas are calculated.

        Deltas should be computed as study2 - study1.
        """
        from src.controller.study_comparison import compare_studies

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)

        # Find WNS comparison
        wns_comparison = None
        for c in report.metric_comparisons:
            if c.metric_name == "wns_ps":
                wns_comparison = c
                break

        assert wns_comparison is not None
        assert wns_comparison.study1_value == -500.0
        assert wns_comparison.study2_value == -300.0
        assert wns_comparison.delta == 200.0  # -300 - (-500) = 200

        # Find TNS comparison
        tns_comparison = None
        for c in report.metric_comparisons:
            if c.metric_name == "tns_ps":
                tns_comparison = c
                break

        assert tns_comparison is not None
        assert tns_comparison.delta == 2000.0  # -3000 - (-5000) = 2000

        # Find hot_ratio comparison
        hot_ratio_comparison = None
        for c in report.metric_comparisons:
            if c.metric_name == "hot_ratio":
                hot_ratio_comparison = c
                break

        assert hot_ratio_comparison is not None
        assert abs(hot_ratio_comparison.delta - (-0.15)) < 0.01  # 0.30 - 0.45 = -0.15

    def test_step_6_verify_delta_percentages_and_direction_indicators(
        self, setup_test_studies
    ):
        """
        Step 6: Verify delta percentages and direction indicators (▲/▼).

        Each comparison should include:
        - Delta percentage
        - Direction indicator (▲ for improvement, ▼ for regression)
        """
        from src.controller.study_comparison import compare_studies

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)

        # Check WNS comparison
        wns_comparison = next(
            (c for c in report.metric_comparisons if c.metric_name == "wns_ps"), None
        )
        assert wns_comparison is not None
        assert wns_comparison.delta_percent is not None
        assert abs(wns_comparison.delta_percent - 40.0) < 0.1  # 200/500 * 100 = 40%
        assert wns_comparison.direction == "▲"  # Improvement (less negative)
        assert wns_comparison.improved is True

        # Check hot_ratio comparison
        hot_ratio_comparison = next(
            (c for c in report.metric_comparisons if c.metric_name == "hot_ratio"), None
        )
        assert hot_ratio_comparison is not None
        assert hot_ratio_comparison.delta_percent is not None
        assert abs(hot_ratio_comparison.delta_percent + 33.33) < 1.0  # -0.15/0.45 * 100
        assert hot_ratio_comparison.direction == "▲"  # Improvement (lower is better)
        assert hot_ratio_comparison.improved is True


class TestStudyComparisonReportFormating:
    """Test report formatting functionality."""

    def test_format_comparison_report_text(self, setup_test_studies):
        """Test text formatting of comparison report."""
        from src.controller.study_comparison import (
            compare_studies,
            format_comparison_report,
        )

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)
        formatted = format_comparison_report(report)

        # Verify report contains key sections
        assert "STUDY COMPARISON REPORT" in formatted
        assert "nangate45_v1" in formatted
        assert "nangate45_v2" in formatted
        assert "METRICS COMPARISON" in formatted
        assert "wns_ps" in formatted
        assert "▲" in formatted  # Should show improvements

    def test_write_comparison_report_json(self, setup_test_studies):
        """Test JSON report writing."""
        from src.controller.study_comparison import (
            compare_studies,
            write_comparison_report,
        )

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)

        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            output_file = Path(f.name)

        write_comparison_report(report, output_file)

        # Verify file was written
        assert output_file.exists()

        # Load and verify structure
        with open(output_file) as f:
            report_data = json.load(f)

        assert report_data["study1_name"] == "nangate45_v1"
        assert report_data["study2_name"] == "nangate45_v2"
        assert "metric_comparisons" in report_data
        assert len(report_data["metric_comparisons"]) == 4  # 4 metrics

        # Clean up
        output_file.unlink()


class TestStudyComparisonOverallAssessment:
    """Test overall improvement/regression assessment."""

    def test_overall_improvement_detected(self, setup_test_studies):
        """Test that overall improvement is correctly detected."""
        from src.controller.study_comparison import compare_studies

        telemetry_root = setup_test_studies / "telemetry"

        report = compare_studies("nangate45_v1", "nangate45_v2", telemetry_root)

        # Study 2 should show overall improvement
        assert report.overall_improvement is True

    def test_overall_regression_detected(self, tmp_path):
        """Test that overall regression is correctly detected."""
        from src.controller.study_comparison import compare_studies

        # Create studies with regression
        telemetry_dir = tmp_path / "telemetry"

        # Study 1 (baseline)
        study1_dir = telemetry_dir / "study1"
        cases1_dir = study1_dir / "cases"
        cases1_dir.mkdir(parents=True, exist_ok=True)

        case1_telemetry = {
            "case_id": "study1_base",
            "trials": [
                {
                    "metrics": {
                        "wns_ps": -300.0,
                        "tns_ps": -3000.0,
                        "hot_ratio": 0.30,
                        "total_power_mw": 12.0,
                    }
                }
            ],
        }

        with open(cases1_dir / "study1_base_telemetry.json", "w") as f:
            json.dump(case1_telemetry, f)

        # Study 2 (worse metrics)
        study2_dir = telemetry_dir / "study2"
        cases2_dir = study2_dir / "cases"
        cases2_dir.mkdir(parents=True, exist_ok=True)

        case2_telemetry = {
            "case_id": "study2_base",
            "trials": [
                {
                    "metrics": {
                        "wns_ps": -600.0,  # Worse
                        "tns_ps": -6000.0,  # Worse
                        "hot_ratio": 0.50,  # Worse
                        "total_power_mw": 18.0,  # Worse
                    }
                }
            ],
        }

        with open(cases2_dir / "study2_base_telemetry.json", "w") as f:
            json.dump(case2_telemetry, f)

        report = compare_studies("study1", "study2", telemetry_dir)

        # Study 2 should show overall regression
        assert report.overall_improvement is False


class TestStudyComparisonErrorHandling:
    """Test error handling in study comparison."""

    def test_compare_nonexistent_study1(self, tmp_path):
        """Test comparison with non-existent study1."""
        from src.controller.study_comparison import compare_studies

        telemetry_dir = tmp_path / "telemetry"
        telemetry_dir.mkdir(parents=True)

        with pytest.raises(FileNotFoundError) as excinfo:
            compare_studies("nonexistent_study", "another_study", telemetry_dir)

        assert "nonexistent_study" in str(excinfo.value)

    def test_compare_nonexistent_study2(self, setup_test_studies):
        """Test comparison with non-existent study2."""
        from src.controller.study_comparison import compare_studies

        telemetry_root = setup_test_studies / "telemetry"

        with pytest.raises(FileNotFoundError) as excinfo:
            compare_studies("nangate45_v1", "nonexistent_study", telemetry_root)

        assert "nonexistent_study" in str(excinfo.value)

    def test_compare_study_with_no_cases(self, tmp_path):
        """Test comparison with study that has no cases."""
        from src.controller.study_comparison import compare_studies

        telemetry_dir = tmp_path / "telemetry"

        # Create empty study
        study_dir = telemetry_dir / "empty_study"
        study_dir.mkdir(parents=True)

        # Create another valid study
        study2_dir = telemetry_dir / "valid_study"
        cases2_dir = study2_dir / "cases"
        cases2_dir.mkdir(parents=True)

        case_telemetry = {
            "case_id": "valid_case",
            "trials": [{"metrics": {"wns_ps": -300.0}}],
        }

        with open(cases2_dir / "valid_case_telemetry.json", "w") as f:
            json.dump(case_telemetry, f)

        with pytest.raises(FileNotFoundError):
            compare_studies("empty_study", "valid_study", telemetry_dir)


class TestStudyComparisonCLI:
    """Test CLI integration for compare command."""

    def test_compare_command_help(self):
        """Test that compare command is available in CLI."""
        import subprocess

        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.cli", "compare", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "compare" in result.stdout.lower()
        assert "--study1" in result.stdout
        assert "--study2" in result.stdout
        assert "direction indicators" in result.stdout.lower()
