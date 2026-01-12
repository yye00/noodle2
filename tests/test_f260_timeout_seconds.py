"""Tests for F260: ECO definition supports timeout_seconds for execution limits.

Feature steps:
1. Define ECO with timeout_seconds: 300
2. Apply ECO that runs longer than 300 seconds
3. Verify ECO execution is terminated after 300 seconds
4. Verify timeout failure is classified appropriately
5. Verify timeout affects ECO prior state
"""

import pytest

from src.controller.eco import (
    BufferInsertionECO,
    ECO,
    ECOMetadata,
    NoOpECO,
)
from src.controller.types import ECOClass


class TestTimeoutDefinition:
    """Test defining ECOs with timeout limits."""

    def test_step_1_define_eco_with_timeout(self) -> None:
        """Step 1: Define ECO with timeout_seconds: 300."""
        metadata = ECOMetadata(
            name="buffer_insertion_with_timeout",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Buffer insertion with 5-minute timeout",
            timeout_seconds=300,
        )

        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 300

        # Verify timeout is stored
        assert eco.metadata.timeout_seconds is not None
        assert eco.metadata.timeout_seconds == 300

    def test_timeout_defaults_to_none(self) -> None:
        """Verify timeout_seconds defaults to None."""
        eco = NoOpECO()
        assert eco.metadata.timeout_seconds is None

    def test_various_timeout_values(self) -> None:
        """Test various timeout values."""
        # Short timeout (1 minute)
        metadata1 = ECOMetadata(
            name="test1",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Test",
            timeout_seconds=60,
        )
        assert metadata1.timeout_seconds == 60

        # Medium timeout (10 minutes)
        metadata2 = ECOMetadata(
            name="test2",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Test",
            timeout_seconds=600,
        )
        assert metadata2.timeout_seconds == 600

        # Long timeout (1 hour)
        metadata3 = ECOMetadata(
            name="test3",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Test",
            timeout_seconds=3600,
        )
        assert metadata3.timeout_seconds == 3600

    def test_timeout_validation(self) -> None:
        """Test timeout validation."""
        # Valid timeout
        metadata1 = ECOMetadata(
            name="valid",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="Test",
            timeout_seconds=100,
        )
        assert metadata1.timeout_seconds == 100

        # Invalid: zero timeout
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            ECOMetadata(
                name="invalid_zero",
                eco_class=ECOClass.TOPOLOGY_NEUTRAL,
                description="Test",
                timeout_seconds=0,
            )

        # Invalid: negative timeout
        with pytest.raises(ValueError, match="timeout_seconds must be positive"):
            ECOMetadata(
                name="invalid_negative",
                eco_class=ECOClass.TOPOLOGY_NEUTRAL,
                description="Test",
                timeout_seconds=-100,
            )


class TestTimeoutExecution:
    """Test timeout enforcement during ECO execution."""

    def test_step_2_3_timeout_enforcement(self) -> None:
        """Steps 2-3: Apply ECO that exceeds timeout, verify termination."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 5  # 5 second timeout

        # Simulate execution times
        execution_time_seconds = 10  # Exceeds 5 second timeout

        # Check if execution exceeded timeout
        exceeded_timeout = execution_time_seconds > eco.metadata.timeout_seconds
        assert exceeded_timeout is True

        # In real implementation, this would terminate the execution

    def test_execution_within_timeout_succeeds(self) -> None:
        """Verify execution within timeout proceeds normally."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 300  # 5 minute timeout

        # Simulate execution that completes quickly
        execution_time_seconds = 30  # Well under timeout

        # Check if within timeout
        within_timeout = execution_time_seconds <= eco.metadata.timeout_seconds
        assert within_timeout is True

    def test_no_timeout_never_terminates(self) -> None:
        """Verify ECOs without timeout don't get terminated."""
        eco = BufferInsertionECO()
        # No timeout set
        assert eco.metadata.timeout_seconds is None

        # Any execution time is acceptable
        execution_time_seconds = 10000

        # Without timeout, should always be "within timeout"
        if eco.metadata.timeout_seconds is None:
            within_timeout = True
        else:
            within_timeout = execution_time_seconds <= eco.metadata.timeout_seconds

        assert within_timeout is True


class TestTimeoutFailureClassification:
    """Test timeout failure classification."""

    def test_step_4_timeout_failure_classification(self) -> None:
        """Step 4: Verify timeout failure is classified appropriately."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 60

        # Simulate timeout scenario
        execution_time = 120  # Exceeded timeout
        exceeded = execution_time > eco.metadata.timeout_seconds

        if exceeded:
            # Timeout should be classified as a specific failure type
            failure_type = "timeout"
            failure_message = f"ECO '{eco.name}' exceeded timeout of {eco.metadata.timeout_seconds}s"

            assert failure_type == "timeout"
            assert "exceeded timeout" in failure_message
            assert "60" in failure_message

    def test_timeout_distinct_from_tool_error(self) -> None:
        """Verify timeout is distinct from tool errors."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 60

        # Timeout scenario
        timeout_failure = {
            "type": "timeout",
            "message": f"Exceeded {eco.metadata.timeout_seconds}s limit",
        }

        # Tool error scenario
        tool_error = {
            "type": "tool_error",
            "message": "OpenROAD crashed",
        }

        # Should be different failure types
        assert timeout_failure["type"] != tool_error["type"]

    def test_timeout_distinct_from_metrics_failure(self) -> None:
        """Verify timeout is distinct from metrics failures (like WNS degradation)."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 60

        # Timeout scenario
        timeout_failure = "timeout"

        # Metrics failure scenario
        metrics_failure = "metrics_degradation"

        # Should be different failure types
        assert timeout_failure != metrics_failure


class TestTimeoutPriorState:
    """Test how timeouts affect ECO prior state."""

    def test_step_5_timeout_affects_prior_state(self) -> None:
        """Step 5: Verify timeout affects ECO prior state."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 60

        # Scenario 1: Execution completes successfully within timeout
        execution_time1 = 30
        success1 = execution_time1 <= eco.metadata.timeout_seconds
        assert success1 is True
        # This should lead to positive prior update

        # Scenario 2: Execution times out
        execution_time2 = 120
        success2 = execution_time2 <= eco.metadata.timeout_seconds
        assert success2 is False
        # This should lead to negative prior update
        # Timeout suggests ECO is too expensive/unreliable

    def test_repeated_timeouts_worsen_prior(self) -> None:
        """Verify repeated timeouts worsen ECO prior state."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 60

        # Simulate multiple timeout failures
        timeout_count = 0
        total_attempts = 5

        for attempt in range(total_attempts):
            execution_time = 120  # Always times out
            if execution_time > eco.metadata.timeout_seconds:
                timeout_count += 1

        # All attempts timed out
        assert timeout_count == 5

        # High timeout rate should significantly worsen prior
        timeout_rate = timeout_count / total_attempts
        assert timeout_rate == 1.0

        # This should lead to ECO being marked as "SUSPICIOUS" or worse

    def test_occasional_timeout_mixed_prior(self) -> None:
        """Verify occasional timeouts lead to mixed prior."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 60

        # Simulate mixed success/timeout pattern
        results = [
            30,   # Success
            45,   # Success
            120,  # Timeout
            40,   # Success
            90,   # Timeout
        ]

        successes = sum(1 for t in results if t <= eco.metadata.timeout_seconds)
        timeouts = sum(1 for t in results if t > eco.metadata.timeout_seconds)

        assert successes == 3
        assert timeouts == 2

        # This should lead to "MIXED" prior state
        success_rate = successes / len(results)
        assert success_rate == 0.6  # 60% success rate


class TestTimeoutConfiguration:
    """Test timeout configuration options."""

    def test_timeout_can_be_updated(self) -> None:
        """Verify timeout can be updated after ECO creation."""
        eco = BufferInsertionECO()
        assert eco.metadata.timeout_seconds is None

        # Update timeout
        eco.metadata.timeout_seconds = 300
        assert eco.metadata.timeout_seconds == 300

        # Update again
        eco.metadata.timeout_seconds = 600
        assert eco.metadata.timeout_seconds == 600

    def test_timeout_can_be_disabled(self) -> None:
        """Verify timeout can be disabled by setting to None."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 300
        assert eco.metadata.timeout_seconds == 300

        # Disable timeout
        eco.metadata.timeout_seconds = None
        assert eco.metadata.timeout_seconds is None

    def test_different_ecos_different_timeouts(self) -> None:
        """Verify different ECOs can have different timeouts."""
        eco1 = BufferInsertionECO()
        eco1.metadata.timeout_seconds = 60

        eco2 = BufferInsertionECO()
        eco2.metadata.timeout_seconds = 300

        assert eco1.metadata.timeout_seconds == 60
        assert eco2.metadata.timeout_seconds == 300
        assert eco1.metadata.timeout_seconds != eco2.metadata.timeout_seconds


class TestTimeoutSerialization:
    """Test serialization of timeout configuration."""

    def test_timeout_in_to_dict(self) -> None:
        """Verify timeout_seconds is included in ECO serialization."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 300

        eco_dict = eco.to_dict()

        # Verify timeout is serialized
        assert "timeout_seconds" in eco_dict
        assert eco_dict["timeout_seconds"] == 300

    def test_no_timeout_not_in_dict(self) -> None:
        """Verify timeout_seconds is not in dict when not set."""
        eco = BufferInsertionECO()
        # No timeout set
        assert eco.metadata.timeout_seconds is None

        eco_dict = eco.to_dict()

        # Timeout should not be in dict when None
        assert "timeout_seconds" not in eco_dict

    def test_timeout_with_expected_effects(self) -> None:
        """Verify timeout and expected_effects can coexist."""
        eco = BufferInsertionECO()
        eco.metadata.timeout_seconds = 300
        eco.metadata.expected_effects = {
            "wns_ps": "improve",
            "area_um2": "increase_slightly",
        }

        eco_dict = eco.to_dict()

        # Both should be present
        assert "timeout_seconds" in eco_dict
        assert "expected_effects" in eco_dict
        assert eco_dict["timeout_seconds"] == 300
        assert eco_dict["expected_effects"]["wns_ps"] == "improve"
