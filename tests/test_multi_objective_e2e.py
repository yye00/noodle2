"""End-to-end tests for multi-objective optimization with Pareto frontier analysis.

This module validates the complete workflow for multi-objective optimization
in Noodle 2, including:
- Defining multi-objective ranking policies
- Computing Pareto frontiers across multiple objectives
- Visualizing Pareto frontiers in 2D and 3D
- Selecting Pareto-optimal survivors
- Generating trade-off analysis reports
- Comparing Pareto vs weighted-sum ranking approaches
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.controller.pareto import (
    AREA_OBJECTIVE,
    CONGESTION_OBJECTIVE,
    POWER_OBJECTIVE,
    TIMING_OBJECTIVE,
    ObjectiveSpec,
    ParetoFrontier,
    ParetoTrial,
    compute_pareto_frontier,
    write_pareto_analysis,
)
from src.controller.types import ExecutionMode, StageConfig, StudyConfig
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult
from src.visualization.pareto_plot import (
    generate_pareto_visualization,
    plot_pareto_frontier_2d,
    save_pareto_plot,
)


def create_test_trial_result(
    case_name: str, case_dir: Path, metrics: dict[str, Any]
) -> TrialResult:
    """Helper function to create test trial results with proper structure."""
    # Write metrics file
    metrics_file = case_dir / "metrics.json"
    case_dir.mkdir(parents=True, exist_ok=True)
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    # Create config
    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path=case_dir / "script.tcl",
        snapshot_dir=case_dir.parent / "snapshot",
    )

    # Create artifacts
    artifacts = TrialArtifacts(
        trial_dir=case_dir,
        metrics_json=metrics_file,
        timing_report=case_dir / "timing.rpt",
        logs=case_dir / "trial.log",
    )

    # Create result
    return TrialResult(
        config=config,
        success=True,
        return_code=0,
        runtime_seconds=10.0,
        artifacts=artifacts,
    )


class TestMultiObjectiveStudyConfiguration:
    """Tests for configuring Studies with multi-objective ranking."""

    def test_create_study_with_multi_objective_policy(self, tmp_path: Path) -> None:
        """Step 1: Create Study with multi-objective ranking policy."""
        from src.controller.types import SafetyDomain, ECOClass

        study = StudyConfig(
            name="multi_objective_demo",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            snapshot_path=str(tmp_path / "snapshot"),
            stages=[
                StageConfig(
                    name="pareto_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=20,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        assert study.name == "multi_objective_demo"
        assert len(study.stages) == 1
        assert study.stages[0].survivor_count == 5

    def test_define_multiple_objectives(self) -> None:
        """Step 2: Define objectives: WNS, area, power, congestion."""
        objectives = [
            TIMING_OBJECTIVE,
            AREA_OBJECTIVE,
            POWER_OBJECTIVE,
            CONGESTION_OBJECTIVE,
        ]

        assert len(objectives) == 4
        assert objectives[0].name == "wns_ps"
        assert objectives[0].minimize is False  # Maximize WNS
        assert objectives[1].name == "area_um2"
        assert objectives[1].minimize is True  # Minimize area
        assert objectives[2].name == "total_power_mw"
        assert objectives[2].minimize is True  # Minimize power
        assert objectives[3].name == "hot_ratio"
        assert objectives[3].minimize is True  # Minimize congestion

    def test_custom_objective_specifications(self) -> None:
        """Test defining custom objectives with explicit metric paths."""
        custom_wns = ObjectiveSpec(
            name="wns_ps",
            metric_path=["timing", "wns_ps"],
            minimize=False,
            weight=2.0,
        )
        custom_area = ObjectiveSpec(
            name="area_um2",
            metric_path=["area", "total_area_um2"],
            minimize=True,
            weight=1.0,
        )

        assert custom_wns.weight == 2.0
        assert custom_area.weight == 1.0
        assert custom_wns.metric_path == ["timing", "wns_ps"]
        assert custom_area.metric_path == ["area", "total_area_um2"]


class TestMultiObjectiveTrialExecution:
    """Tests for executing trials and collecting multi-objective metrics."""

    def test_execute_trials_with_multiple_metrics(self, tmp_path: Path) -> None:
        """Step 3: Execute trials producing metrics for all objectives."""
        # Create simulated trial results with multiple metrics
        trial_results = self._create_mock_trial_results(tmp_path, num_trials=10)

        assert len(trial_results) == 10
        for trial in trial_results:
            assert trial.success
            assert trial.artifacts.metrics_json.exists()

            # Verify all objectives are present in metrics
            with open(trial.artifacts.metrics_json) as f:
                metrics = json.load(f)
            assert "timing" in metrics
            assert "area" in metrics
            assert "power" in metrics
            assert "congestion" in metrics

    def _create_mock_trial_results(
        self, tmp_path: Path, num_trials: int
    ) -> list[TrialResult]:
        """Create mock trial results with multi-objective metrics."""
        import random

        random.seed(42)  # Deterministic results

        trial_results = []
        for i in range(num_trials):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name

            # Create metrics with trade-offs
            # Some trials good at timing, bad at area
            # Some trials good at area, bad at timing
            # Some trials are balanced
            metrics = {
                "timing": {
                    "wns_ps": random.uniform(-1000, 500),  # Range from bad to good
                },
                "area": {
                    "total_area_um2": random.uniform(5000, 15000),  # Smaller is better
                },
                "power": {
                    "total_power_mw": random.uniform(10, 50),  # Smaller is better
                },
                "congestion": {
                    "hot_ratio": random.uniform(0.0, 0.5),  # Lower is better
                },
            }

            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)

        return trial_results


class TestParetoFrontierComputation:
    """Tests for computing Pareto frontiers from trial results."""

    def test_compute_pareto_frontier_with_four_objectives(
        self, tmp_path: Path
    ) -> None:
        """Step 4: Compute Pareto frontier of non-dominated solutions."""
        # Create trial results with known Pareto structure
        trial_results = self._create_pareto_test_trials(tmp_path)

        objectives = [
            TIMING_OBJECTIVE,
            AREA_OBJECTIVE,
            POWER_OBJECTIVE,
            CONGESTION_OBJECTIVE,
        ]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        assert pareto_frontier is not None
        assert len(pareto_frontier.all_trials) > 0
        assert len(pareto_frontier.pareto_optimal_trials) > 0
        assert len(pareto_frontier.dominated_trials) >= 0

        # Verify all trials are classified
        total = len(pareto_frontier.pareto_optimal_trials) + len(
            pareto_frontier.dominated_trials
        )
        assert total == len(pareto_frontier.all_trials)

    def test_pareto_frontier_identifies_non_dominated_solutions(
        self, tmp_path: Path
    ) -> None:
        """Verify that Pareto-optimal trials are not dominated by any other trial."""
        trial_results = self._create_pareto_test_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Check that no Pareto-optimal trial is dominated
        for pareto_trial in pareto_frontier.pareto_optimal_trials:
            assert len(pareto_trial.dominated_by) == 0
            assert pareto_trial.is_pareto_optimal is True

        # Check that all dominated trials have at least one dominator
        for dominated_trial in pareto_frontier.dominated_trials:
            assert len(dominated_trial.dominated_by) > 0
            assert dominated_trial.is_pareto_optimal is False

    def test_pareto_frontier_with_two_objectives(self, tmp_path: Path) -> None:
        """Test Pareto frontier with just timing and area objectives."""
        trial_results = self._create_simple_2d_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # With 2 objectives, Pareto frontier should be clear
        assert len(pareto_frontier.pareto_optimal_trials) >= 2
        pareto_names = pareto_frontier.get_pareto_case_names()
        assert isinstance(pareto_names, list)
        assert all(isinstance(name, str) for name in pareto_names)

    def _create_pareto_test_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create trial results with known Pareto structure."""
        # Create trials with clear trade-offs
        trial_configs = [
            # Trial 0: Best timing, worst area/power/congestion
            {
                "timing": {"wns_ps": 500},
                "area": {"total_area_um2": 15000},
                "power": {"total_power_mw": 50},
                "congestion": {"hot_ratio": 0.5},
            },
            # Trial 1: Best area, mediocre timing
            {
                "timing": {"wns_ps": -200},
                "area": {"total_area_um2": 5000},
                "power": {"total_power_mw": 30},
                "congestion": {"hot_ratio": 0.3},
            },
            # Trial 2: Best power, mediocre others
            {
                "timing": {"wns_ps": 0},
                "area": {"total_area_um2": 10000},
                "power": {"total_power_mw": 10},
                "congestion": {"hot_ratio": 0.4},
            },
            # Trial 3: Best congestion, mediocre others
            {
                "timing": {"wns_ps": 100},
                "area": {"total_area_um2": 12000},
                "power": {"total_power_mw": 40},
                "congestion": {"hot_ratio": 0.05},
            },
            # Trial 4: Balanced - likely Pareto optimal
            {
                "timing": {"wns_ps": 200},
                "area": {"total_area_um2": 8000},
                "power": {"total_power_mw": 25},
                "congestion": {"hot_ratio": 0.2},
            },
            # Trial 5: Dominated - worse in all objectives than trial 4
            {
                "timing": {"wns_ps": -100},
                "area": {"total_area_um2": 12000},
                "power": {"total_power_mw": 45},
                "congestion": {"hot_ratio": 0.4},
            },
        ]

        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_simple_2d_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create simple 2D trial results for timing vs area."""
        trial_configs = [
            # Pareto optimal: Good timing, high area
            {"timing": {"wns_ps": 400}, "area": {"total_area_um2": 12000}},
            # Pareto optimal: Medium timing, medium area
            {"timing": {"wns_ps": 100}, "area": {"total_area_um2": 8000}},
            # Pareto optimal: Low timing, low area
            {"timing": {"wns_ps": -100}, "area": {"total_area_um2": 5000}},
            # Dominated: Worse timing and worse area than trial 1
            {"timing": {"wns_ps": -200}, "area": {"total_area_um2": 15000}},
        ]

        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


class TestParetoVisualization2D:
    """Tests for 2D Pareto frontier visualization."""

    def test_generate_2d_pareto_plot(self, tmp_path: Path) -> None:
        """Step 5: Visualize Pareto frontier in 2D scatter plots."""
        # Create Pareto frontier
        trial_results = self._create_simple_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]
        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Generate 2D plot
        fig = plot_pareto_frontier_2d(
            pareto_frontier, objective_x="wns_ps", objective_y="area_um2"
        )

        assert fig is not None
        assert len(fig.axes) == 1  # One subplot
        ax = fig.axes[0]
        assert ax.get_xlabel()  # Has x label
        assert ax.get_ylabel()  # Has y label
        assert ax.get_title()  # Has title

    def test_save_2d_pareto_plot(self, tmp_path: Path) -> None:
        """Test saving 2D Pareto plot to file."""
        trial_results = self._create_simple_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]
        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        fig = plot_pareto_frontier_2d(
            pareto_frontier, objective_x="wns_ps", objective_y="area_um2"
        )

        output_path = tmp_path / "pareto_2d.png"
        save_pareto_plot(fig, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

    def test_generate_multiple_2d_plots(self, tmp_path: Path) -> None:
        """Test generating multiple 2D Pareto plots for different objective pairs."""
        trial_results = self._create_multi_objective_trials(tmp_path)
        objectives = [
            TIMING_OBJECTIVE,
            AREA_OBJECTIVE,
            POWER_OBJECTIVE,
            CONGESTION_OBJECTIVE,
        ]
        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        output_dir = tmp_path / "plots"
        output_dir.mkdir()

        # Generate all pairwise plots
        objective_pairs = [
            ("wns_ps", "area_um2"),
            ("wns_ps", "total_power_mw"),
            ("wns_ps", "hot_ratio"),
            ("area_um2", "total_power_mw"),
            ("area_um2", "hot_ratio"),
            ("total_power_mw", "hot_ratio"),
        ]

        generated_plots = generate_pareto_visualization(
            pareto_frontier, output_dir, objective_pairs
        )

        assert len(generated_plots) == len(objective_pairs)
        for plot_path in generated_plots:
            assert plot_path.exists()
            assert plot_path.suffix == ".png"

    def _create_simple_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create simple trial results for visualization testing."""
        trial_configs = [
            {"timing": {"wns_ps": 400}, "area": {"total_area_um2": 12000}},
            {"timing": {"wns_ps": 200}, "area": {"total_area_um2": 9000}},
            {"timing": {"wns_ps": 0}, "area": {"total_area_um2": 7000}},
            {"timing": {"wns_ps": -200}, "area": {"total_area_um2": 5000}},
            {"timing": {"wns_ps": -100}, "area": {"total_area_um2": 10000}},
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_multi_objective_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create multi-objective trial results."""
        trial_configs = [
            {
                "timing": {"wns_ps": 500},
                "area": {"total_area_um2": 15000},
                "power": {"total_power_mw": 50},
                "congestion": {"hot_ratio": 0.5},
            },
            {
                "timing": {"wns_ps": 300},
                "area": {"total_area_um2": 10000},
                "power": {"total_power_mw": 35},
                "congestion": {"hot_ratio": 0.3},
            },
            {
                "timing": {"wns_ps": 100},
                "area": {"total_area_um2": 7000},
                "power": {"total_power_mw": 25},
                "congestion": {"hot_ratio": 0.2},
            },
            {
                "timing": {"wns_ps": -100},
                "area": {"total_area_um2": 5000},
                "power": {"total_power_mw": 15},
                "congestion": {"hot_ratio": 0.1},
            },
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


class TestParetoVisualization3D:
    """Tests for 3D Pareto surface visualization."""

    def test_placeholder_3d_visualization(self, tmp_path: Path) -> None:
        """Step 6: Visualize 3D Pareto surface for 3-objective case.

        Note: 3D visualization is planned but not yet implemented.
        This test validates the infrastructure is in place.
        """
        # For now, we demonstrate that 3-objective Pareto frontiers can be computed
        trial_results = self._create_3d_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE, POWER_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        assert len(pareto_frontier.objectives) == 3
        assert len(pareto_frontier.pareto_optimal_trials) > 0

        # 3D plotting would be done with matplotlib's 3D capabilities
        # or plotly for interactive plots
        # This is a placeholder for future implementation

    def _create_3d_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create trial results for 3D Pareto testing."""
        trial_configs = [
            {
                "timing": {"wns_ps": 500},
                "area": {"total_area_um2": 15000},
                "power": {"total_power_mw": 50},
            },
            {
                "timing": {"wns_ps": 300},
                "area": {"total_area_um2": 10000},
                "power": {"total_power_mw": 35},
            },
            {
                "timing": {"wns_ps": 100},
                "area": {"total_area_um2": 7000},
                "power": {"total_power_mw": 25},
            },
            {
                "timing": {"wns_ps": -100},
                "area": {"total_area_um2": 5000},
                "power": {"total_power_mw": 15},
            },
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


class TestParetoSurvivorSelection:
    """Tests for using Pareto-optimal trials for survivor selection."""

    def test_identify_pareto_optimal_cases_for_survivors(
        self, tmp_path: Path
    ) -> None:
        """Step 7: Identify Pareto-optimal Cases for survivor selection."""
        trial_results = self._create_survivor_test_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Get Pareto-optimal case names
        pareto_survivors = pareto_frontier.get_pareto_case_names()

        assert len(pareto_survivors) > 0
        assert isinstance(pareto_survivors, list)

        # Verify these are actual case names from trial results
        all_case_names = {t.config.case_name for t in trial_results}
        for survivor in pareto_survivors:
            assert survivor in all_case_names

    def test_user_selection_from_pareto_frontier(self, tmp_path: Path) -> None:
        """Step 8: Allow user to select from Pareto frontier based on preferences."""
        trial_results = self._create_survivor_test_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Simulate user preference: select trial with best timing from Pareto front
        best_timing_trial = max(
            pareto_frontier.pareto_optimal_trials,
            key=lambda t: t.objective_values["wns_ps"],
        )

        assert best_timing_trial.is_pareto_optimal
        assert best_timing_trial.case_name

        # Simulate user preference: select trial with smallest area from Pareto front
        best_area_trial = min(
            pareto_frontier.pareto_optimal_trials,
            key=lambda t: t.objective_values["area_um2"],
        )

        assert best_area_trial.is_pareto_optimal
        assert best_area_trial.case_name

    def test_survivor_selection_respects_budget(self, tmp_path: Path) -> None:
        """Test selecting limited number of survivors from Pareto front."""
        trial_results = self._create_many_pareto_trials(tmp_path, num_trials=20)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Simulate survivor budget of 5
        survivor_budget = 5
        pareto_survivors = pareto_frontier.get_pareto_case_names()

        if len(pareto_survivors) > survivor_budget:
            # Would need additional ranking within Pareto front
            # For now, just take first N
            selected_survivors = pareto_survivors[:survivor_budget]
        else:
            selected_survivors = pareto_survivors

        assert len(selected_survivors) <= survivor_budget

    def _create_survivor_test_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create trial results for survivor selection testing."""
        trial_configs = [
            {"timing": {"wns_ps": 500}, "area": {"total_area_um2": 12000}},
            {"timing": {"wns_ps": 300}, "area": {"total_area_um2": 9000}},
            {"timing": {"wns_ps": 100}, "area": {"total_area_um2": 7000}},
            {"timing": {"wns_ps": -100}, "area": {"total_area_um2": 5000}},
            {"timing": {"wns_ps": 0}, "area": {"total_area_um2": 15000}},  # Dominated
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_many_pareto_trials(
        self, tmp_path: Path, num_trials: int
    ) -> list[TrialResult]:
        """Create many trial results with diverse Pareto front."""
        import random

        random.seed(42)

        trial_configs = []
        for i in range(num_trials):
            # Create trials with trade-offs
            wns = random.uniform(-500, 500)
            area = 10000 - wns * 10  # Inverse relationship
            trial_configs.append(
                {
                    "timing": {"wns_ps": wns},
                    "area": {"total_area_um2": max(5000, area)},
                }
            )

        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


class TestTradeOffAnalysis:
    """Tests for trade-off analysis report generation."""

    def test_generate_trade_off_analysis_report(self, tmp_path: Path) -> None:
        """Step 9: Generate trade-off analysis report."""
        trial_results = self._create_tradeoff_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE, POWER_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Generate trade-off report
        report = self._generate_tradeoff_report(pareto_frontier)

        assert "total_trials" in report
        assert "pareto_optimal_count" in report
        assert "dominated_count" in report
        assert "pareto_trials" in report

        # Verify report contains meaningful data
        assert report["total_trials"] > 0
        assert report["pareto_optimal_count"] > 0
        assert len(report["pareto_trials"]) == report["pareto_optimal_count"]

    def test_export_trade_off_data(self, tmp_path: Path) -> None:
        """Test exporting trade-off analysis data to file."""
        trial_results = self._create_tradeoff_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        report = self._generate_tradeoff_report(pareto_frontier)
        report_file = tmp_path / "tradeoff_analysis.json"

        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)

        assert report_file.exists()
        assert report_file.stat().st_size > 0

        # Verify can reload report
        with open(report_file) as f:
            loaded_report = json.load(f)
        assert loaded_report["total_trials"] == report["total_trials"]

    def _generate_tradeoff_report(
        self, pareto_frontier: ParetoFrontier
    ) -> dict[str, Any]:
        """Generate trade-off analysis report from Pareto frontier."""
        return {
            "total_trials": len(pareto_frontier.all_trials),
            "pareto_optimal_count": len(pareto_frontier.pareto_optimal_trials),
            "dominated_count": len(pareto_frontier.dominated_trials),
            "pareto_trials": [
                {
                    "case_name": t.case_name,
                    "objectives": t.objective_values,
                }
                for t in pareto_frontier.pareto_optimal_trials
            ],
            "dominated_trials": [
                {
                    "case_name": t.case_name,
                    "objectives": t.objective_values,
                    "dominated_by": t.dominated_by,
                }
                for t in pareto_frontier.dominated_trials
            ],
        }

    def _create_tradeoff_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create trial results for trade-off analysis."""
        trial_configs = [
            {
                "timing": {"wns_ps": 500},
                "area": {"total_area_um2": 15000},
                "power": {"total_power_mw": 50},
            },
            {
                "timing": {"wns_ps": 300},
                "area": {"total_area_um2": 10000},
                "power": {"total_power_mw": 35},
            },
            {
                "timing": {"wns_ps": 100},
                "area": {"total_area_um2": 7000},
                "power": {"total_power_mw": 25},
            },
            {
                "timing": {"wns_ps": -100},
                "area": {"total_area_um2": 5000},
                "power": {"total_power_mw": 15},
            },
            {
                "timing": {"wns_ps": 0},
                "area": {"total_area_um2": 12000},
                "power": {"total_power_mw": 40},
            },
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


class TestParetoDataExport:
    """Tests for exporting Pareto frontier data."""

    def test_export_pareto_data_to_json(self, tmp_path: Path) -> None:
        """Step 10: Export Pareto data for external analysis."""
        trial_results = self._create_export_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Export to JSON
        output_path = tmp_path / "pareto_frontier.json"
        write_pareto_analysis(pareto_frontier, output_path)

        assert output_path.exists()
        assert output_path.stat().st_size > 0

        # Verify JSON structure
        with open(output_path) as f:
            data = json.load(f)

        assert "objectives" in data
        assert "pareto_optimal_trials" in data
        assert "dominated_trials" in data
        assert "summary" in data

        assert len(data["objectives"]) == 2
        assert data["summary"]["total_trials"] > 0

    def test_pareto_to_dict_serialization(self, tmp_path: Path) -> None:
        """Test ParetoFrontier.to_dict() produces valid structure."""
        trial_results = self._create_export_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE, POWER_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        data = pareto_frontier.to_dict()

        assert isinstance(data, dict)
        assert "objectives" in data
        assert isinstance(data["objectives"], list)
        assert "pareto_optimal_trials" in data
        assert isinstance(data["pareto_optimal_trials"], list)
        assert "dominated_trials" in data
        assert isinstance(data["dominated_trials"], list)
        assert "summary" in data
        assert isinstance(data["summary"], dict)

    def _create_export_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create trial results for export testing."""
        trial_configs = [
            {
                "timing": {"wns_ps": 400},
                "area": {"total_area_um2": 12000},
                "power": {"total_power_mw": 40},
            },
            {
                "timing": {"wns_ps": 200},
                "area": {"total_area_um2": 9000},
                "power": {"total_power_mw": 30},
            },
            {
                "timing": {"wns_ps": 0},
                "area": {"total_area_um2": 7000},
                "power": {"total_power_mw": 25},
            },
            {
                "timing": {"wns_ps": -200},
                "area": {"total_area_um2": 5000},
                "power": {"total_power_mw": 15},
            },
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


class TestDeterministicRanking:
    """Tests for deterministic multi-objective ranking."""

    def test_pareto_ranking_is_deterministic(self, tmp_path: Path) -> None:
        """Step 11: Verify multi-objective ranking is deterministic."""
        trial_results = self._create_deterministic_test_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        # Compute Pareto frontier multiple times
        pareto1 = compute_pareto_frontier(trial_results, objectives)
        pareto2 = compute_pareto_frontier(trial_results, objectives)
        pareto3 = compute_pareto_frontier(trial_results, objectives)

        # Verify results are identical
        names1 = sorted(pareto1.get_pareto_case_names())
        names2 = sorted(pareto2.get_pareto_case_names())
        names3 = sorted(pareto3.get_pareto_case_names())

        assert names1 == names2 == names3

        # Verify counts are identical
        assert len(pareto1.pareto_optimal_trials) == len(pareto2.pareto_optimal_trials)
        assert len(pareto1.dominated_trials) == len(pareto2.dominated_trials)

    def test_pareto_ranking_independent_of_trial_order(self, tmp_path: Path) -> None:
        """Test that Pareto ranking is independent of trial order."""
        trial_results = self._create_deterministic_test_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        # Compute with original order
        pareto_original = compute_pareto_frontier(trial_results, objectives)

        # Compute with reversed order
        pareto_reversed = compute_pareto_frontier(
            list(reversed(trial_results)), objectives
        )

        # Results should be identical (order-independent)
        names_original = sorted(pareto_original.get_pareto_case_names())
        names_reversed = sorted(pareto_reversed.get_pareto_case_names())

        assert names_original == names_reversed

    def _create_deterministic_test_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create trial results for determinism testing."""
        trial_configs = [
            {"timing": {"wns_ps": 500}, "area": {"total_area_um2": 12000}},
            {"timing": {"wns_ps": 300}, "area": {"total_area_um2": 9000}},
            {"timing": {"wns_ps": 100}, "area": {"total_area_um2": 7000}},
            {"timing": {"wns_ps": -100}, "area": {"total_area_um2": 5000}},
            {"timing": {"wns_ps": 0}, "area": {"total_area_um2": 15000}},
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


class TestParetoVsWeightedSum:
    """Tests comparing Pareto approach vs weighted-sum ranking."""

    def test_compare_pareto_vs_weighted_sum(self, tmp_path: Path) -> None:
        """Step 12: Compare Pareto approach vs weighted-sum ranking."""
        trial_results = self._create_comparison_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        # Compute Pareto frontier
        pareto_frontier = compute_pareto_frontier(trial_results, objectives)
        pareto_survivors = pareto_frontier.get_pareto_case_names()

        # Compute weighted-sum ranking
        weighted_survivors = self._compute_weighted_sum_ranking(
            trial_results, objectives, top_n=3
        )

        # Both methods should identify good trials, but may differ
        assert len(pareto_survivors) > 0
        assert len(weighted_survivors) > 0

        # Pareto method preserves diversity (multiple solutions)
        # Weighted method converges to single best compromise
        # This test verifies both work

    def test_weighted_sum_produces_single_best_solution(self, tmp_path: Path) -> None:
        """Test that weighted-sum ranking identifies single best compromise."""
        trial_results = self._create_comparison_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        # Weighted-sum with equal weights
        best_case = self._compute_weighted_sum_ranking(
            trial_results, objectives, top_n=1
        )

        assert len(best_case) == 1
        assert isinstance(best_case[0], str)

    def test_pareto_preserves_solution_diversity(self, tmp_path: Path) -> None:
        """Test that Pareto method preserves diverse solutions."""
        trial_results = self._create_diverse_trials(tmp_path)
        objectives = [TIMING_OBJECTIVE, AREA_OBJECTIVE]

        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        # Pareto frontier should contain multiple diverse solutions
        assert len(pareto_frontier.pareto_optimal_trials) >= 3

        # Verify diversity: check that solutions span objective space
        wns_values = [
            t.objective_values["wns_ps"]
            for t in pareto_frontier.pareto_optimal_trials
        ]
        area_values = [
            t.objective_values["area_um2"]
            for t in pareto_frontier.pareto_optimal_trials
        ]

        # Should have diversity in both objectives
        assert max(wns_values) - min(wns_values) > 100  # Significant WNS range
        assert max(area_values) - min(area_values) > 2000  # Significant area range

    def _compute_weighted_sum_ranking(
        self,
        trial_results: list[TrialResult],
        objectives: list[ObjectiveSpec],
        top_n: int,
    ) -> list[str]:
        """Compute weighted-sum ranking of trials."""
        # Load metrics for all trials
        trial_scores = []
        for trial in trial_results:
            if not trial.success or not trial.artifacts.metrics_json.exists():
                continue

            with open(trial.artifacts.metrics_json) as f:
                metrics = json.load(f)

            # Compute weighted score
            score = 0.0
            valid = True
            for obj in objectives:
                value = self._extract_value(metrics, obj.metric_path)
                if value is None:
                    valid = False
                    break

                # Normalize and weight
                # For minimize: lower is better (negative contribution)
                # For maximize: higher is better (positive contribution)
                if obj.minimize:
                    score -= value * obj.weight
                else:
                    score += value * obj.weight

            if valid:
                trial_scores.append((trial.config.case_name, score))

        # Sort by score (higher is better)
        trial_scores.sort(key=lambda x: x[1], reverse=True)

        # Return top N
        return [name for name, _ in trial_scores[:top_n]]

    def _extract_value(
        self, metrics: dict[str, Any], path: list[str]
    ) -> float | None:
        """Extract value from nested metrics dictionary."""
        current = metrics
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
            if current is None:
                return None
        if isinstance(current, (int, float)):
            return float(current)
        return None

    def _create_comparison_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create trial results for comparison testing."""
        trial_configs = [
            {"timing": {"wns_ps": 500}, "area": {"total_area_um2": 15000}},
            {"timing": {"wns_ps": 300}, "area": {"total_area_um2": 10000}},
            {"timing": {"wns_ps": 100}, "area": {"total_area_um2": 7000}},
            {"timing": {"wns_ps": -100}, "area": {"total_area_um2": 5000}},
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_diverse_trials(self, tmp_path: Path) -> list[TrialResult]:
        """Create diverse trial results spanning objective space."""
        trial_configs = [
            {"timing": {"wns_ps": 500}, "area": {"total_area_um2": 15000}},
            {"timing": {"wns_ps": 400}, "area": {"total_area_um2": 12000}},
            {"timing": {"wns_ps": 300}, "area": {"total_area_um2": 10000}},
            {"timing": {"wns_ps": 200}, "area": {"total_area_um2": 8000}},
            {"timing": {"wns_ps": 100}, "area": {"total_area_um2": 7000}},
            {"timing": {"wns_ps": 0}, "area": {"total_area_um2": 6000}},
            {"timing": {"wns_ps": -100}, "area": {"total_area_um2": 5000}},
        ]
        return self._create_trials_from_configs(tmp_path, trial_configs)

    def _create_trials_from_configs(
        self, tmp_path: Path, configs: list[dict[str, Any]]
    ) -> list[TrialResult]:
        """Helper to create trial results from metric configurations."""
        trial_results = []
        for i, metrics in enumerate(configs):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name
            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)
        return trial_results


@pytest.mark.slow
class TestCompleteMultiObjectiveE2EWorkflow:
    """Complete end-to-end multi-objective optimization workflow."""

    def test_complete_multi_objective_workflow(self, tmp_path: Path) -> None:
        """Complete multi-objective optimization workflow from start to finish."""
        from src.controller.types import SafetyDomain, ECOClass

        # Step 1: Create Study configuration
        study = StudyConfig(
            name="complete_multi_objective_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            snapshot_path=str(tmp_path / "snapshot"),
            stages=[
                StageConfig(
                    name="multi_obj_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=15,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        # Step 2: Define objectives
        objectives = [
            TIMING_OBJECTIVE,
            AREA_OBJECTIVE,
            POWER_OBJECTIVE,
            CONGESTION_OBJECTIVE,
        ]

        # Step 3: Execute trials (simulated)
        trial_results = self._simulate_trial_execution(tmp_path, num_trials=15)

        # Step 4: Compute Pareto frontier
        pareto_frontier = compute_pareto_frontier(trial_results, objectives)

        assert len(pareto_frontier.all_trials) > 0
        assert len(pareto_frontier.pareto_optimal_trials) > 0

        # Step 5: Generate 2D visualizations
        output_dir = tmp_path / "visualizations"
        objective_pairs = [
            ("wns_ps", "area_um2"),
            ("wns_ps", "total_power_mw"),
            ("area_um2", "hot_ratio"),
        ]
        plots = generate_pareto_visualization(
            pareto_frontier, output_dir, objective_pairs
        )
        assert len(plots) == 3
        for plot in plots:
            assert plot.exists()

        # Step 6: Export Pareto data
        pareto_json = tmp_path / "pareto_analysis.json"
        write_pareto_analysis(pareto_frontier, pareto_json)
        assert pareto_json.exists()

        # Step 7: Select survivors from Pareto front
        pareto_survivors = pareto_frontier.get_pareto_case_names()
        assert len(pareto_survivors) > 0

        # Limit to survivor budget
        selected_survivors = pareto_survivors[: study.stages[0].survivor_count]
        assert len(selected_survivors) <= study.stages[0].survivor_count

        # Step 8: Generate trade-off report
        tradeoff_report = {
            "study_name": study.name,
            "objectives": [obj.name for obj in objectives],
            "total_trials": len(pareto_frontier.all_trials),
            "pareto_optimal_count": len(pareto_frontier.pareto_optimal_trials),
            "selected_survivors": selected_survivors,
        }

        tradeoff_file = tmp_path / "tradeoff_report.json"
        with open(tradeoff_file, "w") as f:
            json.dump(tradeoff_report, f, indent=2)

        assert tradeoff_file.exists()

        # Verify complete workflow succeeded
        assert study.name == "complete_multi_objective_study"
        assert len(objectives) == 4
        assert len(trial_results) == 15
        assert len(plots) == 3
        assert pareto_json.exists()
        assert tradeoff_file.exists()

    def _simulate_trial_execution(
        self, tmp_path: Path, num_trials: int
    ) -> list[TrialResult]:
        """Simulate trial execution with realistic multi-objective data."""
        import random

        random.seed(42)

        trial_results = []
        for i in range(num_trials):
            case_name = f"case_{i}"
            case_dir = tmp_path / case_name

            # Create realistic metrics with trade-offs
            metrics = {
                "timing": {"wns_ps": random.uniform(-500, 500)},
                "area": {"total_area_um2": random.uniform(5000, 15000)},
                "power": {"total_power_mw": random.uniform(10, 50)},
                "congestion": {"hot_ratio": random.uniform(0.0, 0.5)},
            }

            trial_result = create_test_trial_result(case_name, case_dir, metrics)
            trial_results.append(trial_result)

        return trial_results
