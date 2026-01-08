"""Human-readable summary report generation for Noodle 2.

Generates text-based summary reports from structured telemetry data,
providing operators with quick, scannable overviews of Study execution.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .telemetry import CaseTelemetry, StageTelemetry, StudyTelemetry


@dataclass
class SummaryReportConfig:
    """Configuration for summary report generation."""

    include_top_cases: int = 5  # Number of top-performing cases to show
    include_stage_details: bool = True  # Include per-stage breakdowns
    include_failure_analysis: bool = True  # Include failure type analysis
    include_timing_details: bool = True  # Include timing metric details


class SummaryReportGenerator:
    """
    Generates human-readable summary reports from telemetry data.

    Reports are designed to be scannable and informative, suitable for
    quick review by operators after Study execution.
    """

    def __init__(self, config: SummaryReportConfig | None = None) -> None:
        """
        Initialize summary report generator.

        Args:
            config: Configuration for report generation (optional)
        """
        self.config = config or SummaryReportConfig()

    def generate_study_summary(
        self,
        study_telemetry: StudyTelemetry,
        stage_telemetries: list[StageTelemetry],
        case_telemetries: list[CaseTelemetry] | None = None,
    ) -> str:
        """
        Generate a comprehensive study summary report.

        Args:
            study_telemetry: Study-level telemetry
            stage_telemetries: List of stage telemetries
            case_telemetries: Optional list of case telemetries

        Returns:
            Human-readable text report
        """
        lines: list[str] = []

        # Header
        lines.append("=" * 80)
        lines.append(f"STUDY SUMMARY REPORT: {study_telemetry.study_name}")
        lines.append("=" * 80)
        lines.append("")

        # Study overview
        lines.extend(self._generate_study_overview(study_telemetry))
        lines.append("")

        # Stage summaries
        if self.config.include_stage_details and stage_telemetries:
            lines.extend(self._generate_stage_summaries(stage_telemetries))
            lines.append("")

        # Top-performing cases
        if case_telemetries:
            lines.extend(
                self._generate_top_cases(case_telemetries, study_telemetry.safety_domain)
            )
            lines.append("")

        # Failure analysis
        if self.config.include_failure_analysis and stage_telemetries:
            lines.extend(self._generate_failure_analysis(stage_telemetries))
            lines.append("")

        # Footer
        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)

    def _generate_study_overview(self, telemetry: StudyTelemetry) -> list[str]:
        """Generate study overview section."""
        lines: list[str] = []
        lines.append("STUDY OVERVIEW")
        lines.append("-" * 80)
        lines.append(f"Study Name:      {telemetry.study_name}")
        lines.append(f"Safety Domain:   {telemetry.safety_domain.upper()}")
        lines.append(f"Total Stages:    {telemetry.total_stages}")
        lines.append(f"Stages Completed: {telemetry.stages_completed}")

        # Status
        if telemetry.aborted:
            lines.append(f"Status:          ABORTED ({telemetry.abort_reason})")
        elif telemetry.stages_completed == telemetry.total_stages:
            lines.append("Status:          COMPLETED")
        else:
            lines.append("Status:          IN PROGRESS")

        lines.append("")

        # Trial statistics
        lines.append("TRIAL STATISTICS")
        lines.append("-" * 80)
        lines.append(f"Total Trials:       {telemetry.total_trials}")
        lines.append(f"Successful Trials:  {telemetry.successful_trials}")
        lines.append(f"Failed Trials:      {telemetry.failed_trials}")

        if telemetry.total_trials > 0:
            success_rate = (telemetry.successful_trials / telemetry.total_trials) * 100
            lines.append(f"Success Rate:       {success_rate:.1f}%")

        lines.append("")

        # Runtime statistics
        lines.append("RUNTIME STATISTICS")
        lines.append("-" * 80)

        if telemetry.end_time and telemetry.start_time:
            wall_clock = telemetry.end_time - telemetry.start_time
            lines.append(f"Wall Clock Time:    {self._format_duration(wall_clock)}")

        lines.append(f"Total Trial Time:   {self._format_duration(telemetry.total_runtime_seconds)}")

        if telemetry.total_trials > 0:
            avg_trial_time = telemetry.total_runtime_seconds / telemetry.total_trials
            lines.append(f"Avg Trial Time:     {self._format_duration(avg_trial_time)}")

        lines.append("")

        # Final survivors
        if telemetry.final_survivors:
            lines.append("FINAL SURVIVORS")
            lines.append("-" * 80)
            for i, survivor in enumerate(telemetry.final_survivors, 1):
                lines.append(f"{i}. {survivor}")
        else:
            lines.append("FINAL SURVIVORS: None")

        return lines

    def _generate_stage_summaries(self, stage_telemetries: list[StageTelemetry]) -> list[str]:
        """Generate per-stage summary section."""
        lines: list[str] = []
        lines.append("STAGE SUMMARIES")
        lines.append("=" * 80)

        for stage in stage_telemetries:
            lines.append("")
            lines.append(f"Stage {stage.stage_index}: {stage.stage_name}")
            lines.append("-" * 80)
            lines.append(f"Trial Budget:       {stage.trial_budget}")
            lines.append(f"Trials Executed:    {stage.trials_executed}")
            lines.append(f"Successful Trials:  {stage.successful_trials}")
            lines.append(f"Failed Trials:      {stage.failed_trials}")

            if stage.trials_executed > 0:
                success_rate = (stage.successful_trials / stage.trials_executed) * 100
                lines.append(f"Success Rate:       {success_rate:.1f}%")

            lines.append(f"Survivor Count:     {stage.survivor_count}")
            lines.append(f"Actual Survivors:   {len(stage.survivors)}")
            lines.append(f"Runtime:            {self._format_duration(stage.total_runtime_seconds)}")

            if stage.trials_executed > 0:
                avg_time = stage.total_runtime_seconds / stage.trials_executed
                lines.append(f"Avg Trial Time:     {self._format_duration(avg_time)}")

            # Failure types for this stage
            if stage.failure_types:
                lines.append("")
                lines.append("Failure Types:")
                for failure_type, count in sorted(
                    stage.failure_types.items(), key=lambda x: x[1], reverse=True
                ):
                    lines.append(f"  - {failure_type}: {count}")

        return lines

    def _generate_top_cases(
        self, case_telemetries: list[CaseTelemetry], safety_domain: str
    ) -> list[str]:
        """Generate top-performing cases section."""
        lines: list[str] = []
        lines.append("TOP-PERFORMING CASES")
        lines.append("=" * 80)

        # Sort by best WNS (higher is better)
        cases_with_wns = [c for c in case_telemetries if c.best_wns_ps is not None]

        if not cases_with_wns:
            lines.append("No cases with WNS data available")
            return lines

        cases_sorted = sorted(cases_with_wns, key=lambda c: c.best_wns_ps or float("-inf"), reverse=True)

        for i, case in enumerate(cases_sorted[: self.config.include_top_cases], 1):
            lines.append("")
            lines.append(f"{i}. {case.case_id}")
            lines.append(f"   Best WNS:         {case.best_wns_ps:,} ps")

            if case.best_tns_ps is not None:
                lines.append(f"   Best TNS:         {case.best_tns_ps:,} ps")

            lines.append(f"   Total Trials:     {case.total_trials}")
            lines.append(f"   Successful:       {case.successful_trials}")

            if case.total_trials > 0:
                success_rate = (case.successful_trials / case.total_trials) * 100
                lines.append(f"   Success Rate:     {success_rate:.1f}%")

            lines.append(f"   Runtime:          {self._format_duration(case.total_runtime_seconds)}")

        return lines

    def _generate_failure_analysis(self, stage_telemetries: list[StageTelemetry]) -> list[str]:
        """Generate failure analysis section."""
        lines: list[str] = []
        lines.append("FAILURE ANALYSIS")
        lines.append("=" * 80)

        # Aggregate failure types across all stages
        all_failure_types: dict[str, int] = {}
        for stage in stage_telemetries:
            for failure_type, count in stage.failure_types.items():
                all_failure_types[failure_type] = all_failure_types.get(failure_type, 0) + count

        if not all_failure_types:
            lines.append("No failures recorded")
            return lines

        total_failures = sum(all_failure_types.values())
        lines.append(f"Total Failures: {total_failures}")
        lines.append("")
        lines.append("Failure Type Breakdown:")

        # Sort by count descending
        for failure_type, count in sorted(
            all_failure_types.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / total_failures) * 100 if total_failures > 0 else 0
            lines.append(f"  {failure_type:30s} {count:5d} ({percentage:5.1f}%)")

        return lines

    def _format_duration(self, seconds: float) -> str:
        """
        Format duration in seconds to human-readable string.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted string (e.g., "1h 23m 45s")
        """
        if seconds < 60:
            return f"{seconds:.1f}s"

        minutes = int(seconds // 60)
        remaining_seconds = seconds % 60

        if minutes < 60:
            return f"{minutes}m {remaining_seconds:.0f}s"

        hours = int(minutes // 60)
        remaining_minutes = minutes % 60

        return f"{hours}h {remaining_minutes}m {remaining_seconds:.0f}s"

    def write_summary_report(
        self,
        report_path: Path,
        study_telemetry: StudyTelemetry,
        stage_telemetries: list[StageTelemetry],
        case_telemetries: list[CaseTelemetry] | None = None,
    ) -> Path:
        """
        Generate and write a summary report to file.

        Args:
            report_path: Path where the report should be written
            study_telemetry: Study-level telemetry
            stage_telemetries: List of stage telemetries
            case_telemetries: Optional list of case telemetries

        Returns:
            Path to the written report file
        """
        report_content = self.generate_study_summary(
            study_telemetry, stage_telemetries, case_telemetries
        )

        # Ensure parent directory exists
        report_path.parent.mkdir(parents=True, exist_ok=True)

        # Write report
        with report_path.open("w") as f:
            f.write(report_content)

        return report_path
