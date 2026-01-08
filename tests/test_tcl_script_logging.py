"""
Tests for Feature: Log OpenROAD TCL script invocations for reproducibility.

This feature ensures that every trial saves a copy of the exact TCL script
that was executed, enabling manual reproduction of any trial.

Feature Steps:
1. Generate TCL script for trial execution
2. Write TCL script to trial artifacts
3. Execute OpenROAD with logged TCL script
4. Verify trial is reproducible by re-running logged script
5. Enable manual reproduction of any trial
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from src.controller.types import ExecutionMode
from src.trial_runner.tcl_generator import write_trial_script
from src.trial_runner.trial import Trial, TrialConfig


class TestTCLScriptGeneration:
    """Test Step 1: Generate TCL script for trial execution."""

    @pytest.fixture
    def temp_script_dir(self):
        """Create temporary directory for scripts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_generate_sta_only_script(self, temp_script_dir):
        """Verify STA-only TCL script can be generated."""
        script_path = temp_script_dir / "test_sta.tcl"

        result_path = write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            clock_period_ns=10.0,
        )

        assert result_path.exists(), "Script should be written to file"
        assert result_path == script_path, "Should return correct path"

        # Verify script content
        content = script_path.read_text()
        assert "STA_ONLY" in content, "Should indicate STA-only mode"
        assert "test_design" in content, "Should include design name"
        assert "exit 0" in content, "Should have exit command"

    def test_generate_sta_congestion_script(self, temp_script_dir):
        """Verify STA+congestion TCL script can be generated."""
        script_path = temp_script_dir / "test_congestion.tcl"

        result_path = write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design_cong",
            clock_period_ns=8.0,
        )

        assert result_path.exists(), "Script should be written to file"

        # Verify script content
        content = script_path.read_text()
        assert "STA_CONGESTION" in content, "Should indicate STA+congestion mode"
        assert "global_route" in content or "congestion" in content, "Should mention congestion analysis"

    def test_script_includes_metadata(self, temp_script_dir):
        """Verify TCL script includes metadata when provided."""
        script_path = temp_script_dir / "test_meta.tcl"
        metadata = {"eco_name": "buffer_insertion", "stage": 1}

        write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            metadata=metadata,
        )

        content = script_path.read_text()
        assert "buffer_insertion" in content or "Metadata" in content, "Should include metadata in comments"

    def test_script_includes_seed(self, temp_script_dir):
        """Verify TCL script includes OpenROAD seed for determinism."""
        script_path = temp_script_dir / "test_seed.tcl"

        write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        content = script_path.read_text()
        assert "42" in content, "Should include seed value"
        assert "seed" in content.lower(), "Should mention seed"


class TestTCLScriptCopyToArtifacts:
    """Test Step 2: Write TCL script to trial artifacts."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def temp_script(self):
        """Create a temporary TCL script."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tcl", delete=False) as f:
            f.write("# Test TCL script\nputs \"Hello from test script\"\nexit 0\n")
            script_path = Path(f.name)
        yield script_path
        # Cleanup
        if script_path.exists():
            script_path.unlink()

    def test_script_copied_to_trial_directory(self, temp_script, temp_artifacts_dir):
        """Verify TCL script is copied to trial artifacts."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=temp_script,
            timeout_seconds=30,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)

        # Copy script to trial directory
        copied_script = trial._copy_script_to_trial_dir()

        # Verify script was copied
        assert copied_script.exists(), "Script should be copied to trial directory"
        assert copied_script.name == "trial_script.tcl", "Script should be named trial_script.tcl"
        assert copied_script.parent == trial.trial_dir, "Script should be in trial directory"

        # Verify content matches original
        original_content = temp_script.read_text()
        copied_content = copied_script.read_text()
        assert copied_content == original_content, "Script content should match original"

    def test_script_copy_preserves_exact_content(self, temp_artifacts_dir):
        """Verify script copy preserves exact content including comments and whitespace."""
        # Create script with specific formatting
        script_content = """# Test script with formatting
# Comment line 1
# Comment line 2

puts "Line with spaces"
set var "value"

exit 0
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tcl", delete=False) as f:
            f.write(script_content)
            script_path = Path(f.name)

        try:
            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=script_path,
            )

            trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
            copied_script = trial._copy_script_to_trial_dir()

            # Verify exact match
            copied_content = copied_script.read_text()
            assert copied_content == script_content, "Script content should be preserved exactly"
        finally:
            if script_path.exists():
                script_path.unlink()

    def test_script_copy_fails_if_script_not_found(self, temp_artifacts_dir):
        """Verify error is raised if script file doesn't exist."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/nonexistent/script.tcl",
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)

        with pytest.raises(FileNotFoundError):
            trial._copy_script_to_trial_dir()


class TestTCLScriptInTrialExecution:
    """Test Step 3: Execute OpenROAD with logged TCL script."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def test_script(self):
        """Path to test script."""
        return Path("studies/nangate45_base/run_sta.tcl")

    @pytest.mark.slow
    def test_script_logged_during_execution(self, test_script, temp_artifacts_dir):
        """Verify TCL script is logged when trial is executed."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=120,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify script was logged
        assert result.artifacts.script is not None, "Script artifact should be present"
        assert result.artifacts.script.exists(), "Script file should exist"
        assert result.artifacts.script.name == "trial_script.tcl", "Script should have standard name"

        # Verify script is in trial directory
        expected_path = trial.trial_dir / "trial_script.tcl"
        assert result.artifacts.script == expected_path, "Script should be in trial directory"

    @pytest.mark.slow
    def test_script_accessible_in_trial_summary(self, test_script, temp_artifacts_dir):
        """Verify script path is included in trial summary JSON."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=120,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Check artifacts dictionary includes script
        artifacts_dict = result.artifacts.to_dict()
        assert "script" in artifacts_dict, "Artifacts dict should include script"
        assert artifacts_dict["script"] is not None, "Script path should not be None"
        assert "trial_script.tcl" in artifacts_dict["script"], "Script path should reference trial_script.tcl"


class TestTCLScriptReproducibility:
    """Test Step 4: Verify trial is reproducible by re-running logged script."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def test_script(self):
        """Path to test script."""
        return Path("studies/nangate45_base/run_sta.tcl")

    @pytest.mark.slow
    def test_logged_script_is_valid_tcl(self, test_script, temp_artifacts_dir):
        """Verify logged script is valid TCL that can be executed."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=120,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Get logged script
        logged_script = result.artifacts.script
        assert logged_script is not None, "Logged script should exist"

        # Verify it's valid TCL (has basic TCL structure)
        content = logged_script.read_text()
        assert content.strip() != "", "Script should not be empty"
        assert "puts" in content or "set" in content or "exit" in content, "Should contain TCL commands"

    @pytest.mark.slow
    def test_script_can_be_reexecuted_manually(self, test_script, temp_artifacts_dir):
        """Verify logged script can be re-executed to reproduce trial."""
        # Execute trial once
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=120,
        )

        trial1 = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result1 = trial1.execute()

        # Get the logged script
        logged_script = result1.artifacts.script
        assert logged_script is not None, "Logged script should exist"

        # Create a new temporary directory for second execution
        with tempfile.TemporaryDirectory() as tmpdir2:
            temp_artifacts_dir2 = Path(tmpdir2)

            # Execute trial again using the logged script
            config2 = TrialConfig(
                study_name="test_study_replay",
                case_name="test_case",
                stage_index=0,
                trial_index=1,
                script_path=logged_script,  # Use logged script from first trial
                timeout_seconds=120,
            )

            trial2 = Trial(config=config2, artifacts_root=temp_artifacts_dir2)
            result2 = trial2.execute()

            # Both executions should succeed
            assert result1.success, "First execution should succeed"
            assert result2.success, "Second execution (using logged script) should succeed"

            # Both should produce timing metrics
            assert "wns_ps" in result1.metrics, "First execution should have WNS"
            assert "wns_ps" in result2.metrics, "Second execution should have WNS"

            # Metrics should be similar (within tolerance for any non-determinism)
            # Note: For truly deterministic execution, use openroad_seed
            # Here we just verify both produced valid results
            assert result1.metrics["wns_ps"] > 0, "First WNS should be positive"
            assert result2.metrics["wns_ps"] > 0, "Second WNS should be positive"


class TestManualReproduction:
    """Test Step 5: Enable manual reproduction of any trial."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def test_script(self):
        """Path to test script."""
        return Path("studies/nangate45_base/run_sta.tcl")

    @pytest.mark.slow
    def test_manual_reproduction_instructions_via_script(self, test_script, temp_artifacts_dir):
        """Verify script provides clear path for manual reproduction."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=120,
            metadata={"eco": "buffer_insertion", "note": "test run"},
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify script is accessible
        script_path = result.artifacts.script
        assert script_path is not None, "Script should be logged"
        assert script_path.exists(), "Script file should exist"

        # Manual reproduction would involve:
        # 1. Navigate to trial directory
        trial_dir = result.artifacts.trial_dir
        assert trial_dir.exists(), "Trial directory should exist"

        # 2. Locate the script
        manual_script = trial_dir / "trial_script.tcl"
        assert manual_script.exists(), "Script should be in well-known location"

        # 3. Execute with: openroad -exit trial_script.tcl
        # (We verify the script is present; actual execution tested elsewhere)
        assert manual_script.is_file(), "Script should be a file"
        assert manual_script.stat().st_size > 0, "Script should not be empty"

    def test_script_location_documented_in_artifacts(self, test_script, temp_artifacts_dir):
        """Verify script location is clearly documented."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=30,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)

        # Even before execution, we can verify the standardized path
        expected_script_path = trial.trial_dir / "trial_script.tcl"

        # After copying script
        trial._copy_script_to_trial_dir()

        # Verify script is at expected location
        assert expected_script_path.exists(), "Script should be at standardized location"

    @pytest.mark.slow
    def test_all_required_artifacts_present_for_reproduction(self, test_script, temp_artifacts_dir):
        """Verify all artifacts needed for reproduction are present."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=120,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # For manual reproduction, we need:
        # 1. The script (primary requirement)
        assert result.artifacts.script is not None, "Script is required"
        assert result.artifacts.script.exists(), "Script file must exist"

        # 2. Execution logs (for debugging if reproduction fails)
        assert result.artifacts.logs is not None, "Logs are helpful for debugging"
        assert (result.artifacts.logs / "stdout.txt").exists(), "stdout should be logged"
        assert (result.artifacts.logs / "stderr.txt").exists(), "stderr should be logged"

        # 3. Provenance information (container image, etc.)
        assert result.provenance is not None, "Provenance helps ensure same environment"
        assert result.provenance.container_image is not None, "Container image should be logged"

        # 4. Trial summary (metrics for validation)
        summary_file = result.artifacts.trial_dir / "trial_summary.json"
        assert summary_file.exists(), "Summary helps validate reproduction"


class TestEndToEndScriptLogging:
    """End-to-end integration tests for TCL script logging."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def test_script(self):
        """Path to test script."""
        return Path("studies/nangate45_base/run_sta.tcl")

    @pytest.mark.slow
    def test_complete_workflow_with_script_logging(self, test_script, temp_artifacts_dir):
        """Test complete workflow: generate → execute → log → verify."""
        # Step 1: Configure trial
        config = TrialConfig(
            study_name="complete_test",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=test_script,
            timeout_seconds=120,
            metadata={"purpose": "end_to_end_test"},
        )

        # Step 2: Execute trial (this should log the script automatically)
        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Step 3: Verify execution succeeded
        assert result.success, "Trial should succeed"
        assert result.return_code == 0, "Return code should be 0"

        # Step 4: Verify script was logged
        assert result.artifacts.script is not None, "Script should be logged"
        assert result.artifacts.script.exists(), "Script file should exist"

        # Step 5: Verify script is in trial directory
        assert result.artifacts.script.parent == result.artifacts.trial_dir, "Script should be in trial dir"

        # Step 6: Verify script content is valid
        script_content = result.artifacts.script.read_text()
        assert len(script_content) > 0, "Script should not be empty"
        assert "exit" in script_content, "Script should have exit command"

        # Step 7: Verify script is included in artifacts serialization
        artifacts_dict = result.artifacts.to_dict()
        assert artifacts_dict["script"] is not None, "Script should be in artifacts dict"

    @pytest.mark.slow
    def test_multiple_trials_each_have_own_script(self, test_script, temp_artifacts_dir):
        """Verify each trial gets its own copy of the script."""
        results = []

        # Execute multiple trials
        for i in range(3):
            config = TrialConfig(
                study_name="multi_trial_test",
                case_name="test_case",
                stage_index=0,
                trial_index=i,
                script_path=test_script,
                timeout_seconds=120,
            )

            trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
            result = trial.execute()
            results.append(result)

        # Verify all succeeded
        assert all(r.success for r in results), "All trials should succeed"

        # Verify each has its own script
        script_paths = [r.artifacts.script for r in results]
        assert all(s is not None for s in script_paths), "All should have scripts"
        assert all(s.exists() for s in script_paths), "All script files should exist"

        # Verify scripts are in different directories
        assert len(set(s.parent for s in script_paths)) == 3, "Scripts should be in different trial dirs"

        # Verify all scripts are named the same (standardized name)
        assert all(s.name == "trial_script.tcl" for s in script_paths), "All should use standard name"
