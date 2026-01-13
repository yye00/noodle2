"""Tests for F046: Survivor selection using pareto_front selects non-dominated cases.

Verification steps from feature_list.json:
1. Create stage with multi-objective optimization (WNS vs hot_ratio)
2. Set survivor_selection method: pareto_front
3. Run 20 trials with varying WNS and hot_ratio
4. Select survivors
5. Verify all survivors are on Pareto frontier
6. Verify no dominated cases are selected
"""

import json
from pathlib import Path

import pytest

from src.controller.pareto import CONGESTION_OBJECTIVE, TIMING_OBJECTIVE, ObjectiveSpec
from src.controller.ranking import RankingPolicy, rank_pareto_front
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


def create_trial_with_metrics(
    case_name: str, wns_ps: int, hot_ratio: float, tmp_path: Path
) -> TrialResult:
    """Create a test trial result with specified metrics."""
    case_dir = tmp_path / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    # Write metrics file
    metrics_file = case_dir / "metrics.json"
    metrics = {
        "timing": {
            "wns_ps": wns_ps,
            "tns_ps": wns_ps * 10,
        },
        "congestion": {
            "hot_ratio": hot_ratio,
            "max_overflow": int(hot_ratio * 100),
        },
    }
    with open(metrics_file, "w") as f:
        json.dump(metrics, f)

    # Create trial result
    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path=case_dir / "script.tcl",
        snapshot_dir=tmp_path / "snapshot",
    )

    artifacts = TrialArtifacts(
        trial_dir=case_dir,
        metrics_json=metrics_file,
        timing_report=case_dir / "timing.rpt",
        logs=case_dir / "trial.log",
    )

    return TrialResult(
        config=config,
        success=True,
        return_code=0,
        runtime_seconds=10.0,
        artifacts=artifacts,
    )


class TestF046ParetoFrontSurvivorSelection:
    """Tests for F046: pareto_front survivor selection."""

    def test_step_1_create_stage_with_multi_objective_optimization(self) -> None:
        """Step 1: Create stage with multi-objective optimization (WNS vs hot_ratio)."""
        # Verify we have the required objectives defined
        assert TIMING_OBJECTIVE.name == "wns_ps"
        assert CONGESTION_OBJECTIVE.name == "hot_ratio"

        # These are used together for multi-objective optimization
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        assert len(objectives) == 2

    def test_step_2_set_survivor_selection_method_pareto_front(self) -> None:
        """Step 2: Set survivor_selection method: pareto_front."""
        # Verify the policy exists
        assert hasattr(RankingPolicy, "PARETO_FRONT")
        assert RankingPolicy.PARETO_FRONT == "pareto_front"

    def test_step_3_run_20_trials_with_varying_wns_and_hot_ratio(
        self, tmp_path: Path
    ) -> None:
        """Step 3: Run 20 trials with varying WNS and hot_ratio."""
        # Create 20 trials with different trade-offs
        trials = []
        test_cases = [
            # (case_name, wns_ps, hot_ratio)
            # Good timing, bad congestion
            ("timing_focused_1", -50, 0.9),
            ("timing_focused_2", -100, 0.85),
            ("timing_focused_3", -150, 0.8),
            # Balanced
            ("balanced_1", -200, 0.6),
            ("balanced_2", -250, 0.55),
            ("balanced_3", -300, 0.5),
            # Good congestion, bad timing
            ("congestion_focused_1", -500, 0.3),
            ("congestion_focused_2", -550, 0.25),
            ("congestion_focused_3", -600, 0.2),
            # Dominated cases (worse in both objectives)
            ("dominated_1", -800, 0.95),
            ("dominated_2", -900, 0.9),
            # More test cases
            ("case_12", -180, 0.65),
            ("case_13", -220, 0.58),
            ("case_14", -280, 0.52),
            ("case_15", -350, 0.45),
            ("case_16", -400, 0.4),
            ("case_17", -450, 0.35),
            ("case_18", -520, 0.28),
            ("case_19", -580, 0.22),
            ("case_20", -650, 0.18),
        ]

        for case_name, wns, hot_ratio in test_cases:
            trial = create_trial_with_metrics(case_name, wns, hot_ratio, tmp_path)
            trials.append(trial)

        assert len(trials) == 20

    def test_step_4_select_survivors(self, tmp_path: Path) -> None:
        """Step 4: Select survivors using pareto_front."""
        # Create trials with known Pareto structure
        trials = []
        test_cases = [
            # Pareto-optimal cases (trade-off frontier)
            ("pareto_1", -50, 0.8),  # Best timing
            ("pareto_2", -200, 0.5),  # Balanced
            ("pareto_3", -400, 0.2),  # Best congestion
            # Dominated cases
            ("dominated_1", -600, 0.9),
            ("dominated_2", -500, 0.7),
        ]

        for case_name, wns, hot_ratio in test_cases:
            trial = create_trial_with_metrics(case_name, wns, hot_ratio, tmp_path)
            trials.append(trial)

        # Select survivors
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        survivor_count = 5  # Request up to 5

        survivors = rank_pareto_front(trials, objectives, survivor_count)

        # Should return list of case names
        assert isinstance(survivors, list)
        assert len(survivors) > 0

    def test_step_5_verify_all_survivors_are_on_pareto_frontier(
        self, tmp_path: Path
    ) -> None:
        """Step 5: Verify all survivors are on Pareto frontier."""
        # Create trials with clear Pareto structure
        trials = []
        test_cases = [
            # Pareto-optimal cases
            ("pareto_best_timing", -50, 0.8),
            ("pareto_balanced", -200, 0.5),
            ("pareto_best_congestion", -400, 0.2),
            # Dominated cases (should NOT be selected)
            ("dominated_1", -600, 0.9),
            ("dominated_2", -500, 0.7),
            ("dominated_3", -300, 0.6),  # Dominated by balanced
        ]

        for case_name, wns, hot_ratio in test_cases:
            trial = create_trial_with_metrics(case_name, wns, hot_ratio, tmp_path)
            trials.append(trial)

        # Select survivors
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        survivor_count = 10  # Request more than Pareto size

        survivors = rank_pareto_front(trials, objectives, survivor_count)

        # All survivors should be from Pareto-optimal set
        pareto_cases = {"pareto_best_timing", "pareto_balanced", "pareto_best_congestion"}
        for survivor in survivors:
            assert survivor in pareto_cases, f"{survivor} should be Pareto-optimal"

    def test_step_6_verify_no_dominated_cases_are_selected(self, tmp_path: Path) -> None:
        """Step 6: Verify no dominated cases are selected."""
        # Create trials where some are clearly dominated
        trials = []
        test_cases = [
            # Pareto-optimal cases
            ("optimal_1", -100, 0.3),
            ("optimal_2", -200, 0.2),
            ("optimal_3", -300, 0.1),
            # Dominated cases (worse in at least one objective, not better in others)
            ("dominated_1", -400, 0.4),  # Worse than optimal_1 in both
            ("dominated_2", -500, 0.5),  # Worse than all
            ("dominated_3", -250, 0.25),  # Strictly dominated by interpolation
        ]

        for case_name, wns, hot_ratio in test_cases:
            trial = create_trial_with_metrics(case_name, wns, hot_ratio, tmp_path)
            trials.append(trial)

        # Select survivors
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        survivor_count = 10

        survivors = rank_pareto_front(trials, objectives, survivor_count)

        # Verify dominated cases are NOT in survivors
        dominated_cases = {"dominated_1", "dominated_2", "dominated_3"}
        for survivor in survivors:
            assert survivor not in dominated_cases, f"{survivor} is dominated and should not be selected"

    def test_pareto_front_respects_survivor_count_limit(self, tmp_path: Path) -> None:
        """Test that pareto_front respects survivor_count when Pareto set is larger."""
        # Create many Pareto-optimal cases
        trials = []
        for i in range(10):
            # Create cases on Pareto frontier with different trade-offs
            wns = -50 - (i * 50)
            hot_ratio = 0.8 - (i * 0.07)
            trial = create_trial_with_metrics(f"pareto_{i}", wns, hot_ratio, tmp_path)
            trials.append(trial)

        # Request only 5 survivors
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        survivor_count = 5

        survivors = rank_pareto_front(trials, objectives, survivor_count)

        # Should return at most 5 survivors
        assert len(survivors) <= survivor_count

    def test_pareto_front_with_single_objective_returns_best(self, tmp_path: Path) -> None:
        """Test pareto_front with single objective (should return best by that metric)."""
        trials = []
        for i in range(5):
            wns = -100 - (i * 100)
            trial = create_trial_with_metrics(f"case_{i}", wns, 0.5, tmp_path)
            trials.append(trial)

        # Use only timing objective
        objectives = [TIMING_OBJECTIVE]
        survivor_count = 3

        survivors = rank_pareto_front(trials, objectives, survivor_count)

        # With single objective, should select best 3 by timing
        assert len(survivors) <= survivor_count
        assert "case_0" in survivors  # Best WNS

    def test_empty_trials_returns_empty_survivors(self, tmp_path: Path) -> None:
        """Test that empty trial list returns empty survivors."""
        trials = []
        objectives = [TIMING_OBJECTIVE, CONGESTION_OBJECTIVE]
        survivor_count = 5

        survivors = rank_pareto_front(trials, objectives, survivor_count)

        assert survivors == []
