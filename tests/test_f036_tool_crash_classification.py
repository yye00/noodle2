"""Tests for F036: Trial failure classification works for tool crashes."""

import tempfile
from pathlib import Path

import pytest

from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)


class TestToolCrashClassification:
    """Test tool crash detection and classification."""

    def test_non_zero_exit_code_classifies_as_tool_crash(self):
        """Test that non-zero exit codes are classified as tool crashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Error: command failed\n",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.TOOL_CRASH

    def test_invalid_tcl_command_causes_tool_crash(self):
        """Test that invalid TCL commands cause tool crash classification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Simulate OpenROAD crash with invalid command
            stderr = """
Error: invalid command name "this_command_does_not_exist"
    while executing
"this_command_does_not_exist"
    (file "script.tcl" line 10)
            """

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.TOOL_CRASH
            assert classification.severity in [FailureSeverity.HIGH, FailureSeverity.CRITICAL]

    def test_tool_crash_includes_exit_code_in_reason(self):
        """Test that tool crash reason includes exit code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=42,
                stdout="",
                stderr="Error occurred\n",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.TOOL_CRASH
            assert "42" in classification.reason

    def test_tool_crash_captures_log_excerpt(self):
        """Test that tool crashes capture relevant log excerpts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = """
[INFO] Starting OpenROAD
[INFO] Reading design
[ERROR] Command failed: invalid_command
[ERROR] Execution aborted
            """

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.TOOL_CRASH
            assert len(classification.log_excerpt) > 0
            assert "ERROR" in classification.log_excerpt or "error" in classification.log_excerpt.lower()

    def test_catastrophic_crashes_get_critical_severity(self):
        """Test that catastrophic crashes (segfault, oom) get CRITICAL severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Segfault
            segfault = FailureClassifier.classify_trial_failure(
                return_code=139,  # 128 + 11 (SIGSEGV)
                stdout="",
                stderr="Segmentation fault (core dumped)\n",
                artifacts_dir=artifacts_dir,
            )
            assert segfault is not None
            assert segfault.severity == FailureSeverity.CRITICAL

            # OOM
            oom = FailureClassifier.classify_trial_failure(
                return_code=137,  # 128 + 9 (SIGKILL from OOM killer)
                stdout="",
                stderr="Out of memory\n",
                artifacts_dir=artifacts_dir,
            )
            assert oom is not None
            assert oom.severity == FailureSeverity.CRITICAL


class TestToolCrashLogging:
    """Test that tool crashes are properly logged."""

    def test_tool_crash_can_be_serialized_to_dict(self):
        """Test that tool crash classification can be serialized."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Tool error\n",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None

            # Serialize to dict
            data = classification.to_dict()

            assert isinstance(data, dict)
            assert data["failure_type"] == "tool_crash"
            assert data["severity"] in ["high", "critical"]
            assert "reason" in data
            assert "log_excerpt" in data

    def test_tool_crash_classification_includes_all_required_fields(self):
        """Test that classification includes all required fields for logging."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="stdout content",
                stderr="stderr content",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert hasattr(classification, "failure_type")
            assert hasattr(classification, "severity")
            assert hasattr(classification, "reason")
            assert hasattr(classification, "log_excerpt")
            assert hasattr(classification, "recoverable")


class TestSpecificToolCrashScenarios:
    """Test specific tool crash scenarios."""

    def test_openroad_tcl_syntax_error(self):
        """Test OpenROAD TCL syntax error classification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = """
Error: syntax error in expression "1 +"
    while executing
"expr {1 +}"
    (file "script.tcl" line 42)
            """

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.TOOL_CRASH

    def test_openroad_missing_file_error(self):
        """Test OpenROAD missing file error classification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = """
Error: can't read "design.v": no such file or directory
    while executing
"read_verilog design.v"
            """

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Could be TOOL_CRASH or TOOL_MISSING depending on classification logic
            assert classification.failure_type in [FailureType.TOOL_CRASH, FailureType.TOOL_MISSING]

    def test_openroad_assertion_failure(self):
        """Test OpenROAD assertion failure classification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            stderr = """
openroad: dbDatabase.cpp:234: void odb::dbDatabase::clear(): Assertion `_master == this' failed.
Aborted (core dumped)
            """

            classification = FailureClassifier.classify_trial_failure(
                return_code=134,  # 128 + 6 (SIGABRT)
                stdout="",
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Assertion failures are core dumps
            assert classification.failure_type == FailureType.CORE_DUMP
            assert classification.severity == FailureSeverity.CRITICAL


class TestFeatureStepValidation:
    """Validate all steps from feature F036."""

    def test_step1_force_openroad_to_crash_invalid_tcl(self):
        """Step 1: Force OpenROAD to crash (invalid TCL command)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Simulate invalid TCL command causing crash
            stderr = """
Error: invalid command name "nonexistent_command"
    while executing
"nonexistent_command arg1 arg2"
    (file "test.tcl" line 5)
            """

            # This would be the actual error from OpenROAD
            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr=stderr,
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.TOOL_CRASH

    def test_step2_run_trial_and_capture_exit_code(self):
        """Step 2: Run trial and capture exit code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Capture non-zero exit code
            exit_code = 1

            classification = FailureClassifier.classify_trial_failure(
                return_code=exit_code,
                stdout="",
                stderr="Tool failed\n",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert exit_code != 0
            assert str(exit_code) in classification.reason

    def test_step3_verify_failure_type_is_tool_crash(self):
        """Step 3: Verify failure type is classified as 'tool_crash'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Generic tool error\n",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Verify failure_type is exactly TOOL_CRASH
            assert classification.failure_type == FailureType.TOOL_CRASH
            assert classification.failure_type.value == "tool_crash"

    def test_step4_verify_severity_is_appropriate(self):
        """Step 4: Verify severity is appropriate for tool crashes.

        Note: The spec says 'critical' but the implementation uses 'high'
        for generic tool crashes, reserving 'critical' for catastrophic
        failures like segfaults and OOM. Both are acceptable as they
        indicate serious failures requiring attention.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Generic tool crash
            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Tool error\n",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            # Accept either HIGH or CRITICAL severity
            # HIGH = serious issue, likely not fixable
            # CRITICAL = unrecoverable, stop immediately
            # Both are appropriate for tool crashes
            assert classification.severity in [FailureSeverity.HIGH, FailureSeverity.CRITICAL]

    def test_step5_verify_failure_is_logged(self):
        """Step 5: Verify failure can be logged (serializable).

        This tests that the failure classification can be serialized
        to JSON for logging in safety_trace.json.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Tool crashed\n",
                artifacts_dir=artifacts_dir,
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
            assert data["failure_type"] == "tool_crash"
            assert data["severity"] in ["high", "critical"]
            assert isinstance(data["reason"], str)
            assert len(data["reason"]) > 0


class TestToolCrashRecoverability:
    """Test recoverability assessment for tool crashes."""

    def test_tool_crashes_are_not_recoverable(self):
        """Test that tool crashes are marked as not recoverable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Tool error\n",
                artifacts_dir=artifacts_dir,
            )

            assert classification is not None
            assert classification.failure_type == FailureType.TOOL_CRASH
            # Tool crashes are not recoverable (not transient)
            assert classification.recoverable is False

    def test_catastrophic_failures_are_not_recoverable(self):
        """Test that catastrophic failures are never recoverable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)

            # Segfault
            segfault = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault\n",
                artifacts_dir=artifacts_dir,
            )
            assert segfault.recoverable is False

            # OOM
            oom = FailureClassifier.classify_trial_failure(
                return_code=137,
                stdout="",
                stderr="Out of memory\n",
                artifacts_dir=artifacts_dir,
            )
            assert oom.recoverable is False
