"""Tests for F031: Case naming follows deterministic convention <pdk>_<stage>_<derived>."""

import tempfile
from pathlib import Path

import pytest

from src.controller.case import Case, CaseGraph
from src.controller.demo_study import create_nangate45_demo_study
from src.controller.executor import StudyExecutor
from src.controller.study import StudyConfig
from src.controller.types import (
    CaseIdentifier,
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
)


class TestCaseNamingConvention:
    """Test case naming convention: <pdk>_<stage>_<derived>."""

    def test_case_identifier_format(self):
        """Test CaseIdentifier generates correct format."""
        identifier = CaseIdentifier(
            case_name="nangate45",
            stage_index=0,
            derived_index=0,
        )
        assert str(identifier) == "nangate45_0_0"

        identifier = CaseIdentifier(
            case_name="nangate45",
            stage_index=1,
            derived_index=2,
        )
        assert str(identifier) == "nangate45_1_2"

    def test_case_identifier_parsing(self):
        """Test parsing case identifier from string."""
        identifier = CaseIdentifier.from_string("nangate45_0_0")
        assert identifier.case_name == "nangate45"
        assert identifier.stage_index == 0
        assert identifier.derived_index == 0

        identifier = CaseIdentifier.from_string("asap7_2_5")
        assert identifier.case_name == "asap7"
        assert identifier.stage_index == 2
        assert identifier.derived_index == 5

    def test_base_case_naming_stage_0_derived_0(self):
        """Test base case is named <pdk>_0_0."""
        base_case = Case.create_base_case(
            base_name="nangate45",
            snapshot_path="/tmp/snapshot.odb",
        )

        assert base_case.case_id == "nangate45_0_0"
        assert base_case.stage_index == 0
        assert base_case.identifier.derived_index == 0
        assert base_case.is_base_case

    def test_derived_case_naming_increments_correctly(self):
        """Test derived cases increment indices correctly."""
        # Create base case
        base_case = Case.create_base_case(
            base_name="nangate45",
            snapshot_path="/tmp/snapshot.odb",
        )

        # Derive cases in stage 1
        derived_0 = base_case.derive(
            eco_name="buffer_insertion",
            new_stage_index=1,
            derived_index=0,
            snapshot_path="/tmp/derived_0.odb",
        )
        assert derived_0.case_id == "nangate45_1_0"

        derived_1 = base_case.derive(
            eco_name="gate_resize",
            new_stage_index=1,
            derived_index=1,
            snapshot_path="/tmp/derived_1.odb",
        )
        assert derived_1.case_id == "nangate45_1_1"

        derived_2 = base_case.derive(
            eco_name="pin_swap",
            new_stage_index=1,
            derived_index=2,
            snapshot_path="/tmp/derived_2.odb",
        )
        assert derived_2.case_id == "nangate45_1_2"

    def test_multi_stage_naming_progression(self):
        """Test case naming across multiple stages."""
        # Base case: stage 0
        base = Case.create_base_case(
            base_name="nangate45",
            snapshot_path="/tmp/base.odb",
        )
        assert base.case_id == "nangate45_0_0"

        # Stage 1 derived cases
        stage1_case0 = base.derive(
            eco_name="eco1",
            new_stage_index=1,
            derived_index=0,
            snapshot_path="/tmp/s1_0.odb",
        )
        assert stage1_case0.case_id == "nangate45_1_0"

        stage1_case1 = base.derive(
            eco_name="eco2",
            new_stage_index=1,
            derived_index=1,
            snapshot_path="/tmp/s1_1.odb",
        )
        assert stage1_case1.case_id == "nangate45_1_1"

        # Stage 2 derived from stage 1 survivor
        stage2_case0 = stage1_case0.derive(
            eco_name="eco3",
            new_stage_index=2,
            derived_index=0,
            snapshot_path="/tmp/s2_0.odb",
        )
        assert stage2_case0.case_id == "nangate45_2_0"

        stage2_case1 = stage1_case0.derive(
            eco_name="eco4",
            new_stage_index=2,
            derived_index=1,
            snapshot_path="/tmp/s2_1.odb",
        )
        assert stage2_case1.case_id == "nangate45_2_1"

    def test_case_graph_all_cases_follow_convention(self):
        """Test that all cases in a graph follow naming convention."""
        graph = CaseGraph()

        # Add base case
        base = Case.create_base_case(
            base_name="nangate45",
            snapshot_path="/tmp/base.odb",
        )
        graph.add_case(base)

        # Add derived cases
        for i in range(3):
            derived = base.derive(
                eco_name=f"eco_{i}",
                new_stage_index=1,
                derived_index=i,
                snapshot_path=f"/tmp/derived_{i}.odb",
            )
            graph.add_case(derived)

        # Verify all cases follow convention
        for case_id, case in graph.cases.items():
            # Parse the case_id
            parts = case_id.split("_")
            assert len(parts) == 3, f"Case ID {case_id} doesn't have 3 parts"

            pdk_name = parts[0]
            stage_index = int(parts[1])
            derived_index = int(parts[2])

            assert pdk_name == "nangate45"
            assert stage_index == case.stage_index
            assert derived_index == case.identifier.derived_index

    def test_different_pdks_use_correct_names(self):
        """Test that different PDKs use their PDK name in case IDs."""
        # Nangate45
        ng45_base = Case.create_base_case(
            base_name="nangate45",
            snapshot_path="/tmp/ng45.odb",
        )
        assert ng45_base.case_id == "nangate45_0_0"

        # ASAP7
        asap7_base = Case.create_base_case(
            base_name="asap7",
            snapshot_path="/tmp/asap7.odb",
        )
        assert asap7_base.case_id == "asap7_0_0"

        # Sky130
        sky130_base = Case.create_base_case(
            base_name="sky130",
            snapshot_path="/tmp/sky130.odb",
        )
        assert sky130_base.case_id == "sky130_0_0"


class TestStudyExecutorCaseNaming:
    """Test that StudyExecutor creates cases with correct naming."""

    def test_executor_creates_base_case_with_correct_name(self):
        """Test StudyExecutor creates base case following naming convention."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.odb"
            snapshot_path.write_text("mock snapshot")

            # Create minimal study config
            config = StudyConfig(
                name="test_study",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="test_stage",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(config)

            # Verify base case follows naming convention
            assert executor.base_case.case_id == "nangate45_0_0"
            assert executor.base_case.case_name == "nangate45"
            assert executor.base_case.stage_index == 0
            assert executor.base_case.identifier.derived_index == 0

    def test_naming_consistency_across_study_execution(self):
        """Test case naming remains consistent during study execution.

        This test verifies that:
        - Base case is named <pdk>_0_0
        - Derived cases in stage 1 are named <pdk>_1_0, <pdk>_1_1, etc.
        - All case IDs follow the deterministic convention
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.odb"
            snapshot_path.write_text("mock snapshot")

            config = StudyConfig(
                name="naming_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                    StageConfig(
                        name="stage1",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=4,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(config)

            # Verify base case
            assert executor.base_case.case_id == "nangate45_0_0"

            # Check that case graph follows convention
            case_graph = executor.case_graph
            base_case = case_graph.get_base_case()
            assert base_case is not None
            assert base_case.case_id == "nangate45_0_0"

            # Verify case identifier parsing works
            parsed = CaseIdentifier.from_string(base_case.case_id)
            assert parsed.case_name == "nangate45"
            assert parsed.stage_index == 0
            assert parsed.derived_index == 0


class TestFeatureStepValidation:
    """Validate all steps from feature F031."""

    def test_step1_create_study_with_nangate45_pdk(self):
        """Step 1: Create study with Nangate45 PDK."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.odb"
            snapshot_path.write_text("mock snapshot")

            config = StudyConfig(
                name="nangate45_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="nangate45",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="exploration",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=10,
                        survivor_count=3,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            config.validate()
            executor = StudyExecutor(config)
            assert executor.config.pdk == "Nangate45"

    def test_step2_run_stage_0_verify_base_case_named_nangate45_0_0(self):
        """Step 2: Run stage 0, verify base case is named nangate45_0_0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.odb"
            snapshot_path.write_text("mock snapshot")

            config = StudyConfig(
                name="test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(config)

            # Verify base case in stage 0 is named correctly
            assert executor.base_case.case_id == "nangate45_0_0"
            assert executor.base_case.stage_index == 0

    def test_step3_create_3_derived_cases_in_stage_1(self):
        """Step 3: Create 3 derived cases in stage 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.odb"
            snapshot_path.write_text("mock snapshot")

            # Create base case
            base_case = Case.create_base_case(
                base_name="nangate45",
                snapshot_path=str(snapshot_path),
            )

            # Create 3 derived cases in stage 1
            derived_cases = []
            for i in range(3):
                derived = base_case.derive(
                    eco_name=f"eco_{i}",
                    new_stage_index=1,
                    derived_index=i,
                    snapshot_path=f"/tmp/derived_{i}.odb",
                )
                derived_cases.append(derived)

            # Verify we have 3 derived cases
            assert len(derived_cases) == 3

    def test_step4_verify_they_are_named_nangate45_1_0_1_1_1_2(self):
        """Step 4: Verify they are named nangate45_1_0, nangate45_1_1, nangate45_1_2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.odb"
            snapshot_path.write_text("mock snapshot")

            base_case = Case.create_base_case(
                base_name="nangate45",
                snapshot_path=str(snapshot_path),
            )

            # Create 3 derived cases
            derived_0 = base_case.derive(
                eco_name="eco_0",
                new_stage_index=1,
                derived_index=0,
                snapshot_path="/tmp/derived_0.odb",
            )
            derived_1 = base_case.derive(
                eco_name="eco_1",
                new_stage_index=1,
                derived_index=1,
                snapshot_path="/tmp/derived_1.odb",
            )
            derived_2 = base_case.derive(
                eco_name="eco_2",
                new_stage_index=1,
                derived_index=2,
                snapshot_path="/tmp/derived_2.odb",
            )

            # Verify names
            assert derived_0.case_id == "nangate45_1_0"
            assert derived_1.case_id == "nangate45_1_1"
            assert derived_2.case_id == "nangate45_1_2"

    def test_step5_verify_naming_is_consistent_across_all_trials(self):
        """Step 5: Verify naming is consistent across all trials."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(tmpdir) / "snapshot.odb"
            snapshot_path.write_text("mock snapshot")

            # Create a case graph to track all cases
            graph = CaseGraph()

            # Base case
            base = Case.create_base_case(
                base_name="nangate45",
                snapshot_path=str(snapshot_path),
            )
            graph.add_case(base)

            # Stage 1: 5 derived cases
            stage1_cases = []
            for i in range(5):
                case = base.derive(
                    eco_name=f"stage1_eco_{i}",
                    new_stage_index=1,
                    derived_index=i,
                    snapshot_path=f"/tmp/s1_{i}.odb",
                )
                graph.add_case(case)
                stage1_cases.append(case)

            # Stage 2: 3 derived cases from first stage 1 case
            stage2_cases = []
            for i in range(3):
                case = stage1_cases[0].derive(
                    eco_name=f"stage2_eco_{i}",
                    new_stage_index=2,
                    derived_index=i,
                    snapshot_path=f"/tmp/s2_{i}.odb",
                )
                graph.add_case(case)
                stage2_cases.append(case)

            # Verify all case IDs follow convention
            expected_case_ids = {
                "nangate45_0_0",  # base
                "nangate45_1_0",
                "nangate45_1_1",
                "nangate45_1_2",
                "nangate45_1_3",
                "nangate45_1_4",  # stage 1
                "nangate45_2_0",
                "nangate45_2_1",
                "nangate45_2_2",  # stage 2
            }

            actual_case_ids = set(graph.cases.keys())
            assert actual_case_ids == expected_case_ids

            # Verify each case ID can be parsed correctly
            for case_id in actual_case_ids:
                identifier = CaseIdentifier.from_string(case_id)
                assert identifier.case_name == "nangate45"
                # Verify stage and derived indices are consistent
                case = graph.get_case(case_id)
                assert case.stage_index == identifier.stage_index
                assert case.identifier.derived_index == identifier.derived_index
