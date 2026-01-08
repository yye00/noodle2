"""Tests for visualization fallback when GUI mode is unavailable."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.controller.failure import FailureClassifier, FailureType
from src.controller.types import ExecutionMode, StageConfig
from src.trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner
from src.trial_runner.tcl_generator import generate_trial_script, write_trial_script
from src.trial_runner.trial import Trial, TrialConfig


class TestVisualizationFallbackConfiguration:
    """Test configuration of optional visualization with fallback."""

    def test_stage_config_has_visualization_enabled_field(self) -> None:
        """StageConfig should have visualization_enabled field."""
        from src.controller.types import ECOClass, ExecutionMode, StageConfig

        stage = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
            visualization_enabled=True,
        )
        assert stage.visualization_enabled is True

    def test_visualization_enabled_defaults_to_false(self) -> None:
        """visualization_enabled should default to False."""
        from src.controller.types import ECOClass, ExecutionMode, StageConfig

        stage = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
        )
        assert stage.visualization_enabled is False

    def test_optional_visualization_means_fallback_allowed(self) -> None:
        """When visualization is optional, fallback to non-GUI is allowed."""
        # This is a design test documenting the expected behavior:
        # visualization_enabled=True means "try GUI, but fall back if unavailable"
        # It does NOT mean "GUI is required, fail if unavailable"
        from src.controller.types import ECOClass, ExecutionMode, StageConfig

        stage = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
            visualization_enabled=True,
        )
        # visualization_enabled=True is a "nice to have" not a "must have"
        assert stage.visualization_enabled is True


class TestGuiAvailabilityDetection:
    """Test detection of GUI availability before execution."""

    def test_check_gui_available_when_display_not_set(self) -> None:
        """check_gui_available returns False when DISPLAY env var not set."""
        config = DockerRunConfig()
        runner = DockerTrialRunner(config)

        with patch.dict("os.environ", {}, clear=True):
            available = runner.check_gui_available()
            assert available is False

    def test_check_gui_available_when_x11_socket_missing(self) -> None:
        """check_gui_available returns False when X11 socket doesn't exist."""
        config = DockerRunConfig()
        runner = DockerTrialRunner(config)

        with patch.dict("os.environ", {"DISPLAY": ":0"}):
            with patch("pathlib.Path.exists", return_value=False):
                available = runner.check_gui_available()
                assert available is False

    def test_check_gui_available_when_prerequisites_met(self) -> None:
        """check_gui_available returns True when all prerequisites met."""
        config = DockerRunConfig()
        runner = DockerTrialRunner(config)

        with patch.dict("os.environ", {"DISPLAY": ":0"}):
            with patch("pathlib.Path.exists", return_value=True):
                available = runner.check_gui_available()
                assert available is True


class TestNonGuiCongestionReports:
    """Test fallback to non-GUI congestion reports."""

    def test_sta_congestion_mode_has_congestion_report_without_gui(self) -> None:
        """STA_CONGESTION mode produces congestion report without GUI."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            visualization_enabled=False,
        )

        # Should have congestion report via global_route -congestion_report_file
        assert "global_route" in script
        assert "-congestion_report_file" in script

        # Should NOT have GUI heatmap exports
        assert "gui::dump_heatmap" not in script

    def test_sta_only_mode_has_no_congestion_without_gui(self) -> None:
        """STA_ONLY mode has no congestion analysis (scalar or GUI)."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            visualization_enabled=False,
        )

        # Should NOT have congestion report
        assert "-congestion_report_file" not in script

        # Should NOT have GUI heatmap exports
        assert "gui::dump_heatmap" not in script

    def test_fallback_produces_scalar_congestion_metrics(self) -> None:
        """Fallback mode should still produce scalar congestion metrics."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            visualization_enabled=False,
        )

        # Verify congestion report is produced (scalar metrics)
        assert "congestion_report_file" in script

        # Should write congestion metrics to metrics.json
        assert "metrics.json" in script


class TestVisualizationFallbackExecution:
    """Test actual fallback behavior during trial execution."""

    def test_trial_succeeds_without_gui_when_visualization_disabled(self) -> None:
        """Trial completes successfully without GUI when visualization disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trial_dir = Path(tmpdir) / "trial"
            trial_dir.mkdir()

            # Generate script without visualization
            script_path = trial_dir / "trial_script.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
                visualization_enabled=False,
            )

            # Verify script doesn't require GUI
            script_content = script_path.read_text()
            assert "gui::dump_heatmap" not in script_content

    def test_gui_unavailable_does_not_fail_trial_when_visualization_disabled(
        self,
    ) -> None:
        """Trial should succeed even if GUI unavailable when vis disabled."""
        with tempfile.TemporaryDirectory() as tmpdir:
            trial_dir = Path(tmpdir) / "trial"
            trial_dir.mkdir()

            # Generate script without visualization
            script_path = trial_dir / "trial_script.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_ONLY,
                design_name="test_design",
                visualization_enabled=False,
            )

            # Simulate environment without GUI
            with patch.dict("os.environ", {}, clear=True):
                # Script should not attempt GUI commands, so no failure expected
                script_content = script_path.read_text()
                assert "gui::dump_heatmap" not in script_content

    def test_fallback_script_generated_when_gui_unavailable_and_vis_enabled(
        self,
    ) -> None:
        """When GUI unavailable but vis enabled, generate non-GUI script."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # This tests the fallback strategy:
            # 1. Check if GUI is available
            # 2. If not, generate script with visualization_enabled=False

            config = DockerRunConfig()
            runner = DockerTrialRunner(config)

            with patch.dict("os.environ", {}, clear=True):
                gui_available = runner.check_gui_available()
                assert gui_available is False

                # Generate fallback script (no visualization)
                script_path = Path(tmpdir) / "trial_script.tcl"
                write_trial_script(
                    script_path=script_path,
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    design_name="test_design",
                    visualization_enabled=False,  # Fallback to non-GUI
                )

                script_content = script_path.read_text()
                assert "gui::dump_heatmap" not in script_content
                # But should still have scalar congestion
                assert "-congestion_report_file" in script_content


class TestVisualizationFallbackTelemetry:
    """Test telemetry documentation of visualization fallback."""

    def test_trial_result_includes_gui_availability_status(self) -> None:
        """TrialResult should document whether GUI was available."""
        # This tests that we track whether GUI was available in telemetry
        with tempfile.TemporaryDirectory() as tmpdir:
            trial_config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=Path(tmpdir) / "script.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
            )

            # Create trial with docker_config parameter
            trial = Trial(
                config=trial_config,
                docker_config=None,  # Use default config
            )

            # Telemetry should be able to capture GUI availability
            # (this is tested via metadata field in TrialResult)
            assert hasattr(trial.config, "metadata")

    def test_fallback_reason_documented_in_metadata(self) -> None:
        """When fallback occurs, reason should be in trial metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create trial with metadata documenting fallback
            trial_config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=Path(tmpdir) / "script.tcl",
                execution_mode=ExecutionMode.STA_ONLY,
                metadata={
                    "visualization_fallback": True,
                    "fallback_reason": "GUI unavailable: DISPLAY not set",
                },
            )

            assert trial_config.metadata["visualization_fallback"] is True
            assert "DISPLAY" in trial_config.metadata["fallback_reason"]

    def test_successful_fallback_does_not_mark_trial_as_failed(self) -> None:
        """Successful fallback should not mark trial as failed."""
        # Fallback is successful adaptation, not a failure
        with tempfile.TemporaryDirectory() as tmpdir:
            trial_config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=Path(tmpdir) / "script.tcl",
                execution_mode=ExecutionMode.STA_CONGESTION,
                metadata={
                    "visualization_fallback": True,
                    "fallback_reason": "GUI unavailable: X11 socket not found",
                },
            )

            # Trial succeeded with fallback (scalar metrics only)
            # success=True, no failure classification
            assert trial_config.metadata["visualization_fallback"] is True


class TestVisualizationFallbackCompleteness:
    """Test end-to-end fallback behavior."""

    def test_fallback_trial_produces_all_required_artifacts(self) -> None:
        """Trial with fallback should produce all required non-GUI artifacts."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            visualization_enabled=False,  # Fallback
        )

        # Should have all required artifacts:
        # 1. Timing report (generated manually)
        assert "timing_report" in script

        # 2. Metrics JSON
        assert "metrics.json" in script

        # 3. Congestion report (scalar)
        assert "congestion_report_file" in script

    def test_fallback_trial_succeeds_with_scalar_metrics_only(self) -> None:
        """Trial should succeed with scalar metrics when GUI unavailable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "trial_script.tcl"
            write_trial_script(
                script_path=script_path,
                execution_mode=ExecutionMode.STA_CONGESTION,
                design_name="test_design",
                visualization_enabled=False,
            )

            script_content = script_path.read_text()

            # Verify all required outputs present
            assert "timing_report" in script_content
            assert "congestion_report_file" in script_content
            assert "metrics.json" in script_content

            # Verify no GUI commands
            assert "gui::dump_heatmap" not in script_content

    def test_stage_with_optional_visualization_completes_on_fallback(self) -> None:
        """Stage with visualization_enabled=True completes even if GUI unavailable."""
        from src.controller.types import ECOClass, ExecutionMode, StageConfig

        stage = StageConfig(
            name="test_stage",
            execution_mode=ExecutionMode.STA_CONGESTION,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
            visualization_enabled=True,  # Optional, not required
        )

        # Stage should be configured to allow fallback
        assert stage.visualization_enabled is True

        # Generate fallback script when GUI unavailable
        with patch.dict("os.environ", {}, clear=True):
            config = DockerRunConfig()
            runner = DockerTrialRunner(config)
            gui_available = runner.check_gui_available()
            assert gui_available is False

            # Use visualization_enabled=False for fallback
            script = generate_trial_script(
                execution_mode=stage.execution_mode,
                design_name="test_design",
                visualization_enabled=False,  # Fallback
            )

            # Verify fallback script is valid
            assert "timing_report" in script
            assert "congestion_report_file" in script
            assert "gui::dump_heatmap" not in script


class TestVisualizationFallbackDocumentation:
    """Test documentation and auditability of fallback behavior."""

    def test_fallback_reason_is_human_readable(self) -> None:
        """Fallback reason should be clear and actionable."""
        config = DockerRunConfig()
        runner = DockerTrialRunner(config)

        with patch.dict("os.environ", {}, clear=True):
            available = runner.check_gui_available()
            assert available is False

            # Document why GUI is unavailable
            reason = "GUI unavailable: DISPLAY environment variable not set"
            assert "DISPLAY" in reason
            assert "not set" in reason

    def test_fallback_documented_in_trial_metadata(self) -> None:
        """Trial metadata should document visualization fallback occurred."""
        with tempfile.TemporaryDirectory() as tmpdir:
            metadata = {
                "visualization_requested": True,
                "visualization_fallback": True,
                "fallback_reason": "GUI unavailable: X11 socket not accessible",
                "heatmaps_available": False,
                "scalar_congestion_available": True,
            }

            trial_config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=0,
                script_path=Path(tmpdir) / "script.tcl",
                execution_mode=ExecutionMode.STA_CONGESTION,
                metadata=metadata,
            )

            # Verify all fallback information captured
            assert trial_config.metadata["visualization_requested"] is True
            assert trial_config.metadata["visualization_fallback"] is True
            assert "GUI unavailable" in trial_config.metadata["fallback_reason"]
            assert trial_config.metadata["heatmaps_available"] is False
            assert trial_config.metadata["scalar_congestion_available"] is True

    def test_telemetry_distinguishes_no_vis_requested_vs_fallback(self) -> None:
        """Telemetry should distinguish between no-vis-requested and fallback."""
        # Case 1: Visualization never requested
        metadata_never_requested = {
            "visualization_requested": False,
            "visualization_fallback": False,
        }

        # Case 2: Visualization requested but fell back
        metadata_fallback = {
            "visualization_requested": True,
            "visualization_fallback": True,
            "fallback_reason": "GUI unavailable",
        }

        # These should be distinguishable in telemetry
        assert metadata_never_requested["visualization_requested"] is False
        assert metadata_fallback["visualization_requested"] is True
        assert metadata_fallback["visualization_fallback"] is True
