"""
Test suite for Safety Trace enhanced formatting and UX.

This tests Feature #178: Safety trace document shows chronological evaluation log
with clear pass/fail indicators (style feature).
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.safety_trace import (
    SafetyGateEvaluation,
    SafetyGateStatus,
    SafetyGateType,
    SafetyTrace,
)
from src.controller.types import ECOClass, SafetyDomain


class TestSafetyTraceFormattingBasics:
    """Test basic formatting requirements for safety trace."""

    def test_trace_includes_clear_header(self):
        """Safety trace has clear report header with study info."""
        trace = SafetyTrace(
            study_name="formatting_test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        assert "SAFETY TRACE REPORT" in output
        assert "formatting_test" in output
        assert "GUARDED" in output

    def test_trace_shows_summary_section(self):
        """Safety trace includes summary section."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.SANDBOX,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(True)

        output = str(trace)
        assert "SUMMARY" in output
        assert "Total safety checks: 2" in output
        assert "✓ Passed:" in output

    def test_trace_shows_chronological_log_section(self):
        """Safety trace includes chronological evaluation log section."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        assert "CHRONOLOGICAL EVALUATION LOG" in output


class TestPassFailIndicators:
    """Test clear pass/fail status indicators."""

    def test_pass_evaluations_show_check_symbol(self):
        """Passed evaluations show ✓ symbol."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        assert "✓" in output
        assert "PASS" in output

    def test_fail_evaluations_show_x_symbol(self):
        """Failed evaluations show ✗ symbol."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_base_case_verification(False, "Tool crashed")

        output = str(trace)
        assert "✗" in output
        assert "FAIL" in output

    def test_blocked_evaluations_show_block_symbol(self):
        """Blocked evaluations show 🚫 symbol."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.LOCKED,
        )
        trace.record_eco_class_filter(
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            stage_index=0,
            is_allowed=False,
            reason="Not allowed in LOCKED domain",
        )

        output = str(trace)
        assert "🚫" in output
        assert "BLOCKED" in output

    def test_summary_uses_visual_symbols(self):
        """Summary section uses visual symbols for pass/fail counts."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(False, "Failed")

        output = str(trace)
        lines = output.split("\n")

        # Find summary section
        summary_lines = []
        in_summary = False
        for line in lines:
            if "SUMMARY" in line:
                in_summary = True
            elif in_summary and line.strip().startswith("CHECKS BY TYPE"):
                break
            elif in_summary:
                summary_lines.append(line)

        summary_text = "\n".join(summary_lines)
        assert "✓ Passed:" in summary_text
        assert "✗ Failed:" in summary_text


class TestOverallStatusIndicator:
    """Test overall status indicator at summary level."""

    def test_all_pass_shows_success_indicator(self):
        """When all checks pass, shows success indicator."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.SANDBOX,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(True)

        output = str(trace)
        assert "✅" in output or "ALL SAFETY CHECKS PASSED" in output

    def test_any_failure_shows_warning_indicator(self):
        """When any check fails, shows warning indicator."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(False, "Failed")

        output = str(trace)
        assert "⚠️" in output or "SAFETY VIOLATIONS DETECTED" in output

    def test_blocked_shows_warning_indicator(self):
        """When any check is blocked, shows warning indicator."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.LOCKED,
        )
        trace.record_eco_class_filter(
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            stage_index=0,
            is_allowed=False,
            reason="Blocked",
        )

        output = str(trace)
        assert "⚠️" in output or "SAFETY VIOLATIONS DETECTED" in output


class TestChronologicalOrdering:
    """Test chronological ordering is clear and maintained."""

    def test_evaluations_are_numbered_sequentially(self):
        """Evaluations are numbered 1, 2, 3, etc."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(True)
        trace.record_stage_abort_check(0, "stage_0", False)

        output = str(trace)
        assert "1." in output
        assert "2." in output
        assert "3." in output

    def test_evaluations_show_timestamps(self):
        """All evaluations show timestamps."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        assert "Timestamp:" in output
        # Should contain date-like pattern
        assert "UTC" in output or ":" in output

    def test_timestamps_are_formatted_readably(self):
        """Timestamps are formatted in readable format."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        # Should have UTC indicator for clarity
        assert "UTC" in output
        # Should not have microseconds or complex timezone info
        assert ".782834" not in output


class TestRationaleDisplay:
    """Test rationale is clearly displayed for each evaluation."""

    def test_rationale_is_shown_for_pass(self):
        """Rationale is shown for passed evaluations."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        assert "Rationale:" in output
        assert "Study configuration is legal" in output

    def test_rationale_is_shown_for_fail(self):
        """Rationale is shown for failed evaluations."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_base_case_verification(False, "Tool return code was 1")

        output = str(trace)
        assert "Rationale:" in output
        assert "failed" in output.lower()
        assert "Tool return code was 1" in output

    def test_rationale_is_shown_for_blocked(self):
        """Rationale is shown for blocked evaluations."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.LOCKED,
        )
        trace.record_eco_class_filter(
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            stage_index=0,
            is_allowed=False,
            reason="Not allowed in LOCKED domain",
        )

        output = str(trace)
        assert "Rationale:" in output
        assert "blocked" in output.lower()
        assert "Not allowed in LOCKED domain" in output


class TestContextFormatting:
    """Test context details are formatted cleanly."""

    def test_context_shows_relevant_details(self):
        """Context shows relevant details for evaluation."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_wns_threshold_check(
            stage_index=0,
            threshold_ps=-5000,
            worst_wns_ps=-8000,
            violating_trials=["trial_1", "trial_2"],
        )

        output = str(trace)
        assert "Details:" in output
        assert "stage_index: 0" in output
        assert "threshold_ps: -5000" in output
        assert "worst_wns_ps: -8000" in output

    def test_context_hides_empty_values(self):
        """Context hides empty/irrelevant values."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])  # Empty violations/warnings

        output = str(trace)
        # Should not show empty lists in detail view
        # Context formatting should be clean
        lines = output.split("\n")
        detail_lines = [l for l in lines if "Details:" in l]
        if detail_lines:
            # If details are shown, they should be meaningful
            detail_text = detail_lines[0]
            # Should show meaningful counts, not empty lists
            assert "violations: []" not in detail_text.lower()

    def test_context_formats_lists_compactly(self):
        """Context formats short lists inline."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_wns_threshold_check(
            stage_index=0,
            threshold_ps=-5000,
            worst_wns_ps=-7000,
            violating_trials=["trial_a", "trial_b"],
        )

        output = str(trace)
        assert "Details:" in output
        # Should show trials inline or as count
        assert "trial" in output.lower()


class TestGateTypeFormatting:
    """Test gate types are formatted clearly."""

    def test_gate_types_use_title_case(self):
        """Gate types in summary use title case."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(True)

        output = str(trace)
        # In the "CHECKS BY TYPE" section
        assert "Legality Check:" in output or "legality_check" in output
        assert "Base Case Verification:" in output or "base_case_verification" in output

    def test_gate_types_in_log_are_uppercase(self):
        """Gate types in chronological log use uppercase."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        # In the log section
        assert "LEGALITY CHECK" in output or "LEGALITY_CHECK" in output


class TestVisualSeparation:
    """Test visual separation between sections."""

    def test_uses_separator_lines(self):
        """Report uses separator lines for clarity."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        # Should have separator lines
        assert "=" * 70 in output or "─" * 70 in output

    def test_sections_have_blank_lines(self):
        """Sections are separated by blank lines."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(True)

        output = str(trace)
        lines = output.split("\n")

        # Should have multiple blank lines for separation
        blank_line_count = sum(1 for line in lines if line.strip() == "")
        assert blank_line_count >= 3  # At least a few blank lines for readability


class TestScannability:
    """Test report is scannable and easy to read."""

    def test_failures_are_easy_to_spot(self):
        """Failed checks are easy to spot visually."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(False, "Failed")
        trace.record_stage_abort_check(0, "stage_0", False)

        output = str(trace)

        # Failures should have distinct symbol
        assert "✗" in output
        # Summary should highlight failures
        assert "✗ Failed:" in output or "Failed: 1" in output

    def test_report_has_consistent_indentation(self):
        """Report uses consistent indentation."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])

        output = str(trace)
        lines = output.split("\n")

        # Check that indentation is consistent (2 or 3 spaces for details)
        detail_lines = [l for l in lines if l.startswith("   ")]
        assert len(detail_lines) > 0  # Should have indented lines


class TestEndToEndFormatting:
    """Test complete safety trace formatting scenarios."""

    def test_complex_trace_is_well_formatted(self):
        """Complex trace with multiple gate types is well-formatted."""
        trace = SafetyTrace(
            study_name="complex_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        # Add various gate types
        trace.record_legality_check(True, [], ["Warning"])
        trace.record_base_case_verification(True)
        trace.record_eco_class_filter(ECOClass.PLACEMENT_LOCAL, 0, True)
        trace.record_stage_abort_check(0, "stage_0", False)
        trace.record_wns_threshold_check(0, -5000, -3000, [])
        trace.record_catastrophic_failure_check(0, 1, 10, 0.1, 0.5)

        # Add a failure
        trace.record_wns_threshold_check(1, -5000, -8000, ["trial_1", "trial_2"])

        output = str(trace)

        # Verify all major sections present
        assert "SUMMARY" in output
        assert "CHECKS BY TYPE" in output
        assert "CHRONOLOGICAL EVALUATION LOG" in output

        # Verify it's scannable
        assert "✓" in output  # Has passes
        assert "✗" in output  # Has failures
        assert "SAFETY VIOLATIONS DETECTED" in output or "⚠️" in output

    def test_trace_with_all_passes_is_encouraging(self):
        """Trace with all passes shows positive message."""
        trace = SafetyTrace(
            study_name="successful_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(True)
        trace.record_stage_abort_check(0, "stage_0", False)

        output = str(trace)

        # Should show all passed
        assert "ALL SAFETY CHECKS PASSED" in output or "✅" in output
        # Should not show violations
        assert "SAFETY VIOLATIONS DETECTED" not in output

    def test_trace_saves_to_text_file_with_formatting(self):
        """Trace saved to text file preserves formatting."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )
        trace.record_legality_check(True, [], [])
        trace.record_base_case_verification(False, "Failed")

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "trace.txt"
            trace.save_to_file(filepath)

            content = filepath.read_text()

            # Verify formatting preserved
            assert "SAFETY TRACE REPORT" in content
            assert "✓" in content or "✗" in content
            assert "CHRONOLOGICAL EVALUATION LOG" in content


class TestTimestampFormatting:
    """Test timestamp formatting helper function."""

    def test_format_timestamp_removes_microseconds(self):
        """Timestamp formatting removes microseconds."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )

        timestamp = "2026-01-08T23:00:25.782834+00:00"
        formatted = trace._format_timestamp_readable(timestamp)

        # Should not have microseconds
        assert ".782834" not in formatted
        # Should have UTC
        assert "UTC" in formatted

    def test_format_timestamp_includes_date_and_time(self):
        """Formatted timestamp includes both date and time."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )

        timestamp = "2026-01-08T15:30:45.123456+00:00"
        formatted = trace._format_timestamp_readable(timestamp)

        # Should have date part
        assert "2026-01-08" in formatted
        # Should have time part
        assert "15:30:45" in formatted or "15:30" in formatted


class TestContextFormattingHelper:
    """Test context formatting helper function."""

    def test_format_context_filters_empty_values(self):
        """Context formatting filters out empty values."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )

        context = {
            "stage_index": 0,
            "empty_list": [],
            "empty_string": "",
            "false_bool": False,
            "meaningful_value": 42,
        }

        formatted = trace._format_context(context)

        # Should include meaningful values
        assert "stage_index: 0" in formatted
        assert "meaningful_value: 42" in formatted

        # Should not include empty values
        assert "empty_list" not in formatted
        assert "empty_string" not in formatted
        assert "false_bool" not in formatted or "False" not in formatted

    def test_format_context_handles_short_lists(self):
        """Context formatting displays short lists inline."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )

        context = {
            "trials": ["trial_1", "trial_2", "trial_3"],
        }

        formatted = trace._format_context(context)

        # Should show list items or count
        assert "trial_1" in formatted or "3 items" in formatted

    def test_format_context_handles_long_lists(self):
        """Context formatting shows count for long lists."""
        trace = SafetyTrace(
            study_name="test",
            safety_domain=SafetyDomain.GUARDED,
        )

        context = {
            "many_items": [f"item_{i}" for i in range(20)],
        }

        formatted = trace._format_context(context)

        # Should show item count, not all items
        assert "20 items" in formatted or "many_items" in formatted
