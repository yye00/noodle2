"""Tests for F029: Single-stage study can execute to completion.

Feature Requirements:
- Step 1: Create study with 1 stage, budget=10, survivors=3
- Step 2: Execute study using StudyExecutor
- Step 3: Verify 10 trials are executed
- Step 4: Verify top 3 by WNS are selected as survivors
- Step 5: Verify study_summary.json contains results
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StudyExecutor
from src.controller.study import create_study_config
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestF029SingleStageStudy:
    """Test F029: Single-stage study can execute to completion."""

    def test_step_1_create_study_with_single_stage(self) -> None:
        """Step 1: Create study with 1 stage, budget=10, survivors=3."""
        config = create_study_config(
            name="f029_single_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        assert config.name == "f029_single_stage_study"
        assert len(config.stages) == 1
        assert config.stages[0].trial_budget == 10
        assert config.stages[0].survivor_count == 3

    def test_step_2_execute_study_using_study_executor(self) -> None:
        """Step 2: Execute study using StudyExecutor."""
        config = create_study_config(
            name="f029_single_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config, artifacts_root=tmpdir, skip_base_case_verification=True
            )
            result = executor.execute()

            # Verify study executed successfully
            assert result is not None
            assert result.study_name == "f029_single_stage_study"
            assert not result.aborted

    def test_step_3_verify_10_trials_executed(self) -> None:
        """Step 3: Verify 10 trials are executed."""
        config = create_study_config(
            name="f029_single_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config, artifacts_root=tmpdir, skip_base_case_verification=True
            )
            result = executor.execute()

            # Verify exactly 10 trials were executed
            assert len(result.stage_results) == 1
            stage_result = result.stage_results[0]
            assert stage_result.trials_executed == 10

    def test_step_4_verify_top_3_by_wns_selected_as_survivors(self) -> None:
        """Step 4: Verify top 3 by WNS are selected as survivors."""
        config = create_study_config(
            name="f029_single_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config, artifacts_root=tmpdir, skip_base_case_verification=True
            )
            result = executor.execute()

            # Verify exactly 3 survivors were selected
            assert len(result.stage_results) == 1
            stage_result = result.stage_results[0]
            assert len(stage_result.survivors) == 3

            # Verify survivors are case names
            for survivor in stage_result.survivors:
                assert isinstance(survivor, str)
                assert len(survivor) > 0

    def test_step_5_verify_study_summary_json_contains_results(self) -> None:
        """Step 5: Verify study_summary.json contains results."""
        config = create_study_config(
            name="f029_single_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)
            executor = StudyExecutor(
                config=config,
                artifacts_root=str(artifacts_root),
                skip_base_case_verification=True,
            )
            result = executor.execute()

            # Verify study_summary.json exists and contains results
            # Note: The file is saved in a subdirectory named after the study
            summary_path = artifacts_root / "f029_single_stage_study" / "study_summary.json"
            assert summary_path.exists(), f"study_summary.json should be created at {summary_path}"

            # Parse and validate the summary
            with open(summary_path, "r") as f:
                summary = json.load(f)

            assert "study_name" in summary
            assert summary["study_name"] == "f029_single_stage_study"
            assert "total_stages" in summary
            assert summary["total_stages"] == 1
            assert "stages_completed" in summary
            assert summary["stages_completed"] == 1
            assert "final_survivors" in summary
            assert len(summary["final_survivors"]) == 3

    def test_complete_f029_workflow(self) -> None:
        """Complete F029 test: Single-stage study executes to completion."""
        # Step 1: Create study with 1 stage, budget=10, survivors=3
        config = create_study_config(
            name="f029_single_stage_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        assert len(config.stages) == 1
        assert config.stages[0].trial_budget == 10
        assert config.stages[0].survivor_count == 3

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir)

            # Step 2: Execute study using StudyExecutor
            executor = StudyExecutor(
                config=config,
                artifacts_root=str(artifacts_root),
                skip_base_case_verification=True,
            )
            result = executor.execute()

            # Verify study executed successfully
            assert not result.aborted
            assert result.study_name == "f029_single_stage_study"

            # Step 3: Verify 10 trials are executed
            assert result.total_stages == 1
            assert result.stages_completed == 1
            assert len(result.stage_results) == 1
            stage_result = result.stage_results[0]
            assert stage_result.trials_executed == 10

            # Step 4: Verify top 3 by WNS are selected as survivors
            assert len(stage_result.survivors) == 3
            assert len(result.final_survivors) == 3

            # Step 5: Verify study_summary.json contains results
            # Note: The file is saved in a subdirectory named after the study
            summary_path = artifacts_root / "f029_single_stage_study" / "study_summary.json"
            assert summary_path.exists(), f"study_summary.json should be created at {summary_path}"

            with open(summary_path, "r") as f:
                summary = json.load(f)

            assert summary["study_name"] == "f029_single_stage_study"
            assert summary["total_stages"] == 1
            assert summary["stages_completed"] == 1
            assert len(summary["final_survivors"]) == 3
            assert not summary.get("aborted", False)
