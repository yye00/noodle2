"""Tests for Study resumption from checkpoints."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.controller.study_resumption import (
    StageCheckpoint,
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
# Feature Step 1: Execute multi-stage Study
# ============================================================================


def test_initialize_checkpoint_for_new_study():
    """Test creating a fresh checkpoint for a new Study."""
    checkpoint = initialize_checkpoint("test_study")

    assert checkpoint.study_name == "test_study"
    assert checkpoint.last_completed_stage_index == -1
    assert checkpoint.completed_stages == []
    assert checkpoint.checkpoint_version == "1.0"
    assert checkpoint.created_at is not None


def test_execute_stage_and_create_checkpoint():
    """Test creating a checkpoint after executing a stage."""
    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0_sta_only",
        survivor_case_ids=["case_0_0", "case_0_1", "case_0_2"],
        trials_completed=10,
        trials_failed=2,
        metadata={"avg_wns_ps": -150},
    )

    assert stage_checkpoint.stage_index == 0
    assert stage_checkpoint.stage_name == "stage_0_sta_only"
    assert stage_checkpoint.survivor_case_ids == ["case_0_0", "case_0_1", "case_0_2"]
    assert stage_checkpoint.trials_completed == 10
    assert stage_checkpoint.trials_failed == 2
    assert stage_checkpoint.metadata["avg_wns_ps"] == -150
    assert stage_checkpoint.completed_at is not None

    # Verify timestamp is valid ISO 8601
    datetime.fromisoformat(stage_checkpoint.completed_at)


# ============================================================================
# Feature Step 2: Interrupt execution after Stage 1 completes
# ============================================================================


def test_update_checkpoint_after_stage_completion():
    """Test updating Study checkpoint after a stage completes."""
    checkpoint = initialize_checkpoint("test_study")

    # Complete stage 0
    stage_0_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0", "case_0_1"],
        trials_completed=5,
        trials_failed=0,
    )

    checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)

    assert checkpoint.last_completed_stage_index == 0
    assert len(checkpoint.completed_stages) == 1
    assert checkpoint.completed_stages[0] == stage_0_checkpoint

    # Complete stage 1
    stage_1_checkpoint = create_stage_checkpoint(
        stage_index=1,
        stage_name="stage_1",
        survivor_case_ids=["case_1_0"],
        trials_completed=3,
        trials_failed=1,
    )

    checkpoint = update_checkpoint_after_stage(checkpoint, stage_1_checkpoint)

    assert checkpoint.last_completed_stage_index == 1
    assert len(checkpoint.completed_stages) == 2
    assert checkpoint.completed_stages[1] == stage_1_checkpoint


def test_save_checkpoint_to_disk():
    """Test saving checkpoint to disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        checkpoint = initialize_checkpoint("test_study")
        stage_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name="stage_0",
            survivor_case_ids=["case_0_0"],
            trials_completed=5,
            trials_failed=0,
        )
        checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

        checkpoint_path = save_checkpoint(checkpoint, artifact_dir)

        assert checkpoint_path.exists()
        assert checkpoint_path.name == "study_checkpoint.json"

        # Verify JSON is valid and readable
        with open(checkpoint_path) as f:
            data = json.load(f)

        assert data["study_name"] == "test_study"
        assert data["last_completed_stage_index"] == 0
        assert len(data["completed_stages"]) == 1


# ============================================================================
# Feature Step 3: Load Study state from telemetry
# ============================================================================


def test_load_checkpoint_from_disk():
    """Test loading checkpoint from disk."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        # Create and save checkpoint
        original_checkpoint = initialize_checkpoint("test_study")
        stage_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name="stage_0",
            survivor_case_ids=["case_0_0", "case_0_1"],
            trials_completed=5,
            trials_failed=1,
        )
        original_checkpoint = update_checkpoint_after_stage(
            original_checkpoint, stage_checkpoint
        )

        checkpoint_path = save_checkpoint(original_checkpoint, artifact_dir)

        # Load checkpoint from disk
        loaded_checkpoint = load_checkpoint(checkpoint_path)

        assert loaded_checkpoint.study_name == "test_study"
        assert loaded_checkpoint.last_completed_stage_index == 0
        assert len(loaded_checkpoint.completed_stages) == 1
        assert loaded_checkpoint.completed_stages[0].stage_name == "stage_0"
        assert loaded_checkpoint.completed_stages[0].survivor_case_ids == [
            "case_0_0",
            "case_0_1",
        ]


def test_find_checkpoint_in_artifact_directory():
    """Test finding checkpoint file in artifact directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        # No checkpoint exists yet
        assert find_checkpoint(artifact_dir) is None

        # Save checkpoint
        checkpoint = initialize_checkpoint("test_study")
        save_checkpoint(checkpoint, artifact_dir)

        # Now checkpoint should be found
        found_path = find_checkpoint(artifact_dir)
        assert found_path is not None
        assert found_path.name == "study_checkpoint.json"


def test_load_checkpoint_file_not_found():
    """Test loading checkpoint from non-existent file raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "nonexistent_checkpoint.json"

        with pytest.raises(FileNotFoundError, match="Checkpoint not found"):
            load_checkpoint(checkpoint_path)


def test_load_checkpoint_invalid_json():
    """Test loading checkpoint with invalid JSON raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "invalid_checkpoint.json"

        # Write invalid JSON
        with open(checkpoint_path, "w") as f:
            f.write("{ invalid json }")

        with pytest.raises(ValueError, match="Invalid checkpoint JSON"):
            load_checkpoint(checkpoint_path)


def test_load_checkpoint_malformed_data():
    """Test loading checkpoint with missing required fields raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        checkpoint_path = Path(tmpdir) / "malformed_checkpoint.json"

        # Write JSON with missing required fields
        with open(checkpoint_path, "w") as f:
            json.dump({"study_name": "test"}, f)  # Missing other required fields

        with pytest.raises(ValueError, match="Malformed checkpoint data"):
            load_checkpoint(checkpoint_path)


# ============================================================================
# Feature Step 4: Resume execution starting at Stage 2
# ============================================================================


def test_should_skip_completed_stage():
    """Test determining if a completed stage should be skipped."""
    checkpoint = initialize_checkpoint("test_study")

    # Stage 0 not completed yet
    should_skip, reason = should_skip_stage(checkpoint, 0)
    assert not should_skip
    assert reason == ""

    # Complete stage 0
    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0"],
        trials_completed=5,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Now stage 0 should be skipped
    should_skip, reason = should_skip_stage(checkpoint, 0)
    assert should_skip
    assert "stage_0" in reason
    assert "already completed" in reason

    # Stage 1 not completed yet, should not be skipped
    should_skip, reason = should_skip_stage(checkpoint, 1)
    assert not should_skip


def test_get_next_stage_index():
    """Test getting the next stage index to execute."""
    checkpoint = initialize_checkpoint("test_study")

    # No stages completed, next is 0
    assert checkpoint.get_next_stage_index() == 0

    # Complete stage 0
    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0"],
        trials_completed=5,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Next stage is 1
    assert checkpoint.get_next_stage_index() == 1

    # Complete stage 1
    stage_checkpoint = create_stage_checkpoint(
        stage_index=1,
        stage_name="stage_1",
        survivor_case_ids=["case_1_0"],
        trials_completed=3,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Next stage is 2
    assert checkpoint.get_next_stage_index() == 2


def test_get_survivor_cases_for_resumed_stage():
    """Test getting survivor cases to use when resuming a stage."""
    checkpoint = initialize_checkpoint("test_study")

    # Stage 0 has no previous stage, returns empty list
    survivors = get_survivor_cases_for_stage(checkpoint, 0)
    assert survivors == []

    # Complete stage 0 with survivors
    stage_0_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0", "case_0_1", "case_0_2"],
        trials_completed=10,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)

    # Stage 1 should use stage 0 survivors
    survivors = get_survivor_cases_for_stage(checkpoint, 1)
    assert survivors == ["case_0_0", "case_0_1", "case_0_2"]

    # Complete stage 1 with different survivors
    stage_1_checkpoint = create_stage_checkpoint(
        stage_index=1,
        stage_name="stage_1",
        survivor_case_ids=["case_1_0", "case_1_1"],
        trials_completed=5,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_1_checkpoint)

    # Stage 2 should use stage 1 survivors
    survivors = get_survivor_cases_for_stage(checkpoint, 2)
    assert survivors == ["case_1_0", "case_1_1"]


# ============================================================================
# Feature Step 5: Verify Stage 1 results are preserved and not re-executed
# ============================================================================


def test_is_stage_completed():
    """Test checking if a stage has been completed."""
    checkpoint = initialize_checkpoint("test_study")

    # No stages completed
    assert not checkpoint.is_stage_completed(0)
    assert not checkpoint.is_stage_completed(1)

    # Complete stage 0
    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0"],
        trials_completed=5,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Stage 0 is completed, stage 1 is not
    assert checkpoint.is_stage_completed(0)
    assert not checkpoint.is_stage_completed(1)

    # Complete stage 1
    stage_checkpoint = create_stage_checkpoint(
        stage_index=1,
        stage_name="stage_1",
        survivor_case_ids=["case_1_0"],
        trials_completed=3,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Both stage 0 and 1 are completed
    assert checkpoint.is_stage_completed(0)
    assert checkpoint.is_stage_completed(1)
    assert not checkpoint.is_stage_completed(2)


def test_checkpoint_preserves_stage_results():
    """Test that stage results are preserved across checkpoint save/load."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        # Create checkpoint with multiple completed stages
        checkpoint = initialize_checkpoint("test_study")

        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name="stage_0",
            survivor_case_ids=["case_0_0", "case_0_1"],
            trials_completed=10,
            trials_failed=2,
            metadata={"avg_wns_ps": -200},
        )
        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)

        stage_1_checkpoint = create_stage_checkpoint(
            stage_index=1,
            stage_name="stage_1",
            survivor_case_ids=["case_1_0"],
            trials_completed=5,
            trials_failed=1,
            metadata={"avg_wns_ps": -100},
        )
        checkpoint = update_checkpoint_after_stage(checkpoint, stage_1_checkpoint)

        # Save and reload
        checkpoint_path = save_checkpoint(checkpoint, artifact_dir)
        loaded_checkpoint = load_checkpoint(checkpoint_path)

        # Verify all stage results are preserved
        assert len(loaded_checkpoint.completed_stages) == 2

        stage_0 = loaded_checkpoint.completed_stages[0]
        assert stage_0.stage_index == 0
        assert stage_0.stage_name == "stage_0"
        assert stage_0.survivor_case_ids == ["case_0_0", "case_0_1"]
        assert stage_0.trials_completed == 10
        assert stage_0.trials_failed == 2
        assert stage_0.metadata["avg_wns_ps"] == -200

        stage_1 = loaded_checkpoint.completed_stages[1]
        assert stage_1.stage_index == 1
        assert stage_1.stage_name == "stage_1"
        assert stage_1.survivor_case_ids == ["case_1_0"]
        assert stage_1.trials_completed == 5
        assert stage_1.trials_failed == 1
        assert stage_1.metadata["avg_wns_ps"] == -100


# ============================================================================
# Feature Step 6: Complete Study successfully
# ============================================================================


def test_validate_resumption_success():
    """Test validating a valid resumption checkpoint."""
    checkpoint = initialize_checkpoint("test_study")

    # Complete stages 0 and 1
    for i in range(2):
        stage_checkpoint = create_stage_checkpoint(
            stage_index=i,
            stage_name=f"stage_{i}",
            survivor_case_ids=[f"case_{i}_0"],
            trials_completed=5,
            trials_failed=0,
        )
        checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Validate resumption for a 3-stage Study
    is_valid, issues = validate_resumption(checkpoint, total_stages=3)

    assert is_valid
    assert issues == []


def test_validate_resumption_already_completed():
    """Test validation fails if Study is already fully completed."""
    checkpoint = initialize_checkpoint("test_study")

    # Complete all 3 stages
    for i in range(3):
        stage_checkpoint = create_stage_checkpoint(
            stage_index=i,
            stage_name=f"stage_{i}",
            survivor_case_ids=[f"case_{i}_0"],
            trials_completed=5,
            trials_failed=0,
        )
        checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Validate resumption for a 3-stage Study
    is_valid, issues = validate_resumption(checkpoint, total_stages=3)

    assert not is_valid
    assert len(issues) == 1
    assert "already fully completed" in issues[0]


def test_validate_resumption_missing_stages():
    """Test validation fails if there are gaps in completed stages."""
    # Manually create checkpoint with gap in stages
    checkpoint = StudyCheckpoint(
        study_name="test_study",
        last_completed_stage_index=2,
        completed_stages=[
            StageCheckpoint(
                stage_index=0,
                stage_name="stage_0",
                completed_at=datetime.now(timezone.utc).isoformat(),
                survivor_case_ids=["case_0_0"],
                trials_completed=5,
                trials_failed=0,
            ),
            # Stage 1 is missing
            StageCheckpoint(
                stage_index=2,
                stage_name="stage_2",
                completed_at=datetime.now(timezone.utc).isoformat(),
                survivor_case_ids=["case_2_0"],
                trials_completed=5,
                trials_failed=0,
            ),
        ],
    )

    is_valid, issues = validate_resumption(checkpoint, total_stages=4)

    assert not is_valid
    assert any("Missing stage checkpoints" in issue for issue in issues)


def test_validate_resumption_ordering_mismatch():
    """Test validation fails if stage checkpoints are out of order."""
    # Manually create checkpoint with misordered stages
    checkpoint = StudyCheckpoint(
        study_name="test_study",
        last_completed_stage_index=1,
        completed_stages=[
            StageCheckpoint(
                stage_index=1,  # Wrong order
                stage_name="stage_1",
                completed_at=datetime.now(timezone.utc).isoformat(),
                survivor_case_ids=["case_1_0"],
                trials_completed=5,
                trials_failed=0,
            ),
            StageCheckpoint(
                stage_index=0,  # Wrong order
                stage_name="stage_0",
                completed_at=datetime.now(timezone.utc).isoformat(),
                survivor_case_ids=["case_0_0"],
                trials_completed=5,
                trials_failed=0,
            ),
        ],
    )

    is_valid, issues = validate_resumption(checkpoint, total_stages=3)

    assert not is_valid
    assert any("order mismatch" in issue for issue in issues)


# ============================================================================
# Serialization Tests
# ============================================================================


def test_stage_checkpoint_serialization():
    """Test StageCheckpoint serialization to/from dict."""
    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0", "case_0_1"],
        trials_completed=10,
        trials_failed=2,
        metadata={"avg_wns_ps": -150},
    )

    # Serialize to dict
    data = stage_checkpoint.to_dict()

    assert data["stage_index"] == 0
    assert data["stage_name"] == "stage_0"
    assert data["survivor_case_ids"] == ["case_0_0", "case_0_1"]
    assert data["trials_completed"] == 10
    assert data["trials_failed"] == 2
    assert data["metadata"]["avg_wns_ps"] == -150

    # Deserialize from dict
    loaded = StageCheckpoint.from_dict(data)

    assert loaded.stage_index == stage_checkpoint.stage_index
    assert loaded.stage_name == stage_checkpoint.stage_name
    assert loaded.survivor_case_ids == stage_checkpoint.survivor_case_ids
    assert loaded.trials_completed == stage_checkpoint.trials_completed
    assert loaded.trials_failed == stage_checkpoint.trials_failed
    assert loaded.metadata == stage_checkpoint.metadata


def test_study_checkpoint_serialization():
    """Test StudyCheckpoint serialization to/from dict."""
    checkpoint = initialize_checkpoint("test_study")

    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0"],
        trials_completed=5,
        trials_failed=0,
    )
    checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Serialize to dict
    data = checkpoint.to_dict()

    assert data["study_name"] == "test_study"
    assert data["last_completed_stage_index"] == 0
    assert len(data["completed_stages"]) == 1
    assert data["checkpoint_version"] == "1.0"

    # Deserialize from dict
    loaded = StudyCheckpoint.from_dict(data)

    assert loaded.study_name == checkpoint.study_name
    assert loaded.last_completed_stage_index == checkpoint.last_completed_stage_index
    assert len(loaded.completed_stages) == 1
    assert loaded.checkpoint_version == checkpoint.checkpoint_version


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


def test_checkpoint_with_no_survivors():
    """Test creating checkpoint with empty survivor list."""
    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=[],  # No survivors
        trials_completed=10,
        trials_failed=10,  # All failed
    )

    assert stage_checkpoint.survivor_case_ids == []
    assert stage_checkpoint.trials_failed == 10


def test_checkpoint_preserves_original_creation_time():
    """Test that updating checkpoint preserves original creation time."""
    checkpoint = initialize_checkpoint("test_study")
    original_created_at = checkpoint.created_at

    # Complete stage 0
    stage_checkpoint = create_stage_checkpoint(
        stage_index=0,
        stage_name="stage_0",
        survivor_case_ids=["case_0_0"],
        trials_completed=5,
        trials_failed=0,
    )

    updated_checkpoint = update_checkpoint_after_stage(checkpoint, stage_checkpoint)

    # Original creation time should be preserved
    assert updated_checkpoint.created_at == original_created_at


def test_multiple_checkpoints_same_directory():
    """Test that saving multiple times overwrites previous checkpoint."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        # Save first checkpoint
        checkpoint1 = initialize_checkpoint("test_study")
        save_checkpoint(checkpoint1, artifact_dir)

        # Complete a stage and save again
        stage_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name="stage_0",
            survivor_case_ids=["case_0_0"],
            trials_completed=5,
            trials_failed=0,
        )
        checkpoint2 = update_checkpoint_after_stage(checkpoint1, stage_checkpoint)
        save_checkpoint(checkpoint2, artifact_dir)

        # Load checkpoint - should be the latest one
        checkpoint_path = find_checkpoint(artifact_dir)
        loaded = load_checkpoint(checkpoint_path)

        assert loaded.last_completed_stage_index == 0
        assert len(loaded.completed_stages) == 1


def test_end_to_end_resumption_workflow():
    """Test complete resumption workflow from execution to reload."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        # Initialize Study
        checkpoint = initialize_checkpoint("multi_stage_study")
        save_checkpoint(checkpoint, artifact_dir)

        # Execute stage 0
        stage_0_survivors = ["case_0_0", "case_0_1", "case_0_2"]
        stage_0_checkpoint = create_stage_checkpoint(
            stage_index=0,
            stage_name="sta_baseline",
            survivor_case_ids=stage_0_survivors,
            trials_completed=15,
            trials_failed=3,
        )
        checkpoint = update_checkpoint_after_stage(checkpoint, stage_0_checkpoint)
        save_checkpoint(checkpoint, artifact_dir)

        # Simulate interruption and reload
        checkpoint_path = find_checkpoint(artifact_dir)
        assert checkpoint_path is not None

        loaded_checkpoint = load_checkpoint(checkpoint_path)

        # Verify we should resume at stage 1
        assert loaded_checkpoint.get_next_stage_index() == 1

        # Verify stage 0 should be skipped
        should_skip, reason = should_skip_stage(loaded_checkpoint, 0)
        assert should_skip

        # Verify stage 1 should NOT be skipped
        should_skip, reason = should_skip_stage(loaded_checkpoint, 1)
        assert not should_skip

        # Get survivors for stage 1
        stage_1_input_cases = get_survivor_cases_for_stage(loaded_checkpoint, 1)
        assert stage_1_input_cases == stage_0_survivors

        # Execute stage 1
        stage_1_checkpoint = create_stage_checkpoint(
            stage_index=1,
            stage_name="sta_refinement",
            survivor_case_ids=["case_1_0", "case_1_1"],
            trials_completed=10,
            trials_failed=1,
        )
        loaded_checkpoint = update_checkpoint_after_stage(
            loaded_checkpoint, stage_1_checkpoint
        )
        save_checkpoint(loaded_checkpoint, artifact_dir)

        # Validate for 3-stage Study
        is_valid, issues = validate_resumption(loaded_checkpoint, total_stages=3)
        assert is_valid
        assert issues == []

        # Verify we should resume at stage 2
        assert loaded_checkpoint.get_next_stage_index() == 2
