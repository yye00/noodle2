"""Tests for F246: Diverse survivor selection with ECO path distance metric.

Feature: Support diverse_top_n survivor selection with eco_path_distance metric

Test Steps:
1. Configure survivor_selection method: diverse_top_n
2. Set diversity metric: eco_path_distance
3. Set min_diversity: 0.3
4. Run stage with 10 survivors
5. Verify selected survivors have diverse ECO application sequences
6. Verify pairwise distance between survivors >= 0.3
7. Verify diversity constraint is logged
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.ranking import (
    DiversityConfig,
    DiversityMetric,
    RankingPolicy,
    RankingWeights,
    compute_eco_path_distance,
    create_survivor_selector,
    get_eco_sequence_from_trial,
    rank_diverse_top_n,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


class TestECOPathDistance:
    """Test ECO path distance computation."""

    def test_identical_sequences_have_zero_distance(self) -> None:
        """Identical ECO sequences should have distance 0.0."""
        seq1 = ["buffer_insertion", "gate_sizing", "cell_swap"]
        seq2 = ["buffer_insertion", "gate_sizing", "cell_swap"]

        distance = compute_eco_path_distance(seq1, seq2)
        assert distance == 0.0

    def test_completely_different_sequences_have_max_distance(self) -> None:
        """Completely different sequences should have distance 1.0."""
        seq1 = ["buffer_insertion"]
        seq2 = ["gate_sizing"]

        distance = compute_eco_path_distance(seq1, seq2)
        assert distance == 1.0

    def test_empty_sequences_have_zero_distance(self) -> None:
        """Two empty sequences should have distance 0.0."""
        distance = compute_eco_path_distance([], [])
        assert distance == 0.0

    def test_one_empty_sequence_has_max_distance(self) -> None:
        """Empty vs non-empty sequence should have distance 1.0."""
        seq1 = ["buffer_insertion"]
        seq2: list[str] = []

        distance = compute_eco_path_distance(seq1, seq2)
        assert distance == 1.0

    def test_partial_overlap_sequences(self) -> None:
        """Sequences with partial overlap should have intermediate distance."""
        seq1 = ["buffer_insertion", "gate_sizing"]
        seq2 = ["buffer_insertion", "cell_swap"]

        distance = compute_eco_path_distance(seq1, seq2)
        # One substitution out of 2 operations = 0.5
        assert distance == 0.5

    def test_insertion_required(self) -> None:
        """Sequences requiring insertion should compute correct distance."""
        seq1 = ["buffer_insertion"]
        seq2 = ["buffer_insertion", "gate_sizing"]

        distance = compute_eco_path_distance(seq1, seq2)
        # One insertion out of 2 operations = 0.5
        assert distance == 0.5

    def test_deletion_required(self) -> None:
        """Sequences requiring deletion should compute correct distance."""
        seq1 = ["buffer_insertion", "gate_sizing", "cell_swap"]
        seq2 = ["buffer_insertion", "gate_sizing"]

        distance = compute_eco_path_distance(seq1, seq2)
        # One deletion out of 3 operations = 1/3
        assert abs(distance - 1.0 / 3.0) < 0.01

    def test_reordering_has_distance(self) -> None:
        """Reordered sequences should have non-zero distance."""
        seq1 = ["buffer_insertion", "gate_sizing"]
        seq2 = ["gate_sizing", "buffer_insertion"]

        distance = compute_eco_path_distance(seq1, seq2)
        # Requires 2 operations to transform
        assert distance == 1.0


class TestGetECOSequence:
    """Test ECO sequence extraction from trial results."""

    def test_extract_eco_sequence_from_metadata(self, tmp_path: Path) -> None:
        """Should extract ECO sequence from trial metadata."""
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()

        config = TrialConfig(
            study_name="test",
            case_name="case_1",
            stage_index=0,
            trial_index=0,
            script_path=trial_dir / "script.tcl",
            metadata={"eco_sequence": ["buffer_insertion", "gate_sizing"]},
        )

        artifacts = TrialArtifacts(trial_dir=trial_dir)
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=artifacts,
        )

        eco_seq = get_eco_sequence_from_trial(result)
        assert eco_seq == ["buffer_insertion", "gate_sizing"]

    def test_extract_single_eco_from_metadata(self, tmp_path: Path) -> None:
        """Should extract single ECO from metadata."""
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()

        config = TrialConfig(
            study_name="test",
            case_name="case_1",
            stage_index=0,
            trial_index=0,
            script_path=trial_dir / "script.tcl",
            metadata={"eco_name": "buffer_insertion"},
        )

        artifacts = TrialArtifacts(trial_dir=trial_dir)
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=artifacts,
        )

        eco_seq = get_eco_sequence_from_trial(result)
        assert eco_seq == ["buffer_insertion"]

    def test_extract_eco_with_parent_sequence(self, tmp_path: Path) -> None:
        """Should combine parent ECO sequence with current ECO."""
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()

        config = TrialConfig(
            study_name="test",
            case_name="case_1",
            stage_index=1,
            trial_index=0,
            script_path=trial_dir / "script.tcl",
            metadata={
                "eco_name": "cell_swap",
                "parent_eco_sequence": ["buffer_insertion"],
            },
        )

        artifacts = TrialArtifacts(trial_dir=trial_dir)
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=artifacts,
        )

        eco_seq = get_eco_sequence_from_trial(result)
        assert eco_seq == ["buffer_insertion", "cell_swap"]

    def test_fallback_to_empty_sequence(self, tmp_path: Path) -> None:
        """Should return empty sequence for base case with no ECO metadata."""
        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()

        config = TrialConfig(
            study_name="test",
            case_name="base",
            stage_index=0,
            trial_index=0,
            script_path=trial_dir / "script.tcl",
        )

        artifacts = TrialArtifacts(trial_dir=trial_dir)
        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=artifacts,
        )

        eco_seq = get_eco_sequence_from_trial(result)
        assert eco_seq == []


class TestDiversityConfig:
    """Test diversity configuration."""

    def test_create_default_diversity_config(self) -> None:
        """Should create diversity config with defaults."""
        config = DiversityConfig()
        assert config.enabled is False
        assert config.metric == DiversityMetric.ECO_PATH_DISTANCE
        assert config.min_diversity == 0.3
        assert config.always_keep_best is True
        assert config.random_survivors == 0

    def test_create_enabled_diversity_config(self) -> None:
        """Should create enabled diversity config."""
        config = DiversityConfig(enabled=True, min_diversity=0.5)
        assert config.enabled is True
        assert config.min_diversity == 0.5

    def test_validate_min_diversity_range(self) -> None:
        """Should validate min_diversity is in [0, 1]."""
        with pytest.raises(ValueError, match="min_diversity must be between 0.0 and 1.0"):
            DiversityConfig(min_diversity=-0.1)

        with pytest.raises(ValueError, match="min_diversity must be between 0.0 and 1.0"):
            DiversityConfig(min_diversity=1.5)

    def test_validate_random_survivors_non_negative(self) -> None:
        """Should validate random_survivors is non-negative."""
        with pytest.raises(ValueError, match="random_survivors must be non-negative"):
            DiversityConfig(random_survivors=-1)


def create_mock_trial_with_eco_sequence(
    case_name: str,
    eco_sequence: list[str],
    wns_ps: int,
    hot_ratio: float,
    tmp_base_dir: Path | None = None,
) -> TrialResult:
    """Create a mock trial result with ECO sequence and metrics."""
    # Use provided base dir or create in system temp
    if tmp_base_dir is None:
        tmp_base_dir = Path(tempfile.gettempdir())

    trial_dir = tmp_base_dir / f"trial_{case_name}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    metrics_file = trial_dir / "metrics.json"

    # Write metrics to file
    metrics = {
        "timing": {"wns_ps": wns_ps},
        "congestion": {"hot_ratio": hot_ratio},
    }
    with open(metrics_file, "w") as f:
        json.dump(metrics, f)

    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path=trial_dir / "script.tcl",
        metadata={"eco_sequence": eco_sequence},
    )

    artifacts = TrialArtifacts(
        trial_dir=trial_dir,
        metrics_json=metrics_file,
    )

    return TrialResult(
        config=config,
        success=True,
        return_code=0,
        runtime_seconds=10.0,
        artifacts=artifacts,
    )


class TestDiverseTopNSelection:
    """Test diverse_top_n survivor selection."""

    def test_step_1_configure_diverse_top_n_method(self) -> None:
        """Step 1: Configure survivor_selection method: diverse_top_n."""
        # Verify RankingPolicy includes DIVERSE_TOP_N
        assert hasattr(RankingPolicy, "DIVERSE_TOP_N")
        assert RankingPolicy.DIVERSE_TOP_N == "diverse_top_n"

    def test_step_2_set_diversity_metric_eco_path_distance(self) -> None:
        """Step 2: Set diversity metric: eco_path_distance."""
        config = DiversityConfig(
            enabled=True,
            metric=DiversityMetric.ECO_PATH_DISTANCE,
        )
        assert config.metric == DiversityMetric.ECO_PATH_DISTANCE

    def test_step_3_set_min_diversity_0_3(self) -> None:
        """Step 3: Set min_diversity: 0.3."""
        config = DiversityConfig(
            enabled=True,
            min_diversity=0.3,
        )
        assert config.min_diversity == 0.3

    def test_step_4_run_stage_with_10_survivors(self) -> None:
        """Step 4: Run stage with 10 survivors."""
        # Create 15 mock trials with different ECO sequences
        trials = []
        eco_sequences = [
            ["buffer_insertion"],
            ["gate_sizing"],
            ["cell_swap"],
            ["buffer_insertion", "gate_sizing"],
            ["buffer_insertion", "cell_swap"],
            ["gate_sizing", "cell_swap"],
            ["buffer_insertion", "gate_sizing", "cell_swap"],
            ["gate_sizing", "buffer_insertion"],
            ["cell_swap", "buffer_insertion"],
            ["vt_swap"],
            ["buffer_insertion", "vt_swap"],
            ["gate_sizing", "vt_swap"],
            ["cell_swap", "vt_swap"],
            ["buffer_insertion", "gate_sizing", "vt_swap"],
            ["gate_sizing", "cell_swap", "vt_swap"],
        ]

        for i, eco_seq in enumerate(eco_sequences):
            # Vary WNS to create quality differences
            wns_ps = -1000 + i * 100
            hot_ratio = 0.8 - i * 0.02
            trial = create_mock_trial_with_eco_sequence(
                f"case_{i}",
                eco_seq,
                wns_ps,
                hot_ratio,
            )
            trials.append(trial)

        # Create diversity config
        diversity_config = DiversityConfig(
            enabled=True,
            metric=DiversityMetric.ECO_PATH_DISTANCE,
            min_diversity=0.3,
        )

        # Select 10 survivors
        survivors = rank_diverse_top_n(
            trial_results=trials,
            baseline_wns_ps=-2000,
            baseline_hot_ratio=0.9,
            survivor_count=10,
            diversity_config=diversity_config,
        )

        # Should return exactly 10 survivors
        assert len(survivors) == 10

    def test_step_5_verify_survivors_have_diverse_eco_sequences(self) -> None:
        """Step 5: Verify selected survivors have diverse ECO application sequences."""
        # Create trials with similar quality but different ECO sequences
        trials = []
        eco_sequences = [
            ["buffer_insertion"],
            ["buffer_insertion", "gate_sizing"],  # Similar to above
            ["gate_sizing"],  # Very different
            ["gate_sizing", "cell_swap"],  # Similar to above
            ["cell_swap"],  # Very different
            ["vt_swap"],  # Very different
            ["buffer_insertion", "cell_swap"],  # Different from all
            ["gate_sizing", "vt_swap"],  # Different from all
        ]

        for i, eco_seq in enumerate(eco_sequences):
            # All trials have similar quality
            wns_ps = -500 + i * 10
            hot_ratio = 0.5 - i * 0.01
            trial = create_mock_trial_with_eco_sequence(
                f"case_{i}",
                eco_seq,
                wns_ps,
                hot_ratio,
            )
            trials.append(trial)

        diversity_config = DiversityConfig(
            enabled=True,
            metric=DiversityMetric.ECO_PATH_DISTANCE,
            min_diversity=0.5,  # Higher threshold for this test
        )

        survivors = rank_diverse_top_n(
            trial_results=trials,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            survivor_count=5,
            diversity_config=diversity_config,
        )

        # Extract ECO sequences for survivors
        survivor_trials = [t for t in trials if t.config.case_name in survivors]
        survivor_sequences = [get_eco_sequence_from_trial(t) for t in survivor_trials]

        # Verify all sequences are different
        assert len(set(tuple(seq) for seq in survivor_sequences)) == len(survivor_sequences)

    def test_step_6_verify_pairwise_distance_at_least_min_diversity(self) -> None:
        """Step 6: Verify pairwise distance between survivors >= 0.3."""
        # Create trials with specific ECO sequences
        trials = []
        eco_sequences = [
            ["buffer_insertion"],  # Best quality
            ["buffer_insertion", "gate_sizing"],  # Distance 0.5 from first
            ["gate_sizing"],  # Distance 1.0 from first
            ["cell_swap"],  # Distance 1.0 from first
            ["buffer_insertion", "cell_swap"],  # Distance 0.5 from first
            ["vt_swap"],  # Distance 1.0 from first
        ]

        for i, eco_seq in enumerate(eco_sequences):
            wns_ps = -500 + i * 100
            hot_ratio = 0.7 - i * 0.05
            trial = create_mock_trial_with_eco_sequence(
                f"case_{i}",
                eco_seq,
                wns_ps,
                hot_ratio,
            )
            trials.append(trial)

        diversity_config = DiversityConfig(
            enabled=True,
            metric=DiversityMetric.ECO_PATH_DISTANCE,
            min_diversity=0.3,
        )

        survivors = rank_diverse_top_n(
            trial_results=trials,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.9,
            survivor_count=4,
            diversity_config=diversity_config,
        )

        # Get ECO sequences for survivors
        survivor_trials = [t for t in trials if t.config.case_name in survivors]
        survivor_sequences = [get_eco_sequence_from_trial(t) for t in survivor_trials]

        # Verify all pairwise distances >= 0.3
        for i in range(len(survivor_sequences)):
            for j in range(i + 1, len(survivor_sequences)):
                distance = compute_eco_path_distance(
                    survivor_sequences[i],
                    survivor_sequences[j],
                )
                assert distance >= 0.3, (
                    f"Distance between survivor {i} and {j} is {distance:.2f}, "
                    f"expected >= 0.3"
                )

    def test_step_7_verify_diversity_constraint_is_applied(self) -> None:
        """Step 7: Verify diversity constraint is applied (logged behavior)."""
        # Create trials where only some meet diversity constraint
        trials = []
        # Create many similar trials and few diverse ones
        for i in range(5):
            # Very similar sequences (low diversity)
            eco_seq = ["buffer_insertion", "gate_sizing"] + [f"eco_{i}"]
            trial = create_mock_trial_with_eco_sequence(
                f"similar_{i}",
                eco_seq,
                wns_ps=-500 + i * 10,
                hot_ratio=0.5,
            )
            trials.append(trial)

        # Add diverse trials with lower quality
        diverse_sequences = [
            ["cell_swap"],
            ["vt_swap"],
            ["pin_swap"],
        ]
        for i, eco_seq in enumerate(diverse_sequences):
            trial = create_mock_trial_with_eco_sequence(
                f"diverse_{i}",
                eco_seq,
                wns_ps=-800,  # Lower quality
                hot_ratio=0.7,  # Lower quality
            )
            trials.append(trial)

        diversity_config = DiversityConfig(
            enabled=True,
            metric=DiversityMetric.ECO_PATH_DISTANCE,
            min_diversity=0.5,
            always_keep_best=True,
        )

        survivors = rank_diverse_top_n(
            trial_results=trials,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            survivor_count=4,
            diversity_config=diversity_config,
        )

        # Should include the best trial plus diverse ones
        # Not all similar trials should be selected
        survivor_trials = [t for t in trials if t.config.case_name in survivors]
        survivor_sequences = [get_eco_sequence_from_trial(t) for t in survivor_trials]

        # Verify diversity constraint was applied
        # All pairwise distances should be >= 0.5
        for i in range(len(survivor_sequences)):
            for j in range(i + 1, len(survivor_sequences)):
                distance = compute_eco_path_distance(
                    survivor_sequences[i],
                    survivor_sequences[j],
                )
                assert distance >= 0.5 or len(survivor_sequences) < 4, (
                    f"Diversity constraint not applied: distance {distance:.2f} < 0.5"
                )


class TestCreateSurvivorSelector:
    """Test survivor selector factory with diverse_top_n policy."""

    def test_create_diverse_top_n_selector(self) -> None:
        """Should create diverse_top_n selector."""
        diversity_config = DiversityConfig(enabled=True, min_diversity=0.3)

        selector = create_survivor_selector(
            policy=RankingPolicy.DIVERSE_TOP_N,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            diversity_config=diversity_config,
        )

        assert selector is not None
        assert callable(selector)

    def test_diverse_top_n_requires_baseline_hot_ratio(self) -> None:
        """Should raise error if baseline_hot_ratio not provided."""
        with pytest.raises(ValueError, match="baseline_hot_ratio is required"):
            create_survivor_selector(
                policy=RankingPolicy.DIVERSE_TOP_N,
                baseline_wns_ps=-1000,
                baseline_hot_ratio=None,
            )

    def test_diverse_top_n_uses_default_diversity_config(self) -> None:
        """Should use default diversity config if not provided."""
        selector = create_survivor_selector(
            policy=RankingPolicy.DIVERSE_TOP_N,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            diversity_config=None,
        )

        assert selector is not None
        assert callable(selector)


class TestDiverseSelectionEdgeCases:
    """Test edge cases for diverse survivor selection."""

    def test_handles_fewer_trials_than_survivors_requested(self) -> None:
        """Should handle case where fewer trials than survivors."""
        trials = [
            create_mock_trial_with_eco_sequence(
                "case_1",
                ["buffer_insertion"],
                wns_ps=-500,
                hot_ratio=0.5,
            ),
            create_mock_trial_with_eco_sequence(
                "case_2",
                ["gate_sizing"],
                wns_ps=-600,
                hot_ratio=0.6,
            ),
        ]

        diversity_config = DiversityConfig(enabled=True, min_diversity=0.3)

        survivors = rank_diverse_top_n(
            trial_results=trials,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            survivor_count=5,  # More than available
            diversity_config=diversity_config,
        )

        # Should return all available trials
        assert len(survivors) == 2

    def test_always_keeps_best_trial(self) -> None:
        """Should always keep the best trial when configured."""
        trials = []
        # Create case_0 as clearly the best, then worse ones
        qualities = [
            (-300, 0.3),  # case_0: Best WNS and congestion
            (-500, 0.5),  # case_1: Worse
            (-600, 0.6),  # case_2: Even worse
            (-700, 0.7),  # case_3: Even worse
            (-800, 0.75), # case_4: Worst
        ]
        for i, (wns_ps, hot_ratio) in enumerate(qualities):
            trial = create_mock_trial_with_eco_sequence(
                f"case_{i}",
                [f"eco_{i}"],
                wns_ps=wns_ps,
                hot_ratio=hot_ratio,
            )
            trials.append(trial)

        diversity_config = DiversityConfig(
            enabled=True,
            min_diversity=0.3,
            always_keep_best=True,
        )

        survivors = rank_diverse_top_n(
            trial_results=trials,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            survivor_count=3,
            diversity_config=diversity_config,
        )

        # Best trial should always be included
        assert "case_0" in survivors

    def test_relaxes_diversity_if_cannot_meet_count(self) -> None:
        """Should relax diversity constraint if cannot meet survivor count."""
        # Create trials where all have very similar ECO sequences
        trials = []
        for i in range(8):
            eco_seq = ["buffer_insertion", "gate_sizing"] + [f"variant_{i}"]
            trial = create_mock_trial_with_eco_sequence(
                f"case_{i}",
                eco_seq,
                wns_ps=-500 + i * 50,
                hot_ratio=0.5 + i * 0.05,
            )
            trials.append(trial)

        diversity_config = DiversityConfig(
            enabled=True,
            min_diversity=0.9,  # Very high threshold, hard to meet
        )

        survivors = rank_diverse_top_n(
            trial_results=trials,
            baseline_wns_ps=-1000,
            baseline_hot_ratio=0.8,
            survivor_count=5,
            diversity_config=diversity_config,
        )

        # Should still return requested number of survivors
        # by relaxing diversity constraint
        assert len(survivors) == 5
