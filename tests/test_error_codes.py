"""Tests for error code system and custom exceptions."""

import pytest

from controller.exceptions import (
    # Configuration errors
    ConfigurationError,
    StudyNameError,
    NoStagesError,
    SnapshotPathError,
    TrialBudgetError,
    SurvivorCountError,
    SurvivorBudgetMismatchError,
    TimeoutConfigError,
    ECOBlacklistWhitelistConflictError,
    # Case management errors
    CaseManagementError,
    InvalidCaseIdentifierError,
    DuplicateCaseError,
    ParentCaseNotFoundError,
    CaseNotFoundError,
    # ECO execution errors
    ECOExecutionError,
    ECONotAllowedError,
    ECOParameterError,
    RiskEnvelopeViolationError,
    # Trial execution errors
    TrialExecutionError,
    DockerImageNotFoundError,
    SnapshotNotFoundError,
    TrialTimeoutError,
    ContainerExecutionError,
    # Parsing errors
    ParsingError,
    TimingReportParseError,
    CongestionReportParseError,
    CustomMetricParseError,
    # Safety errors
    SafetyError,
    IllegalStudyConfigurationError,
    AbortThresholdExceededError,
    StageGateFailureError,
    # File/IO errors
    FileOperationError,
    ArtifactNotFoundError,
    TelemetryWriteError,
    YAMLParseError,
    # Error code registry
    get_error_code_description,
    ERROR_CODE_REGISTRY,
)


class TestErrorCodeFormat:
    """Test that all errors have correct error code format."""

    def test_study_name_error_has_code(self):
        """Test StudyNameError includes error code."""
        with pytest.raises(StudyNameError, match=r"\[N2-E-001\]"):
            raise StudyNameError()

    def test_error_message_includes_code(self):
        """Test error message includes bracketed error code."""
        try:
            raise StudyNameError("Custom message")
        except StudyNameError as e:
            assert "[N2-E-001]" in str(e)
            assert "Custom message" in str(e)

    def test_error_code_attribute(self):
        """Test exception has error_code attribute."""
        error = StudyNameError()
        assert error.error_code == "N2-E-001"

    def test_error_details_attribute(self):
        """Test exception has details attribute."""
        error = TrialBudgetError(stage_idx=2)
        assert error.error_code == "N2-E-004"
        assert error.details["stage_idx"] == 2


class TestConfigurationErrors:
    """Test configuration error codes (N2-E-001 to N2-E-099)."""

    def test_study_name_error(self):
        """Test N2-E-001: Study name empty."""
        with pytest.raises(StudyNameError) as exc_info:
            raise StudyNameError()
        assert exc_info.value.error_code == "N2-E-001"
        assert "Study name cannot be empty" in str(exc_info.value)

    def test_no_stages_error(self):
        """Test N2-E-002: No stages defined."""
        with pytest.raises(NoStagesError) as exc_info:
            raise NoStagesError()
        assert exc_info.value.error_code == "N2-E-002"
        assert "at least one stage" in str(exc_info.value)

    def test_snapshot_path_error(self):
        """Test N2-E-003: Missing snapshot_path."""
        with pytest.raises(SnapshotPathError) as exc_info:
            raise SnapshotPathError()
        assert exc_info.value.error_code == "N2-E-003"
        assert "snapshot_path" in str(exc_info.value)

    def test_trial_budget_error(self):
        """Test N2-E-004: Invalid trial_budget."""
        with pytest.raises(TrialBudgetError) as exc_info:
            raise TrialBudgetError(stage_idx=1)
        assert exc_info.value.error_code == "N2-E-004"
        assert "Stage 1" in str(exc_info.value)
        assert "trial_budget" in str(exc_info.value)

    def test_survivor_count_error(self):
        """Test N2-E-005: Invalid survivor_count."""
        with pytest.raises(SurvivorCountError) as exc_info:
            raise SurvivorCountError(stage_idx=0)
        assert exc_info.value.error_code == "N2-E-005"
        assert "survivor_count" in str(exc_info.value)

    def test_survivor_budget_mismatch_error(self):
        """Test N2-E-006: survivor_count exceeds trial_budget."""
        with pytest.raises(SurvivorBudgetMismatchError) as exc_info:
            raise SurvivorBudgetMismatchError(
                stage_idx=0, survivor_count=10, trial_budget=5
            )
        assert exc_info.value.error_code == "N2-E-006"
        assert "cannot exceed" in str(exc_info.value)
        assert exc_info.value.details["survivor_count"] == 10
        assert exc_info.value.details["trial_budget"] == 5

    def test_timeout_config_error(self):
        """Test N2-E-007: Invalid timeout configuration."""
        with pytest.raises(TimeoutConfigError) as exc_info:
            raise TimeoutConfigError("soft_timeout_seconds must be positive")
        assert exc_info.value.error_code == "N2-E-007"
        assert "timeout" in str(exc_info.value).lower()

    def test_blacklist_whitelist_conflict_error(self):
        """Test N2-E-008: ECO in both blacklist and whitelist."""
        with pytest.raises(ECOBlacklistWhitelistConflictError) as exc_info:
            raise ECOBlacklistWhitelistConflictError(["eco1", "eco2"])
        assert exc_info.value.error_code == "N2-E-008"
        assert "blacklist and whitelist" in str(exc_info.value)
        assert exc_info.value.details["conflicting_ecos"] == ["eco1", "eco2"]


class TestCaseManagementErrors:
    """Test case management error codes (N2-E-100 to N2-E-149)."""

    def test_invalid_case_identifier_error(self):
        """Test N2-E-100: Invalid case identifier format."""
        with pytest.raises(InvalidCaseIdentifierError) as exc_info:
            raise InvalidCaseIdentifierError("bad_id", "missing underscores")
        assert exc_info.value.error_code == "N2-E-100"
        assert "bad_id" in str(exc_info.value)
        assert "missing underscores" in str(exc_info.value)

    def test_duplicate_case_error(self):
        """Test N2-E-101: Case already exists."""
        with pytest.raises(DuplicateCaseError) as exc_info:
            raise DuplicateCaseError("nangate45_0_0")
        assert exc_info.value.error_code == "N2-E-101"
        assert "already exists" in str(exc_info.value)
        assert exc_info.value.details["case_id"] == "nangate45_0_0"

    def test_parent_case_not_found_error(self):
        """Test N2-E-102: Parent case not found."""
        with pytest.raises(ParentCaseNotFoundError) as exc_info:
            raise ParentCaseNotFoundError("child_0_1", "parent_0_0")
        assert exc_info.value.error_code == "N2-E-102"
        assert "Parent case" in str(exc_info.value)
        assert "parent_0_0" in str(exc_info.value)

    def test_case_not_found_error(self):
        """Test N2-E-103: Case not found."""
        with pytest.raises(CaseNotFoundError) as exc_info:
            raise CaseNotFoundError("missing_0_0")
        assert exc_info.value.error_code == "N2-E-103"
        assert "not found" in str(exc_info.value)


class TestECOExecutionErrors:
    """Test ECO execution error codes (N2-E-150 to N2-E-199)."""

    def test_eco_not_allowed_error(self):
        """Test N2-E-150: ECO not allowed by configuration."""
        with pytest.raises(ECONotAllowedError) as exc_info:
            raise ECONotAllowedError("risky_eco", "blacklisted in Study")
        assert exc_info.value.error_code == "N2-E-150"
        assert "not allowed" in str(exc_info.value)
        assert "risky_eco" in str(exc_info.value)

    def test_eco_parameter_error(self):
        """Test N2-E-151: Invalid ECO parameter."""
        with pytest.raises(ECOParameterError) as exc_info:
            raise ECOParameterError("buffer_insert", "max_cap", "must be positive")
        assert exc_info.value.error_code == "N2-E-151"
        assert "max_cap" in str(exc_info.value)
        assert "buffer_insert" in str(exc_info.value)

    def test_risk_envelope_violation_error(self):
        """Test N2-E-152: Risk envelope violated."""
        with pytest.raises(RiskEnvelopeViolationError) as exc_info:
            raise RiskEnvelopeViolationError(
                "placement_eco", ["max_cells_affected: 150 > 100"]
            )
        assert exc_info.value.error_code == "N2-E-152"
        assert "risk envelope" in str(exc_info.value)
        assert "max_cells_affected" in str(exc_info.value)


class TestTrialExecutionErrors:
    """Test trial execution error codes (N2-E-200 to N2-E-249)."""

    def test_docker_image_not_found_error(self):
        """Test N2-E-200: Docker image not found."""
        with pytest.raises(DockerImageNotFoundError) as exc_info:
            raise DockerImageNotFoundError("custom/openroad:v1.0")
        assert exc_info.value.error_code == "N2-E-200"
        assert "custom/openroad:v1.0" in str(exc_info.value)

    def test_snapshot_not_found_error(self):
        """Test N2-E-201: Snapshot not found."""
        with pytest.raises(SnapshotNotFoundError) as exc_info:
            raise SnapshotNotFoundError("/path/to/snapshot")
        assert exc_info.value.error_code == "N2-E-201"
        assert "/path/to/snapshot" in str(exc_info.value)

    def test_trial_timeout_error(self):
        """Test N2-E-202: Trial exceeded timeout."""
        with pytest.raises(TrialTimeoutError) as exc_info:
            raise TrialTimeoutError(timeout_seconds=3600, trial_id="trial_123")
        assert exc_info.value.error_code == "N2-E-202"
        assert "3600" in str(exc_info.value)
        assert "trial_123" in str(exc_info.value)

    def test_container_execution_error(self):
        """Test N2-E-203: Container execution failed."""
        with pytest.raises(ContainerExecutionError) as exc_info:
            raise ContainerExecutionError(return_code=127, stderr="Command not found")
        assert exc_info.value.error_code == "N2-E-203"
        assert "127" in str(exc_info.value)


class TestParsingErrors:
    """Test parsing error codes (N2-E-250 to N2-E-299)."""

    def test_timing_report_parse_error(self):
        """Test N2-E-250: Timing report parse failure."""
        with pytest.raises(TimingReportParseError) as exc_info:
            raise TimingReportParseError("/path/timing.rpt", "malformed output")
        assert exc_info.value.error_code == "N2-E-250"
        assert "timing.rpt" in str(exc_info.value)
        assert "malformed" in str(exc_info.value)

    def test_congestion_report_parse_error(self):
        """Test N2-E-251: Congestion report parse failure."""
        with pytest.raises(CongestionReportParseError) as exc_info:
            raise CongestionReportParseError("/path/congestion.rpt", "missing bins")
        assert exc_info.value.error_code == "N2-E-251"
        assert "congestion.rpt" in str(exc_info.value)

    def test_custom_metric_parse_error(self):
        """Test N2-E-252: Custom metric extraction failure."""
        with pytest.raises(CustomMetricParseError) as exc_info:
            raise CustomMetricParseError("power_mw", "file not found")
        assert exc_info.value.error_code == "N2-E-252"
        assert "power_mw" in str(exc_info.value)


class TestSafetyErrors:
    """Test safety and policy error codes (N2-E-300 to N2-E-349)."""

    def test_illegal_study_configuration_error(self):
        """Test N2-E-300: Illegal Study configuration."""
        with pytest.raises(IllegalStudyConfigurationError) as exc_info:
            raise IllegalStudyConfigurationError(
                "global_disruptive ECO not allowed in locked domain"
            )
        assert exc_info.value.error_code == "N2-E-300"
        assert "Illegal" in str(exc_info.value)

    def test_abort_threshold_exceeded_error(self):
        """Test N2-E-301: Abort threshold exceeded."""
        with pytest.raises(AbortThresholdExceededError) as exc_info:
            raise AbortThresholdExceededError("wns_ps", -1500, -1000)
        assert exc_info.value.error_code == "N2-E-301"
        assert "threshold exceeded" in str(exc_info.value)
        assert "-1500" in str(exc_info.value)

    def test_stage_gate_failure_error(self):
        """Test N2-E-302: Stage gate failure."""
        with pytest.raises(StageGateFailureError) as exc_info:
            raise StageGateFailureError(1, "no survivors meet criteria")
        assert exc_info.value.error_code == "N2-E-302"
        assert "Stage 1" in str(exc_info.value)
        assert "gate failure" in str(exc_info.value)


class TestFileOperationErrors:
    """Test file and I/O error codes (N2-E-350 to N2-E-399)."""

    def test_artifact_not_found_error(self):
        """Test N2-E-350: Artifact not found."""
        with pytest.raises(ArtifactNotFoundError) as exc_info:
            raise ArtifactNotFoundError("/path/artifact.json", "timing report")
        assert exc_info.value.error_code == "N2-E-350"
        assert "artifact.json" in str(exc_info.value)
        assert "timing report" in str(exc_info.value)

    def test_telemetry_write_error(self):
        """Test N2-E-351: Telemetry write failure."""
        with pytest.raises(TelemetryWriteError) as exc_info:
            raise TelemetryWriteError("/path/telemetry.json", "permission denied")
        assert exc_info.value.error_code == "N2-E-351"
        assert "telemetry.json" in str(exc_info.value)

    def test_yaml_parse_error(self):
        """Test N2-E-352: YAML parse failure."""
        with pytest.raises(YAMLParseError) as exc_info:
            raise YAMLParseError("/path/study.yaml", "invalid syntax")
        assert exc_info.value.error_code == "N2-E-352"
        assert "study.yaml" in str(exc_info.value)
        assert "YAML" in str(exc_info.value)


class TestErrorCodeRegistry:
    """Test error code registry and documentation."""

    def test_registry_exists(self):
        """Test error code registry is populated."""
        assert len(ERROR_CODE_REGISTRY) > 0
        assert "N2-E-001" in ERROR_CODE_REGISTRY
        assert "N2-E-100" in ERROR_CODE_REGISTRY
        assert "N2-E-200" in ERROR_CODE_REGISTRY

    def test_all_error_codes_documented(self):
        """Test all defined error codes are in registry."""
        # Configuration errors
        assert "N2-E-001" in ERROR_CODE_REGISTRY
        assert "N2-E-002" in ERROR_CODE_REGISTRY
        assert "N2-E-003" in ERROR_CODE_REGISTRY
        assert "N2-E-004" in ERROR_CODE_REGISTRY
        assert "N2-E-005" in ERROR_CODE_REGISTRY
        assert "N2-E-006" in ERROR_CODE_REGISTRY
        assert "N2-E-007" in ERROR_CODE_REGISTRY
        assert "N2-E-008" in ERROR_CODE_REGISTRY
        # Case management errors
        assert "N2-E-100" in ERROR_CODE_REGISTRY
        assert "N2-E-101" in ERROR_CODE_REGISTRY
        assert "N2-E-102" in ERROR_CODE_REGISTRY
        assert "N2-E-103" in ERROR_CODE_REGISTRY
        # ECO execution errors
        assert "N2-E-150" in ERROR_CODE_REGISTRY
        assert "N2-E-151" in ERROR_CODE_REGISTRY
        assert "N2-E-152" in ERROR_CODE_REGISTRY
        # Trial execution errors
        assert "N2-E-200" in ERROR_CODE_REGISTRY
        assert "N2-E-201" in ERROR_CODE_REGISTRY
        assert "N2-E-202" in ERROR_CODE_REGISTRY
        assert "N2-E-203" in ERROR_CODE_REGISTRY
        # Parsing errors
        assert "N2-E-250" in ERROR_CODE_REGISTRY
        assert "N2-E-251" in ERROR_CODE_REGISTRY
        assert "N2-E-252" in ERROR_CODE_REGISTRY
        # Safety errors
        assert "N2-E-300" in ERROR_CODE_REGISTRY
        assert "N2-E-301" in ERROR_CODE_REGISTRY
        assert "N2-E-302" in ERROR_CODE_REGISTRY
        # File/IO errors
        assert "N2-E-350" in ERROR_CODE_REGISTRY
        assert "N2-E-351" in ERROR_CODE_REGISTRY
        assert "N2-E-352" in ERROR_CODE_REGISTRY

    def test_get_error_code_description(self):
        """Test error code description lookup."""
        desc = get_error_code_description("N2-E-001")
        assert desc is not None
        assert "Study name" in desc

        desc = get_error_code_description("N2-E-100")
        assert desc is not None
        assert "case identifier" in desc.lower()

        # Test unknown code
        desc = get_error_code_description("N2-E-999")
        assert desc is None

    def test_error_code_descriptions_meaningful(self):
        """Test all descriptions are non-empty and meaningful."""
        for code, desc in ERROR_CODE_REGISTRY.items():
            assert desc, f"Error code {code} has empty description"
            assert len(desc) > 10, f"Error code {code} description too short"
            assert not desc.isupper(), f"Error code {code} description is all caps"


class TestErrorHierarchy:
    """Test exception class hierarchy."""

    def test_configuration_error_is_noodle2_error(self):
        """Test ConfigurationError inherits from Noodle2Error."""
        error = StudyNameError()
        assert isinstance(error, ConfigurationError)

    def test_case_management_error_hierarchy(self):
        """Test CaseManagementError hierarchy."""
        error = DuplicateCaseError("test_id")
        assert isinstance(error, CaseManagementError)

    def test_eco_execution_error_hierarchy(self):
        """Test ECOExecutionError hierarchy."""
        error = ECONotAllowedError("test_eco", "reason")
        assert isinstance(error, ECOExecutionError)

    def test_all_inherit_from_exception(self):
        """Test all custom errors inherit from Exception."""
        error = StudyNameError()
        assert isinstance(error, Exception)
