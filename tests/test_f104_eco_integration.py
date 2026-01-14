"""Unit tests for F104: ECO integration in trial execution.

This test verifies that the Study executor properly:
1. Creates ECO instances for each trial
2. Generates trial scripts with ECO commands injected
3. Saves custom scripts to trial directories
"""

import tempfile
from pathlib import Path

import pytest

from src.controller.eco import (
    BufferInsertionECO,
    CellResizeECO,
    CellSwapECO,
    GateCloningECO,
    NoOpECO,
    PlacementDensityECO,
)
from src.controller.executor import StudyExecutor
from src.controller.types import ExecutionMode


class TestF104ECOIntegration:
    """Test ECO integration in trial execution."""

    def test_create_eco_for_trial_creates_different_ecos(self) -> None:
        """Test that _create_eco_for_trial creates different ECOs for different trials."""
        # Create a minimal study config for testing
        from src.controller.types import SafetyDomain, StageConfig, StudyConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="test_study",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=10,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Test trial 0 gets NoOpECO
            eco_0 = executor._create_eco_for_trial(trial_index=0, stage_index=0)
            assert isinstance(eco_0, NoOpECO), "Trial 0 should use NoOpECO"

            # Test subsequent trials get different ECO types (5-ECO cycle)
            eco_1 = executor._create_eco_for_trial(trial_index=1, stage_index=0)
            assert isinstance(eco_1, CellResizeECO), "Trial 1 should use CellResizeECO"

            eco_2 = executor._create_eco_for_trial(trial_index=2, stage_index=0)
            assert isinstance(eco_2, BufferInsertionECO), "Trial 2 should use BufferInsertionECO"

            eco_3 = executor._create_eco_for_trial(trial_index=3, stage_index=0)
            assert isinstance(eco_3, CellSwapECO), "Trial 3 should use CellSwapECO"

            eco_4 = executor._create_eco_for_trial(trial_index=4, stage_index=0)
            assert isinstance(eco_4, GateCloningECO), "Trial 4 should use GateCloningECO"

            eco_5 = executor._create_eco_for_trial(trial_index=5, stage_index=0)
            assert isinstance(
                eco_5, PlacementDensityECO
            ), "Trial 5 should use PlacementDensityECO"

            # Test that cycle repeats and parameters vary
            eco_6 = executor._create_eco_for_trial(trial_index=6, stage_index=0)
            assert isinstance(
                eco_6, CellResizeECO
            ), "Trial 6 should cycle back to CellResizeECO"

            # Check that parameters differ between trial 1 and trial 6
            if isinstance(eco_1, CellResizeECO) and isinstance(eco_6, CellResizeECO):
                params_1 = eco_1.metadata.parameters
                params_6 = eco_6.metadata.parameters
                assert (
                    params_1 != params_6
                ), "Different trials should have different parameters"

    def test_eco_generates_valid_tcl(self) -> None:
        """Test that ECOs generate valid TCL scripts."""
        # Test CellResizeECO
        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        tcl = eco.generate_tcl()

        assert "repair_design" in tcl, "CellResizeECO should generate repair_design command"
        assert "Pass" in tcl, "CellResizeECO should include multi-pass strategy"

        # Test BufferInsertionECO
        eco = BufferInsertionECO(max_capacitance=0.15, buffer_cell="BUF_X4")
        tcl = eco.generate_tcl()

        assert "buffer" in tcl.lower() or "repair_design" in tcl, "BufferInsertionECO should reference buffering"

        # Test CellSwapECO
        eco = CellSwapECO(path_count=50)
        tcl = eco.generate_tcl()

        assert "swap" in tcl.lower() or "repair_timing" in tcl, "CellSwapECO should reference cell swapping or repair_timing"

    def test_trial_script_with_eco_contains_eco_section(self) -> None:
        """Test that generated trial scripts contain ECO commands."""
        from src.trial_runner.tcl_generator import generate_trial_script_with_eco

        # Create an ECO
        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        eco_tcl = eco.generate_tcl()

        # Generate trial script with ECO
        script = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            eco_tcl=eco_tcl,
            output_odb_path="/work/modified_design.odb",
            pdk="nangate45",
        )

        # Verify ECO section exists
        assert "ECO APPLICATION" in script, "Script should have ECO APPLICATION section"
        assert "repair_design" in script, "Script should contain actual ECO commands"
        assert "write_db" in script, "Script should save modified ODB"
        assert "/work/modified_design.odb" in script, "Script should reference output ODB path"

    def test_trial_script_with_eco_has_before_after_sta(self) -> None:
        """Test that trial scripts run STA before and after ECO."""
        from src.trial_runner.tcl_generator import generate_trial_script_with_eco

        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        eco_tcl = eco.generate_tcl()

        script = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            eco_tcl=eco_tcl,
            pdk="nangate45",
        )

        # Verify structure: baseline STA -> ECO -> post-ECO STA
        assert "baseline STA" in script.lower() or "before ECO" in script, "Should have baseline STA"
        assert "post-ECO STA" in script or "after ECO" in script, "Should have post-ECO STA"

    def test_trial_script_with_eco_loads_and_saves_odb(self) -> None:
        """Test that trial scripts with input ODB properly load and save."""
        from src.trial_runner.tcl_generator import generate_trial_script_with_eco

        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        eco_tcl = eco.generate_tcl()

        # Use STA_CONGESTION mode which supports ODB files
        script = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            eco_tcl=eco_tcl,
            input_odb_path="/work/input_design.odb",
            output_odb_path="/work/modified_design.odb",
            pdk="nangate45",
        )

        # Verify ODB load/save
        assert "read_db" in script, "Script should load input ODB"
        assert "/work/input_design.odb" in script, "Script should reference input ODB"
        assert "write_db" in script, "Script should save modified ODB"
        assert "/work/modified_design.odb" in script, "Script should reference output ODB"

    def test_eco_metadata_includes_parameters(self) -> None:
        """Test that ECO metadata includes parameter information."""
        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)

        assert eco.metadata.name == "cell_resize", "ECO should have correct name"
        assert "size_multiplier" in eco.metadata.parameters, "Should include size_multiplier"
        assert "max_paths" in eco.metadata.parameters, "Should include max_paths"
        assert eco.metadata.parameters["size_multiplier"] == 1.5
        assert eco.metadata.parameters["max_paths"] == 100

    def test_different_trials_have_different_parameters(self) -> None:
        """Test that trials with the same ECO type get different parameters."""
        from src.controller.types import SafetyDomain, StageConfig, StudyConfig

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="test_study",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=10,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Get three CellResizeECO instances (trials 1, 6, 11 with 5-ECO cycle)
            eco_1 = executor._create_eco_for_trial(trial_index=1, stage_index=0)
            eco_6 = executor._create_eco_for_trial(trial_index=6, stage_index=0)
            eco_11 = executor._create_eco_for_trial(trial_index=11, stage_index=0)

            # All should be CellResizeECO but with different parameters
            assert isinstance(eco_1, CellResizeECO)
            assert isinstance(eco_6, CellResizeECO)
            assert isinstance(eco_11, CellResizeECO)

            params_1 = eco_1.metadata.parameters
            params_6 = eco_6.metadata.parameters
            params_11 = eco_11.metadata.parameters

            # At least one parameter should differ
            assert (
                params_1 != params_6 or params_1 != params_11 or params_6 != params_11
            ), "Different trials should explore different parameters"
