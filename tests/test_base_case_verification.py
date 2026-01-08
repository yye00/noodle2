"""Tests for base case verification and Study abortion on failure."""

import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StudyExecutor
from src.controller.study import StudyConfig
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestBaseCaseVerification:
    """Tests for base case structural runnability verification."""

    @pytest.mark.slow
    def test_valid_base_case_passes_verification(self) -> None:
        """Test that a valid base case passes verification."""
        # Use the Nangate45 base case snapshot that we know works
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="valid_base_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify base case
            is_valid, failure_message = executor.verify_base_case()

            assert is_valid is True
            assert failure_message == ""

    def test_broken_base_case_fails_verification(self) -> None:
        """Test that a broken base case fails verification."""
        # Create a snapshot path that doesn't exist
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(f"{tmpdir}/nonexistent_snapshot")

            config = StudyConfig(
                name="broken_base_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify base case
            is_valid, failure_message = executor.verify_base_case()

            assert is_valid is False
            assert failure_message != ""
            assert "Base case failed structural runnability" in failure_message


class TestStudyAbortionOnBaseCaseFailure:
    """Tests for Study abortion when base case fails."""

    def test_study_aborts_on_broken_base_case(self) -> None:
        """Test that Study execution aborts when base case fails."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(f"{tmpdir}/broken_snapshot")

            config = StudyConfig(
                name="abort_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=3,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                    StageConfig(
                        name="stage_1",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=3,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Execute Study - should abort immediately
            result = executor.execute()

            # Verify Study was aborted
            assert result.aborted is True
            assert result.stages_completed == 0
            assert len(result.stage_results) == 0
            assert len(result.final_survivors) == 0
            assert "Base case failed structural runnability" in result.abort_reason

    def test_no_eco_experimentation_after_base_case_failure(self) -> None:
        """Test that no ECO trials are executed after base case failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(f"{tmpdir}/broken_snapshot")

            config = StudyConfig(
                name="no_eco_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=10,  # Many trials budgeted
                        survivor_count=5,
                        allowed_eco_classes=[
                            ECOClass.TOPOLOGY_NEUTRAL,
                            ECOClass.PLACEMENT_LOCAL,
                        ],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            result = executor.execute()

            # Verify no stages were executed (no trials ran)
            assert result.aborted is True
            assert result.stages_completed == 0
            assert len(result.stage_results) == 0

    def test_study_blocked_message_is_clear(self) -> None:
        """Test that Study blocked message is clear and informative."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(f"{tmpdir}/broken_snapshot")

            config = StudyConfig(
                name="clear_message_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            result = executor.execute()

            # Verify abort message is informative
            assert result.abort_reason is not None
            assert "Base case failed structural runnability" in result.abort_reason
            # Should contain some diagnostic information
            assert len(result.abort_reason) > 50  # More than just the header

    @pytest.mark.slow
    def test_valid_base_case_allows_study_to_proceed(self) -> None:
        """Test that a valid base case allows Study to proceed normally."""
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="proceed_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=2,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            result = executor.execute()

            # Verify Study executed normally
            assert result.aborted is False
            assert result.stages_completed == 1
            assert len(result.stage_results) == 1


class TestBaseCaseVerificationTelemetry:
    """Tests for telemetry emission during base case verification failures."""

    def test_aborted_study_emits_telemetry(self) -> None:
        """Test that aborted Study due to base case failure emits telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(f"{tmpdir}/broken_snapshot")
            telemetry_root = Path(f"{tmpdir}/telemetry")

            config = StudyConfig(
                name="telemetry_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=str(telemetry_root),
            )

            result = executor.execute()

            # Verify telemetry was emitted
            study_telemetry_file = telemetry_root / "telemetry_test" / "study_telemetry.json"
            assert study_telemetry_file.exists()

            # Read and verify telemetry content
            import json

            with open(study_telemetry_file) as f:
                telemetry = json.load(f)

            assert telemetry["study_name"] == "telemetry_test"
            assert telemetry["aborted"] is True
            assert "Base case failed structural runnability" in telemetry["abort_reason"]
            assert telemetry["stages_completed"] == 0
            assert len(telemetry["final_survivors"]) == 0


class TestBaseCaseVerificationContract:
    """Tests for base case verification contract requirements."""

    def test_verification_checks_return_code(self) -> None:
        """Test that verification checks tool return code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(f"{tmpdir}/broken_snapshot")

            config = StudyConfig(
                name="rc_check_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            is_valid, failure_message = executor.verify_base_case()

            # Should fail with non-zero return code or missing files
            assert is_valid is False
            # Message should mention return code or failure
            assert ("return_code" in failure_message.lower()) or (
                "failed" in failure_message.lower()
            )

    def test_verification_checks_required_reports(self) -> None:
        """Test that verification checks for required reports."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_path = Path(f"{tmpdir}/broken_snapshot")

            config = StudyConfig(
                name="report_check_test",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            is_valid, failure_message = executor.verify_base_case()

            # Verification should fail
            assert is_valid is False
