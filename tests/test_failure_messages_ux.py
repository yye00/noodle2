"""Test failure classification messages for clarity and actionability.

This test suite validates that all failure messages are:
1. Clear - explain what went wrong
2. Actionable - suggest next steps or workarounds where applicable
3. Human-friendly - readable and professional

This addresses Feature: "Failure classification messages are clear, actionable, and human-friendly"
"""

import pytest
from pathlib import Path
from src.controller.failure import (
    FailureClassifier,
    FailureType,
    FailureSeverity,
    FailureClassification,
)


class TestFailureMessageClarity:
    """Test that failure messages clearly explain what went wrong."""

    def test_tool_crash_message_is_clear(self, tmp_path):
        """Tool crash messages should clearly state exit code and context."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Error: Something went wrong",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert "Tool exited with non-zero code: 1" in classification.reason
        assert classification.failure_type == FailureType.TOOL_CRASH
        # Message should be human-readable
        assert len(classification.reason) > 0
        assert classification.log_excerpt  # Should include context

    def test_oom_message_includes_memory_context(self, tmp_path):
        """OOM messages should include peak memory and limit for diagnosis."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="[ERROR] out of memory",
            artifacts_dir=tmp_path,
            peak_memory_mb=4096.5,
            memory_limit_mb=4000.0,
        )

        assert classification is not None
        assert "Out of memory error" in classification.reason
        # Should include specific memory values
        assert "4096" in classification.reason or "4.1" in classification.reason  # Peak usage
        assert "4000" in classification.reason or "4.0" in classification.reason  # Limit
        # Should suggest fix
        assert "increasing memory limit" in classification.reason.lower() or "increase" in classification.reason.lower()

    def test_timeout_message_is_clear(self, tmp_path):
        """Timeout messages should clearly indicate trial exceeded time limit."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=124,
            stdout="",
            stderr="timeout: command timed out after 3600 seconds",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert "timeout" in classification.reason.lower()
        assert classification.failure_type == FailureType.TIMEOUT

    def test_segfault_message_is_clear(self, tmp_path):
        """Segfault messages should clearly identify catastrophic failure."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=139,
            stdout="",
            stderr="Segmentation fault (core dumped)",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert "Segmentation fault" in classification.reason
        assert classification.severity == FailureSeverity.CRITICAL
        assert not classification.recoverable

    def test_missing_output_message_lists_files(self, tmp_path):
        """Missing output messages should list which files are missing."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=0,
            stdout="Success",
            stderr="",
            artifacts_dir=tmp_path,
            expected_outputs=["timing_report.txt", "congestion_report.json"],
        )

        assert classification is not None
        assert "timing_report.txt" in classification.reason
        assert "congestion_report.json" in classification.reason
        assert "not produced" in classification.reason.lower()

    def test_parse_failure_message_names_file(self):
        """Parse failure messages should name the file that failed."""
        classification = FailureClassifier.classify_parse_failure(
            file_path=Path("/artifacts/timing_report.txt"),
            error_message="Expected numeric value, got 'N/A'",
        )

        assert classification is not None
        assert "timing_report.txt" in classification.reason
        assert "parse" in classification.reason.lower()
        assert "N/A" in classification.log_excerpt


class TestFailureMessageActionability:
    """Test that failure messages suggest actionable next steps."""

    def test_oom_suggests_memory_increase(self, tmp_path):
        """OOM failures should suggest specific memory limit increase."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="out of memory",
            artifacts_dir=tmp_path,
            peak_memory_mb=3950.0,
            memory_limit_mb=4000.0,
        )

        assert classification is not None
        # Should suggest specific increase (1.5x)
        assert "6000" in classification.reason or "increasing" in classification.reason.lower()

    def test_asap7_routing_suggests_fix(self, tmp_path):
        """ASAP7 routing failures should suggest explicit routing layer config."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="[ERROR] Failed to infer routing track information for ASAP7",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.CONFIGURATION_ERROR
        # Should mention the fix
        assert "set_routing_layers" in classification.reason
        assert "metal2-metal9" in classification.reason or "metal6-metal9" in classification.reason

    def test_asap7_site_suggests_fix(self, tmp_path):
        """ASAP7 site failures should suggest explicit site specification."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="[ERROR] Cannot determine floorplan site for ASAP7",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.CONFIGURATION_ERROR
        # Should mention the site name
        assert "asap7sc7p5t" in classification.reason.lower() or "site specification" in classification.reason.lower()

    def test_tool_missing_identifies_tool(self, tmp_path):
        """Tool missing errors should identify what's missing."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=127,
            stdout="",
            stderr="openroad: command not found",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.TOOL_MISSING
        assert "not found" in classification.reason.lower()

    def test_invalid_eco_suggests_correction(self):
        """Invalid ECO messages should be actionable."""
        classification = FailureClassifier.classify_invalid_eco(
            eco_name="buffer_insertion",
            reason="max_capacitance parameter must be positive",
        )

        assert classification is not None
        assert "buffer_insertion" in classification.reason
        assert "parameter must be positive" in classification.reason
        assert classification.recoverable  # Can be fixed


class TestFailureMessageHumanFriendliness:
    """Test that failure messages are readable and professional."""

    def test_messages_use_complete_sentences(self, tmp_path):
        """Failure messages should be complete sentences."""
        # Test various failure types
        classifications = [
            FailureClassifier.classify_trial_failure(
                return_code=1, stdout="", stderr="error", artifacts_dir=tmp_path
            ),
            FailureClassifier.classify_trial_failure(
                return_code=137, stdout="", stderr="oom", artifacts_dir=tmp_path,
                peak_memory_mb=4000.0, memory_limit_mb=4000.0
            ),
            FailureClassifier.classify_trial_failure(
                return_code=124, stdout="", stderr="timeout", artifacts_dir=tmp_path
            ),
        ]

        for classification in classifications:
            assert classification is not None
            # Should start with capital letter
            assert classification.reason[0].isupper()
            # Should not be all caps (shouting)
            assert not classification.reason.isupper()
            # Should be a reasonable length (not too terse, not too verbose)
            assert 10 < len(classification.reason) < 500

    def test_messages_avoid_jargon_where_possible(self, tmp_path):
        """Messages should be understandable to operators, not just developers."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="killed",
            artifacts_dir=tmp_path,
            peak_memory_mb=4096.0,
            memory_limit_mb=4000.0,
        )

        assert classification is not None
        # Should say "Out of memory" not "OOM killer invoked SIGKILL"
        assert "Out of memory" in classification.reason
        # Should include helpful context
        assert "MB" in classification.reason  # Units are clear

    def test_severity_matches_message_tone(self, tmp_path):
        """Critical failures should be clearly marked as serious."""
        # Critical failure - segfault
        critical = FailureClassifier.classify_trial_failure(
            return_code=139,
            stdout="",
            stderr="Segmentation fault",
            artifacts_dir=tmp_path,
        )

        assert critical is not None
        assert critical.severity == FailureSeverity.CRITICAL
        assert not critical.recoverable

        # Medium severity - transient network error
        medium = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="connection refused",
            artifacts_dir=tmp_path,
        )

        assert medium is not None
        assert medium.severity == FailureSeverity.MEDIUM
        assert medium.recoverable

    def test_log_excerpts_are_bounded(self, tmp_path):
        """Log excerpts should not overwhelm the reader."""
        # Create a very long stderr
        long_stderr = "\n".join([f"Line {i}: Some log message" for i in range(100)])

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr=long_stderr,
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        # Log excerpt should be truncated to last 20 lines
        excerpt_lines = classification.log_excerpt.split("\n")
        assert len(excerpt_lines) <= 20


class TestFailureTypesCoverage:
    """Test that we have messages for all expected failure types."""

    def test_tool_crash_covered(self, tmp_path):
        """Tool crash failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1, stdout="", stderr="error", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.TOOL_CRASH

    def test_oom_covered(self, tmp_path):
        """OOM failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137, stdout="", stderr="oom", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.OOM

    def test_timeout_covered(self, tmp_path):
        """Timeout failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=124, stdout="", stderr="timeout", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.TIMEOUT

    def test_segfault_covered(self, tmp_path):
        """Segfault failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=139, stdout="", stderr="segfault", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.SEGFAULT

    def test_network_error_covered(self, tmp_path):
        """Network error failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1, stdout="", stderr="network error", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.NETWORK_ERROR

    def test_resource_busy_covered(self, tmp_path):
        """Resource busy failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1, stdout="", stderr="resource busy", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.RESOURCE_BUSY

    def test_container_error_covered(self, tmp_path):
        """Container error failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1, stdout="", stderr="container error", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.CONTAINER_ERROR

    def test_tool_missing_covered(self, tmp_path):
        """Tool missing failures have clear messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=127, stdout="", stderr="command not found", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.TOOL_MISSING

    def test_placement_failed_covered(self, tmp_path):
        """Placement failure messages are clear."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1, stdout="", stderr="placement failed", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.PLACEMENT_FAILED

    def test_routing_failed_covered(self, tmp_path):
        """Routing failure messages are clear."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1, stdout="", stderr="routing failed", artifacts_dir=tmp_path
        )
        assert classification is not None
        assert classification.failure_type == FailureType.ROUTING_FAILED


class TestEndToEndFailureMessages:
    """Test complete failure classification workflow."""

    def test_failure_classification_includes_all_required_fields(self, tmp_path):
        """Every failure should have type, severity, reason, and recoverability."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="Some output",
            stderr="Some error",
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        assert isinstance(classification.failure_type, FailureType)
        assert isinstance(classification.severity, FailureSeverity)
        assert isinstance(classification.reason, str)
        assert isinstance(classification.recoverable, bool)
        assert len(classification.reason) > 0

    def test_failure_serialization_preserves_message(self, tmp_path):
        """Serialized failures maintain human-readable messages."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="out of memory",
            artifacts_dir=tmp_path,
            peak_memory_mb=4096.0,
            memory_limit_mb=4000.0,
        )

        assert classification is not None
        result_dict = classification.to_dict()

        # JSON should be readable
        assert "reason" in result_dict
        assert "Out of memory" in result_dict["reason"]
        assert "failure_type" in result_dict
        assert result_dict["failure_type"] == "out_of_memory"

    def test_messages_support_debugging(self, tmp_path):
        """Failure messages should include enough context for debugging."""
        # Simulate a realistic failure with logs
        stderr_log = """
[INFO] Starting placement
[INFO] Placing 1000 cells
[WARNING] High congestion detected
[ERROR] Placement overflow detected
[ERROR] Unable to place remaining cells
[ERROR] Placement failed with exit code 1
"""

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr=stderr_log,
            artifacts_dir=tmp_path,
        )

        assert classification is not None
        # Should include relevant log context
        assert len(classification.log_excerpt) > 0
        # Should identify as placement failure
        assert classification.failure_type == FailureType.PLACEMENT_FAILED
