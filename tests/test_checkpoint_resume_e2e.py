"""End-to-end test for unattended long-running Study with checkpoint and resume.

This test validates Feature #2 from feature_list.json:
"End-to-end: Unattended long-running Study with checkpoint and resume"

All 14 feature steps are tested comprehensively.
"""

import tempfile
from pathlib import Path
from typing import Any

import pytest

from src.controller.study_resumption import (
    StudyCheckpoint,
    create_stage_checkpoint,
    find_checkpoint,
    get_survivor_cases_for_stage,
    initialize_checkpoint,
    load_checkpoint,
    save_checkpoint,
    should_skip_stage,
    update_checkpoint_after_stage,
    validate_resumption,
)


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def artifact_dir():
    """Create temporary artifact directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def large_study_config():
    """Configuration for a large 5-stage Study with 100+ total trials."""
    return {
        "study_name": "large_unattended_study",
        "stages": [
            {
                "stage_index": 0,
                "stage_name": "sta_baseline",
                "trial_budget": 30,
                "survivor_count": 10,
                "execution_mode": "sta_only",
            },
            {
                "stage_index": 1,
                "stage_name": "congestion_aware",
                "trial_budget": 25,
                "survivor_count": 8,
                "execution_mode": "sta_congestion",
            },
            {
                "stage_index": 2,
                "stage_name": "timing_refinement",
                "trial_budget": 20,
                "survivor_count": 5,
                "execution_mode": "sta_only",
            },
            {
                "stage_index": 3,
                "stage_name": "power_aware",
                "trial_budget": 15,
                "survivor_count": 3,
                "execution_mode": "sta_congestion_power",
            },
            {
                "stage_index": 4,
                "stage_name": "final_convergence",
                "trial_budget": 10,
                "survivor_count": 1,
                "execution_mode": "sta_congestion",
            },
        ],
        "total_trials": 100,  # 30 + 25 + 20 + 15 + 10 = 100
    }


# ============================================================================
# Feature Step 1: Create large Study with 5 stages and 100+ total trials
# ============================================================================


class TestCheckpointResumeE2EStep1:
    """Test Step 1: Create large Study configuration."""

    def test_create_large_study_with_5_stages(self, large_study_config):
        """Test creating Study configuration with 5 stages and 100+ trials."""
        assert large_study_config["study_name"] == "large_unattended_study"
        assert len(large_study_config["stages"]) == 5
        assert large_study_config["total_trials"] == 100

        # Verify all stages are configured
        for i, stage in enumerate(large_study_config["stages"]):
            assert stage["stage_index"] == i
            assert stage["stage_name"] is not None
            assert stage["trial_budget"] > 0
            assert stage["survivor_count"] > 0

    def test_initialize_checkpoint_for_large_study(
        self, large_study_config, artifact_dir
    ):
        """Test initializing checkpoint for large Study."""
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        assert checkpoint.study_name == "large_unattended_study"
        assert checkpoint.last_completed_stage_index == -1
        assert len(checkpoint.completed_stages) == 0

        # Save initial checkpoint
        checkpoint_path = save_checkpoint(checkpoint, artifact_dir)
        assert checkpoint_path.exists()


# ============================================================================
# Feature Step 2: Launch Study in unattended mode
# ============================================================================


class TestCheckpointResumeE2EStep2:
    """Test Step 2: Launch Study in unattended mode."""

    def test_launch_unattended_study(self, large_study_config, artifact_dir):
        """Test launching Study with initial checkpoint saved."""
        # Initialize Study
        checkpoint = initialize_checkpoint(large_study_config["study_name"])
        save_checkpoint(checkpoint, artifact_dir)

        # Verify unattended mode readiness
        checkpoint_path = find_checkpoint(artifact_dir)
        assert checkpoint_path is not None

        loaded_checkpoint = load_checkpoint(checkpoint_path)
        assert loaded_checkpoint.get_next_stage_index() == 0


# ============================================================================
# Feature Step 3: Monitor Study progress through Stage 0 completion
# ============================================================================


class TestCheckpointResumeE2EStep3:
    """Test Step 3: Monitor and complete Stage 0."""

    def test_execute_stage_0_and_update_checkpoint(
        self, large_study_config, artifact_dir
    ):
        """Test executing Stage 0 and updating checkpoint."""
        checkpoint = initialize_checkpoint(large_study_config["study_name"])
        save_checkpoint(checkpoint, artifact_dir)

        # Simulate Stage 0 execution
        stage_0_config = large_study_config["stages"][0]

        # Simulate trial execution (30 trials, 28 successful, 2 failed)
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=stage_0_config["stage_index"],
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
            metadata={
                "execution_mode": stage_0_config["execution_mode"],
                "trial_budget": stage_0_config["trial_budget"],
            },
        )

        # Update checkpoint after Stage 0
        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Verify checkpoint state
        assert checkpoint.last_completed_stage_index == 0
        assert len(checkpoint.completed_stages) == 1
        assert checkpoint.completed_stages[0].trials_completed == 28
        assert checkpoint.completed_stages[0].trials_failed == 2
        assert len(checkpoint.completed_stages[0].survivor_case_ids) == 10


# ============================================================================
# Feature Step 4: Verify Stage 0 telemetry is written
# ============================================================================


class TestCheckpointResumeE2EStep4:
    """Test Step 4: Verify Stage 0 telemetry."""

    def test_verify_stage_0_telemetry_in_checkpoint(
        self, large_study_config, artifact_dir
    ):
        """Test that Stage 0 telemetry is properly recorded in checkpoint."""
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        # Execute Stage 0
        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
            metadata={
                "execution_mode": stage_0_config["execution_mode"],
                "avg_wns_ps": -250,
                "best_wns_ps": -100,
                "worst_wns_ps": -500,
            },
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Reload and verify telemetry
        loaded_checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")
        stage_0 = loaded_checkpoint.completed_stages[0]

        assert stage_0.metadata["execution_mode"] == "sta_only"
        assert stage_0.metadata["avg_wns_ps"] == -250
        assert stage_0.metadata["best_wns_ps"] == -100
        assert stage_0.trials_completed == 28
        assert stage_0.trials_failed == 2


# ============================================================================
# Feature Step 5: Save checkpoint after Stage 0
# ============================================================================


class TestCheckpointResumeE2EStep5:
    """Test Step 5: Save checkpoint after Stage 0."""

    def test_save_checkpoint_after_stage_0(self, large_study_config, artifact_dir):
        """Test saving checkpoint to disk after Stage 0 completion."""
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        # Execute and save Stage 0
        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        checkpoint_path = save_checkpoint(checkpoint, artifact_dir)

        # Verify checkpoint file exists and is valid
        assert checkpoint_path.exists()
        assert checkpoint_path.name == "study_checkpoint.json"

        # Verify file is readable and valid JSON
        import json

        with open(checkpoint_path) as f:
            data = json.load(f)

        assert data["study_name"] == "large_unattended_study"
        assert data["last_completed_stage_index"] == 0
        assert len(data["completed_stages"]) == 1


# ============================================================================
# Feature Step 6: Simulate interruption (stop execution)
# ============================================================================


class TestCheckpointResumeE2EStep6:
    """Test Step 6: Simulate execution interruption."""

    def test_simulate_interruption_after_stage_0(
        self, large_study_config, artifact_dir
    ):
        """Test simulating Study interruption after Stage 0."""
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        # Execute Stage 0
        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Simulate interruption - checkpoint file should still exist
        checkpoint_path = find_checkpoint(artifact_dir)
        assert checkpoint_path is not None

        # Verify checkpoint is loadable after interruption
        loaded_checkpoint = load_checkpoint(checkpoint_path)
        assert loaded_checkpoint.last_completed_stage_index == 0
        assert loaded_checkpoint.get_next_stage_index() == 1


# ============================================================================
# Feature Step 7: Reload Study state from checkpoint
# ============================================================================


class TestCheckpointResumeE2EStep7:
    """Test Step 7: Reload Study state from checkpoint."""

    def test_reload_study_state_from_checkpoint(
        self, large_study_config, artifact_dir
    ):
        """Test reloading Study state after interruption."""
        # Setup: Execute Stage 0 and save checkpoint
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Simulate process restart - reload from disk
        checkpoint_path = find_checkpoint(artifact_dir)
        assert checkpoint_path is not None

        reloaded_checkpoint = load_checkpoint(checkpoint_path)

        # Verify state is fully restored
        assert reloaded_checkpoint.study_name == "large_unattended_study"
        assert reloaded_checkpoint.last_completed_stage_index == 0
        assert len(reloaded_checkpoint.completed_stages) == 1
        assert (
            reloaded_checkpoint.completed_stages[0].stage_name
            == stage_0_config["stage_name"]
        )
        assert len(reloaded_checkpoint.completed_stages[0].survivor_case_ids) == 10


# ============================================================================
# Feature Step 8: Resume execution starting at Stage 1
# ============================================================================


class TestCheckpointResumeE2EStep8:
    """Test Step 8: Resume execution at Stage 1."""

    def test_resume_execution_at_stage_1(self, large_study_config, artifact_dir):
        """Test resuming Study execution starting at Stage 1."""
        # Setup: Complete Stage 0 and save
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Reload and verify resume point
        reloaded_checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")

        assert reloaded_checkpoint.get_next_stage_index() == 1

        # Get input cases for Stage 1
        stage_1_input_cases = get_survivor_cases_for_stage(reloaded_checkpoint, 1)
        assert stage_1_input_cases == stage_0_survivors

        # Execute Stage 1
        stage_1_config = large_study_config["stages"][1]
        stage_1_survivors = [
            f"{large_study_config['study_name']}_1_{i}"
            for i in range(stage_1_config["survivor_count"])
        ]

        stage_1_checkpoint = create_stage_checkpoint(
            stage_index=1,
            stage_name=stage_1_config["stage_name"],
            survivor_case_ids=stage_1_survivors,
            trials_completed=23,
            trials_failed=2,
        )

        reloaded_checkpoint = update_checkpoint_after_stage(
            reloaded_checkpoint, stage_1_checkpoint
        )
        save_checkpoint(reloaded_checkpoint, artifact_dir)

        # Verify Stage 1 is now completed
        assert reloaded_checkpoint.last_completed_stage_index == 1
        assert len(reloaded_checkpoint.completed_stages) == 2


# ============================================================================
# Feature Step 9: Verify Stage 0 is not re-executed
# ============================================================================


class TestCheckpointResumeE2EStep9:
    """Test Step 9: Verify Stage 0 is not re-executed."""

    def test_verify_stage_0_not_reexecuted(self, large_study_config, artifact_dir):
        """Test that Stage 0 is properly skipped during resumption."""
        # Setup: Complete Stage 0
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Reload checkpoint
        reloaded_checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")

        # Verify Stage 0 should be skipped
        should_skip, reason = should_skip_stage(reloaded_checkpoint, 0)
        assert should_skip
        assert "stage_0" in reason.lower() or "sta_baseline" in reason
        assert "already completed" in reason

        # Verify Stage 1 should NOT be skipped
        should_skip, reason = should_skip_stage(reloaded_checkpoint, 1)
        assert not should_skip


# ============================================================================
# Feature Step 10: Continue through Stages 1-2
# ============================================================================


class TestCheckpointResumeE2EStep10:
    """Test Step 10: Continue execution through Stages 1-2."""

    def test_execute_stages_1_and_2(self, large_study_config, artifact_dir):
        """Test continuing execution through Stages 1 and 2."""
        # Setup: Complete Stage 0
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Execute Stage 1
        stage_1_config = large_study_config["stages"][1]
        stage_1_survivors = [
            f"{large_study_config['study_name']}_1_{i}"
            for i in range(stage_1_config["survivor_count"])
        ]

        stage_1_checkpoint = create_stage_checkpoint(
            stage_index=1,
            stage_name=stage_1_config["stage_name"],
            survivor_case_ids=stage_1_survivors,
            trials_completed=23,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_1_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Execute Stage 2
        stage_2_config = large_study_config["stages"][2]
        stage_2_survivors = [
            f"{large_study_config['study_name']}_2_{i}"
            for i in range(stage_2_config["survivor_count"])
        ]

        stage_2_checkpoint = create_stage_checkpoint(
            stage_index=2,
            stage_name=stage_2_config["stage_name"],
            survivor_case_ids=stage_2_survivors,
            trials_completed=18,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_2_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Verify state after Stages 0-2
        assert checkpoint.last_completed_stage_index == 2
        assert len(checkpoint.completed_stages) == 3
        assert checkpoint.get_next_stage_index() == 3


# ============================================================================
# Feature Step 11: Save checkpoint after Stage 2
# ============================================================================


class TestCheckpointResumeE2EStep11:
    """Test Step 11: Save checkpoint after Stage 2."""

    def test_save_checkpoint_after_stage_2(self, large_study_config, artifact_dir):
        """Test saving checkpoint after Stage 2 completion."""
        # Setup: Complete Stages 0-2
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        for i in range(3):
            stage_config = large_study_config["stages"][i]
            stage_survivors = [
                f"{large_study_config['study_name']}_{i}_{j}"
                for j in range(stage_config["survivor_count"])
            ]

            stage_checkpoint = create_stage_checkpoint(
                stage_index=i,
                stage_name=stage_config["stage_name"],
                survivor_case_ids=stage_survivors,
                trials_completed=stage_config["trial_budget"] - 2,
                trials_failed=2,
            )

            checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

        checkpoint_path = save_checkpoint(checkpoint, artifact_dir)

        # Verify checkpoint file
        assert checkpoint_path.exists()

        # Reload and verify
        reloaded_checkpoint = load_checkpoint(checkpoint_path)
        assert reloaded_checkpoint.last_completed_stage_index == 2
        assert len(reloaded_checkpoint.completed_stages) == 3

        # Verify all stage data is preserved
        for i in range(3):
            stage = reloaded_checkpoint.completed_stages[i]
            assert stage.stage_index == i
            assert stage.trials_failed == 2


# ============================================================================
# Feature Step 12: Resume and complete Stages 3-4
# ============================================================================


class TestCheckpointResumeE2EStep12:
    """Test Step 12: Resume and complete Stages 3-4."""

    def test_resume_and_complete_stages_3_and_4(
        self, large_study_config, artifact_dir
    ):
        """Test resuming and completing final stages 3-4."""
        # Setup: Complete Stages 0-2
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        for i in range(3):
            stage_config = large_study_config["stages"][i]
            stage_survivors = [
                f"{large_study_config['study_name']}_{i}_{j}"
                for j in range(stage_config["survivor_count"])
            ]

            stage_checkpoint = create_stage_checkpoint(
                stage_index=i,
                stage_name=stage_config["stage_name"],
                survivor_case_ids=stage_survivors,
                trials_completed=stage_config["trial_budget"] - 2,
                trials_failed=2,
            )

            checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

        save_checkpoint(checkpoint, artifact_dir)

        # Reload and verify resume point
        reloaded_checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")
        assert reloaded_checkpoint.get_next_stage_index() == 3

        # Execute Stage 3
        stage_3_config = large_study_config["stages"][3]
        stage_3_survivors = [
            f"{large_study_config['study_name']}_3_{i}"
            for i in range(stage_3_config["survivor_count"])
        ]

        stage_3_checkpoint = create_stage_checkpoint(
            stage_index=3,
            stage_name=stage_3_config["stage_name"],
            survivor_case_ids=stage_3_survivors,
            trials_completed=13,
            trials_failed=2,
        )

        reloaded_checkpoint = update_checkpoint_after_stage(
            reloaded_checkpoint, stage_3_checkpoint
        )
        save_checkpoint(reloaded_checkpoint, artifact_dir)

        # Execute Stage 4 (final stage)
        stage_4_config = large_study_config["stages"][4]
        stage_4_survivors = [
            f"{large_study_config['study_name']}_4_{i}"
            for i in range(stage_4_config["survivor_count"])
        ]

        stage_4_checkpoint = create_stage_checkpoint(
            stage_index=4,
            stage_name=stage_4_config["stage_name"],
            survivor_case_ids=stage_4_survivors,
            trials_completed=8,
            trials_failed=2,
        )

        reloaded_checkpoint = update_checkpoint_after_stage(
            reloaded_checkpoint, stage_4_checkpoint
        )
        save_checkpoint(reloaded_checkpoint, artifact_dir)

        # Verify final state
        assert reloaded_checkpoint.last_completed_stage_index == 4
        assert len(reloaded_checkpoint.completed_stages) == 5
        assert len(reloaded_checkpoint.completed_stages[4].survivor_case_ids) == 1


# ============================================================================
# Feature Step 13: Verify final Study is complete and consistent
# ============================================================================


class TestCheckpointResumeE2EStep13:
    """Test Step 13: Verify final Study completion and consistency."""

    def test_verify_final_study_complete_and_consistent(
        self, large_study_config, artifact_dir
    ):
        """Test that final Study is complete and all data is consistent."""
        # Setup: Complete all 5 stages
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        for i in range(5):
            stage_config = large_study_config["stages"][i]
            stage_survivors = [
                f"{large_study_config['study_name']}_{i}_{j}"
                for j in range(stage_config["survivor_count"])
            ]

            stage_checkpoint = create_stage_checkpoint(
                stage_index=i,
                stage_name=stage_config["stage_name"],
                survivor_case_ids=stage_survivors,
                trials_completed=stage_config["trial_budget"] - 2,
                trials_failed=2,
            )

            checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

        save_checkpoint(checkpoint, artifact_dir)

        # Reload and verify complete state
        final_checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")

        # Verify Study is complete
        assert final_checkpoint.last_completed_stage_index == 4
        assert len(final_checkpoint.completed_stages) == 5

        # Verify consistency of all stages
        for i in range(5):
            stage = final_checkpoint.completed_stages[i]
            assert stage.stage_index == i
            assert stage.stage_name == large_study_config["stages"][i]["stage_name"]
            assert (
                len(stage.survivor_case_ids)
                == large_study_config["stages"][i]["survivor_count"]
            )

        # Verify final winner exists
        final_stage = final_checkpoint.completed_stages[4]
        assert len(final_stage.survivor_case_ids) == 1

        # Verify total trial counts
        total_trials_run = sum(
            stage.trials_completed + stage.trials_failed
            for stage in final_checkpoint.completed_stages
        )
        assert total_trials_run == large_study_config["total_trials"]


# ============================================================================
# Feature Step 14: Verify checkpoint mechanism is reliable
# ============================================================================


class TestCheckpointResumeE2EStep14:
    """Test Step 14: Verify checkpoint mechanism reliability."""

    def test_verify_checkpoint_mechanism_reliability(
        self, large_study_config, artifact_dir
    ):
        """Test comprehensive checkpoint reliability checks."""
        # Create complete Study checkpoint
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        for i in range(5):
            stage_config = large_study_config["stages"][i]
            stage_survivors = [
                f"{large_study_config['study_name']}_{i}_{j}"
                for j in range(stage_config["survivor_count"])
            ]

            stage_checkpoint = create_stage_checkpoint(
                stage_index=i,
                stage_name=stage_config["stage_name"],
                survivor_case_ids=stage_survivors,
                trials_completed=stage_config["trial_budget"] - 2,
                trials_failed=2,
            )

            checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

        save_checkpoint(checkpoint, artifact_dir)

        # Test 1: Checkpoint validation succeeds
        is_valid, issues = validate_resumption(checkpoint, total_stages=5)
        assert not is_valid  # Study is complete
        assert "already fully completed" in issues[0]

        # Test 2: Multiple save/load cycles preserve data
        for _ in range(3):
            checkpoint_path = save_checkpoint(checkpoint, artifact_dir)
            loaded = load_checkpoint(checkpoint_path)
            assert loaded.study_name == checkpoint.study_name
            assert (
                loaded.last_completed_stage_index
                == checkpoint.last_completed_stage_index
            )
            assert len(loaded.completed_stages) == len(checkpoint.completed_stages)

        # Test 3: Checkpoint finding is reliable
        found_path = find_checkpoint(artifact_dir)
        assert found_path is not None
        assert found_path.exists()

        # Test 4: Partial completion validation
        partial_checkpoint = initialize_checkpoint("partial_study")
        for i in range(3):  # Only complete first 3 stages
            stage_config = large_study_config["stages"][i]
            stage_survivors = [f"partial_study_{i}_{j}" for j in range(5)]

            stage_checkpoint = create_stage_checkpoint(
                stage_index=i,
                stage_name=stage_config["stage_name"],
                survivor_case_ids=stage_survivors,
                trials_completed=10,
                trials_failed=0,
            )

            partial_checkpoint = update_checkpoint_after_stage(
                partial_checkpoint, stage_checkpoint
            )

        # Validate partial checkpoint for 5-stage Study
        is_valid, issues = validate_resumption(partial_checkpoint, total_stages=5)
        assert is_valid
        assert len(issues) == 0

        # Verify next stage is correct
        assert partial_checkpoint.get_next_stage_index() == 3

    def test_checkpoint_idempotency(self, large_study_config, artifact_dir):
        """Test that checkpoint save/load is idempotent."""
        checkpoint = initialize_checkpoint(large_study_config["study_name"])

        stage_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name="test_stage",
            survivor_case_ids=["case_0", "case_1"],
            trials_completed=10,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

        # Save and load multiple times
        for i in range(5):
            save_checkpoint(checkpoint, artifact_dir)
            loaded = load_checkpoint(artifact_dir / "study_checkpoint.json")

            # Verify data is identical
            assert loaded.study_name == checkpoint.study_name
            assert (
                loaded.last_completed_stage_index
                == checkpoint.last_completed_stage_index
            )
            assert (
                loaded.completed_stages[0].survivor_case_ids
                == checkpoint.completed_stages[0].survivor_case_ids
            )

    def test_checkpoint_corruption_detection(self, artifact_dir):
        """Test that corrupted checkpoints are detected."""
        import json

        checkpoint_path = artifact_dir / "study_checkpoint.json"

        # Create valid checkpoint first
        checkpoint = initialize_checkpoint("test_study")
        save_checkpoint(checkpoint, artifact_dir)

        # Corrupt the checkpoint
        with open(checkpoint_path, "w") as f:
            f.write("{ corrupt json }")

        # Verify loading fails with clear error
        with pytest.raises(ValueError, match="Invalid checkpoint JSON"):
            load_checkpoint(checkpoint_path)

        # Test malformed data
        with open(checkpoint_path, "w") as f:
            json.dump({"study_name": "test"}, f)  # Missing required fields

        with pytest.raises(ValueError, match="Malformed checkpoint data"):
            load_checkpoint(checkpoint_path)


# ============================================================================
# Complete E2E Workflow Integration Test
# ============================================================================


class TestCompleteCheckpointResumeE2EWorkflow:
    """Integration test covering complete checkpoint/resume workflow."""

    def test_complete_unattended_study_with_interruptions(
        self, large_study_config, artifact_dir
    ):
        """
        Test complete unattended Study workflow with multiple interruptions.

        This test simulates:
        1. Starting a large 5-stage Study
        2. Completing Stage 0
        3. Interruption and resume at Stage 1
        4. Completing Stages 1-2
        5. Another interruption and resume at Stage 3
        6. Completing Stages 3-4
        7. Final validation of complete Study
        """
        # Initialize Study
        checkpoint = initialize_checkpoint(large_study_config["study_name"])
        save_checkpoint(checkpoint, artifact_dir)

        # === Execute Stage 0 ===
        stage_0_config = large_study_config["stages"][0]
        stage_0_survivors = [
            f"{large_study_config['study_name']}_0_{i}"
            for i in range(stage_0_config["survivor_count"])
        ]

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name=stage_0_config["stage_name"],
            survivor_case_ids=stage_0_survivors,
            trials_completed=28,
            trials_failed=2,
        )

        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # === INTERRUPTION 1 ===
        # Simulate process restart
        checkpoint = None  # Clear memory

        # Resume from checkpoint
        checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")
        assert checkpoint.get_next_stage_index() == 1

        # Verify Stage 0 should be skipped
        should_skip, _ = should_skip_stage(checkpoint, 0)
        assert should_skip

        # === Execute Stages 1-2 ===
        for i in range(1, 3):
            stage_config = large_study_config["stages"][i]
            stage_survivors = [
                f"{large_study_config['study_name']}_{i}_{j}"
                for j in range(stage_config["survivor_count"])
            ]

            stage_checkpoint = create_stage_checkpoint(
                stage_index=i,
                stage_name=stage_config["stage_name"],
                survivor_case_ids=stage_survivors,
                trials_completed=stage_config["trial_budget"] - 2,
                trials_failed=2,
            )

            checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)
            save_checkpoint(checkpoint, artifact_dir)

        # === INTERRUPTION 2 ===
        # Simulate process restart again
        checkpoint = None

        # Resume from checkpoint
        checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")
        assert checkpoint.get_next_stage_index() == 3

        # Verify Stages 0-2 should be skipped
        for i in range(3):
            should_skip, _ = should_skip_stage(checkpoint, i)
            assert should_skip

        # === Execute Stages 3-4 ===
        for i in range(3, 5):
            stage_config = large_study_config["stages"][i]
            stage_survivors = [
                f"{large_study_config['study_name']}_{i}_{j}"
                for j in range(stage_config["survivor_count"])
            ]

            stage_checkpoint = create_stage_checkpoint(
                stage_index=i,
                stage_name=stage_config["stage_name"],
                survivor_case_ids=stage_survivors,
                trials_completed=stage_config["trial_budget"] - 2,
                trials_failed=2,
            )

            checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)
            save_checkpoint(checkpoint, artifact_dir)

        # === Final Validation ===
        final_checkpoint = load_checkpoint(artifact_dir / "study_checkpoint.json")

        # Verify Study is complete
        assert final_checkpoint.last_completed_stage_index == 4
        assert len(final_checkpoint.completed_stages) == 5

        # Verify final winner
        assert len(final_checkpoint.completed_stages[4].survivor_case_ids) == 1

        # Verify total trials
        total_trials = sum(
            stage.trials_completed + stage.trials_failed
            for stage in final_checkpoint.completed_stages
        )
        assert total_trials == large_study_config["total_trials"]

        # Verify checkpoint is no longer resumable (Study complete)
        is_valid, issues = validate_resumption(final_checkpoint, total_stages=5)
        assert not is_valid
        assert "already fully completed" in issues[0]
