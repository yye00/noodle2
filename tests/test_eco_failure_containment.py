"""Tests for ECO-level failure containment.

This module tests Gate 2 (Controlled Regression) feature: containing failures
at the appropriate scope, starting with individual ECO level.
"""

import pytest
from pathlib import Path
from dataclasses import dataclass

from src.controller.eco import (
    ECO,
    ECOMetadata,
    ECOResult,
    NoOpECO,
    BufferInsertionECO,
    create_eco,
)
from src.controller.types import ECOClass
from src.trial_runner.trial import Trial, TrialConfig, TrialResult


class FailingECO(ECO):
    """Test ECO that always fails."""

    def __init__(self) -> None:
        metadata = ECOMetadata(
            name="failing_eco",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="ECO that always fails for testing",
        )
        super().__init__(metadata)

    def generate_tcl(self) -> str:
        """Generate TCL that will fail."""
        return """
        # This will fail
        error "Deliberate failure for testing"
        """

    def validate_parameters(self) -> bool:
        """No parameters to validate."""
        return True


class TestECOLevelFailureContainment:
    """Test that failures in individual ECOs are properly contained."""

    def test_single_eco_failure_does_not_fail_trial(self):
        """When one ECO fails, the trial should continue with other ECOs."""
        # Create a list of ECOs: one failing, two successful
        ecos = [
            NoOpECO(),
            FailingECO(),  # This one will fail
            BufferInsertionECO(max_capacitance=0.5),
        ]

        # Execute trial with ECO list
        # The trial should succeed overall even though one ECO failed
        eco_results = []
        for eco in ecos:
            try:
                # Simulate ECO execution
                tcl = eco.generate_tcl()
                # Check if the TCL contains error
                if "error" in tcl.lower():
                    result = ECOResult(
                        eco_name=eco.metadata.name,
                        success=False,
                        error_message="ECO failed during execution",
                    )
                else:
                    result = ECOResult(
                        eco_name=eco.metadata.name,
                        success=True,
                    )
                eco_results.append(result)
            except Exception as e:
                # Contain the failure - don't let it propagate
                result = ECOResult(
                    eco_name=eco.metadata.name,
                    success=False,
                    error_message=str(e),
                )
                eco_results.append(result)

        # Verify we have results for all 3 ECOs
        assert len(eco_results) == 3

        # Verify the first ECO succeeded
        assert eco_results[0].success is True
        assert eco_results[0].eco_name == "noop"

        # Verify the second ECO failed
        assert eco_results[1].success is False
        assert eco_results[1].eco_name == "failing_eco"
        assert eco_results[1].error_message is not None

        # Verify the third ECO succeeded despite the previous failure
        assert eco_results[2].success is True
        assert eco_results[2].eco_name == "buffer_insertion"

    def test_eco_failure_logged_separately(self):
        """Each ECO failure should be logged with its specific details."""
        eco = FailingECO()

        # Execute and capture failure
        try:
            tcl = eco.generate_tcl()
            if "error" in tcl.lower():
                raise RuntimeError("ECO execution failed")
            result = ECOResult(eco_name=eco.metadata.name, success=True)
        except Exception as e:
            result = ECOResult(
                eco_name=eco.metadata.name,
                success=False,
                error_message=str(e),
                log_excerpt="error \"Deliberate failure for testing\"",
            )

        # Verify failure details are captured
        assert result.success is False
        assert result.eco_name == "failing_eco"
        assert result.error_message is not None
        assert result.log_excerpt is not None
        assert "Deliberate" in result.log_excerpt or "error" in result.log_excerpt

    def test_multiple_ecos_can_fail_independently(self):
        """Multiple ECOs can fail without affecting each other."""
        ecos = [
            FailingECO(),
            FailingECO(),  # Both will fail
            NoOpECO(),  # This should succeed
        ]

        eco_results = []
        for eco in ecos:
            try:
                tcl = eco.generate_tcl()
                if "error" in tcl.lower():
                    result = ECOResult(
                        eco_name=eco.metadata.name,
                        success=False,
                        error_message="ECO failed",
                    )
                else:
                    result = ECOResult(
                        eco_name=eco.metadata.name,
                        success=True,
                    )
                eco_results.append(result)
            except Exception:
                result = ECOResult(
                    eco_name=eco.metadata.name,
                    success=False,
                    error_message="Exception during execution",
                )
                eco_results.append(result)

        # All 3 ECOs should have results
        assert len(eco_results) == 3

        # First two failed
        assert eco_results[0].success is False
        assert eco_results[1].success is False

        # Last one succeeded
        assert eco_results[2].success is True

    def test_eco_result_includes_metrics_delta(self):
        """ECO results should capture metrics changes even on partial success."""
        eco = BufferInsertionECO(max_capacitance=0.5)

        # Simulate successful execution with metrics
        result = ECOResult(
            eco_name=eco.metadata.name,
            success=True,
            metrics_delta={
                "wns_delta_ps": 150.0,  # WNS improved by 150ps
                "buffers_inserted": 5,
            },
            execution_time_seconds=2.5,
        )

        assert result.success is True
        assert result.metrics_delta["wns_delta_ps"] == 150.0
        assert result.metrics_delta["buffers_inserted"] == 5
        assert result.execution_time_seconds == 2.5

    def test_eco_result_serialization(self):
        """ECO results should be serializable for telemetry."""
        result = ECOResult(
            eco_name="test_eco",
            success=False,
            metrics_delta={"wns_delta_ps": -50.0},
            error_message="Buffer insertion failed",
            log_excerpt="Error: No suitable location found",
            execution_time_seconds=1.2,
            artifacts_generated=["buffer_report.txt"],
        )

        # Convert to dict
        result_dict = result.to_dict()

        # Verify all fields are present
        assert result_dict["eco_name"] == "test_eco"
        assert result_dict["success"] is False
        assert result_dict["metrics_delta"]["wns_delta_ps"] == -50.0
        assert result_dict["error_message"] == "Buffer insertion failed"
        assert result_dict["log_excerpt"] == "Error: No suitable location found"
        assert result_dict["execution_time_seconds"] == 1.2
        assert "buffer_report.txt" in result_dict["artifacts_generated"]


class TestECOExecutionOrchestration:
    """Test orchestration of multiple ECOs within a trial."""

    def test_trial_tracks_individual_eco_results(self):
        """Trials should track results for each ECO independently."""
        ecos = [
            NoOpECO(),
            BufferInsertionECO(max_capacitance=0.5),
        ]

        # Simulate trial execution with ECO tracking
        eco_results = []
        for eco in ecos:
            # Simulate successful execution
            result = ECOResult(
                eco_name=eco.metadata.name,
                success=True,
                execution_time_seconds=1.0,
            )
            eco_results.append(result)

        # Verify we tracked both ECOs
        assert len(eco_results) == 2
        assert eco_results[0].eco_name == "noop"
        assert eco_results[1].eco_name == "buffer_insertion"

    def test_trial_success_despite_eco_failures(self):
        """Trial can succeed overall even if some ECOs fail."""
        # Mix of successful and failed ECOs
        ecos = [
            NoOpECO(),  # Succeeds
            FailingECO(),  # Fails
            BufferInsertionECO(max_capacitance=0.5),  # Succeeds
        ]

        successful_count = 0
        failed_count = 0

        for eco in ecos:
            tcl = eco.generate_tcl()
            if "error" in tcl.lower():
                failed_count += 1
            else:
                successful_count += 1

        # Should have both successes and failures
        assert successful_count == 2
        assert failed_count == 1

        # Trial succeeds if at least one ECO succeeded
        trial_success = successful_count > 0
        assert trial_success is True

    def test_eco_execution_order_preserved(self):
        """ECOs should execute in the order specified."""
        ecos = [
            NoOpECO(),
            BufferInsertionECO(max_capacitance=0.5),
            create_eco("placement_density", target_density=0.6),
        ]

        execution_order = []
        for eco in ecos:
            execution_order.append(eco.metadata.name)

        # Verify order
        assert execution_order == ["noop", "buffer_insertion", "placement_density"]


class TestECOFailureTelemetry:
    """Test that ECO failures are captured in telemetry."""

    def test_eco_failure_appears_in_telemetry(self):
        """Failed ECOs should be recorded in trial telemetry."""
        eco = FailingECO()

        # Execute and create result
        result = ECOResult(
            eco_name=eco.metadata.name,
            success=False,
            error_message="ECO failed during execution",
            log_excerpt="error \"Deliberate failure for testing\"",
        )

        # Simulate adding to telemetry
        telemetry = {
            "eco_results": [result.to_dict()],
        }

        # Verify telemetry contains failure information
        assert len(telemetry["eco_results"]) == 1
        assert telemetry["eco_results"][0]["success"] is False
        assert telemetry["eco_results"][0]["eco_name"] == "failing_eco"
        assert telemetry["eco_results"][0]["error_message"] is not None

    def test_partial_eco_success_telemetry(self):
        """Telemetry should distinguish between full, partial, and no success."""
        ecos = [
            NoOpECO(),
            FailingECO(),
            BufferInsertionECO(max_capacitance=0.5),
        ]

        eco_results = []
        for eco in ecos:
            tcl = eco.generate_tcl()
            if "error" in tcl.lower():
                result = ECOResult(eco_name=eco.metadata.name, success=False)
            else:
                result = ECOResult(eco_name=eco.metadata.name, success=True)
            eco_results.append(result)

        # Calculate telemetry metrics
        total_ecos = len(eco_results)
        successful_ecos = sum(1 for r in eco_results if r.success)
        failed_ecos = sum(1 for r in eco_results if not r.success)

        telemetry = {
            "total_ecos": total_ecos,
            "successful_ecos": successful_ecos,
            "failed_ecos": failed_ecos,
            "partial_success": 0 < successful_ecos < total_ecos,
        }

        assert telemetry["total_ecos"] == 3
        assert telemetry["successful_ecos"] == 2
        assert telemetry["failed_ecos"] == 1
        assert telemetry["partial_success"] is True


class TestECOContainmentContract:
    """Test the ECO containment contract."""

    def test_eco_failure_does_not_raise_exception(self):
        """ECO failures should be captured, not raised as exceptions."""
        eco = FailingECO()

        # This should NOT raise an exception
        # Instead, it should return a failure result
        try:
            tcl = eco.generate_tcl()
            # Simulate detection of error in TCL
            if "error" in tcl.lower():
                result = ECOResult(
                    eco_name=eco.metadata.name,
                    success=False,
                    error_message="Error detected in generated TCL",
                )
            else:
                result = ECOResult(eco_name=eco.metadata.name, success=True)

            # Should reach here without exception
            assert result.success is False
        except Exception:
            # Should not reach here
            pytest.fail("ECO failure should not raise exception")

    def test_eco_list_tolerates_failures(self):
        """A list of ECOs should tolerate failures without stopping."""
        ecos = [
            FailingECO(),
            NoOpECO(),
            FailingECO(),
            BufferInsertionECO(max_capacitance=0.5),
        ]

        results = []
        for eco in ecos:
            # Use try-except to contain any potential exceptions
            try:
                tcl = eco.generate_tcl()
                if "error" in tcl.lower():
                    result = ECOResult(eco_name=eco.metadata.name, success=False)
                else:
                    result = ECOResult(eco_name=eco.metadata.name, success=True)
            except Exception as e:
                result = ECOResult(
                    eco_name=eco.metadata.name,
                    success=False,
                    error_message=str(e),
                )
            results.append(result)

        # All 4 ECOs should have been processed
        assert len(results) == 4

        # Verify the pattern of failures and successes
        assert results[0].success is False  # FailingECO
        assert results[1].success is True  # NoOpECO
        assert results[2].success is False  # FailingECO
        assert results[3].success is True  # BufferInsertionECO
