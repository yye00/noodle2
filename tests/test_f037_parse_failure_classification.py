"""Tests for F037: Trial failure classification works for parse failures."""

import tempfile
from pathlib import Path

import pytest

from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)


class TestParseFailureClassification:
    """Test parse failure detection and classification."""

    def test_classify_parse_failure_creates_correct_classification(self):
        """Test that classify_parse_failure creates correct classification."""
        file_path = Path("/tmp/metrics.json")
        error_message = "Unexpected token at line 42"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE
        assert classification.severity == FailureSeverity.HIGH
        assert "metrics.json" in classification.reason
        assert error_message in classification.reason

    def test_parse_failure_includes_file_name(self):
        """Test that parse failure includes the file name that failed."""
        file_path = Path("/artifacts/timing_report.txt")
        error_message = "Could not parse timing data"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert "timing_report.txt" in classification.reason

    def test_parse_failure_includes_error_message(self):
        """Test that parse failure includes the error message."""
        file_path = Path("/tmp/output.json")
        error_message = "JSON decode error: Expecting ',' delimiter"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert error_message in classification.reason
        assert error_message in classification.log_excerpt

    def test_parse_failure_severity_is_high(self):
        """Test that parse failures have HIGH severity."""
        file_path = Path("/tmp/file.txt")
        error_message = "Parse error"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.severity == FailureSeverity.HIGH

    def test_parse_failure_is_not_recoverable(self):
        """Test that parse failures are marked as not recoverable."""
        file_path = Path("/tmp/file.txt")
        error_message = "Parse error"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.recoverable is False


class TestParseFailureScenarios:
    """Test specific parse failure scenarios."""

    def test_json_parse_failure(self):
        """Test JSON parsing failure classification."""
        file_path = Path("/artifacts/metrics.json")
        error_message = "JSONDecodeError: Expecting value: line 1 column 1 (char 0)"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE
        assert "metrics.json" in classification.reason

    def test_timing_report_parse_failure(self):
        """Test timing report parsing failure."""
        file_path = Path("/artifacts/timing.rpt")
        error_message = "Could not extract WNS: regex pattern not found"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE
        assert "timing.rpt" in classification.reason

    def test_congestion_metrics_parse_failure(self):
        """Test congestion metrics parsing failure."""
        file_path = Path("/artifacts/congestion.rpt")
        error_message = "Unexpected format: missing overflow counts"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE
        assert "congestion.rpt" in classification.reason

    def test_corrupted_output_file(self):
        """Test corrupted output file parsing failure."""
        file_path = Path("/artifacts/output.txt")
        error_message = "File appears to be corrupted or truncated"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE


class TestParseFailureLogging:
    """Test that parse failures are properly logged."""

    def test_parse_failure_can_be_serialized(self):
        """Test that parse failure classification can be serialized."""
        file_path = Path("/tmp/file.txt")
        error_message = "Parse error"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        # Serialize to dict
        data = classification.to_dict()

        assert isinstance(data, dict)
        assert data["failure_type"] == "parse_failure"
        assert data["severity"] == "high"
        assert "reason" in data
        assert "log_excerpt" in data

    def test_parse_failure_includes_all_required_fields(self):
        """Test that classification includes all required fields."""
        file_path = Path("/tmp/file.txt")
        error_message = "Parse error"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert hasattr(classification, "failure_type")
        assert hasattr(classification, "severity")
        assert hasattr(classification, "reason")
        assert hasattr(classification, "log_excerpt")
        assert hasattr(classification, "recoverable")


class TestFeatureStepValidation:
    """Validate all steps from feature F037."""

    def test_step1_run_trial_that_produces_corrupted_output(self):
        """Step 1: Run trial that produces corrupted output file.

        This simulates a trial that completed but produced output
        that cannot be parsed correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Simulate successful execution (rc=0) but corrupted output
            # Create a corrupted output file
            output_file = artifacts_dir / "metrics.json"
            output_file.write_text("{ corrupt json data ][")

            # When we try to parse it, we get a parse failure
            file_path = output_file
            error_message = "JSON decode error: Invalid JSON format"

            classification = FailureClassifier.classify_parse_failure(
                file_path=file_path,
                error_message=error_message,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.PARSE_FAILURE

    def test_step2_attempt_to_parse_metrics(self):
        """Step 2: Attempt to parse metrics.

        This simulates the parser encountering an error when trying
        to extract metrics from the corrupted output.
        """
        file_path = Path("/artifacts/metrics.json")
        error_message = "Failed to parse JSON: Unexpected character"

        # This is what the parser would call when it fails
        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None

    def test_step3_verify_failure_type_is_parse_failure(self):
        """Step 3: Verify failure type is classified as 'parse_failure'."""
        file_path = Path("/tmp/output.json")
        error_message = "Parse error"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        # Verify failure_type is exactly PARSE_FAILURE
        assert classification.failure_type == FailureType.PARSE_FAILURE
        assert classification.failure_type.value == "parse_failure"

    def test_step4_verify_severity_is_high(self):
        """Step 4: Verify severity is 'high'."""
        file_path = Path("/tmp/output.json")
        error_message = "Parse error"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.severity == FailureSeverity.HIGH
        assert classification.severity.value == "high"

    def test_step5_verify_failure_is_logged(self):
        """Step 5: Verify failure is logged.

        This tests that the failure classification can be serialized
        to JSON for logging.
        """
        file_path = Path("/tmp/output.json")
        error_message = "Parse error: unexpected token"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None

        # Verify can be serialized to dict (for JSON logging)
        data = classification.to_dict()

        assert isinstance(data, dict)
        assert "failure_type" in data
        assert "severity" in data
        assert "reason" in data
        assert "log_excerpt" in data
        assert "recoverable" in data

        # Verify values are correct
        assert data["failure_type"] == "parse_failure"
        assert data["severity"] == "high"
        assert isinstance(data["reason"], str)
        assert len(data["reason"]) > 0


class TestParseFailureVsToolCrash:
    """Test distinction between parse failures and tool crashes."""

    def test_successful_execution_with_parse_failure(self):
        """Test that successful execution (rc=0) can still have parse failure.

        Tool completes successfully but output is unparseable.
        """
        file_path = Path("/tmp/metrics.json")
        error_message = "Could not extract metrics"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        # This is a PARSE_FAILURE, not a TOOL_CRASH
        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE
        assert classification.failure_type != FailureType.TOOL_CRASH

    def test_tool_crash_vs_parse_failure_distinction(self):
        """Test that tool crashes and parse failures are distinct."""
        # Tool crash (non-zero exit code)
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            tool_crash = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Tool error\n",
                artifacts_dir=artifacts_dir,
            )

            assert tool_crash is not None
            assert tool_crash.failure_type == FailureType.TOOL_CRASH

        # Parse failure (explicit classification)
        parse_failure = FailureClassifier.classify_parse_failure(
            file_path=Path("/tmp/file.txt"),
            error_message="Parse error",
        )

        assert parse_failure is not None
        assert parse_failure.failure_type == FailureType.PARSE_FAILURE

        # They should be different
        assert tool_crash.failure_type != parse_failure.failure_type


class TestRealWorldParseFailures:
    """Test real-world parse failure scenarios."""

    def test_empty_output_file(self):
        """Test empty output file causing parse failure."""
        file_path = Path("/artifacts/timing.rpt")
        error_message = "File is empty, cannot extract metrics"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE

    def test_truncated_output_file(self):
        """Test truncated output file causing parse failure."""
        file_path = Path("/artifacts/metrics.json")
        error_message = "Unexpected EOF while parsing JSON"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE

    def test_wrong_format_output_file(self):
        """Test wrong format output file causing parse failure."""
        file_path = Path("/artifacts/report.txt")
        error_message = "Expected OpenROAD report format, got unexpected format"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE

    def test_missing_required_fields(self):
        """Test missing required fields in output causing parse failure."""
        file_path = Path("/artifacts/metrics.json")
        error_message = "Missing required field: 'wns_ps'"

        classification = FailureClassifier.classify_parse_failure(
            file_path=file_path,
            error_message=error_message,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PARSE_FAILURE
