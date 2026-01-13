"""Verification test for F104: ECO execution infrastructure is in place.

This test verifies that the infrastructure for ECO execution is properly implemented,
without requiring a full study run.
"""

import tempfile
from pathlib import Path

from src.controller.executor import StudyExecutor
from src.controller.types import (
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)


class TestF104Infrastructure:
    """Test that F104 infrastructure is correctly implemented."""

    def test_step_1_multiple_trials_have_different_eco_parameters(self) -> None:
        """Step 1: Verify multiple trials get different ECO parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal study config
            config = StudyConfig(
                name="test_eco_params",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test",
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

            # Get ECOs for several trials
            ecos = []
            for i in range(10):
                eco = executor._create_eco_for_trial(trial_index=i, stage_index=0)
                ecos.append(eco)

            # Collect all parameter sets
            param_sets = []
            for eco in ecos[1:]:  # Skip trial 0 (NoOpECO)
                if eco:
                    param_sets.append(str(eco.metadata.parameters))

            # Verify we have multiple different parameter sets
            unique_params = len(set(param_sets))
            assert unique_params > 1, (
                f"Expected multiple different ECO parameter sets, got {unique_params}. "
                f"Parameter sets: {param_sets[:5]}"
            )

    def test_step_4_trial_scripts_contain_eco_commands(self) -> None:
        """Step 4: Verify trial scripts contain actual ECO commands."""
        from src.trial_runner.tcl_generator import generate_trial_script_with_eco

        # Create a CellResizeECO
        from src.controller.eco import CellResizeECO

        eco = CellResizeECO(size_multiplier=1.5, max_paths=100)
        eco_tcl = eco.generate_tcl()

        # Generate trial script with ECO
        script = generate_trial_script_with_eco(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            eco_tcl=eco_tcl,
            pdk="nangate45",
        )

        # Verify ECO commands are present
        assert "repair_design" in script, "Script must contain repair_design command"
        assert "ECO APPLICATION" in script, "Script must have ECO APPLICATION section"
        assert "write_db" in script, "Script must save modified ODB"

    def test_infrastructure_generates_unique_scripts_per_trial(self) -> None:
        """Verify that different trials generate different scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="test_unique_scripts",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=5,
                        survivor_count=2,
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

            # Generate TCL for multiple trials
            scripts = []
            for trial_idx in range(1, 5):  # Trials 1-4 (skip 0 which is NoOp)
                eco = executor._create_eco_for_trial(trial_idx, stage_index=0)
                if eco:
                    tcl = eco.generate_tcl()
                    scripts.append(tcl)

            # All scripts should be non-empty
            assert all(len(s) > 0 for s in scripts), "All ECO scripts should be non-empty"

            # At least some scripts should differ (different ECO types or parameters)
            unique_scripts = len(set(scripts))
            assert unique_scripts > 1, (
                f"Expected different scripts for different trials, got {unique_scripts} unique scripts"
            )
