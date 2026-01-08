"""Tests for multi-stage Study execution with sequential stage progression."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StageResult, StudyExecutor, StudyResult
from src.controller.study import create_study_config
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig
from src.trial_runner.trial import TrialConfig, TrialResult


class TestStudyExecutor:
    """Test Study execution framework."""

    def test_create_study_executor(self) -> None:
        """Test creating a StudyExecutor with basic config."""
        config = create_study_config(
            name="test_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
        )

        executor = StudyExecutor(config=config)

        assert executor.config.name == "test_study"
        assert executor.base_case.case_name == "nangate45_base"
        assert len(executor.case_graph.cases) == 1  # Base case added

    def test_single_stage_execution(self) -> None:
        """Test executing a Study with a single stage."""
        config = create_study_config(
            name="single_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir)
            result = executor.execute()

            assert result.study_name == "single_stage_study"
            assert result.total_stages == 1
            assert result.stages_completed == 1
            assert not result.aborted
            assert result.abort_reason is None
            assert len(result.stage_results) == 1

    def test_multi_stage_sequential_execution(self) -> None:
        """Test that stages execute sequentially, not in parallel."""
        stages = [
            StageConfig(
                name="exploration",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL, ECOClass.PLACEMENT_LOCAL],
            ),
            StageConfig(
                name="refinement",
                execution_mode=ExecutionMode.STA_CONGESTION,
                trial_budget=5,
                survivor_count=3,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="closure",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="three_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir)
            result = executor.execute()

            # Verify all three stages executed
            assert result.total_stages == 3
            assert result.stages_completed == 3
            assert len(result.stage_results) == 3

            # Verify stage indices are sequential
            for i, stage_result in enumerate(result.stage_results):
                assert stage_result.stage_index == i

            # Verify stage names match configuration
            assert result.stage_results[0].stage_name == "exploration"
            assert result.stage_results[1].stage_name == "refinement"
            assert result.stage_results[2].stage_name == "closure"

    def test_trial_budget_enforcement(self) -> None:
        """Test that trial budget is enforced per stage."""
        config = create_study_config(
            name="budget_test_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir)
            result = executor.execute()

            # Verify exactly trial_budget trials were executed
            stage_result = result.stage_results[0]
            assert stage_result.trials_executed == 10

    def test_survivor_count_limits(self) -> None:
        """Test that survivor count is enforced."""
        config = create_study_config(
            name="survivor_test_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir)
            result = executor.execute()

            # Verify exactly survivor_count survivors selected
            stage_result = result.stage_results[0]
            assert len(stage_result.survivors) == 3

    def test_only_survivors_advance_to_next_stage(self) -> None:
        """Test that only survivors advance to the next stage."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=2,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="survivor_progression_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir)
            result = executor.execute()

            # Stage 0 should have 5 survivors
            assert len(result.stage_results[0].survivors) == 5

            # Stage 1 should have 2 survivors (from the 5 that advanced)
            assert len(result.stage_results[1].survivors) == 2

            # Final survivors should be stage 1 survivors
            assert result.final_survivors == result.stage_results[1].survivors

    def test_stage_with_different_eco_classes(self) -> None:
        """Test that different ECO classes can be allowed per stage."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=3,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL, ECOClass.PLACEMENT_LOCAL],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],  # More restrictive
            ),
        ]

        config = create_study_config(
            name="eco_class_progression_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        executor = StudyExecutor(config=config)

        # Verify stage configurations
        assert len(executor.config.stages[0].allowed_eco_classes) == 2
        assert len(executor.config.stages[1].allowed_eco_classes) == 1


class TestStageResult:
    """Test StageResult data structure."""

    def test_stage_result_creation(self) -> None:
        """Test creating a StageResult."""
        result = StageResult(
            stage_index=0,
            stage_name="exploration",
            trials_executed=10,
            survivors=["nangate45_0_0", "nangate45_0_1", "nangate45_0_2"],
            total_runtime_seconds=45.5,
        )

        assert result.stage_index == 0
        assert result.stage_name == "exploration"
        assert result.trials_executed == 10
        assert len(result.survivors) == 3
        assert result.total_runtime_seconds == 45.5

    def test_stage_result_to_dict(self) -> None:
        """Test serializing StageResult to dictionary."""
        result = StageResult(
            stage_index=1,
            stage_name="refinement",
            trials_executed=5,
            survivors=["nangate45_1_0"],
            total_runtime_seconds=30.0,
            metadata={"execution_mode": "sta_only"},
        )

        result_dict = result.to_dict()

        assert result_dict["stage_index"] == 1
        assert result_dict["stage_name"] == "refinement"
        assert result_dict["trials_executed"] == 5
        assert result_dict["survivors"] == ["nangate45_1_0"]
        assert result_dict["metadata"]["execution_mode"] == "sta_only"

        # Verify JSON serializable
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)


class TestStudyResult:
    """Test StudyResult data structure."""

    def test_study_result_creation(self) -> None:
        """Test creating a StudyResult."""
        result = StudyResult(
            study_name="test_study",
            total_stages=3,
            stages_completed=3,
            total_runtime_seconds=120.5,
            final_survivors=["nangate45_2_0"],
        )

        assert result.study_name == "test_study"
        assert result.total_stages == 3
        assert result.stages_completed == 3
        assert result.total_runtime_seconds == 120.5
        assert len(result.final_survivors) == 1
        assert not result.aborted

    def test_study_result_aborted(self) -> None:
        """Test StudyResult with abortion."""
        result = StudyResult(
            study_name="aborted_study",
            total_stages=3,
            stages_completed=1,
            total_runtime_seconds=10.0,
            final_survivors=[],
            aborted=True,
            abort_reason="Stage 1 produced no survivors",
        )

        assert result.aborted
        assert result.abort_reason == "Stage 1 produced no survivors"
        assert result.stages_completed == 1
        assert len(result.final_survivors) == 0

    def test_study_result_to_dict(self) -> None:
        """Test serializing StudyResult to dictionary."""
        stage_result = StageResult(
            stage_index=0,
            stage_name="stage_0",
            trials_executed=5,
            survivors=["case_0_0"],
            total_runtime_seconds=20.0,
        )

        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=20.5,
            stage_results=[stage_result],
            final_survivors=["case_0_0"],
        )

        result_dict = result.to_dict()

        assert result_dict["study_name"] == "test_study"
        assert result_dict["total_stages"] == 1
        assert len(result_dict["stage_results"]) == 1
        assert result_dict["final_survivors"] == ["case_0_0"]

        # Verify JSON serializable
        json_str = json.dumps(result_dict)
        assert isinstance(json_str, str)


class TestSurvivorSelection:
    """Test survivor selection logic."""

    def test_default_survivor_selector(self) -> None:
        """Test default survivor selection based on success."""
        config = create_study_config(
            name="selector_test",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
        )

        executor = StudyExecutor(config=config)

        # Create mock trial results
        trial_results = [
            TrialResult(
                config=TrialConfig(
                    study_name="test",
                    case_name="case_0",
                    stage_index=0,
                    trial_index=0,
                    script_path="test.tcl",
                ),
                success=True,
                return_code=0,
                runtime_seconds=10.0,
                artifacts=None,  # type: ignore
            ),
            TrialResult(
                config=TrialConfig(
                    study_name="test",
                    case_name="case_1",
                    stage_index=0,
                    trial_index=1,
                    script_path="test.tcl",
                ),
                success=False,
                return_code=1,
                runtime_seconds=5.0,
                artifacts=None,  # type: ignore
            ),
            TrialResult(
                config=TrialConfig(
                    study_name="test",
                    case_name="case_2",
                    stage_index=0,
                    trial_index=2,
                    script_path="test.tcl",
                ),
                success=True,
                return_code=0,
                runtime_seconds=12.0,
                artifacts=None,  # type: ignore
            ),
        ]

        # Select 2 survivors
        survivors = executor._default_survivor_selector(trial_results, survivor_count=2)

        # Should select only successful trials
        assert len(survivors) == 2
        assert "case_0" in survivors
        assert "case_2" in survivors
        assert "case_1" not in survivors  # Failed trial

    def test_survivor_selector_with_no_successful_trials(self) -> None:
        """Test survivor selection when all trials fail."""
        config = create_study_config(
            name="all_fail_test",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
        )

        executor = StudyExecutor(config=config)

        # All trials failed
        trial_results = [
            TrialResult(
                config=TrialConfig(
                    study_name="test",
                    case_name=f"case_{i}",
                    stage_index=0,
                    trial_index=i,
                    script_path="test.tcl",
                ),
                success=False,
                return_code=1,
                runtime_seconds=5.0,
                artifacts=None,  # type: ignore
            )
            for i in range(5)
        ]

        survivors = executor._default_survivor_selector(trial_results, survivor_count=3)

        # No survivors if all failed
        assert len(survivors) == 0

    def test_custom_survivor_selector(self) -> None:
        """Test using a custom survivor selection function."""

        def custom_selector(trial_results: list[TrialResult], survivor_count: int) -> list[str]:
            """Custom selector: pick trials with longest runtime."""
            sorted_trials = sorted(trial_results, key=lambda t: t.runtime_seconds, reverse=True)
            return [t.config.case_name for t in sorted_trials[:survivor_count]]

        config = create_study_config(
            name="custom_selector_test",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
        )

        executor = StudyExecutor(config=config, survivor_selector=custom_selector)

        assert executor.survivor_selector == custom_selector


class TestStageAbortion:
    """Test stage abortion conditions."""

    def test_study_aborts_when_stage_produces_no_survivors(self) -> None:
        """Test that Study aborts if a stage produces no survivors."""

        # Custom survivor selector that returns no survivors
        def no_survivors_selector(trial_results: list[TrialResult], survivor_count: int) -> list[str]:
            return []  # Always return empty list

        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=3,  # Request 3 but selector will return 0
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="abort_test_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir, survivor_selector=no_survivors_selector)
            result = executor.execute()

            # Should abort after stage 0
            assert result.aborted
            assert result.stages_completed == 1
            assert "no survivors" in result.abort_reason.lower()
            assert len(result.final_survivors) == 0

    def test_downstream_stages_not_executed_after_abort(self) -> None:
        """Test that downstream stages are not executed after abortion."""

        # Custom survivor selector that returns no survivors
        def no_survivors_selector(trial_results: list[TrialResult], survivor_count: int) -> list[str]:
            return []  # Always return empty list

        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=3,  # Request 3 but selector will return 0
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="stage_2",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=2,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="downstream_abort_test",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir, survivor_selector=no_survivors_selector)
            result = executor.execute()

            # Only stage 0 should have executed
            assert result.stages_completed == 1
            assert len(result.stage_results) == 1
            assert result.aborted


class TestCaseGraphProgression:
    """Test that case graph is built correctly across stages."""

    def test_case_graph_tracks_lineage(self) -> None:
        """Test that case graph maintains lineage across stages."""
        config = create_study_config(
            name="lineage_test",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage_1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(config=config, artifacts_root=tmpdir)
            result = executor.execute()

            # Verify case graph structure
            # Should have: 1 base case + 2 stage 0 cases + 1 stage 1 case (from survivors)
            total_cases = len(executor.case_graph.cases)
            assert total_cases >= 1  # At least base case

            # Verify base case exists
            base_case = executor.case_graph.get_case("nangate45_base_0_0")
            assert base_case is not None
            assert base_case.case_name == "nangate45_base"
            assert base_case.is_base_case
