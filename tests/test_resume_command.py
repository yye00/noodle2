"""Tests for F051 and F052: Study resume functionality.

F051: Study can resume from latest checkpoint
F052: Study can resume from specific checkpoint file

These tests validate the 'noodle2 resume' CLI command works correctly.
"""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.controller.study_resumption import (
    StudyCheckpoint,
    create_stage_checkpoint,
    initialize_checkpoint,
    save_checkpoint,
    update_checkpoint_after_stage,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_workspace():
    """Create temporary workspace with standard directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)

        # Create standard directories
        artifacts_dir = workspace / "artifacts"
        studies_dir = workspace / "studies"
        artifacts_dir.mkdir()
        studies_dir.mkdir()

        yield workspace


@pytest.fixture
def sample_study_config():
    """Sample study configuration for testing."""
    return {
        "name": "test_study",
        "pdk": "nangate45",
        "safety_domain": "sandbox",
        "stages": [
            {
                "stage_index": 0,
                "stage_name": "baseline",
                "trial_budget": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "refinement",
                "trial_budget": 8,
                "survivor_count": 3,
            },
            {
                "stage_index": 2,
                "stage_name": "final",
                "trial_budget": 5,
                "survivor_count": 1,
            },
        ],
    }


@pytest.fixture
def partial_checkpoint():
    """Create a checkpoint with stage 0 completed."""
    checkpoint = initialize_checkpoint("test_study")

    # Add stage 0 completion
    stage0 = create_stage_checkpoint(
        stage_index=0,
        stage_name="baseline",
        survivor_case_ids=["case_1", "case_2", "case_3"],
        trials_completed=10,
        trials_failed=0,
    )

    checkpoint = update_checkpoint_after_stage(checkpoint, stage0)
    return checkpoint


@pytest.fixture
def multi_stage_checkpoint():
    """Create a checkpoint with stages 0 and 1 completed."""
    checkpoint = initialize_checkpoint("test_study")

    # Add stage 0
    stage0 = create_stage_checkpoint(
        stage_index=0,
        stage_name="baseline",
        survivor_case_ids=["case_1", "case_2", "case_3"],
        trials_completed=10,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage0)

    # Add stage 1
    stage1 = create_stage_checkpoint(
        stage_index=1,
        stage_name="refinement",
        survivor_case_ids=["case_1", "case_3"],
        trials_completed=8,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage1)

    return checkpoint


def create_study_yaml(path: Path, config: dict[str, Any]) -> None:
    """Create a minimal study YAML configuration."""
    yaml_content = f"""study:
  name: {config['name']}
  pdk: {config['pdk']}
  safety_domain: {config['safety_domain']}

stages:
"""
    for stage in config['stages']:
        yaml_content += f"""  - stage_index: {stage['stage_index']}
    stage_name: {stage['stage_name']}
    trial_budget: {stage['trial_budget']}
    survivor_count: {stage['survivor_count']}
"""

    path.write_text(yaml_content)


# ============================================================================
# F051: Resume from latest checkpoint
# ============================================================================


class TestF051ResumeFromLatest:
    """Test F051: Study can resume from latest checkpoint.

    Steps:
    1. Run study partway through (complete stage 0)
    2. Interrupt study
    3. Resume using 'noodle2 resume --study <name>'
    4. Verify study continues from stage 1 (not from beginning)
    5. Verify previous stage results are preserved
    """

    def test_step_1_and_2_create_interrupted_study(
        self, temp_workspace, sample_study_config, partial_checkpoint
    ):
        """Step 1-2: Create study with checkpoint after stage 0."""
        # Create study artifacts directory
        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)

        # Save checkpoint (simulates interruption after stage 0)
        checkpoint_path = save_checkpoint(partial_checkpoint, study_dir)

        # Verify checkpoint exists
        assert checkpoint_path.exists()
        assert checkpoint_path.name == "study_checkpoint.json"

        # Verify checkpoint content
        with open(checkpoint_path) as f:
            data = json.load(f)

        assert data["study_name"] == "test_study"
        assert data["last_completed_stage_index"] == 0
        assert len(data["completed_stages"]) == 1
        assert data["completed_stages"][0]["stage_name"] == "baseline"

    def test_step_3_resume_command_finds_latest_checkpoint(
        self, temp_workspace, sample_study_config, partial_checkpoint
    ):
        """Step 3: Resume command can locate latest checkpoint."""
        from src.controller.study_resumption import find_checkpoint

        # Setup: Create study with checkpoint
        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)
        save_checkpoint(partial_checkpoint, study_dir)

        # Test: find_checkpoint locates the file
        found_path = find_checkpoint(study_dir)

        assert found_path is not None
        assert found_path.exists()
        assert found_path.name == "study_checkpoint.json"

    def test_step_3_resume_command_parses_arguments(self):
        """Step 3: Resume command accepts correct arguments."""
        from src.cli import create_parser

        parser = create_parser()

        # Test with study name only (uses latest checkpoint)
        args = parser.parse_args(["resume", "--study", "test_study"])

        assert args.command == "resume"
        assert args.study == "test_study"
        assert args.checkpoint is None  # Latest checkpoint
        assert args.ray_address == "auto"

    @patch('src.controller.executor.StudyExecutor')
    @patch('src.controller.study.load_study_config')
    def test_step_4_resume_continues_from_stage_1(
        self, mock_load_config, mock_executor_class,
        temp_workspace, sample_study_config, partial_checkpoint
    ):
        """Step 4: Resume continues from stage 1, not from beginning."""
        from src.cli import cmd_resume
        from argparse import Namespace

        # Setup: Create study structure
        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)
        save_checkpoint(partial_checkpoint, study_dir)

        # Create study config YAML
        config_path = temp_workspace / "studies" / "test_study.yaml"
        create_study_yaml(config_path, sample_study_config)

        # Mock the config loader
        mock_config = MagicMock()
        mock_config.name = "test_study"
        mock_config.pdk = "nangate45"
        mock_config.safety_domain = "sandbox"
        mock_config.stages = sample_study_config["stages"]
        mock_load_config.return_value = mock_config

        # Mock executor
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.total_stages = 3
        mock_result.stages_completed = 3
        mock_result.total_runtime_seconds = 10.0
        mock_result.final_survivors = ["case_1"]
        mock_result.aborted = False
        mock_executor.execute.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        # Change to workspace for relative paths
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            # Execute resume command
            args = Namespace(
                study="test_study",
                checkpoint=None,  # Use latest
                ray_address="auto",
            )

            result = cmd_resume(args)

            # Verify success
            assert result == 0

            # Verify executor was called with checkpoint
            mock_executor_class.assert_called_once()
            call_kwargs = mock_executor_class.call_args[1]
            assert "checkpoint" in call_kwargs
            assert call_kwargs["checkpoint"].study_name == "test_study"
            assert call_kwargs["checkpoint"].last_completed_stage_index == 0

        finally:
            os.chdir(original_cwd)

    def test_step_5_previous_stage_results_preserved(
        self, partial_checkpoint
    ):
        """Step 5: Previous stage results are preserved in checkpoint."""
        # Verify checkpoint contains stage 0 data
        assert len(partial_checkpoint.completed_stages) == 1

        stage0 = partial_checkpoint.completed_stages[0]
        assert stage0.stage_index == 0
        assert stage0.stage_name == "baseline"
        assert stage0.survivor_case_ids == ["case_1", "case_2", "case_3"]
        assert stage0.trials_completed == 10
        assert stage0.trials_failed == 0
        assert stage0.completed_at is not None

        # Verify next stage index is correct
        assert partial_checkpoint.get_next_stage_index() == 1


# ============================================================================
# F052: Resume from specific checkpoint
# ============================================================================


class TestF052ResumeFromSpecificCheckpoint:
    """Test F052: Study can resume from specific checkpoint file.

    Steps:
    1. Complete multi-stage study with checkpoints
    2. Resume from earlier checkpoint using '--checkpoint <path>'
    3. Verify study restarts from that checkpoint's stage
    4. Verify later stage results are discarded/overwritten
    """

    def test_step_1_create_multi_stage_checkpoints(
        self, temp_workspace, multi_stage_checkpoint
    ):
        """Step 1: Create study with multiple stage checkpoints."""
        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)

        # Save checkpoint with 2 stages completed
        checkpoint_path = save_checkpoint(multi_stage_checkpoint, study_dir)

        # Verify checkpoint has both stages
        with open(checkpoint_path) as f:
            data = json.load(f)

        assert data["last_completed_stage_index"] == 1
        assert len(data["completed_stages"]) == 2
        assert data["completed_stages"][0]["stage_name"] == "baseline"
        assert data["completed_stages"][1]["stage_name"] == "refinement"

    def test_step_2_resume_with_specific_checkpoint_path(self):
        """Step 2: Resume command accepts --checkpoint argument."""
        from src.cli import create_parser

        parser = create_parser()

        # Test with specific checkpoint path
        args = parser.parse_args([
            "resume",
            "--study", "test_study",
            "--checkpoint", "/path/to/checkpoint.json"
        ])

        assert args.command == "resume"
        assert args.study == "test_study"
        assert args.checkpoint == Path("/path/to/checkpoint.json")

    @patch('src.controller.executor.StudyExecutor')
    @patch('src.controller.study.load_study_config')
    def test_step_3_resume_from_earlier_stage(
        self, mock_load_config, mock_executor_class,
        temp_workspace, sample_study_config, partial_checkpoint
    ):
        """Step 3: Resume from earlier checkpoint restarts from that stage."""
        from src.cli import cmd_resume
        from argparse import Namespace

        # Setup: Create study structure
        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)

        # Save checkpoint at stage 0
        checkpoint_path = save_checkpoint(partial_checkpoint, study_dir)

        # Create study config
        config_path = temp_workspace / "studies" / "test_study.yaml"
        create_study_yaml(config_path, sample_study_config)

        # Mock config loader
        mock_config = MagicMock()
        mock_config.name = "test_study"
        mock_config.pdk = "nangate45"
        mock_config.safety_domain = "sandbox"
        mock_config.stages = sample_study_config["stages"]
        mock_load_config.return_value = mock_config

        # Mock executor
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.total_stages = 3
        mock_result.stages_completed = 3
        mock_result.total_runtime_seconds = 15.0
        mock_result.final_survivors = ["case_1"]
        mock_result.aborted = False
        mock_executor.execute.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        # Execute
        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            args = Namespace(
                study="test_study",
                checkpoint=checkpoint_path,  # Specific checkpoint
                ray_address="auto",
            )

            result = cmd_resume(args)

            assert result == 0

            # Verify executor received the specific checkpoint
            call_kwargs = mock_executor_class.call_args[1]
            checkpoint = call_kwargs["checkpoint"]
            assert checkpoint.last_completed_stage_index == 0
            assert checkpoint.get_next_stage_index() == 1

        finally:
            os.chdir(original_cwd)

    def test_step_4_later_results_overwritten_semantics(
        self, multi_stage_checkpoint
    ):
        """Step 4: Resuming from earlier checkpoint means later stages re-run.

        This test verifies the checkpoint state makes it clear that
        only stages <= last_completed_stage_index are preserved.
        """
        # Checkpoint has stages 0 and 1 completed
        assert multi_stage_checkpoint.last_completed_stage_index == 1
        assert len(multi_stage_checkpoint.completed_stages) == 2

        # If we resume from stage 0 checkpoint, stage 1 would be discarded
        # Create stage 0 only checkpoint
        stage0_only = StudyCheckpoint(
            study_name="test_study",
            last_completed_stage_index=0,
            completed_stages=[multi_stage_checkpoint.completed_stages[0]],
        )

        # Verify stage0_only doesn't include stage 1
        assert stage0_only.get_next_stage_index() == 1
        assert not stage0_only.is_stage_completed(1)
        assert stage0_only.is_stage_completed(0)

        # When resuming from stage0_only, stage 1 will be re-executed


# ============================================================================
# Integration Tests
# ============================================================================


class TestResumeCommandIntegration:
    """Integration tests for resume command."""

    def test_resume_command_rejects_missing_study(self, temp_workspace):
        """Resume command fails gracefully when study not found."""
        from src.cli import cmd_resume
        from argparse import Namespace

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            args = Namespace(
                study="nonexistent_study",
                checkpoint=None,
                ray_address="auto",
            )

            result = cmd_resume(args)

            # Should fail with non-zero exit code
            assert result != 0

        finally:
            os.chdir(original_cwd)

    def test_resume_command_rejects_missing_checkpoint(
        self, temp_workspace, sample_study_config
    ):
        """Resume command fails when no checkpoint exists."""
        from src.cli import cmd_resume
        from argparse import Namespace

        # Create study dir but no checkpoint
        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            args = Namespace(
                study="test_study",
                checkpoint=None,
                ray_address="auto",
            )

            result = cmd_resume(args)

            # Should fail
            assert result != 0

        finally:
            os.chdir(original_cwd)

    def test_resume_command_rejects_invalid_checkpoint_file(
        self, temp_workspace
    ):
        """Resume command fails with corrupted checkpoint."""
        from src.cli import cmd_resume
        from argparse import Namespace

        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)

        # Create invalid checkpoint
        bad_checkpoint = study_dir / "bad_checkpoint.json"
        bad_checkpoint.write_text("{ invalid json")

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            args = Namespace(
                study="test_study",
                checkpoint=bad_checkpoint,
                ray_address="auto",
            )

            result = cmd_resume(args)

            # Should fail
            assert result != 0

        finally:
            os.chdir(original_cwd)


# ============================================================================
# End-to-End Workflow
# ============================================================================


class TestCompleteResumeWorkflow:
    """Complete workflow test combining F051 and F052."""

    @patch('src.controller.executor.StudyExecutor')
    @patch('src.controller.study.load_study_config')
    def test_complete_resume_workflow(
        self, mock_load_config, mock_executor_class,
        temp_workspace, sample_study_config
    ):
        """Test complete workflow: interrupt → resume latest → resume earlier."""
        from src.cli import cmd_resume
        from argparse import Namespace

        # Setup
        study_dir = temp_workspace / "artifacts" / "test_study"
        study_dir.mkdir(parents=True)

        config_path = temp_workspace / "studies" / "test_study.yaml"
        create_study_yaml(config_path, sample_study_config)

        # Create checkpoint after stage 0
        checkpoint_stage0 = initialize_checkpoint("test_study")
        stage0 = create_stage_checkpoint(
            stage_index=0,
            stage_name="baseline",
            survivor_case_ids=["case_1", "case_2"],
            trials_completed=10,
            trials_failed=0,
        )
        checkpoint_stage0 = update_checkpoint_after_stage(checkpoint_stage0, stage0)
        checkpoint0_path = save_checkpoint(checkpoint_stage0, study_dir)

        # Mock config
        mock_config = MagicMock()
        mock_config.name = "test_study"
        mock_config.pdk = "nangate45"
        mock_config.safety_domain = "sandbox"
        mock_config.stages = sample_study_config["stages"]
        mock_load_config.return_value = mock_config

        # Mock executor
        mock_executor = MagicMock()
        mock_result = MagicMock()
        mock_result.total_stages = 3
        mock_result.stages_completed = 3
        mock_result.total_runtime_seconds = 10.0
        mock_result.final_survivors = ["case_1"]
        mock_result.aborted = False
        mock_executor.execute.return_value = mock_result
        mock_executor_class.return_value = mock_executor

        import os
        original_cwd = os.getcwd()
        try:
            os.chdir(temp_workspace)

            # Test 1: Resume from latest checkpoint
            args1 = Namespace(
                study="test_study",
                checkpoint=None,  # Latest
                ray_address="auto",
            )

            result1 = cmd_resume(args1)
            assert result1 == 0

            # Test 2: Resume from specific earlier checkpoint
            args2 = Namespace(
                study="test_study",
                checkpoint=checkpoint0_path,  # Specific
                ray_address="auto",
            )

            result2 = cmd_resume(args2)
            assert result2 == 0

            # Both should succeed
            assert mock_executor_class.call_count == 2

        finally:
            os.chdir(original_cwd)
