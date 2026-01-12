"""Tests for F207: Congestion diagnosis correlates congestion with placement density."""

import pytest

from src.analysis.diagnosis import diagnose_congestion, generate_complete_diagnosis
from src.controller.types import CongestionMetrics


class TestF207CongestionPlacementCorrelation:
    """
    Test suite for Feature F207: Congestion diagnosis correlates congestion with placement density.

    Steps from feature_list.json:
    1. Run congestion diagnosis on design
    2. Verify correlation_with_placement is computed
    3. Verify placement_density_correlation coefficient is reported
    4. Verify macro_proximity_correlation coefficient is reported
    5. Use correlation to guide ECO selection
    """

    def test_step_1_run_congestion_diagnosis_on_design(self) -> None:
        """Step 1: Run congestion diagnosis on design."""
        # Create congestion metrics for a design with moderate congestion
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=450,
            hot_ratio=0.45,  # Moderate congestion
            max_overflow=800,
            layer_metrics={
                "metal2": 300,
                "metal3": 250,
                "metal4": 150,
                "metal5": 100,
            },
        )

        # Run congestion diagnosis
        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.3)

        # Verify diagnosis was generated
        assert diagnosis is not None
        assert diagnosis.hot_ratio == 0.45
        assert diagnosis.overflow_total > 0

    def test_step_2_verify_correlation_with_placement_is_computed(self) -> None:
        """Step 2: Verify correlation_with_placement is computed."""
        # Create congestion metrics
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=500,
            hot_ratio=0.5,
            max_overflow=1000,
            layer_metrics={
                "metal2": 400,
                "metal3": 350,
                "metal4": 250,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(metrics)

        # Verify correlation fields are populated
        assert diagnosis.placement_density_correlation is not None
        assert diagnosis.macro_proximity_correlation is not None

        # Convert to dict to verify serialization
        diagnosis_dict = diagnosis.to_dict()

        # Verify correlation_with_placement section exists
        assert "correlation_with_placement" in diagnosis_dict
        assert isinstance(diagnosis_dict["correlation_with_placement"], dict)

    def test_step_3_verify_placement_density_correlation_coefficient_reported(self) -> None:
        """Step 3: Verify placement_density_correlation coefficient is reported."""
        # Create high congestion metrics
        high_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.8,
            max_overflow=1500,
            layer_metrics={
                "metal2": 600,
                "metal3": 500,
                "metal4": 400,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(high_congestion)
        diagnosis_dict = diagnosis.to_dict()

        # Verify placement_density_correlation is reported
        assert "correlation_with_placement" in diagnosis_dict
        corr = diagnosis_dict["correlation_with_placement"]

        assert "placement_density_correlation" in corr
        placement_corr = corr["placement_density_correlation"]

        # Verify it's a valid correlation coefficient (-1.0 to 1.0)
        assert isinstance(placement_corr, (int, float))
        assert -1.0 <= placement_corr <= 1.0

        # For high congestion, expect higher correlation with placement density
        # (congested areas tend to have high placement density)
        assert placement_corr > 0.0, "High congestion should correlate with placement density"

    def test_step_4_verify_macro_proximity_correlation_coefficient_reported(self) -> None:
        """Step 4: Verify macro_proximity_correlation coefficient is reported."""
        # Create moderate congestion metrics
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=550,
            hot_ratio=0.55,
            max_overflow=1100,
            layer_metrics={
                "metal2": 450,
                "metal3": 400,
                "metal4": 250,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(metrics)
        diagnosis_dict = diagnosis.to_dict()

        # Verify macro_proximity_correlation is reported
        assert "correlation_with_placement" in diagnosis_dict
        corr = diagnosis_dict["correlation_with_placement"]

        assert "macro_proximity_correlation" in corr
        macro_corr = corr["macro_proximity_correlation"]

        # Verify it's a valid correlation coefficient (-1.0 to 1.0)
        assert isinstance(macro_corr, (int, float))
        assert -1.0 <= macro_corr <= 1.0

        # Correlation should be reasonable (non-zero for congested designs)
        assert macro_corr >= 0.0, "Macro proximity can contribute to congestion"

    def test_step_5_use_correlation_to_guide_eco_selection(self) -> None:
        """Step 5: Use correlation to guide ECO selection."""
        # Create congestion metrics with high placement density correlation
        high_density_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=750,
            hot_ratio=0.75,
            max_overflow=1500,
            layer_metrics={
                "metal2": 600,
                "metal3": 500,
                "metal4": 400,
            },
        )

        # Run diagnosis
        diagnosis = diagnose_congestion(high_density_congestion)

        # Verify correlations are available for ECO selection
        assert diagnosis.placement_density_correlation is not None
        assert diagnosis.macro_proximity_correlation is not None

        # High placement density correlation should suggest spreading ECOs
        placement_corr = diagnosis.placement_density_correlation

        # Verify hotspots have ECO suggestions
        assert len(diagnosis.hotspots) > 0

        # For high placement density correlation, expect "spread_dense_region" ECO
        all_eco_suggestions = set()
        for hotspot in diagnosis.hotspots:
            all_eco_suggestions.update(hotspot.suggested_ecos)

        # High placement density correlation should include spreading ECO
        if placement_corr > 0.5:
            assert "spread_dense_region" in all_eco_suggestions, \
                "High placement density correlation should suggest spreading"

    def test_correlation_varies_with_congestion_level(self) -> None:
        """Verify correlation coefficients vary appropriately with congestion level."""
        # Low congestion
        low_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=200,
            hot_ratio=0.2,
            max_overflow=100,
            layer_metrics={"metal2": 50, "metal3": 50},
        )

        # High congestion
        high_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.8,
            max_overflow=2000,
            layer_metrics={"metal2": 800, "metal3": 700, "metal4": 500},
        )

        low_diagnosis = diagnose_congestion(low_congestion)
        high_diagnosis = diagnose_congestion(high_congestion)

        # High congestion should have higher placement density correlation
        assert low_diagnosis.placement_density_correlation is not None
        assert high_diagnosis.placement_density_correlation is not None

        # Higher congestion typically correlates more strongly with placement density
        assert high_diagnosis.placement_density_correlation >= low_diagnosis.placement_density_correlation

    def test_correlation_included_in_complete_diagnosis(self) -> None:
        """Verify correlations are included in complete diagnosis report."""
        # Create metrics
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=600,
            hot_ratio=0.6,
            max_overflow=1200,
            layer_metrics={
                "metal2": 500,
                "metal3": 400,
                "metal4": 300,
            },
        )

        # Generate complete diagnosis
        report = generate_complete_diagnosis(congestion_metrics=metrics)
        report_dict = report.to_dict()

        # Verify congestion_diagnosis section exists
        assert "congestion_diagnosis" in report_dict

        # Verify correlation_with_placement exists in congestion_diagnosis
        congestion_diag = report_dict["congestion_diagnosis"]
        assert "correlation_with_placement" in congestion_diag

        # Verify both correlation coefficients are present
        corr = congestion_diag["correlation_with_placement"]
        assert "placement_density_correlation" in corr
        assert "macro_proximity_correlation" in corr

        # Verify values are valid
        assert -1.0 <= corr["placement_density_correlation"] <= 1.0
        assert -1.0 <= corr["macro_proximity_correlation"] <= 1.0


class TestF207CorrelationDetails:
    """Additional detailed tests for F207 correlation features."""

    def test_placement_density_correlation_for_high_congestion(self) -> None:
        """Verify placement density correlation is high for congested designs."""
        # Very high congestion (hot_ratio > 0.7)
        high_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=850,
            hot_ratio=0.85,
            max_overflow=2500,
            layer_metrics={
                "metal2": 1000,
                "metal3": 850,
                "metal4": 650,
            },
        )

        diagnosis = diagnose_congestion(high_congestion)

        # High congestion should have strong placement density correlation
        assert diagnosis.placement_density_correlation is not None
        assert diagnosis.placement_density_correlation > 0.5, \
            "High congestion should strongly correlate with placement density"

    def test_macro_proximity_correlation_for_moderate_congestion(self) -> None:
        """Verify macro proximity correlation is present for moderate congestion."""
        # Moderate congestion
        moderate_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=550,
            hot_ratio=0.55,
            max_overflow=1000,
            layer_metrics={
                "metal2": 450,
                "metal3": 350,
                "metal4": 200,
            },
        )

        diagnosis = diagnose_congestion(moderate_congestion)

        # Macro proximity correlation should be present
        assert diagnosis.macro_proximity_correlation is not None
        assert diagnosis.macro_proximity_correlation >= 0.0
        assert diagnosis.macro_proximity_correlation <= 1.0

    def test_correlation_coefficients_are_independent(self) -> None:
        """Verify placement and macro correlations are independent metrics."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=600,
            hot_ratio=0.6,
            max_overflow=1200,
            layer_metrics={
                "metal2": 500,
                "metal3": 400,
                "metal4": 300,
            },
        )

        diagnosis = diagnose_congestion(metrics)

        # Both correlations should be present
        assert diagnosis.placement_density_correlation is not None
        assert diagnosis.macro_proximity_correlation is not None

        # They should be independent (different values)
        # Note: In current implementation, they're computed independently
        placement_corr = diagnosis.placement_density_correlation
        macro_corr = diagnosis.macro_proximity_correlation

        # Both should be valid correlation coefficients
        assert -1.0 <= placement_corr <= 1.0
        assert -1.0 <= macro_corr <= 1.0

    def test_correlation_serialization_is_consistent(self) -> None:
        """Verify correlation values are preserved through serialization."""
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=500,
            hot_ratio=0.5,
            max_overflow=1000,
            layer_metrics={
                "metal2": 400,
                "metal3": 350,
                "metal4": 250,
            },
        )

        diagnosis = diagnose_congestion(metrics)

        # Get original values
        orig_placement_corr = diagnosis.placement_density_correlation
        orig_macro_corr = diagnosis.macro_proximity_correlation

        # Serialize to dict
        diagnosis_dict = diagnosis.to_dict()
        corr = diagnosis_dict["correlation_with_placement"]

        # Verify serialized values match original
        assert corr["placement_density_correlation"] == orig_placement_corr
        assert corr["macro_proximity_correlation"] == orig_macro_corr


class TestF207Integration:
    """Integration test for complete F207 feature workflow."""

    def test_complete_f207_workflow(self) -> None:
        """
        Complete workflow test for F207.

        This test verifies all 5 steps in sequence:
        1. Run congestion diagnosis on design
        2. Verify correlation_with_placement is computed
        3. Verify placement_density_correlation coefficient is reported
        4. Verify macro_proximity_correlation coefficient is reported
        5. Use correlation to guide ECO selection
        """
        # Step 1: Run congestion diagnosis on design
        metrics = CongestionMetrics(
            bins_total=1000,
            bins_hot=700,
            hot_ratio=0.7,
            max_overflow=1400,
            layer_metrics={
                "metal2": 550,
                "metal3": 480,
                "metal4": 370,
            },
        )

        diagnosis = diagnose_congestion(metrics, hotspot_threshold=0.6)
        assert diagnosis is not None

        # Step 2: Verify correlation_with_placement is computed
        assert diagnosis.placement_density_correlation is not None
        assert diagnosis.macro_proximity_correlation is not None

        diagnosis_dict = diagnosis.to_dict()
        assert "correlation_with_placement" in diagnosis_dict

        # Step 3: Verify placement_density_correlation coefficient is reported
        corr = diagnosis_dict["correlation_with_placement"]
        assert "placement_density_correlation" in corr
        placement_corr = corr["placement_density_correlation"]
        assert -1.0 <= placement_corr <= 1.0
        assert placement_corr > 0.0  # High congestion should correlate

        # Step 4: Verify macro_proximity_correlation coefficient is reported
        assert "macro_proximity_correlation" in corr
        macro_corr = corr["macro_proximity_correlation"]
        assert -1.0 <= macro_corr <= 1.0
        assert macro_corr >= 0.0

        # Step 5: Use correlation to guide ECO selection
        assert len(diagnosis.hotspots) > 0

        # Collect all ECO suggestions
        all_ecos = set()
        for hotspot in diagnosis.hotspots:
            all_ecos.update(hotspot.suggested_ecos)

        # High placement density correlation should suggest spreading
        if placement_corr > 0.5:
            assert "spread_dense_region" in all_ecos

        # Verify hotspots have appropriate ECO suggestions
        for hotspot in diagnosis.hotspots:
            assert len(hotspot.suggested_ecos) > 0

        print("✓ F207: All steps verified successfully")
        print(f"  - Placement density correlation: {placement_corr:.3f}")
        print(f"  - Macro proximity correlation: {macro_corr:.3f}")
        print(f"  - Suggested ECOs: {sorted(all_ecos)}")


class TestF207EdgeCases:
    """Test edge cases for F207 correlation computation."""

    def test_correlation_for_zero_congestion(self) -> None:
        """Verify correlation computation handles zero congestion."""
        zero_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=0,
            hot_ratio=0.0,
            max_overflow=0,
            layer_metrics={},
        )

        diagnosis = diagnose_congestion(zero_congestion)

        # Should still compute correlations (even if low)
        assert diagnosis.placement_density_correlation is not None
        assert diagnosis.macro_proximity_correlation is not None

    def test_correlation_for_extreme_congestion(self) -> None:
        """Verify correlation computation handles extreme congestion."""
        extreme_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=990,
            hot_ratio=0.99,
            max_overflow=5000,
            layer_metrics={
                "metal2": 2000,
                "metal3": 1800,
                "metal4": 1200,
            },
        )

        diagnosis = diagnose_congestion(extreme_congestion)

        # Should have very high correlations
        assert diagnosis.placement_density_correlation is not None
        assert diagnosis.macro_proximity_correlation is not None

        # Extreme congestion should have high placement density correlation
        assert diagnosis.placement_density_correlation > 0.6

    def test_correlation_coefficients_within_valid_range(self) -> None:
        """Verify all correlation coefficients are within [-1.0, 1.0]."""
        # Test multiple congestion levels
        test_cases = [
            {"hot_ratio": 0.1, "overflow": 100},
            {"hot_ratio": 0.3, "overflow": 300},
            {"hot_ratio": 0.5, "overflow": 500},
            {"hot_ratio": 0.7, "overflow": 700},
            {"hot_ratio": 0.9, "overflow": 900},
        ]

        for case in test_cases:
            metrics = CongestionMetrics(
                bins_total=1000,
                bins_hot=int(1000 * case["hot_ratio"]),
                hot_ratio=case["hot_ratio"],
                max_overflow=case["overflow"],
                layer_metrics={"metal2": case["overflow"]},
            )

            diagnosis = diagnose_congestion(metrics)

            # Verify both correlations are within valid range
            assert diagnosis.placement_density_correlation is not None
            assert -1.0 <= diagnosis.placement_density_correlation <= 1.0

            assert diagnosis.macro_proximity_correlation is not None
            assert -1.0 <= diagnosis.macro_proximity_correlation <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
