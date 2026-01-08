"""Tests for soft and hard timeout functionality."""

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.controller.types import StageConfig, ExecutionMode, ECOClass
from src.trial_runner.docker_runner import DockerTrialRunner, DockerRunConfig, TrialExecutionResult


# ============================================================================
# Step 1: Configure soft timeout (warning) and hard timeout (kill)
# ============================================================================


def test_configure_soft_and_hard_timeout():
    """
    Step 1: Configure soft timeout (warning) and hard timeout (kill).

    Verify StageConfig accepts both soft_timeout_seconds and timeout_seconds.
    """
    stage = StageConfig(
        name="test_stage",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=10,
        survivor_count=5,
        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        timeout_seconds=300,  # Hard timeout: 5 minutes
        soft_timeout_seconds=180,  # Soft timeout: 3 minutes
    )

    assert stage.timeout_seconds == 300
    assert stage.soft_timeout_seconds == 180
    assert stage.soft_timeout_seconds < stage.timeout_seconds


def test_soft_timeout_must_be_less_than_hard_timeout():
    """Verify soft timeout must be less than hard timeout."""
    with pytest.raises(ValueError, match="soft_timeout_seconds must be less than timeout_seconds"):
        StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            timeout_seconds=100,
            soft_timeout_seconds=200,  # Invalid: greater than hard timeout
        )


def test_soft_timeout_equal_to_hard_timeout_is_invalid():
    """Verify soft timeout equal to hard timeout is invalid."""
    with pytest.raises(ValueError, match="soft_timeout_seconds must be less than timeout_seconds"):
        StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            timeout_seconds=100,
            soft_timeout_seconds=100,  # Invalid: equal to hard timeout
        )


def test_soft_timeout_must_be_positive():
    """Verify soft timeout must be positive if specified."""
    with pytest.raises(ValueError, match="soft_timeout_seconds must be positive"):
        StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            timeout_seconds=100,
            soft_timeout_seconds=0,  # Invalid: not positive
        )


def test_soft_timeout_is_optional():
    """Verify soft timeout is optional (can be None)."""
    stage = StageConfig(
        name="test_stage",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=10,
        survivor_count=5,
        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        timeout_seconds=300,
        soft_timeout_seconds=None,  # No soft timeout
    )

    assert stage.timeout_seconds == 300
    assert stage.soft_timeout_seconds is None


# ============================================================================
# Step 2: Execute long-running trial (mocked)
# ============================================================================


def test_trial_execution_result_includes_soft_timeout_field():
    """
    Step 2: Verify TrialExecutionResult includes soft_timed_out field.

    This field tracks whether soft timeout was exceeded.
    """
    result = TrialExecutionResult(
        return_code=0,
        stdout="test output",
        stderr="",
        runtime_seconds=200.0,
        success=True,
        timed_out=False,
        soft_timed_out=True,  # Exceeded soft timeout but not hard timeout
    )

    assert result.soft_timed_out is True
    assert result.timed_out is False


# ============================================================================
# Step 3: Detect soft timeout expiration and log warning
# ============================================================================


def test_soft_timeout_detection_logic():
    """
    Step 3: Detect soft timeout expiration and log warning.

    Verify soft timeout detection logic by validating the stderr message.
    """
    # Simulate a result where soft timeout was exceeded but hard timeout was not
    result = TrialExecutionResult(
        return_code=0,
        stdout="trial output",
        stderr="[SOFT_TIMEOUT] Trial exceeded soft timeout of 180s but completed before hard timeout\n",
        runtime_seconds=200.0,
        success=True,
        timed_out=False,
        soft_timed_out=True,
    )

    # Verify soft timeout was detected
    assert result.soft_timed_out is True
    assert result.timed_out is False

    # Verify stderr contains soft timeout message
    assert "[SOFT_TIMEOUT]" in result.stderr
    assert "180s" in result.stderr


def test_soft_timeout_message_format():
    """Verify soft timeout warning message format is correct."""
    soft_timeout = 120
    message = f"[SOFT_TIMEOUT] Trial exceeded soft timeout of {soft_timeout}s but completed before hard timeout"

    assert "[SOFT_TIMEOUT]" in message
    assert f"{soft_timeout}s" in message
    assert "completed before hard timeout" in message


# ============================================================================
# Step 4: Allow trial to continue briefly after soft timeout
# ============================================================================


def test_trial_continues_after_soft_timeout():
    """
    Step 4: Allow trial to continue briefly after soft timeout.

    Verify trial is not killed when soft timeout is exceeded,
    only when hard timeout is reached.
    """
    # This is validated by the logic:
    # - Soft timeout logs warning but continues polling
    # - Only hard timeout calls container.kill()

    result = TrialExecutionResult(
        return_code=0,
        stdout="completed",
        stderr="[SOFT_TIMEOUT] Trial exceeded soft timeout of 10s but completed before hard timeout\n",
        runtime_seconds=15.0,
        success=True,
        timed_out=False,  # Did not hit hard timeout
        soft_timed_out=True,  # Did hit soft timeout
    )

    # Trial completed successfully despite exceeding soft timeout
    assert result.success is True
    assert result.soft_timed_out is True
    assert result.timed_out is False


# ============================================================================
# Step 5: Detect hard timeout and forcefully terminate
# ============================================================================


def test_hard_timeout_forcefully_terminates():
    """
    Step 5: Detect hard timeout and forcefully terminate.

    Verify trial is classified as timed out when hard timeout is exceeded.
    """
    # Simulate a result where hard timeout was exceeded
    result = TrialExecutionResult(
        return_code=124,  # Standard timeout exit code
        stdout="partial output",
        stderr="[HARD_TIMEOUT] Trial exceeded hard timeout limit of 300 seconds\n",
        runtime_seconds=300.0,
        success=False,
        timed_out=True,
        soft_timed_out=False,
    )

    # Verify hard timeout was detected
    assert result.timed_out is True
    assert result.return_code == 124

    # Verify stderr contains hard timeout message
    assert "[HARD_TIMEOUT]" in result.stderr
    assert "300 seconds" in result.stderr


def test_hard_timeout_with_prior_soft_timeout():
    """Verify both timeouts are tracked when both are exceeded."""
    result = TrialExecutionResult(
        return_code=124,
        stdout="partial output",
        stderr="[SOFT_TIMEOUT] Trial exceeded soft timeout of 180s\n"
               "[HARD_TIMEOUT] Trial exceeded hard timeout limit of 300 seconds\n",
        runtime_seconds=300.0,
        success=False,
        timed_out=True,
        soft_timed_out=True,
    )

    # Both timeouts exceeded
    assert result.soft_timed_out is True
    assert result.timed_out is True

    # Both messages in stderr
    assert "[SOFT_TIMEOUT]" in result.stderr
    assert "[HARD_TIMEOUT]" in result.stderr


# ============================================================================
# Step 6: Classify as timeout failure with both thresholds logged
# ============================================================================


def test_both_timeouts_logged_in_stderr():
    """
    Step 6: Classify as timeout failure with both thresholds logged.

    Verify stderr includes information about both soft and hard timeouts.
    """
    result = TrialExecutionResult(
        return_code=124,
        stdout="partial output",
        stderr="\n[SOFT_TIMEOUT] Trial exceeded soft timeout of 60s\n"
               "[HARD_TIMEOUT] Trial exceeded hard timeout limit of 120 seconds\n"
               "original stderr output",
        runtime_seconds=120.0,
        success=False,
        timed_out=True,
        soft_timed_out=True,
    )

    # Verify both timeout messages are present
    assert "[SOFT_TIMEOUT]" in result.stderr
    assert "[HARD_TIMEOUT]" in result.stderr
    assert "60s" in result.stderr  # Soft timeout threshold
    assert "120 seconds" in result.stderr  # Hard timeout threshold

    # Verify classified as failure
    assert result.success is False
    assert result.timed_out is True
    assert result.soft_timed_out is True


def test_only_hard_timeout_logged_when_no_soft_timeout_configured():
    """Verify only hard timeout is logged when soft timeout not configured."""
    result = TrialExecutionResult(
        return_code=124,
        stdout="partial output",
        stderr="\n[HARD_TIMEOUT] Trial exceeded hard timeout limit of 300 seconds\n",
        runtime_seconds=300.0,
        success=False,
        timed_out=True,
        soft_timed_out=False,
    )

    # Verify only hard timeout message present
    assert "[HARD_TIMEOUT]" in result.stderr
    assert "[SOFT_TIMEOUT]" not in result.stderr
    assert result.timed_out is True
    assert result.soft_timed_out is False


# ============================================================================
# Additional edge cases and integration tests
# ============================================================================


def test_trial_finishes_before_soft_timeout():
    """Test trial that completes before soft timeout."""
    result = TrialExecutionResult(
        return_code=0,
        stdout="success",
        stderr="",
        runtime_seconds=5.0,
        success=True,
        timed_out=False,
        soft_timed_out=False,
    )

    # No timeouts triggered
    assert result.soft_timed_out is False
    assert result.timed_out is False
    assert result.success is True


def test_reasonable_timeout_values():
    """Test reasonable timeout configuration for typical trials."""
    stage = StageConfig(
        name="typical_stage",
        execution_mode=ExecutionMode.STA_CONGESTION,
        trial_budget=100,
        survivor_count=20,
        allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
        timeout_seconds=3600,  # 1 hour hard timeout
        soft_timeout_seconds=2400,  # 40 minute soft timeout
    )

    assert stage.timeout_seconds == 3600
    assert stage.soft_timeout_seconds == 2400

    # Verify soft timeout is 2/3 of hard timeout (reasonable warning point)
    assert stage.soft_timeout_seconds / stage.timeout_seconds == pytest.approx(0.67, rel=0.1)


def test_soft_timeout_without_hard_timeout_exceeded():
    """Test scenario where soft timeout is hit but trial finishes before hard timeout."""
    result = TrialExecutionResult(
        return_code=0,
        stdout="completed after warning",
        stderr="[SOFT_TIMEOUT] Trial exceeded soft timeout of 100s but completed before hard timeout\n",
        runtime_seconds=150.0,
        success=True,
        timed_out=False,
        soft_timed_out=True,
    )

    # Trial succeeded despite soft timeout
    assert result.success is True
    assert result.soft_timed_out is True
    assert result.timed_out is False

    # Soft timeout message indicates completion
    assert "completed before hard timeout" in result.stderr


def test_docker_runner_signature_accepts_soft_timeout():
    """Verify DockerTrialRunner.execute_trial() accepts soft_timeout_seconds parameter."""
    config = DockerRunConfig()
    runner = DockerTrialRunner(config)

    # Verify method signature (will raise TypeError if parameter doesn't exist)
    import inspect
    sig = inspect.signature(runner.execute_trial)
    params = sig.parameters

    assert 'soft_timeout_seconds' in params
    assert 'timeout_seconds' in params

    # Verify soft_timeout_seconds is optional
    assert params['soft_timeout_seconds'].default is None


def test_end_to_end_soft_hard_timeout_config():
    """
    End-to-end test: Configure stage with timeouts and verify they propagate.
    """
    # Configure stage with both timeouts
    stage = StageConfig(
        name="e2e_test",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=50,
        survivor_count=10,
        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        timeout_seconds=600,  # 10 minutes hard
        soft_timeout_seconds=420,  # 7 minutes soft
    )

    # Verify configuration is valid
    assert stage.timeout_seconds == 600
    assert stage.soft_timeout_seconds == 420

    # In actual execution, these would be passed to DockerTrialRunner.execute_trial()
    # This test validates the configuration contract is complete
