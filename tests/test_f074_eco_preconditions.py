"""Tests for F074: ECO preconditions can gate ECO application.

Feature steps:
1. Create ECO with precondition: requires_timing_issue: true
2. Run on case with no timing violations
3. Verify ECO is skipped (precondition not met)
4. Run on case with timing violations
5. Verify ECO is applied (precondition met)
"""

import pytest

from src.controller.eco import (
    ECO,
    ECOMetadata,
    ECOPrecondition,
    ECOResult,
)
from src.controller.types import ECOClass


class TestF074ECOPreconditions:
    """Test F074: ECO preconditions can gate ECO application."""

    def test_step_1_create_eco_with_precondition_requires_timing_issue(self) -> None:
        """Step 1: Create ECO with precondition: requires_timing_issue: true."""

        # Define precondition: requires timing issue (WNS < 0)
        def requires_timing_issue(metrics: dict) -> bool:
            """Check if design has timing violations."""
            wns = metrics.get("wns_ps", 0)
            return wns < 0  # True if there are timing violations

        precondition = ECOPrecondition(
            name="requires_timing_issue",
            description="ECO should only apply when timing violations exist",
            check=requires_timing_issue,
            parameters={"requires_timing_issue": True},
        )

        # Create ECO with precondition
        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix ECO\nrepair_timing -setup\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing violations only when they exist",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Verify ECO has precondition
        assert len(eco.metadata.preconditions) == 1
        assert eco.metadata.preconditions[0].name == "requires_timing_issue"
        assert eco.metadata.preconditions[0].parameters["requires_timing_issue"] is True

    def test_step_2_run_on_case_with_no_timing_violations(self) -> None:
        """Step 2: Run on case with no timing violations."""

        # Define precondition
        def requires_timing_issue(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < 0

        precondition = ECOPrecondition(
            name="requires_timing_issue",
            description="Requires timing violations",
            check=requires_timing_issue,
        )

        # Create ECO
        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Design with NO timing violations (WNS = 50ps, positive slack)
        design_metrics_no_violations = {"wns_ps": 50}

        # Evaluate preconditions
        satisfied, failures = eco.evaluate_preconditions(design_metrics_no_violations)

        # Verify preconditions are NOT satisfied
        assert not satisfied
        assert len(failures) == 1

    def test_step_3_verify_eco_is_skipped_when_precondition_not_met(self) -> None:
        """Step 3: Verify ECO is skipped (precondition not met)."""

        # Define precondition
        def requires_timing_issue(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < 0

        precondition = ECOPrecondition(
            name="requires_timing_issue",
            description="Requires timing violations",
            check=requires_timing_issue,
        )

        # Create ECO
        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Design with NO timing violations (WNS = 50ps)
        design_metrics_no_violations = {"wns_ps": 50}

        # Evaluate preconditions
        satisfied, failures = eco.evaluate_preconditions(design_metrics_no_violations)

        # Verify ECO should be skipped
        assert not satisfied, "ECO should be skipped when no timing violations exist"
        assert "requires_timing_issue" in failures

        # In a real execution, this would result in an ECOResult with:
        # - skipped_due_to_preconditions: True
        # - precondition_failures: ["requires_timing_issue"]

    def test_step_4_run_on_case_with_timing_violations(self) -> None:
        """Step 4: Run on case with timing violations."""

        # Define precondition
        def requires_timing_issue(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < 0

        precondition = ECOPrecondition(
            name="requires_timing_issue",
            description="Requires timing violations",
            check=requires_timing_issue,
        )

        # Create ECO
        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Design WITH timing violations (WNS = -800ps, negative slack)
        design_metrics_with_violations = {"wns_ps": -800}

        # Evaluate preconditions
        satisfied, failures = eco.evaluate_preconditions(design_metrics_with_violations)

        # Verify preconditions ARE satisfied
        assert satisfied
        assert len(failures) == 0

    def test_step_5_verify_eco_is_applied_when_precondition_met(self) -> None:
        """Step 5: Verify ECO is applied (precondition met)."""

        # Define precondition
        def requires_timing_issue(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < 0

        precondition = ECOPrecondition(
            name="requires_timing_issue",
            description="Requires timing violations",
            check=requires_timing_issue,
        )

        # Create ECO
        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix\nrepair_timing -setup\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Design WITH timing violations (WNS = -800ps)
        design_metrics_with_violations = {"wns_ps": -800}

        # Evaluate preconditions
        satisfied, failures = eco.evaluate_preconditions(design_metrics_with_violations)

        # Verify ECO should be applied
        assert satisfied, "ECO should be applied when timing violations exist"
        assert len(failures) == 0

        # Verify TCL can be generated (ECO would be applied)
        tcl = eco.generate_tcl()
        assert "repair_timing" in tcl


class TestF074PreconditionEdgeCases:
    """Test edge cases for ECO preconditions."""

    def test_eco_with_no_preconditions_always_applies(self) -> None:
        """Verify ECO with no preconditions is always applied."""

        class AlwaysApplyECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Always apply\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="always_apply",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Always applies",
            preconditions=[],  # No preconditions
        )

        eco = AlwaysApplyECO(metadata)

        # Evaluate with any metrics
        satisfied, failures = eco.evaluate_preconditions({"wns_ps": 50})
        assert satisfied
        assert len(failures) == 0

        satisfied, failures = eco.evaluate_preconditions({"wns_ps": -800})
        assert satisfied
        assert len(failures) == 0

    def test_multiple_preconditions_all_must_be_satisfied(self) -> None:
        """Verify all preconditions must be satisfied for ECO to apply."""

        def requires_timing_issue(metrics: dict) -> bool:
            return metrics.get("wns_ps", 0) < 0

        def requires_low_congestion(metrics: dict) -> bool:
            return metrics.get("congestion_overflow", 1.0) < 0.5

        preconditions = [
            ECOPrecondition(
                name="requires_timing_issue",
                description="Requires timing violations",
                check=requires_timing_issue,
            ),
            ECOPrecondition(
                name="requires_low_congestion",
                description="Requires low congestion",
                check=requires_low_congestion,
            ),
        ]

        class ConditionalECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Conditional ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="conditional_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Conditional application",
            preconditions=preconditions,
        )

        eco = ConditionalECO(metadata)

        # Case 1: Both preconditions satisfied
        satisfied, failures = eco.evaluate_preconditions({
            "wns_ps": -500,
            "congestion_overflow": 0.3,
        })
        assert satisfied
        assert len(failures) == 0

        # Case 2: Only timing issue (congestion too high)
        satisfied, failures = eco.evaluate_preconditions({
            "wns_ps": -500,
            "congestion_overflow": 0.8,
        })
        assert not satisfied
        assert "requires_low_congestion" in failures

        # Case 3: Only low congestion (no timing issue)
        satisfied, failures = eco.evaluate_preconditions({
            "wns_ps": 50,
            "congestion_overflow": 0.3,
        })
        assert not satisfied
        assert "requires_timing_issue" in failures

        # Case 4: Neither precondition satisfied
        satisfied, failures = eco.evaluate_preconditions({
            "wns_ps": 50,
            "congestion_overflow": 0.8,
        })
        assert not satisfied
        assert len(failures) == 2

    def test_precondition_with_threshold_parameter(self) -> None:
        """Test precondition with configurable threshold."""

        def check_wns_threshold(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            # Access threshold from closure (would be passed via precondition)
            threshold = -500
            return wns < threshold

        precondition = ECOPrecondition(
            name="wns_threshold",
            description="WNS must be worse than threshold",
            check=check_wns_threshold,
            parameters={"threshold_ps": -500},
        )

        class ThresholdECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Threshold ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="threshold_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Threshold-based ECO",
            preconditions=[precondition],
        )

        eco = ThresholdECO(metadata)

        # WNS = -300ps (better than -500ps threshold) -> should fail
        satisfied, _ = eco.evaluate_preconditions({"wns_ps": -300})
        assert not satisfied

        # WNS = -800ps (worse than -500ps threshold) -> should pass
        satisfied, _ = eco.evaluate_preconditions({"wns_ps": -800})
        assert satisfied

    def test_precondition_evaluation_handles_missing_metrics(self) -> None:
        """Test precondition evaluation with missing metrics."""

        def requires_timing_issue(metrics: dict) -> bool:
            # Use get() with default to handle missing metrics
            wns = metrics.get("wns_ps", 0)
            return wns < 0

        precondition = ECOPrecondition(
            name="requires_timing_issue",
            description="Requires timing violations",
            check=requires_timing_issue,
        )

        class RobustECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Robust ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="robust_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Handles missing metrics",
            preconditions=[precondition],
        )

        eco = RobustECO(metadata)

        # Empty metrics -> defaults to 0, precondition fails
        satisfied, _ = eco.evaluate_preconditions({})
        assert not satisfied

    def test_precondition_serialization(self) -> None:
        """Test precondition can be serialized to dict."""

        def check_wns(metrics: dict) -> bool:
            return metrics.get("wns_ps", 0) < -500

        precondition = ECOPrecondition(
            name="wns_check",
            description="Check WNS threshold",
            check=check_wns,
            parameters={"threshold": -500, "metric": "wns_ps"},
        )

        precondition_dict = precondition.to_dict()

        assert precondition_dict["name"] == "wns_check"
        assert precondition_dict["description"] == "Check WNS threshold"
        assert precondition_dict["parameters"]["threshold"] == -500
        assert precondition_dict["parameters"]["metric"] == "wns_ps"

    def test_eco_result_tracks_precondition_evaluation(self) -> None:
        """Test ECOResult can track precondition evaluation."""

        # Create a result indicating precondition failure
        result = ECOResult(
            eco_name="timing_fix",
            success=False,
            preconditions_satisfied=False,
            precondition_failures=["requires_timing_issue"],
            skipped_due_to_preconditions=True,
        )

        assert not result.preconditions_satisfied
        assert result.skipped_due_to_preconditions
        assert "requires_timing_issue" in result.precondition_failures

        # Verify serialization includes precondition info
        result_dict = result.to_dict()
        assert result_dict["preconditions_satisfied"] is False
        assert result_dict["skipped_due_to_preconditions"] is True
        assert "requires_timing_issue" in result_dict["precondition_failures"]
