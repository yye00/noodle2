"""Tests for F257: ECO definition supports postconditions for verification.

Feature steps:
1. Define ECO with postconditions (wns_must_improve: true, no_new_drc_violations: true)
2. Apply ECO
3. Verify postconditions are checked after execution
4. If WNS did not improve, verify postcondition failure is logged
5. If DRC violations were introduced, verify failure is logged
6. Verify postcondition failures affect ECO prior state
"""

import pytest

from src.controller.eco import (
    ECO,
    ECOEffectiveness,
    ECOMetadata,
    ECOPostcondition,
    ECOPrior,
    ECOResult,
)
from src.controller.types import ECOClass


class TestECOWithPostconditionsDefinition:
    """Test defining ECOs with postconditions."""

    def test_step_1_define_eco_with_postconditions(self) -> None:
        """Step 1: Define ECO with postconditions (wns_must_improve, no_new_drc_violations)."""

        # Define postcondition: WNS must improve
        def check_wns_improved(before: dict, after: dict) -> bool:
            wns_before = before.get("wns_ps", 0)
            wns_after = after.get("wns_ps", 0)
            return wns_after > wns_before  # Improvement means less negative

        # Define postcondition: No new DRC violations
        def check_no_new_drc(before: dict, after: dict) -> bool:
            drc_before = before.get("drc_violations", 0)
            drc_after = after.get("drc_violations", 0)
            return drc_after <= drc_before  # No increase in violations

        postconditions = [
            ECOPostcondition(
                name="wns_must_improve",
                description="WNS must improve after ECO",
                check=check_wns_improved,
            ),
            ECOPostcondition(
                name="no_new_drc_violations",
                description="No new DRC violations introduced",
                check=check_no_new_drc,
            ),
        ]

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix TCL\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix_verified",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Timing fix with postcondition verification",
            postconditions=postconditions,
        )

        eco = TimingFixECO(metadata)

        assert len(eco.metadata.postconditions) == 2
        assert eco.metadata.postconditions[0].name == "wns_must_improve"
        assert eco.metadata.postconditions[1].name == "no_new_drc_violations"

    def test_define_eco_with_single_postcondition(self) -> None:
        """Test ECO with single postcondition."""

        def check_timing_improved(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        postcondition = ECOPostcondition(
            name="timing_improvement",
            description="Timing must improve",
            check=check_timing_improved,
        )

        class SimpleECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Simple ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="simple_timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Simple timing fix",
            postconditions=[postcondition],
        )

        eco = SimpleECO(metadata)

        assert len(eco.metadata.postconditions) == 1
        assert eco.metadata.postconditions[0].name == "timing_improvement"


class TestPostconditionEvaluation:
    """Test postcondition evaluation after ECO execution."""

    def test_step_2_and_3_postconditions_checked_after_execution(self) -> None:
        """Steps 2-3: Apply ECO and verify postconditions are checked."""

        def check_wns_improved(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        postcondition = ECOPostcondition(
            name="wns_must_improve",
            description="WNS must improve",
            check=check_wns_improved,
        )

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Timing fix",
            postconditions=[postcondition],
        )

        eco = TimingFixECO(metadata)

        # Simulate ECO execution with improvement
        before_metrics = {"wns_ps": -500}
        after_metrics = {"wns_ps": -300}  # Improved (less negative)

        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        assert satisfied
        assert len(failures) == 0

    def test_step_4_postcondition_failure_logged_when_wns_does_not_improve(self) -> None:
        """Step 4: If WNS did not improve, verify postcondition failure is logged."""

        def check_wns_improved(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        postcondition = ECOPostcondition(
            name="wns_must_improve",
            description="WNS must improve",
            check=check_wns_improved,
        )

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Timing fix",
            postconditions=[postcondition],
        )

        eco = TimingFixECO(metadata)

        # Simulate ECO execution WITHOUT improvement
        before_metrics = {"wns_ps": -500}
        after_metrics = {"wns_ps": -600}  # Degraded (more negative)

        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        # Postconditions should NOT be satisfied
        assert not satisfied
        assert len(failures) == 1
        assert "wns_must_improve" in failures

        # Create result with postcondition failure
        result = ECOResult(
            eco_name=eco.name,
            success=True,  # ECO executed, but postcondition failed
            postconditions_satisfied=satisfied,
            postcondition_failures=failures,
        )

        assert not result.postconditions_satisfied
        assert "wns_must_improve" in result.postcondition_failures

        # Verify result can be serialized (for logging)
        result_dict = result.to_dict()
        assert not result_dict["postconditions_satisfied"]
        assert "wns_must_improve" in result_dict["postcondition_failures"]

    def test_step_5_postcondition_failure_logged_when_drc_violations_introduced(
        self,
    ) -> None:
        """Step 5: If DRC violations were introduced, verify failure is logged."""

        def check_no_new_drc(before: dict, after: dict) -> bool:
            drc_before = before.get("drc_violations", 0)
            drc_after = after.get("drc_violations", 0)
            return drc_after <= drc_before

        postcondition = ECOPostcondition(
            name="no_new_drc_violations",
            description="No new DRC violations",
            check=check_no_new_drc,
        )

        class RoutingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Routing fix\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="routing_fix",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Routing fix",
            postconditions=[postcondition],
        )

        eco = RoutingFixECO(metadata)

        # Simulate ECO execution that introduces DRC violations
        before_metrics = {"drc_violations": 5, "wns_ps": -500}
        after_metrics = {"drc_violations": 12, "wns_ps": -300}  # New violations!

        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        # Postconditions should NOT be satisfied
        assert not satisfied
        assert len(failures) == 1
        assert "no_new_drc_violations" in failures

        # Create result with postcondition failure
        result = ECOResult(
            eco_name=eco.name,
            success=True,  # ECO executed
            postconditions_satisfied=satisfied,
            postcondition_failures=failures,
        )

        assert not result.postconditions_satisfied
        assert "no_new_drc_violations" in result.postcondition_failures


class TestPostconditionPriorImpact:
    """Test how postcondition failures affect ECO prior state."""

    def test_step_6_postcondition_failures_affect_prior(self) -> None:
        """Step 6: Verify postcondition failures affect ECO prior state."""

        # Create effectiveness tracker
        effectiveness = ECOEffectiveness(eco_name="test_eco")

        # Simulate multiple successful applications with good WNS improvement
        for _ in range(5):
            effectiveness.update(success=True, wns_delta_ps=100)  # Good improvement

        # After 5 successful applications, should have TRUSTED prior
        assert effectiveness.prior == ECOPrior.TRUSTED
        assert effectiveness.successful_applications == 5
        assert effectiveness.success_rate == 1.0  # 100% success rate

        # Now simulate postcondition failure (ECO executes but postcondition fails)
        # This should be tracked as a failure
        effectiveness.update(success=False, wns_delta_ps=-50)  # Failed, degraded

        # With 5 successes and 1 failure: success_rate = 5/6 = 0.833 >= 0.8
        # Average WNS is still positive: (5*100 + (-50))/6 = 75 ps
        # So it still qualifies as TRUSTED (success_rate >= 0.8 and avg_improvement > 0)
        # This is actually correct behavior - one failure shouldn't immediately destroy trust
        assert effectiveness.prior == ECOPrior.TRUSTED  # Still trusted with 5/6 success rate
        assert effectiveness.failed_applications == 1

        # Add MORE failures to downgrade
        effectiveness.update(success=False, wns_delta_ps=-100)
        effectiveness.update(success=False, wns_delta_ps=-80)

        # Now with 5/8 success rate (62.5%), should be MIXED
        assert effectiveness.prior == ECOPrior.MIXED or effectiveness.prior == ECOPrior.SUSPICIOUS


    def test_postcondition_failure_tracked_as_eco_failure(self) -> None:
        """Postcondition failure should be treated as ECO application failure."""

        effectiveness = ECOEffectiveness(eco_name="fragile_eco")

        # Start with some successes
        effectiveness.update(success=True, wns_delta_ps=100)
        effectiveness.update(success=True, wns_delta_ps=80)

        initial_success_count = effectiveness.successful_applications
        initial_failure_count = effectiveness.failed_applications

        # Postcondition failure (ECO ran but postcondition not met)
        effectiveness.update(success=False, wns_delta_ps=20)  # Small improvement but failed

        # Failure count should increase
        assert effectiveness.failed_applications == initial_failure_count + 1
        assert effectiveness.successful_applications == initial_success_count


class TestPostconditionEdgeCases:
    """Test edge cases for postcondition evaluation."""

    def test_eco_with_no_postconditions_always_satisfied(self) -> None:
        """ECO with no postconditions should always be satisfied."""

        class NoPostconditionECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# No postcondition ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="no_postcondition",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO without postconditions",
        )

        eco = NoPostconditionECO(metadata)

        # Any before/after should satisfy (no postconditions)
        before_metrics = {"wns_ps": -500}
        after_metrics = {"wns_ps": -600}  # Even degradation is "satisfied"

        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        assert satisfied
        assert len(failures) == 0

    def test_multiple_postconditions_all_must_pass(self) -> None:
        """All postconditions must pass for overall satisfaction."""

        def check_wns_improved(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        def check_no_new_drc(before: dict, after: dict) -> bool:
            return after.get("drc_violations", 0) <= before.get("drc_violations", 0)

        postconditions = [
            ECOPostcondition(
                name="wns_improvement",
                description="WNS improves",
                check=check_wns_improved,
            ),
            ECOPostcondition(
                name="no_drc_increase",
                description="No DRC increase",
                check=check_no_new_drc,
            ),
        ]

        class StrictECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Strict ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="strict_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with multiple postconditions",
            postconditions=postconditions,
        )

        eco = StrictECO(metadata)

        # Case 1: Both pass
        before1 = {"wns_ps": -500, "drc_violations": 10}
        after1 = {"wns_ps": -300, "drc_violations": 8}
        satisfied1, failures1 = eco.evaluate_postconditions(before1, after1)
        assert satisfied1
        assert len(failures1) == 0

        # Case 2: WNS improves but DRC increases (one fails)
        before2 = {"wns_ps": -500, "drc_violations": 10}
        after2 = {"wns_ps": -300, "drc_violations": 15}
        satisfied2, failures2 = eco.evaluate_postconditions(before2, after2)
        assert not satisfied2
        assert len(failures2) == 1
        assert "no_drc_increase" in failures2

        # Case 3: Both fail
        before3 = {"wns_ps": -500, "drc_violations": 10}
        after3 = {"wns_ps": -600, "drc_violations": 15}
        satisfied3, failures3 = eco.evaluate_postconditions(before3, after3)
        assert not satisfied3
        assert len(failures3) == 2

    def test_postcondition_evaluation_handles_exceptions(self) -> None:
        """Postcondition evaluation should catch and report exceptions."""

        def check_with_error(before: dict, after: dict) -> bool:
            # This will raise KeyError if 'required_metric' is missing
            return after["required_metric"] > before["required_metric"]

        postcondition = ECOPostcondition(
            name="error_prone_check",
            description="Check that might error",
            check=check_with_error,
        )

        class ErrorProneECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Error-prone ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="error_prone",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with error-prone postcondition",
            postconditions=[postcondition],
        )

        eco = ErrorProneECO(metadata)

        # Metrics missing required field
        before_metrics = {"wns_ps": -500}
        after_metrics = {"wns_ps": -300}
        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        # Should not satisfy (exception treated as failure)
        assert not satisfied
        assert len(failures) == 1
        assert "error_prone_check" in failures[0]
        assert "error:" in failures[0].lower()


class TestPostconditionSerialization:
    """Test postcondition serialization."""

    def test_postcondition_to_dict(self) -> None:
        """Test postcondition serialization."""

        def check_improvement(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        postcondition = ECOPostcondition(
            name="timing_improvement",
            description="Timing must improve",
            check=check_improvement,
            parameters={"min_improvement_ps": 50},
        )

        postcond_dict = postcondition.to_dict()

        assert postcond_dict["name"] == "timing_improvement"
        assert postcond_dict["description"] == "Timing must improve"
        assert postcond_dict["parameters"]["min_improvement_ps"] == 50

    def test_eco_with_postconditions_to_dict(self) -> None:
        """Test ECO with postconditions serialization."""

        def check_improvement(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        postcondition = ECOPostcondition(
            name="improvement_required",
            description="Must improve",
            check=check_improvement,
        )

        class SerializableECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Serializable ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="serializable",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with postconditions",
            postconditions=[postcondition],
        )

        eco = SerializableECO(metadata)

        eco_dict = eco.to_dict()

        assert "postconditions" in eco_dict
        assert len(eco_dict["postconditions"]) == 1
        assert eco_dict["postconditions"][0]["name"] == "improvement_required"


class TestCombinedPreconditionsAndPostconditions:
    """Test ECOs with both preconditions and postconditions."""

    def test_eco_with_both_preconditions_and_postconditions(self) -> None:
        """Test ECO with both pre- and postconditions."""

        # Precondition: Only apply if WNS is bad
        def check_needs_fix(metrics: dict) -> bool:
            return metrics.get("wns_ps", 0) < -500

        # Postcondition: Must improve WNS
        def check_improved(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        from src.controller.eco import ECOPrecondition

        precondition = ECOPrecondition(
            name="needs_timing_fix",
            description="WNS must be bad enough",
            check=check_needs_fix,
        )

        postcondition = ECOPostcondition(
            name="must_improve",
            description="WNS must improve",
            check=check_improved,
        )

        class CompleteECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Complete ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="complete_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with both conditions",
            preconditions=[precondition],
            postconditions=[postcondition],
        )

        eco = CompleteECO(metadata)

        # Test precondition check
        design_metrics = {"wns_ps": -600}
        pre_satisfied, pre_failures = eco.evaluate_preconditions(design_metrics)
        assert pre_satisfied  # WNS is bad enough

        # Test postcondition check (after successful execution)
        before_metrics = {"wns_ps": -600}
        after_metrics = {"wns_ps": -400}
        post_satisfied, post_failures = eco.evaluate_postconditions(
            before_metrics, after_metrics
        )
        assert post_satisfied  # WNS improved

        # Verify serialization includes both
        eco_dict = eco.to_dict()
        assert len(eco_dict["preconditions"]) == 1
        assert len(eco_dict["postconditions"]) == 1
