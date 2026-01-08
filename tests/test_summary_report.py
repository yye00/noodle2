"""Tests for human-readable summary report generation."""

import time
from pathlib import Path

import pytest

from src.controller import (
    CaseTelemetry,
    StageTelemetry,
    StudyTelemetry,
    SummaryReportConfig,
    SummaryReportGenerator,
)


class TestSummaryReportGeneration:
    """Test suite for summary report generation."""

    def test_summary_report_generator_initialization(self) -> None:
        """Test that SummaryReportGenerator initializes with default config."""
        generator = SummaryReportGenerator()
        assert generator.config is not None
        assert generator.config.include_top_cases == 5
        assert generator.config.include_stage_details is True
        assert generator.config.include_failure_analysis is True

    def test_summary_report_generator_with_custom_config(self) -> None:
        """Test that SummaryReportGenerator accepts custom config."""
        config = SummaryReportConfig(
            include_top_cases=10,
            include_stage_details=False,
            include_failure_analysis=False,
        )
        generator = SummaryReportGenerator(config)
        assert generator.config.include_top_cases == 10
        assert generator.config.include_stage_details is False
        assert generator.config.include_failure_analysis is False

    def test_generate_study_summary_has_header(self) -> None:
        """Test that summary report has proper header."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )
        study_telemetry.finalize(final_survivors=[], aborted=False)

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], [])

        assert "STUDY SUMMARY REPORT: test_study" in report
        assert "=" * 80 in report
        assert "STUDY OVERVIEW" in report

    def test_generate_study_summary_includes_safety_domain(self) -> None:
        """Test that summary includes safety domain information."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="guarded",
            total_stages=2,
        )
        study_telemetry.finalize(final_survivors=[], aborted=False)

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], [])

        assert "Safety Domain:   GUARDED" in report

    def test_generate_study_summary_shows_trial_statistics(self) -> None:
        """Test that summary includes trial statistics."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
            total_trials=20,
            successful_trials=15,
            failed_trials=5,
        )
        study_telemetry.finalize(final_survivors=[], aborted=False)

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], [])

        assert "TRIAL STATISTICS" in report
        assert "Total Trials:       20" in report
        assert "Successful Trials:  15" in report
        assert "Failed Trials:      5" in report
        assert "Success Rate:       75.0%" in report

    def test_generate_study_summary_shows_runtime_statistics(self) -> None:
        """Test that summary includes runtime statistics."""
        start_time = time.time()
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
            total_trials=10,
            total_runtime_seconds=120.5,
            start_time=start_time,
        )
        study_telemetry.finalize(final_survivors=[], aborted=False)

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], [])

        assert "RUNTIME STATISTICS" in report
        assert "Total Trial Time:" in report
        assert "Avg Trial Time:" in report

    def test_generate_study_summary_shows_final_survivors(self) -> None:
        """Test that summary lists final survivors."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )
        final_survivors = ["case_0_0_0", "case_0_0_1", "case_0_0_2"]
        study_telemetry.finalize(final_survivors=final_survivors, aborted=False)

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], [])

        assert "FINAL SURVIVORS" in report
        assert "1. case_0_0_0" in report
        assert "2. case_0_0_1" in report
        assert "3. case_0_0_2" in report

    def test_generate_study_summary_shows_aborted_status(self) -> None:
        """Test that summary shows ABORTED status when applicable."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="guarded",
            total_stages=3,
            stages_completed=1,
        )
        study_telemetry.finalize(
            final_survivors=[],
            aborted=True,
            abort_reason="Stage 1 aborted: no_survivors",
        )

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], [])

        assert "Status:          ABORTED (Stage 1 aborted: no_survivors)" in report

    def test_generate_study_summary_shows_completed_status(self) -> None:
        """Test that summary shows COMPLETED status when all stages finish."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=3,
            stages_completed=3,
        )
        study_telemetry.finalize(final_survivors=["case_2_0_0"], aborted=False)

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], [])

        assert "Status:          COMPLETED" in report


class TestStageDetailsSummary:
    """Test suite for per-stage summary section."""

    def test_generate_stage_summaries_includes_all_stages(self) -> None:
        """Test that stage summaries include all provided stages."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="exploration",
                trial_budget=20,
                survivor_count=5,
                trials_executed=20,
                successful_trials=18,
                failed_trials=2,
                total_runtime_seconds=60.0,
            ),
            StageTelemetry(
                stage_index=1,
                stage_name="refinement",
                trial_budget=10,
                survivor_count=2,
                trials_executed=10,
                successful_trials=10,
                failed_trials=0,
                total_runtime_seconds=30.0,
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        assert "STAGE SUMMARIES" in report
        assert "Stage 0: exploration" in report
        assert "Stage 1: refinement" in report

    def test_stage_summary_includes_trial_statistics(self) -> None:
        """Test that stage summary includes trial execution statistics."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="baseline",
                trial_budget=15,
                survivor_count=3,
                trials_executed=15,
                successful_trials=12,
                failed_trials=3,
                total_runtime_seconds=45.0,
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        assert "Trial Budget:       15" in report
        assert "Trials Executed:    15" in report
        assert "Successful Trials:  12" in report
        assert "Failed Trials:      3" in report
        assert "Success Rate:       80.0%" in report

    def test_stage_summary_includes_failure_types(self) -> None:
        """Test that stage summary lists failure type breakdown."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="baseline",
                trial_budget=10,
                survivor_count=2,
                trials_executed=10,
                successful_trials=7,
                failed_trials=3,
                total_runtime_seconds=30.0,
                failure_types={
                    "tool_crash": 2,
                    "parse_error": 1,
                },
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        assert "Failure Types:" in report
        assert "- tool_crash: 2" in report
        assert "- parse_error: 1" in report

    def test_stage_summary_can_be_disabled(self) -> None:
        """Test that stage details can be excluded from summary."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="baseline",
                trial_budget=10,
                survivor_count=2,
            ),
        ]

        config = SummaryReportConfig(include_stage_details=False)
        generator = SummaryReportGenerator(config)
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        assert "STAGE SUMMARIES" not in report


class TestTopCasesSummary:
    """Test suite for top-performing cases section."""

    def test_top_cases_sorted_by_wns(self) -> None:
        """Test that top cases are sorted by best WNS (higher is better)."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        case_telemetries = [
            CaseTelemetry(
                case_id="case_1",
                base_case="base",
                stage_index=0,
                derived_index=0,
                best_wns_ps=-500,  # Worse
                total_trials=5,
                successful_trials=5,
            ),
            CaseTelemetry(
                case_id="case_2",
                base_case="base",
                stage_index=0,
                derived_index=1,
                best_wns_ps=1000,  # Best
                total_trials=5,
                successful_trials=5,
            ),
            CaseTelemetry(
                case_id="case_3",
                base_case="base",
                stage_index=0,
                derived_index=2,
                best_wns_ps=200,  # Middle
                total_trials=5,
                successful_trials=5,
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], case_telemetries)

        assert "TOP-PERFORMING CASES" in report
        # Check ordering: case_2 (1000), case_3 (200), case_1 (-500)
        lines = report.split("\n")
        case2_line = next(i for i, line in enumerate(lines) if "case_2" in line)
        case3_line = next(i for i, line in enumerate(lines) if "case_3" in line)
        case1_line = next(i for i, line in enumerate(lines) if "case_1" in line)
        assert case2_line < case3_line < case1_line

    def test_top_cases_respects_limit(self) -> None:
        """Test that only top N cases are shown based on config."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        # Create 10 cases
        case_telemetries = [
            CaseTelemetry(
                case_id=f"case_{i}",
                base_case="base",
                stage_index=0,
                derived_index=i,
                best_wns_ps=i * 100,
                total_trials=5,
                successful_trials=5,
            )
            for i in range(10)
        ]

        config = SummaryReportConfig(include_top_cases=3)
        generator = SummaryReportGenerator(config)
        report = generator.generate_study_summary(study_telemetry, [], case_telemetries)

        # Should only show top 3 (case_9, case_8, case_7)
        assert "case_9" in report
        assert "case_8" in report
        assert "case_7" in report
        assert "case_0" not in report
        assert "case_1" not in report

    def test_top_cases_shows_wns_and_tns(self) -> None:
        """Test that top cases show both WNS and TNS when available."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        case_telemetries = [
            CaseTelemetry(
                case_id="case_1",
                base_case="base",
                stage_index=0,
                derived_index=0,
                best_wns_ps=1000,
                best_tns_ps=-5000,
                total_trials=5,
                successful_trials=5,
                total_runtime_seconds=25.0,
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], case_telemetries)

        assert "Best WNS:         1,000 ps" in report
        assert "Best TNS:         -5,000 ps" in report

    def test_top_cases_shows_success_rate(self) -> None:
        """Test that top cases show trial success rate."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        case_telemetries = [
            CaseTelemetry(
                case_id="case_1",
                base_case="base",
                stage_index=0,
                derived_index=0,
                best_wns_ps=500,
                total_trials=10,
                successful_trials=8,
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], case_telemetries)

        assert "Total Trials:     10" in report
        assert "Successful:       8" in report
        assert "Success Rate:     80.0%" in report

    def test_top_cases_handles_no_wns_data(self) -> None:
        """Test that top cases section handles cases without WNS data."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        case_telemetries = [
            CaseTelemetry(
                case_id="case_1",
                base_case="base",
                stage_index=0,
                derived_index=0,
                best_wns_ps=None,  # No WNS data
                total_trials=5,
                successful_trials=0,
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, [], case_telemetries)

        assert "TOP-PERFORMING CASES" in report
        assert "No cases with WNS data available" in report


class TestFailureAnalysisSummary:
    """Test suite for failure analysis section."""

    def test_failure_analysis_aggregates_across_stages(self) -> None:
        """Test that failure analysis aggregates failure types across all stages."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="exploration",
                trial_budget=10,
                survivor_count=5,
                failure_types={
                    "tool_crash": 2,
                    "parse_error": 1,
                },
            ),
            StageTelemetry(
                stage_index=1,
                stage_name="refinement",
                trial_budget=5,
                survivor_count=2,
                failure_types={
                    "tool_crash": 1,
                    "timeout": 2,
                },
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        assert "FAILURE ANALYSIS" in report
        assert "Total Failures: 6" in report
        # tool_crash: 3 (2+1), parse_error: 1, timeout: 2
        assert "tool_crash" in report
        assert "parse_error" in report
        assert "timeout" in report

    def test_failure_analysis_shows_percentages(self) -> None:
        """Test that failure analysis shows percentage breakdown."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="baseline",
                trial_budget=10,
                survivor_count=5,
                failure_types={
                    "tool_crash": 8,
                    "parse_error": 2,
                },
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        # 8/10 = 80%, 2/10 = 20%
        assert "tool_crash" in report
        assert "80.0%" in report
        assert "parse_error" in report
        assert "20.0%" in report

    def test_failure_analysis_sorted_by_count(self) -> None:
        """Test that failure types are sorted by count (descending)."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="baseline",
                trial_budget=10,
                survivor_count=5,
                failure_types={
                    "rare_error": 1,
                    "common_error": 5,
                    "medium_error": 3,
                },
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        lines = report.split("\n")
        common_line = next(i for i, line in enumerate(lines) if "common_error" in line)
        medium_line = next(i for i, line in enumerate(lines) if "medium_error" in line)
        rare_line = next(i for i, line in enumerate(lines) if "rare_error" in line)
        assert common_line < medium_line < rare_line

    def test_failure_analysis_handles_no_failures(self) -> None:
        """Test that failure analysis handles case with no failures."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="baseline",
                trial_budget=10,
                survivor_count=5,
                failure_types={},  # No failures
            ),
        ]

        generator = SummaryReportGenerator()
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        assert "FAILURE ANALYSIS" in report
        assert "No failures recorded" in report

    def test_failure_analysis_can_be_disabled(self) -> None:
        """Test that failure analysis can be excluded from summary."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )

        stage_telemetries = [
            StageTelemetry(
                stage_index=0,
                stage_name="baseline",
                trial_budget=10,
                survivor_count=5,
                failure_types={"error": 2},
            ),
        ]

        config = SummaryReportConfig(include_failure_analysis=False)
        generator = SummaryReportGenerator(config)
        report = generator.generate_study_summary(study_telemetry, stage_telemetries, [])

        assert "FAILURE ANALYSIS" not in report


class TestDurationFormatting:
    """Test suite for duration formatting helper."""

    def test_format_duration_seconds(self) -> None:
        """Test formatting of short durations (< 1 minute)."""
        generator = SummaryReportGenerator()
        assert generator._format_duration(5.7) == "5.7s"
        assert generator._format_duration(45.0) == "45.0s"

    def test_format_duration_minutes(self) -> None:
        """Test formatting of medium durations (minutes)."""
        generator = SummaryReportGenerator()
        assert generator._format_duration(90.0) == "1m 30s"
        assert generator._format_duration(125.5) == "2m 6s"

    def test_format_duration_hours(self) -> None:
        """Test formatting of long durations (hours)."""
        generator = SummaryReportGenerator()
        assert generator._format_duration(3665.0) == "1h 1m 5s"
        assert generator._format_duration(7384.0) == "2h 3m 4s"


class TestSummaryReportFileWriting:
    """Test suite for writing summary reports to files."""

    def test_write_summary_report_creates_file(self, tmp_path: Path) -> None:
        """Test that write_summary_report creates the report file."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )
        study_telemetry.finalize(final_survivors=[], aborted=False)

        report_path = tmp_path / "summary.txt"
        generator = SummaryReportGenerator()
        result_path = generator.write_summary_report(
            report_path, study_telemetry, [], []
        )

        assert result_path == report_path
        assert report_path.exists()

    def test_write_summary_report_creates_parent_directory(self, tmp_path: Path) -> None:
        """Test that write_summary_report creates parent directories if needed."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )
        study_telemetry.finalize(final_survivors=[], aborted=False)

        report_path = tmp_path / "artifacts" / "study_name" / "summary.txt"
        generator = SummaryReportGenerator()
        result_path = generator.write_summary_report(
            report_path, study_telemetry, [], []
        )

        assert result_path == report_path
        assert report_path.exists()

    def test_write_summary_report_content_matches_generate(self, tmp_path: Path) -> None:
        """Test that written file content matches generate_study_summary output."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="guarded",
            total_stages=1,
            total_trials=10,
            successful_trials=8,
            failed_trials=2,
        )
        study_telemetry.finalize(final_survivors=["case_0"], aborted=False)

        generator = SummaryReportGenerator()
        expected_content = generator.generate_study_summary(study_telemetry, [], [])

        report_path = tmp_path / "summary.txt"
        generator.write_summary_report(report_path, study_telemetry, [], [])

        actual_content = report_path.read_text()
        assert actual_content == expected_content

    def test_summary_report_has_footer(self, tmp_path: Path) -> None:
        """Test that summary report has proper footer."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=1,
        )
        study_telemetry.finalize(final_survivors=[], aborted=False)

        report_path = tmp_path / "summary.txt"
        generator = SummaryReportGenerator()
        generator.write_summary_report(report_path, study_telemetry, [], [])

        content = report_path.read_text()
        assert "END OF REPORT" in content
        assert content.strip().endswith("=" * 80)
