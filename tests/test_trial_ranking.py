"""Tests for trial ranking and survivor selection."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.ranking import (
    RankingPolicy,
    RankingWeights,
    create_survivor_selector,
    rank_by_congestion_delta,
    rank_by_wns_delta,
    rank_multi_objective,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


def create_mock_trial(
    case_name: str,
    wns_ps: int,
    hot_ratio: float | None = None,
    success: bool = True,
) -> TrialResult:
    """Create a mock trial result with metrics."""
    # Create temporary directory for artifacts
    tmpdir = Path(tempfile.mkdtemp())
    metrics_file = tmpdir / "metrics.json"

    # Write metrics
    metrics = {"timing": {"wns_ps": wns_ps}}
    if hot_ratio is not None:
        metrics["congestion"] = {"hot_ratio": hot_ratio}

    with open(metrics_file, "w") as f:
        json.dump(metrics, f)

    # Create trial result
    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path="/dev/null",
    )

    artifacts = TrialArtifacts(trial_dir=tmpdir, metrics_json=metrics_file)

    return TrialResult(
        config=config,
        success=success,
        return_code=0,
        runtime_seconds=1.0,
        artifacts=artifacts,
    )


class TestRankingWeights:
    """Test RankingWeights validation."""

    def test_default_weights(self):
        """Test default weights sum to 1.0."""
        weights = RankingWeights()
        assert weights.timing_weight == 0.6
        assert weights.congestion_weight == 0.4
        assert abs(weights.timing_weight + weights.congestion_weight - 1.0) < 0.01

    def test_custom_weights(self):
        """Test custom weights are accepted."""
        weights = RankingWeights(timing_weight=0.7, congestion_weight=0.3)
        assert weights.timing_weight == 0.7
        assert weights.congestion_weight == 0.3

    def test_weights_must_be_in_range(self):
        """Test weights must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            RankingWeights(timing_weight=1.5, congestion_weight=-0.5)

    def test_weights_must_sum_to_one(self):
        """Test weights must sum to 1.0."""
        with pytest.raises(ValueError, match="must equal 1.0"):
            RankingWeights(timing_weight=0.6, congestion_weight=0.6)


class TestRankByWNSDelta:
    """Test WNS-based ranking."""

    def test_rank_by_wns_improvement(self):
        """Test trials are ranked by WNS improvement."""
        baseline_wns = -1000  # Bad timing

        trials = [
            create_mock_trial("trial_0", wns_ps=-900),  # +100 improvement
            create_mock_trial("trial_1", wns_ps=-500),  # +500 improvement (best)
            create_mock_trial("trial_2", wns_ps=-800),  # +200 improvement
        ]

        survivors = rank_by_wns_delta(trials, baseline_wns, survivor_count=2)

        # Best two should be trial_1 and trial_2
        assert len(survivors) == 2
        assert survivors[0] == "trial_1"  # Best improvement
        assert survivors[1] == "trial_2"  # Second best

    def test_rank_by_wns_handles_negative_slack(self):
        """Test ranking works with all negative slacks."""
        baseline_wns = -2000

        trials = [
            create_mock_trial("trial_0", wns_ps=-1800),  # +200
            create_mock_trial("trial_1", wns_ps=-1500),  # +500 (best)
            create_mock_trial("trial_2", wns_ps=-1900),  # +100
        ]

        survivors = rank_by_wns_delta(trials, baseline_wns, survivor_count=1)

        assert len(survivors) == 1
        assert survivors[0] == "trial_1"

    def test_rank_by_wns_handles_positive_slack(self):
        """Test ranking works when timing improves to positive slack."""
        baseline_wns = -500

        trials = [
            create_mock_trial("trial_0", wns_ps=-100),  # +400
            create_mock_trial("trial_1", wns_ps=200),  # +700 (best)
            create_mock_trial("trial_2", wns_ps=100),  # +600
        ]

        survivors = rank_by_wns_delta(trials, baseline_wns, survivor_count=3)

        assert len(survivors) == 3
        assert survivors[0] == "trial_1"
        assert survivors[1] == "trial_2"
        assert survivors[2] == "trial_0"

    def test_rank_by_wns_filters_failed_trials(self):
        """Test failed trials are excluded from ranking."""
        baseline_wns = -1000

        trials = [
            create_mock_trial("trial_0", wns_ps=-500, success=True),
            create_mock_trial("trial_1", wns_ps=-100, success=False),  # Failed
            create_mock_trial("trial_2", wns_ps=-800, success=True),
        ]

        survivors = rank_by_wns_delta(trials, baseline_wns, survivor_count=2)

        # Only successful trials ranked
        assert len(survivors) == 2
        assert "trial_1" not in survivors

    def test_rank_by_wns_returns_empty_if_no_successful_trials(self):
        """Test empty list returned when all trials fail."""
        baseline_wns = -1000

        trials = [
            create_mock_trial("trial_0", wns_ps=-500, success=False),
            create_mock_trial("trial_1", wns_ps=-100, success=False),
        ]

        survivors = rank_by_wns_delta(trials, baseline_wns, survivor_count=2)

        assert survivors == []

    def test_rank_by_wns_limits_to_survivor_count(self):
        """Test survivor count is respected."""
        baseline_wns = -1000

        trials = [
            create_mock_trial("trial_0", wns_ps=-900),
            create_mock_trial("trial_1", wns_ps=-500),
            create_mock_trial("trial_2", wns_ps=-800),
            create_mock_trial("trial_3", wns_ps=-700),
        ]

        survivors = rank_by_wns_delta(trials, baseline_wns, survivor_count=2)

        assert len(survivors) == 2


class TestRankByCongestionDelta:
    """Test congestion-based ranking."""

    def test_rank_by_congestion_reduction(self):
        """Test trials are ranked by congestion reduction."""
        baseline_hot_ratio = 0.8  # High congestion

        trials = [
            create_mock_trial("trial_0", wns_ps=-1000, hot_ratio=0.7),  # -0.1 reduction
            create_mock_trial("trial_1", wns_ps=-1000, hot_ratio=0.3),  # -0.5 (best)
            create_mock_trial("trial_2", wns_ps=-1000, hot_ratio=0.5),  # -0.3
        ]

        survivors = rank_by_congestion_delta(
            trials, baseline_hot_ratio, survivor_count=2
        )

        assert len(survivors) == 2
        assert survivors[0] == "trial_1"  # Best reduction
        assert survivors[1] == "trial_2"  # Second best

    def test_rank_by_congestion_handles_no_improvement(self):
        """Test ranking when some trials worsen congestion."""
        baseline_hot_ratio = 0.5

        trials = [
            create_mock_trial("trial_0", wns_ps=-1000, hot_ratio=0.4),  # -0.1 (good)
            create_mock_trial("trial_1", wns_ps=-1000, hot_ratio=0.6),  # +0.1 (worse)
            create_mock_trial("trial_2", wns_ps=-1000, hot_ratio=0.2),  # -0.3 (best)
        ]

        survivors = rank_by_congestion_delta(
            trials, baseline_hot_ratio, survivor_count=3
        )

        # All trials ranked, even those that worsen
        assert len(survivors) == 3
        assert survivors[0] == "trial_2"  # Best
        assert survivors[1] == "trial_0"
        assert survivors[2] == "trial_1"  # Worst

    def test_rank_by_congestion_filters_trials_without_metrics(self):
        """Test trials without congestion metrics are excluded."""
        baseline_hot_ratio = 0.8

        trials = [
            create_mock_trial(
                "trial_0", wns_ps=-1000, hot_ratio=0.5
            ),  # Has congestion
            create_mock_trial("trial_1", wns_ps=-1000, hot_ratio=None),  # No congestion
            create_mock_trial(
                "trial_2", wns_ps=-1000, hot_ratio=0.3
            ),  # Has congestion
        ]

        survivors = rank_by_congestion_delta(
            trials, baseline_hot_ratio, survivor_count=2
        )

        # Only trials with congestion metrics
        assert len(survivors) == 2
        assert "trial_1" not in survivors

    def test_rank_by_congestion_returns_empty_if_no_metrics(self):
        """Test empty list when no trials have congestion metrics."""
        baseline_hot_ratio = 0.8

        trials = [
            create_mock_trial("trial_0", wns_ps=-1000, hot_ratio=None),
            create_mock_trial("trial_1", wns_ps=-1000, hot_ratio=None),
        ]

        survivors = rank_by_congestion_delta(
            trials, baseline_hot_ratio, survivor_count=2
        )

        assert survivors == []


class TestRankMultiObjective:
    """Test multi-objective ranking."""

    def test_rank_multi_objective_balances_metrics(self):
        """Test multi-objective ranking balances timing and congestion."""
        baseline_wns = -1000
        baseline_hot_ratio = 0.8

        # trial_0: great timing, poor congestion
        # trial_1: poor timing, great congestion
        # trial_2: balanced improvement
        trials = [
            create_mock_trial("trial_0", wns_ps=-100, hot_ratio=0.7),  # WNS +900, HR -0.1
            create_mock_trial("trial_1", wns_ps=-900, hot_ratio=0.2),  # WNS +100, HR -0.6
            create_mock_trial("trial_2", wns_ps=-500, hot_ratio=0.4),  # WNS +500, HR -0.4
        ]

        # Default weights: 60% timing, 40% congestion
        survivors = rank_multi_objective(
            trials, baseline_wns, baseline_hot_ratio, survivor_count=3
        )

        assert len(survivors) == 3
        # trial_0 should rank highest (best timing, default favors timing)
        assert survivors[0] == "trial_0"

    def test_rank_multi_objective_with_custom_weights(self):
        """Test multi-objective ranking respects custom weights."""
        baseline_wns = -1000
        baseline_hot_ratio = 0.8

        trials = [
            create_mock_trial("trial_0", wns_ps=-100, hot_ratio=0.7),  # Great timing
            create_mock_trial("trial_1", wns_ps=-900, hot_ratio=0.2),  # Great congestion
            create_mock_trial("trial_2", wns_ps=-500, hot_ratio=0.4),  # Balanced
        ]

        # Heavily favor congestion
        weights = RankingWeights(timing_weight=0.2, congestion_weight=0.8)
        survivors = rank_multi_objective(
            trials, baseline_wns, baseline_hot_ratio, survivor_count=3, weights=weights
        )

        # trial_1 should now rank highest (best congestion)
        assert survivors[0] == "trial_1"

    def test_rank_multi_objective_handles_equal_performance(self):
        """Test multi-objective ranking when all trials perform equally."""
        baseline_wns = -1000
        baseline_hot_ratio = 0.8

        trials = [
            create_mock_trial("trial_0", wns_ps=-500, hot_ratio=0.4),
            create_mock_trial("trial_1", wns_ps=-500, hot_ratio=0.4),
            create_mock_trial("trial_2", wns_ps=-500, hot_ratio=0.4),
        ]

        survivors = rank_multi_objective(
            trials, baseline_wns, baseline_hot_ratio, survivor_count=2
        )

        # Should return 2 survivors (order doesn't matter for equal performance)
        assert len(survivors) == 2

    def test_rank_multi_objective_filters_trials_without_metrics(self):
        """Test trials without timing metrics are excluded."""
        baseline_wns = -1000
        baseline_hot_ratio = 0.8

        trials = [
            create_mock_trial("trial_0", wns_ps=-500, hot_ratio=0.4),
            create_mock_trial("trial_1", wns_ps=-700, hot_ratio=None),  # No congestion
            create_mock_trial("trial_2", wns_ps=-300, hot_ratio=0.3),
        ]

        survivors = rank_multi_objective(
            trials, baseline_wns, baseline_hot_ratio, survivor_count=3
        )

        # trial_1 still ranked (congestion defaults to 0 contribution)
        assert len(survivors) == 3

    def test_rank_multi_objective_normalization(self):
        """Test multi-objective ranking normalizes deltas correctly."""
        baseline_wns = -1000
        baseline_hot_ratio = 0.5

        # Wide range of improvements
        trials = [
            create_mock_trial("trial_0", wns_ps=-100, hot_ratio=0.1),  # Best both
            create_mock_trial("trial_1", wns_ps=-900, hot_ratio=0.4),  # Worst both
            create_mock_trial("trial_2", wns_ps=-500, hot_ratio=0.25),  # Middle
        ]

        survivors = rank_multi_objective(
            trials, baseline_wns, baseline_hot_ratio, survivor_count=3
        )

        # trial_0 should dominate (best on both objectives)
        assert survivors[0] == "trial_0"
        assert survivors[1] == "trial_2"
        assert survivors[2] == "trial_1"


class TestCreateSurvivorSelector:
    """Test survivor selector factory."""

    def test_create_wns_selector(self):
        """Test creating WNS-based survivor selector."""
        selector = create_survivor_selector(
            policy=RankingPolicy.WNS_DELTA, baseline_wns_ps=-1000
        )

        trials = [
            create_mock_trial("trial_0", wns_ps=-500),
            create_mock_trial("trial_1", wns_ps=-800),
        ]

        survivors = selector(trials, 1)

        assert len(survivors) == 1
        assert survivors[0] == "trial_0"

    def test_create_congestion_selector(self):
        """Test creating congestion-based survivor selector."""
        selector = create_survivor_selector(
            policy=RankingPolicy.CONGESTION_DELTA,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
        )

        trials = [
            create_mock_trial("trial_0", wns_ps=-1000, hot_ratio=0.5),
            create_mock_trial("trial_1", wns_ps=-1000, hot_ratio=0.3),
        ]

        survivors = selector(trials, 1)

        assert len(survivors) == 1
        assert survivors[0] == "trial_1"

    def test_create_multi_objective_selector(self):
        """Test creating multi-objective survivor selector."""
        selector = create_survivor_selector(
            policy=RankingPolicy.MULTI_OBJECTIVE,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
        )

        trials = [
            create_mock_trial("trial_0", wns_ps=-100, hot_ratio=0.5),
            create_mock_trial("trial_1", wns_ps=-500, hot_ratio=0.2),
        ]

        survivors = selector(trials, 2)

        assert len(survivors) == 2

    def test_create_selector_requires_hot_ratio_for_congestion(self):
        """Test congestion selector requires baseline_hot_ratio."""
        with pytest.raises(ValueError, match="baseline_hot_ratio is required"):
            create_survivor_selector(
                policy=RankingPolicy.CONGESTION_DELTA, baseline_wns_ps=-1000
            )

    def test_create_selector_requires_hot_ratio_for_multi_objective(self):
        """Test multi-objective selector requires baseline_hot_ratio."""
        with pytest.raises(ValueError, match="baseline_hot_ratio is required"):
            create_survivor_selector(
                policy=RankingPolicy.MULTI_OBJECTIVE, baseline_wns_ps=-1000
            )

    def test_create_selector_with_custom_weights(self):
        """Test creating selector with custom weights."""
        weights = RankingWeights(timing_weight=0.7, congestion_weight=0.3)
        selector = create_survivor_selector(
            policy=RankingPolicy.MULTI_OBJECTIVE,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            weights=weights,
        )

        # Selector should use the custom weights
        trials = [
            create_mock_trial("trial_0", wns_ps=-100, hot_ratio=0.7),
            create_mock_trial("trial_1", wns_ps=-900, hot_ratio=0.2),
        ]

        survivors = selector(trials, 1)

        # With 70% timing weight, trial_0 (best timing) should win
        assert survivors[0] == "trial_0"


class TestDeterministicRanking:
    """Test ranking is deterministic."""

    def test_wns_ranking_is_deterministic(self):
        """Test WNS ranking produces same results on multiple runs."""
        baseline_wns = -1000

        trials = [
            create_mock_trial("trial_0", wns_ps=-500),
            create_mock_trial("trial_1", wns_ps=-800),
            create_mock_trial("trial_2", wns_ps=-300),
        ]

        # Run ranking multiple times
        results = [
            rank_by_wns_delta(trials, baseline_wns, survivor_count=2) for _ in range(5)
        ]

        # All results should be identical
        for result in results[1:]:
            assert result == results[0]

    def test_multi_objective_ranking_is_deterministic(self):
        """Test multi-objective ranking is deterministic."""
        baseline_wns = -1000
        baseline_hot_ratio = 0.8

        trials = [
            create_mock_trial("trial_0", wns_ps=-500, hot_ratio=0.5),
            create_mock_trial("trial_1", wns_ps=-800, hot_ratio=0.3),
            create_mock_trial("trial_2", wns_ps=-300, hot_ratio=0.6),
        ]

        # Run ranking multiple times
        results = [
            rank_multi_objective(trials, baseline_wns, baseline_hot_ratio, survivor_count=2)
            for _ in range(5)
        ]

        # All results should be identical
        for result in results[1:]:
            assert result == results[0]
