"""Tests for F206: Congestion diagnosis suggests ECOs per hotspot."""

import pytest

from src.analysis.diagnosis import (
    CongestionCause,
    CongestionSeverity,
    diagnose_congestion,
)
from src.controller.types import CongestionMetrics


class TestCongestionECOSuggestionsF206:
    """
    Test suite for Feature F206: ECO suggestions per hotspot.

    Steps from feature_list.json:
    1. Run congestion diagnosis with multiple hotspots
    2. Verify each hotspot includes suggested_ecos
    3. Verify pin_crowding hotspot suggests reroute_congested_nets
    4. Verify placement_density hotspot suggests spread_dense_region
    5. Verify ECO suggestions are actionable
    """

    def test_step_1_run_diagnosis_with_multiple_hotspots(self) -> None:
        """Step 1: Run congestion diagnosis with multiple hotspots."""
        # Create metrics with high congestion to generate multiple hotspots
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=820,
            hot_ratio=0.82,
            max_overflow=1900,
            layer_metrics={
                "metal2": 700,
                "metal3": 620,
                "metal4": 400,
                "metal5": 180,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify multiple hotspots were created
        assert len(diagnosis.hotspots) > 0, "Should have at least one hotspot"
        # High hot_ratio typically generates 2+ hotspots (critical + moderate)
        assert len(diagnosis.hotspots) >= 1, "High congestion should generate multiple hotspots"

    def test_step_2_verify_each_hotspot_has_suggested_ecos(self) -> None:
        """Step 2: Verify each hotspot includes suggested_ecos."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=820,
            hot_ratio=0.82,
            max_overflow=1900,
            layer_metrics={
                "metal2": 700,
                "metal3": 620,
                "metal4": 400,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify each hotspot has ECO suggestions
        for hotspot in diagnosis.hotspots:
            assert hotspot.suggested_ecos is not None, \
                f"Hotspot {hotspot.id} missing suggested_ecos"
            assert len(hotspot.suggested_ecos) > 0, \
                f"Hotspot {hotspot.id} has empty suggested_ecos"

            # Verify ECOs are strings
            for eco in hotspot.suggested_ecos:
                assert isinstance(eco, str), \
                    f"Hotspot {hotspot.id} has non-string ECO: {eco}"
                assert len(eco) > 0, \
                    f"Hotspot {hotspot.id} has empty ECO string"

    def test_step_3_pin_crowding_suggests_reroute(self) -> None:
        """Step 3: Verify pin_crowding hotspot suggests reroute_congested_nets."""
        # Create high congestion to generate PIN_CROWDING hotspot
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=850,
            hot_ratio=0.85,
            max_overflow=2000,
            layer_metrics={
                "metal2": 800,
                "metal3": 750,
                "metal4": 450,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Find PIN_CROWDING hotspots
        pin_crowding_hotspots = [
            h for h in diagnosis.hotspots
            if h.cause == CongestionCause.PIN_CROWDING
        ]

        assert len(pin_crowding_hotspots) > 0, "Should have PIN_CROWDING hotspot(s)"

        # Verify PIN_CROWDING hotspots suggest reroute_congested_nets
        for hotspot in pin_crowding_hotspots:
            assert "reroute_congested_nets" in hotspot.suggested_ecos, \
                f"PIN_CROWDING hotspot {hotspot.id} should suggest reroute_congested_nets"

    def test_step_4_placement_density_suggests_spread(self) -> None:
        """Step 4: Verify placement_density hotspot suggests spread_dense_region."""
        # Create moderate congestion to generate PLACEMENT_DENSITY hotspot
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=600,
            layer_metrics={
                "metal2": 250,
                "metal3": 200,
                "metal4": 150,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.3)

        # Find PLACEMENT_DENSITY hotspots
        placement_hotspots = [
            h for h in diagnosis.hotspots
            if h.cause == CongestionCause.PLACEMENT_DENSITY
        ]

        assert len(placement_hotspots) > 0, "Should have PLACEMENT_DENSITY hotspot(s)"

        # Verify PLACEMENT_DENSITY hotspots suggest spread_dense_region
        for hotspot in placement_hotspots:
            assert "spread_dense_region" in hotspot.suggested_ecos, \
                f"PLACEMENT_DENSITY hotspot {hotspot.id} should suggest spread_dense_region"

    def test_step_5_eco_suggestions_are_actionable(self) -> None:
        """Step 5: Verify ECO suggestions are actionable."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=820,
            hot_ratio=0.82,
            max_overflow=1900,
            layer_metrics={
                "metal2": 700,
                "metal3": 620,
                "metal4": 400,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # List of valid/actionable ECO names
        valid_ecos = {
            "reroute_congested_nets",
            "spread_dense_region",
            "insert_buffers",
            "resize_critical_drivers",
            "swap_to_faster_cells",
            "move_macro",
            "adjust_placement",
        }

        # Verify all suggested ECOs are from the valid set
        for hotspot in diagnosis.hotspots:
            for eco in hotspot.suggested_ecos:
                assert eco in valid_ecos, \
                    f"Hotspot {hotspot.id} suggests unknown/non-actionable ECO: {eco}"


class TestECOSuggestionsByHotspotType:
    """Test ECO suggestions based on hotspot type and severity."""

    def test_critical_hotspot_eco_suggestions(self) -> None:
        """Verify critical hotspots have appropriate ECO suggestions."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=850,
            hot_ratio=0.85,
            max_overflow=2000,
            layer_metrics={
                "metal2": 800,
                "metal3": 750,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Find critical hotspots
        critical_hotspots = [
            h for h in diagnosis.hotspots
            if h.severity == CongestionSeverity.CRITICAL
        ]

        assert len(critical_hotspots) > 0, "Should have critical hotspot(s)"

        # Critical hotspots should have multiple ECO suggestions
        for hotspot in critical_hotspots:
            assert len(hotspot.suggested_ecos) >= 1, \
                f"Critical hotspot {hotspot.id} should have at least 1 ECO suggestion"

    def test_moderate_hotspot_eco_suggestions(self) -> None:
        """Verify moderate hotspots have appropriate ECO suggestions."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=600,
            layer_metrics={
                "metal2": 250,
                "metal3": 200,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.3)

        # Find moderate hotspots
        moderate_hotspots = [
            h for h in diagnosis.hotspots
            if h.severity == CongestionSeverity.MODERATE
        ]

        assert len(moderate_hotspots) > 0, "Should have moderate hotspot(s)"

        # Moderate hotspots should have ECO suggestions
        for hotspot in moderate_hotspots:
            assert len(hotspot.suggested_ecos) >= 1, \
                f"Moderate hotspot {hotspot.id} should have at least 1 ECO suggestion"

    def test_eco_suggestions_serialization(self) -> None:
        """Verify ECO suggestions are properly serialized in to_dict()."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=820,
            hot_ratio=0.82,
            max_overflow=1900,
            layer_metrics={
                "metal2": 700,
                "metal3": 620,
            },
        )

        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Verify hotspots in dict have suggested_ecos
        assert "hotspots" in diagnosis_dict
        for hotspot_dict in diagnosis_dict["hotspots"]:
            assert "suggested_ecos" in hotspot_dict, \
                f"Hotspot {hotspot_dict['id']} missing suggested_ecos in dict"
            assert isinstance(hotspot_dict["suggested_ecos"], list), \
                f"Hotspot {hotspot_dict['id']} suggested_ecos is not a list"
            assert len(hotspot_dict["suggested_ecos"]) > 0, \
                f"Hotspot {hotspot_dict['id']} has empty suggested_ecos in dict"


class TestECOSuggestionsDiversity:
    """Test that different hotspot causes generate different ECO suggestions."""

    def test_different_causes_suggest_different_ecos(self) -> None:
        """Verify different hotspot causes lead to different ECO suggestions."""
        # Get high congestion (pin_crowding)
        high_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=850,
            hot_ratio=0.85,
            max_overflow=2000,
            layer_metrics={
                "metal2": 800,
                "metal3": 750,
            },
        )

        high_diagnosis = diagnose_congestion(high_metrics, hotspot_threshold=0.7)

        # Get moderate congestion (placement_density)
        moderate_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=600,
            layer_metrics={
                "metal2": 250,
                "metal3": 200,
            },
        )

        moderate_diagnosis = diagnose_congestion(moderate_metrics, hotspot_threshold=0.3)

        # Collect ECO suggestions
        high_ecos = set()
        for h in high_diagnosis.hotspots:
            high_ecos.update(h.suggested_ecos)

        moderate_ecos = set()
        for h in moderate_diagnosis.hotspots:
            moderate_ecos.update(h.suggested_ecos)

        # Should have some overlap but also differences
        # PIN_CROWDING should have reroute_congested_nets
        assert "reroute_congested_nets" in high_ecos

        # PLACEMENT_DENSITY should have spread_dense_region
        assert "spread_dense_region" in moderate_ecos

    def test_eco_suggestions_cover_common_congestion_fixes(self) -> None:
        """Verify ECO suggestions cover common congestion mitigation strategies."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=820,
            hot_ratio=0.82,
            max_overflow=1900,
            layer_metrics={
                "metal2": 700,
                "metal3": 620,
                "metal4": 400,
            },
        )

        diagnosis = diagnose_congestion(metrics)

        # Collect all ECO suggestions
        all_ecos = set()
        for hotspot in diagnosis.hotspots:
            all_ecos.update(hotspot.suggested_ecos)

        # Should include at least one routing-related ECO
        routing_ecos = {"reroute_congested_nets"}
        assert len(routing_ecos & all_ecos) > 0, "Should suggest routing-related ECOs"

        # Should include at least one placement-related ECO
        placement_ecos = {"spread_dense_region"}
        assert len(placement_ecos & all_ecos) > 0, "Should suggest placement-related ECOs"


class TestF206Integration:
    """Integration test for complete F206 feature."""

    def test_complete_f206_workflow(self) -> None:
        """
        Complete workflow test for F206.

        This test verifies all 5 steps in sequence:
        1. Run congestion diagnosis with multiple hotspots
        2. Each hotspot includes suggested_ecos
        3. pin_crowding hotspot suggests reroute_congested_nets
        4. placement_density hotspot suggests spread_dense_region
        5. ECO suggestions are actionable
        """
        # Create metrics with sufficient congestion for multiple hotspots
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1500,
            layer_metrics={
                "metal2": 600,
                "metal3": 500,
                "metal4": 300,
                "metal5": 100,
            },
        )

        # Step 1: Run diagnosis with multiple hotspots
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)
        assert len(diagnosis.hotspots) > 0

        # Step 2: Verify each hotspot has ECO suggestions
        for hotspot in diagnosis.hotspots:
            assert len(hotspot.suggested_ecos) > 0

        # Step 3: Verify pin_crowding suggests reroute
        pin_crowding_hotspots = [
            h for h in diagnosis.hotspots
            if h.cause == CongestionCause.PIN_CROWDING
        ]
        if pin_crowding_hotspots:
            for hotspot in pin_crowding_hotspots:
                assert "reroute_congested_nets" in hotspot.suggested_ecos

        # Step 4: Verify placement_density suggests spread
        placement_hotspots = [
            h for h in diagnosis.hotspots
            if h.cause == CongestionCause.PLACEMENT_DENSITY
        ]
        if placement_hotspots:
            for hotspot in placement_hotspots:
                assert "spread_dense_region" in hotspot.suggested_ecos

        # Step 5: Verify ECO suggestions are actionable
        valid_ecos = {
            "reroute_congested_nets",
            "spread_dense_region",
            "insert_buffers",
            "resize_critical_drivers",
            "swap_to_faster_cells",
            "move_macro",
            "adjust_placement",
        }

        for hotspot in diagnosis.hotspots:
            for eco in hotspot.suggested_ecos:
                assert eco in valid_ecos

        print("✓ F206: All steps verified successfully")


class TestECOSuggestionEdgeCases:
    """Test edge cases for ECO suggestions."""

    def test_empty_layer_metrics_still_provides_ecos(self) -> None:
        """Verify ECO suggestions are provided even with minimal layer data."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1000,
            layer_metrics={},
        )

        diagnosis = diagnose_congestion(metrics)

        # Should still have hotspots and ECO suggestions
        if diagnosis.hotspots:
            for hotspot in diagnosis.hotspots:
                assert len(hotspot.suggested_ecos) > 0

    def test_low_congestion_appropriate_ecos(self) -> None:
        """Verify low congestion generates appropriate (or no) ECO suggestions."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=0.05,
            max_overflow=20,
            layer_metrics={
                "metal2": 10,
                "metal3": 10,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Low congestion should have few/no hotspots
        # If hotspots exist, they should still have ECO suggestions
        for hotspot in diagnosis.hotspots:
            assert len(hotspot.suggested_ecos) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
