"""
Comprehensive end-to-end test for telemetry validation and schema evolution.

This test validates:
- Study, Stage, Case, and Trial level telemetry schema
- Required field presence
- ISO 8601 timestamp format
- Numeric bounds on metrics
- Schema version evolution and backward compatibility
"""

import json
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src.controller.types import ExecutionMode
from src.controller.telemetry import CaseTelemetry, StageTelemetry, StudyTelemetry, TelemetryEmitter
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


# ============================================================================
# Schema Validation Functions
# ============================================================================


def validate_iso8601_timestamp(timestamp_str: str | float | None) -> bool:
    """Validate that a timestamp is in ISO 8601 format or a Unix timestamp."""
    if timestamp_str is None:
        return True  # Optional timestamps

    # Handle Unix timestamps (float)
    if isinstance(timestamp_str, (int, float)):
        # Reasonable bounds: between year 2000 and 2100
        return 946684800 < timestamp_str < 4102444800

    # Handle ISO 8601 strings
    if isinstance(timestamp_str, str):
        try:
            datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            return True
        except (ValueError, AttributeError):
            return False

    return False


def validate_numeric_bounded(value: float | int | None, lower: float = -1e12, upper: float = 1e12) -> bool:
    """Validate that a numeric value is within reasonable bounds."""
    if value is None:
        return True  # Optional metrics

    if not isinstance(value, (int, float)):
        return False

    return lower <= value <= upper


@dataclass
class TelemetrySchemaValidator:
    """Validates telemetry against expected schema."""

    errors: list[str] = field(default_factory=list)

    def validate_trial_schema(self, trial_data: dict[str, Any]) -> bool:
        """Validate trial-level telemetry schema."""
        self.errors.clear()

        # Required fields
        required_fields = ["trial_index", "success", "return_code", "runtime_seconds"]
        for field_name in required_fields:
            if field_name not in trial_data:
                self.errors.append(f"Missing required field: {field_name}")

        # Type validations
        if "trial_index" in trial_data and not isinstance(trial_data["trial_index"], int):
            self.errors.append(f"trial_index must be int, got {type(trial_data['trial_index'])}")

        if "success" in trial_data and not isinstance(trial_data["success"], bool):
            self.errors.append(f"success must be bool, got {type(trial_data['success'])}")

        if "return_code" in trial_data and not isinstance(trial_data["return_code"], int):
            self.errors.append(f"return_code must be int, got {type(trial_data['return_code'])}")

        # Numeric bounds
        if "runtime_seconds" in trial_data:
            if not validate_numeric_bounded(trial_data["runtime_seconds"], 0, 86400):  # 0 to 24 hours
                self.errors.append(f"runtime_seconds out of bounds: {trial_data['runtime_seconds']}")

        # Metrics should be present
        if "metrics" in trial_data:
            metrics = trial_data["metrics"]
            if not isinstance(metrics, dict):
                self.errors.append(f"metrics must be dict, got {type(metrics)}")

            # Validate timing metrics if present
            for metric_name in ["wns_ps", "tns_ps"]:
                if metric_name in metrics:
                    if not validate_numeric_bounded(metrics[metric_name], -1e9, 1e9):
                        self.errors.append(f"{metric_name} out of bounds: {metrics[metric_name]}")

        return len(self.errors) == 0

    def validate_case_schema(self, case_data: dict[str, Any]) -> bool:
        """Validate case-level telemetry schema."""
        self.errors.clear()

        # Required fields
        required_fields = [
            "case_id", "base_case", "stage_index", "derived_index",
            "trials", "total_trials", "successful_trials", "failed_trials",
            "total_runtime_seconds"
        ]
        for field_name in required_fields:
            if field_name not in case_data:
                self.errors.append(f"Missing required field: {field_name}")

        # Type validations
        if "case_id" in case_data and not isinstance(case_data["case_id"], str):
            self.errors.append(f"case_id must be str, got {type(case_data['case_id'])}")

        if "stage_index" in case_data and not isinstance(case_data["stage_index"], int):
            self.errors.append(f"stage_index must be int, got {type(case_data['stage_index'])}")

        if "trials" in case_data and not isinstance(case_data["trials"], list):
            self.errors.append(f"trials must be list, got {type(case_data['trials'])}")

        # Validate trial count consistency
        if "trials" in case_data and "total_trials" in case_data:
            if len(case_data["trials"]) != case_data["total_trials"]:
                self.errors.append(
                    f"Trial count mismatch: {len(case_data['trials'])} trials vs {case_data['total_trials']} total_trials"
                )

        # Validate success + failed = total
        if all(k in case_data for k in ["successful_trials", "failed_trials", "total_trials"]):
            expected_total = case_data["successful_trials"] + case_data["failed_trials"]
            if expected_total != case_data["total_trials"]:
                self.errors.append(
                    f"Trial count inconsistency: {case_data['successful_trials']} + "
                    f"{case_data['failed_trials']} != {case_data['total_trials']}"
                )

        # Numeric bounds
        if "total_runtime_seconds" in case_data:
            if not validate_numeric_bounded(case_data["total_runtime_seconds"], 0, 864000):  # 0 to 10 days
                self.errors.append(f"total_runtime_seconds out of bounds: {case_data['total_runtime_seconds']}")

        return len(self.errors) == 0

    def validate_stage_schema(self, stage_data: dict[str, Any]) -> bool:
        """Validate stage-level telemetry schema."""
        self.errors.clear()

        # Required fields
        required_fields = [
            "stage_index", "stage_name", "trial_budget", "survivor_count",
            "trials_executed", "successful_trials", "failed_trials",
            "success_rate", "survivors", "total_runtime_seconds",
            "cases_processed"
        ]
        for field_name in required_fields:
            if field_name not in stage_data:
                self.errors.append(f"Missing required field: {field_name}")

        # Type validations
        if "stage_index" in stage_data and not isinstance(stage_data["stage_index"], int):
            self.errors.append(f"stage_index must be int, got {type(stage_data['stage_index'])}")

        if "stage_name" in stage_data and not isinstance(stage_data["stage_name"], str):
            self.errors.append(f"stage_name must be str, got {type(stage_data['stage_name'])}")

        if "survivors" in stage_data and not isinstance(stage_data["survivors"], list):
            self.errors.append(f"survivors must be list, got {type(stage_data['survivors'])}")

        if "cases_processed" in stage_data and not isinstance(stage_data["cases_processed"], list):
            self.errors.append(f"cases_processed must be list, got {type(stage_data['cases_processed'])}")

        # Validate success_rate is in [0, 1]
        if "success_rate" in stage_data:
            rate = stage_data["success_rate"]
            if not isinstance(rate, (int, float)) or not (0 <= rate <= 1):
                self.errors.append(f"success_rate must be in [0, 1], got {rate}")

        # Validate trial counts
        if all(k in stage_data for k in ["successful_trials", "failed_trials", "trials_executed"]):
            expected_total = stage_data["successful_trials"] + stage_data["failed_trials"]
            if expected_total != stage_data["trials_executed"]:
                self.errors.append(
                    f"Trial count inconsistency: {stage_data['successful_trials']} + "
                    f"{stage_data['failed_trials']} != {stage_data['trials_executed']}"
                )

        # Validate survivor count
        if "survivors" in stage_data and "survivor_count" in stage_data:
            if len(stage_data["survivors"]) > stage_data["survivor_count"]:
                self.errors.append(
                    f"Too many survivors: {len(stage_data['survivors'])} > {stage_data['survivor_count']}"
                )

        return len(self.errors) == 0

    def validate_study_schema(self, study_data: dict[str, Any]) -> bool:
        """Validate study-level telemetry schema."""
        self.errors.clear()

        # Required fields
        required_fields = [
            "study_name", "safety_domain", "total_stages", "stages_completed",
            "total_trials", "successful_trials", "failed_trials", "success_rate",
            "total_runtime_seconds", "final_survivors", "aborted",
            "start_time", "end_time"
        ]
        for field_name in required_fields:
            if field_name not in study_data:
                self.errors.append(f"Missing required field: {field_name}")

        # Type validations
        if "study_name" in study_data and not isinstance(study_data["study_name"], str):
            self.errors.append(f"study_name must be str, got {type(study_data['study_name'])}")

        if "safety_domain" in study_data and not isinstance(study_data["safety_domain"], str):
            self.errors.append(f"safety_domain must be str, got {type(study_data['safety_domain'])}")

        if "aborted" in study_data and not isinstance(study_data["aborted"], bool):
            self.errors.append(f"aborted must be bool, got {type(study_data['aborted'])}")

        if "final_survivors" in study_data and not isinstance(study_data["final_survivors"], list):
            self.errors.append(f"final_survivors must be list, got {type(study_data['final_survivors'])}")

        # Validate timestamps
        if "start_time" in study_data:
            if not validate_iso8601_timestamp(study_data["start_time"]):
                self.errors.append(f"Invalid start_time timestamp: {study_data['start_time']}")

        if "end_time" in study_data:
            if not validate_iso8601_timestamp(study_data["end_time"]):
                self.errors.append(f"Invalid end_time timestamp: {study_data['end_time']}")

        # Validate time ordering
        if all(k in study_data for k in ["start_time", "end_time"]):
            if study_data["end_time"] is not None:
                if study_data["end_time"] < study_data["start_time"]:
                    self.errors.append(
                        f"end_time ({study_data['end_time']}) < start_time ({study_data['start_time']})"
                    )

        # Validate wall_clock_seconds if present
        if "wall_clock_seconds" in study_data:
            if not validate_numeric_bounded(study_data["wall_clock_seconds"], 0, 864000):
                self.errors.append(f"wall_clock_seconds out of bounds: {study_data['wall_clock_seconds']}")

        # Validate success_rate
        if "success_rate" in study_data:
            rate = study_data["success_rate"]
            if not isinstance(rate, (int, float)) or not (0 <= rate <= 1):
                self.errors.append(f"success_rate must be in [0, 1], got {rate}")

        # Validate trial counts
        if all(k in study_data for k in ["successful_trials", "failed_trials", "total_trials"]):
            expected_total = study_data["successful_trials"] + study_data["failed_trials"]
            if expected_total != study_data["total_trials"]:
                self.errors.append(
                    f"Trial count inconsistency: {study_data['successful_trials']} + "
                    f"{study_data['failed_trials']} != {study_data['total_trials']}"
                )

        return len(self.errors) == 0


# ============================================================================
# Schema Evolution Tests
# ============================================================================


@dataclass
class TelemetrySchemaV1:
    """Original telemetry schema (v1)."""

    study_name: str
    total_trials: int
    successful_trials: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "study_name": self.study_name,
            "total_trials": self.total_trials,
            "successful_trials": self.successful_trials,
        }


@dataclass
class TelemetrySchemaV2:
    """Extended telemetry schema (v2) with backward compatibility."""

    study_name: str
    total_trials: int
    successful_trials: int
    # New optional fields in v2
    failed_trials: int = 0
    total_runtime_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "study_name": self.study_name,
            "total_trials": self.total_trials,
            "successful_trials": self.successful_trials,
            "failed_trials": self.failed_trials,
            "total_runtime_seconds": self.total_runtime_seconds,
        }

    @classmethod
    def from_v1(cls, v1_data: dict[str, Any]) -> "TelemetrySchemaV2":
        """Parse v1 telemetry with v2 parser (backward compatibility)."""
        return cls(
            study_name=v1_data["study_name"],
            total_trials=v1_data["total_trials"],
            successful_trials=v1_data["successful_trials"],
            # New fields have defaults
            failed_trials=v1_data.get("failed_trials", 0),
            total_runtime_seconds=v1_data.get("total_runtime_seconds", 0.0),
        )


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def temp_telemetry_dir() -> Path:
    """Create temporary directory for telemetry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_trial_result() -> TrialResult:
    """Create a mock successful trial result."""
    config = TrialConfig(
        study_name="test_study",
        case_name="test_case_0_0",
        stage_index=0,
        trial_index=0,
        script_path="/tmp/eco_script.tcl",
        snapshot_dir=Path("/tmp/snapshot"),
        execution_mode=ExecutionMode.STA_ONLY,
    )

    artifacts = TrialArtifacts(
        trial_dir=Path("/tmp/trial_0"),
        timing_report=Path("/tmp/trial_0/timing.rpt"),
        metrics_json=Path("/tmp/trial_0/metrics.json"),
    )

    return TrialResult(
        config=config,
        success=True,
        return_code=0,
        stdout="Success",
        stderr="",
        runtime_seconds=42.5,
        artifacts=artifacts,
        metrics={"wns_ps": 150, "tns_ps": 0, "area_um2": 5000.0},
        failure=None,
    )


@pytest.fixture
def mock_failed_trial_result() -> TrialResult:
    """Create a mock failed trial result."""
    from src.controller.failure import FailureClassification, FailureSeverity, FailureType

    config = TrialConfig(
        study_name="test_study",
        case_name="test_case_0_1",
        stage_index=0,
        trial_index=1,
        script_path="/tmp/eco_script_failing.tcl",
        snapshot_dir=Path("/tmp/snapshot"),
        execution_mode=ExecutionMode.STA_ONLY,
    )

    artifacts = TrialArtifacts(
        trial_dir=Path("/tmp/trial_1"),
        timing_report=None,  # Failed trial may not have complete artifacts
        metrics_json=None,
    )

    failure = FailureClassification(
        failure_type=FailureType.STA_FAILED,
        severity=FailureSeverity.HIGH,
        reason="Static timing analysis failed",
    )

    return TrialResult(
        config=config,
        success=False,
        return_code=1,
        stdout="Failed",
        stderr="Error: timing violation",
        runtime_seconds=15.3,
        artifacts=artifacts,
        metrics={},
        failure=failure,
    )


# ============================================================================
# Step 1: Execute Study generating complete telemetry
# ============================================================================


class TestStep1ExecuteStudyGenerateCompleteTelemetry:
    """Test that executing a Study generates complete telemetry."""

    def test_execute_study_generates_telemetry(
        self, temp_telemetry_dir: Path, mock_trial_result: TrialResult
    ) -> None:
        """Execute study and verify telemetry is generated."""
        emitter = TelemetryEmitter("test_study", temp_telemetry_dir)

        # Create study telemetry
        study_telemetry = StudyTelemetry(
            study_name="test_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        # Create stage telemetry
        stage0_telemetry = StageTelemetry(
            stage_index=0,
            stage_name="stage_0",
            trial_budget=10,
            survivor_count=3,
        )

        # Add trial results
        stage0_telemetry.add_trial_result(mock_trial_result)
        study_telemetry.add_stage_telemetry(stage0_telemetry)

        # Emit telemetry
        stage_file = emitter.emit_stage_telemetry(stage0_telemetry)
        study_file = emitter.emit_study_telemetry(study_telemetry)

        # Verify files exist
        assert stage_file.exists()
        assert study_file.exists()

        # Verify content is valid JSON
        with open(stage_file) as f:
            stage_data = json.load(f)
            assert "stage_index" in stage_data

        with open(study_file) as f:
            study_data = json.load(f)
            assert "study_name" in study_data


# ============================================================================
# Step 2-5: Validate telemetry schemas at all levels
# ============================================================================


class TestStep2ValidateStudyLevelTelemetrySchema:
    """Test study-level telemetry schema validation."""

    def test_validate_complete_study_telemetry(self) -> None:
        """Validate a complete study telemetry object."""
        study_telemetry = StudyTelemetry(
            study_name="validation_study",
            safety_domain="production",
            total_stages=3,
            stages_completed=3,
            total_trials=50,
            successful_trials=45,
            failed_trials=5,
        )
        study_telemetry.finalize(final_survivors=["case_2_3"], aborted=False)

        validator = TelemetrySchemaValidator()
        study_data = study_telemetry.to_dict()

        assert validator.validate_study_schema(study_data), f"Errors: {validator.errors}"

    def test_detect_missing_study_fields(self) -> None:
        """Detect missing required fields in study telemetry."""
        incomplete_data = {
            "study_name": "test",
            # Missing many required fields
        }

        validator = TelemetrySchemaValidator()
        assert not validator.validate_study_schema(incomplete_data)
        assert len(validator.errors) > 0
        assert any("Missing required field" in err for err in validator.errors)


class TestStep3ValidateStageLevelTelemetrySchema:
    """Test stage-level telemetry schema validation."""

    def test_validate_complete_stage_telemetry(self, mock_trial_result: TrialResult) -> None:
        """Validate a complete stage telemetry object."""
        stage_telemetry = StageTelemetry(
            stage_index=1,
            stage_name="stage_1_sta_only",
            trial_budget=20,
            survivor_count=5,
        )

        # Add some trials
        for i in range(10):
            stage_telemetry.add_trial_result(mock_trial_result)

        validator = TelemetrySchemaValidator()
        stage_data = stage_telemetry.to_dict()

        assert validator.validate_stage_schema(stage_data), f"Errors: {validator.errors}"

    def test_detect_invalid_success_rate(self) -> None:
        """Detect invalid success_rate values."""
        invalid_data = {
            "stage_index": 0,
            "stage_name": "test",
            "trial_budget": 10,
            "survivor_count": 3,
            "trials_executed": 10,
            "successful_trials": 8,
            "failed_trials": 2,
            "success_rate": 1.5,  # Invalid: > 1
            "survivors": [],
            "total_runtime_seconds": 100.0,
            "cases_processed": [],
        }

        validator = TelemetrySchemaValidator()
        assert not validator.validate_stage_schema(invalid_data)
        assert any("success_rate" in err for err in validator.errors)


class TestStep4ValidateCaseLevelTelemetrySchema:
    """Test case-level telemetry schema validation."""

    def test_validate_complete_case_telemetry(self, mock_trial_result: TrialResult) -> None:
        """Validate a complete case telemetry object."""
        case_telemetry = CaseTelemetry(
            case_id="test_case_0_0",
            base_case="baseline",
            stage_index=0,
            derived_index=0,
        )

        # Add trials
        case_telemetry.add_trial(mock_trial_result)

        validator = TelemetrySchemaValidator()
        case_data = case_telemetry.to_dict()

        assert validator.validate_case_schema(case_data), f"Errors: {validator.errors}"

    def test_detect_trial_count_mismatch(self) -> None:
        """Detect trial count inconsistencies."""
        invalid_data = {
            "case_id": "test",
            "base_case": "baseline",
            "stage_index": 0,
            "derived_index": 0,
            "trials": [{"trial_index": 0}, {"trial_index": 1}],  # 2 trials
            "total_trials": 5,  # Claims 5 trials
            "successful_trials": 3,
            "failed_trials": 2,
            "total_runtime_seconds": 100.0,
        }

        validator = TelemetrySchemaValidator()
        assert not validator.validate_case_schema(invalid_data)
        assert any("Trial count mismatch" in err for err in validator.errors)


class TestStep5ValidateTrialLevelTelemetrySchema:
    """Test trial-level telemetry schema validation."""

    def test_validate_complete_trial_telemetry(self) -> None:
        """Validate a complete trial telemetry object."""
        trial_data = {
            "trial_index": 5,
            "success": True,
            "return_code": 0,
            "runtime_seconds": 42.7,
            "metrics": {
                "wns_ps": 200,
                "tns_ps": 0,
                "area_um2": 6000.0,
            },
        }

        validator = TelemetrySchemaValidator()
        assert validator.validate_trial_schema(trial_data), f"Errors: {validator.errors}"

    def test_detect_invalid_runtime(self) -> None:
        """Detect invalid runtime values."""
        invalid_data = {
            "trial_index": 0,
            "success": True,
            "return_code": 0,
            "runtime_seconds": 100000.0,  # > 24 hours
            "metrics": {},
        }

        validator = TelemetrySchemaValidator()
        assert not validator.validate_trial_schema(invalid_data)
        assert any("runtime_seconds out of bounds" in err for err in validator.errors)


# ============================================================================
# Step 6: Verify all required fields are present
# ============================================================================


class TestStep6VerifyAllRequiredFieldsPresent:
    """Test that all required fields are present across telemetry levels."""

    def test_study_telemetry_has_all_required_fields(self) -> None:
        """Verify study telemetry includes all required fields."""
        study = StudyTelemetry(
            study_name="complete_test",
            safety_domain="sandbox",
            total_stages=1,
        )
        study.finalize(final_survivors=[], aborted=False)

        data = study.to_dict()
        required = [
            "study_name", "safety_domain", "total_stages", "stages_completed",
            "total_trials", "successful_trials", "failed_trials", "success_rate",
            "total_runtime_seconds", "final_survivors", "aborted",
            "start_time", "end_time"
        ]

        for field in required:
            assert field in data, f"Missing required field: {field}"

    def test_stage_telemetry_has_all_required_fields(self) -> None:
        """Verify stage telemetry includes all required fields."""
        stage = StageTelemetry(
            stage_index=0,
            stage_name="test_stage",
            trial_budget=10,
            survivor_count=3,
        )

        data = stage.to_dict()
        required = [
            "stage_index", "stage_name", "trial_budget", "survivor_count",
            "trials_executed", "successful_trials", "failed_trials",
            "success_rate", "survivors", "total_runtime_seconds",
            "cases_processed"
        ]

        for field in required:
            assert field in data, f"Missing required field: {field}"

    def test_case_telemetry_has_all_required_fields(self) -> None:
        """Verify case telemetry includes all required fields."""
        case = CaseTelemetry(
            case_id="test_case",
            base_case="baseline",
            stage_index=0,
            derived_index=0,
        )

        data = case.to_dict()
        required = [
            "case_id", "base_case", "stage_index", "derived_index",
            "trials", "total_trials", "successful_trials", "failed_trials",
            "total_runtime_seconds"
        ]

        for field in required:
            assert field in data, f"Missing required field: {field}"


# ============================================================================
# Step 7: Verify timestamps are in ISO 8601 format
# ============================================================================


class TestStep7VerifyTimestampsISO8601:
    """Test that timestamps use ISO 8601 format or Unix timestamps."""

    def test_timestamps_are_valid_unix_timestamps(self) -> None:
        """Verify Unix timestamps are within reasonable bounds."""
        study = StudyTelemetry(
            study_name="timestamp_test",
            safety_domain="sandbox",
            total_stages=1,
        )
        study.finalize(final_survivors=[], aborted=False)

        data = study.to_dict()

        assert validate_iso8601_timestamp(data["start_time"])
        assert validate_iso8601_timestamp(data["end_time"])

    def test_iso8601_string_validation(self) -> None:
        """Test ISO 8601 string validation."""
        valid_timestamps = [
            "2024-01-08T10:30:00",
            "2024-01-08T10:30:00.123456",
            "2024-01-08T10:30:00Z",
            "2024-01-08T10:30:00+00:00",
        ]

        for ts in valid_timestamps:
            assert validate_iso8601_timestamp(ts), f"Failed to validate: {ts}"

    def test_reject_invalid_timestamps(self) -> None:
        """Test rejection of invalid timestamps."""
        invalid_timestamps = [
            "not a timestamp",
            "2024-13-45",  # Invalid date
            123,  # Too small (before 2000)
            9999999999,  # Too large (after 2100)
        ]

        for ts in invalid_timestamps:
            assert not validate_iso8601_timestamp(ts), f"Should reject: {ts}"


# ============================================================================
# Step 8: Verify metrics are numeric and bounded
# ============================================================================


class TestStep8VerifyMetricsNumericAndBounded:
    """Test that metrics are numeric and within reasonable bounds."""

    def test_timing_metrics_within_bounds(self) -> None:
        """Verify timing metrics are bounded."""
        trial_data = {
            "trial_index": 0,
            "success": True,
            "return_code": 0,
            "runtime_seconds": 50.0,
            "metrics": {
                "wns_ps": 300,  # 300 ps WNS is reasonable
                "tns_ps": -1000,  # Negative TNS is valid
            },
        }

        validator = TelemetrySchemaValidator()
        assert validator.validate_trial_schema(trial_data)

    def test_reject_out_of_bounds_metrics(self) -> None:
        """Reject metrics that are unreasonably large."""
        trial_data = {
            "trial_index": 0,
            "success": True,
            "return_code": 0,
            "runtime_seconds": 50.0,
            "metrics": {
                "wns_ps": 1e15,  # Unreasonably large
            },
        }

        validator = TelemetrySchemaValidator()
        assert not validator.validate_trial_schema(trial_data)
        assert any("wns_ps out of bounds" in err for err in validator.errors)

    def test_metrics_must_be_numeric(self) -> None:
        """Metrics must be numeric types."""
        assert validate_numeric_bounded(42)
        assert validate_numeric_bounded(3.14159)
        assert validate_numeric_bounded(None)  # Optional

        # Non-numeric should fail
        assert not validate_numeric_bounded("not a number")


# ============================================================================
# Step 9-14: Schema evolution and backward compatibility
# ============================================================================


class TestStep9SimulateSchemaVersionUpgrade:
    """Test schema version upgrade simulation."""

    def test_define_schema_v1_and_v2(self) -> None:
        """Define v1 and v2 schemas."""
        v1 = TelemetrySchemaV1(
            study_name="evolution_test",
            total_trials=100,
            successful_trials=95,
        )

        v2 = TelemetrySchemaV2(
            study_name="evolution_test",
            total_trials=100,
            successful_trials=95,
            failed_trials=5,
            total_runtime_seconds=3600.0,
        )

        assert v1.to_dict()["schema_version"] == 1
        assert v2.to_dict()["schema_version"] == 2


class TestStep10AddNewOptionalFieldsV2:
    """Test adding new optional fields in schema v2."""

    def test_v2_includes_new_fields(self) -> None:
        """Verify v2 includes new optional fields."""
        v2 = TelemetrySchemaV2(
            study_name="test",
            total_trials=10,
            successful_trials=8,
            failed_trials=2,
            total_runtime_seconds=500.0,
        )

        data = v2.to_dict()

        assert "failed_trials" in data
        assert "total_runtime_seconds" in data
        assert data["failed_trials"] == 2
        assert data["total_runtime_seconds"] == 500.0


class TestStep11ParseV1TelemetryWithV2Parser:
    """Test parsing v1 telemetry with v2 parser (backward compatibility)."""

    def test_v2_parser_handles_v1_data(self) -> None:
        """Verify v2 parser can read v1 data."""
        v1_data = {
            "schema_version": 1,
            "study_name": "legacy_study",
            "total_trials": 50,
            "successful_trials": 48,
        }

        # Parse with v2
        v2_obj = TelemetrySchemaV2.from_v1(v1_data)

        assert v2_obj.study_name == "legacy_study"
        assert v2_obj.total_trials == 50
        assert v2_obj.successful_trials == 48
        # New fields get defaults
        assert v2_obj.failed_trials == 0
        assert v2_obj.total_runtime_seconds == 0.0


class TestStep12VerifyBackwardCompatibility:
    """Test backward compatibility is maintained."""

    def test_v1_fields_preserved_in_v2(self) -> None:
        """Verify v1 fields are preserved in v2."""
        v1_data = {
            "schema_version": 1,
            "study_name": "compat_test",
            "total_trials": 30,
            "successful_trials": 25,
        }

        v2_obj = TelemetrySchemaV2.from_v1(v1_data)
        v2_data = v2_obj.to_dict()

        # All v1 fields must be present in v2
        assert v2_data["study_name"] == v1_data["study_name"]
        assert v2_data["total_trials"] == v1_data["total_trials"]
        assert v2_data["successful_trials"] == v1_data["successful_trials"]


class TestStep13GenerateV2TelemetryWithNewFields:
    """Test generating v2 telemetry with new fields."""

    def test_generate_complete_v2_telemetry(self) -> None:
        """Generate v2 telemetry with all new fields."""
        v2 = TelemetrySchemaV2(
            study_name="modern_study",
            total_trials=200,
            successful_trials=195,
            failed_trials=5,
            total_runtime_seconds=7200.0,
        )

        data = v2.to_dict()

        assert data["schema_version"] == 2
        assert data["failed_trials"] == 5
        assert data["total_runtime_seconds"] == 7200.0


class TestStep14VerifyAdditiveEvolutionEnforced:
    """Test that schema evolution is additive only."""

    def test_no_fields_removed_in_v2(self) -> None:
        """Verify v2 doesn't remove any v1 fields."""
        v1_fields = set(TelemetrySchemaV1(
            study_name="test", total_trials=1, successful_trials=1
        ).to_dict().keys())

        v2_fields = set(TelemetrySchemaV2(
            study_name="test", total_trials=1, successful_trials=1
        ).to_dict().keys())

        # All v1 fields must exist in v2 (except version which changed)
        v1_data_fields = v1_fields - {"schema_version"}
        v2_data_fields = v2_fields - {"schema_version"}

        assert v1_data_fields.issubset(v2_data_fields), (
            f"V2 removed fields from v1: {v1_data_fields - v2_data_fields}"
        )

    def test_new_fields_are_optional(self) -> None:
        """Verify new v2 fields have defaults."""
        # Can construct v2 without specifying new fields
        v2_minimal = TelemetrySchemaV2(
            study_name="test",
            total_trials=1,
            successful_trials=1,
            # failed_trials and total_runtime_seconds have defaults
        )

        assert v2_minimal.failed_trials == 0
        assert v2_minimal.total_runtime_seconds == 0.0


# ============================================================================
# Complete E2E Workflow Test
# ============================================================================


class TestCompleteTelemetryValidationE2EWorkflow:
    """Complete end-to-end telemetry validation workflow."""

    def test_complete_telemetry_validation_workflow(
        self,
        temp_telemetry_dir: Path,
        mock_trial_result: TrialResult,
        mock_failed_trial_result: TrialResult,
    ) -> None:
        """
        Complete workflow:
        1. Generate telemetry at all levels
        2. Validate schemas
        3. Test evolution
        4. Verify backward compatibility
        """
        # Create emitter
        emitter = TelemetryEmitter("complete_e2e_study", temp_telemetry_dir)

        # Create study telemetry
        study_telemetry = StudyTelemetry(
            study_name="complete_e2e_study",
            safety_domain="sandbox",
            total_stages=2,
        )

        validator = TelemetrySchemaValidator()

        # Stage 0
        stage0 = StageTelemetry(
            stage_index=0,
            stage_name="stage_0_sta",
            trial_budget=20,
            survivor_count=5,
        )

        # Add successful and failed trials
        for i in range(15):
            stage0.add_trial_result(mock_trial_result)
        for i in range(5):
            stage0.add_trial_result(mock_failed_trial_result)

        # Validate stage schema
        stage0_data = stage0.to_dict()
        assert validator.validate_stage_schema(stage0_data), f"Stage errors: {validator.errors}"

        # Emit stage telemetry
        stage0_file = emitter.emit_stage_telemetry(stage0)
        assert stage0_file.exists()

        # Add to study
        study_telemetry.add_stage_telemetry(stage0)

        # Stage 1
        stage1 = StageTelemetry(
            stage_index=1,
            stage_name="stage_1_full",
            trial_budget=15,
            survivor_count=3,
        )

        for i in range(15):
            stage1.add_trial_result(mock_trial_result)

        stage1_data = stage1.to_dict()
        assert validator.validate_stage_schema(stage1_data), f"Stage errors: {validator.errors}"

        stage1_file = emitter.emit_stage_telemetry(stage1)
        assert stage1_file.exists()

        study_telemetry.add_stage_telemetry(stage1)

        # Finalize study
        study_telemetry.finalize(final_survivors=["case_1_2"], aborted=False)

        # Validate study schema
        study_data = study_telemetry.to_dict()
        assert validator.validate_study_schema(study_data), f"Study errors: {validator.errors}"

        # Emit study telemetry
        study_file = emitter.emit_study_telemetry(study_telemetry)
        assert study_file.exists()

        # Verify all telemetry files are valid JSON
        with open(study_file) as f:
            loaded_study = json.load(f)
            assert loaded_study["study_name"] == "complete_e2e_study"
            assert loaded_study["total_stages"] == 2
            assert loaded_study["total_trials"] == 35  # 20 + 15

        # Test schema evolution
        v1_data = {
            "schema_version": 1,
            "study_name": loaded_study["study_name"],
            "total_trials": loaded_study["total_trials"],
            "successful_trials": loaded_study["successful_trials"],
        }

        # Parse with v2
        v2_obj = TelemetrySchemaV2.from_v1(v1_data)
        assert v2_obj.study_name == "complete_e2e_study"
        assert v2_obj.total_trials == 35

        # Verify all files are accessible
        assert (temp_telemetry_dir / "complete_e2e_study" / "study_telemetry.json").exists()
        assert (temp_telemetry_dir / "complete_e2e_study" / "stage_0_telemetry.json").exists()
        assert (temp_telemetry_dir / "complete_e2e_study" / "stage_1_telemetry.json").exists()
