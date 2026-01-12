"""Tests for F205: Congestion diagnosis identifies hotspot causes and affected layers."""

import pytest

from src.analysis.diagnosis import (
    CongestionCause,
    CongestionSeverity,
    diagnose_congestion,
)
from src.controller.types import CongestionMetrics


class TestCongestionHotspotAnalysisF205:
    """
    Test suite for Feature F205: Hotspot cause and layer identification.

    Steps from feature_list.json:
    1. Run congestion diagnosis on design with hotspots
    2. Verify each hotspot has bbox coordinates
    3. Verify cause is classified (pin_crowding vs placement_density)
    4. Verify affected_layers list is populated
    5. Verify layer_breakdown shows per-layer usage and overflow
    """

    def test_step_1_run_congestion_diagnosis_with_hotspots(self) -> None:
        """Step 1: Run congestion diagnosis on design with hotspots."""
        # Create metrics with high congestion to generate hotspots
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.80,
            max_overflow=1800,
            layer_metrics={
                "metal2": 650,
                "metal3": 580,
                "metal4": 420,
                "metal5": 150,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify hotspots were created
        assert diagnosis is not None
        assert len(diagnosis.hotspots) > 0, "Should have hotspots for hot_ratio=0.80"

    def test_step_2_verify_hotspots_have_bbox_coordinates(self) -> None:
        """Step 2: Verify each hotspot has bbox coordinates."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.80,
            max_overflow=1800,
            layer_metrics={
                "metal2": 650,
                "metal3": 580,
                "metal4": 420,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify each hotspot has a bounding box
        for hotspot in diagnosis.hotspots:
            assert hotspot.bbox is not None, f"Hotspot {hotspot.id} missing bbox"

            # Verify bbox has all required coordinates
            assert hasattr(hotspot.bbox, "x1")
            assert hasattr(hotspot.bbox, "y1")
            assert hasattr(hotspot.bbox, "x2")
            assert hasattr(hotspot.bbox, "y2")

            # Verify bbox is valid (x2 > x1, y2 > y1)
            assert hotspot.bbox.x2 > hotspot.bbox.x1, f"Hotspot {hotspot.id} has invalid x coords"
            assert hotspot.bbox.y2 > hotspot.bbox.y1, f"Hotspot {hotspot.id} has invalid y coords"

            # Verify bbox coordinates are non-negative
            assert hotspot.bbox.x1 >= 0
            assert hotspot.bbox.y1 >= 0
            assert hotspot.bbox.x2 >= 0
            assert hotspot.bbox.y2 >= 0

    def test_step_3_verify_cause_classification(self) -> None:
        """Step 3: Verify cause is classified (pin_crowding vs placement_density)."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.80,
            max_overflow=1800,
            layer_metrics={
                "metal2": 650,
                "metal3": 580,
                "metal4": 420,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify each hotspot has a classified cause
        for hotspot in diagnosis.hotspots:
            assert hotspot.cause is not None, f"Hotspot {hotspot.id} missing cause"

            # Verify cause is one of the valid types
            assert hotspot.cause in [
                CongestionCause.PIN_CROWDING,
                CongestionCause.PLACEMENT_DENSITY,
                CongestionCause.MACRO_PROXIMITY,
                CongestionCause.ROUTING_DETOUR,
                CongestionCause.UNKNOWN,
            ], f"Hotspot {hotspot.id} has invalid cause: {hotspot.cause}"

        # Verify we have at least one of the main causes
        causes = {h.cause for h in diagnosis.hotspots}
        assert CongestionCause.PIN_CROWDING in causes or CongestionCause.PLACEMENT_DENSITY in causes, \
            "Should have at least one hotspot with PIN_CROWDING or PLACEMENT_DENSITY cause"

    def test_step_4_verify_affected_layers_populated(self) -> None:
        """Step 4: Verify affected_layers list is populated."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.80,
            max_overflow=1800,
            layer_metrics={
                "metal2": 650,
                "metal3": 580,
                "metal4": 420,
                "metal5": 150,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify each hotspot has affected layers
        for hotspot in diagnosis.hotspots:
            assert hotspot.affected_layers is not None, f"Hotspot {hotspot.id} missing affected_layers"
            assert len(hotspot.affected_layers) > 0, f"Hotspot {hotspot.id} has empty affected_layers"

            # Verify layers are strings
            for layer in hotspot.affected_layers:
                assert isinstance(layer, str), f"Hotspot {hotspot.id} has non-string layer: {layer}"
                # Verify layer names follow metal layer naming convention
                assert "metal" in layer.lower() or layer.startswith("M"), \
                    f"Hotspot {hotspot.id} has unexpected layer name: {layer}"

    def test_step_5_verify_layer_breakdown_usage_and_overflow(self) -> None:
        """Step 5: Verify layer_breakdown shows per-layer usage and overflow."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.80,
            max_overflow=1800,
            layer_metrics={
                "metal2": 650,
                "metal3": 580,
                "metal4": 420,
                "metal5": 150,
            },
        )

        diagnosis = diagnose_congestion(metrics)

        # Verify layer_breakdown exists
        assert diagnosis.layer_breakdown is not None
        assert len(diagnosis.layer_breakdown) > 0, "layer_breakdown should not be empty"

        # Verify each layer has usage_pct and overflow
        for layer_name, layer_data in diagnosis.layer_breakdown.items():
            # Verify layer data has required fields
            assert hasattr(layer_data, "usage_pct"), f"Layer {layer_name} missing usage_pct"
            assert hasattr(layer_data, "overflow"), f"Layer {layer_name} missing overflow"

            # Verify usage_pct is valid percentage (0-100)
            assert 0.0 <= layer_data.usage_pct <= 100.0, \
                f"Layer {layer_name} has invalid usage_pct: {layer_data.usage_pct}"

            # Verify overflow is non-negative
            assert layer_data.overflow >= 0, \
                f"Layer {layer_name} has negative overflow: {layer_data.overflow}"

        # Verify layer_breakdown covers the input layers
        expected_layers = set(metrics.layer_metrics.keys())
        actual_layers = set(diagnosis.layer_breakdown.keys())
        assert actual_layers == expected_layers, \
            f"layer_breakdown layers {actual_layers} don't match input {expected_layers}"


class TestHotspotCauseClassification:
    """Test different hotspot cause classifications."""

    def test_pin_crowding_cause_is_detected(self) -> None:
        """Verify PIN_CROWDING cause is detected for high congestion."""
        # High congestion typically indicates pin crowding
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

        # Should have at least one PIN_CROWDING hotspot
        pin_crowding_hotspots = [
            h for h in diagnosis.hotspots
            if h.cause == CongestionCause.PIN_CROWDING
        ]
        assert len(pin_crowding_hotspots) > 0, "Should detect PIN_CROWDING in high congestion"

    def test_placement_density_cause_is_detected(self) -> None:
        """Verify PLACEMENT_DENSITY cause is detected for moderate congestion."""
        # Moderate congestion typically indicates placement density issues
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

        # Should have at least one PLACEMENT_DENSITY hotspot
        placement_hotspots = [
            h for h in diagnosis.hotspots
            if h.cause == CongestionCause.PLACEMENT_DENSITY
        ]
        assert len(placement_hotspots) > 0, "Should detect PLACEMENT_DENSITY in moderate congestion"

    def test_cause_to_dict_serialization(self) -> None:
        """Verify cause is properly serialized in to_dict()."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.80,
            max_overflow=1800,
            layer_metrics={
                "metal2": 650,
                "metal3": 580,
            },
        )

        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Verify hotspots in dict have cause field
        assert "hotspots" in diagnosis_dict
        for hotspot_dict in diagnosis_dict["hotspots"]:
            assert "cause" in hotspot_dict
            # Cause should be serialized as string value
            assert isinstance(hotspot_dict["cause"], str)
            assert hotspot_dict["cause"] in [
                "pin_crowding",
                "placement_density",
                "macro_proximity",
                "routing_detour",
                "unknown",
            ]


class TestLayerBreakdownDetails:
    """Test layer breakdown reporting details."""

    def test_layer_breakdown_matches_input_layers(self) -> None:
        """Verify layer_breakdown covers all input layers."""
        input_layers = {
            "metal2": 450,
            "metal3": 380,
            "metal4": 290,
            "metal5": 130,
            "metal6": 50,
        }

        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics=input_layers,
        )

        diagnosis = diagnose_congestion(metrics)

        # Verify all input layers are in breakdown
        for layer_name in input_layers.keys():
            assert layer_name in diagnosis.layer_breakdown, \
                f"Layer {layer_name} missing from breakdown"

    def test_layer_breakdown_overflow_correlates_with_input(self) -> None:
        """Verify layer_breakdown overflow matches input layer_metrics."""
        layer_metrics = {
            "metal2": 450,
            "metal3": 380,
            "metal4": 290,
        }

        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics=layer_metrics,
        )

        diagnosis = diagnose_congestion(metrics)

        # Verify overflow values match input
        for layer_name, expected_overflow in layer_metrics.items():
            actual_overflow = diagnosis.layer_breakdown[layer_name].overflow
            assert actual_overflow == expected_overflow, \
                f"Layer {layer_name} overflow mismatch: expected {expected_overflow}, got {actual_overflow}"

    def test_layer_breakdown_usage_is_estimated(self) -> None:
        """Verify layer_breakdown includes usage estimates."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
            },
        )

        diagnosis = diagnose_congestion(metrics)

        # Verify usage_pct is estimated for each layer
        for layer_name, layer_data in diagnosis.layer_breakdown.items():
            assert layer_data.usage_pct > 0.0, \
                f"Layer {layer_name} should have positive usage_pct"
            # Layers with overflow should have high usage
            if layer_data.overflow > 300:
                assert layer_data.usage_pct > 70.0, \
                    f"Layer {layer_name} with high overflow should have high usage_pct"

    def test_layer_breakdown_to_dict_serialization(self) -> None:
        """Verify layer_breakdown is properly serialized in to_dict()."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
            },
        )

        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Verify layer_breakdown in dict
        assert "layer_breakdown" in diagnosis_dict
        layer_breakdown = diagnosis_dict["layer_breakdown"]

        # Verify structure
        for layer_name, layer_data in layer_breakdown.items():
            assert "usage_pct" in layer_data
            assert "overflow" in layer_data
            assert isinstance(layer_data["usage_pct"], (int, float))
            assert isinstance(layer_data["overflow"], int)


class TestF205Integration:
    """Integration test for complete F205 feature."""

    def test_complete_f205_workflow(self) -> None:
        """
        Complete workflow test for F205.

        This test verifies all 5 steps in sequence:
        1. Run congestion diagnosis on design with hotspots
        2. Each hotspot has bbox coordinates
        3. Cause is classified
        4. affected_layers list is populated
        5. layer_breakdown shows per-layer usage and overflow
        """
        # Step 1: Run diagnosis on congested design
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

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)
        assert len(diagnosis.hotspots) > 0

        # Step 2: Verify bbox coordinates
        for hotspot in diagnosis.hotspots:
            assert hotspot.bbox is not None
            assert hotspot.bbox.x1 < hotspot.bbox.x2
            assert hotspot.bbox.y1 < hotspot.bbox.y2

        # Step 3: Verify cause classification
        for hotspot in diagnosis.hotspots:
            assert hotspot.cause in [
                CongestionCause.PIN_CROWDING,
                CongestionCause.PLACEMENT_DENSITY,
                CongestionCause.MACRO_PROXIMITY,
                CongestionCause.ROUTING_DETOUR,
                CongestionCause.UNKNOWN,
            ]

        # Step 4: Verify affected_layers populated
        for hotspot in diagnosis.hotspots:
            assert len(hotspot.affected_layers) > 0
            for layer in hotspot.affected_layers:
                assert isinstance(layer, str)

        # Step 5: Verify layer_breakdown
        assert len(diagnosis.layer_breakdown) > 0
        for layer_name, layer_data in diagnosis.layer_breakdown.items():
            assert 0.0 <= layer_data.usage_pct <= 100.0
            assert layer_data.overflow >= 0

        print("✓ F205: All steps verified successfully")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
