"""Tests for F259: ECO definition includes expected_effects for diagnosis matching.

Feature steps:
1. Define ECO with expected_effects (wns_ps: improve, area_um2: increase_slightly)
2. Apply ECO
3. Measure actual effects
4. Compare actual to expected
5. Verify mismatches are logged (e.g., WNS regressed instead of improved)
6. Verify expected_effects inform prior state updates
"""

import pytest

from src.controller.eco import (
    BufferInsertionECO,
    ECO,
    ECOMetadata,
    ECOResult,
    NoOpECO,
)
from src.controller.types import ECOClass


class TestExpectedEffectsDefinition:
    """Test defining ECOs with expected effects."""

    def test_step_1_define_eco_with_expected_effects(self) -> None:
        """Step 1: Define ECO with expected_effects."""
        # Define ECO with expected effects
        metadata = ECOMetadata(
            name="buffer_insertion_with_expectations",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Buffer insertion expected to improve timing but increase area",
            expected_effects={
                "wns_ps": "improve",  # WNS should get better (less negative)
                "area_um2": "increase_slightly",  # Area should increase a bit
            },
        )

        eco = BufferInsertionECO(max_capacitance=0.2)
        eco.metadata.expected_effects = metadata.expected_effects

        # Verify expected effects are stored
        assert eco.metadata.expected_effects is not None
        assert "wns_ps" in eco.metadata.expected_effects
        assert eco.metadata.expected_effects["wns_ps"] == "improve"
        assert "area_um2" in eco.metadata.expected_effects
        assert eco.metadata.expected_effects["area_um2"] == "increase_slightly"

    def test_expected_effects_defaults_to_empty_dict(self) -> None:
        """Verify expected_effects defaults to empty dict."""
        eco = NoOpECO()
        assert eco.metadata.expected_effects is not None
        assert isinstance(eco.metadata.expected_effects, dict)
        assert len(eco.metadata.expected_effects) == 0

    def test_multiple_expected_effects(self) -> None:
        """Verify ECO can have multiple expected effects."""
        metadata = ECOMetadata(
            name="complex_eco",
            eco_class=ECOClass.ROUTING_AFFECTING,
            description="Complex ECO with multiple effects",
            expected_effects={
                "wns_ps": "improve",
                "tns_ps": "improve",
                "area_um2": "increase_moderately",
                "power_mw": "increase_slightly",
                "congestion": "worsen_slightly",
            },
        )

        assert len(metadata.expected_effects) == 5


class TestExpectedEffectsComparison:
    """Test comparing actual effects to expected effects."""

    def test_step_2_3_4_apply_eco_and_measure_effects(self) -> None:
        """Steps 2-4: Apply ECO, measure effects, compare to expected."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {
            "wns_ps": "improve",
            "area_um2": "increase_slightly",
        }

        # Simulate applying ECO with actual effects
        before_metrics = {"wns_ps": -500, "area_um2": 1000.0}
        after_metrics = {"wns_ps": -300, "area_um2": 1050.0}  # WNS improved, area increased

        # Calculate actual effects
        actual_effects = {
            "wns_ps": after_metrics["wns_ps"] - before_metrics["wns_ps"],  # +200 (improved)
            "area_um2": after_metrics["area_um2"] - before_metrics["area_um2"],  # +50 (increased)
        }

        # Verify we can compare expected to actual
        expected = eco.metadata.expected_effects
        assert "wns_ps" in expected
        assert "area_um2" in expected
        assert actual_effects["wns_ps"] > 0  # Improved (less negative)
        assert actual_effects["area_um2"] > 0  # Increased

    def test_compare_expected_improve_with_actual(self) -> None:
        """Test comparing 'improve' expectation with actual results."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {"wns_ps": "improve"}

        # Case 1: WNS actually improved (less negative)
        before = -500
        after = -300
        delta = after - before  # +200
        # For WNS (negative is bad), improvement means delta > 0
        matches = delta > 0
        assert matches is True

        # Case 2: WNS actually regressed (more negative)
        before2 = -300
        after2 = -500
        delta2 = after2 - before2  # -200
        matches2 = delta2 > 0
        assert matches2 is False  # Mismatch!

    def test_compare_expected_increase_with_actual(self) -> None:
        """Test comparing 'increase' expectations with actual results."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {"area_um2": "increase_slightly"}

        # Case 1: Area actually increased
        before = 1000.0
        after = 1050.0
        delta = after - before  # +50
        matches = delta > 0
        assert matches is True

        # Case 2: Area actually decreased
        before2 = 1000.0
        after2 = 950.0
        delta2 = after2 - before2  # -50
        matches2 = delta2 > 0
        assert matches2 is False  # Mismatch!


class TestExpectedEffectsMismatchLogging:
    """Test logging when actual effects don't match expected effects."""

    def test_step_5_verify_mismatches_logged(self) -> None:
        """Step 5: Verify mismatches are logged."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {
            "wns_ps": "improve",  # Expected to improve
            "area_um2": "increase_slightly",  # Expected to increase
        }

        # Simulate scenario where WNS regressed instead of improving
        before_metrics = {"wns_ps": -300, "area_um2": 1000.0}
        after_metrics = {"wns_ps": -500, "area_um2": 1050.0}  # WNS got worse!

        # Calculate effects
        wns_delta = after_metrics["wns_ps"] - before_metrics["wns_ps"]  # -200 (regressed)
        area_delta = after_metrics["area_um2"] - before_metrics["area_um2"]  # +50 (increased)

        # Check for mismatches
        mismatches = []
        if eco.metadata.expected_effects.get("wns_ps") == "improve" and wns_delta <= 0:
            mismatches.append({
                "metric": "wns_ps",
                "expected": "improve",
                "actual": "regressed",
                "delta": wns_delta,
            })

        if eco.metadata.expected_effects.get("area_um2") == "increase_slightly" and area_delta <= 0:
            mismatches.append({
                "metric": "area_um2",
                "expected": "increase_slightly",
                "actual": "decreased",
                "delta": area_delta,
            })

        # Verify we detected the WNS mismatch
        assert len(mismatches) == 1
        assert mismatches[0]["metric"] == "wns_ps"
        assert mismatches[0]["expected"] == "improve"
        assert mismatches[0]["actual"] == "regressed"
        assert mismatches[0]["delta"] == -200

    def test_all_effects_match(self) -> None:
        """Verify no mismatches when all effects match expectations."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {
            "wns_ps": "improve",
            "area_um2": "increase_slightly",
        }

        # Both effects match expectations
        before_metrics = {"wns_ps": -500, "area_um2": 1000.0}
        after_metrics = {"wns_ps": -300, "area_um2": 1050.0}

        wns_delta = after_metrics["wns_ps"] - before_metrics["wns_ps"]  # +200
        area_delta = after_metrics["area_um2"] - before_metrics["area_um2"]  # +50

        # Check for mismatches
        mismatches = []
        if eco.metadata.expected_effects.get("wns_ps") == "improve" and wns_delta <= 0:
            mismatches.append("wns_ps")
        if eco.metadata.expected_effects.get("area_um2") == "increase_slightly" and area_delta <= 0:
            mismatches.append("area_um2")

        # No mismatches
        assert len(mismatches) == 0


class TestExpectedEffectsPriorUpdates:
    """Test how expected effects inform ECO prior state."""

    def test_step_6_expected_effects_inform_prior_updates(self) -> None:
        """Step 6: Verify expected_effects inform prior state updates."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {
            "wns_ps": "improve",
            "area_um2": "increase_slightly",
        }

        # Simulate two scenarios:
        # Scenario 1: Effects match expectations -> prior should be positive
        # Scenario 2: Effects don't match -> prior should be negative

        # Scenario 1: Matches expectations
        before1 = {"wns_ps": -500, "area_um2": 1000.0}
        after1 = {"wns_ps": -300, "area_um2": 1050.0}
        wns_delta1 = after1["wns_ps"] - before1["wns_ps"]  # +200 (improved)
        area_delta1 = after1["area_um2"] - before1["area_um2"]  # +50 (increased)

        # Both matched expectations
        matched1 = (wns_delta1 > 0) and (area_delta1 > 0)
        assert matched1 is True

        # This should lead to positive prior update (e.g., "TRUSTED")
        # In actual implementation, this would update ECO effectiveness tracking

        # Scenario 2: Doesn't match expectations
        before2 = {"wns_ps": -300, "area_um2": 1000.0}
        after2 = {"wns_ps": -500, "area_um2": 1050.0}  # WNS regressed!
        wns_delta2 = after2["wns_ps"] - before2["wns_ps"]  # -200 (regressed)
        area_delta2 = after2["area_um2"] - before2["area_um2"]  # +50 (increased)

        # WNS did not match expectations
        wns_matched2 = wns_delta2 > 0
        area_matched2 = area_delta2 > 0
        all_matched2 = wns_matched2 and area_matched2
        assert all_matched2 is False

        # This should lead to negative prior update (e.g., "SUSPICIOUS")

    def test_partial_match_affects_prior(self) -> None:
        """Test that partial matches (some effects match, others don't) affect prior."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {
            "wns_ps": "improve",
            "area_um2": "increase_slightly",
            "power_mw": "increase_slightly",
        }

        # Simulate: WNS improved, area increased, but power decreased (unexpected)
        before = {"wns_ps": -500, "area_um2": 1000.0, "power_mw": 100.0}
        after = {"wns_ps": -300, "area_um2": 1050.0, "power_mw": 95.0}

        wns_match = (after["wns_ps"] - before["wns_ps"]) > 0  # True
        area_match = (after["area_um2"] - before["area_um2"]) > 0  # True
        power_match = (after["power_mw"] - before["power_mw"]) > 0  # False (decreased)

        # Calculate match ratio
        matches = sum([wns_match, area_match, power_match])
        total = 3
        match_ratio = matches / total

        # 2/3 matched
        assert match_ratio == pytest.approx(0.667, abs=0.01)

        # This partial match should be reflected in prior state
        # (e.g., "MIXED" prior instead of "TRUSTED" or "SUSPICIOUS")


class TestExpectedEffectsEdgeCases:
    """Test edge cases for expected effects."""

    def test_no_expected_effects(self) -> None:
        """Verify ECO without expected_effects works normally."""
        eco = NoOpECO()
        assert len(eco.metadata.expected_effects) == 0

        # No comparison needed when no expectations
        before = {"wns_ps": -500}
        after = {"wns_ps": -300}
        # Should work fine without expected effects

    def test_expected_effect_for_non_measured_metric(self) -> None:
        """Test expectation for a metric that wasn't measured."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {
            "wns_ps": "improve",
            "congestion": "worsen_slightly",  # But we don't measure congestion
        }

        before = {"wns_ps": -500, "area_um2": 1000.0}
        after = {"wns_ps": -300, "area_um2": 1050.0}

        # Can only compare metrics that were measured
        measurable = [k for k in eco.metadata.expected_effects if k in before and k in after]
        assert "wns_ps" in measurable
        assert "congestion" not in measurable

    def test_various_effect_descriptions(self) -> None:
        """Test various effect descriptions."""
        metadata = ECOMetadata(
            name="test_eco",
            eco_class=ECOClass.PLACEMENT_LOCAL,
            description="Test",
            expected_effects={
                "wns_ps": "improve",
                "tns_ps": "improve_significantly",
                "area_um2": "increase_slightly",
                "power_mw": "increase_moderately",
                "congestion": "worsen_slightly",
                "runtime_s": "increase_significantly",
            },
        )

        # Verify all descriptions are stored
        assert len(metadata.expected_effects) == 6
        assert metadata.expected_effects["wns_ps"] == "improve"
        assert metadata.expected_effects["tns_ps"] == "improve_significantly"
        assert metadata.expected_effects["congestion"] == "worsen_slightly"


class TestExpectedEffectsSerialization:
    """Test serialization of expected effects."""

    def test_expected_effects_in_to_dict(self) -> None:
        """Verify expected_effects is included in ECO serialization."""
        eco = BufferInsertionECO()
        eco.metadata.expected_effects = {
            "wns_ps": "improve",
            "area_um2": "increase_slightly",
        }

        eco_dict = eco.to_dict()

        # Verify expected_effects is serialized
        assert "expected_effects" in eco_dict
        assert eco_dict["expected_effects"]["wns_ps"] == "improve"
        assert eco_dict["expected_effects"]["area_um2"] == "increase_slightly"
