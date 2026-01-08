"""Tests for Pareto frontier computation."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.pareto import (
    AREA_OBJECTIVE,
    CONGESTION_OBJECTIVE,
    DRV_OBJECTIVE,
    POWER_OBJECTIVE,
    TIMING_OBJECTIVE,
    ObjectiveSpec,
    ParetoFrontier,
    ParetoTrial,
    compute_pareto_frontier,
    extract_objective_value,
    write_pareto_analysis,
)
from src.trial_runner.trial import (
    TrialArtifacts,
    TrialConfig,
    TrialResult,
)


@pytest.fixture
def temp_dir():
    """Create temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def create_test_trial(
    case_name: str,
    wns_ps: int,
    hot_ratio: float | None = None,
    area_um2: float | None = None,
    power_mw: float | None = None,
    drv_count: int | None = None,
    temp_dir: Path | None = None,
) -> TrialResult:
    """Create a test trial with metrics."""
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp())

    # Create metrics file
    metrics = {"timing": {"wns_ps": wns_ps}}
    if hot_ratio is not None:
        metrics["congestion"] = {"hot_ratio": hot_ratio}
    if area_um2 is not None:
        metrics["area"] = {"total_area_um2": area_um2}
    if power_mw is not None:
        metrics["power"] = {"total_power_mw": power_mw}
    if drv_count is not None:
        metrics["drv"] = {"total_violations": drv_count}

    metrics_file = temp_dir / f"{case_name}_metrics.json"
    with open(metrics_file, "w") as f:
        json.dump(metrics, f)

    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path=temp_dir / "script.tcl",
        snapshot_dir=temp_dir / "snapshot",
    )

    artifacts = TrialArtifacts(
        trial_dir=temp_dir / "artifacts",
        metrics_json=metrics_file,
    )

    return TrialResult(
        config=config,
        success=True,
        return_code=0,
        runtime_seconds=10.0,
        artifacts=artifacts,
    )


class TestObjectiveSpec:
    """Tests for ObjectiveSpec."""

    def test_create_objective_spec(self):
        """Test creating an objective specification."""
        obj = ObjectiveSpec(
            name="wns_ps", metric_path=["timing", "wns_ps"], minimize=False
        )
        assert obj.name == "wns_ps"
        assert obj.metric_path == ["timing", "wns_ps"]
        assert obj.minimize is False
        assert obj.weight == 1.0

    def test_objective_spec_with_weight(self):
        """Test objective spec with custom weight."""
        obj = ObjectiveSpec(
            name="wns_ps",
            metric_path=["timing", "wns_ps"],
            minimize=False,
            weight=2.0,
        )
        assert obj.weight == 2.0

    def test_objective_spec_validation(self):
        """Test objective spec validation."""
        # Empty name
        with pytest.raises(ValueError, match="name cannot be empty"):
            ObjectiveSpec(name="", metric_path=["timing", "wns_ps"], minimize=False)

        # Empty metric path
        with pytest.raises(ValueError, match="Metric path cannot be empty"):
            ObjectiveSpec(name="wns_ps", metric_path=[], minimize=False)

        # Negative weight
        with pytest.raises(ValueError, match="Weight must be positive"):
            ObjectiveSpec(
                name="wns_ps",
                metric_path=["timing", "wns_ps"],
                minimize=False,
                weight=-1.0,
            )

    def test_predefined_objectives(self):
        """Test predefined objective specifications."""
        assert TIMING_OBJECTIVE.name == "wns_ps"
        assert TIMING_OBJECTIVE.minimize is False

        assert CONGESTION_OBJECTIVE.name == "hot_ratio"
        assert CONGESTION_OBJECTIVE.minimize is True

        assert AREA_OBJECTIVE.name == "area_um2"
        assert AREA_OBJECTIVE.minimize is True

        assert POWER_OBJECTIVE.name == "total_power_mw"
        assert POWER_OBJECTIVE.minimize is True

        assert DRV_OBJECTIVE.name == "total_violations"
        assert DRV_OBJECTIVE.minimize is True


class TestExtractObjectiveValue:
    """Tests for extract_objective_value."""

    def test_extract_simple_path(self):
        """Test extracting value from simple path."""
        metrics = {"timing": {"wns_ps": -500}}
        value = extract_objective_value(metrics, ["timing", "wns_ps"])
        assert value == -500.0

    def test_extract_nested_path(self):
        """Test extracting value from deeply nested path."""
        metrics = {"level1": {"level2": {"level3": {"value": 42}}}}
        value = extract_objective_value(metrics, ["level1", "level2", "level3", "value"])
        assert value == 42.0

    def test_extract_missing_key(self):
        """Test extracting value with missing key."""
        metrics = {"timing": {"wns_ps": -500}}
        value = extract_objective_value(metrics, ["timing", "tns_ps"])
        assert value is None

    def test_extract_missing_nested_key(self):
        """Test extracting value with missing nested key."""
        metrics = {"timing": {"wns_ps": -500}}
        value = extract_objective_value(metrics, ["congestion", "hot_ratio"])
        assert value is None

    def test_extract_non_numeric_value(self):
        """Test extracting non-numeric value returns None."""
        metrics = {"timing": {"wns_ps": "not_a_number"}}
        value = extract_objective_value(metrics, ["timing", "wns_ps"])
        assert value is None


class TestParetoTrial:
    """Tests for ParetoTrial."""

    def test_pareto_trial_creation(self, temp_dir):
        """Test creating a ParetoTrial."""
        trial_result = create_test_trial("case1", wns_ps=-500, temp_dir=temp_dir)
        pareto_trial = ParetoTrial(
            case_name="case1",
            trial_result=trial_result,
            objective_values={"wns_ps": -500.0},
        )
        assert pareto_trial.case_name == "case1"
        assert pareto_trial.objective_values == {"wns_ps": -500.0}
        assert pareto_trial.is_pareto_optimal is False
        assert pareto_trial.dominated_by == []

    def test_dominance_single_objective_maximize(self, temp_dir):
        """Test dominance with single objective (maximize WNS)."""
        trial1 = create_test_trial("case1", wns_ps=-500, temp_dir=temp_dir)
        trial2 = create_test_trial("case2", wns_ps=-1000, temp_dir=temp_dir)

        pareto1 = ParetoTrial(
            case_name="case1",
            trial_result=trial1,
            objective_values={"wns_ps": -500.0},
        )
        pareto2 = ParetoTrial(
            case_name="case2",
            trial_result=trial2,
            objective_values={"wns_ps": -1000.0},
        )

        objectives = [TIMING_OBJECTIVE]

        # case1 has better WNS (-500 > -1000), so it dominates case2
        assert pareto1.dominates(pareto2, objectives) is True
        assert pareto2.dominates(pareto1, objectives) is False

    def test_dominance_single_objective_minimize(self, temp_dir):
        """Test dominance with single objective (minimize congestion)."""
        trial1 = create_test_trial("case1", wns_ps=-500, hot_ratio=0.3, temp_dir=temp_dir)
        trial2 = create_test_trial("case2", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir)

        pareto1 = ParetoTrial(
            case_name="case1",
            trial_result=trial1,
            objective_values={"hot_ratio": 0.3},
        )
        pareto2 = ParetoTrial(
            case_name="case2",
            trial_result=trial2,
            objective_values={"hot_ratio": 0.7},
        )

        objectives = [CONGESTION_OBJECTIVE]

        # case1 has lower congestion (0.3 < 0.7), so it dominates case2
        assert pareto1.dominates(pareto2, objectives) is True
        assert pareto2.dominates(pareto1, objectives) is False

    def test_dominance_multi_objective_clear_winner(self, temp_dir):
        """Test dominance with multiple objectives and clear winner."""
        trial1 = create_test_trial("case1", wns_ps=-500, hot_ratio=0.3, temp_dir=temp_dir)
        trial2 = create_test_trial("case2", wns_ps=-1000, hot_ratio=0.7, temp_dir=temp_dir)

        pareto1 = ParetoTrial(
            case_name="case1",
            trial_result=trial1,
            objective_values={"wns_ps": -500.0, "hot_ratio": 0.3},
        )
        pareto2 = ParetoTrial(
            case_name="case2",
            trial_result=trial2,
            objective_values={"wns_ps": -1000.0, "hot_ratio": 0.7},
        )

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]

        # case1 is better in both objectives, so it dominates case2
        assert pareto1.dominates(pareto2, objectives) is True
        assert pareto2.dominates(pareto1, objectives) is False

    def test_dominance_multi_objective_pareto_optimal(self, temp_dir):
        """Test dominance with trade-offs (both Pareto-optimal)."""
        # case1: better timing, worse congestion
        trial1 = create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir)
        # case2: worse timing, better congestion
        trial2 = create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir)

        pareto1 = ParetoTrial(
            case_name="case1",
            trial_result=trial1,
            objective_values={"wns_ps": -500.0, "hot_ratio": 0.7},
        )
        pareto2 = ParetoTrial(
            case_name="case2",
            trial_result=trial2,
            objective_values={"wns_ps": -1000.0, "hot_ratio": 0.3},
        )

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]

        # Neither dominates the other (trade-off)
        assert pareto1.dominates(pareto2, objectives) is False
        assert pareto2.dominates(pareto1, objectives) is False

    def test_dominance_with_missing_objective(self, temp_dir):
        """Test dominance with missing objective value."""
        trial1 = create_test_trial("case1", wns_ps=-500, temp_dir=temp_dir)
        trial2 = create_test_trial("case2", wns_ps=-1000, temp_dir=temp_dir)

        pareto1 = ParetoTrial(
            case_name="case1",
            trial_result=trial1,
            objective_values={"wns_ps": -500.0},  # Missing hot_ratio
        )
        pareto2 = ParetoTrial(
            case_name="case2",
            trial_result=trial2,
            objective_values={"wns_ps": -1000.0, "hot_ratio": 0.5},
        )

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]

        # Cannot establish dominance with missing values
        assert pareto1.dominates(pareto2, objectives) is False
        assert pareto2.dominates(pareto1, objectives) is False


class TestComputeParetoFrontier:
    """Tests for compute_pareto_frontier."""

    def test_step1_execute_stage_with_multi_objective_metrics(self, temp_dir):
        """Step 1: Execute stage with multi-objective metrics (WNS, area, power)."""
        trials = [
            create_test_trial(
                "case1", wns_ps=-500, area_um2=1000.0, power_mw=10.0, temp_dir=temp_dir
            ),
            create_test_trial(
                "case2", wns_ps=-1000, area_um2=800.0, power_mw=8.0, temp_dir=temp_dir
            ),
        ]

        objectives = [
            TIMING_OBJECTIVE,
            ObjectiveSpec(name="area_um2", metric_path=["area", "total_area_um2"], minimize=True),
            ObjectiveSpec(
                name="total_power_mw", metric_path=["power", "total_power_mw"], minimize=True
            ),
        ]

        # Should execute without errors
        frontier = compute_pareto_frontier(trials, objectives)
        assert frontier is not None
        assert len(frontier.all_trials) == 2

    def test_step2_compute_pareto_frontier(self, temp_dir):
        """Step 2: Compute Pareto frontier of non-dominated trials."""
        trials = [
            # case1: best timing, worst congestion
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.8, temp_dir=temp_dir),
            # case2: worst timing, best congestion
            create_test_trial("case2", wns_ps=-1500, hot_ratio=0.2, temp_dir=temp_dir),
            # case3: middle ground
            create_test_trial("case3", wns_ps=-1000, hot_ratio=0.5, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # All three are Pareto-optimal (each represents a different trade-off)
        # case1: best timing, worst congestion
        # case2: worst timing, best congestion
        # case3: middle timing, middle congestion (not dominated by either)
        assert len(frontier.pareto_optimal_trials) == 3
        pareto_names = frontier.get_pareto_case_names()
        assert "case1" in pareto_names
        assert "case2" in pareto_names
        assert "case3" in pareto_names

    def test_step3_identify_pareto_optimal_cases(self, temp_dir):
        """Step 3: Identify Pareto-optimal Cases."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # Both are Pareto-optimal (trade-off between timing and congestion)
        assert len(frontier.pareto_optimal_trials) == 2
        for trial in frontier.pareto_optimal_trials:
            assert trial.is_pareto_optimal is True

    def test_step4_visualize_pareto_frontier(self, temp_dir):
        """Step 4: Visualize Pareto frontier (export data for plotting)."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # Export to dict for visualization tools
        data = frontier.to_dict()
        assert "pareto_optimal_trials" in data
        assert "dominated_trials" in data
        assert len(data["pareto_optimal_trials"]) == 2

        # Each trial has case_name and objective_values for plotting
        for trial_data in data["pareto_optimal_trials"]:
            assert "case_name" in trial_data
            assert "objective_values" in trial_data
            assert "wns_ps" in trial_data["objective_values"]
            assert "hot_ratio" in trial_data["objective_values"]

    def test_step5_include_pareto_analysis_in_stage_summary(self, temp_dir):
        """Step 5: Include Pareto analysis in stage summary."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir),
            create_test_trial("case3", wns_ps=-1200, hot_ratio=0.6, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # Serialize to stage summary
        summary = frontier.to_dict()
        assert summary["summary"]["total_trials"] == 3
        assert summary["summary"]["pareto_optimal_count"] == 2
        assert summary["summary"]["dominated_count"] == 1

        # Write to file for stage summary
        output_file = temp_dir / "pareto_analysis.json"
        write_pareto_analysis(frontier, output_file)
        assert output_file.exists()

    def test_single_trial_is_pareto_optimal(self, temp_dir):
        """Test single trial is always Pareto-optimal."""
        trials = [create_test_trial("case1", wns_ps=-500, hot_ratio=0.5, temp_dir=temp_dir)]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        assert len(frontier.pareto_optimal_trials) == 1
        assert frontier.pareto_optimal_trials[0].case_name == "case1"
        assert len(frontier.dominated_trials) == 0

    def test_clear_dominated_trial(self, temp_dir):
        """Test trial clearly dominated by another."""
        trials = [
            # case1 dominates case2 in all objectives
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.3, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.7, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        assert len(frontier.pareto_optimal_trials) == 1
        assert frontier.pareto_optimal_trials[0].case_name == "case1"
        assert len(frontier.dominated_trials) == 1
        assert frontier.dominated_trials[0].case_name == "case2"
        assert "case1" in frontier.dominated_trials[0].dominated_by

    def test_three_objectives(self, temp_dir):
        """Test Pareto frontier with three objectives."""
        trials = [
            # case1: best timing, worst congestion and area
            create_test_trial(
                "case1", wns_ps=-500, hot_ratio=0.8, area_um2=1500.0, temp_dir=temp_dir
            ),
            # case2: worst timing, best congestion, middle area
            create_test_trial(
                "case2", wns_ps=-1500, hot_ratio=0.2, area_um2=1000.0, temp_dir=temp_dir
            ),
            # case3: middle timing and congestion, best area
            create_test_trial(
                "case3", wns_ps=-1000, hot_ratio=0.5, area_um2=800.0, temp_dir=temp_dir
            ),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE, AREA_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # All three should be Pareto-optimal (each best in one objective)
        assert len(frontier.pareto_optimal_trials) == 3

    def test_empty_trial_list(self, temp_dir):
        """Test compute_pareto_frontier with empty trial list."""
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier([], objectives)

        assert len(frontier.all_trials) == 0
        assert len(frontier.pareto_optimal_trials) == 0
        assert len(frontier.dominated_trials) == 0

    def test_no_objectives_raises_error(self, temp_dir):
        """Test compute_pareto_frontier with no objectives raises error."""
        trials = [create_test_trial("case1", wns_ps=-500, temp_dir=temp_dir)]

        with pytest.raises(ValueError, match="At least one objective must be specified"):
            compute_pareto_frontier(trials, [])

    def test_trials_missing_metrics_are_skipped(self, temp_dir):
        """Test trials missing objective metrics are skipped."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.5, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, temp_dir=temp_dir),  # Missing hot_ratio
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # Only case1 has all metrics
        assert len(frontier.all_trials) == 1
        assert frontier.all_trials[0].case_name == "case1"

    def test_failed_trials_are_skipped(self, temp_dir):
        """Test failed trials are skipped."""
        trial1 = create_test_trial("case1", wns_ps=-500, hot_ratio=0.5, temp_dir=temp_dir)
        trial2 = create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir)
        trial2.success = False  # Mark as failed

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier([trial1, trial2], objectives)

        # Only successful trials included
        assert len(frontier.all_trials) == 1
        assert frontier.all_trials[0].case_name == "case1"


class TestParetoFrontierSerialization:
    """Tests for Pareto frontier serialization."""

    def test_to_dict_structure(self, temp_dir):
        """Test to_dict produces correct structure."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        data = frontier.to_dict()
        assert "objectives" in data
        assert "pareto_optimal_trials" in data
        assert "dominated_trials" in data
        assert "summary" in data

    def test_to_dict_objectives(self, temp_dir):
        """Test to_dict includes objective specifications."""
        trials = [create_test_trial("case1", wns_ps=-500, hot_ratio=0.5, temp_dir=temp_dir)]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        data = frontier.to_dict()
        assert len(data["objectives"]) == 2
        assert data["objectives"][0]["name"] == "wns_ps"
        assert data["objectives"][0]["minimize"] is False
        assert data["objectives"][1]["name"] == "hot_ratio"
        assert data["objectives"][1]["minimize"] is True

    def test_to_dict_summary(self, temp_dir):
        """Test to_dict includes summary statistics."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir),
            create_test_trial("case3", wns_ps=-1200, hot_ratio=0.6, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        data = frontier.to_dict()
        summary = data["summary"]
        assert summary["total_trials"] == 3
        assert summary["pareto_optimal_count"] == 2
        assert summary["dominated_count"] == 1

    def test_write_pareto_analysis(self, temp_dir):
        """Test writing Pareto analysis to file."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        output_file = temp_dir / "stage_summary" / "pareto_analysis.json"
        write_pareto_analysis(frontier, output_file)

        assert output_file.exists()
        with open(output_file) as f:
            data = json.load(f)
        assert "pareto_optimal_trials" in data
        assert len(data["pareto_optimal_trials"]) == 2


class TestParetoEndToEnd:
    """End-to-end tests for Pareto frontier analysis."""

    def test_realistic_multi_objective_study(self, temp_dir):
        """Test realistic multi-objective Study with timing, congestion, and DRV."""
        # Five trials with different trade-offs
        trials = [
            # case1: Best timing, worst congestion and DRV
            create_test_trial(
                "case1", wns_ps=-200, hot_ratio=0.8, drv_count=50, temp_dir=temp_dir
            ),
            # case2: Worst timing, best congestion, middle DRV
            create_test_trial(
                "case2", wns_ps=-1500, hot_ratio=0.1, drv_count=10, temp_dir=temp_dir
            ),
            # case3: Middle timing and congestion, best DRV
            create_test_trial(
                "case3", wns_ps=-800, hot_ratio=0.4, drv_count=0, temp_dir=temp_dir
            ),
            # case4: Clearly dominated by case1 (worse in all metrics)
            create_test_trial(
                "case4", wns_ps=-2000, hot_ratio=0.9, drv_count=100, temp_dir=temp_dir
            ),
            # case5: Another Pareto-optimal point
            create_test_trial(
                "case5", wns_ps=-600, hot_ratio=0.3, drv_count=5, temp_dir=temp_dir
            ),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE, DRV_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # case1, case2, case3, case5 should be Pareto-optimal
        # case4 is dominated
        assert len(frontier.pareto_optimal_trials) == 4
        assert len(frontier.dominated_trials) == 1
        assert frontier.dominated_trials[0].case_name == "case4"

        # Export for visualization
        data = frontier.to_dict()
        assert data["summary"]["total_trials"] == 5
        assert data["summary"]["pareto_optimal_count"] == 4

    def test_integration_with_survivor_selection(self, temp_dir):
        """Test using Pareto frontier for survivor selection."""
        trials = [
            create_test_trial("case1", wns_ps=-500, hot_ratio=0.7, temp_dir=temp_dir),
            create_test_trial("case2", wns_ps=-1000, hot_ratio=0.3, temp_dir=temp_dir),
            create_test_trial("case3", wns_ps=-1200, hot_ratio=0.6, temp_dir=temp_dir),
        ]

        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        frontier = compute_pareto_frontier(trials, objectives)

        # Use Pareto-optimal trials as survivors for next stage
        pareto_case_names = frontier.get_pareto_case_names()
        assert len(pareto_case_names) == 2
        assert "case1" in pareto_case_names
        assert "case2" in pareto_case_names
        assert "case3" not in pareto_case_names  # Dominated
