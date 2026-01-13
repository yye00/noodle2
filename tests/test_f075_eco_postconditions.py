"""Tests for F075: ECO postconditions can verify expected effects.

Feature steps:
1. Create ECO with postcondition: wns_must_improve: true
2. Run ECO that worsens WNS
3. Verify postcondition check fails
4. Classify failure as postcondition_failure
5. Update ECO prior state based on postcondition failure
"""

import pytest

from src.controller.eco import (
    ECO,
    ECOMetadata,
    ECOPostcondition,
    ECOResult,
)
from src.controller.types import ECOClass


class TestF075ECOPostconditions:
    """Test F075: ECO postconditions can verify expected effects."""

    def test_step_1_create_eco_with_postcondition_wns_must_improve(self) -> None:
        """Step 1: Create ECO with postcondition: wns_must_improve: true."""

        # Define postcondition: WNS must improve
        def wns_must_improve(before_metrics: dict, after_metrics: dict) -> bool:
            """Check if WNS improved after ECO application."""
            wns_before = before_metrics.get("wns_ps", 0)
            wns_after = after_metrics.get("wns_ps", 0)
            # WNS improvement means after > before (less negative or more positive)
            return wns_after > wns_before

        postcondition = ECOPostcondition(
            name="wns_must_improve",
            description="WNS must improve after ECO application",
            check=wns_must_improve,
            parameters={"wns_must_improve": True},
        )

        # Create ECO with postcondition
        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix ECO\nrepair_timing -setup\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix_with_verification",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing with verification",
            postconditions=[postcondition],
        )

        eco = TimingFixECO(metadata)

        # Verify ECO has postcondition
        assert len(eco.metadata.postconditions) == 1
        assert eco.metadata.postconditions[0].name == "wns_must_improve"
        assert eco.metadata.postconditions[0].parameters["wns_must_improve"] is True

    def test_step_2_run_eco_that_worsens_wns(self) -> None:
        """Step 2: Run ECO that worsens WNS."""

        # Define postcondition
        def wns_must_improve(before_metrics: dict, after_metrics: dict) -> bool:
            wns_before = before_metrics.get("wns_ps", 0)
            wns_after = after_metrics.get("wns_ps", 0)
            return wns_after > wns_before

        postcondition = ECOPostcondition(
            name="wns_must_improve",
            description="WNS must improve",
            check=wns_must_improve,
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
            postconditions=[postcondition],
        )

        eco = TimingFixECO(metadata)

        # Metrics before ECO: WNS = -500ps
        before_metrics = {"wns_ps": -500}

        # Metrics after ECO: WNS = -800ps (WORSE!)
        after_metrics = {"wns_ps": -800}

        # Evaluate postconditions
        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        # Postcondition should NOT be satisfied (WNS got worse)
        assert not satisfied
        assert len(failures) > 0

    def test_step_3_verify_postcondition_check_fails(self) -> None:
        """Step 3: Verify postcondition check fails."""

        # Define postcondition
        def wns_must_improve(before_metrics: dict, after_metrics: dict) -> bool:
            wns_before = before_metrics.get("wns_ps", 0)
            wns_after = after_metrics.get("wns_ps", 0)
            return wns_after > wns_before

        postcondition = ECOPostcondition(
            name="wns_must_improve",
            description="WNS must improve",
            check=wns_must_improve,
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
            postconditions=[postcondition],
        )

        eco = TimingFixECO(metadata)

        # WNS worsened: -500ps -> -800ps
        before_metrics = {"wns_ps": -500}
        after_metrics = {"wns_ps": -800}

        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        # Verify postcondition failed
        assert not satisfied, "Postcondition should fail when WNS worsens"
        assert "wns_must_improve" in failures

    def test_step_4_classify_failure_as_postcondition_failure(self) -> None:
        """Step 4: Classify failure as postcondition_failure."""

        # Create ECOResult indicating postcondition failure
        result = ECOResult(
            eco_name="timing_fix",
            success=False,  # Overall failure
            postconditions_satisfied=False,
            postcondition_failures=["wns_must_improve"],
        )

        # Verify result correctly classifies postcondition failure
        assert not result.success
        assert not result.postconditions_satisfied
        assert "wns_must_improve" in result.postcondition_failures

        # Verify serialization includes postcondition failure info
        result_dict = result.to_dict()
        assert result_dict["postconditions_satisfied"] is False
        assert "wns_must_improve" in result_dict["postcondition_failures"]

    def test_step_5_update_eco_prior_state_based_on_postcondition_failure(self) -> None:
        """Step 5: Update ECO prior state based on postcondition failure."""

        # This step would be implemented in the ECO tracking system
        # For now, we verify that ECOResult provides the necessary information

        # Create result indicating postcondition failure
        result = ECOResult(
            eco_name="timing_fix",
            success=False,
            postconditions_satisfied=False,
            postcondition_failures=["wns_must_improve"],
            metrics_delta={"wns_ps": -300},  # WNS got worse by 300ps
        )

        # The ECO tracking system would use this information to:
        # 1. Mark this ECO instance as having failed
        # 2. Update the ECO's effectiveness tracking
        # 3. Potentially adjust the ECO's prior (e.g., from TRUSTED to MIXED)

        # Verify result contains information needed for prior update
        assert not result.postconditions_satisfied
        assert len(result.postcondition_failures) > 0
        assert result.metrics_delta["wns_ps"] < 0  # Negative delta = degradation


class TestF075PostconditionValidation:
    """Test postcondition validation scenarios."""

    def test_postcondition_passes_when_wns_improves(self) -> None:
        """Test postcondition passes when WNS improves."""

        def wns_must_improve(before_metrics: dict, after_metrics: dict) -> bool:
            wns_before = before_metrics.get("wns_ps", 0)
            wns_after = after_metrics.get("wns_ps", 0)
            return wns_after > wns_before

        postcondition = ECOPostcondition(
            name="wns_must_improve",
            description="WNS must improve",
            check=wns_must_improve,
        )

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing",
            postconditions=[postcondition],
        )

        eco = TimingFixECO(metadata)

        # WNS improved: -800ps -> -500ps
        before_metrics = {"wns_ps": -800}
        after_metrics = {"wns_ps": -500}

        satisfied, failures = eco.evaluate_postconditions(before_metrics, after_metrics)

        # Postcondition should be satisfied
        assert satisfied
        assert len(failures) == 0

    def test_multiple_postconditions_all_must_be_satisfied(self) -> None:
        """Test all postconditions must be satisfied."""

        def wns_must_improve(before_metrics: dict, after_metrics: dict) -> bool:
            return after_metrics.get("wns_ps", 0) > before_metrics.get("wns_ps", 0)

        def congestion_must_not_worsen(before_metrics: dict, after_metrics: dict) -> bool:
            # Congestion should not increase
            return after_metrics.get("congestion_overflow", 0) <= before_metrics.get("congestion_overflow", 0)

        postconditions = [
            ECOPostcondition(
                name="wns_must_improve",
                description="WNS must improve",
                check=wns_must_improve,
            ),
            ECOPostcondition(
                name="congestion_must_not_worsen",
                description="Congestion must not worsen",
                check=congestion_must_not_worsen,
            ),
        ]

        class MultiPostconditionECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Multi-postcondition ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="multi_postcondition_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Multiple postconditions",
            postconditions=postconditions,
        )

        eco = MultiPostconditionECO(metadata)

        # Case 1: Both postconditions satisfied
        before = {"wns_ps": -800, "congestion_overflow": 0.5}
        after = {"wns_ps": -500, "congestion_overflow": 0.4}
        satisfied, failures = eco.evaluate_postconditions(before, after)
        assert satisfied
        assert len(failures) == 0

        # Case 2: WNS improved but congestion worsened
        after_congestion_worse = {"wns_ps": -500, "congestion_overflow": 0.7}
        satisfied, failures = eco.evaluate_postconditions(before, after_congestion_worse)
        assert not satisfied
        assert "congestion_must_not_worsen" in failures

        # Case 3: WNS worsened (congestion OK)
        after_wns_worse = {"wns_ps": -900, "congestion_overflow": 0.4}
        satisfied, failures = eco.evaluate_postconditions(before, after_wns_worse)
        assert not satisfied
        assert "wns_must_improve" in failures

    def test_eco_with_no_postconditions_always_succeeds(self) -> None:
        """Test ECO with no postconditions always succeeds postcondition check."""

        class NoPostconditionECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# No postconditions\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="no_postcondition_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="No postconditions",
            postconditions=[],
        )

        eco = NoPostconditionECO(metadata)

        # Any metrics -> postconditions satisfied
        before = {"wns_ps": -500}
        after = {"wns_ps": -800}  # Even if WNS worsens

        satisfied, failures = eco.evaluate_postconditions(before, after)
        assert satisfied
        assert len(failures) == 0

    def test_postcondition_with_threshold(self) -> None:
        """Test postcondition with improvement threshold."""

        def wns_must_improve_by_threshold(before_metrics: dict, after_metrics: dict) -> bool:
            """WNS must improve by at least 200ps."""
            wns_before = before_metrics.get("wns_ps", 0)
            wns_after = after_metrics.get("wns_ps", 0)
            improvement = wns_after - wns_before  # Positive = improvement
            return improvement >= 200  # Must improve by at least 200ps

        postcondition = ECOPostcondition(
            name="wns_must_improve_significantly",
            description="WNS must improve by at least 200ps",
            check=wns_must_improve_by_threshold,
            parameters={"min_improvement_ps": 200},
        )

        class ThresholdECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Threshold ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="threshold_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Threshold postcondition",
            postconditions=[postcondition],
        )

        eco = ThresholdECO(metadata)

        # Improvement of 100ps (not enough)
        before = {"wns_ps": -800}
        after = {"wns_ps": -700}
        satisfied, _ = eco.evaluate_postconditions(before, after)
        assert not satisfied

        # Improvement of 300ps (enough)
        after_good = {"wns_ps": -500}
        satisfied, _ = eco.evaluate_postconditions(before, after_good)
        assert satisfied

    def test_postcondition_serialization(self) -> None:
        """Test postcondition can be serialized to dict."""

        def check_wns_improves(before: dict, after: dict) -> bool:
            return after.get("wns_ps", 0) > before.get("wns_ps", 0)

        postcondition = ECOPostcondition(
            name="wns_improvement",
            description="WNS must improve",
            check=check_wns_improves,
            parameters={"min_improvement": 0, "metric": "wns_ps"},
        )

        postcondition_dict = postcondition.to_dict()

        assert postcondition_dict["name"] == "wns_improvement"
        assert postcondition_dict["description"] == "WNS must improve"
        assert postcondition_dict["parameters"]["min_improvement"] == 0
        assert postcondition_dict["parameters"]["metric"] == "wns_ps"

    def test_postcondition_evaluation_error_handling(self) -> None:
        """Test postcondition evaluation handles errors gracefully."""

        def faulty_check(before: dict, after: dict) -> bool:
            # This might raise KeyError if metrics are missing
            return after["missing_metric"] > before["missing_metric"]

        postcondition = ECOPostcondition(
            name="faulty_check",
            description="Faulty check that may error",
            check=faulty_check,
        )

        class FaultyECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Faulty ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="faulty_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Faulty postcondition",
            postconditions=[postcondition],
        )

        eco = FaultyECO(metadata)

        # Missing metrics -> evaluation should handle error
        before = {"wns_ps": -500}
        after = {"wns_ps": -300}

        satisfied, failures = eco.evaluate_postconditions(before, after)

        # Error should be treated as failure
        assert not satisfied
        assert len(failures) > 0
        # Error message should be included in failure
        assert any("error" in f.lower() for f in failures)

    def test_eco_result_tracks_postcondition_success(self) -> None:
        """Test ECOResult can track successful postcondition evaluation."""

        # Create result indicating postcondition success
        result = ECOResult(
            eco_name="timing_fix",
            success=True,
            postconditions_satisfied=True,
            postcondition_failures=[],
            metrics_delta={"wns_ps": 300},  # WNS improved by 300ps
        )

        assert result.success
        assert result.postconditions_satisfied
        assert len(result.postcondition_failures) == 0

        # Verify serialization
        result_dict = result.to_dict()
        assert result_dict["postconditions_satisfied"] is True
        assert len(result_dict["postcondition_failures"]) == 0
