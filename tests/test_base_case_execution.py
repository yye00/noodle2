"""
Tests for Feature #3: Execute Nangate45 base case with no-op ECO.

This is the critical smoke test that validates the entire end-to-end stack:
- Load Nangate45 base case snapshot
- Execute with empty/no-op ECO
- Verify tool return code rc == 0
- Confirm report_checks timing report is produced
- Parse timing report and extract wns_ps value
- Verify artifact directory contains required files
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.trial_runner.trial import Trial, TrialConfig


class TestBaseCase:
    """Test base case execution - Gate 0 validation."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def nangate45_base_script(self):
        """Path to Nangate45 base case script."""
        return Path("studies/nangate45_base/run_sta.tcl")

    def test_base_case_script_exists(self, nangate45_base_script):
        """Step 1: Verify base case script exists."""
        assert nangate45_base_script.exists(), f"Base case script not found: {nangate45_base_script}"

    @pytest.mark.slow
    def test_base_case_execution_success(self, nangate45_base_script, temp_artifacts_dir):
        """
        Feature #3: Execute Nangate45 base case and verify structural runnability.

        Steps:
        1. Load Nangate45 base case snapshot
        2. Execute with empty/no-op ECO
        3. Verify tool return code rc == 0
        4. Confirm report_checks timing report is produced
        5. Parse timing report and extract wns_ps value
        6. Verify artifact directory contains required files
        """
        # Create trial configuration
        config = TrialConfig(
            study_name="nangate45_base",
            case_name="base",
            stage_index=0,
            trial_index=0,
            script_path=nangate45_base_script,
            snapshot_dir=None,  # No snapshot needed for this minimal test
            timeout_seconds=120,
            metadata={"test": "base_case_execution"},
        )

        # Create and execute trial
        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Step 3: Verify tool return code rc == 0
        assert result.return_code == 0, f"Expected return code 0, got {result.return_code}"
        assert result.success is True, "Trial should succeed"

        # Step 4: Verify timing report is produced
        assert result.artifacts.timing_report is not None, "Timing report should be produced"
        assert result.artifacts.timing_report.exists(), "Timing report file should exist"

        # Step 5: Parse timing report and extract wns_ps value
        assert "wns_ps" in result.metrics, "Metrics should contain wns_ps"
        wns_ps = result.metrics["wns_ps"]
        assert isinstance(wns_ps, (int, float)), f"wns_ps should be numeric, got {type(wns_ps)}"
        assert wns_ps > 0, "WNS should be positive (timing met)"

        # Step 6: Verify artifact directory contains required files
        assert result.artifacts.trial_dir.exists(), "Trial directory should exist"
        assert result.artifacts.metrics_json is not None, "Metrics JSON should be produced"
        assert result.artifacts.metrics_json.exists(), "Metrics JSON file should exist"

        # Verify logs were captured
        assert result.artifacts.logs is not None, "Logs directory should exist"
        assert (result.artifacts.logs / "stdout.txt").exists(), "stdout.txt should exist"
        assert (result.artifacts.logs / "stderr.txt").exists(), "stderr.txt should exist"

        # Verify trial summary was written
        summary_file = result.artifacts.trial_dir / "trial_summary.json"
        assert summary_file.exists(), "Trial summary should be written"

        # Verify summary is valid JSON and contains expected fields
        with summary_file.open() as f:
            summary = json.load(f)

        assert summary["study_name"] == "nangate45_base"
        assert summary["case_name"] == "base"
        assert summary["stage_index"] == 0
        assert summary["trial_index"] == 0
        assert summary["success"] is True
        assert summary["return_code"] == 0

    @pytest.mark.slow
    def test_base_case_metrics_extraction(self, nangate45_base_script, temp_artifacts_dir):
        """Verify metrics are correctly extracted from base case execution."""
        config = TrialConfig(
            study_name="nangate45_base",
            case_name="base",
            stage_index=0,
            trial_index=1,  # Different trial index
            script_path=nangate45_base_script,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify metrics
        assert result.success is True
        assert "wns_ps" in result.metrics, "Should extract WNS"

        # Should extract TNS if available
        if "tns_ps" in result.metrics:
            tns_ps = result.metrics["tns_ps"]
            assert isinstance(tns_ps, (int, float)), "TNS should be numeric"

        # Verify metrics are reasonable
        wns_ps = result.metrics["wns_ps"]
        assert -100000 < wns_ps < 100000, "WNS should be in reasonable range"

    @pytest.mark.slow
    def test_base_case_artifact_index(self, nangate45_base_script, temp_artifacts_dir):
        """Verify artifact index is generated correctly."""
        config = TrialConfig(
            study_name="nangate45_base",
            case_name="base",
            stage_index=0,
            trial_index=2,
            script_path=nangate45_base_script,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Get artifact index
        index = trial.get_artifact_index()

        # Verify index structure
        assert "trial_id" in index
        assert "trial_dir" in index
        assert "artifacts" in index
        assert "metadata" in index

        # Verify trial ID format
        expected_id = "nangate45_base/base/stage_0/trial_2"
        assert index["trial_id"] == expected_id

        # Verify metadata
        assert index["metadata"]["study_name"] == "nangate45_base"
        assert index["metadata"]["case_name"] == "base"
        assert index["metadata"]["stage_index"] == 0
        assert index["metadata"]["trial_index"] == 2

    @pytest.mark.slow
    def test_base_case_deterministic_artifact_path(self, nangate45_base_script, temp_artifacts_dir):
        """Verify artifact paths follow deterministic naming contract."""
        config = TrialConfig(
            study_name="nangate45_base",
            case_name="base",
            stage_index=0,
            trial_index=3,
            script_path=nangate45_base_script,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)

        # Verify trial directory follows naming contract
        expected_path = (
            temp_artifacts_dir / "nangate45_base" / "base" / "stage_0" / "trial_3"
        )
        assert trial.trial_dir == expected_path

        # Execute and verify artifacts are in expected location
        result = trial.execute()
        assert result.artifacts.trial_dir == expected_path
        assert result.artifacts.trial_dir.exists()

    @pytest.mark.slow
    def test_base_case_runtime_tracking(self, nangate45_base_script, temp_artifacts_dir):
        """Verify runtime is tracked correctly."""
        config = TrialConfig(
            study_name="nangate45_base",
            case_name="base",
            stage_index=0,
            trial_index=4,
            script_path=nangate45_base_script,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify runtime is tracked
        assert result.runtime_seconds > 0, "Runtime should be positive"
        assert result.runtime_seconds < 60, "Simple test should complete quickly"

    @pytest.mark.slow
    def test_base_case_multiple_trials_isolated(self, nangate45_base_script, temp_artifacts_dir):
        """Verify multiple trials are isolated in separate directories."""
        configs = [
            TrialConfig(
                study_name="nangate45_base",
                case_name="base",
                stage_index=0,
                trial_index=i,
                script_path=nangate45_base_script,
            )
            for i in range(3)
        ]

        results = []
        for config in configs:
            trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
            result = trial.execute()
            results.append(result)

        # Verify all succeeded
        assert all(r.success for r in results), "All trials should succeed"

        # Verify trials are in different directories
        trial_dirs = [r.artifacts.trial_dir for r in results]
        assert len(set(trial_dirs)) == 3, "Each trial should have unique directory"

        # Verify all artifacts exist
        for result in results:
            assert result.artifacts.timing_report.exists()
            assert result.artifacts.metrics_json.exists()
