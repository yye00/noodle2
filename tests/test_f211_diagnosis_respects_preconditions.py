"""Test F211: Auto-diagnosis respects preconditions defined in ECO definitions.

This test ensures that the diagnosis system evaluates ECO preconditions
before suggesting ECOs, and only suggests ECOs whose preconditions are satisfied.
"""

import pytest

from src.analysis.diagnosis import (
    ECOSuggestion,
    filter_eco_suggestions_by_preconditions,
)
from src.controller.eco import ECO, ECOMetadata, ECOPrecondition
from src.controller.types import ECOClass


class TimingRequiredECO(ECO):
    """ECO that requires a timing issue to be present."""

    def __init__(self) -> None:
        """Initialize ECO with timing precondition."""
        metadata = ECOMetadata(
            name="timing_required_eco",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="ECO that requires timing issue",
            preconditions=[
                ECOPrecondition(
                    name="requires_timing_issue",
                    description="Requires WNS < 0",
                    check=lambda metrics: metrics.get("wns_ps", 0) < 0,
                )
            ],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs) -> str:  # type: ignore
        """Generate TCL script."""
        return "# ECO that requires timing issue\n"

    def validate_parameters(self) -> bool:
        """Validate parameters."""
        return True


class CongestionRequiredECO(ECO):
    """ECO that requires congestion to be present."""

    def __init__(self) -> None:
        """Initialize ECO with congestion precondition."""
        metadata = ECOMetadata(
            name="congestion_required_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="ECO that requires congestion",
            preconditions=[
                ECOPrecondition(
                    name="requires_congestion",
                    description="Requires hot_ratio > 0.3",
                    check=lambda metrics: metrics.get("hot_ratio", 0.0) > 0.3,
                )
            ],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs) -> str:  # type: ignore
        """Generate TCL script."""
        return "# ECO that requires congestion\n"

    def validate_parameters(self) -> bool:
        """Validate parameters."""
        return True


class NoopECO(ECO):
    """ECO with no preconditions."""

    def __init__(self) -> None:
        """Initialize noop ECO."""
        metadata = ECOMetadata(
            name="noop_eco",
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            description="No-op ECO with no preconditions",
            preconditions=[],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs) -> str:  # type: ignore
        """Generate TCL script."""
        return "# No-op ECO\n"

    def validate_parameters(self) -> bool:
        """Validate parameters."""
        return True


class TestF211Step1:
    """Step 1: Define ECO with preconditions (requires_timing_issue: true)."""

    def test_define_eco_with_timing_precondition(self) -> None:
        """Verify we can define an ECO with a timing precondition."""
        eco = TimingRequiredECO()

        assert eco.name == "timing_required_eco"
        assert len(eco.metadata.preconditions) == 1
        assert eco.metadata.preconditions[0].name == "requires_timing_issue"
        assert eco.metadata.preconditions[0].description == "Requires WNS < 0"


class TestF211Step2:
    """Step 2: Run diagnosis on design without timing issue."""

    def test_run_diagnosis_without_timing_issue(self) -> None:
        """Verify diagnosis runs on design with no timing issue."""
        # Design metrics with no timing issue (WNS >= 0)
        metrics = {
            "wns_ps": 100,  # Positive slack - no timing issue
            "hot_ratio": 0.1,  # Low congestion
        }

        # Create ECO registry
        eco_registry = {
            "timing_required_eco": TimingRequiredECO(),
            "congestion_required_eco": CongestionRequiredECO(),
            "noop_eco": NoopECO(),
        }

        # Create suggestions from diagnosis (simulated)
        suggestions = [
            ECOSuggestion(
                eco="timing_required_eco",
                priority=1,
                reason="test suggestion",
                addresses="timing",
            ),
            ECOSuggestion(
                eco="congestion_required_eco",
                priority=2,
                reason="test suggestion",
                addresses="congestion",
            ),
            ECOSuggestion(
                eco="noop_eco",
                priority=3,
                reason="test suggestion",
                addresses="timing",
            ),
        ]

        # Filter suggestions by preconditions
        filtered, evaluation_log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        # Verify filtering occurred
        assert len(filtered) < len(suggestions)
        assert evaluation_log is not None


class TestF211Step3:
    """Step 3: Verify ECO is not suggested."""

    def test_verify_timing_eco_not_suggested_without_timing_issue(self) -> None:
        """Verify ECO with timing precondition is not suggested when no timing issue."""
        metrics = {
            "wns_ps": 50,  # Positive - no timing issue
            "hot_ratio": 0.1,
        }

        eco_registry = {
            "timing_required_eco": TimingRequiredECO(),
            "noop_eco": NoopECO(),
        }

        suggestions = [
            ECOSuggestion(
                eco="timing_required_eco",
                priority=1,
                reason="test",
                addresses="timing",
            ),
            ECOSuggestion(
                eco="noop_eco",
                priority=2,
                reason="test",
                addresses="timing",
            ),
        ]

        filtered, _ = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        # timing_required_eco should be filtered out
        filtered_names = [s.eco for s in filtered]
        assert "timing_required_eco" not in filtered_names
        assert "noop_eco" in filtered_names


class TestF211Step4:
    """Step 4: Run diagnosis on design with timing issue."""

    def test_run_diagnosis_with_timing_issue(self) -> None:
        """Verify diagnosis runs on design with timing issue."""
        metrics = {
            "wns_ps": -500,  # Negative slack - timing issue present
            "hot_ratio": 0.1,
        }

        eco_registry = {
            "timing_required_eco": TimingRequiredECO(),
            "noop_eco": NoopECO(),
        }

        suggestions = [
            ECOSuggestion(
                eco="timing_required_eco",
                priority=1,
                reason="test",
                addresses="timing",
            ),
            ECOSuggestion(
                eco="noop_eco",
                priority=2,
                reason="test",
                addresses="timing",
            ),
        ]

        filtered, evaluation_log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        # Both ECOs should pass (timing issue present, noop has no preconditions)
        assert len(filtered) == 2
        assert evaluation_log is not None


class TestF211Step5:
    """Step 5: Verify ECO is suggested."""

    def test_verify_timing_eco_is_suggested_with_timing_issue(self) -> None:
        """Verify ECO with timing precondition IS suggested when timing issue present."""
        metrics = {
            "wns_ps": -1000,  # Negative - timing issue
            "hot_ratio": 0.1,
        }

        eco_registry = {
            "timing_required_eco": TimingRequiredECO(),
            "noop_eco": NoopECO(),
        }

        suggestions = [
            ECOSuggestion(
                eco="timing_required_eco",
                priority=1,
                reason="test",
                addresses="timing",
            ),
            ECOSuggestion(
                eco="noop_eco",
                priority=2,
                reason="test",
                addresses="timing",
            ),
        ]

        filtered, _ = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        # Both should be suggested (preconditions satisfied)
        filtered_names = [s.eco for s in filtered]
        assert "timing_required_eco" in filtered_names
        assert "noop_eco" in filtered_names
        assert len(filtered) == 2


class TestF211Step6:
    """Step 6: Verify precondition evaluation is logged."""

    def test_verify_precondition_evaluation_logged(self) -> None:
        """Verify that precondition evaluations are logged."""
        metrics = {
            "wns_ps": 100,  # No timing issue
            "hot_ratio": 0.5,  # Congestion present
        }

        eco_registry = {
            "timing_required_eco": TimingRequiredECO(),
            "congestion_required_eco": CongestionRequiredECO(),
            "noop_eco": NoopECO(),
        }

        suggestions = [
            ECOSuggestion(
                eco="timing_required_eco",
                priority=1,
                reason="test",
                addresses="timing",
            ),
            ECOSuggestion(
                eco="congestion_required_eco",
                priority=2,
                reason="test",
                addresses="congestion",
            ),
            ECOSuggestion(
                eco="noop_eco",
                priority=3,
                reason="test",
                addresses="timing",
            ),
        ]

        filtered, evaluation_log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        # Verify evaluation log exists and contains information
        assert evaluation_log is not None
        assert "timing_required_eco" in evaluation_log
        assert "congestion_required_eco" in evaluation_log
        assert "noop_eco" in evaluation_log

        # Verify log shows correct evaluation results
        assert not evaluation_log["timing_required_eco"]["all_satisfied"]
        assert evaluation_log["congestion_required_eco"]["all_satisfied"]
        assert evaluation_log["noop_eco"]["all_satisfied"]

        # Verify failed preconditions are recorded
        assert len(evaluation_log["timing_required_eco"]["failed"]) > 0
        assert "requires_timing_issue" in evaluation_log["timing_required_eco"]["failed"]


class TestF211EdgeCases:
    """Additional edge case tests for precondition filtering."""

    def test_eco_not_in_registry_is_skipped(self) -> None:
        """ECO not in registry should be kept (assume no preconditions)."""
        metrics = {"wns_ps": -100, "hot_ratio": 0.2}

        eco_registry = {
            "noop_eco": NoopECO(),
        }

        suggestions = [
            ECOSuggestion(
                eco="unknown_eco",  # Not in registry
                priority=1,
                reason="test",
                addresses="timing",
            ),
            ECOSuggestion(
                eco="noop_eco",
                priority=2,
                reason="test",
                addresses="timing",
            ),
        ]

        filtered, evaluation_log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        # Both should be kept (unknown ECO assumed to have no preconditions)
        assert len(filtered) == 2
        assert "unknown_eco" in evaluation_log
        assert evaluation_log["unknown_eco"]["all_satisfied"]

    def test_multiple_preconditions_all_must_pass(self) -> None:
        """ECO with multiple preconditions requires all to pass."""

        class MultiPreconditionECO(ECO):
            def __init__(self) -> None:
                metadata = ECOMetadata(
                    name="multi_precondition_eco",
                    eco_class=ECOClass.TOPOLOGY_NEUTRAL,
                    description="ECO with multiple preconditions",
                    preconditions=[
                        ECOPrecondition(
                            name="requires_timing",
                            description="Requires WNS < 0",
                            check=lambda m: m.get("wns_ps", 0) < 0,
                        ),
                        ECOPrecondition(
                            name="requires_congestion",
                            description="Requires hot_ratio > 0.3",
                            check=lambda m: m.get("hot_ratio", 0.0) > 0.3,
                        ),
                    ],
                )
                super().__init__(metadata)

            def generate_tcl(self, **kwargs) -> str:  # type: ignore
                return "# Multi-precondition ECO\n"

            def validate_parameters(self) -> bool:
                return True

        # Case 1: Both conditions met
        metrics = {"wns_ps": -500, "hot_ratio": 0.5}
        eco_registry = {"multi": MultiPreconditionECO()}
        suggestions = [
            ECOSuggestion(eco="multi", priority=1, reason="test", addresses="timing")
        ]

        filtered, log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )
        assert len(filtered) == 1
        assert log["multi"]["all_satisfied"]

        # Case 2: Only one condition met (timing but not congestion)
        metrics = {"wns_ps": -500, "hot_ratio": 0.1}
        filtered, log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )
        assert len(filtered) == 0  # Filtered out
        assert not log["multi"]["all_satisfied"]
        assert "requires_congestion" in log["multi"]["failed"]

    def test_empty_suggestions_returns_empty(self) -> None:
        """Empty suggestion list returns empty result."""
        metrics = {"wns_ps": -100, "hot_ratio": 0.2}
        eco_registry = {"noop": NoopECO()}
        suggestions: list[ECOSuggestion] = []

        filtered, log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        assert len(filtered) == 0
        assert len(log) == 0

    def test_empty_registry_keeps_all_suggestions(self) -> None:
        """Empty registry means no preconditions, keep all suggestions."""
        metrics = {"wns_ps": -100, "hot_ratio": 0.2}
        eco_registry: dict[str, ECO] = {}
        suggestions = [
            ECOSuggestion(eco="eco1", priority=1, reason="test", addresses="timing"),
            ECOSuggestion(eco="eco2", priority=2, reason="test", addresses="congestion"),
        ]

        filtered, log = filter_eco_suggestions_by_preconditions(
            suggestions, eco_registry, metrics
        )

        # All kept (assumed no preconditions)
        assert len(filtered) == 2
        assert log["eco1"]["all_satisfied"]
        assert log["eco2"]["all_satisfied"]
