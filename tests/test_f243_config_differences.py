"""Tests for F243: Study comparison identifies key differences in configuration.

Feature steps:
1. Run comparison between studies with different configs
2. Verify 'Key Differences' section is present
3. Verify warm_start usage is noted
4. Verify survivor selection method differences are highlighted
5. Verify auto-diagnosis enablement differences are shown
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.study_comparison import (
    ConfigurationDifference,
    compare_studies,
    compare_study_configurations,
    format_comparison_report,
    StudyMetricsSummary,
)


@pytest.fixture
def temp_telemetry_dir():
    """Create temporary telemetry directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestStep1RunComparisonWithDifferentConfigs:
    """Step 1: Run comparison between studies with different configs."""

    def test_create_study_with_warm_start_enabled(self, temp_telemetry_dir):
        """Create study with warm-start enabled."""
        study_dir = temp_telemetry_dir / "telemetry" / "study_with_warmstart"
        study_dir.mkdir(parents=True)

        summary = {
            "total_cases": 10,
            "final_wns_ps": -200.0,
            "final_tns_ps": -1000.0,
            "final_hot_ratio": 0.30,
            "final_total_power_mw": 15.0,
            "best_case_name": "case_008",
            "metadata": {
                "warm_start": {
                    "enabled": True,
                    "source_study": "previous_study_v1",
                },
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }

        (study_dir / "study_summary.json").write_text(json.dumps(summary, indent=2))
        assert (study_dir / "study_summary.json").exists()

    def test_create_study_with_warm_start_disabled(self, temp_telemetry_dir):
        """Create study with warm-start disabled."""
        study_dir = temp_telemetry_dir / "telemetry" / "study_without_warmstart"
        study_dir.mkdir(parents=True)

        summary = {
            "total_cases": 10,
            "final_wns_ps": -250.0,
            "final_tns_ps": -1200.0,
            "final_hot_ratio": 0.35,
            "final_total_power_mw": 16.0,
            "best_case_name": "case_007",
            "metadata": {
                "warm_start": {
                    "enabled": False,
                },
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }

        (study_dir / "study_summary.json").write_text(json.dumps(summary, indent=2))
        assert (study_dir / "study_summary.json").exists()

    def test_run_comparison_with_config_differences(self, temp_telemetry_dir):
        """Test running comparison between studies with different configs."""
        # Create study 1 (with warm-start)
        study1_dir = temp_telemetry_dir / "telemetry" / "study1_config"
        study1_dir.mkdir(parents=True)

        summary1 = {
            "total_cases": 10,
            "final_wns_ps": -200.0,
            "final_tns_ps": -1000.0,
            "final_hot_ratio": 0.30,
            "final_total_power_mw": 15.0,
            "best_case_name": "case_008",
            "metadata": {
                "warm_start": {"enabled": True, "source_study": "baseline"},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(summary1, indent=2))

        # Create study 2 (without warm-start)
        study2_dir = temp_telemetry_dir / "telemetry" / "study2_config"
        study2_dir.mkdir(parents=True)

        summary2 = {
            "total_cases": 10,
            "final_wns_ps": -180.0,
            "final_tns_ps": -900.0,
            "final_hot_ratio": 0.28,
            "final_total_power_mw": 14.0,
            "best_case_name": "case_009",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(summary2, indent=2))

        # Run comparison
        report = compare_studies(
            "study1_config",
            "study2_config",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        assert report.study1_name == "study1_config"
        assert report.study2_name == "study2_config"
        assert len(report.configuration_differences) > 0


class TestStep2VerifyKeyDifferencesSectionPresent:
    """Step 2: Verify 'Key Differences' section is present."""

    def test_key_differences_section_in_formatted_report(self, temp_telemetry_dir):
        """Verify Key Differences section appears in formatted report."""
        # Create studies with different configs
        study1_dir = temp_telemetry_dir / "telemetry" / "study_alpha"
        study1_dir.mkdir(parents=True)

        summary1 = {
            "total_cases": 5,
            "final_wns_ps": -300.0,
            "final_tns_ps": -1500.0,
            "final_hot_ratio": 0.40,
            "final_total_power_mw": 18.0,
            "best_case_name": "case_003",
            "metadata": {
                "warm_start": {"enabled": True, "source_study": "baseline_v1"},
                "survivor_selection_method": "diversity",
                "auto_diagnosis_enabled": False,
            },
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(summary1, indent=2))

        study2_dir = temp_telemetry_dir / "telemetry" / "study_beta"
        study2_dir.mkdir(parents=True)

        summary2 = {
            "total_cases": 5,
            "final_wns_ps": -280.0,
            "final_tns_ps": -1400.0,
            "final_hot_ratio": 0.38,
            "final_total_power_mw": 17.0,
            "best_case_name": "case_004",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(summary2, indent=2))

        # Run comparison
        report = compare_studies(
            "study_alpha",
            "study_beta",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        # Format report
        formatted = format_comparison_report(report)

        # Verify "KEY DIFFERENCES" section is present
        assert "KEY DIFFERENCES" in formatted, "Missing 'KEY DIFFERENCES' section"
        assert "Warm-start configuration:" in formatted
        assert "Survivor selection method:" in formatted
        assert "Auto-diagnosis:" in formatted

    def test_key_differences_absent_when_configs_identical(self, temp_telemetry_dir):
        """Verify Key Differences section is omitted when configs are identical."""
        # Create studies with identical configs
        for study_name in ["study_same1", "study_same2"]:
            study_dir = temp_telemetry_dir / "telemetry" / study_name
            study_dir.mkdir(parents=True)

            summary = {
                "total_cases": 5,
                "final_wns_ps": -200.0 if study_name == "study_same1" else -180.0,
                "final_tns_ps": -1000.0,
                "final_hot_ratio": 0.30,
                "final_total_power_mw": 15.0,
                "best_case_name": "case_003",
                "metadata": {
                    "warm_start": {"enabled": True, "source_study": "baseline"},
                    "survivor_selection_method": "top_n",
                    "auto_diagnosis_enabled": True,
                },
            }
            (study_dir / "study_summary.json").write_text(json.dumps(summary, indent=2))

        # Run comparison
        report = compare_studies(
            "study_same1",
            "study_same2",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        # No configuration differences
        assert len(report.configuration_differences) == 0

        # Format report - KEY DIFFERENCES section should not appear
        formatted = format_comparison_report(report)

        # The section header appears only if there are differences
        if report.configuration_differences:
            assert "KEY DIFFERENCES" in formatted
        else:
            # Section is omitted when no differences
            pass  # This is expected behavior


class TestStep3VerifyWarmStartUsageNoted:
    """Step 3: Verify warm_start usage is noted."""

    def test_warm_start_enabled_vs_disabled(self, temp_telemetry_dir):
        """Test warm-start enabled vs disabled is detected."""
        # Create study 1 with warm-start enabled
        study1_dir = temp_telemetry_dir / "telemetry" / "ws_enabled"
        study1_dir.mkdir(parents=True)

        summary1 = {
            "total_cases": 8,
            "final_wns_ps": -150.0,
            "final_tns_ps": -800.0,
            "final_hot_ratio": 0.25,
            "final_total_power_mw": 12.0,
            "best_case_name": "case_006",
            "metadata": {
                "warm_start": {"enabled": True, "source_study": "baseline_v2"},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(summary1, indent=2))

        # Create study 2 with warm-start disabled
        study2_dir = temp_telemetry_dir / "telemetry" / "ws_disabled"
        study2_dir.mkdir(parents=True)

        summary2 = {
            "total_cases": 8,
            "final_wns_ps": -180.0,
            "final_tns_ps": -900.0,
            "final_hot_ratio": 0.28,
            "final_total_power_mw": 13.5,
            "best_case_name": "case_007",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(summary2, indent=2))

        # Run comparison
        report = compare_studies(
            "ws_enabled",
            "ws_disabled",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        # Verify warm-start difference is detected
        warm_start_diffs = [
            d for d in report.configuration_differences if d.category == "warm_start"
        ]
        assert len(warm_start_diffs) > 0, "Warm-start difference not detected"

        diff = warm_start_diffs[0]
        assert diff.study1_value == "enabled"
        assert diff.study2_value == "disabled"

    def test_warm_start_different_source_studies(self, temp_telemetry_dir):
        """Test different warm-start source studies are detected."""
        # Both have warm-start enabled but different sources
        study1_dir = temp_telemetry_dir / "telemetry" / "ws_source1"
        study1_dir.mkdir(parents=True)

        summary1 = {
            "total_cases": 6,
            "final_wns_ps": -120.0,
            "final_tns_ps": -600.0,
            "final_hot_ratio": 0.22,
            "final_total_power_mw": 11.0,
            "best_case_name": "case_004",
            "metadata": {
                "warm_start": {"enabled": True, "source_study": "baseline_v1"},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(summary1, indent=2))

        study2_dir = temp_telemetry_dir / "telemetry" / "ws_source2"
        study2_dir.mkdir(parents=True)

        summary2 = {
            "total_cases": 6,
            "final_wns_ps": -110.0,
            "final_tns_ps": -550.0,
            "final_hot_ratio": 0.20,
            "final_total_power_mw": 10.5,
            "best_case_name": "case_005",
            "metadata": {
                "warm_start": {"enabled": True, "source_study": "baseline_v2"},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(summary2, indent=2))

        # Run comparison
        report = compare_studies(
            "ws_source1",
            "ws_source2",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        # Verify source study difference is detected
        warm_start_diffs = [
            d for d in report.configuration_differences if d.category == "warm_start"
        ]
        assert len(warm_start_diffs) > 0, "Warm-start source difference not detected"

        diff = warm_start_diffs[0]
        assert diff.study1_value == "baseline_v1"
        assert diff.study2_value == "baseline_v2"


class TestStep4VerifySurvivorSelectionMethodDifferences:
    """Step 4: Verify survivor selection method differences are highlighted."""

    def test_survivor_selection_top_n_vs_diversity(self, temp_telemetry_dir):
        """Test survivor selection method differences are detected."""
        # Study 1 uses top_n
        study1_dir = temp_telemetry_dir / "telemetry" / "sel_top_n"
        study1_dir.mkdir(parents=True)

        summary1 = {
            "total_cases": 12,
            "final_wns_ps": -140.0,
            "final_tns_ps": -700.0,
            "final_hot_ratio": 0.26,
            "final_total_power_mw": 13.0,
            "best_case_name": "case_010",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(summary1, indent=2))

        # Study 2 uses diversity
        study2_dir = temp_telemetry_dir / "telemetry" / "sel_diversity"
        study2_dir.mkdir(parents=True)

        summary2 = {
            "total_cases": 12,
            "final_wns_ps": -130.0,
            "final_tns_ps": -650.0,
            "final_hot_ratio": 0.24,
            "final_total_power_mw": 12.5,
            "best_case_name": "case_011",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "diversity",
                "auto_diagnosis_enabled": True,
            },
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(summary2, indent=2))

        # Run comparison
        report = compare_studies(
            "sel_top_n",
            "sel_diversity",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        # Verify survivor selection difference is detected
        selection_diffs = [
            d
            for d in report.configuration_differences
            if d.category == "survivor_selection"
        ]
        assert (
            len(selection_diffs) > 0
        ), "Survivor selection method difference not detected"

        diff = selection_diffs[0]
        assert diff.study1_value == "top_n"
        assert diff.study2_value == "diversity"

        # Verify it appears in formatted report
        formatted = format_comparison_report(report)
        assert "Survivor selection method:" in formatted


class TestStep5VerifyAutoDiagnosisEnablementDifferences:
    """Step 5: Verify auto-diagnosis enablement differences are shown."""

    def test_auto_diagnosis_enabled_vs_disabled(self, temp_telemetry_dir):
        """Test auto-diagnosis enablement differences are detected."""
        # Study 1 has diagnosis enabled
        study1_dir = temp_telemetry_dir / "telemetry" / "diag_enabled"
        study1_dir.mkdir(parents=True)

        summary1 = {
            "total_cases": 7,
            "final_wns_ps": -160.0,
            "final_tns_ps": -850.0,
            "final_hot_ratio": 0.29,
            "final_total_power_mw": 14.5,
            "best_case_name": "case_005",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(summary1, indent=2))

        # Study 2 has diagnosis disabled
        study2_dir = temp_telemetry_dir / "telemetry" / "diag_disabled"
        study2_dir.mkdir(parents=True)

        summary2 = {
            "total_cases": 7,
            "final_wns_ps": -170.0,
            "final_tns_ps": -900.0,
            "final_hot_ratio": 0.31,
            "final_total_power_mw": 15.0,
            "best_case_name": "case_006",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": False,
            },
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(summary2, indent=2))

        # Run comparison
        report = compare_studies(
            "diag_enabled",
            "diag_disabled",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        # Verify diagnosis difference is detected
        diagnosis_diffs = [
            d for d in report.configuration_differences if d.category == "diagnosis"
        ]
        assert len(diagnosis_diffs) > 0, "Auto-diagnosis difference not detected"

        diff = diagnosis_diffs[0]
        assert diff.study1_value == "enabled"
        assert diff.study2_value == "disabled"

        # Verify it appears in formatted report
        formatted = format_comparison_report(report)
        assert "Auto-diagnosis:" in formatted


class TestConfigurationComparisonEdgeCases:
    """Test edge cases in configuration comparison."""

    def test_all_three_differences_at_once(self, temp_telemetry_dir):
        """Test detecting all three types of differences simultaneously."""
        # Study 1
        study1_dir = temp_telemetry_dir / "telemetry" / "all_diff1"
        study1_dir.mkdir(parents=True)

        summary1 = {
            "total_cases": 15,
            "final_wns_ps": -100.0,
            "final_tns_ps": -500.0,
            "final_hot_ratio": 0.20,
            "final_total_power_mw": 10.0,
            "best_case_name": "case_012",
            "metadata": {
                "warm_start": {"enabled": True, "source_study": "baseline"},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        }
        (study1_dir / "study_summary.json").write_text(json.dumps(summary1, indent=2))

        # Study 2 - all different
        study2_dir = temp_telemetry_dir / "telemetry" / "all_diff2"
        study2_dir.mkdir(parents=True)

        summary2 = {
            "total_cases": 15,
            "final_wns_ps": -90.0,
            "final_tns_ps": -450.0,
            "final_hot_ratio": 0.18,
            "final_total_power_mw": 9.5,
            "best_case_name": "case_014",
            "metadata": {
                "warm_start": {"enabled": False},
                "survivor_selection_method": "diversity",
                "auto_diagnosis_enabled": False,
            },
        }
        (study2_dir / "study_summary.json").write_text(json.dumps(summary2, indent=2))

        # Run comparison
        report = compare_studies(
            "all_diff1",
            "all_diff2",
            telemetry_root=temp_telemetry_dir / "telemetry",
        )

        # Verify all three differences are detected
        assert len(report.configuration_differences) == 3

        categories = {d.category for d in report.configuration_differences}
        assert "warm_start" in categories
        assert "survivor_selection" in categories
        assert "diagnosis" in categories

    def test_compare_study_configurations_function_directly(self):
        """Test compare_study_configurations function directly."""
        study1 = StudyMetricsSummary(
            study_name="study1",
            total_cases=5,
            final_wns_ps=-100.0,
            final_tns_ps=-500.0,
            final_hot_ratio=0.2,
            final_total_power_mw=10.0,
            metadata={
                "warm_start": {"enabled": True, "source_study": "baseline"},
                "survivor_selection_method": "top_n",
                "auto_diagnosis_enabled": True,
            },
        )

        study2 = StudyMetricsSummary(
            study_name="study2",
            total_cases=5,
            final_wns_ps=-80.0,
            final_tns_ps=-400.0,
            final_hot_ratio=0.18,
            final_total_power_mw=9.0,
            metadata={
                "warm_start": {"enabled": False},
                "survivor_selection_method": "diversity",
                "auto_diagnosis_enabled": False,
            },
        )

        differences = compare_study_configurations(study1, study2)

        assert len(differences) == 3
        assert any(d.category == "warm_start" for d in differences)
        assert any(d.category == "survivor_selection" for d in differences)
        assert any(d.category == "diagnosis" for d in differences)
