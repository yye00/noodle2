"""Tests for F044: Survivor selection using pure_top_n works correctly.

Verification steps from feature_list.json:
1. Create stage with survivor_selection method: pure_top_n, count: 5
2. Run 20 trials with varying WNS
3. Select survivors
4. Verify exactly 5 cases with best WNS are selected
5. Verify selection is deterministic (repeated runs select same cases)
"""

import json
from pathlib import Path

import pytest

from src.controller.ranking import RankingPolicy, rank_pure_top_n
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


def create_trial_with_wns(
    case_name: str, wns_ps: int, tmp_path: Path
) -> TrialResult:
    """Create a test trial result with specified WNS."""
    case_dir = tmp_path / case_name
    case_dir.mkdir(parents=True, exist_ok=True)

    # Write metrics file
    metrics_file = case_dir / "metrics.json"
    metrics = {
        "timing": {
            "wns_ps": wns_ps,
            "tns_ps": wns_ps * 10,  # arbitrary
        }
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


class TestF044PureTopNSurvivorSelection:
    """Tests for F044: pure_top_n survivor selection."""

    def test_step_1_create_stage_with_pure_top_n_method(self) -> None:
        """Step 1: Create stage with survivor_selection method: pure_top_n, count: 5."""
        # Verify the policy exists
        assert hasattr(RankingPolicy, "PURE_TOP_N")
        assert RankingPolicy.PURE_TOP_N == "pure_top_n"

    def test_step_2_run_20_trials_with_varying_wns(self, tmp_path: Path) -> None:
        """Step 2: Run 20 trials with varying WNS."""
        # Create 20 trials with different WNS values
        trials = []
        wns_values = [
            -1000, -950, -900, -850, -800,  # Best 5
            -750, -700, -650, -600, -550,
            -500, -450, -400, -350, -300,
            -250, -200, -150, -100, -50,  # Worst 5
        ]

        for i, wns in enumerate(wns_values):
            trial = create_trial_with_wns(f"case_{i:02d}", wns, tmp_path)
            trials.append(trial)

        assert len(trials) == 20

    def test_step_3_select_survivors(self, tmp_path: Path) -> None:
        """Step 3: Select survivors using pure_top_n."""
        # Create trials
        trials = []
        wns_values = [
            -1000, -950, -900, -850, -800,  # Best 5
            -750, -700, -650, -600, -550,
            -500, -450, -400, -350, -300,
            -250, -200, -150, -100, -50,
        ]

        for i, wns in enumerate(wns_values):
            trial = create_trial_with_wns(f"case_{i:02d}", wns, tmp_path)
            trials.append(trial)

        # Select survivors
        baseline_wns_ps = -1200  # Worse than all trials
        survivor_count = 5
        survivors = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)

        # Should return list of case names
        assert isinstance(survivors, list)
        assert len(survivors) == survivor_count

    def test_step_4_verify_exactly_5_cases_with_best_wns_are_selected(
        self, tmp_path: Path
    ) -> None:
        """Step 4: Verify exactly 5 cases with best WNS are selected."""
        # Create trials with known WNS order
        trials = []
        wns_values = [
            -1000, -950, -900, -850, -800,  # Best 5 (higher/less negative is better)
            -750, -700, -650, -600, -550,
            -500, -450, -400, -350, -300,
            -250, -200, -150, -100, -50,  # These are actually worse in OpenROAD terms
        ]

        # Note: In timing analysis, WNS closer to 0 or positive is better
        # But -50 is better than -1000 (less negative slack)
        # So let's fix this - the best WNS should be the least negative
        wns_values_corrected = [
            -50, -100, -150, -200, -250,  # Best 5 (least negative)
            -300, -350, -400, -450, -500,
            -550, -600, -650, -700, -750,
            -800, -850, -900, -950, -1000,  # Worst 5 (most negative)
        ]

        for i, wns in enumerate(wns_values_corrected):
            trial = create_trial_with_wns(f"case_{i:02d}", wns, tmp_path)
            trials.append(trial)

        # Select survivors
        baseline_wns_ps = -1200
        survivor_count = 5
        survivors = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)

        # Verify exactly 5 survivors
        assert len(survivors) == 5

        # Verify these are the 5 cases with best (least negative) WNS
        # Best cases should be case_00 through case_04
        expected_best_cases = {"case_00", "case_01", "case_02", "case_03", "case_04"}
        assert set(survivors) == expected_best_cases

    def test_step_5_verify_selection_is_deterministic(self, tmp_path: Path) -> None:
        """Step 5: Verify selection is deterministic (repeated runs select same cases)."""
        # Create trials
        trials = []
        wns_values = [-50, -100, -150, -200, -250, -300, -350, -400, -450, -500]

        for i, wns in enumerate(wns_values):
            trial = create_trial_with_wns(f"case_{i:02d}", wns, tmp_path)
            trials.append(trial)

        # Run selection multiple times
        baseline_wns_ps = -600
        survivor_count = 5

        run_1 = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)
        run_2 = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)
        run_3 = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)

        # All runs should produce identical results
        assert run_1 == run_2 == run_3

    def test_deterministic_tiebreaking(self, tmp_path: Path) -> None:
        """Test that ties in WNS are broken deterministically by case name."""
        # Create trials with identical WNS
        trials = []
        for i, case_name in enumerate(["case_c", "case_a", "case_b", "case_d"]):
            trial = create_trial_with_wns(case_name, -500, tmp_path)
            trials.append(trial)

        # All have same WNS, so selection should be by case name alphabetically
        baseline_wns_ps = -600
        survivor_count = 2

        survivors = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)

        # Should select case_a and case_b (alphabetically first)
        assert len(survivors) == 2
        assert survivors == ["case_a", "case_b"]

    def test_handles_fewer_trials_than_requested_survivors(self, tmp_path: Path) -> None:
        """Test that pure_top_n handles case where fewer trials than survivor_count."""
        # Create only 3 trials
        trials = []
        for i in range(3):
            trial = create_trial_with_wns(f"case_{i:02d}", -100 * (i + 1), tmp_path)
            trials.append(trial)

        # Request 5 survivors but only 3 available
        baseline_wns_ps = -500
        survivor_count = 5

        survivors = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)

        # Should return all 3 available trials
        assert len(survivors) == 3

    def test_empty_trial_list(self, tmp_path: Path) -> None:
        """Test that pure_top_n handles empty trial list gracefully."""
        trials = []
        baseline_wns_ps = -500
        survivor_count = 5

        survivors = rank_pure_top_n(trials, baseline_wns_ps, survivor_count)

        # Should return empty list
        assert survivors == []
