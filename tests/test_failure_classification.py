"""Tests for failure classification and detection."""

import tempfile
from pathlib import Path

import pytest

from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)
from src.trial_runner.trial import Trial, TrialConfig


def test_classify_success():
    """Test that successful trials return None (no failure)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=0,
            stdout="All operations completed successfully",
            stderr="",
            artifacts_dir=artifacts_dir,
            expected_outputs=None,
        )

        assert classification is None


def test_classify_tool_crash():
    """Test classification of tool crash (non-zero exit code)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="Processing design...",
            stderr="Error: Tool crashed unexpectedly",
            artifacts_dir=artifacts_dir,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.TOOL_CRASH
        assert classification.severity == FailureSeverity.HIGH
        assert "non-zero code" in classification.reason.lower()
        assert not classification.recoverable


def test_classify_oom_failure():
    """Test classification of out-of-memory failure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="Allocating memory...",
            stderr="Out of memory\nKilled",
            artifacts_dir=artifacts_dir,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.OOM
        assert classification.severity == FailureSeverity.CRITICAL
        assert "out of memory" in classification.reason.lower()
        assert not classification.recoverable


def test_classify_timeout():
    """Test classification of timeout failure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=124,
            stdout="Running placement...",
            stderr="Timeout exceeded",
            artifacts_dir=artifacts_dir,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.TIMEOUT
        assert classification.severity == FailureSeverity.HIGH
        assert "timeout" in classification.reason.lower()


def test_classify_tool_missing():
    """Test classification of missing tool."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=127,
            stdout="",
            stderr="openroad: command not found",
            artifacts_dir=artifacts_dir,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.TOOL_MISSING
        assert classification.severity == FailureSeverity.CRITICAL
        assert "not found" in classification.reason.lower()


def test_classify_placement_failure():
    """Test classification of placement failure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Error: placement failed due to insufficient space",
            artifacts_dir=artifacts_dir,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.PLACEMENT_FAILED
        assert classification.severity == FailureSeverity.HIGH
        assert "placement" in classification.reason.lower()


def test_classify_routing_failure():
    """Test classification of routing failure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="Starting global routing...",
            stderr="Error: routing cannot complete - too congested",
            artifacts_dir=artifacts_dir,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.ROUTING_FAILED
        assert classification.severity == FailureSeverity.HIGH
        assert "routing" in classification.reason.lower()


def test_classify_missing_output():
    """Test classification of missing required outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        # Success exit code but missing outputs
        classification = FailureClassifier.classify_trial_failure(
            return_code=0,
            stdout="Run completed",
            stderr="",
            artifacts_dir=artifacts_dir,
            expected_outputs=["timing_report.txt", "metrics.json"],
        )

        assert classification is not None
        assert classification.failure_type == FailureType.MISSING_OUTPUT
        assert classification.severity == FailureSeverity.HIGH
        assert "not produced" in classification.reason


def test_classify_missing_output_with_some_files():
    """Test classification when some but not all outputs are produced."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        # Create one file but not the other
        (artifacts_dir / "timing_report.txt").write_text("WNS: -1.5 ns")

        classification = FailureClassifier.classify_trial_failure(
            return_code=0,
            stdout="Run completed",
            stderr="",
            artifacts_dir=artifacts_dir,
            expected_outputs=["timing_report.txt", "metrics.json"],
        )

        assert classification is not None
        assert classification.failure_type == FailureType.MISSING_OUTPUT
        assert "metrics.json" in classification.reason


def test_classify_parse_failure():
    """Test classification of parse failure."""
    classification = FailureClassifier.classify_parse_failure(
        file_path=Path("/work/timing_report.txt"),
        error_message="Could not find WNS value in report",
    )

    assert classification.failure_type == FailureType.PARSE_FAILURE
    assert classification.severity == FailureSeverity.HIGH
    assert "timing_report.txt" in classification.reason
    assert "Could not find WNS value" in classification.reason
    assert not classification.recoverable


def test_classify_invalid_eco():
    """Test classification of invalid ECO."""
    classification = FailureClassifier.classify_invalid_eco(
        eco_name="buffer_insertion",
        reason="Target net does not exist",
    )

    assert classification.failure_type == FailureType.INVALID_ECO
    assert classification.severity == FailureSeverity.MEDIUM
    assert "buffer_insertion" in classification.reason
    assert "does not exist" in classification.reason
    assert classification.recoverable  # Can be fixed


def test_classify_visualization_unavailable():
    """Test classification of visualization unavailability."""
    classification = FailureClassifier.classify_visualization_unavailable(
        reason="DISPLAY not set, GUI mode not available"
    )

    assert classification.failure_type == FailureType.VISUALIZATION_UNAVAILABLE
    assert classification.severity == FailureSeverity.INFO
    assert "DISPLAY" in classification.reason
    assert classification.recoverable  # Can fall back


def test_log_excerpt_extraction():
    """Test that log excerpts are extracted correctly."""
    stderr = "\n".join([f"Line {i}" for i in range(100)])
    stdout = ""

    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout=stdout,
            stderr=stderr,
            artifacts_dir=artifacts_dir,
        )

        assert classification is not None
        # Should extract last 20 lines
        lines = classification.log_excerpt.split("\n")
        assert len(lines) <= 20
        # Should be the most recent lines
        assert "Line 99" in classification.log_excerpt


def test_failure_classification_to_dict():
    """Test that FailureClassification serializes to dict correctly."""
    classification = FailureClassification(
        failure_type=FailureType.TOOL_CRASH,
        severity=FailureSeverity.HIGH,
        reason="Tool crashed with exit code 1",
        log_excerpt="Error on line 42",
        metrics={"exit_code": 1},
        recoverable=False,
    )

    result = classification.to_dict()

    assert result["failure_type"] == "tool_crash"
    assert result["severity"] == "high"
    assert result["reason"] == "Tool crashed with exit code 1"
    assert result["log_excerpt"] == "Error on line 42"
    assert result["metrics"] == {"exit_code": 1}
    assert result["recoverable"] is False


def test_trial_with_failure_classification():
    """Test that Trial integrates failure classification."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create a script that will fail
        script_path = tmpdir / "fail.tcl"
        script_path.write_text("exit 1")

        artifacts_root = tmpdir / "artifacts"

        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=None,
        )

        trial = Trial(config, artifacts_root=artifacts_root)

        # This will fail but should not raise an exception
        result = trial.execute()

        # Verify failure was classified
        assert not result.success
        assert result.return_code == 1
        assert result.failure is not None
        assert result.failure.failure_type == FailureType.TOOL_CRASH
        assert result.failure.severity == FailureSeverity.HIGH


def test_trial_result_with_failure_serialization():
    """Test that TrialResult with failure serializes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        script_path = tmpdir / "fail.tcl"
        script_path.write_text("exit 1")

        artifacts_root = tmpdir / "artifacts"

        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
            snapshot_dir=None,
        )

        trial = Trial(config, artifacts_root=artifacts_root)
        result = trial.execute()

        # Serialize to dict
        result_dict = result.to_dict()

        # Verify failure is included
        assert "failure" in result_dict
        assert result_dict["failure"]["failure_type"] == "tool_crash"
        assert result_dict["failure"]["severity"] == "high"
        assert "non-zero code" in result_dict["failure"]["reason"].lower()


def test_deterministic_classification():
    """Test that failure classification is deterministic."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        # Same inputs should produce same classification
        classification1 = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="Test output",
            stderr="Error: placement failed",
            artifacts_dir=artifacts_dir,
        )

        classification2 = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="Test output",
            stderr="Error: placement failed",
            artifacts_dir=artifacts_dir,
        )

        assert classification1.failure_type == classification2.failure_type
        assert classification1.severity == classification2.severity
        assert classification1.reason == classification2.reason


def test_multiple_error_indicators():
    """Test that classifier handles multiple error indicators correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifacts_dir = Path(tmpdir)

        # OOM takes precedence over generic error
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Error: placement failed\nOut of memory\nKilled",
            artifacts_dir=artifacts_dir,
        )

        assert classification.failure_type == FailureType.OOM
        assert classification.severity == FailureSeverity.CRITICAL
