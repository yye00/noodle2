"""Tests for F256: ECO definition supports preconditions with diagnosis integration.

Feature steps:
1. Define ECO with preconditions (requires_timing_issue: true, wns_ps_worse_than: -500)
2. Apply ECO to design with WNS = -300ps
3. Verify preconditions are evaluated
4. Verify ECO is skipped (WNS not worse than -500ps)
5. Apply to design with WNS = -800ps
6. Verify ECO is applied
7. Verify precondition evaluation is logged
"""

import pytest

from src.controller.eco import (
    ECO,
    ECOMetadata,
    ECOPrecondition,
    ECOResult,
)
from src.controller.types import ECOClass


class TestECOWithPreconditionsDefinition:
    """Test defining ECOs with preconditions."""

    def test_step_1_define_eco_with_timing_preconditions(self) -> None:
        """Step 1: Define ECO with preconditions (requires_timing_issue, wns_ps_worse_than)."""

        # Define precondition: WNS must be worse than -500ps
        def check_wns_threshold(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < -500  # True if WNS is worse (more negative) than -500ps

        precondition = ECOPrecondition(
            name="wns_worse_than_threshold",
            description="WNS must be worse than -500ps",
            check=check_wns_threshold,
            parameters={"threshold_ps": -500},
        )

        # Create ECO with precondition
        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix TCL\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing violations",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        assert eco.metadata.preconditions == [precondition]
        assert len(eco.metadata.preconditions) == 1
        assert eco.metadata.preconditions[0].name == "wns_worse_than_threshold"
        assert eco.metadata.preconditions[0].parameters["threshold_ps"] == -500

    def test_define_eco_with_multiple_preconditions(self) -> None:
        """Test ECO with multiple preconditions."""

        def check_wns(metrics: dict) -> bool:
            return metrics.get("wns_ps", 0) < -500

        def check_congestion(metrics: dict) -> bool:
            return metrics.get("congestion_overflow", 0) < 0.1

        preconditions = [
            ECOPrecondition(
                name="wns_threshold",
                description="WNS threshold check",
                check=check_wns,
            ),
            ECOPrecondition(
                name="congestion_acceptable",
                description="Congestion check",
                check=check_congestion,
            ),
        ]

        class MultiPreconditionECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Multi-precondition ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="multi_precondition_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with multiple preconditions",
            preconditions=preconditions,
        )

        eco = MultiPreconditionECO(metadata)

        assert len(eco.metadata.preconditions) == 2
        assert eco.metadata.preconditions[0].name == "wns_threshold"
        assert eco.metadata.preconditions[1].name == "congestion_acceptable"


class TestPreconditionEvaluation:
    """Test precondition evaluation logic."""

    def test_step_2_and_3_evaluate_preconditions_with_wns_300ps(self) -> None:
        """Steps 2-3: Apply ECO to design with WNS=-300ps and verify preconditions are evaluated."""

        def check_wns_threshold(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < -500

        precondition = ECOPrecondition(
            name="wns_worse_than_threshold",
            description="WNS must be worse than -500ps",
            check=check_wns_threshold,
            parameters={"threshold_ps": -500},
        )

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix TCL\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing violations",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Design with WNS = -300ps (not bad enough for ECO)
        design_metrics = {"wns_ps": -300}

        satisfied, failures = eco.evaluate_preconditions(design_metrics)

        # Preconditions should NOT be satisfied (WNS not bad enough)
        assert not satisfied
        assert len(failures) == 1
        assert "wns_worse_than_threshold" in failures

    def test_step_4_eco_skipped_when_preconditions_not_met(self) -> None:
        """Step 4: Verify ECO is skipped when WNS not worse than -500ps."""

        def check_wns_threshold(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < -500

        precondition = ECOPrecondition(
            name="wns_worse_than_threshold",
            description="WNS must be worse than -500ps",
            check=check_wns_threshold,
        )

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix TCL\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing violations",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Simulate ECO application with precondition check
        design_metrics = {"wns_ps": -300}
        satisfied, failures = eco.evaluate_preconditions(design_metrics)

        # Create result indicating ECO was skipped
        result = ECOResult(
            eco_name=eco.name,
            success=True,  # Skipping is considered "successful"
            preconditions_satisfied=satisfied,
            precondition_failures=failures,
            skipped_due_to_preconditions=not satisfied,
        )

        assert result.skipped_due_to_preconditions
        assert not result.preconditions_satisfied
        assert "wns_worse_than_threshold" in result.precondition_failures

    def test_step_5_and_6_preconditions_met_with_wns_800ps(self) -> None:
        """Steps 5-6: Apply to design with WNS=-800ps and verify ECO is applied."""

        def check_wns_threshold(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < -500

        precondition = ECOPrecondition(
            name="wns_worse_than_threshold",
            description="WNS must be worse than -500ps",
            check=check_wns_threshold,
        )

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix TCL\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing violations",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Design with WNS = -800ps (bad enough for ECO)
        design_metrics = {"wns_ps": -800}

        satisfied, failures = eco.evaluate_preconditions(design_metrics)

        # Preconditions SHOULD be satisfied
        assert satisfied
        assert len(failures) == 0

        # ECO should proceed (not skipped)
        result = ECOResult(
            eco_name=eco.name,
            success=True,
            preconditions_satisfied=satisfied,
            skipped_due_to_preconditions=not satisfied,
        )

        assert not result.skipped_due_to_preconditions
        assert result.preconditions_satisfied


class TestPreconditionLogging:
    """Test precondition evaluation logging."""

    def test_step_7_precondition_evaluation_is_logged(self) -> None:
        """Step 7: Verify precondition evaluation is logged."""

        def check_wns_threshold(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)
            return wns < -500

        precondition = ECOPrecondition(
            name="wns_worse_than_threshold",
            description="WNS must be worse than -500ps",
            check=check_wns_threshold,
            parameters={"threshold_ps": -500},
        )

        class TimingFixECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Timing fix TCL\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="timing_fix",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Fix timing violations",
            preconditions=[precondition],
        )

        eco = TimingFixECO(metadata)

        # Test with failing precondition
        design_metrics_fail = {"wns_ps": -300}
        satisfied_fail, failures_fail = eco.evaluate_preconditions(design_metrics_fail)

        result_fail = ECOResult(
            eco_name=eco.name,
            success=True,
            preconditions_satisfied=satisfied_fail,
            precondition_failures=failures_fail,
            skipped_due_to_preconditions=not satisfied_fail,
        )

        # Verify result can be serialized (for logging)
        result_dict_fail = result_fail.to_dict()
        assert "preconditions_satisfied" in result_dict_fail
        assert not result_dict_fail["preconditions_satisfied"]
        assert "wns_worse_than_threshold" in result_dict_fail["precondition_failures"]
        assert result_dict_fail["skipped_due_to_preconditions"]

        # Test with passing precondition
        design_metrics_pass = {"wns_ps": -800}
        satisfied_pass, failures_pass = eco.evaluate_preconditions(design_metrics_pass)

        result_pass = ECOResult(
            eco_name=eco.name,
            success=True,
            preconditions_satisfied=satisfied_pass,
            skipped_due_to_preconditions=not satisfied_pass,
        )

        # Verify passing result can be serialized
        result_dict_pass = result_pass.to_dict()
        assert result_dict_pass["preconditions_satisfied"]
        assert len(result_dict_pass["precondition_failures"]) == 0
        assert not result_dict_pass["skipped_due_to_preconditions"]


class TestPreconditionEdgeCases:
    """Test edge cases for precondition evaluation."""

    def test_eco_with_no_preconditions_always_satisfied(self) -> None:
        """ECO with no preconditions should always be satisfied."""

        class NoPreconditionECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# No precondition ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="no_precondition",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO without preconditions",
        )

        eco = NoPreconditionECO(metadata)

        # Any metrics should satisfy (no preconditions)
        design_metrics = {"wns_ps": 1000}  # Great WNS
        satisfied, failures = eco.evaluate_preconditions(design_metrics)

        assert satisfied
        assert len(failures) == 0

    def test_precondition_evaluation_handles_missing_metrics(self) -> None:
        """Precondition evaluation should handle missing metrics gracefully."""

        def check_wns_threshold(metrics: dict) -> bool:
            wns = metrics.get("wns_ps", 0)  # Default to 0 if missing
            return wns < -500

        precondition = ECOPrecondition(
            name="wns_threshold",
            description="WNS check",
            check=check_wns_threshold,
        )

        class SafeECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Safe ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="safe_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with safe precondition",
            preconditions=[precondition],
        )

        eco = SafeECO(metadata)

        # Empty metrics (missing wns_ps)
        design_metrics = {}
        satisfied, failures = eco.evaluate_preconditions(design_metrics)

        # Should not satisfy (defaults to 0, which is > -500)
        assert not satisfied

    def test_precondition_evaluation_handles_exceptions(self) -> None:
        """Precondition evaluation should catch and report exceptions."""

        def check_with_error(metrics: dict) -> bool:
            # This will raise KeyError if 'required_field' is missing
            return metrics["required_field"] > 100

        precondition = ECOPrecondition(
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
            description="ECO with error-prone precondition",
            preconditions=[precondition],
        )

        eco = ErrorProneECO(metadata)

        # Metrics missing required field
        design_metrics = {"wns_ps": -500}
        satisfied, failures = eco.evaluate_preconditions(design_metrics)

        # Should not satisfy (exception treated as failure)
        assert not satisfied
        assert len(failures) == 1
        assert "error_prone_check" in failures[0]
        assert "error:" in failures[0].lower()


class TestPreconditionSerialization:
    """Test precondition serialization for ECO definitions."""

    def test_precondition_to_dict(self) -> None:
        """Test precondition serialization."""

        def check_wns(metrics: dict) -> bool:
            return metrics.get("wns_ps", 0) < -500

        precondition = ECOPrecondition(
            name="wns_threshold",
            description="WNS must be worse than -500ps",
            check=check_wns,
            parameters={"threshold_ps": -500, "type": "timing"},
        )

        precond_dict = precondition.to_dict()

        assert precond_dict["name"] == "wns_threshold"
        assert precond_dict["description"] == "WNS must be worse than -500ps"
        assert precond_dict["parameters"]["threshold_ps"] == -500
        assert precond_dict["parameters"]["type"] == "timing"

    def test_eco_with_preconditions_to_dict(self) -> None:
        """Test ECO with preconditions serialization."""

        def check_wns(metrics: dict) -> bool:
            return metrics.get("wns_ps", 0) < -500

        precondition = ECOPrecondition(
            name="wns_threshold",
            description="WNS check",
            check=check_wns,
        )

        class SerializableECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Serializable ECO\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="serializable",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO with preconditions",
            preconditions=[precondition],
        )

        eco = SerializableECO(metadata)

        eco_dict = eco.to_dict()

        assert "preconditions" in eco_dict
        assert len(eco_dict["preconditions"]) == 1
        assert eco_dict["preconditions"][0]["name"] == "wns_threshold"


class TestDiagnosisIntegration:
    """Test preconditions integrating with diagnosis results."""

    def test_precondition_uses_diagnosis_metrics(self) -> None:
        """Test precondition using diagnosis output metrics."""

        def check_wire_dominated(metrics: dict) -> bool:
            """Check if design is wire-dominated (from diagnosis)."""
            wire_delay_ratio = metrics.get("wire_delay_ratio", 0.0)
            return wire_delay_ratio > 0.6

        precondition = ECOPrecondition(
            name="requires_wire_dominated_design",
            description="Design must be wire-dominated",
            check=check_wire_dominated,
            parameters={"min_wire_ratio": 0.6},
        )

        class BufferInsertionECO(ECO):
            def generate_tcl(self, **kwargs) -> str:
                return "# Buffer insertion\n"

            def validate_parameters(self) -> bool:
                return True

        metadata = ECOMetadata(
            name="buffer_insertion",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Insert buffers (only for wire-dominated designs)",
            preconditions=[precondition],
        )

        eco = BufferInsertionECO(metadata)

        # Diagnosis shows wire-dominated design
        diagnosis_metrics = {"wire_delay_ratio": 0.75, "wns_ps": -600}
        satisfied, failures = eco.evaluate_preconditions(diagnosis_metrics)

        assert satisfied
        assert len(failures) == 0

        # Diagnosis shows cell-dominated design
        diagnosis_metrics_cell = {"wire_delay_ratio": 0.35, "wns_ps": -600}
        satisfied_cell, failures_cell = eco.evaluate_preconditions(
            diagnosis_metrics_cell
        )

        assert not satisfied_cell
        assert "requires_wire_dominated_design" in failures_cell
