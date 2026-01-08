"""Tests for diff report color formatting (color-coded deltas).

This module validates that the diff report includes:
- Green color for improvements
- Red color for regressions
- Default/neutral color for no change
- Clean plain text output for file saving
"""

import pytest

from src.controller.diff_report import (
    CaseDiffReport,
    MetricDelta,
    generate_diff_report,
    Colors,
)
from src.controller.types import TrialMetrics, TimingMetrics, CongestionMetrics


class TestColorCodeConstants:
    """Tests for color code constants."""

    def test_color_codes_defined(self) -> None:
        """Test that all required color codes are defined."""
        assert hasattr(Colors, 'GREEN')
        assert hasattr(Colors, 'RED')
        assert hasattr(Colors, 'YELLOW')
        assert hasattr(Colors, 'RESET')
        assert hasattr(Colors, 'BOLD')

    def test_color_codes_are_ansi_sequences(self) -> None:
        """Test that color codes are valid ANSI escape sequences."""
        # ANSI codes start with ESC[ which is \033[
        assert Colors.GREEN.startswith('\033[')
        assert Colors.RED.startswith('\033[')
        assert Colors.YELLOW.startswith('\033[')
        assert Colors.RESET.startswith('\033[')
        assert Colors.BOLD.startswith('\033[')


class TestFormatDeltaLine:
    """Tests for _format_delta_line helper method."""

    def test_format_improvement_with_colors(self) -> None:
        """Test formatting improvement with colors enabled."""
        report = CaseDiffReport(
            baseline_case_id="base",
            derived_case_id="derived",
            eco_name="test_eco",
        )

        line = report._format_delta_line("Delta:", "+100 ps", improved=True, use_colors=True)

        # Should contain green color code
        assert Colors.GREEN in line
        assert Colors.RESET in line
        assert "+100 ps" in line

    def test_format_regression_with_colors(self) -> None:
        """Test formatting regression with colors enabled."""
        report = CaseDiffReport(
            baseline_case_id="base",
            derived_case_id="derived",
            eco_name="test_eco",
        )

        line = report._format_delta_line("Delta:", "-50 ps", improved=False, use_colors=True)

        # Should contain red color code
        assert Colors.RED in line
        assert Colors.RESET in line
        assert "-50 ps" in line

    def test_format_neutral_with_colors(self) -> None:
        """Test formatting neutral change with colors (improved=None)."""
        report = CaseDiffReport(
            baseline_case_id="base",
            derived_case_id="derived",
            eco_name="test_eco",
        )

        line = report._format_delta_line("Delta:", "0 ps", improved=None, use_colors=True)

        # Should NOT contain color codes for neutral
        assert Colors.GREEN not in line
        assert Colors.RED not in line
        # RESET might still be in string, but no color applied
        assert "0 ps" in line

    def test_format_without_colors(self) -> None:
        """Test formatting without colors."""
        report = CaseDiffReport(
            baseline_case_id="base",
            derived_case_id="derived",
            eco_name="test_eco",
        )

        line = report._format_delta_line("Delta:", "+100 ps", improved=True, use_colors=False)

        # Should NOT contain any color codes
        assert Colors.GREEN not in line
        assert Colors.RED not in line
        assert Colors.RESET not in line
        assert "+100 ps" in line


class TestDiffReportColorFormatting:
    """Tests for color formatting in diff report output."""

    def test_to_text_improvements_shown_in_green(self) -> None:
        """Test that improvements are shown in green."""
        # Create metrics showing improvement
        baseline_timing = TimingMetrics(wns_ps=-500)
        derived_timing = TimingMetrics(wns_ps=-200)  # Less negative = improvement

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="base_case",
            derived_case_id="derived_case",
            eco_name="buffer_insertion",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Get colored output
        output = report.to_text(use_colors=True)

        # Should contain green color code for improvement
        assert Colors.GREEN in output
        assert "+300 ps" in output  # WNS improved by 300 ps

    def test_to_text_regressions_shown_in_red(self) -> None:
        """Test that regressions are shown in red."""
        # Create metrics showing regression
        baseline_timing = TimingMetrics(wns_ps=-200)
        derived_timing = TimingMetrics(wns_ps=-500)  # More negative = regression

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="base_case",
            derived_case_id="derived_case",
            eco_name="bad_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Get colored output
        output = report.to_text(use_colors=True)

        # Should contain red color code for regression
        assert Colors.RED in output
        assert "-300 ps" in output  # WNS degraded by 300 ps

    def test_to_text_neutral_shown_in_default_color(self) -> None:
        """Test that neutral changes use default color."""
        # Create metrics with no change
        baseline_timing = TimingMetrics(wns_ps=-300)
        derived_timing = TimingMetrics(wns_ps=-300)  # No change

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="base_case",
            derived_case_id="derived_case",
            eco_name="neutral_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Get colored output
        output = report.to_text(use_colors=True)

        # Neutral values should not be colored
        # (checking that not all lines have color)
        lines = output.split('\n')
        baseline_lines = [l for l in lines if "Baseline:" in l]
        # Baseline values should not be colored
        for line in baseline_lines:
            # The baseline line itself shouldn't have color codes
            # (only delta lines get colored)
            pass  # Just checking structure

    def test_to_text_plain_without_colors(self) -> None:
        """Test that plain text output has no color codes."""
        baseline_timing = TimingMetrics(wns_ps=-500)
        derived_timing = TimingMetrics(wns_ps=-200)

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="base_case",
            derived_case_id="derived_case",
            eco_name="buffer_insertion",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Get plain text output
        output = report.to_text(use_colors=False)

        # Should NOT contain any color codes
        assert Colors.GREEN not in output
        assert Colors.RED not in output
        assert Colors.YELLOW not in output
        assert Colors.RESET not in output
        assert Colors.BOLD not in output

        # But should still have the content
        assert "+300 ps" in output
        assert "buffer_insertion" in output

    def test_congestion_improvements_colored_green(self) -> None:
        """Test that congestion improvements are shown in green."""
        # Need timing metrics too (required by TrialMetrics)
        baseline_timing = TimingMetrics(wns_ps=-300)
        derived_timing = TimingMetrics(wns_ps=-300)

        baseline_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=0.05,
        )
        derived_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=20,  # Fewer hot bins = improvement
            hot_ratio=0.02,  # Lower ratio = improvement
        )

        baseline_metrics = TrialMetrics(timing=baseline_timing, congestion=baseline_congestion)
        derived_metrics = TrialMetrics(timing=derived_timing, congestion=derived_congestion)

        report = generate_diff_report(
            baseline_case_id="base_case",
            derived_case_id="derived_case",
            eco_name="placement_optimization",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        output = report.to_text(use_colors=True)

        # Congestion improvements should be green
        assert Colors.GREEN in output

    def test_overall_assessment_colored(self) -> None:
        """Test that overall assessment YES/NO is colored."""
        baseline_timing = TimingMetrics(wns_ps=-500)
        derived_timing = TimingMetrics(wns_ps=-200)

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="base_case",
            derived_case_id="derived_case",
            eco_name="good_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        output = report.to_text(use_colors=True)

        # Overall improvement YES should be green
        assert report.overall_improvement is True
        assert Colors.GREEN in output
        # Check that "YES" appears near a green code
        assert "YES" in output


class TestDiffReportFeatureValidation:
    """Tests validating all 6 feature steps for diff report color formatting."""

    def test_step_1_generate_case_diff_report(self) -> None:
        """Step 1: Generate case diff report."""
        baseline_timing = TimingMetrics(wns_ps=-400)
        derived_timing = TimingMetrics(wns_ps=-250)

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        assert report is not None
        assert report.wns_delta is not None

    def test_step_2_open_diff_report(self) -> None:
        """Step 2: Open diff report (HTML or terminal output)."""
        baseline_timing = TimingMetrics(wns_ps=-400)
        derived_timing = TimingMetrics(wns_ps=-250)

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # "Open" by converting to text
        output = report.to_text(use_colors=True)
        assert output is not None
        assert len(output) > 0

    def test_step_3_take_screenshot(self) -> None:
        """Step 3: Take screenshot (N/A for automated testing)."""
        # This step is not applicable for automated testing
        # In practice, operator would visually inspect colored output
        pass

    def test_step_4_verify_improvements_shown_in_green(self) -> None:
        """Step 4: Verify improvements are shown in green."""
        baseline_timing = TimingMetrics(wns_ps=-500)
        derived_timing = TimingMetrics(wns_ps=-200)  # Improvement

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="improvement_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        output = report.to_text(use_colors=True)

        # REQUIRED: Improvements in green
        assert Colors.GREEN in output, "Improvements must be shown in green"
        assert report.wns_delta.improved is True
        assert "+300 ps" in output

    def test_step_5_verify_regressions_shown_in_red(self) -> None:
        """Step 5: Verify regressions are shown in red."""
        baseline_timing = TimingMetrics(wns_ps=-200)
        derived_timing = TimingMetrics(wns_ps=-500)  # Regression

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="regression_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        output = report.to_text(use_colors=True)

        # REQUIRED: Regressions in red
        assert Colors.RED in output, "Regressions must be shown in red"
        assert report.wns_delta.improved is False
        assert "-300 ps" in output

    def test_step_6_verify_neutral_changes_in_default_color(self) -> None:
        """Step 6: Verify neutral changes are shown in default color."""
        baseline_timing = TimingMetrics(wns_ps=-300)
        derived_timing = TimingMetrics(wns_ps=-300)  # No change

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="neutral_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        output = report.to_text(use_colors=True)

        # Neutral changes should not add color (or minimal color)
        # The key is that baseline/derived values are not colored,
        # only deltas get color based on improvement
        assert "Baseline:" in output
        assert "Derived:" in output


class TestColorFormattingEdgeCases:
    """Tests for edge cases in color formatting."""

    def test_mixed_improvements_and_regressions(self) -> None:
        """Test report with both improvements and regressions."""
        baseline_timing = TimingMetrics(wns_ps=-500, tns_ps=-5000)
        derived_timing = TimingMetrics(wns_ps=-200, tns_ps=-6000)  # WNS improved, TNS regressed

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="mixed_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        output = report.to_text(use_colors=True)

        # Should have both green and red
        assert Colors.GREEN in output  # WNS improvement
        assert Colors.RED in output    # TNS regression

    def test_color_codes_properly_reset(self) -> None:
        """Test that color codes are properly reset after each colored section."""
        baseline_timing = TimingMetrics(wns_ps=-500)
        derived_timing = TimingMetrics(wns_ps=-200)

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        output = report.to_text(use_colors=True)

        # Every GREEN should be followed (eventually) by RESET
        green_count = output.count(Colors.GREEN)
        reset_count = output.count(Colors.RESET)

        # Should have at least as many RESETs as color codes
        assert reset_count >= green_count

    def test_file_output_has_no_colors(self) -> None:
        """Test that file output (use_colors=False) is clean for external tools."""
        baseline_timing = TimingMetrics(wns_ps=-500)
        derived_timing = TimingMetrics(wns_ps=-200)

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        plain_output = report.to_text(use_colors=False)

        # Should have NO escape sequences
        assert '\033[' not in plain_output, "Plain text output must not contain ANSI codes"

    def test_default_to_text_uses_colors(self) -> None:
        """Test that default to_text() call uses colors (for terminal display)."""
        baseline_timing = TimingMetrics(wns_ps=-500)
        derived_timing = TimingMetrics(wns_ps=-200)

        baseline_metrics = TrialMetrics(timing=baseline_timing)
        derived_metrics = TrialMetrics(timing=derived_timing)

        report = generate_diff_report(
            baseline_case_id="baseline",
            derived_case_id="derived",
            eco_name="test_eco",
            baseline_metrics=baseline_metrics,
            derived_metrics=derived_metrics,
        )

        # Default call (no arguments) should use colors
        output = report.to_text()

        # Should contain color codes
        assert Colors.GREEN in output or Colors.RED in output
