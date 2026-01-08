"""Retry logic with exponential backoff for transient trial failures."""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Callable

from src.controller.failure import FailureClassification, FailureClassifier
from src.trial_runner.trial import TrialConfig, TrialResult

logger = logging.getLogger(__name__)


def calculate_backoff_delay(
    attempt: int,
    base: float = 2.0,
    max_delay: float = 60.0,
) -> float:
    """
    Calculate exponential backoff delay for retry attempt.

    Args:
        attempt: Current retry attempt number (0-indexed)
        base: Base multiplier for exponential backoff (seconds)
        max_delay: Maximum delay to cap backoff (seconds)

    Returns:
        Delay in seconds before next retry
    """
    # Exponential backoff: base * 2^attempt
    delay = base * (2**attempt)
    # Cap at max_delay
    return min(delay, max_delay)


def should_retry_failure(
    failure: FailureClassification | None,
    retry_count: int,
    max_retries: int,
) -> bool:
    """
    Determine if a trial should be retried based on its failure.

    Args:
        failure: FailureClassification from the trial
        retry_count: Number of retries already attempted
        max_retries: Maximum number of retries allowed

    Returns:
        True if trial should be retried, False otherwise
    """
    # No failure means success - don't retry
    if failure is None:
        return False

    # Exhausted retries
    if retry_count >= max_retries:
        return False

    # Only retry transient failures
    return FailureClassifier.is_transient(failure)


def execute_trial_with_retry(
    config: TrialConfig,
    trial_executor: Callable[[TrialConfig], TrialResult],
) -> TrialResult:
    """
    Execute a trial with retry logic for transient failures.

    This function wraps trial execution with exponential backoff retry logic.
    Transient failures (network errors, resource contention, etc.) will be
    retried up to max_retries times. Non-transient failures return immediately.

    Args:
        config: TrialConfig for the trial
        trial_executor: Function that executes the trial and returns TrialResult

    Returns:
        TrialResult with retry tracking information
    """
    retry_count = 0
    retry_history: list[dict[str, Any]] = []

    while True:
        # Log retry attempt
        if retry_count > 0:
            logger.info(
                f"Retry attempt {retry_count}/{config.max_retries} for "
                f"{config.study_name}/{config.case_name}/stage_{config.stage_index}/trial_{config.trial_index}"
            )

        # Execute trial
        result = trial_executor(config)

        # Add retry tracking to result
        result.retry_count = retry_count
        result.retry_history = retry_history.copy()

        # Check if we should retry
        if should_retry_failure(result.failure, retry_count, config.max_retries):
            # Record this attempt in history
            retry_record = {
                "attempt": retry_count,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "failure_type": result.failure.failure_type.value if result.failure else None,
                "failure_reason": result.failure.reason if result.failure else None,
                "return_code": result.return_code,
            }
            retry_history.append(retry_record)

            # Calculate backoff delay
            delay = calculate_backoff_delay(
                retry_count,
                base=config.retry_backoff_base,
                max_delay=config.retry_backoff_max,
            )

            logger.info(
                f"Transient failure detected ({result.failure.failure_type.value}). "
                f"Retrying after {delay:.1f}s backoff..."
            )

            # Wait before retry
            time.sleep(delay)

            # Increment retry counter
            retry_count += 1
            continue

        # Either success or non-transient failure - don't retry
        if result.failure and retry_count > 0:
            # Log final failure after retries
            if retry_count >= config.max_retries:
                logger.warning(
                    f"Trial failed after {retry_count} retries. "
                    f"Final failure: {result.failure.failure_type.value}"
                )
            else:
                logger.warning(
                    f"Non-transient failure ({result.failure.failure_type.value}). "
                    "Not retrying."
                )

        return result
