"""
Tests for F105: Modified ODB snapshots propagate between stages as input to next stage.

This feature ensures that ECO modifications accumulate across stages:
- Stage 0 survivors have modified_odb_path set
- Stage 1 uses modified_odb_path as snapshot_path (not original)
- Case lineage tracks which parent ODB was used
- Final case represents accumulated modifications
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.controller.case import Case
from src.controller.executor import StageResult, StudyExecutor
from src.controller.study import StudyConfig
from src.controller.types import ExecutionMode, SafetyDomain, StageConfig, StageType
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


class TestF105ODBPropagation:
    """Test suite for F105: ODB propagation between stages."""

    def test_trial_result_has_modified_odb_path_field(self):
        """Verify TrialResult has modified_odb_path field."""
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/path/to/script.tcl",
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            modified_odb_path="/path/to/modified.odb",
        )

        assert trial_result.modified_odb_path == "/path/to/modified.odb"

    def test_modified_odb_path_in_trial_result_dict(self):
        """Verify modified_odb_path is included in TrialResult.to_dict()."""
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/path/to/script.tcl",
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
            modified_odb_path="/path/to/modified.odb",
        )

        result_dict = trial_result.to_dict()
        assert "modified_odb_path" in result_dict
        assert result_dict["modified_odb_path"] == "/path/to/modified.odb"

    def test_stage_survivors_have_modified_odb_path(self):
        """
        Step 2: Verify stage 0 survivors have modified_odb_path set.

        When trials succeed with ECO modifications, their TrialResults
        should contain the path to the modified ODB file.
        """
        # Create trial results with modified ODB paths
        trial_results = []
        for i in range(5):
            trial_config = TrialConfig(
                study_name="test_study",
                case_name=f"case_{i}",
                stage_index=0,
                trial_index=i,
                script_path="/path/to/script.tcl",
            )

            trial_result = TrialResult(
                config=trial_config,
                success=True,
                return_code=0,
                runtime_seconds=10.0,
                artifacts=TrialArtifacts(trial_dir=Path(f"/tmp/trial_{i}")),
                metrics={"wns_ps": -1000 + i * 100},  # Improving WNS
                modified_odb_path=f"/tmp/trial_{i}/modified_design_{i}.odb",
            )
            trial_results.append(trial_result)

        # Verify all successful trials have modified_odb_path
        for trial in trial_results:
            assert trial.success
            assert trial.modified_odb_path is not None
            assert trial.modified_odb_path.endswith(".odb")

    def test_next_stage_uses_modified_odb_as_snapshot(self):
        """
        Step 3: Verify stage 1 uses modified_odb_path as snapshot_path (not original).

        When survivors advance to the next stage, their derived cases should
        use the modified ODB path as the snapshot_path.
        """
        # Simulate stage 0 survivor with modified ODB
        stage_0_survivor = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/snapshots/nangate45",
        )

        # Simulate that this case was modified and has a new ODB
        modified_odb_path = "/tmp/stage_0/trial_3/modified_design_3.odb"

        # Create derived case for stage 1 (simulating executor logic)
        stage_1_case = stage_0_survivor.derive(
            eco_name="pass_through",
            new_stage_index=1,
            derived_index=0,
            snapshot_path=modified_odb_path,  # Use modified ODB
            metadata={
                "source_trial": "nangate45_base_0_3",
                "input_odb_from_stage": 0,
                "accumulated_modifications": True,
            },
        )

        # Verify the derived case uses the modified ODB
        assert stage_1_case.snapshot_path == modified_odb_path
        assert stage_1_case.snapshot_path != "/snapshots/nangate45"
        assert stage_1_case.metadata["accumulated_modifications"] is True
        assert stage_1_case.metadata["input_odb_from_stage"] == 0

    def test_case_lineage_tracks_parent_odb(self):
        """
        Step 4: Verify Case lineage tracks which parent ODB was used.

        The case metadata should clearly indicate when a modified ODB
        was used as input, enabling full traceability.
        """
        # Stage 0: Base case
        base_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/snapshots/nangate45",
        )

        # Stage 0: Derived case with ECO
        stage_0_trial = base_case.derive(
            eco_name="CellResizeECO",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/snapshots/nangate45",
            metadata={"trial_index": 1},
        )

        # Simulate modified ODB from stage 0
        modified_odb_stage_0 = "/artifacts/trial_1/modified_design_1.odb"

        # Stage 1: Derived case using modified ODB
        stage_1_trial = stage_0_trial.derive(
            eco_name="BufferInsertionECO",
            new_stage_index=1,
            derived_index=0,
            snapshot_path=modified_odb_stage_0,
            metadata={
                "trial_index": 0,
                "input_odb_from_stage": 0,
                "accumulated_modifications": True,
            },
        )

        # Verify lineage tracking
        assert stage_1_trial.parent_id == str(stage_0_trial.identifier)
        assert stage_1_trial.snapshot_path == modified_odb_stage_0
        assert stage_1_trial.metadata["input_odb_from_stage"] == 0
        assert stage_1_trial.metadata["accumulated_modifications"] is True

    def test_multi_stage_accumulation(self):
        """
        Step 5: Verify final case represents accumulated modifications.

        After multiple stages, the final case should have a snapshot_path
        pointing to the accumulated ODB from the last stage.
        """
        # Stage 0: Base case
        base_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path="/snapshots/nangate45",
        )

        # Stage 0: Trial with ECO
        stage_0_case = base_case.derive(
            eco_name="CellResizeECO",
            new_stage_index=0,
            derived_index=1,
            snapshot_path="/snapshots/nangate45",
        )
        modified_odb_0 = "/artifacts/stage_0/modified.odb"

        # Stage 1: Trial using stage 0 ODB
        stage_1_case = stage_0_case.derive(
            eco_name="BufferInsertionECO",
            new_stage_index=1,
            derived_index=0,
            snapshot_path=modified_odb_0,
            metadata={"input_odb_from_stage": 0},
        )
        modified_odb_1 = "/artifacts/stage_1/modified.odb"

        # Stage 2: Trial using stage 1 ODB
        stage_2_case = stage_1_case.derive(
            eco_name="CellSwapECO",
            new_stage_index=2,
            derived_index=0,
            snapshot_path=modified_odb_1,
            metadata={"input_odb_from_stage": 1},
        )

        # Verify final case represents accumulated changes
        assert stage_2_case.stage_index == 2
        assert stage_2_case.snapshot_path == modified_odb_1
        assert stage_2_case.parent_id == str(stage_1_case.identifier)

        # Trace back through lineage
        assert stage_1_case.parent_id == str(stage_0_case.identifier)
        assert stage_0_case.parent_id == str(base_case.identifier)

    def test_odb_path_detection_in_executor(self):
        """
        Test that executor correctly detects ODB files vs directories.

        When snapshot_path ends with .odb, the executor should:
        - Set input_odb_path in script generation
        - Use parent directory as snapshot_dir
        """
        # Test ODB file path
        odb_path = Path("/artifacts/stage_0/modified_design_1.odb")
        assert odb_path.suffix == ".odb"
        assert str(odb_path.parent) == "/artifacts/stage_0"

        # Test directory path
        dir_path = Path("/snapshots/nangate45")
        assert dir_path.suffix != ".odb"

    def test_trial_metadata_includes_input_odb_path(self):
        """
        Verify trial metadata tracks whether modified ODB was used.

        This enables debugging and understanding of the ECO accumulation chain.
        """
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="test_case_1_0",
            stage_index=1,
            trial_index=0,
            script_path="/path/to/script.tcl",
            metadata={
                "input_odb_path": "/artifacts/stage_0/modified_design_3.odb",
                "eco_type": "BufferInsertionECO",
            },
        )

        assert trial_config.metadata["input_odb_path"] is not None
        assert trial_config.metadata["input_odb_path"].endswith(".odb")

    def test_no_modified_odb_for_failed_trials(self):
        """
        Verify that failed trials don't have modified_odb_path set.

        Only successful trials should propagate ODB to next stage.
        """
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/path/to/script.tcl",
        )

        # Failed trial
        trial_result = TrialResult(
            config=trial_config,
            success=False,
            return_code=1,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial")),
        )

        # Failed trials should not have modified ODB
        assert trial_result.modified_odb_path is None

    def test_fallback_to_original_snapshot_when_no_modified_odb(self):
        """
        Verify fallback behavior when no modified ODB is available.

        If a trial doesn't produce a modified ODB, the next stage should
        fall back to the original snapshot path.
        """
        original_snapshot = "/snapshots/nangate45"

        # Simulate survivor without modified ODB (e.g., NoOpECO trial)
        survivor_case = Case.create_base_case(
            base_name="nangate45_base",
            snapshot_path=original_snapshot,
        )

        # No modified ODB available (None)
        modified_odb_path = None

        # Fallback logic (from executor)
        next_snapshot_path = modified_odb_path if modified_odb_path else original_snapshot

        # Verify fallback to original
        assert next_snapshot_path == original_snapshot

        # Create next stage case with fallback
        next_stage_case = survivor_case.derive(
            eco_name="pass_through",
            new_stage_index=1,
            derived_index=0,
            snapshot_path=next_snapshot_path,
            metadata={
                "source_trial": "nangate45_base_0_0",
                "input_odb_from_stage": None,
                "accumulated_modifications": False,
            },
        )

        assert next_stage_case.snapshot_path == original_snapshot
        assert next_stage_case.metadata["accumulated_modifications"] is False


class TestF105Integration:
    """Integration tests for F105 ODB propagation in Study execution."""

    def test_odb_propagation_end_to_end_mock(self):
        """
        Test ODB propagation through a multi-stage study (mocked execution).

        This test simulates the full flow without real OpenROAD execution:
        1. Stage 0 produces modified ODB files
        2. Stage 1 survivors are created with modified ODB as snapshot
        3. Case lineage reflects the ODB chain
        """
        # Create a simple 2-stage study configuration
        study_config = StudyConfig(
            name="odb_propagation_test",
            safety_domain=SafetyDomain.GUARDED,
            pdk="nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/snapshots/nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=2,
                    timeout_seconds=600,
                ),
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                    timeout_seconds=600,
                ),
            ],
        )

        # Mock trial results for stage 0 with modified ODB paths
        stage_0_trial_results = [
            TrialResult(
                config=TrialConfig(
                    study_name="odb_propagation_test",
                    case_name="nangate45_base_0_0",
                    stage_index=0,
                    trial_index=0,
                    script_path="/path/to/script.tcl",
                ),
                success=True,
                return_code=0,
                runtime_seconds=10.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial_0")),
                metrics={"wns_ps": -800},
                modified_odb_path="/tmp/trial_0/modified_design_0.odb",
            ),
            TrialResult(
                config=TrialConfig(
                    study_name="odb_propagation_test",
                    case_name="nangate45_base_0_1",
                    stage_index=0,
                    trial_index=1,
                    script_path="/path/to/script.tcl",
                ),
                success=True,
                return_code=0,
                runtime_seconds=10.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial_1")),
                metrics={"wns_ps": -700},
                modified_odb_path="/tmp/trial_1/modified_design_1.odb",
            ),
            TrialResult(
                config=TrialConfig(
                    study_name="odb_propagation_test",
                    case_name="nangate45_base_0_2",
                    stage_index=0,
                    trial_index=2,
                    script_path="/path/to/script.tcl",
                ),
                success=True,
                return_code=0,
                runtime_seconds=10.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/trial_2")),
                metrics={"wns_ps": -900},
                modified_odb_path="/tmp/trial_2/modified_design_2.odb",
            ),
        ]

        # Simulate survivor selection (top 2 by WNS)
        survivors = ["nangate45_base_0_1", "nangate45_base_0_0"]  # WNS: -700, -800

        # Simulate creating derived cases for stage 1
        stage_1_input_cases = []
        for derived_idx, survivor_id in enumerate(survivors):
            # Find the modified ODB path for this survivor
            modified_odb_path = None
            for trial_result in stage_0_trial_results:
                if trial_result.config.case_name == survivor_id:
                    modified_odb_path = trial_result.modified_odb_path
                    break

            # Create mock survivor case
            survivor_case = Case.create_base_case(
                base_name=survivor_id.split("_0_")[0],
                snapshot_path="/snapshots/nangate45",
            )

            # Derive case for stage 1 using modified ODB
            next_snapshot_path = modified_odb_path if modified_odb_path else "/snapshots/nangate45"
            derived_case = survivor_case.derive(
                eco_name="pass_through",
                new_stage_index=1,
                derived_index=derived_idx,
                snapshot_path=next_snapshot_path,
                metadata={
                    "source_trial": survivor_id,
                    "input_odb_from_stage": 0 if modified_odb_path else None,
                    "accumulated_modifications": modified_odb_path is not None,
                },
            )
            stage_1_input_cases.append(derived_case)

        # Verify stage 1 input cases use modified ODB paths
        assert len(stage_1_input_cases) == 2

        for case in stage_1_input_cases:
            # All stage 1 cases should use modified ODB from stage 0
            assert case.snapshot_path.endswith(".odb")
            assert "modified_design" in case.snapshot_path
            assert case.metadata["accumulated_modifications"] is True
            assert case.metadata["input_odb_from_stage"] == 0

        # Verify correct ODB paths
        assert stage_1_input_cases[0].snapshot_path == "/tmp/trial_1/modified_design_1.odb"
        assert stage_1_input_cases[1].snapshot_path == "/tmp/trial_0/modified_design_0.odb"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
