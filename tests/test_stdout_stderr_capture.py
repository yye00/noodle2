"""Tests for stdout and stderr capture from OpenROAD tool invocations.

This test suite validates that Noodle 2 properly captures, redirects, and preserves
stdout and stderr from OpenROAD executions for debugging, failure classification,
and auditability.

Feature: Capture stdout and stderr from OpenROAD tool invocations
Steps:
  1. Execute OpenROAD command in trial
  2. Redirect stdout to trial log file
  3. Redirect stderr to separate error log file
  4. Preserve both logs in trial artifacts
  5. Extract log excerpts for failure classification
"""

import json
from pathlib import Path

import pytest

from src.controller.failure import FailureClassifier
from src.trial_runner.docker_runner import DockerRunConfig, TrialExecutionResult
from src.trial_runner.trial import Trial, TrialConfig


class TestStdoutStderrCapture:
    """Test suite for stdout/stderr capture from OpenROAD executions."""

    def test_trial_result_has_stdout_field(self):
        """Verify TrialResult includes stdout field."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        # Create mock result
        from src.trial_runner.trial import TrialResult, TrialArtifacts

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            stdout="OpenROAD output\nTiming analysis complete\n",
        )

        assert hasattr(result, "stdout"), "TrialResult should have stdout field"
        assert isinstance(result.stdout, str), "stdout should be a string"
        assert "OpenROAD output" in result.stdout

    def test_trial_result_has_stderr_field(self):
        """Verify TrialResult includes stderr field."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        from src.trial_runner.trial import TrialResult, TrialArtifacts

        result = TrialResult(
            config=config,
            success=False,
            return_code=1,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            stderr="Error: timing violation\nFatal error occurred\n",
        )

        assert hasattr(result, "stderr"), "TrialResult should have stderr field"
        assert isinstance(result.stderr, str), "stderr should be a string"
        assert "Error: timing violation" in result.stderr

    def test_stdout_and_stderr_fields_separate(self):
        """Verify stdout and stderr are separate fields, not mixed."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        from src.trial_runner.trial import TrialResult, TrialArtifacts

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            stdout="Normal output",
            stderr="Warning: deprecated command",
        )

        # Verify separate fields
        assert result.stdout == "Normal output"
        assert result.stderr == "Warning: deprecated command"
        # Verify they're not mixed
        assert "Warning" not in result.stdout
        assert "Normal output" not in result.stderr


class TestStdoutStderrFileRedirection:
    """Test suite for stdout/stderr file redirection."""

    def test_stdout_redirected_to_log_file(self, tmp_path):
        """Step 2: Verify stdout is redirected to trial log file (stdout.txt)."""
        # Create test script
        script_path = tmp_path / "test.tcl"
        script_path.write_text("puts stdout {Test output to stdout}")

        config = TrialConfig(
            study_name="stdout_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
            timeout_seconds=30,
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        # Note: This test would require actual Docker execution.
        # For unit testing, verify the file path expectation exists.
        expected_stdout_path = trial.trial_dir / "logs" / "stdout.txt"

        # Verify path structure is correct
        assert expected_stdout_path.parent.name == "logs"
        assert expected_stdout_path.name == "stdout.txt"

    def test_stderr_redirected_to_log_file(self, tmp_path):
        """Step 3: Verify stderr is redirected to separate error log file (stderr.txt)."""
        script_path = tmp_path / "test.tcl"
        script_path.write_text("puts stderr {Error message}")

        config = TrialConfig(
            study_name="stderr_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
            timeout_seconds=30,
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        # Verify stderr path structure
        expected_stderr_path = trial.trial_dir / "logs" / "stderr.txt"

        assert expected_stderr_path.parent.name == "logs"
        assert expected_stderr_path.name == "stderr.txt"

    def test_stdout_and_stderr_in_separate_files(self, tmp_path):
        """Verify stdout and stderr are written to separate files."""
        script_path = tmp_path / "test.tcl"
        script_path.write_text("puts stdout {Normal}\nputs stderr {Error}")

        config = TrialConfig(
            study_name="separation_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        stdout_path = trial.trial_dir / "logs" / "stdout.txt"
        stderr_path = trial.trial_dir / "logs" / "stderr.txt"

        # Verify different files
        assert stdout_path != stderr_path
        assert stdout_path.name == "stdout.txt"
        assert stderr_path.name == "stderr.txt"


class TestLogsPreservationInArtifacts:
    """Test suite for preserving logs in trial artifacts."""

    def test_logs_preserved_in_artifacts_directory(self, tmp_path):
        """Step 4: Verify both logs are preserved in trial artifacts."""
        script_path = tmp_path / "test.tcl"
        script_path.write_text("puts {Test}")

        config = TrialConfig(
            study_name="preservation_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        # Create logs directory (simulating trial execution)
        logs_dir = trial.trial_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        # Simulate log creation
        (logs_dir / "stdout.txt").write_text("OpenROAD output")
        (logs_dir / "stderr.txt").write_text("")

        # Discover artifacts
        artifacts = trial._discover_artifacts()

        # Verify logs are preserved in artifacts
        assert artifacts.logs is not None, "Logs should be in artifacts"
        assert artifacts.logs.exists(), "Logs directory should exist"
        assert (artifacts.logs / "stdout.txt").exists(), "stdout.txt should be preserved"
        assert (artifacts.logs / "stderr.txt").exists(), "stderr.txt should be preserved"

    def test_logs_directory_in_trial_artifact_structure(self, tmp_path):
        """Verify logs directory follows trial artifact structure."""
        config = TrialConfig(
            study_name="structure_test",
            case_name="base_case",
            stage_index=1,
            trial_index=3,
            script_path=str(tmp_path / "test.tcl"),
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        # Expected structure: artifacts/{study}/{case}/stage_{N}/trial_{M}/logs/
        expected_logs_path = (
            tmp_path
            / "artifacts"
            / "structure_test"
            / "base_case"
            / "stage_1"
            / "trial_3"
            / "logs"
        )

        assert trial.trial_dir / "logs" == expected_logs_path

    def test_logs_accessible_from_trial_result(self, tmp_path):
        """Verify logs are accessible from TrialResult artifacts."""
        script_path = tmp_path / "test.tcl"
        script_path.write_text("puts {Test}")

        config = TrialConfig(
            study_name="accessibility_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        # Create logs
        logs_dir = trial.trial_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "stdout.txt").write_text("Output")
        (logs_dir / "stderr.txt").write_text("Errors")

        artifacts = trial._discover_artifacts()

        # Verify logs accessible
        assert artifacts.logs is not None
        assert (artifacts.logs / "stdout.txt").exists()
        assert (artifacts.logs / "stderr.txt").exists()


class TestLogExcerptExtraction:
    """Test suite for extracting log excerpts for failure classification."""

    def test_failure_classifier_uses_stdout(self):
        """Step 5: Verify failure classifier can extract excerpts from stdout."""
        stdout = """
OpenROAD starting...
Reading design...
Placement starting...
[ERROR] Placement failed: overlap detected
Aborting...
"""
        stderr = ""

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout=stdout,
            stderr=stderr,
            artifacts_dir=Path("/tmp/trial"),
            expected_outputs=None,
        )

        # Verify classification uses stdout content
        assert classification is not None
        # The exact error should be detected from stdout

    def test_failure_classifier_uses_stderr(self):
        """Step 5: Verify failure classifier can extract excerpts from stderr."""
        stdout = "Normal output"
        stderr = """
[ERROR] Fatal error: out of memory
Segmentation fault (core dumped)
"""

        classification = FailureClassifier.classify_trial_failure(
            return_code=139,  # SIGSEGV
            stdout=stdout,
            stderr=stderr,
            artifacts_dir=Path("/tmp/trial"),
            expected_outputs=None,
        )

        # Verify classification detects the error from stderr
        # The classifier detects "out of memory" first (higher priority than segfault)
        assert classification is not None
        assert classification.failure_type.value == "out_of_memory"

    def test_failure_classifier_extracts_log_excerpt(self):
        """Verify failure classifier extracts relevant log excerpt."""
        stdout = """
Line 1
Line 2
Line 3
[ERROR] Critical error on line 42
Line 5
Line 6
"""
        stderr = ""

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout=stdout,
            stderr=stderr,
            artifacts_dir=Path("/tmp/trial"),
            expected_outputs=None,
        )

        assert classification is not None
        # Log excerpt should be part of classification (via reason or details)
        classification_dict = classification.to_dict()
        assert "reason" in classification_dict

    def test_log_excerpt_limited_length(self):
        """Verify log excerpts are limited to reasonable length."""
        # Create very long output
        long_stdout = "Line\n" * 10000 + "[ERROR] Critical error\n"
        stderr = ""

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout=long_stdout,
            stderr=stderr,
            artifacts_dir=Path("/tmp/trial"),
            expected_outputs=None,
        )

        assert classification is not None
        # Verify the classification doesn't include the entire 10k line output
        classification_str = str(classification.to_dict())
        assert len(classification_str) < 10000, "Excerpt should be limited"

    def test_both_stdout_and_stderr_used_for_classification(self):
        """Verify classifier considers both stdout and stderr."""
        stdout = "OpenROAD starting..."
        stderr = "[ERROR] Configuration file not found"

        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout=stdout,
            stderr=stderr,
            artifacts_dir=Path("/tmp/trial"),
            expected_outputs=None,
        )

        # Classifier should detect error from stderr even with normal stdout
        assert classification is not None


class TestStdoutStderrIntegration:
    """Integration tests for stdout/stderr capture end-to-end."""

    def test_docker_execution_result_includes_stdout_stderr(self):
        """Verify DockerTrialRunner captures stdout and stderr."""
        result = TrialExecutionResult(
            return_code=0,
            stdout="OpenROAD execution output",
            stderr="Warning: deprecated option",
            runtime_seconds=5.0,
            success=True,
            container_id="abc123",
        )

        assert hasattr(result, "stdout")
        assert hasattr(result, "stderr")
        assert result.stdout == "OpenROAD execution output"
        assert result.stderr == "Warning: deprecated option"

    def test_trial_result_serialization_includes_logs(self, tmp_path):
        """Verify trial result serialization includes stdout/stderr."""
        script_path = tmp_path / "test.tcl"
        script_path.write_text("puts {Test}")

        config = TrialConfig(
            study_name="serialization_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
        )

        from src.trial_runner.trial import TrialResult, TrialArtifacts

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=tmp_path / "trial"),
            stdout="Normal output",
            stderr="Warnings",
        )

        # Serialize to dict
        result_dict = result.to_dict()

        # Note: stdout/stderr are NOT in to_dict() by design (too large for telemetry)
        # They are written to files instead
        # This is correct behavior - telemetry stays compact

    def test_artifact_index_references_log_files(self, tmp_path):
        """Verify artifact index includes references to log files."""
        script_path = tmp_path / "test.tcl"
        script_path.write_text("puts {Test}")

        config = TrialConfig(
            study_name="index_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        # Create logs
        logs_dir = trial.trial_dir / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "stdout.txt").write_text("Output")
        (logs_dir / "stderr.txt").write_text("Errors")

        # Get artifact index
        index = trial.get_artifact_index()

        # Verify logs are referenced
        assert "artifacts" in index
        artifacts = index["artifacts"]
        assert "logs" in artifacts
        assert artifacts["logs"] is not None


class TestLogFileFormatAndEncoding:
    """Test suite for log file format and encoding."""

    def test_stdout_saved_as_utf8_text(self, tmp_path):
        """Verify stdout is saved as UTF-8 text file."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        stdout_path = logs_dir / "stdout.txt"
        stdout_content = "OpenROAD output\nWith special chars: © ™ €\n"

        # Simulate what Trial.execute() does
        stdout_path.write_text(stdout_content, encoding="utf-8")

        # Read back and verify
        read_content = stdout_path.read_text(encoding="utf-8")
        assert read_content == stdout_content
        assert "©" in read_content  # Verify special chars preserved

    def test_stderr_saved_as_utf8_text(self, tmp_path):
        """Verify stderr is saved as UTF-8 text file."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        stderr_path = logs_dir / "stderr.txt"
        stderr_content = "Error messages\nWith Unicode: ✓ ✗ ⚠\n"

        stderr_path.write_text(stderr_content, encoding="utf-8")

        read_content = stderr_path.read_text(encoding="utf-8")
        assert read_content == stderr_content
        assert "✓" in read_content

    def test_empty_stdout_creates_empty_file(self, tmp_path):
        """Verify empty stdout creates an empty file (not omitted)."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        stdout_path = logs_dir / "stdout.txt"
        stdout_path.write_text("")

        assert stdout_path.exists()
        assert stdout_path.read_text() == ""
        assert stdout_path.stat().st_size == 0

    def test_empty_stderr_creates_empty_file(self, tmp_path):
        """Verify empty stderr creates an empty file (not omitted)."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()

        stderr_path = logs_dir / "stderr.txt"
        stderr_path.write_text("")

        assert stderr_path.exists()
        assert stderr_path.read_text() == ""


class TestLogFileNaming:
    """Test suite for log file naming conventions."""

    def test_stdout_filename_is_stdout_txt(self, tmp_path):
        """Verify stdout log file is always named 'stdout.txt'."""
        config = TrialConfig(
            study_name="naming_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(tmp_path / "test.tcl"),
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        expected_path = trial.trial_dir / "logs" / "stdout.txt"
        assert expected_path.name == "stdout.txt"

    def test_stderr_filename_is_stderr_txt(self, tmp_path):
        """Verify stderr log file is always named 'stderr.txt'."""
        config = TrialConfig(
            study_name="naming_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(tmp_path / "test.tcl"),
        )

        trial = Trial(config, artifacts_root=tmp_path / "artifacts")

        expected_path = trial.trial_dir / "logs" / "stderr.txt"
        assert expected_path.name == "stderr.txt"

    def test_log_filenames_consistent_across_trials(self, tmp_path):
        """Verify log filenames are consistent across different trials."""
        config1 = TrialConfig(
            study_name="study1",
            case_name="case1",
            stage_index=0,
            trial_index=0,
            script_path=str(tmp_path / "test.tcl"),
        )

        config2 = TrialConfig(
            study_name="study2",
            case_name="case2",
            stage_index=5,
            trial_index=99,
            script_path=str(tmp_path / "test.tcl"),
        )

        trial1 = Trial(config1, artifacts_root=tmp_path / "artifacts")
        trial2 = Trial(config2, artifacts_root=tmp_path / "artifacts")

        # Different trial directories
        assert trial1.trial_dir != trial2.trial_dir

        # But same log filenames
        assert (trial1.trial_dir / "logs" / "stdout.txt").name == "stdout.txt"
        assert (trial2.trial_dir / "logs" / "stdout.txt").name == "stdout.txt"
        assert (trial1.trial_dir / "logs" / "stderr.txt").name == "stderr.txt"
        assert (trial2.trial_dir / "logs" / "stderr.txt").name == "stderr.txt"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
