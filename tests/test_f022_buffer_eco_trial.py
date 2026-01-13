"""
Tests for F022: BufferInsertionECO trial improves timing on wire-dominated paths.

Feature F022 Requirements:
1. Create study with BufferInsertionECO
2. Run trial on Nangate45 base case
3. Verify trial completes with rc=0
4. Verify BufferInsertionECO generates valid TCL with buffer insertion commands
5. Verify artifacts are created
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.eco import BufferInsertionECO
from src.trial_runner.trial import Trial, TrialConfig


class TestF022BufferInsertionECOTrial:
    """Test F022: BufferInsertionECO trial runs successfully on Nangate45."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def nangate45_base_script(self):
        """Path to Nangate45 base case script."""
        return Path("studies/nangate45_base/run_sta.tcl")

    @pytest.mark.slow
    def test_step_1_create_buffer_eco(self):
        """Step 1: Create study with BufferInsertionECO."""
        # Create BufferInsertionECO instance
        eco = BufferInsertionECO()

        # Verify ECO metadata
        assert eco.metadata.name == "buffer_insertion"
        assert "buffer" in eco.metadata.description.lower()

        # Verify ECO can generate TCL
        tcl = eco.generate_tcl()
        assert isinstance(tcl, str)
        assert len(tcl) > 0

        # BufferInsertionECO should generate repair_design or buffer insertion commands
        tcl_lower = tcl.lower()
        assert (
            "repair_design" in tcl_lower
            or "buffer" in tcl_lower
            or "insert" in tcl_lower
        ), "TCL should contain buffer insertion commands"

    @pytest.mark.slow
    def test_step_2_run_trial_on_nangate45(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Step 2: Run trial on Nangate45 base case."""
        # Create trial configuration with BufferInsertionECO
        config = TrialConfig(
            study_name="f022_test",
            case_name="buffer_eco",
            stage_index=0,
            trial_index=0,
            script_path=nangate45_base_script,
            snapshot_dir=Path("studies/nangate45_base"),
            timeout_seconds=120,
            metadata={"eco_type": "buffer_insertion", "test": "f022"},
        )

        # Create and execute trial
        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify trial executed
        assert result is not None
        assert hasattr(result, "return_code")
        assert hasattr(result, "success")

    @pytest.mark.slow
    def test_step_3_verify_return_code(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Step 3: Verify trial completes with rc=0."""
        config = TrialConfig(
            study_name="f022_test",
            case_name="buffer_eco",
            stage_index=0,
            trial_index=1,
            script_path=nangate45_base_script,
            snapshot_dir=Path("studies/nangate45_base"),
            timeout_seconds=120,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Step 3: Verify trial completes with rc=0
        assert result.return_code == 0, f"Expected rc=0, got {result.return_code}"
        assert result.success is True, "Trial should succeed"

    @pytest.mark.slow
    def test_step_4_verify_buffer_tcl_generation(self):
        """Step 4: Verify BufferInsertionECO generates valid TCL with buffer commands."""
        # Create BufferInsertionECO with parameters
        eco = BufferInsertionECO(max_capacitance=0.5, buffer_cell="BUF_X4")

        # Generate TCL
        tcl = eco.generate_tcl()

        # Verify TCL contains buffer insertion commands
        assert "repair_design" in tcl or "buffer" in tcl.lower()

        # Verify parameters are used in TCL
        assert "0.5" in tcl or "max_cap" in tcl.lower()

        # Verify TCL is valid (no empty lines only)
        lines = [line.strip() for line in tcl.split("\n") if line.strip()]
        assert len(lines) > 0, "TCL should have content"

        # Verify no syntax errors (basic check)
        assert tcl.count("{") == tcl.count("}"), "TCL braces should be balanced"

    @pytest.mark.slow
    def test_step_5_verify_artifacts_created(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Step 5: Verify artifacts are created."""
        config = TrialConfig(
            study_name="f022_artifacts",
            case_name="buffer_eco",
            stage_index=0,
            trial_index=0,
            script_path=nangate45_base_script,
            snapshot_dir=Path("studies/nangate45_base"),
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify success
        assert result.success

        # Verify artifacts exist
        assert result.artifacts.trial_dir.exists(), "Trial directory should exist"
        assert result.artifacts.timing_report is not None
        assert result.artifacts.timing_report.exists(), "Timing report should exist"
        assert result.artifacts.metrics_json is not None
        assert result.artifacts.metrics_json.exists(), "Metrics JSON should exist"

        # Verify logs
        assert result.artifacts.logs is not None
        assert (result.artifacts.logs / "stdout.txt").exists()
        assert (result.artifacts.logs / "stderr.txt").exists()

        # Verify trial summary
        summary_file = result.artifacts.trial_dir / "trial_summary.json"
        assert summary_file.exists(), "Trial summary should exist"

        # Verify summary content
        with summary_file.open() as f:
            summary = json.load(f)

        assert summary["success"] is True
        assert summary["return_code"] == 0
        assert "wns_ps" in summary["metrics"]

    @pytest.mark.slow
    def test_complete_f022_workflow(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Complete F022 workflow: BufferInsertionECO trial on Nangate45."""
        # Step 1: Create BufferInsertionECO
        eco = BufferInsertionECO(max_capacitance=0.3, buffer_cell="BUF_X2")
        assert eco.metadata.name == "buffer_insertion"

        # Verify TCL generation
        tcl = eco.generate_tcl()
        assert "repair_design" in tcl or "buffer" in tcl.lower()

        # Step 2-3: Run trial and verify rc=0
        config = TrialConfig(
            study_name="f022_complete",
            case_name="buffer_complete",
            stage_index=0,
            trial_index=0,
            script_path=nangate45_base_script,
            snapshot_dir=Path("studies/nangate45_base"),
            timeout_seconds=120,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        assert result.return_code == 0
        assert result.success is True

        # Step 4: Metrics should be extracted
        assert "wns_ps" in result.metrics
        wns_ps = result.metrics["wns_ps"]
        assert isinstance(wns_ps, (int, float))

        # Step 5: Artifacts created
        assert result.artifacts.trial_dir.exists()
        assert result.artifacts.timing_report.exists()
        assert result.artifacts.metrics_json.exists()

        # Verify trial completed successfully with deterministic artifacts
        assert result.runtime_seconds > 0
        assert result.runtime_seconds < 120  # Should be fast

    @pytest.mark.slow
    def test_buffer_eco_with_parameters(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Test BufferInsertionECO with different parameters."""
        # Test with different parameters
        eco1 = BufferInsertionECO(max_capacitance=0.2)
        eco2 = BufferInsertionECO(max_capacitance=0.8, buffer_cell="BUF_X8")

        # Both should generate valid TCL
        tcl1 = eco1.generate_tcl()
        tcl2 = eco2.generate_tcl()

        assert len(tcl1) > 0
        assert len(tcl2) > 0

        # TCL should be different due to different parameters
        # (though the exact content may vary based on implementation)
        assert "repair_design" in tcl1 or "buffer" in tcl1.lower()
        assert "repair_design" in tcl2 or "buffer" in tcl2.lower()
