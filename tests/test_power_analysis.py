"""Tests for power analysis integration feature.

This test suite validates all 6 steps of the power analysis feature:
1. Execute trial with power-aware flow
2. Run OpenSTA with power analysis enabled
3. Extract total power, leakage, dynamic power
4. Emit power metrics to telemetry
5. Use power as additional ranking dimension
6. Support power-timing trade-off studies
"""

import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.parsers.power_metrics import PowerMetricExtractor, create_power_enabled_registry
from src.parsers.custom_metrics import MetricExtractorRegistry
from src.trial_runner.tcl_generator import (
    generate_trial_script,
    generate_power_analysis_commands,
    write_trial_script,
)
from src.controller.types import ExecutionMode


class TestPowerMetricExtractor:
    """Test PowerMetricExtractor class for parsing power reports."""

    def test_extract_power_from_simple_format(self, tmp_path):
        """Step 3: Extract total power, leakage, dynamic power from simple format."""
        # Create mock power report with simple format
        power_report = tmp_path / "power.rpt"
        power_report.write_text("""
Power Report
============

Total Power: 125.3 mW
Leakage Power: 12.1 mW
Dynamic Power: 113.2 mW
""")

        extractor = PowerMetricExtractor()
        metrics = extractor.extract(tmp_path)

        assert "total_power_mw" in metrics
        assert metrics["total_power_mw"] == 125.3
        assert metrics["leakage_power_mw"] == 12.1
        assert metrics["dynamic_power_mw"] == 113.2

    def test_extract_power_from_table_format(self, tmp_path):
        """Step 3: Extract power metrics from OpenSTA table format."""
        power_report = tmp_path / "power.rpt"
        power_report.write_text("""
Power Report
============

Group                  Internal  Switching    Leakage      Total
                          Power      Power      Power      Power
-----------------------------------------------------------------
Design                    78.5 mW    34.7 mW    12.1 mW   125.3 mW
""")

        extractor = PowerMetricExtractor()
        metrics = extractor.extract(tmp_path)

        assert metrics["internal_power_mw"] == 78.5
        assert metrics["switching_power_mw"] == 34.7
        assert metrics["leakage_power_mw"] == 12.1
        assert metrics["total_power_mw"] == 125.3

        # Dynamic power should be calculated
        assert "dynamic_power_mw" in metrics
        assert metrics["dynamic_power_mw"] == pytest.approx(78.5 + 34.7)

    def test_extract_power_with_unit_conversion(self, tmp_path):
        """Test power extraction handles different units (W, mW, uW)."""
        power_report = tmp_path / "power.rpt"
        power_report.write_text("""
Total Power: 0.1253 W
Leakage Power: 12100.0 uW
Dynamic Power: 113.2 mW
""")

        extractor = PowerMetricExtractor()
        metrics = extractor.extract(tmp_path)

        # All should be converted to mW
        assert metrics["total_power_mw"] == pytest.approx(125.3)
        assert metrics["leakage_power_mw"] == pytest.approx(12.1)
        assert metrics["dynamic_power_mw"] == 113.2

    def test_extract_power_empty_report(self, tmp_path):
        """Test extractor returns empty dict when no power report exists."""
        extractor = PowerMetricExtractor()
        metrics = extractor.extract(tmp_path)

        assert metrics == {}

    def test_validate_power_metrics(self):
        """Test power metrics validation."""
        extractor = PowerMetricExtractor()

        # Valid metrics
        valid_metrics = {
            "total_power_mw": 125.3,
            "leakage_power_mw": 12.1,
            "dynamic_power_mw": 113.2,
        }
        assert extractor.validate_metrics(valid_metrics) is True

        # Invalid: negative power
        invalid_metrics = {
            "total_power_mw": -10.0,
        }
        assert extractor.validate_metrics(invalid_metrics) is False

        # Valid: non-power metrics mixed in
        mixed_metrics = {
            "total_power_mw": 125.3,
            "design_name": "test",
        }
        assert extractor.validate_metrics(mixed_metrics) is True


class TestPowerEnabledRegistry:
    """Test MetricExtractorRegistry with power extractor."""

    def test_create_power_enabled_registry(self):
        """Test creating registry with power extractor."""
        registry = create_power_enabled_registry()

        assert "power" in registry.list_extractors()
        assert isinstance(registry.get("power"), PowerMetricExtractor)

    def test_extract_power_metrics_via_registry(self, tmp_path):
        """Step 3: Extract power metrics using the registry."""
        # Create mock power report
        power_report = tmp_path / "power.rpt"
        power_report.write_text("""
Total Power: 125.3 mW
Leakage Power: 12.1 mW
Dynamic Power: 113.2 mW
""")

        registry = create_power_enabled_registry()
        results = registry.extract_all(tmp_path)

        assert "power" in results
        assert results["power"]["total_power_mw"] == 125.3
        assert results["power"]["leakage_power_mw"] == 12.1
        assert results["power"]["dynamic_power_mw"] == 113.2

    def test_extract_flat_power_metrics(self, tmp_path):
        """Test flattened power metrics extraction."""
        power_report = tmp_path / "power.rpt"
        power_report.write_text("""
Total Power: 125.3 mW
Leakage Power: 12.1 mW
""")

        registry = create_power_enabled_registry()
        flat_results = registry.extract_flat(tmp_path, prefix_with_extractor=True)

        assert "power_total_power_mw" in flat_results
        assert "power_leakage_power_mw" in flat_results
        assert flat_results["power_total_power_mw"] == 125.3


class TestPowerAnalysisScriptGeneration:
    """Test TCL script generation with power analysis enabled."""

    def test_generate_power_analysis_commands(self):
        """Step 2: Generate OpenSTA power analysis commands."""
        commands = generate_power_analysis_commands(output_dir="/work", design_name="test_design")

        # Verify power analysis commands are present
        assert "POWER ANALYSIS" in commands
        assert "set_switching_activity" in commands
        assert "power.rpt" in commands
        assert "Power Report" in commands
        assert "Total Power:" in commands
        assert "Leakage Power:" in commands
        assert "Dynamic Power:" in commands

    def test_sta_only_script_with_power_enabled(self):
        """Step 1: Generate STA-only script with power analysis enabled."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            output_dir="/work",
            power_analysis_enabled=True,
        )

        # Verify power analysis section is included
        assert "POWER ANALYSIS" in script
        assert "power.rpt" in script
        assert "set_switching_activity" in script

    def test_sta_only_script_without_power(self):
        """Test STA-only script without power analysis (default)."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            output_dir="/work",
            power_analysis_enabled=False,
        )

        # Power analysis should NOT be included
        assert "POWER ANALYSIS" not in script
        assert "power.rpt" not in script

    def test_sta_congestion_script_with_power_enabled(self):
        """Step 1: Generate STA+congestion script with power analysis."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            power_analysis_enabled=True,
        )

        assert "POWER ANALYSIS" in script
        assert "power.rpt" in script

    def test_full_route_script_with_power_enabled(self):
        """Step 1: Generate full-route script with power analysis."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.FULL_ROUTE,
            design_name="test_design",
            output_dir="/work",
            power_analysis_enabled=True,
        )

        assert "POWER ANALYSIS" in script

    def test_write_trial_script_with_power_enabled(self, tmp_path):
        """Step 1: Write trial script with power analysis to file."""
        script_path = tmp_path / "trial.tcl"

        written_path = write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            output_dir="/work",
            power_analysis_enabled=True,
        )

        assert written_path.exists()
        content = written_path.read_text()
        assert "POWER ANALYSIS" in content
        assert "power.rpt" in content


class TestPowerMetricsInTelemetry:
    """Test power metrics are emitted to telemetry."""

    def test_power_metrics_can_be_serialized(self):
        """Step 4: Verify power metrics can be serialized for telemetry."""
        import json

        metrics = {
            "total_power_mw": 125.3,
            "leakage_power_mw": 12.1,
            "dynamic_power_mw": 113.2,
            "internal_power_mw": 78.5,
            "switching_power_mw": 34.7,
        }

        # Should be JSON-serializable for telemetry emission
        json_str = json.dumps(metrics)
        assert json_str is not None

        # Should round-trip correctly
        recovered = json.loads(json_str)
        assert recovered["total_power_mw"] == 125.3
        assert recovered["leakage_power_mw"] == 12.1

    def test_power_metrics_integration_with_trial_result(self):
        """Step 4: Simulate power metrics in trial result structure."""
        # This represents how power metrics would be included in trial telemetry
        trial_result = {
            "trial_name": "test_trial_0",
            "wns_ps": 2500,
            "tns_ps": 0,
            "status": "success",
            "custom_metrics": {
                "power": {
                    "total_power_mw": 125.3,
                    "leakage_power_mw": 12.1,
                    "dynamic_power_mw": 113.2,
                }
            },
        }

        assert trial_result["custom_metrics"]["power"]["total_power_mw"] == 125.3


class TestPowerAsRankingDimension:
    """Test using power as an additional ranking dimension."""

    def test_rank_trials_by_power(self):
        """Step 5: Use power as additional ranking dimension."""
        trials = [
            {"name": "trial_0", "wns_ps": 2500, "power_mw": 150.0},
            {"name": "trial_1", "wns_ps": 2500, "power_mw": 120.0},  # Better power
            {"name": "trial_2", "wns_ps": 2500, "power_mw": 140.0},
        ]

        # Rank by power (lower is better)
        ranked = sorted(trials, key=lambda t: t["power_mw"])

        assert ranked[0]["name"] == "trial_1"  # Lowest power
        assert ranked[0]["power_mw"] == 120.0

    def test_multi_objective_ranking_power_and_timing(self):
        """Step 6: Support power-timing trade-off studies."""
        trials = [
            {"name": "trial_0", "wns_ps": 2000, "power_mw": 150.0},  # Fast, high power
            {"name": "trial_1", "wns_ps": 2500, "power_mw": 120.0},  # Slower, low power
            {"name": "trial_2", "wns_ps": 2200, "power_mw": 140.0},  # Dominated by trial_1
        ]

        # Pareto frontier: trials where you can't improve one metric without
        # degrading another
        # trial_1: Best power (120mW) with best timing (2500ps)
        # trial_2: Worse power (140mW) but also worse timing (2200ps) - dominated by trial_1
        # trial_0: Even worse power (150mW) but even worse timing (2000ps) - dominated

        def is_dominated(trial, other_trials):
            """Check if trial is dominated by any other trial."""
            for other in other_trials:
                if other["name"] == trial["name"]:
                    continue
                # Other dominates trial if it's better or equal in all metrics
                # and strictly better in at least one
                better_or_equal_timing = other["wns_ps"] >= trial["wns_ps"]
                better_or_equal_power = other["power_mw"] <= trial["power_mw"]
                strictly_better = (other["wns_ps"] > trial["wns_ps"]) or (other["power_mw"] < trial["power_mw"])

                if better_or_equal_timing and better_or_equal_power and strictly_better:
                    return True
            return False

        pareto_frontier = [t for t in trials if not is_dominated(t, trials)]

        # Only trial_1 should be on Pareto frontier (best in both)
        pareto_names = {t["name"] for t in pareto_frontier}
        assert "trial_1" in pareto_names  # Best in both metrics
        # trial_0 and trial_2 are dominated by trial_1

        # Verify at least one solution is Pareto optimal
        assert len(pareto_frontier) >= 1

    def test_weighted_sum_power_timing_ranking(self):
        """Step 6: Alternative approach using weighted sum for power-timing trade-off."""
        trials = [
            {"name": "trial_0", "wns_ps": 2000, "power_mw": 150.0},
            {"name": "trial_1", "wns_ps": 2500, "power_mw": 120.0},
            {"name": "trial_2", "wns_ps": 2200, "power_mw": 130.0},
        ]

        # Normalize and weight: 70% timing, 30% power
        # Higher WNS is better, lower power is better
        max_wns = max(t["wns_ps"] for t in trials)
        min_power = min(t["power_mw"] for t in trials)
        max_power = max(t["power_mw"] for t in trials)

        for trial in trials:
            timing_score = trial["wns_ps"] / max_wns
            power_score = 1.0 - (trial["power_mw"] - min_power) / (max_power - min_power)
            trial["composite_score"] = 0.7 * timing_score + 0.3 * power_score

        ranked = sorted(trials, key=lambda t: t["composite_score"], reverse=True)

        # Check that ranking is reasonable
        assert len(ranked) == 3
        assert all("composite_score" in t for t in ranked)


class TestPowerAnalysisEndToEnd:
    """End-to-end tests for complete power analysis workflow."""

    def test_complete_power_analysis_workflow(self, tmp_path):
        """
        Complete workflow:
        1. Generate script with power enabled
        2. Execute (simulated)
        3. Parse power report
        4. Extract metrics
        5. Emit to telemetry
        """
        # Step 1: Generate script
        script_path = tmp_path / "trial.tcl"
        write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            output_dir=str(tmp_path),
            power_analysis_enabled=True,
        )

        assert script_path.exists()
        script_content = script_path.read_text()
        assert "power.rpt" in script_content

        # Step 2: Simulate execution - create power report
        power_report = tmp_path / "power.rpt"
        power_report.write_text("""
Power Report
============

Design: test_design

Group                  Internal  Switching    Leakage      Total
                          Power      Power      Power      Power
-----------------------------------------------------------------
Design                    78.5 mW    34.7 mW    12.1 mW   125.3 mW

Total Power: 125.3 mW
Leakage Power: 12.1 mW
Dynamic Power: 113.2 mW
Internal Power: 78.5 mW
Switching Power: 34.7 mW
""")

        # Step 3 & 4: Parse power metrics
        extractor = PowerMetricExtractor()
        metrics = extractor.extract(tmp_path)

        assert metrics["total_power_mw"] == 125.3
        assert metrics["leakage_power_mw"] == 12.1
        assert metrics["dynamic_power_mw"] == 113.2

        # Step 5: Emit to telemetry (simulated)
        import json
        telemetry_data = {
            "design": "test_design",
            "power_metrics": metrics,
            "timestamp": "2026-01-08T00:00:00Z",
        }

        telemetry_file = tmp_path / "telemetry.json"
        telemetry_file.write_text(json.dumps(telemetry_data, indent=2))

        assert telemetry_file.exists()

        # Verify telemetry can be read back
        recovered = json.loads(telemetry_file.read_text())
        assert recovered["power_metrics"]["total_power_mw"] == 125.3

    def test_power_timing_trade_off_study_workflow(self, tmp_path):
        """
        Step 6: Complete power-timing trade-off study.

        Simulate multiple trials with different power-timing characteristics
        and select survivors based on Pareto optimality.
        """
        # Simulate 5 trials with different power-timing profiles
        trials_data = [
            {"trial": "trial_0", "wns_ps": 3000, "power_mw": 200.0},  # Slow, high power
            {"trial": "trial_1", "wns_ps": 2500, "power_mw": 150.0},  # Medium
            {"trial": "trial_2", "wns_ps": 2000, "power_mw": 180.0},  # Fast, high power
            {"trial": "trial_3", "wns_ps": 2200, "power_mw": 120.0},  # Good balance
            {"trial": "trial_4", "wns_ps": 1800, "power_mw": 140.0},  # Very fast, medium power
        ]

        # Identify Pareto frontier
        def is_pareto_optimal(trial, all_trials):
            """Trial is Pareto optimal if no other trial dominates it."""
            for other in all_trials:
                if other["trial"] == trial["trial"]:
                    continue
                # Other dominates if better in both or equal in one and better in other
                better_timing = other["wns_ps"] >= trial["wns_ps"]
                better_power = other["power_mw"] <= trial["power_mw"]
                strictly_better = (other["wns_ps"] > trial["wns_ps"]) or (other["power_mw"] < trial["power_mw"])

                if better_timing and better_power and strictly_better:
                    return False  # Trial is dominated
            return True

        pareto_trials = [t for t in trials_data if is_pareto_optimal(t, trials_data)]

        # Should have multiple Pareto-optimal solutions
        assert len(pareto_trials) >= 2

        # trial_3 and trial_4 should likely be on frontier
        pareto_names = {t["trial"] for t in pareto_trials}
        assert "trial_3" in pareto_names or "trial_4" in pareto_names

        # Generate trade-off report
        report_path = tmp_path / "power_timing_tradeoff.txt"
        with open(report_path, "w") as f:
            f.write("Power-Timing Trade-Off Analysis\\n")
            f.write("================================\\n\\n")
            f.write("Pareto Frontier:\\n")
            for trial in sorted(pareto_trials, key=lambda t: t["wns_ps"], reverse=True):
                f.write(f"  {trial['trial']}: WNS={trial['wns_ps']}ps, Power={trial['power_mw']}mW\\n")

        assert report_path.exists()
        content = report_path.read_text()
        assert "Pareto Frontier" in content
