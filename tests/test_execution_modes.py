"""Tests for execution mode support (STA-only vs STA+congestion)."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.types import ExecutionMode
from src.trial_runner.tcl_generator import (
    generate_trial_script,
    write_trial_script,
)
from src.trial_runner.trial import Trial, TrialConfig


class TestTCLScriptGeneration:
    """Test TCL script generation for different execution modes."""

    def test_generate_sta_only_script(self):
        """STA-only script should include timing analysis only."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Should include STA mode marker
        assert "STA-Only" in script or "STA_ONLY" in script
        assert "Execution Mode: STA_ONLY" in script

        # Should include timing analysis
        assert "timing_report" in script.lower()
        assert "wns_ps" in script

        # Should explicitly skip congestion
        assert "congestion skipped" in script or "timing analysis only" in script

        # Should not include congestion analysis
        assert "congestion_report" not in script

    def test_generate_sta_congestion_script(self):
        """STA+congestion script should include both timing and congestion analysis."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            output_dir="/work",
            clock_period_ns=10.0,
        )

        # Should include STA+congestion mode marker
        assert "STA+Congestion" in script or "STA_CONGESTION" in script
        assert "Execution Mode: STA_CONGESTION" in script

        # Should include timing analysis
        assert "timing_report" in script.lower()
        assert "wns_ps" in script

        # Should include congestion analysis
        assert "congestion_report" in script.lower()
        assert "bins_total" in script
        assert "bins_hot" in script or "hot_ratio" in script

    def test_generate_script_with_metadata(self):
        """Generated script should include metadata when provided."""
        metadata = {"eco_name": "test_eco", "trial_id": 123}
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            metadata=metadata,
        )

        # Metadata should be present in script
        assert "Metadata" in script or "metadata" in script

    def test_generate_script_with_custom_clock_period(self):
        """Generated script should use custom clock period."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            clock_period_ns=5.5,
        )

        # Clock period should be in script
        assert "5.5" in script

    def test_write_script_to_file(self):
        """write_trial_script should create file with correct content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "subdir" / "test_script.tcl"

            result_path = write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
            )

            # File should exist
            assert result_path.exists()
            assert result_path == script_path

            # Parent directory should be created
            assert result_path.parent.exists()

            # Content should be correct
            content = result_path.read_text()
            assert "STA" in content
            assert "test_design" in content

    def test_unsupported_execution_mode_raises_error(self):
        """Unsupported execution mode should raise ValueError."""
        # Create a fake execution mode
        with pytest.raises(ValueError, match="Unsupported execution mode"):
            generate_trial_script(
                execution_mode="invalid_mode",  # type: ignore
                design_name="test_design",
            )


class TestTrialConfigExecutionMode:
    """Test TrialConfig execution mode field."""

    def test_trial_config_has_execution_mode_field(self):
        """TrialConfig should have execution_mode field."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            execution_mode=ExecutionMode.STA_ONLY,
        )

        assert hasattr(config, "execution_mode")
        assert config.execution_mode == ExecutionMode.STA_ONLY

    def test_trial_config_default_execution_mode(self):
        """TrialConfig should default to STA_ONLY if not specified."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        assert config.execution_mode == ExecutionMode.STA_ONLY

    def test_trial_config_sta_congestion_mode(self):
        """TrialConfig should support STA_CONGESTION mode."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            execution_mode=ExecutionMode.STA_CONGESTION,
        )

        assert config.execution_mode == ExecutionMode.STA_CONGESTION


class TestExecutionModeIntegration:
    """Integration tests for execution modes with Trial execution."""

    def test_sta_only_trial_produces_timing_metrics_only(self):
        """STA-only trial should produce timing metrics but not congestion metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Generate STA-only script
            script_path = tmpdir_path / "run_sta.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
                output_dir="/work",
            )

            # Create trial config
            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=str(script_path),
                execution_mode=ExecutionMode.STA_ONLY,
            )

            # Create trial
            trial = Trial(config, artifacts_root=str(tmpdir_path))

            # Execute trial
            result = trial.execute()

            # Should succeed
            assert result.success

            # Should have timing metrics
            assert "wns_ps" in result.metrics
            assert "tns_ps" in result.metrics

            # Should NOT have congestion metrics
            assert "bins_total" not in result.metrics
            assert "bins_hot" not in result.metrics
            assert "hot_ratio" not in result.metrics

            # Execution mode should be in metadata
            assert config.execution_mode == ExecutionMode.STA_ONLY

    def test_sta_congestion_trial_produces_both_metrics(self):
        """STA+congestion trial should produce both timing and congestion metrics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Generate STA+congestion script
            script_path = tmpdir_path / "run_sta_congestion.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test_design",
                output_dir="/work",
            )

            # Create trial config
            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=str(script_path),
                execution_mode=ExecutionMode.STA_CONGESTION,
            )

            # Create trial
            trial = Trial(config, artifacts_root=str(tmpdir_path))

            # Execute trial
            result = trial.execute()

            # Should succeed
            assert result.success

            # Should have timing metrics
            assert "wns_ps" in result.metrics
            assert "tns_ps" in result.metrics

            # Should have congestion metrics
            assert "bins_total" in result.metrics
            assert "bins_hot" in result.metrics
            assert "hot_ratio" in result.metrics

            # Execution mode should be in metadata
            assert config.execution_mode == ExecutionMode.STA_CONGESTION

    def test_sta_only_is_faster_than_sta_congestion(self):
        """STA-only mode should be faster than STA+congestion mode."""
        # This is a behavioral test, not a strict performance test
        # We just verify that STA-only doesn't do congestion analysis

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Generate both scripts
            sta_script = tmpdir_path / "run_sta.tcl"
            sta_cong_script = tmpdir_path / "run_sta_congestion.tcl"

            write_trial_script(
                script_path=sta_script,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
            )
            write_trial_script(
                script_path=sta_cong_script,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test_design",
            )

            # STA-only script should be shorter (less work)
            sta_content = sta_script.read_text()
            sta_cong_content = sta_cong_script.read_text()

            # STA+congestion should have more content (congestion section)
            assert len(sta_cong_content) > len(sta_content)

            # STA-only should not have congestion section
            assert "Congestion" not in sta_content or "congestion skipped" in sta_content.lower()

            # STA+congestion should have congestion section
            assert "Congestion" in sta_cong_content


class TestExecutionModeArtifacts:
    """Test artifact generation for different execution modes."""

    def test_sta_only_artifacts_include_timing_report_only(self):
        """STA-only mode artifacts should include timing report but not congestion report."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            script_path = tmpdir_path / "run_sta.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
                output_dir="/work",
            )

            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=str(script_path),
                execution_mode=ExecutionMode.STA_ONLY,
            )

            trial = Trial(config, artifacts_root=str(tmpdir_path))
            result = trial.execute()

            # Should have timing report
            assert result.artifacts.timing_report is not None
            assert result.artifacts.timing_report.exists()

            # Should NOT have congestion report
            assert result.artifacts.congestion_report is None

    def test_sta_congestion_artifacts_include_both_reports(self):
        """STA+congestion mode artifacts should include both timing and congestion reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            script_path = tmpdir_path / "run_sta_congestion.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test_design",
                output_dir="/work",
            )

            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=str(script_path),
                execution_mode=ExecutionMode.STA_CONGESTION,
            )

            trial = Trial(config, artifacts_root=str(tmpdir_path))
            result = trial.execute()

            # Should have timing report
            assert result.artifacts.timing_report is not None
            assert result.artifacts.timing_report.exists()

            # Should have congestion report
            assert result.artifacts.congestion_report is not None
            assert result.artifacts.congestion_report.exists()


class TestExecutionModeMetrics:
    """Test metrics parsing for different execution modes."""

    def test_sta_only_metrics_json_excludes_congestion(self):
        """Metrics JSON from STA-only mode should not include congestion fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            script_path = tmpdir_path / "run_sta.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
                output_dir="/work",
            )

            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=str(script_path),
                execution_mode=ExecutionMode.STA_ONLY,
            )

            trial = Trial(config, artifacts_root=str(tmpdir_path))
            result = trial.execute()

            # Read metrics.json directly
            metrics_file = trial.trial_dir / "metrics.json"
            assert metrics_file.exists()

            with open(metrics_file) as f:
                metrics = json.load(f)

            # Should have timing fields
            assert "wns_ps" in metrics
            assert "execution_mode" in metrics
            assert metrics["execution_mode"] == "sta_only"

            # Should NOT have congestion fields
            assert "bins_total" not in metrics
            assert "bins_hot" not in metrics
            assert "hot_ratio" not in metrics

    def test_sta_congestion_metrics_json_includes_both(self):
        """Metrics JSON from STA+congestion mode should include both timing and congestion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            script_path = tmpdir_path / "run_sta_congestion.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test_design",
                output_dir="/work",
            )

            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=str(script_path),
                execution_mode=ExecutionMode.STA_CONGESTION,
            )

            trial = Trial(config, artifacts_root=str(tmpdir_path))
            result = trial.execute()

            # Read metrics.json directly
            metrics_file = trial.trial_dir / "metrics.json"
            assert metrics_file.exists()

            with open(metrics_file) as f:
                metrics = json.load(f)

            # Should have timing fields
            assert "wns_ps" in metrics
            assert "execution_mode" in metrics
            assert metrics["execution_mode"] == "sta_congestion"

            # Should have congestion fields
            assert "bins_total" in metrics
            assert "bins_hot" in metrics
            assert "hot_ratio" in metrics
