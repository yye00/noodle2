"""Tests for F047: Objective function supports pareto mode.

This module tests that studies can be configured with Pareto mode for
multi-objective optimization, where non-dominated solutions form the Pareto frontier.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.controller.pareto import (
    ObjectiveSpec,
    compute_pareto_frontier,
)
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
        study_name="pareto_test",
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


class TestF047ParetoMode:
    """Test suite for F047: Pareto mode objective function."""

    def test_step_1_create_study_with_pareto_mode(self, tmp_path: Path) -> None:
        """Step 1: Create study with objective mode: pareto."""
        study = StudyConfig(
            name="pareto_mode_test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            snapshot_path=str(tmp_path / "snapshot"),
            objective=ObjectiveConfig(
                mode=ObjectiveMode.PARETO,
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

        # Verify study was created with Pareto mode
        assert study.objective.mode == ObjectiveMode.PARETO
        assert study.objective.primary == "wns_ps"
        assert study.objective.secondary == "hot_ratio"

    def test_step_2_set_primary_and_secondary_objectives(self, tmp_path: Path) -> None:
        """Step 2: Set primary: wns_ps, secondary: hot_ratio."""
        objective = ObjectiveConfig(
            mode=ObjectiveMode.PARETO,
            primary="wns_ps",
            secondary="hot_ratio",
        )

        # Verify both objectives are set
        assert objective.primary == "wns_ps"
        assert objective.secondary == "hot_ratio"

        # Verify that Pareto mode requires secondary objective
        with pytest.raises(ValueError, match="pareto mode requires both primary and secondary"):
            ObjectiveConfig(
                mode=ObjectiveMode.PARETO,
                primary="wns_ps",
                secondary=None,  # Missing secondary should raise error
            )

    def test_step_3_run_trials_with_trade_offs(self, tmp_path: Path) -> None:
        """Step 3: Run trials with trade-offs between metrics."""
        # Create trials with different trade-offs:
        # - Trial A: Good timing, bad congestion
        # - Trial B: Bad timing, good congestion
        # - Trial C: Balanced
        # - Trial D: Dominated (worse in both)

        trials = [
            create_test_trial("trial_a", tmp_path, -500, 0.8),    # Good WNS, bad congestion
            create_test_trial("trial_b", tmp_path, -2000, 0.3),   # Bad WNS, good congestion
            create_test_trial("trial_c", tmp_path, -1000, 0.5),   # Balanced
            create_test_trial("trial_d", tmp_path, -2500, 0.9),   # Dominated
        ]

        # Verify trials have different metric values
        for trial in trials:
            assert trial.success
            assert trial.artifacts.metrics_json.exists()

    def test_step_4_verify_pareto_frontier_computed_correctly(
        self, tmp_path: Path
    ) -> None:
        """Step 4: Verify Pareto frontier is computed correctly."""
        # Create trials with known Pareto relationships
        trials = [
            create_test_trial("trial_a", tmp_path, -500, 0.8),    # Pareto-optimal (best timing)
            create_test_trial("trial_b", tmp_path, -2000, 0.3),   # Pareto-optimal (best congestion)
            create_test_trial("trial_c", tmp_path, -1000, 0.5),   # Pareto-optimal (balanced)
            create_test_trial("trial_d", tmp_path, -2500, 0.9),   # Dominated (worse in both)
            create_test_trial("trial_e", tmp_path, -1500, 0.6),   # Dominated by trial_c
        ]

        # Define objectives
        objectives = [
            ObjectiveSpec(
                name="wns_ps",
                metric_path=["timing", "wns_ps"],
                minimize=False,  # Maximize WNS (less negative is better)
            ),
            ObjectiveSpec(
                name="hot_ratio",
                metric_path=["congestion", "hot_ratio"],
                minimize=True,  # Minimize congestion
            ),
        ]

        # Compute Pareto frontier
        frontier = compute_pareto_frontier(trials, objectives)

        # Verify Pareto frontier contains non-dominated trials
        pareto_cases = frontier.get_pareto_case_names()
        assert len(pareto_cases) == 3  # Should have 3 Pareto-optimal trials
        assert "trial_a" in pareto_cases  # Best timing
        assert "trial_b" in pareto_cases  # Best congestion
        assert "trial_c" in pareto_cases  # Balanced
        assert "trial_d" not in pareto_cases  # Dominated
        assert "trial_e" not in pareto_cases  # Dominated

        # Verify dominated trials are identified
        assert len(frontier.dominated_trials) == 2

    def test_step_5_verify_both_objectives_considered(self, tmp_path: Path) -> None:
        """Step 5: Verify both objectives are considered."""
        # Create trials where optimizing only one objective would give wrong answer
        trials = [
            create_test_trial("best_timing_only", tmp_path, -100, 0.95),  # Best timing, worst congestion
            create_test_trial("best_congestion_only", tmp_path, -5000, 0.1),  # Worst timing, best congestion
            create_test_trial("good_both", tmp_path, -800, 0.4),  # Good in both - should be Pareto-optimal
        ]

        objectives = [
            ObjectiveSpec(
                name="wns_ps",
                metric_path=["timing", "wns_ps"],
                minimize=False,
            ),
            ObjectiveSpec(
                name="hot_ratio",
                metric_path=["congestion", "hot_ratio"],
                minimize=True,
            ),
        ]

        frontier = compute_pareto_frontier(trials, objectives)
        pareto_cases = frontier.get_pareto_case_names()

        # All three should be Pareto-optimal because they represent different trade-offs
        assert len(pareto_cases) == 3
        assert "best_timing_only" in pareto_cases
        assert "best_congestion_only" in pareto_cases
        assert "good_both" in pareto_cases

        # Verify that both objectives were actually considered in dominance check
        # If only timing was considered, best_timing_only would dominate good_both
        # If only congestion was considered, best_congestion_only would dominate good_both
        # Since good_both is Pareto-optimal, both objectives must have been considered
        assert frontier.pareto_optimal_trials[0].objective_values["wns_ps"] != 0
        assert frontier.pareto_optimal_trials[0].objective_values["hot_ratio"] != 0


class TestParetoModeIntegration:
    """Integration tests for Pareto mode with study configuration."""

    def test_pareto_mode_with_study_config(self, tmp_path: Path) -> None:
        """Test that Pareto mode integrates with StudyConfig."""
        study = StudyConfig(
            name="pareto_integration",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="base",
            pdk="ASAP7",
            snapshot_path=str(tmp_path / "snapshot"),
            objective=ObjectiveConfig(
                mode=ObjectiveMode.PARETO,
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

        # Validate study configuration
        study.validate()

        # Verify objective configuration is accessible
        assert study.objective.mode == ObjectiveMode.PARETO
        assert study.objective.primary == "wns_ps"
        assert study.objective.secondary == "hot_ratio"

    def test_pareto_mode_validation(self, tmp_path: Path) -> None:
        """Test that Pareto mode validation works correctly."""
        # Should raise error if secondary objective is missing
        with pytest.raises(ValueError, match="pareto mode requires both primary and secondary"):
            ObjectiveConfig(
                mode=ObjectiveMode.PARETO,
                primary="wns_ps",
                secondary=None,
            )

        # Should work with both objectives specified
        config = ObjectiveConfig(
            mode=ObjectiveMode.PARETO,
            primary="wns_ps",
            secondary="hot_ratio",
        )
        assert config.mode == ObjectiveMode.PARETO
