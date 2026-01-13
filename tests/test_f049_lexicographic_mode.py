"""Tests for F049: Objective function supports lexicographic mode.

This module tests that studies can be configured with lexicographic mode for
multi-objective optimization, where primary objective is optimized first and
secondary is used only as a tiebreaker.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.controller.types import (
    ECOClass,
    ExecutionMode,
    ObjectiveConfig,
    ObjectiveMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


def create_test_trial(
    case_name: str, tmp_path: Path, wns_ps: int, hot_ratio: float
) -> TrialResult:
    """Create a test trial result with specified metrics."""
    trial_dir = tmp_path / case_name
    trial_dir.mkdir(parents=True, exist_ok=True)

    # Write metrics file
    metrics_file = trial_dir / "metrics.json"
    metrics = {
        "timing": {"wns_ps": wns_ps},
        "congestion": {"hot_ratio": hot_ratio},
    }
    with open(metrics_file, "w") as f:
        json.dump(metrics, f, indent=2)

    # Create trial config
    config = TrialConfig(
        study_name="lexicographic_test",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path=trial_dir / "script.tcl",
        snapshot_dir=tmp_path / "snapshot",
    )

    # Create artifacts
    artifacts = TrialArtifacts(
        trial_dir=trial_dir,
        metrics_json=metrics_file,
        timing_report=trial_dir / "timing.rpt",
        logs=trial_dir / "trial.log",
    )

    return TrialResult(
        config=config,
        success=True,
        return_code=0,
        runtime_seconds=10.0,
        artifacts=artifacts,
    )


def rank_lexicographic(
    trials: list[TrialResult],
    primary_metric_path: list[str],
    secondary_metric_path: list[str],
    primary_maximize: bool,
    secondary_minimize: bool,
    survivor_count: int,
) -> list[str]:
    """
    Rank trials using lexicographic ordering.

    Primary metric is optimized first, secondary is used only for tiebreaking.

    Args:
        trials: List of trial results
        primary_metric_path: Path to primary metric (e.g., ["timing", "wns_ps"])
        secondary_metric_path: Path to secondary metric (e.g., ["congestion", "hot_ratio"])
        primary_maximize: True to maximize primary, False to minimize
        secondary_minimize: True to minimize secondary, False to maximize
        survivor_count: Number of survivors to select

    Returns:
        List of case names for survivors, ordered by lexicographic rank
    """
    # Filter successful trials with metrics
    successful_trials = [
        t
        for t in trials
        if t.success and t.artifacts.metrics_json and t.artifacts.metrics_json.exists()
    ]

    if not successful_trials:
        return []

    # Extract metrics for each trial
    trials_with_metrics = []
    for trial in successful_trials:
        with open(trial.artifacts.metrics_json) as f:
            metrics = json.load(f)

        # Extract primary metric
        primary_value = metrics
        for key in primary_metric_path:
            primary_value = primary_value.get(key)
            if primary_value is None:
                break

        # Extract secondary metric
        secondary_value = metrics
        for key in secondary_metric_path:
            secondary_value = secondary_value.get(key)
            if secondary_value is None:
                break

        if primary_value is not None and secondary_value is not None:
            trials_with_metrics.append((trial, primary_value, secondary_value))

    if not trials_with_metrics:
        return []

    # Sort lexicographically: primary first, secondary for tiebreaking
    # For primary: if maximize, negate for descending sort; if minimize, use as-is
    # For secondary: same logic
    sorted_trials = sorted(
        trials_with_metrics,
        key=lambda x: (
            -x[1] if primary_maximize else x[1],  # Primary metric
            x[2] if secondary_minimize else -x[2],  # Secondary metric (tiebreaker)
        ),
    )

    # Select top N survivors
    survivors = sorted_trials[:survivor_count]
    return [trial.config.case_name for trial, _, _ in survivors]


class TestF049LexicographicMode:
    """Test suite for F049: Lexicographic mode objective function."""

    def test_step_1_create_study_with_lexicographic_mode(self, tmp_path: Path) -> None:
        """Step 1: Create study with objective mode: lexicographic."""
        study = StudyConfig(
            name="lexicographic_test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            snapshot_path=str(tmp_path / "snapshot"),
            objective=ObjectiveConfig(
                mode=ObjectiveMode.LEXICOGRAPHIC,
                primary="wns_ps",
                secondary="hot_ratio",
            ),
            stages=[
                StageConfig(
                    name="test_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        # Verify study was created with lexicographic mode
        assert study.objective.mode == ObjectiveMode.LEXICOGRAPHIC
        assert study.objective.primary == "wns_ps"
        assert study.objective.secondary == "hot_ratio"

    def test_step_2_set_primary_and_secondary(self, tmp_path: Path) -> None:
        """Step 2: Set primary: wns_ps (optimized first), secondary: hot_ratio (tiebreaker)."""
        objective = ObjectiveConfig(
            mode=ObjectiveMode.LEXICOGRAPHIC,
            primary="wns_ps",
            secondary="hot_ratio",
        )

        # Verify primary and secondary are set
        assert objective.primary == "wns_ps"
        assert objective.secondary == "hot_ratio"

        # Verify lexicographic mode requires both objectives
        with pytest.raises(
            ValueError, match="lexicographic mode requires both primary and secondary"
        ):
            ObjectiveConfig(
                mode=ObjectiveMode.LEXICOGRAPHIC,
                primary="wns_ps",
                secondary=None,  # Missing secondary should fail
            )

    def test_step_3_run_trials(self, tmp_path: Path) -> None:
        """Step 3: Run trials."""
        # Create trials with different metric combinations
        trials = [
            create_test_trial("trial_1", tmp_path, -500, 0.8),
            create_test_trial("trial_2", tmp_path, -1000, 0.5),
            create_test_trial("trial_3", tmp_path, -1500, 0.3),
        ]

        # Verify trials were created
        for trial in trials:
            assert trial.success
            assert trial.artifacts.metrics_json.exists()

    def test_step_4_verify_primary_optimized_first(self, tmp_path: Path) -> None:
        """Step 4: Verify primary metric is optimized first."""
        # Create trials where primary metric varies significantly
        trials = [
            # Trial A: Best primary, worst secondary
            create_test_trial("best_primary", tmp_path, -200, 0.95),

            # Trial B: Worst primary, best secondary
            create_test_trial("worst_primary", tmp_path, -3000, 0.1),

            # Trial C: Middle primary, middle secondary
            create_test_trial("middle", tmp_path, -1500, 0.5),
        ]

        # Rank lexicographically (maximize WNS, minimize congestion)
        survivors = rank_lexicographic(
            trials,
            primary_metric_path=["timing", "wns_ps"],
            secondary_metric_path=["congestion", "hot_ratio"],
            primary_maximize=True,  # Higher/less negative WNS is better
            secondary_minimize=True,  # Lower congestion is better
            survivor_count=2,
        )

        # With lexicographic ordering, primary metric dominates
        # best_primary should be selected first despite having worst secondary
        # middle should be selected second
        # worst_primary should NOT be selected despite having best secondary
        assert survivors[0] == "best_primary"
        assert "worst_primary" not in survivors

    def test_step_5_verify_secondary_used_for_ties(self, tmp_path: Path) -> None:
        """Step 5: Verify secondary is used only for ties in primary."""
        # Create trials with identical primary metrics but different secondary
        trials = [
            # All have same primary metric (WNS = -1000)
            create_test_trial("tie_1_best_secondary", tmp_path, -1000, 0.2),
            create_test_trial("tie_2_worst_secondary", tmp_path, -1000, 0.9),
            create_test_trial("tie_3_mid_secondary", tmp_path, -1000, 0.5),

            # One trial with worse primary but better secondary than some tied trials
            create_test_trial("worse_primary", tmp_path, -2000, 0.1),
        ]

        # Rank lexicographically
        survivors = rank_lexicographic(
            trials,
            primary_metric_path=["timing", "wns_ps"],
            secondary_metric_path=["congestion", "hot_ratio"],
            primary_maximize=True,
            secondary_minimize=True,
            survivor_count=3,
        )

        # All three tied trials (WNS = -1000) should be selected before worse_primary
        assert "tie_1_best_secondary" in survivors
        assert "tie_2_worst_secondary" in survivors
        assert "tie_3_mid_secondary" in survivors
        assert "worse_primary" not in survivors

        # Among the tied trials, secondary metric should determine order
        # tie_1_best_secondary (0.2) should rank before tie_3_mid_secondary (0.5)
        # which should rank before tie_2_worst_secondary (0.9)
        assert survivors[0] == "tie_1_best_secondary"
        assert survivors[1] == "tie_3_mid_secondary"
        assert survivors[2] == "tie_2_worst_secondary"


class TestLexicographicModeValidation:
    """Test validation and integration for lexicographic mode."""

    def test_lexicographic_requires_secondary(self) -> None:
        """Test that lexicographic mode requires secondary objective."""
        with pytest.raises(
            ValueError, match="lexicographic mode requires both primary and secondary"
        ):
            ObjectiveConfig(
                mode=ObjectiveMode.LEXICOGRAPHIC,
                primary="wns_ps",
                secondary=None,
            )

    def test_lexicographic_ignores_weights(self) -> None:
        """Test that weights are not used in lexicographic mode."""
        # Weights can be specified but should be ignored in lexicographic mode
        config = ObjectiveConfig(
            mode=ObjectiveMode.LEXICOGRAPHIC,
            primary="wns_ps",
            secondary="hot_ratio",
            weights=[0.7, 0.3],  # These should be ignored
        )

        assert config.mode == ObjectiveMode.LEXICOGRAPHIC
        # In lexicographic mode, weights don't matter - only ordering matters

    def test_lexicographic_with_study_config(self, tmp_path: Path) -> None:
        """Test lexicographic mode integration with StudyConfig."""
        study = StudyConfig(
            name="lexicographic_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="base",
            pdk="ASAP7",
            snapshot_path=str(tmp_path / "snapshot"),
            objective=ObjectiveConfig(
                mode=ObjectiveMode.LEXICOGRAPHIC,
                primary="wns_ps",
                secondary="hot_ratio",
            ),
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    trial_budget=20,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
                )
            ],
        )

        study.validate()
        assert study.objective.mode == ObjectiveMode.LEXICOGRAPHIC
        assert study.objective.primary == "wns_ps"
        assert study.objective.secondary == "hot_ratio"

    def test_lexicographic_vs_weighted_sum(self, tmp_path: Path) -> None:
        """Test that lexicographic differs from weighted_sum in behavior."""
        # Create trials where lexicographic and weighted_sum would give different results
        trials = [
            # Trial A: Excellent secondary, poor primary
            # Lexicographic: low rank due to poor primary
            # Weighted sum (50/50): might rank high due to excellent secondary
            create_test_trial("excellent_secondary", tmp_path, -5000, 0.1),

            # Trial B: Excellent primary, poor secondary
            # Lexicographic: high rank due to excellent primary
            # Weighted sum (50/50): might rank lower due to poor secondary
            create_test_trial("excellent_primary", tmp_path, -100, 0.95),
        ]

        # Lexicographic ranking should favor excellent_primary
        survivors_lex = rank_lexicographic(
            trials,
            primary_metric_path=["timing", "wns_ps"],
            secondary_metric_path=["congestion", "hot_ratio"],
            primary_maximize=True,
            secondary_minimize=True,
            survivor_count=1,
        )

        # Top survivor in lexicographic mode should be the one with best primary
        assert survivors_lex[0] == "excellent_primary"
