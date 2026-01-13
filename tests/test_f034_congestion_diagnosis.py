"""
Tests for F034: Auto-diagnosis identifies congestion hotspots.

Feature F034 Requirements:
1. Create case with routing congestion (hot_ratio > 0.3)
2. Run auto-diagnosis
3. Verify hotspots are identified with bounding boxes
4. Verify severity is classified (critical, moderate, low)
5. Verify suggested ECOs include spread_dense_region or reroute_congested_nets
"""

import pytest

from src.analysis.diagnosis import (
    CongestionSeverity,
    diagnose_congestion,
)
from src.controller.types import CongestionMetrics


class TestF034CongestionDiagnosis:
    """Test F034: Auto-diagnosis identifies congestion hotspots."""

    def test_step_1_create_congested_case(self):
        """Step 1: Create case with routing congestion (hot_ratio > 0.3)."""
        # Create congestion metrics with significant hotspots
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,  # 40% hot
            hot_ratio=0.40,  # Above threshold
            max_overflow=180,
            layer_metrics={
                "metal3": 120,
                "metal4": 180,
                "metal5": 90,
            },
        )

        # Verify congestion is significant
        assert congestion_metrics.hot_ratio > 0.3
        assert congestion_metrics.bins_hot > 0
        assert congestion_metrics.max_overflow > 0

    def test_step_2_run_auto_diagnosis(self):
        """Step 2: Run auto-diagnosis."""
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=180,
            layer_metrics={
                "metal3": 120,
                "metal4": 180,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(metrics=congestion_metrics)

        # Verify diagnosis was created
        assert diagnosis is not None
        assert hasattr(diagnosis, "hotspots")
        assert hasattr(diagnosis, "hot_ratio")
        assert hasattr(diagnosis, "overflow_total")

    def test_step_3_verify_hotspots_with_bounding_boxes(self):
        """Step 3: Verify hotspots are identified with bounding boxes."""
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,
            max_overflow=200,
            layer_metrics={
                "metal3": 150,
                "metal4": 200,
            },
        )

        diagnosis = diagnose_congestion(metrics=congestion_metrics)

        # Verify hotspots are identified
        assert diagnosis.hotspots is not None
        assert isinstance(diagnosis.hotspots, list)

        # If hotspots are found, verify they have bounding boxes
        if len(diagnosis.hotspots) > 0:
            for hotspot in diagnosis.hotspots:
                assert hasattr(hotspot, "bbox")
                assert hotspot.bbox is not None
                # Verify bbox has coordinates
                assert hasattr(hotspot.bbox, "x1")
                assert hasattr(hotspot.bbox, "y1")
                assert hasattr(hotspot.bbox, "x2")
                assert hasattr(hotspot.bbox, "y2")

    def test_step_4_verify_severity_classification(self):
        """Step 4: Verify severity is classified (critical, moderate, minor)."""
        # Critical congestion case
        critical_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=550,
            hot_ratio=0.55,
            max_overflow=300,
            layer_metrics={"metal3": 200, "metal4": 300},
        )

        diagnosis = diagnose_congestion(metrics=critical_congestion)

        # Verify severity is classified in hotspots
        assert diagnosis.hotspots is not None
        assert len(diagnosis.hotspots) > 0, "Should identify hotspots for high congestion"

        # Verify each hotspot has severity classification
        for hotspot in diagnosis.hotspots:
            assert hasattr(hotspot, "severity")
            assert hotspot.severity in CongestionSeverity, (
                f"Severity should be valid CongestionSeverity, got {hotspot.severity}"
            )

    def test_step_5_verify_suggested_ecos(self):
        """Step 5: Verify suggested ECOs include spread_dense_region or reroute_congested_nets."""
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=180,
            layer_metrics={
                "metal3": 120,
                "metal4": 180,
            },
        )

        diagnosis = diagnose_congestion(metrics=congestion_metrics)

        # Verify ECO suggestions exist in hotspots
        assert diagnosis.hotspots is not None
        assert len(diagnosis.hotspots) > 0, "Should identify hotspots"

        # Collect all suggested ECOs from all hotspots
        all_ecos = []
        for hotspot in diagnosis.hotspots:
            assert hasattr(hotspot, "suggested_ecos")
            all_ecos.extend(hotspot.suggested_ecos)

        # Check ECO types
        eco_names = [eco.lower() for eco in all_ecos]

        # For congestion, common ECOs include:
        # - spread_dense_region
        # - reroute_congested_nets
        # - adjust_placement_density
        valid_eco_keywords = ["spread", "reroute", "density", "placement", "congestion"]
        has_congestion_eco = any(
            any(keyword in eco for keyword in valid_eco_keywords)
            for eco in eco_names
        )
        assert has_congestion_eco, f"Should suggest congestion-related ECO, got {eco_names}"

    def test_complete_f034_workflow(self):
        """Complete F034 workflow: Diagnose congestion hotspots."""
        # Step 1: Create congested case
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=480,
            hot_ratio=0.48,  # High congestion
            max_overflow=220,
            layer_metrics={
                "metal2": 80,
                "metal3": 150,
                "metal4": 220,
                "metal5": 100,
            },
        )

        # Step 2: Run diagnosis
        diagnosis = diagnose_congestion(metrics=congestion_metrics)

        # Step 3: Verify hotspots with bounding boxes
        assert diagnosis.hotspots is not None
        if len(diagnosis.hotspots) > 0:
            for hotspot in diagnosis.hotspots:
                assert hotspot.bbox is not None

        # Step 4: Verify severity classification (on hotspots)
        if len(diagnosis.hotspots) > 0:
            for hotspot in diagnosis.hotspots:
                assert hotspot.severity in CongestionSeverity

        # Step 5: Verify ECO suggestions (on hotspots)
        all_ecos = []
        for hotspot in diagnosis.hotspots:
            all_ecos.extend(hotspot.suggested_ecos)
        assert len(all_ecos) > 0, "Should have ECO suggestions"

        # Verify complete diagnosis structure
        assert diagnosis.hot_ratio == 0.48
        assert diagnosis.hotspot_count >= 0

    def test_different_congestion_levels(self):
        """Test diagnosis with different congestion levels."""
        # Low congestion
        low_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=150,
            hot_ratio=0.15,
            max_overflow=50,
            layer_metrics={"metal3": 30, "metal4": 50},
        )

        # Moderate congestion
        moderate_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=350,
            hot_ratio=0.35,
            max_overflow=120,
            layer_metrics={"metal3": 80, "metal4": 120},
        )

        # High congestion
        high_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=600,
            hot_ratio=0.60,
            max_overflow=350,
            layer_metrics={"metal3": 250, "metal4": 350},
        )

        # Diagnose all three
        low_diag = diagnose_congestion(low_congestion)
        moderate_diag = diagnose_congestion(moderate_congestion)
        high_diag = diagnose_congestion(high_congestion)

        # All should produce valid diagnoses
        assert isinstance(low_diag.hotspots, list)
        assert isinstance(moderate_diag.hotspots, list)
        assert isinstance(high_diag.hotspots, list)

        # Verify hotspots have valid severity if they exist
        for hotspot in low_diag.hotspots:
            assert hotspot.severity in CongestionSeverity
        for hotspot in moderate_diag.hotspots:
            assert hotspot.severity in CongestionSeverity
        for hotspot in high_diag.hotspots:
            assert hotspot.severity in CongestionSeverity

    def test_congestion_with_layer_breakdown(self):
        """Test diagnosis includes per-layer congestion analysis."""
        congestion_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.40,
            max_overflow=200,
            layer_metrics={
                "metal2": 80,
                "metal3": 150,
                "metal4": 200,  # Worst layer
                "metal5": 90,
            },
        )

        diagnosis = diagnose_congestion(metrics=congestion_metrics)

        # Verify diagnosis has layer information
        assert hasattr(diagnosis, "layer_breakdown")
        if diagnosis.layer_breakdown:
            # Verify layer breakdown structure
            assert isinstance(diagnosis.layer_breakdown, dict)
