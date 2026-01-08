"""Tests for ECO effectiveness comparison across multiple Cases.

Tests for Feature #72: Compare ECO effectiveness across multiple Cases in comparative study

This test suite validates:
1. ECO effectiveness aggregation across multiple Cases
2. Ranking ECOs by aggregate effectiveness
3. Identifying best-performing ECO classes
4. Comparative report generation
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior
from src.controller.eco_comparison import (
    ECOClassComparison,
    ECOComparator,
    ECOComparisonMetrics,
)
from src.controller.types import ECOClass


class TestECOComparisonMetrics:
    """Test ECOComparisonMetrics aggregation."""

    def test_create_empty_metrics(self) -> None:
        """Test creating empty comparison metrics."""
        metrics = ECOComparisonMetrics(eco_name="buffer_insertion")

        assert metrics.eco_name == "buffer_insertion"
        assert metrics.total_cases == 0
        assert metrics.total_applications == 0
        assert metrics.success_rate == 0.0
        assert metrics.improvement_rate == 0.0

    def test_add_single_case_data(self) -> None:
        """Test adding effectiveness data from a single Case."""
        metrics = ECOComparisonMetrics(eco_name="buffer_insertion")

        # Create effectiveness from a Case
        effectiveness = ECOEffectiveness(eco_name="buffer_insertion")
        effectiveness.update(success=True, wns_delta_ps=500.0)
        effectiveness.update(success=True, wns_delta_ps=600.0)

        # Add to comparison metrics
        metrics.add_case_data(case_id="case1", effectiveness=effectiveness)

        assert metrics.total_cases == 1
        assert metrics.total_applications == 2
        assert metrics.successful_applications == 2
        assert metrics.failed_applications == 0
        assert metrics.success_rate == 1.0
        assert metrics.average_wns_improvement_ps == 550.0

    def test_add_multiple_case_data(self) -> None:
        """Test aggregating data from multiple Cases."""
        metrics = ECOComparisonMetrics(
            eco_name="buffer_insertion",
            eco_class=ECOClass.PLACEMENT_LOCAL
        )

        # Case 1: 2 successful applications
        eff1 = ECOEffectiveness(eco_name="buffer_insertion")
        eff1.update(success=True, wns_delta_ps=500.0)
        eff1.update(success=True, wns_delta_ps=600.0)
        metrics.add_case_data(case_id="case1", effectiveness=eff1)

        # Case 2: 1 successful, 1 failed
        eff2 = ECOEffectiveness(eco_name="buffer_insertion")
        eff2.update(success=True, wns_delta_ps=400.0)
        eff2.update(success=False, wns_delta_ps=-200.0)
        metrics.add_case_data(case_id="case2", effectiveness=eff2)

        # Verify aggregation
        assert metrics.total_cases == 2
        assert metrics.total_applications == 4
        assert metrics.successful_applications == 3
        assert metrics.failed_applications == 1
        assert metrics.success_rate == 0.75  # 3/4

        # Average WNS improvement across all 4 applications
        expected_avg = (500.0 + 600.0 + 400.0 + (-200.0)) / 4
        assert abs(metrics.average_wns_improvement_ps - expected_avg) < 0.01

    def test_case_impact_classification(self) -> None:
        """Test classification of Cases as improved/degraded/neutral."""
        metrics = ECOComparisonMetrics(eco_name="test_eco")

        # Case with significant improvement (>100 ps)
        eff1 = ECOEffectiveness(eco_name="test_eco")
        eff1.update(success=True, wns_delta_ps=500.0)
        metrics.add_case_data(case_id="improved_case", effectiveness=eff1)

        # Case with significant degradation (<-100 ps)
        eff2 = ECOEffectiveness(eco_name="test_eco")
        eff2.update(success=True, wns_delta_ps=-300.0)
        metrics.add_case_data(case_id="degraded_case", effectiveness=eff2)

        # Case with minimal impact (-100 to 100 ps)
        eff3 = ECOEffectiveness(eco_name="test_eco")
        eff3.update(success=True, wns_delta_ps=50.0)
        metrics.add_case_data(case_id="neutral_case", effectiveness=eff3)

        assert metrics.cases_improved == 1
        assert metrics.cases_degraded == 1
        assert metrics.cases_neutral == 1
        assert metrics.improvement_rate == 1.0 / 3.0

    def test_best_worst_tracking(self) -> None:
        """Test tracking of best improvement and worst degradation."""
        metrics = ECOComparisonMetrics(eco_name="test_eco")

        # Case 1: moderate improvement
        eff1 = ECOEffectiveness(eco_name="test_eco")
        eff1.update(success=True, wns_delta_ps=500.0)
        eff1.update(success=True, wns_delta_ps=700.0)
        metrics.add_case_data(case_id="case1", effectiveness=eff1)

        # Case 2: best improvement and worst degradation
        eff2 = ECOEffectiveness(eco_name="test_eco")
        eff2.update(success=True, wns_delta_ps=1200.0)  # Best
        eff2.update(success=True, wns_delta_ps=-800.0)  # Worst
        metrics.add_case_data(case_id="case2", effectiveness=eff2)

        assert metrics.best_wns_improvement_ps == 1200.0
        assert metrics.worst_wns_degradation_ps == -800.0

    def test_to_dict_serialization(self) -> None:
        """Test conversion to dictionary for JSON serialization."""
        metrics = ECOComparisonMetrics(
            eco_name="buffer_insertion",
            eco_class=ECOClass.PLACEMENT_LOCAL
        )

        eff = ECOEffectiveness(eco_name="buffer_insertion")
        eff.update(success=True, wns_delta_ps=500.0)
        metrics.add_case_data(case_id="case1", effectiveness=eff)

        data = metrics.to_dict()

        assert data["eco_name"] == "buffer_insertion"
        assert data["eco_class"] == "placement_local"
        assert data["total_cases"] == 1
        assert data["total_applications"] == 1
        assert data["success_rate"] == 1.0
        assert "per_case_effectiveness" in data


class TestECOComparator:
    """Test ECOComparator for multi-Case comparison."""

    def test_create_comparator(self) -> None:
        """Test creating empty comparator."""
        comparator = ECOComparator()

        assert len(comparator.eco_metrics) == 0
        assert len(comparator.eco_class_map) == 0

    def test_add_single_case_eco_data(self) -> None:
        """Test adding ECO data from a single Case."""
        comparator = ECOComparator()

        # Create effectiveness map for a Case
        effectiveness_map = {
            "buffer_insertion": ECOEffectiveness(eco_name="buffer_insertion"),
            "placement_density": ECOEffectiveness(eco_name="placement_density"),
        }

        effectiveness_map["buffer_insertion"].update(success=True, wns_delta_ps=500.0)
        effectiveness_map["placement_density"].update(success=True, wns_delta_ps=300.0)

        eco_class_map = {
            "buffer_insertion": ECOClass.PLACEMENT_LOCAL,
            "placement_density": ECOClass.ROUTING_AFFECTING,
        }

        comparator.add_case_eco_data(
            case_id="case1",
            eco_effectiveness_map=effectiveness_map,
            eco_class_map=eco_class_map,
        )

        assert len(comparator.eco_metrics) == 2
        assert "buffer_insertion" in comparator.eco_metrics
        assert "placement_density" in comparator.eco_metrics
        assert comparator.eco_metrics["buffer_insertion"].total_cases == 1

    def test_add_multiple_cases_eco_data(self) -> None:
        """Test aggregating ECO data from multiple Cases."""
        comparator = ECOComparator()

        eco_class_map = {
            "buffer_insertion": ECOClass.PLACEMENT_LOCAL,
            "noop": ECOClass.TOPOLOGY_NEUTRAL,
        }

        # Case 1
        eff_map_1 = {
            "buffer_insertion": ECOEffectiveness(eco_name="buffer_insertion"),
            "noop": ECOEffectiveness(eco_name="noop"),
        }
        eff_map_1["buffer_insertion"].update(success=True, wns_delta_ps=500.0)
        eff_map_1["noop"].update(success=True, wns_delta_ps=0.0)

        comparator.add_case_eco_data("case1", eff_map_1, eco_class_map)

        # Case 2
        eff_map_2 = {
            "buffer_insertion": ECOEffectiveness(eco_name="buffer_insertion"),
            "noop": ECOEffectiveness(eco_name="noop"),
        }
        eff_map_2["buffer_insertion"].update(success=True, wns_delta_ps=600.0)
        eff_map_2["noop"].update(success=True, wns_delta_ps=0.0)

        comparator.add_case_eco_data("case2", eff_map_2, eco_class_map)

        # Verify aggregation
        buffer_metrics = comparator.eco_metrics["buffer_insertion"]
        assert buffer_metrics.total_cases == 2
        assert buffer_metrics.total_applications == 2
        assert buffer_metrics.successful_applications == 2

    def test_get_ranked_ecos_by_wns_improvement(self) -> None:
        """Test ranking ECOs by average WNS improvement."""
        comparator = ECOComparator()

        eco_class_map = {
            "buffer_insertion": ECOClass.PLACEMENT_LOCAL,
            "placement_density": ECOClass.ROUTING_AFFECTING,
            "noop": ECOClass.TOPOLOGY_NEUTRAL,
        }

        # Add data for 3 ECOs across 2 Cases
        for case_id in ["case1", "case2"]:
            eff_map = {
                "buffer_insertion": ECOEffectiveness(eco_name="buffer_insertion"),
                "placement_density": ECOEffectiveness(eco_name="placement_density"),
                "noop": ECOEffectiveness(eco_name="noop"),
            }

            # Buffer insertion: high improvement
            eff_map["buffer_insertion"].update(success=True, wns_delta_ps=800.0)

            # Placement density: moderate improvement
            eff_map["placement_density"].update(success=True, wns_delta_ps=400.0)

            # Noop: no improvement
            eff_map["noop"].update(success=True, wns_delta_ps=0.0)

            comparator.add_case_eco_data(case_id, eff_map, eco_class_map)

        # Get ranked ECOs
        ranked = comparator.get_ranked_ecos(sort_by="average_wns_improvement")

        assert len(ranked) == 3
        assert ranked[0].eco_name == "buffer_insertion"
        assert ranked[1].eco_name == "placement_density"
        assert ranked[2].eco_name == "noop"

    def test_get_ranked_ecos_by_success_rate(self) -> None:
        """Test ranking ECOs by success rate."""
        comparator = ECOComparator()

        # ECO 1: 100% success rate
        eff1 = ECOEffectiveness(eco_name="reliable_eco")
        eff1.update(success=True, wns_delta_ps=300.0)
        eff1.update(success=True, wns_delta_ps=400.0)

        # ECO 2: 50% success rate
        eff2 = ECOEffectiveness(eco_name="unreliable_eco")
        eff2.update(success=True, wns_delta_ps=500.0)
        eff2.update(success=False, wns_delta_ps=-100.0)

        comparator.add_case_eco_data("case1", {"reliable_eco": eff1, "unreliable_eco": eff2})

        ranked = comparator.get_ranked_ecos(sort_by="success_rate")

        assert ranked[0].eco_name == "reliable_eco"
        assert ranked[0].success_rate == 1.0
        assert ranked[1].eco_name == "unreliable_eco"
        assert ranked[1].success_rate == 0.5

    def test_get_ranked_ecos_min_applications_filter(self) -> None:
        """Test filtering ECOs by minimum applications."""
        comparator = ECOComparator()

        # ECO with 1 application
        eff1 = ECOEffectiveness(eco_name="rarely_used")
        eff1.update(success=True, wns_delta_ps=1000.0)

        # ECO with 5 applications
        eff2 = ECOEffectiveness(eco_name="frequently_used")
        for _ in range(5):
            eff2.update(success=True, wns_delta_ps=300.0)

        comparator.add_case_eco_data("case1", {"rarely_used": eff1, "frequently_used": eff2})

        # With min_applications=3, only frequently_used should appear
        ranked = comparator.get_ranked_ecos(min_applications=3)

        assert len(ranked) == 1
        assert ranked[0].eco_name == "frequently_used"

    def test_get_eco_class_comparison(self) -> None:
        """Test aggregating comparison by ECO class."""
        comparator = ECOComparator()

        eco_class_map = {
            "buffer_insertion": ECOClass.PLACEMENT_LOCAL,
            "timing_optimization": ECOClass.PLACEMENT_LOCAL,
            "density_reduction": ECOClass.ROUTING_AFFECTING,
        }

        # Add data for 3 ECOs (2 in PLACEMENT_LOCAL, 1 in ROUTING_AFFECTING)
        eff_map = {
            "buffer_insertion": ECOEffectiveness(eco_name="buffer_insertion"),
            "timing_optimization": ECOEffectiveness(eco_name="timing_optimization"),
            "density_reduction": ECOEffectiveness(eco_name="density_reduction"),
        }

        eff_map["buffer_insertion"].update(success=True, wns_delta_ps=500.0)
        eff_map["timing_optimization"].update(success=True, wns_delta_ps=600.0)
        eff_map["density_reduction"].update(success=True, wns_delta_ps=300.0)

        comparator.add_case_eco_data("case1", eff_map, eco_class_map)

        # Get ECO class comparison
        class_comp = comparator.get_eco_class_comparison()

        assert len(class_comp) == 2

        # Find PLACEMENT_LOCAL class
        placement_local = next(c for c in class_comp if c.eco_class == ECOClass.PLACEMENT_LOCAL)
        assert placement_local.eco_count == 2
        assert placement_local.total_applications == 2

        # PLACEMENT_LOCAL should rank first (avg improvement: 550 ps)
        assert class_comp[0].eco_class == ECOClass.PLACEMENT_LOCAL

    def test_generate_comparison_report(self) -> None:
        """Test generation of human-readable comparison report."""
        comparator = ECOComparator()

        eco_class_map = {
            "buffer_insertion": ECOClass.PLACEMENT_LOCAL,
            "noop": ECOClass.TOPOLOGY_NEUTRAL,
        }

        # Add sample data
        eff_map = {
            "buffer_insertion": ECOEffectiveness(eco_name="buffer_insertion"),
            "noop": ECOEffectiveness(eco_name="noop"),
        }
        eff_map["buffer_insertion"].update(success=True, wns_delta_ps=500.0)
        eff_map["noop"].update(success=True, wns_delta_ps=0.0)

        comparator.add_case_eco_data("case1", eff_map, eco_class_map)

        # Generate report
        report = comparator.generate_comparison_report(top_n=5)

        # Verify report content
        assert "ECO EFFECTIVENESS COMPARISON REPORT" in report
        assert "SUMMARY" in report
        assert "Total ECOs Analyzed:" in report
        assert "buffer_insertion" in report
        assert "ECO CLASS COMPARISON" in report

    def test_write_comparison_report(self) -> None:
        """Test writing comparison report to file."""
        comparator = ECOComparator()

        # Add minimal data
        eff = ECOEffectiveness(eco_name="test_eco")
        eff.update(success=True, wns_delta_ps=100.0)
        comparator.add_case_eco_data("case1", {"test_eco": eff})

        # Write to temporary file
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "comparison_report.txt"
            result_path = comparator.write_comparison_report(report_path, top_n=3)

            # Verify file was created
            assert result_path.exists()
            assert result_path == report_path

            # Verify content
            content = result_path.read_text()
            assert "ECO EFFECTIVENESS COMPARISON REPORT" in content

    def test_to_dict_serialization(self) -> None:
        """Test conversion to dictionary for JSON export."""
        comparator = ECOComparator()

        eco_class_map = {
            "buffer_insertion": ECOClass.PLACEMENT_LOCAL,
        }

        eff = ECOEffectiveness(eco_name="buffer_insertion")
        eff.update(success=True, wns_delta_ps=500.0)

        comparator.add_case_eco_data("case1", {"buffer_insertion": eff}, eco_class_map)

        # Convert to dict
        data = comparator.to_dict()

        assert "eco_metrics" in data
        assert "eco_class_comparison" in data
        assert "ranked_ecos" in data
        assert "buffer_insertion" in data["eco_metrics"]

        # Verify JSON serializable
        json_str = json.dumps(data)
        assert len(json_str) > 0


class TestECOClassComparison:
    """Test ECO class-level comparison."""

    def test_create_eco_class_comparison(self) -> None:
        """Test creating ECO class comparison."""
        comp = ECOClassComparison(eco_class=ECOClass.PLACEMENT_LOCAL)

        assert comp.eco_class == ECOClass.PLACEMENT_LOCAL
        assert comp.eco_count == 0
        assert comp.total_applications == 0
        assert comp.success_rate == 0.0

    def test_to_dict_serialization(self) -> None:
        """Test conversion to dictionary."""
        comp = ECOClassComparison(
            eco_class=ECOClass.ROUTING_AFFECTING,
            eco_count=5,
            total_applications=20,
            successful_applications=18,
            average_wns_improvement_ps=450.0,
        )

        data = comp.to_dict()

        assert data["eco_class"] == "routing_affecting"
        assert data["eco_count"] == 5
        assert data["total_applications"] == 20
        assert data["success_rate"] == 0.9
        assert data["average_wns_improvement_ps"] == 450.0


class TestECOComparisonEndToEnd:
    """End-to-end tests simulating real Study comparison."""

    def test_multi_case_study_comparison(self) -> None:
        """Test complete workflow: Define Study with multiple Cases,
        execute (simulated), collect metrics, generate comparative report."""

        comparator = ECOComparator()

        # Define ECO classes
        eco_class_map = {
            "noop": ECOClass.TOPOLOGY_NEUTRAL,
            "buffer_insertion": ECOClass.PLACEMENT_LOCAL,
            "placement_density": ECOClass.ROUTING_AFFECTING,
            "clock_tree_synthesis": ECOClass.GLOBAL_DISRUPTIVE,
        }

        # Simulate 3 Cases with different ECO effectiveness patterns
        cases = ["nangate45_base", "nangate45_stressed", "nangate45_optimized"]

        for case_id in cases:
            eff_map: dict[str, ECOEffectiveness] = {}

            # Base case: noop always runs
            noop_eff = ECOEffectiveness(eco_name="noop")
            noop_eff.update(success=True, wns_delta_ps=0.0)
            eff_map["noop"] = noop_eff

            # Buffer insertion: consistently helpful
            buffer_eff = ECOEffectiveness(eco_name="buffer_insertion")
            buffer_eff.update(success=True, wns_delta_ps=600.0)
            buffer_eff.update(success=True, wns_delta_ps=550.0)
            eff_map["buffer_insertion"] = buffer_eff

            # Placement density: moderate improvement, some failures
            density_eff = ECOEffectiveness(eco_name="placement_density")
            density_eff.update(success=True, wns_delta_ps=300.0)
            density_eff.update(success=False, wns_delta_ps=-100.0)
            eff_map["placement_density"] = density_eff

            # Clock tree synthesis: high risk, variable results
            cts_eff = ECOEffectiveness(eco_name="clock_tree_synthesis")
            cts_eff.update(success=True, wns_delta_ps=1000.0)
            cts_eff.update(success=False, wns_delta_ps=-500.0)
            eff_map["clock_tree_synthesis"] = cts_eff

            comparator.add_case_eco_data(case_id, eff_map, eco_class_map)

        # Rank ECOs by aggregate effectiveness
        ranked = comparator.get_ranked_ecos(sort_by="average_wns_improvement")

        # Verify ranking
        assert len(ranked) == 4
        assert ranked[0].eco_name == "buffer_insertion"  # Most consistent
        assert ranked[0].total_cases == 3
        assert ranked[0].total_applications == 6  # 2 applications per case

        # Identify best-performing ECO classes
        class_comparison = comparator.get_eco_class_comparison()
        assert len(class_comparison) > 0

        # Generate comparative report
        report = comparator.generate_comparison_report(top_n=10)
        assert "buffer_insertion" in report
        assert "ECO CLASS COMPARISON" in report

        # Export to JSON
        data = comparator.to_dict()
        assert len(data["eco_metrics"]) == 4
        assert len(data["ranked_ecos"]) == 4

    def test_ranking_criteria_consistency(self) -> None:
        """Test that different ranking criteria produce consistent results."""
        comparator = ECOComparator()

        # Create ECOs with distinct characteristics
        # ECO 1: High WNS improvement, low success rate (33%)
        eff1 = ECOEffectiveness(eco_name="high_impact_risky")
        eff1.update(success=True, wns_delta_ps=3000.0)  # One big win
        eff1.update(success=False, wns_delta_ps=-100.0)  # Two failures
        eff1.update(success=False, wns_delta_ps=-100.0)
        # Average: (3000 - 100 - 100) / 3 = 933.3 ps

        # ECO 2: Moderate WNS improvement, high success rate (100%)
        eff2 = ECOEffectiveness(eco_name="moderate_reliable")
        eff2.update(success=True, wns_delta_ps=400.0)
        eff2.update(success=True, wns_delta_ps=400.0)
        eff2.update(success=True, wns_delta_ps=400.0)
        # Average: 400 ps

        comparator.add_case_eco_data(
            "case1",
            {"high_impact_risky": eff1, "moderate_reliable": eff2}
        )

        # Rank by WNS improvement
        by_wns = comparator.get_ranked_ecos(sort_by="average_wns_improvement")
        # Rank by success rate
        by_success = comparator.get_ranked_ecos(sort_by="success_rate")

        # Different criteria should produce different rankings
        assert by_wns[0].eco_name != by_success[0].eco_name
        assert by_wns[0].eco_name == "high_impact_risky"  # Better avg WNS improvement
        assert by_success[0].eco_name == "moderate_reliable"  # 100% success rate
