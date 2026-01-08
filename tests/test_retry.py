"""Tests for retry logic with exponential backoff."""

import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)
from src.trial_runner.retry import (
    calculate_backoff_delay,
    execute_trial_with_retry,
    should_retry_failure,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


class TestBackoffCalculation:
    """Test exponential backoff delay calculation."""

    def test_backoff_increases_exponentially(self):
        """Verify backoff delay increases exponentially with attempts."""
        # Base = 2.0 seconds
        delays = [calculate_backoff_delay(i, base=2.0, max_delay=60.0) for i in range(5)]

        # Should follow: 2 * 2^0, 2 * 2^1, 2 * 2^2, 2 * 2^3, 2 * 2^4
        expected = [2.0, 4.0, 8.0, 16.0, 32.0]
        assert delays == expected

    def test_backoff_capped_at_max(self):
        """Verify backoff delay is capped at max_delay."""
        # With large attempts, should cap at max_delay
        delay = calculate_backoff_delay(10, base=2.0, max_delay=60.0)
        assert delay == 60.0

        # Multiple large attempts all cap
        for i in range(10, 20):
            assert calculate_backoff_delay(i, base=2.0, max_delay=60.0) == 60.0

    def test_backoff_custom_base(self):
        """Verify custom base multiplier works correctly."""
        # Base = 1.0 second
        delays = [calculate_backoff_delay(i, base=1.0, max_delay=100.0) for i in range(4)]
        expected = [1.0, 2.0, 4.0, 8.0]
        assert delays == expected

    def test_backoff_zero_attempt(self):
        """Verify attempt 0 gives base delay."""
        delay = calculate_backoff_delay(0, base=2.0, max_delay=60.0)
        assert delay == 2.0


class TestShouldRetryFailure:
    """Test retry decision logic."""

    def test_success_no_retry(self):
        """Successful trials should not be retried."""
        assert not should_retry_failure(None, retry_count=0, max_retries=3)

    def test_transient_failure_retries(self):
        """Transient failures should be retried if retries remain."""
        transient_failure = FailureClassification(
            failure_type=FailureType.NETWORK_ERROR,
            severity=FailureSeverity.MEDIUM,
            reason="Network timeout",
            recoverable=True,
        )

        assert should_retry_failure(transient_failure, retry_count=0, max_retries=3)
        assert should_retry_failure(transient_failure, retry_count=1, max_retries=3)
        assert should_retry_failure(transient_failure, retry_count=2, max_retries=3)

    def test_exhausted_retries_no_retry(self):
        """Should not retry after exhausting max_retries."""
        transient_failure = FailureClassification(
            failure_type=FailureType.NETWORK_ERROR,
            severity=FailureSeverity.MEDIUM,
            reason="Network timeout",
            recoverable=True,
        )

        assert not should_retry_failure(transient_failure, retry_count=3, max_retries=3)
        assert not should_retry_failure(transient_failure, retry_count=5, max_retries=3)

    def test_non_transient_failure_no_retry(self):
        """Non-transient failures should not be retried."""
        non_transient = FailureClassification(
            failure_type=FailureType.SEGFAULT,
            severity=FailureSeverity.CRITICAL,
            reason="Segmentation fault",
            recoverable=False,
        )

        assert not should_retry_failure(non_transient, retry_count=0, max_retries=3)

    def test_all_transient_failure_types_retry(self):
        """All transient failure types should be retryable."""
        transient_types = [
            FailureType.NETWORK_ERROR,
            FailureType.RESOURCE_BUSY,
            FailureType.CONTAINER_ERROR,
            FailureType.FILESYSTEM_ERROR,
        ]

        for failure_type in transient_types:
            failure = FailureClassification(
                failure_type=failure_type,
                severity=FailureSeverity.MEDIUM,
                reason="Transient issue",
                recoverable=True,
            )
            assert should_retry_failure(failure, retry_count=0, max_retries=3)


class TestExecuteTrialWithRetry:
    """Test trial execution with retry logic."""

    def _make_trial_config(self, max_retries: int = 3) -> TrialConfig:
        """Helper to create a TrialConfig for testing."""
        return TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            max_retries=max_retries,
            retry_backoff_base=0.1,  # Fast for testing
            retry_backoff_max=1.0,
        )

    def _make_success_result(self, config: TrialConfig) -> TrialResult:
        """Helper to create a successful TrialResult."""
        return TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
        )

    def _make_failure_result(
        self,
        config: TrialConfig,
        failure_type: FailureType,
        transient: bool = True,
    ) -> TrialResult:
        """Helper to create a failed TrialResult."""
        failure = FailureClassification(
            failure_type=failure_type,
            severity=FailureSeverity.MEDIUM if transient else FailureSeverity.CRITICAL,
            reason="Test failure",
            recoverable=transient,
        )

        return TrialResult(
            config=config,
            success=False,
            return_code=1,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            failure=failure,
        )

    def test_success_on_first_attempt(self):
        """Trial succeeds on first attempt - no retries."""
        config = self._make_trial_config()
        executor = MagicMock(return_value=self._make_success_result(config))

        result = execute_trial_with_retry(config, executor)

        assert result.success
        assert result.retry_count == 0
        assert len(result.retry_history) == 0
        executor.assert_called_once()

    def test_transient_failure_retries_until_success(self):
        """Transient failure retries and eventually succeeds."""
        config = self._make_trial_config(max_retries=3)

        # Fail twice, then succeed
        results = [
            self._make_failure_result(config, FailureType.NETWORK_ERROR),
            self._make_failure_result(config, FailureType.NETWORK_ERROR),
            self._make_success_result(config),
        ]
        executor = MagicMock(side_effect=results)

        start_time = time.time()
        result = execute_trial_with_retry(config, executor)
        elapsed = time.time() - start_time

        assert result.success
        assert result.retry_count == 2
        assert len(result.retry_history) == 2
        assert executor.call_count == 3

        # Verify backoff occurred (at least some delay)
        # 0.1 + 0.2 = 0.3 seconds minimum
        assert elapsed >= 0.3

        # Verify retry history
        assert result.retry_history[0]["attempt"] == 0
        assert result.retry_history[0]["failure_type"] == "network_error"
        assert result.retry_history[1]["attempt"] == 1

    def test_exhausts_retries_on_persistent_transient_failure(self):
        """Trial exhausts retries when transient failure persists."""
        config = self._make_trial_config(max_retries=2)

        # Always fail with transient error
        failure_result = self._make_failure_result(config, FailureType.RESOURCE_BUSY)
        executor = MagicMock(return_value=failure_result)

        result = execute_trial_with_retry(config, executor)

        assert not result.success
        assert result.retry_count == 2  # 0, 1, 2 = 3 total attempts
        assert len(result.retry_history) == 2
        assert executor.call_count == 3

    def test_non_transient_failure_no_retry(self):
        """Non-transient failure returns immediately without retry."""
        config = self._make_trial_config(max_retries=3)

        failure_result = self._make_failure_result(
            config, FailureType.SEGFAULT, transient=False
        )
        executor = MagicMock(return_value=failure_result)

        result = execute_trial_with_retry(config, executor)

        assert not result.success
        assert result.retry_count == 0
        assert len(result.retry_history) == 0
        executor.assert_called_once()

    def test_retry_history_records_all_attempts(self):
        """Retry history accurately records all failed attempts."""
        config = self._make_trial_config(max_retries=3)

        # Create different transient failures
        results = [
            self._make_failure_result(config, FailureType.NETWORK_ERROR),
            self._make_failure_result(config, FailureType.CONTAINER_ERROR),
            self._make_failure_result(config, FailureType.FILESYSTEM_ERROR),
            self._make_failure_result(config, FailureType.RESOURCE_BUSY),
        ]
        executor = MagicMock(side_effect=results)

        result = execute_trial_with_retry(config, executor)

        assert not result.success
        assert result.retry_count == 3
        assert len(result.retry_history) == 3

        # Verify failure types recorded
        assert result.retry_history[0]["failure_type"] == "network_error"
        assert result.retry_history[1]["failure_type"] == "container_error"
        assert result.retry_history[2]["failure_type"] == "filesystem_error"

        # Final result shows last failure
        assert result.failure.failure_type == FailureType.RESOURCE_BUSY

    def test_max_retries_zero_no_retry(self):
        """With max_retries=0, should not retry at all."""
        config = self._make_trial_config(max_retries=0)

        failure_result = self._make_failure_result(config, FailureType.NETWORK_ERROR)
        executor = MagicMock(return_value=failure_result)

        result = execute_trial_with_retry(config, executor)

        assert not result.success
        assert result.retry_count == 0
        assert len(result.retry_history) == 0
        executor.assert_called_once()


class TestFailureClassifierTransientDetection:
    """Test transient failure detection in FailureClassifier."""

    def test_network_error_detection(self):
        """Network errors should be classified as transient."""
        failure = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Error: connection timeout connecting to registry",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=[],
        )

        assert failure is not None
        assert failure.failure_type == FailureType.NETWORK_ERROR
        assert failure.recoverable
        assert FailureClassifier.is_transient(failure)

    def test_resource_busy_detection(self):
        """Resource busy errors should be classified as transient."""
        failure = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Error: resource temporarily unavailable, try again later",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=[],
        )

        assert failure is not None
        assert failure.failure_type == FailureType.RESOURCE_BUSY
        assert failure.recoverable
        assert FailureClassifier.is_transient(failure)

    def test_container_error_detection(self):
        """Container errors should be classified as transient."""
        failure = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="docker error: failed to create container sandbox",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=[],
        )

        assert failure is not None
        assert failure.failure_type == FailureType.CONTAINER_ERROR
        assert failure.recoverable
        assert FailureClassifier.is_transient(failure)

    def test_filesystem_error_detection(self):
        """Filesystem errors should be classified as transient."""
        failure = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Error: no space left on device",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=[],
        )

        assert failure is not None
        assert failure.failure_type == FailureType.FILESYSTEM_ERROR
        assert failure.recoverable
        assert FailureClassifier.is_transient(failure)

    def test_segfault_not_transient(self):
        """Segfaults should not be classified as transient."""
        failure = FailureClassifier.classify_trial_failure(
            return_code=139,
            stdout="",
            stderr="Segmentation fault (core dumped)",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=[],
        )

        assert failure is not None
        assert failure.failure_type == FailureType.SEGFAULT
        assert not failure.recoverable
        assert not FailureClassifier.is_transient(failure)

    def test_is_transient_helper(self):
        """Test is_transient helper method."""
        transient_types = [
            FailureType.NETWORK_ERROR,
            FailureType.RESOURCE_BUSY,
            FailureType.CONTAINER_ERROR,
            FailureType.FILESYSTEM_ERROR,
        ]

        for failure_type in transient_types:
            failure = FailureClassification(
                failure_type=failure_type,
                severity=FailureSeverity.MEDIUM,
                reason="Test",
                recoverable=True,
            )
            assert FailureClassifier.is_transient(failure)

        # Non-transient types
        non_transient_types = [
            FailureType.SEGFAULT,
            FailureType.OOM,
            FailureType.TOOL_CRASH,
            FailureType.PLACEMENT_FAILED,
        ]

        for failure_type in non_transient_types:
            failure = FailureClassification(
                failure_type=failure_type,
                severity=FailureSeverity.CRITICAL,
                reason="Test",
                recoverable=False,
            )
            assert not FailureClassifier.is_transient(failure)
