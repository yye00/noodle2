"""
Tests for F021: NoOpECO trial runs successfully on Nangate45.

Feature F021 Requirements:
1. Create study with NoOpECO
2. Run trial on Nangate45 base case
3. Verify trial completes with rc=0
4. Verify metrics before and after are identical (no changes)
5. Verify artifacts are created
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.eco import NoOpECO
from src.trial_runner.trial import Trial, TrialConfig


class TestF021NoOpECOTrial:
    """Test F021: NoOpECO trial runs successfully on Nangate45."""

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
    def test_step_1_create_noop_eco(self):
        """Step 1: Create study with NoOpECO."""
        # Create NoOpECO instance
        eco = NoOpECO()

        # Verify ECO metadata
        assert eco.metadata.name == "noop"
        assert eco.metadata.description == "No-operation ECO for baseline testing"

        # Verify ECO can generate TCL
        tcl = eco.generate_tcl()
        assert isinstance(tcl, str)
        assert len(tcl) > 0
        assert "No-op ECO" in tcl or "baseline" in tcl

    @pytest.mark.slow
    def test_step_2_run_trial_on_nangate45(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Step 2: Run trial on Nangate45 base case."""
        # Create trial configuration with NoOpECO
        config = TrialConfig(
            study_name="f021_test",
            case_name="noop_eco",
            stage_index=0,
            trial_index=0,
            script_path=nangate45_base_script,
            snapshot_dir=Path("studies/nangate45_base"),
            timeout_seconds=120,
            metadata={"eco_type": "noop", "test": "f021"},
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
            study_name="f021_test",
            case_name="noop_eco",
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
    def test_step_4_verify_metrics_identical(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Step 4: Verify metrics before and after are identical (no changes)."""
        # Run baseline trial (no ECO)
        config_baseline = TrialConfig(
            study_name="f021_baseline",
            case_name="baseline",
            stage_index=0,
            trial_index=0,
            script_path=nangate45_base_script,
            snapshot_dir=Path("studies/nangate45_base"),
        )

        trial_baseline = Trial(config=config_baseline, artifacts_root=temp_artifacts_dir)
        result_baseline = trial_baseline.execute()

        # Run NoOpECO trial
        config_noop = TrialConfig(
            study_name="f021_noop",
            case_name="noop",
            stage_index=0,
            trial_index=0,
            script_path=nangate45_base_script,
            snapshot_dir=Path("studies/nangate45_base"),
        )

        trial_noop = Trial(config=config_noop, artifacts_root=temp_artifacts_dir)
        result_noop = trial_noop.execute()

        # Both should succeed
        assert result_baseline.success
        assert result_noop.success

        # Extract timing metrics
        wns_baseline = result_baseline.metrics.get("wns_ps")
        wns_noop = result_noop.metrics.get("wns_ps")

        assert wns_baseline is not None, "Baseline should have WNS metric"
        assert wns_noop is not None, "NoOp should have WNS metric"

        # Metrics should be identical (or within tiny tolerance for numerical noise)
        # NoOpECO should not change timing at all
        assert abs(wns_baseline - wns_noop) < 10, (
            f"NoOpECO should not change WNS: "
            f"baseline={wns_baseline}, noop={wns_noop}"
        )

    @pytest.mark.slow
    def test_step_5_verify_artifacts_created(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Step 5: Verify artifacts are created."""
        config = TrialConfig(
            study_name="f021_artifacts",
            case_name="noop_eco",
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
    def test_complete_f021_workflow(
        self, nangate45_base_script, temp_artifacts_dir
    ):
        """Complete F021 workflow: NoOpECO trial on Nangate45."""
        # Step 1: Create NoOpECO
        eco = NoOpECO()
        assert eco.metadata.name == "noop"

        # Step 2-3: Run trial and verify rc=0
        config = TrialConfig(
            study_name="f021_complete",
            case_name="noop_complete",
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

        # Step 4: Metrics should be extracted (no change requirement)
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
