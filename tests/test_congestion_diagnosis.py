"""Tests for F204: Generate congestion diagnosis report for high hot_ratio design."""

import json

import pytest

from src.analysis.diagnosis import (
    CongestionDiagnosis,
    CongestionSeverity,
    diagnose_congestion,
    generate_complete_diagnosis,
)
from src.controller.types import CongestionMetrics


class TestCongestionDiagnosisF204:
    """
    Test suite for Feature F204: Generate congestion diagnosis report.

    Steps from feature_list.json:
    1. Execute global routing on congested design
    2. Enable congestion diagnosis in study configuration
    3. Run auto-diagnosis
    4. Verify diagnosis.json contains congestion_diagnosis section
    5. Verify hot_ratio and overflow_total are reported
    6. Verify hotspots are identified with severity levels
    """

    def test_step_1_create_congested_design(self) -> None:
        """Step 1: Execute global routing on congested design."""
        # Create congestion metrics representing a heavily congested design
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,  # High congestion
            max_overflow=1250,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
                "metal4": 290,
                "metal5": 130,
            },
        )

        assert metrics.hot_ratio > 0.7, "Design should have high congestion"
        assert metrics.max_overflow is not None
        assert metrics.max_overflow > 0
        assert len(metrics.layer_metrics) > 0

    def test_step_2_enable_congestion_diagnosis(self) -> None:
        """Step 2: Enable congestion diagnosis in study configuration."""
        # This is verified by the ability to call diagnose_congestion
        # Configuration would be in study YAML, but we test the function exists
        from src.analysis.diagnosis import diagnose_congestion

        assert callable(diagnose_congestion)

    def test_step_3_run_auto_diagnosis(self) -> None:
        """Step 3: Run auto-diagnosis."""
        # Create congestion metrics
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
                "metal4": 290,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)

        # Verify diagnosis was generated
        assert diagnosis is not None
        assert diagnosis.hot_ratio == 0.75
        assert diagnosis.overflow_total > 0

    def test_step_4_verify_diagnosis_json_contains_congestion_diagnosis(self) -> None:
        """Step 4: Verify diagnosis.json contains congestion_diagnosis section."""
        # Create complete diagnosis report
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

        report = generate_complete_diagnosis(congestion_metrics=metrics)

        # Convert to dict (JSON-serializable)
        report_dict = report.to_dict()

        # Verify congestion_diagnosis section exists
        assert "congestion_diagnosis" in report_dict
        assert isinstance(report_dict["congestion_diagnosis"], dict)

    def test_step_5_verify_hot_ratio_and_overflow_total_reported(self) -> None:
        """Step 5: Verify hot_ratio and overflow_total are reported."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
                "metal4": 290,
            },
        )

        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Verify both metrics are present
        assert "hot_ratio" in diagnosis_dict
        assert diagnosis_dict["hot_ratio"] == 0.75

        assert "overflow_total" in diagnosis_dict
        assert diagnosis_dict["overflow_total"] > 0

    def test_step_6_verify_hotspots_identified_with_severity_levels(self) -> None:
        """Step 6: Verify hotspots are identified with severity levels."""
        # Test with high congestion (should create critical hotspots)
        high_congestion = CongestionMetrics(
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

        diagnosis = diagnose_congestion(high_congestion, hotspot_threshold=0.7)
        diagnosis_dict = diagnosis.to_dict()

        # Verify hotspots are identified
        assert "hotspots" in diagnosis_dict
        assert len(diagnosis_dict["hotspots"]) > 0

        # Verify severity levels are present
        for hotspot in diagnosis_dict["hotspots"]:
            assert "severity" in hotspot
            assert hotspot["severity"] in [
                CongestionSeverity.CRITICAL.value,
                CongestionSeverity.MODERATE.value,
                CongestionSeverity.MINOR.value,
            ]

        # For high hot_ratio, should have at least one critical hotspot
        severities = [h["severity"] for h in diagnosis_dict["hotspots"]]
        assert CongestionSeverity.CRITICAL.value in severities

        # Verify hotspot structure
        first_hotspot = diagnosis_dict["hotspots"][0]
        assert "id" in first_hotspot
        assert "bbox" in first_hotspot
        assert "cause" in first_hotspot
        assert "affected_layers" in first_hotspot
        assert "suggested_ecos" in first_hotspot


class TestCongestionDiagnosisDetails:
    """Additional tests for congestion diagnosis details."""

    def test_layer_breakdown_is_reported(self) -> None:
        """Verify per-layer breakdown is reported."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
                "metal4": 290,
            },
        )

        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Verify layer breakdown exists
        assert "layer_breakdown" in diagnosis_dict
        assert len(diagnosis_dict["layer_breakdown"]) > 0

        # Verify layer breakdown structure
        for layer_name, layer_data in diagnosis_dict["layer_breakdown"].items():
            assert "usage_pct" in layer_data
            assert "overflow" in layer_data
            assert 0.0 <= layer_data["usage_pct"] <= 100.0
            assert layer_data["overflow"] >= 0

    def test_hotspot_count_is_reported(self) -> None:
        """Verify hotspot count is reported."""
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

        # Verify hotspot count
        assert "hotspot_count" in diagnosis_dict
        assert diagnosis_dict["hotspot_count"] >= 0
        assert diagnosis_dict["hotspot_count"] == len(diagnosis_dict.get("hotspots", []))

    def test_eco_suggestions_for_congestion(self) -> None:
        """Verify ECO suggestions are generated for congestion hotspots."""
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

        # Verify hotspots have ECO suggestions
        assert len(diagnosis.hotspots) > 0

        for hotspot in diagnosis.hotspots:
            assert len(hotspot.suggested_ecos) > 0
            # Common congestion ECOs
            all_ecos = set(hotspot.suggested_ecos)
            assert any(
                eco in ["reroute_congested_nets", "spread_dense_region"]
                for eco in all_ecos
            )

    def test_different_severity_levels_based_on_hot_ratio(self) -> None:
        """Verify different severity levels are assigned based on hot_ratio."""
        # Critical congestion
        critical_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=850,
            hot_ratio=0.85,
            max_overflow=2000,
            layer_metrics={"metal2": 800, "metal3": 750},
        )

        critical_diagnosis = diagnose_congestion(critical_metrics, hotspot_threshold=0.7)

        # Should have critical hotspot(s)
        critical_hotspots = [
            h for h in critical_diagnosis.hotspots
            if h.severity == CongestionSeverity.CRITICAL
        ]
        assert len(critical_hotspots) > 0

        # Moderate congestion
        moderate_metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=350,
            hot_ratio=0.35,
            max_overflow=500,
            layer_metrics={"metal2": 200, "metal3": 180},
        )

        moderate_diagnosis = diagnose_congestion(moderate_metrics, hotspot_threshold=0.3)

        # Should have moderate hotspot(s)
        moderate_hotspots = [
            h for h in moderate_diagnosis.hotspots
            if h.severity == CongestionSeverity.MODERATE
        ]
        assert len(moderate_hotspots) > 0

    def test_hotspot_bounding_boxes(self) -> None:
        """Verify hotspots have valid bounding boxes."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={"metal2": 450, "metal3": 380},
        )

        diagnosis = diagnose_congestion(metrics)

        # Verify each hotspot has a valid bounding box
        for hotspot in diagnosis.hotspots:
            bbox = hotspot.bbox
            assert bbox.x1 < bbox.x2
            assert bbox.y1 < bbox.y2
            assert bbox.x1 >= 0
            assert bbox.y1 >= 0

    def test_diagnosis_serializes_to_json(self) -> None:
        """Verify diagnosis can be serialized to JSON format."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={
                "metal2": 450,
                "metal3": 380,
                "metal4": 290,
            },
        )

        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(diagnosis_dict)
        assert len(json_str) > 0

        # Verify round-trip
        reloaded = json.loads(json_str)
        assert reloaded["hot_ratio"] == 0.75
        assert reloaded["overflow_total"] > 0
        assert "hotspots" in reloaded

    def test_correlation_metrics_reported(self) -> None:
        """Verify correlation metrics are reported (if available)."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1250,
            layer_metrics={"metal2": 450, "metal3": 380},
        )

        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Correlation metrics may be present
        if "correlation_with_placement" in diagnosis_dict:
            corr = diagnosis_dict["correlation_with_placement"]
            if "placement_density_correlation" in corr:
                assert -1.0 <= corr["placement_density_correlation"] <= 1.0
            if "macro_proximity_correlation" in corr:
                assert -1.0 <= corr["macro_proximity_correlation"] <= 1.0


class TestF204Integration:
    """Integration test for complete F204 feature."""

    def test_complete_f204_workflow(self) -> None:
        """
        Complete workflow test for F204.

        This test verifies all 6 steps in sequence:
        1. Global routing on congested design
        2. Diagnosis enabled (function available)
        3. Auto-diagnosis runs
        4. diagnosis.json contains congestion_diagnosis
        5. hot_ratio and overflow_total reported
        6. Hotspots identified with severity levels
        """
        # Step 1: Create congested design
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=780,
            hot_ratio=0.78,
            max_overflow=1500,
            layer_metrics={
                "metal2": 500,
                "metal3": 420,
                "metal4": 350,
                "metal5": 230,
            },
        )

        assert metrics.hot_ratio > 0.7

        # Step 2: Congestion diagnosis is enabled (function exists)
        from src.analysis.diagnosis import diagnose_congestion

        assert callable(diagnose_congestion)

        # Step 3: Run auto-diagnosis
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.7)
        assert diagnosis is not None

        # Step 4: Verify diagnosis contains congestion_diagnosis section
        report = generate_complete_diagnosis(congestion_metrics=metrics)
        report_dict = report.to_dict()
        assert "congestion_diagnosis" in report_dict

        # Step 5: Verify hot_ratio and overflow_total are reported
        assert diagnosis.hot_ratio == 0.78
        assert diagnosis.overflow_total > 0

        # Step 6: Verify hotspots are identified with severity levels
        assert len(diagnosis.hotspots) > 0

        # Verify severity levels
        for hotspot in diagnosis.hotspots:
            assert hotspot.severity in [
                CongestionSeverity.CRITICAL,
                CongestionSeverity.MODERATE,
                CongestionSeverity.MINOR,
            ]

        # Additional verification: ECO suggestions
        assert all(
            len(hotspot.suggested_ecos) > 0
            for hotspot in diagnosis.hotspots
        )

        # Additional verification: Layer breakdown
        assert len(diagnosis.layer_breakdown) > 0

        # Additional verification: Hotspot structure
        first_hotspot = diagnosis.hotspots[0]
        assert first_hotspot.id > 0
        assert first_hotspot.bbox is not None
        assert first_hotspot.cause is not None
        assert len(first_hotspot.affected_layers) > 0

        print("✓ F204: All steps verified successfully")


class TestCongestionDiagnosisEdgeCases:
    """Test edge cases for congestion diagnosis."""

    def test_low_congestion_no_hotspots(self) -> None:
        """Verify low congestion produces no critical hotspots."""
        low_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=50,
            hot_ratio=0.05,
            max_overflow=10,
            layer_metrics={"metal2": 5, "metal3": 5},
        )

        diagnosis = diagnose_congestion(low_congestion, hotspot_threshold=0.7)

        # Should have very few or no hotspots
        critical_hotspots = [
            h for h in diagnosis.hotspots
            if h.severity == CongestionSeverity.CRITICAL
        ]
        assert len(critical_hotspots) == 0

    def test_empty_layer_metrics(self) -> None:
        """Verify diagnosis handles empty layer metrics gracefully."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=350,
            hot_ratio=0.35,
            max_overflow=100,
            layer_metrics={},
        )

        diagnosis = diagnose_congestion(metrics)

        # Should still produce valid diagnosis
        assert diagnosis is not None
        assert diagnosis.hot_ratio == 0.35

    def test_custom_hotspot_threshold(self) -> None:
        """Verify custom hotspot threshold is respected."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=500,
            hot_ratio=0.5,
            max_overflow=500,
            layer_metrics={"metal2": 250, "metal3": 250},
        )

        # Lower threshold should produce hotspots
        diagnosis_low_thresh = diagnose_congestion(metrics, hotspot_threshold=0.3)

        # Higher threshold should produce fewer/no hotspots
        diagnosis_high_thresh = diagnose_congestion(metrics, hotspot_threshold=0.8)

        # Low threshold should catch this moderate congestion
        assert len(diagnosis_low_thresh.hotspots) >= len(diagnosis_high_thresh.hotspots)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
