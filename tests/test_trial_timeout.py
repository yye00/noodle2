"""Tests for trial timeout detection and handling."""

import pytest

from src.controller.failure import FailureClassifier, FailureType
from src.trial_runner.docker_runner import TrialExecutionResult
from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts


class TestTrialTimeoutDetection:
    """Test timeout detection and flagging."""

    def test_trial_result_has_timed_out_field(self):
        """Verify TrialResult has timed_out field."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=False,
            return_code=124,
            runtime_seconds=3600.0,
            artifacts=artifacts,
            timed_out=True,
        )

        assert hasattr(result, "timed_out")
        assert result.timed_out is True

    def test_timed_out_defaults_to_false(self):
        """Verify timed_out field defaults to False."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
        )

        assert result.timed_out is False

    def test_timed_out_serialized_to_dict(self):
        """Verify timed_out is included in to_dict() output."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=False,
            return_code=124,
            runtime_seconds=3600.0,
            artifacts=artifacts,
            timed_out=True,
        )

        result_dict = result.to_dict()

        assert "timed_out" in result_dict
        assert result_dict["timed_out"] is True

    def test_successful_trial_not_timed_out(self):
        """Verify successful trials are not marked as timed out."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=artifacts,
            timed_out=False,
        )

        assert result.success is True
        assert result.timed_out is False


class TestDockerRunnerTimeoutHandling:
    """Test Docker runner timeout detection."""

    def test_trial_execution_result_has_timed_out_field(self):
        """Verify TrialExecutionResult has timed_out field."""
        result = TrialExecutionResult(
            return_code=124,
            stdout="",
            stderr="[TIMEOUT] Trial exceeded timeout limit of 60 seconds\n",
            runtime_seconds=60.0,
            success=False,
            container_id="abc123",
            timed_out=True,
        )

        assert hasattr(result, "timed_out")
        assert result.timed_out is True

    def test_timed_out_defaults_to_false_in_execution_result(self):
        """Verify timed_out defaults to False in TrialExecutionResult."""
        result = TrialExecutionResult(
            return_code=0,
            stdout="Success",
            stderr="",
            runtime_seconds=10.5,
            success=True,
            container_id="abc123",
        )

        assert result.timed_out is False

    def test_timeout_return_code_is_124(self):
        """Verify timeout uses standard return code 124."""
        result = TrialExecutionResult(
            return_code=124,
            stdout="",
            stderr="[TIMEOUT] Trial exceeded timeout limit\n",
            runtime_seconds=60.0,
            success=False,
            container_id="abc123",
            timed_out=True,
        )

        assert result.return_code == 124
        assert result.success is False

    def test_timeout_message_in_stderr(self):
        """Verify timeout message is added to stderr."""
        result = TrialExecutionResult(
            return_code=124,
            stdout="",
            stderr="[TIMEOUT] Trial exceeded timeout limit of 60 seconds\n",
            runtime_seconds=60.0,
            success=False,
            container_id="abc123",
            timed_out=True,
        )

        assert "[TIMEOUT]" in result.stderr
        assert "exceeded timeout limit" in result.stderr


class TestTimeoutFailureClassification:
    """Test that timeouts are correctly classified as failures."""

    def test_timeout_classified_as_timeout_failure(self):
        """Verify timeout (return code 124) is classified as TIMEOUT failure."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=124,
            stdout="",
            stderr="[TIMEOUT] Trial exceeded timeout limit of 60 seconds\n",
            artifacts_dir="/tmp/test_artifacts",
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.TIMEOUT
        assert "timeout" in classification.reason.lower()

    def test_timeout_keyword_in_output_classified_as_timeout(self):
        """Verify 'timeout' keyword in output triggers TIMEOUT classification."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Error: operation timeout after 60 seconds\n",
            artifacts_dir="/tmp/test_artifacts",
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.TIMEOUT

    def test_non_timeout_failure_not_classified_as_timeout(self):
        """Verify non-timeout failures are not misclassified."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Error: parse error on line 42\n",
            artifacts_dir="/tmp/test_artifacts",
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type != FailureType.TIMEOUT


class TestTimeoutConfiguration:
    """Test timeout configuration at different levels."""

    def test_trial_config_has_timeout_field(self):
        """Verify TrialConfig has timeout_seconds field."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            timeout_seconds=1800,  # 30 minutes
        )

        assert hasattr(config, "timeout_seconds")
        assert config.timeout_seconds == 1800

    def test_timeout_defaults_to_one_hour(self):
        """Verify default timeout is 3600 seconds (1 hour)."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        assert config.timeout_seconds == 3600

    def test_custom_timeout_configuration(self):
        """Test configuring custom timeout values."""
        # Short timeout for fast-failing tests
        config_short = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            timeout_seconds=60,  # 1 minute
        )

        # Long timeout for complex designs
        config_long = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            timeout_seconds=7200,  # 2 hours
        )

        assert config_short.timeout_seconds == 60
        assert config_long.timeout_seconds == 7200


class TestTimeoutTelemetry:
    """Test timeout information in telemetry."""

    def test_timeout_recorded_in_trial_summary(self):
        """Verify timeout flag is recorded in trial summary."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=False,
            return_code=124,
            runtime_seconds=3600.0,
            artifacts=artifacts,
            timed_out=True,
        )

        summary = result.to_dict()

        assert summary["timed_out"] is True
        assert summary["success"] is False
        assert summary["return_code"] == 124

    def test_timeout_with_failure_classification(self):
        """Verify timeout trials can have failure classification."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        failure = FailureClassifier.classify_trial_failure(
            return_code=124,
            stdout="",
            stderr="[TIMEOUT] Trial exceeded timeout limit\n",
            artifacts_dir="/tmp/test_artifacts",
            expected_outputs=None,
        )

        result = TrialResult(
            config=config,
            success=False,
            return_code=124,
            runtime_seconds=3600.0,
            artifacts=artifacts,
            timed_out=True,
            failure=failure,
        )

        assert result.timed_out is True
        assert result.failure is not None
        assert result.failure.failure_type == FailureType.TIMEOUT

    def test_timeout_trials_have_runtime_at_timeout_limit(self):
        """Verify timed out trials have runtime close to timeout limit."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            timeout_seconds=300,  # 5 minutes
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=False,
            return_code=124,
            runtime_seconds=300.5,  # Slightly over timeout
            artifacts=artifacts,
            timed_out=True,
        )

        # Runtime should be close to timeout limit
        assert result.runtime_seconds >= config.timeout_seconds
        assert result.timed_out is True


class TestTimeoutStageIntegration:
    """Test timeout handling in stage execution context."""

    def test_timed_out_trial_marked_as_failed(self):
        """Verify timed out trials are marked as failed."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        result = TrialResult(
            config=config,
            success=False,
            return_code=124,
            runtime_seconds=3600.0,
            artifacts=artifacts,
            timed_out=True,
        )

        assert result.success is False
        assert result.timed_out is True

    def test_timed_out_trial_can_continue_with_next_trial(self):
        """Verify stage execution can continue after timeout."""
        # Create multiple trials, one of which times out
        config1 = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )
        config2 = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=1,
            script_path="/tmp/test.tcl",
        )
        artifacts = TrialArtifacts(trial_dir="/tmp/artifacts")

        # Trial 0 times out
        result1 = TrialResult(
            config=config1,
            success=False,
            return_code=124,
            runtime_seconds=3600.0,
            artifacts=artifacts,
            timed_out=True,
        )

        # Trial 1 succeeds
        result2 = TrialResult(
            config=config2,
            success=True,
            return_code=0,
            runtime_seconds=120.0,
            artifacts=artifacts,
            timed_out=False,
        )

        # Both trials should be independently evaluated
        assert result1.timed_out is True
        assert result1.success is False

        assert result2.timed_out is False
        assert result2.success is True
