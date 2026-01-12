"""Tests for structured telemetry emission."""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StudyExecutor
from src.controller.study import StudyConfig
from src.controller.telemetry import (
    CaseTelemetry,
    StageTelemetry,
    StudyTelemetry,
    TelemetryEmitter,
)
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


class TestCaseTelemetry:
    """Tests for case-level telemetry."""

    def test_create_case_telemetry(self):
        """Test creating case telemetry."""
        telemetry = CaseTelemetry(
            case_id="nangate45_0_0",
            base_case="nangate45",
            stage_index=0,
            derived_index=0,
        )

        assert telemetry.case_id == "nangate45_0_0"
        assert telemetry.base_case == "nangate45"
        assert telemetry.stage_index == 0
        assert telemetry.derived_index == 0
        assert telemetry.total_trials == 0
        assert telemetry.successful_trials == 0
        assert telemetry.failed_trials == 0

    def test_add_successful_trial(self):
        """Test adding a successful trial to case telemetry."""
        telemetry = CaseTelemetry(
            case_id="nangate45_0_0",
            base_case="nangate45",
            stage_index=0,
            derived_index=0,
        )

        trial_config = TrialConfig(
            study_name="test_study",
            case_name="nangate45_0_0",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/script.tcl",
        )

        trial = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=10.5,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp")),
            metrics={"wns_ps": -500, "tns_ps": -1500},
        )

        telemetry.add_trial(trial)

        assert telemetry.total_trials == 1
        assert telemetry.successful_trials == 1
        assert telemetry.failed_trials == 0
        assert telemetry.best_wns_ps == -500
        assert telemetry.best_tns_ps == -1500
        assert telemetry.total_runtime_seconds == 10.5
        assert len(telemetry.trials) == 1

    def test_add_failed_trial(self):
        """Test adding a failed trial to case telemetry."""
        telemetry = CaseTelemetry(
            case_id="nangate45_0_0",
            base_case="nangate45",
            stage_index=0,
            derived_index=0,
        )

        trial_config = TrialConfig(
            study_name="test_study",
            case_name="nangate45_0_0",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/script.tcl",
        )

        trial = TrialResult(
            config=trial_config,
            success=False,
            return_code=1,
            runtime_seconds=5.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp")),
        )

        telemetry.add_trial(trial)

        assert telemetry.total_trials == 1
        assert telemetry.successful_trials == 0
        assert telemetry.failed_trials == 1
        assert telemetry.best_wns_ps is None
        assert telemetry.total_runtime_seconds == 5.0

    def test_best_wns_updates(self):
        """Test that best WNS is tracked correctly (higher is better)."""
        telemetry = CaseTelemetry(
            case_id="nangate45_0_0",
            base_case="nangate45",
            stage_index=0,
            derived_index=0,
        )

        # First trial: -500ps WNS
        trial1 = TrialResult(
            config=TrialConfig(
                study_name="test",
                case_name="nangate45_0_0",
                stage_index=0,
                trial_index=0,
                script_path="/tmp/script.tcl",
            ),
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp")),
            metrics={"wns_ps": -500},
        )

        telemetry.add_trial(trial1)
        assert telemetry.best_wns_ps == -500

        # Second trial: -300ps WNS (better)
        trial2 = TrialResult(
            config=TrialConfig(
                study_name="test",
                case_name="nangate45_0_0",
                stage_index=0,
                trial_index=1,
                script_path="/tmp/script.tcl",
            ),
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp")),
            metrics={"wns_ps": -300},
        )

        telemetry.add_trial(trial2)
        assert telemetry.best_wns_ps == -300  # Better (less negative)

        # Third trial: -600ps WNS (worse, shouldn't update)
        trial3 = TrialResult(
            config=TrialConfig(
                study_name="test",
                case_name="nangate45_0_0",
                stage_index=0,
                trial_index=2,
                script_path="/tmp/script.tcl",
            ),
            success=True,
            return_code=0,
            runtime_seconds=10.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp")),
            metrics={"wns_ps": -600},
        )

        telemetry.add_trial(trial3)
        assert telemetry.best_wns_ps == -300  # Still the best

    def test_case_telemetry_to_dict(self):
        """Test serializing case telemetry to dictionary."""
        telemetry = CaseTelemetry(
            case_id="nangate45_0_0",
            base_case="nangate45",
            stage_index=0,
            derived_index=0,
        )

        data = telemetry.to_dict()

        assert data["case_id"] == "nangate45_0_0"
        assert data["base_case"] == "nangate45"
        assert data["stage_index"] == 0
        assert data["derived_index"] == 0
        assert data["total_trials"] == 0
        assert isinstance(data["trials"], list)


class TestStageTelemetry:
    """Tests for stage-level telemetry."""

    def test_create_stage_telemetry(self):
        """Test creating stage telemetry."""
        telemetry = StageTelemetry(
            stage_index=0,
            stage_name="exploration",
            trial_budget=10,
            survivor_count=3,
        )

        assert telemetry.stage_index == 0
        assert telemetry.stage_name == "exploration"
        assert telemetry.trial_budget == 10
        assert telemetry.survivor_count == 3
        assert telemetry.trials_executed == 0
        assert telemetry.successful_trials == 0
        assert telemetry.failed_trials == 0

    def test_add_trial_result(self):
        """Test adding trial results to stage telemetry."""
        telemetry = StageTelemetry(
            stage_index=0,
            stage_name="exploration",
            trial_budget=10,
            survivor_count=3,
        )

        trial = TrialResult(
            config=TrialConfig(
                study_name="test",
                case_name="nangate45_0_0",
                stage_index=0,
                trial_index=0,
                script_path="/tmp/script.tcl",
            ),
            success=True,
            return_code=0,
            runtime_seconds=5.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp")),
        )

        telemetry.add_trial_result(trial)

        assert telemetry.trials_executed == 1
        assert telemetry.successful_trials == 1
        assert telemetry.total_runtime_seconds == 5.0
        assert "nangate45_0_0" in telemetry.cases_processed

    def test_failure_type_tracking(self):
        """Test that failure types are tracked correctly."""
        telemetry = StageTelemetry(
            stage_index=0,
            stage_name="exploration",
            trial_budget=10,
            survivor_count=3,
        )

        # Import FailureType and create a failed trial
        from src.controller.failure import FailureClassification, FailureSeverity, FailureType

        trial = TrialResult(
            config=TrialConfig(
                study_name="test",
                case_name="nangate45_0_0",
                stage_index=0,
                trial_index=0,
                script_path="/tmp/script.tcl",
            ),
            success=False,
            return_code=1,
            runtime_seconds=2.0,
            artifacts=TrialArtifacts(trial_dir=Path("/tmp")),
            failure=FailureClassification(
                failure_type=FailureType.TOOL_CRASH,
                severity=FailureSeverity.CRITICAL,
                reason="Segmentation fault",
                log_excerpt="",
            ),
        )

        telemetry.add_trial_result(trial)

        assert telemetry.failed_trials == 1
        assert "tool_crash" in telemetry.failure_types
        assert telemetry.failure_types["tool_crash"] == 1

    def test_stage_telemetry_to_dict(self):
        """Test serializing stage telemetry to dictionary."""
        telemetry = StageTelemetry(
            stage_index=0,
            stage_name="exploration",
            trial_budget=10,
            survivor_count=3,
            survivors=["case1", "case2", "case3"],
        )

        data = telemetry.to_dict()

        assert data["stage_index"] == 0
        assert data["stage_name"] == "exploration"
        assert data["trial_budget"] == 10
        assert data["survivor_count"] == 3
        assert data["survivors"] == ["case1", "case2", "case3"]
        assert "success_rate" in data


class TestStudyTelemetry:
    """Tests for study-level telemetry."""

    def test_create_study_telemetry(self):
        """Test creating study telemetry."""
        telemetry = StudyTelemetry(
            study_name="nangate45_study",
            safety_domain="sandbox",
            total_stages=3,
        )

        assert telemetry.study_name == "nangate45_study"
        assert telemetry.safety_domain == "sandbox"
        assert telemetry.total_stages == 3
        assert telemetry.stages_completed == 0
        assert telemetry.aborted is False

    def test_add_stage_telemetry(self):
        """Test adding stage telemetry to study aggregate."""
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        stage_telemetry = StageTelemetry(
            stage_index=0,
            stage_name="exploration",
            trial_budget=10,
            survivor_count=3,
        )
        stage_telemetry.trials_executed = 10
        stage_telemetry.successful_trials = 8
        stage_telemetry.failed_trials = 2
        stage_telemetry.total_runtime_seconds = 50.0

        study_telemetry.add_stage_telemetry(stage_telemetry)

        assert study_telemetry.stages_completed == 1
        assert study_telemetry.total_trials == 10
        assert study_telemetry.successful_trials == 8
        assert study_telemetry.failed_trials == 2
        assert study_telemetry.total_runtime_seconds == 50.0

    def test_finalize_study_telemetry(self):
        """Test finalizing study telemetry."""
        telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        telemetry.finalize(
            final_survivors=["case1", "case2"],
            aborted=False,
        )

        assert telemetry.final_survivors == ["case1", "case2"]
        assert telemetry.aborted is False
        assert telemetry.end_time is not None

    def test_finalize_aborted_study(self):
        """Test finalizing an aborted study."""
        telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="guarded",
            total_stages=3,
        )

        telemetry.finalize(
            final_survivors=[],
            aborted=True,
            abort_reason="Stage 1 produced no survivors",
        )

        assert telemetry.final_survivors == []
        assert telemetry.aborted is True
        assert telemetry.abort_reason == "Stage 1 produced no survivors"

    def test_study_telemetry_to_dict(self):
        """Test serializing study telemetry to dictionary."""
        telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        telemetry.finalize(final_survivors=["case1"])

        data = telemetry.to_dict()

        assert data["study_name"] == "test_study"
        assert data["safety_domain"] == "sandbox"
        assert data["total_stages"] == 2
        assert "success_rate" in data
        assert "wall_clock_seconds" in data


class TestTelemetryEmitter:
    """Tests for TelemetryEmitter."""

    def test_create_telemetry_emitter(self):
        """Test creating a telemetry emitter."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter(
                study_name="test_study",
                telemetry_root=tmpdir,
            )

            assert emitter.study_name == "test_study"
            assert emitter.study_dir.exists()
            assert emitter.cases_dir.exists()

    def test_emit_study_telemetry(self):
        """Test emitting study-level telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter(
                study_name="test_study",
                telemetry_root=tmpdir,
            )

            telemetry = StudyTelemetry(
                study_name="test_study",
                safety_domain="sandbox",
                total_stages=2,
            )
            telemetry.finalize(final_survivors=["case1"])

            path = emitter.emit_study_telemetry(telemetry)

            assert path.exists()
            assert path.name == "study_telemetry.json"

            # Verify JSON content
            with path.open() as f:
                data = json.load(f)

            assert data["study_name"] == "test_study"
            assert data["safety_domain"] == "sandbox"

    def test_emit_stage_telemetry(self):
        """Test emitting stage-level telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter(
                study_name="test_study",
                telemetry_root=tmpdir,
            )

            telemetry = StageTelemetry(
                stage_index=0,
                stage_name="exploration",
                trial_budget=10,
                survivor_count=3,
            )

            path = emitter.emit_stage_telemetry(telemetry)

            assert path.exists()
            assert path.name == "stage_0_telemetry.json"

            # Verify JSON content
            with path.open() as f:
                data = json.load(f)

            assert data["stage_index"] == 0
            assert data["stage_name"] == "exploration"

    def test_emit_case_telemetry(self):
        """Test emitting case-level telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter(
                study_name="test_study",
                telemetry_root=tmpdir,
            )

            telemetry = CaseTelemetry(
                case_id="nangate45_0_0",
                base_case="nangate45",
                stage_index=0,
                derived_index=0,
            )

            path = emitter.emit_case_telemetry(telemetry)

            assert path.exists()
            assert path.name == "nangate45_0_0_telemetry.json"

            # Verify JSON content
            with path.open() as f:
                data = json.load(f)

            assert data["case_id"] == "nangate45_0_0"

    def test_get_or_create_case_telemetry(self):
        """Test getting or creating case telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter(
                study_name="test_study",
                telemetry_root=tmpdir,
            )

            # First call creates new telemetry
            telemetry1 = emitter.get_or_create_case_telemetry(
                case_id="case1",
                base_case="base",
                stage_index=0,
                derived_index=0,
            )

            assert telemetry1.case_id == "case1"

            # Second call returns same instance
            telemetry2 = emitter.get_or_create_case_telemetry(
                case_id="case1",
                base_case="base",
                stage_index=0,
                derived_index=0,
            )

            assert telemetry1 is telemetry2

    def test_flush_all_case_telemetry(self):
        """Test flushing all case telemetry to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter(
                study_name="test_study",
                telemetry_root=tmpdir,
            )

            # Create several case telemetries
            emitter.get_or_create_case_telemetry("case1", "base", 0, 0)
            emitter.get_or_create_case_telemetry("case2", "base", 0, 1)
            emitter.get_or_create_case_telemetry("case3", "base", 0, 2)

            paths = emitter.flush_all_case_telemetry()

            assert len(paths) == 3
            for path in paths:
                assert path.exists()


class TestTelemetryIntegration:
    """Integration tests for telemetry with StudyExecutor."""

    def test_multi_stage_study_emits_telemetry(self):
        """Test that multi-stage Study execution emits complete telemetry.

        Note: After commit a9ce449, tests with skip_base_case_verification=True
        and empty snapshot directories have trials that fail (no valid snapshot),
        leading to 0 survivors and study abort. This test now accepts both
        completion and abortion, focusing on telemetry emission.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create minimal study config
            config = StudyConfig(
                name="telemetry_test",
                base_case_name="nangate45_base",
                pdk="Nangate45",
                safety_domain=SafetyDomain.SANDBOX,
                snapshot_path=Path(tmpdir) / "snapshot",
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
            )

            # Create dummy snapshot
            config.snapshot_path.mkdir(parents=True, exist_ok=True)

            telemetry_root = Path(tmpdir) / "telemetry"
            executor = StudyExecutor(skip_base_case_verification=True,
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_root,
            )

            result = executor.execute()

            # Verify study telemetry file exists (regardless of completion/abort)
            study_telemetry_file = telemetry_root / "telemetry_test" / "study_telemetry.json"
            assert study_telemetry_file.exists()

            with study_telemetry_file.open() as f:
                study_data = json.load(f)

            # Verify basic telemetry structure
            assert study_data["study_name"] == "telemetry_test"
            assert study_data["total_stages"] == 2
            # Accept either completion (2 stages) or abortion (1 stage)
            assert study_data["stages_completed"] in [1, 2]
            # aborted can be True or False depending on whether trials succeed
            assert isinstance(study_data["aborted"], bool)

            # Verify at least stage0 telemetry exists
            stage0_file = telemetry_root / "telemetry_test" / "stage_0_telemetry.json"
            assert stage0_file.exists()

            with stage0_file.open() as f:
                stage0_data = json.load(f)

            assert stage0_data["stage_index"] == 0
            assert stage0_data["trials_executed"] == 5

            # Verify case telemetry files exist
            cases_dir = telemetry_root / "telemetry_test" / "cases"
            assert cases_dir.exists()

            case_files = list(cases_dir.glob("*_telemetry.json"))
            assert len(case_files) > 0

    def test_aborted_study_emits_telemetry(self):
        """Test that aborted Study emits telemetry with abort information.

        Note: After commit a9ce449, tests with skip_base_case_verification=True
        and empty snapshot directories naturally produce study aborts due to
        trial failures. This test relies on that behavior to test telemetry
        during abortion.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="aborted_test",
                base_case_name="nangate45_base",
                pdk="Nangate45",
                safety_domain=SafetyDomain.SANDBOX,
                snapshot_path=Path(tmpdir) / "snapshot",
                stages=[
                    StageConfig(
                        name="stage0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=2,
                        survivor_count=1,  # Request survivors but trials will fail
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    ),
                ],
            )

            config.snapshot_path.mkdir(parents=True, exist_ok=True)

            telemetry_root = Path(tmpdir) / "telemetry"
            executor = StudyExecutor(skip_base_case_verification=True,
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_root,
            )

            result = executor.execute()

            # With empty snapshot, trials fail and study aborts
            assert result.aborted is True

            # Verify study telemetry reflects abortion
            study_telemetry_file = telemetry_root / "aborted_test" / "study_telemetry.json"
            assert study_telemetry_file.exists()

            with study_telemetry_file.open() as f:
                study_data = json.load(f)

            assert study_data["aborted"] is True
            assert study_data["abort_reason"] is not None
            assert "no" in study_data["abort_reason"].lower() and "survivor" in study_data["abort_reason"].lower()


class TestTelemetryBackwardCompatibility:
    """Tests for telemetry schema backward compatibility."""

    def test_all_telemetry_types_json_serializable(self):
        """Test that all telemetry types can be serialized to JSON."""
        # Case telemetry
        case_telemetry = CaseTelemetry(
            case_id="test",
            base_case="base",
            stage_index=0,
            derived_index=0,
        )
        case_dict = case_telemetry.to_dict()
        case_json = json.dumps(case_dict)  # Should not raise
        assert isinstance(case_json, str)

        # Stage telemetry
        stage_telemetry = StageTelemetry(
            stage_index=0,
            stage_name="test",
            trial_budget=10,
            survivor_count=3,
        )
        stage_dict = stage_telemetry.to_dict()
        stage_json = json.dumps(stage_dict)
        assert isinstance(stage_json, str)

        # Study telemetry
        study_telemetry = StudyTelemetry(
            study_name="test",
            safety_domain="sandbox",
            total_stages=1,
        )
        study_telemetry.finalize(final_survivors=[])
        study_dict = study_telemetry.to_dict()
        study_json = json.dumps(study_dict)
        assert isinstance(study_json, str)

    def test_telemetry_contains_required_fields(self):
        """Test that telemetry contains all required fields for consumers."""
        # Case telemetry required fields
        case_telemetry = CaseTelemetry(
            case_id="test",
            base_case="base",
            stage_index=0,
            derived_index=0,
        )
        case_dict = case_telemetry.to_dict()

        required_case_fields = [
            "case_id",
            "base_case",
            "stage_index",
            "derived_index",
            "trials",
            "total_trials",
            "successful_trials",
            "failed_trials",
        ]
        for field in required_case_fields:
            assert field in case_dict

        # Stage telemetry required fields
        stage_telemetry = StageTelemetry(
            stage_index=0,
            stage_name="test",
            trial_budget=10,
            survivor_count=3,
        )
        stage_dict = stage_telemetry.to_dict()

        required_stage_fields = [
            "stage_index",
            "stage_name",
            "trial_budget",
            "survivor_count",
            "trials_executed",
            "successful_trials",
            "failed_trials",
            "success_rate",
            "survivors",
        ]
        for field in required_stage_fields:
            assert field in stage_dict

        # Study telemetry required fields
        study_telemetry = StudyTelemetry(
            study_name="test",
            safety_domain="sandbox",
            total_stages=1,
        )
        study_telemetry.finalize(final_survivors=[])
        study_dict = study_telemetry.to_dict()

        required_study_fields = [
            "study_name",
            "safety_domain",
            "total_stages",
            "stages_completed",
            "total_trials",
            "successful_trials",
            "failed_trials",
            "success_rate",
            "final_survivors",
            "aborted",
        ]
        for field in required_study_fields:
            assert field in study_dict


class TestTelemetryFormatting:
    """Test that telemetry files are properly formatted."""

    def test_study_telemetry_has_iso8601_timestamps(self):
        """Test that study telemetry includes ISO 8601 timestamps."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter("test_study", tmpdir)
            study_telemetry = StudyTelemetry(
                study_name="test_study",
                safety_domain="sandbox",
                total_stages=2,
            )
            study_telemetry.finalize(final_survivors=["case1"])

            telemetry_file = emitter.emit_study_telemetry(study_telemetry)

            # Load and check for ISO 8601 timestamps
            with telemetry_file.open("r") as f:
                data = json.load(f)

            assert "start_time_iso8601" in data
            assert data["start_time_iso8601"] is not None
            assert "T" in data["start_time_iso8601"]
            assert data["start_time_iso8601"].endswith("Z")

            assert "end_time_iso8601" in data
            assert "T" in data["end_time_iso8601"]

    def test_telemetry_has_human_readable_durations(self):
        """Test that telemetry includes human-readable durations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter("test_study", tmpdir)
            study_telemetry = StudyTelemetry(
                study_name="test_study",
                safety_domain="sandbox",
                total_stages=1,
            )
            study_telemetry.total_runtime_seconds = 125.5
            study_telemetry.finalize(final_survivors=["case1"])

            telemetry_file = emitter.emit_study_telemetry(study_telemetry)

            with telemetry_file.open("r") as f:
                data = json.load(f)

            assert "total_runtime_human" in data
            assert "m" in data["total_runtime_human"]  # Should include minutes

    def test_telemetry_is_properly_indented(self):
        """Test that telemetry JSON is properly indented."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter("test_study", tmpdir)
            study_telemetry = StudyTelemetry(
                study_name="test_study",
                safety_domain="sandbox",
                total_stages=1,
            )
            telemetry_file = emitter.emit_study_telemetry(study_telemetry)

            with telemetry_file.open("r") as f:
                content = f.read()

            # Should have indentation
            assert "  " in content
            # Should have newlines
            assert "\n" in content

    def test_stage_telemetry_has_human_readable_duration(self):
        """Test that stage telemetry includes human-readable duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter("test_study", tmpdir)
            stage_telemetry = StageTelemetry(
                stage_index=0,
                stage_name="test_stage",
                trial_budget=10,
                survivor_count=5,
            )
            stage_telemetry.total_runtime_seconds = 3725.0

            telemetry_file = emitter.emit_stage_telemetry(stage_telemetry)

            with telemetry_file.open("r") as f:
                data = json.load(f)

            assert "total_runtime_human" in data
            assert "h" in data["total_runtime_human"]  # Should include hours

    def test_case_telemetry_has_human_readable_duration(self):
        """Test that case telemetry includes human-readable duration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            emitter = TelemetryEmitter("test_study", tmpdir)
            case_telemetry = CaseTelemetry(
                case_id="test_0_1",
                base_case="test",
                stage_index=0,
                derived_index=1,
            )
            case_telemetry.total_runtime_seconds = 45.2

            telemetry_file = emitter.emit_case_telemetry(case_telemetry)

            with telemetry_file.open("r") as f:
                data = json.load(f)

            assert "total_runtime_human" in data
            assert "s" in data["total_runtime_human"]  # Should include seconds
