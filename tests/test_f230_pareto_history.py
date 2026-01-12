"""Tests for F230: Track Pareto history in pareto_history.json.

Feature: F230 - Track Pareto history in pareto_history.json
Priority: medium
Category: functional

Steps:
1. Run study with Pareto tracking
2. Verify pareto_history.json is created
3. Verify each stage has Pareto frontier snapshot
4. Verify non-dominated solutions are marked per stage
5. Verify history enables evolution visualization
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.controller.pareto import (
    ObjectiveSpec,
    ParetoFrontier,
    ParetoTrial,
    compute_pareto_frontier,
)
from src.controller.pareto_history import (
    ParetoHistory,
    ParetoStageSnapshot,
    create_pareto_history_from_stage_frontiers,
    load_pareto_history,
    write_pareto_history,
)
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


def create_mock_trial(
    case_name: str,
    wns_ps: float,
    hot_ratio: float,
    tmp_path: Path,
) -> TrialResult:
    """Helper to create mock trial with metrics."""
    metrics = {
        "timing": {"wns_ps": wns_ps},
        "congestion": {"hot_ratio": hot_ratio},
    }

    trial_dir = tmp_path / case_name
    trial_dir.mkdir(exist_ok=True)

    metrics_json = trial_dir / "metrics.json"
    metrics_json.write_text(json.dumps(metrics))

    artifacts = TrialArtifacts(
        trial_dir=trial_dir,
        metrics_json=metrics_json,
    )

    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
        script_path="/tmp/test.tcl",
        snapshot_dir=tmp_path,
    )

    return TrialResult(
        config=config,
        success=True,
        return_code=0,
        runtime_seconds=10.0,
        artifacts=artifacts,
    )


@pytest.fixture
def objectives() -> list[ObjectiveSpec]:
    """Standard objectives for testing."""
    return [
        ObjectiveSpec(
            name="wns_ps",
            metric_path=["timing", "wns_ps"],
            minimize=False,  # Maximize WNS
        ),
        ObjectiveSpec(
            name="hot_ratio",
            metric_path=["congestion", "hot_ratio"],
            minimize=True,  # Minimize congestion
        ),
    ]


@pytest.fixture
def stage_frontiers(tmp_path: Path, objectives: list[ObjectiveSpec]) -> list[ParetoFrontier]:
    """Create mock stage frontiers for testing."""
    frontiers = []

    # Stage 0: Initial trials
    stage0_trials = [
        create_mock_trial("s0_case1", wns_ps=-100, hot_ratio=0.5, tmp_path=tmp_path),
        create_mock_trial("s0_case2", wns_ps=-50, hot_ratio=0.8, tmp_path=tmp_path),
        create_mock_trial("s0_case3", wns_ps=-75, hot_ratio=0.6, tmp_path=tmp_path),
    ]
    frontiers.append(compute_pareto_frontier(stage0_trials, objectives))

    # Stage 1: Some improvement
    stage1_trials = [
        create_mock_trial("s1_case1", wns_ps=-80, hot_ratio=0.4, tmp_path=tmp_path),
        create_mock_trial("s1_case2", wns_ps=-40, hot_ratio=0.7, tmp_path=tmp_path),
        create_mock_trial("s1_case3", wns_ps=-60, hot_ratio=0.5, tmp_path=tmp_path),
    ]
    frontiers.append(compute_pareto_frontier(stage1_trials, objectives))

    # Stage 2: Further improvement
    stage2_trials = [
        create_mock_trial("s2_case1", wns_ps=-50, hot_ratio=0.3, tmp_path=tmp_path),
        create_mock_trial("s2_case2", wns_ps=-30, hot_ratio=0.5, tmp_path=tmp_path),
        create_mock_trial("s2_case3", wns_ps=-40, hot_ratio=0.4, tmp_path=tmp_path),
    ]
    frontiers.append(compute_pareto_frontier(stage2_trials, objectives))

    return frontiers


class TestParetoHistoryCreation:
    """Test Pareto history creation and tracking."""

    def test_create_empty_history(self) -> None:
        """Test creating an empty history."""
        history = ParetoHistory(study_name="test_study")

        assert history.study_name == "test_study"
        assert history.get_stage_count() == 0
        assert history.stages == []

    def test_add_stage_snapshot(
        self, tmp_path: Path, objectives: list[ObjectiveSpec]
    ) -> None:
        """Test adding a stage snapshot."""
        history = ParetoHistory(study_name="test_study")

        # Create a simple frontier
        trials = [
            create_mock_trial("case1", wns_ps=-100, hot_ratio=0.5, tmp_path=tmp_path),
            create_mock_trial("case2", wns_ps=-50, hot_ratio=0.8, tmp_path=tmp_path),
        ]
        frontier = compute_pareto_frontier(trials, objectives)

        # Add snapshot
        history.add_stage_snapshot(
            stage_name="floorplan",
            stage_index=0,
            pareto_frontier=frontier,
        )

        assert history.get_stage_count() == 1
        snapshot = history.stages[0]
        assert snapshot.stage_name == "floorplan"
        assert snapshot.stage_index == 0
        assert snapshot.total_trials == 2
        assert len(snapshot.pareto_optimal_cases) > 0

    def test_create_from_stage_frontiers(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test creating history from stage frontiers."""
        stage_names = ["synth", "floorplan", "place"]

        history = create_pareto_history_from_stage_frontiers(
            study_name="nangate45_test",
            stage_names=stage_names,
            stage_frontiers=stage_frontiers,
        )

        assert history.study_name == "nangate45_test"
        assert history.get_stage_count() == 3
        assert [s.stage_name for s in history.stages] == stage_names


class TestParetoHistorySerialization:
    """Test serialization and deserialization of Pareto history."""

    def test_snapshot_to_dict(
        self, tmp_path: Path, objectives: list[ObjectiveSpec]
    ) -> None:
        """Test snapshot serialization."""
        trials = [
            create_mock_trial("case1", wns_ps=-100, hot_ratio=0.5, tmp_path=tmp_path),
            create_mock_trial("case2", wns_ps=-50, hot_ratio=0.8, tmp_path=tmp_path),
        ]
        frontier = compute_pareto_frontier(trials, objectives)

        history = ParetoHistory(study_name="test")
        history.add_stage_snapshot("place", 0, frontier)

        snapshot_dict = history.stages[0].to_dict()

        assert snapshot_dict["stage_name"] == "place"
        assert snapshot_dict["stage_index"] == 0
        assert "pareto_optimal_count" in snapshot_dict
        assert "dominated_count" in snapshot_dict
        assert "total_trials" in snapshot_dict
        assert "pareto_optimal_cases" in snapshot_dict
        assert "objectives" in snapshot_dict
        assert "frontier_data" in snapshot_dict

    def test_history_to_dict(self, stage_frontiers: list[ParetoFrontier]) -> None:
        """Test history serialization."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="test_study",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        history_dict = history.to_dict()

        assert history_dict["study_name"] == "test_study"
        assert history_dict["total_stages"] == 3
        assert len(history_dict["stages"]) == 3
        assert "evolution_summary" in history_dict
        assert "pareto_counts_per_stage" in history_dict["evolution_summary"]
        assert "total_trials_per_stage" in history_dict["evolution_summary"]


class TestParetoHistoryIO:
    """Test reading and writing Pareto history files."""

    def test_write_pareto_history(
        self, tmp_path: Path, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test writing history to JSON file."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="nangate45_test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        output_path = tmp_path / "pareto_history.json"
        write_pareto_history(history, output_path)

        assert output_path.exists()

        # Verify JSON is valid
        with open(output_path) as f:
            data = json.load(f)

        assert data["study_name"] == "nangate45_test"
        assert data["total_stages"] == 3

    def test_load_pareto_history(
        self, tmp_path: Path, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test loading history from JSON file."""
        # Write history
        original_history = create_pareto_history_from_stage_frontiers(
            study_name="nangate45_test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        output_path = tmp_path / "pareto_history.json"
        write_pareto_history(original_history, output_path)

        # Load history
        loaded_history = load_pareto_history(output_path)

        assert loaded_history.study_name == original_history.study_name
        assert loaded_history.get_stage_count() == original_history.get_stage_count()
        assert len(loaded_history.stages) == len(original_history.stages)

    def test_load_nonexistent_file(self, tmp_path: Path) -> None:
        """Test loading from nonexistent file raises error."""
        nonexistent_path = tmp_path / "missing.json"

        with pytest.raises(FileNotFoundError):
            load_pareto_history(nonexistent_path)

    def test_load_invalid_json(self, tmp_path: Path) -> None:
        """Test loading invalid JSON raises error."""
        invalid_path = tmp_path / "invalid.json"
        invalid_path.write_text('{"invalid": "format"}')

        with pytest.raises(ValueError, match="Invalid pareto_history.json format"):
            load_pareto_history(invalid_path)


class TestParetoEvolution:
    """Test Pareto evolution tracking."""

    def test_get_pareto_evolution(self, stage_frontiers: list[ParetoFrontier]) -> None:
        """Test extracting Pareto evolution across stages."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        evolution = history.get_pareto_evolution()

        assert len(evolution) == 3
        for stage_pareto_cases in evolution:
            assert isinstance(stage_pareto_cases, list)
            assert all(isinstance(case, str) for case in stage_pareto_cases)

    def test_get_stage_snapshot(self, stage_frontiers: list[ParetoFrontier]) -> None:
        """Test retrieving specific stage snapshot."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        # Get stage 1
        snapshot = history.get_stage_snapshot(1)
        assert snapshot is not None
        assert snapshot.stage_name == "floorplan"
        assert snapshot.stage_index == 1

        # Get nonexistent stage
        missing = history.get_stage_snapshot(99)
        assert missing is None


class TestF230FeatureSteps:
    """Test F230 feature requirements."""

    def test_step_1_run_study_with_pareto_tracking(
        self, tmp_path: Path, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 1: Run study with Pareto tracking."""
        # Simulate running a study and tracking Pareto frontiers
        history = ParetoHistory(study_name="nangate45_test")

        for idx, frontier in enumerate(stage_frontiers):
            stage_name = ["synth", "floorplan", "place"][idx]
            history.add_stage_snapshot(stage_name, idx, frontier)

        assert history.get_stage_count() == 3

    def test_step_2_verify_pareto_history_json_is_created(
        self, tmp_path: Path, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 2: Verify pareto_history.json is created."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="nangate45_test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        output_path = tmp_path / "artifacts" / "pareto_history.json"
        write_pareto_history(history, output_path)

        # Verify file exists
        assert output_path.exists()
        assert output_path.name == "pareto_history.json"

    def test_step_3_verify_each_stage_has_pareto_frontier_snapshot(
        self, tmp_path: Path, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 3: Verify each stage has Pareto frontier snapshot."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="nangate45_test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        output_path = tmp_path / "pareto_history.json"
        write_pareto_history(history, output_path)

        # Load and verify
        loaded = load_pareto_history(output_path)

        # Each stage should have a snapshot
        assert loaded.get_stage_count() == 3

        for idx in range(3):
            snapshot = loaded.get_stage_snapshot(idx)
            assert snapshot is not None
            assert snapshot.stage_index == idx
            assert snapshot.stage_name in ["synth", "floorplan", "place"]

    def test_step_4_verify_non_dominated_solutions_marked_per_stage(
        self, tmp_path: Path, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 4: Verify non-dominated solutions are marked per stage."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="nangate45_test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        # Check each stage has non-dominated solutions identified
        for snapshot in history.stages:
            assert snapshot.pareto_optimal_count > 0
            assert len(snapshot.pareto_optimal_cases) > 0

            # Verify frontier data contains full Pareto analysis
            frontier_data = snapshot.frontier_data
            assert "pareto_optimal_trials" in frontier_data
            assert "dominated_trials" in frontier_data
            assert len(frontier_data["pareto_optimal_trials"]) > 0

    def test_step_5_verify_history_enables_evolution_visualization(
        self, tmp_path: Path, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Step 5: Verify history enables evolution visualization."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="nangate45_test",
            stage_names=["synth", "floorplan", "place"],
            stage_frontiers=stage_frontiers,
        )

        # Get evolution data
        evolution = history.get_pareto_evolution()

        # Evolution should have data for each stage
        assert len(evolution) == 3

        # Each stage should have Pareto-optimal cases
        for stage_cases in evolution:
            assert len(stage_cases) > 0

        # Verify summary data supports visualization
        history_dict = history.to_dict()
        summary = history_dict["evolution_summary"]

        assert len(summary["pareto_counts_per_stage"]) == 3
        assert len(summary["total_trials_per_stage"]) == 3
        assert all(count > 0 for count in summary["pareto_counts_per_stage"])
        assert all(count > 0 for count in summary["total_trials_per_stage"])


class TestParetoHistoryEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_stage_frontiers(self) -> None:
        """Test handling empty stage frontiers list."""
        history = create_pareto_history_from_stage_frontiers(
            study_name="test",
            stage_names=[],
            stage_frontiers=[],
        )

        assert history.get_stage_count() == 0
        assert history.get_pareto_evolution() == []

    def test_mismatched_stage_names_and_frontiers(
        self, stage_frontiers: list[ParetoFrontier]
    ) -> None:
        """Test error when stage names and frontiers don't match."""
        with pytest.raises(ValueError, match="Mismatched lengths"):
            create_pareto_history_from_stage_frontiers(
                study_name="test",
                stage_names=["synth", "floorplan"],  # Only 2 names
                stage_frontiers=stage_frontiers,  # 3 frontiers
            )

    def test_single_stage_history(
        self, tmp_path: Path, objectives: list[ObjectiveSpec]
    ) -> None:
        """Test history with single stage."""
        trials = [
            create_mock_trial("case1", wns_ps=-100, hot_ratio=0.5, tmp_path=tmp_path),
            create_mock_trial("case2", wns_ps=-50, hot_ratio=0.8, tmp_path=tmp_path),
        ]
        frontier = compute_pareto_frontier(trials, objectives)

        history = create_pareto_history_from_stage_frontiers(
            study_name="test",
            stage_names=["place"],
            stage_frontiers=[frontier],
        )

        assert history.get_stage_count() == 1
        evolution = history.get_pareto_evolution()
        assert len(evolution) == 1

    def test_history_with_no_pareto_optimal_trials(
        self, tmp_path: Path, objectives: list[ObjectiveSpec]
    ) -> None:
        """Test history when a stage has no Pareto-optimal trials."""
        # Create empty frontier (no successful trials)
        empty_frontier = compute_pareto_frontier([], objectives)

        history = create_pareto_history_from_stage_frontiers(
            study_name="test",
            stage_names=["place"],
            stage_frontiers=[empty_frontier],
        )

        assert history.get_stage_count() == 1
        snapshot = history.stages[0]
        assert snapshot.pareto_optimal_count == 0
        assert snapshot.pareto_optimal_cases == []
