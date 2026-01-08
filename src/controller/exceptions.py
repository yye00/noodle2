"""
Custom exception classes with error codes for Noodle 2.

Error codes follow the format: N2-{SEVERITY}-{NUMBER}
- Severity: E (Error), W (Warning)
- Number: Three-digit sequence number

This enables programmatic error handling and clear error identification.
"""

from typing import Optional


class Noodle2Error(Exception):
    """Base exception class for all Noodle 2 errors with error codes."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        """
        Initialize Noodle 2 exception with error code.

        Args:
            message: Human-readable error message
            error_code: Unique error code (e.g., "N2-E-001")
            details: Optional dict with additional context
        """
        self.error_code = error_code
        self.details = details or {}
        full_message = f"[{error_code}] {message}"
        super().__init__(full_message)


# =============================================================================
# Configuration and Validation Errors (N2-E-001 to N2-E-099)
# =============================================================================


class ConfigurationError(Noodle2Error):
    """Raised when Study or Stage configuration is invalid."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, details)


class StudyNameError(ConfigurationError):
    """Raised when Study name is invalid."""

    def __init__(self, message: str = "Study name cannot be empty"):
        super().__init__(message, "N2-E-001")


class NoStagesError(ConfigurationError):
    """Raised when Study has no stages defined."""

    def __init__(self, message: str = "Study must have at least one stage"):
        super().__init__(message, "N2-E-002")


class SnapshotPathError(ConfigurationError):
    """Raised when snapshot_path is missing or invalid."""

    def __init__(self, message: str = "Study must specify a snapshot_path"):
        super().__init__(message, "N2-E-003")


class TrialBudgetError(ConfigurationError):
    """Raised when trial_budget is invalid."""

    def __init__(self, stage_idx: int, message: Optional[str] = None):
        msg = message or f"Stage {stage_idx} trial_budget must be positive"
        super().__init__(msg, "N2-E-004", {"stage_idx": stage_idx})


class SurvivorCountError(ConfigurationError):
    """Raised when survivor_count is invalid."""

    def __init__(self, stage_idx: int, message: Optional[str] = None):
        msg = message or f"Stage {stage_idx} survivor_count must be positive"
        super().__init__(msg, "N2-E-005", {"stage_idx": stage_idx})


class SurvivorBudgetMismatchError(ConfigurationError):
    """Raised when survivor_count exceeds trial_budget."""

    def __init__(self, stage_idx: int, survivor_count: int, trial_budget: int):
        msg = f"Stage {stage_idx} survivor_count ({survivor_count}) cannot exceed trial_budget ({trial_budget})"
        super().__init__(
            msg,
            "N2-E-006",
            {
                "stage_idx": stage_idx,
                "survivor_count": survivor_count,
                "trial_budget": trial_budget,
            },
        )


class TimeoutConfigError(ConfigurationError):
    """Raised when timeout configuration is invalid."""

    def __init__(self, message: str):
        super().__init__(message, "N2-E-007")


class ECOBlacklistWhitelistConflictError(ConfigurationError):
    """Raised when ECO appears in both blacklist and whitelist."""

    def __init__(self, eco_names: list[str]):
        msg = f"ECOs cannot be in both blacklist and whitelist: {eco_names}"
        super().__init__(msg, "N2-E-008", {"conflicting_ecos": eco_names})


# =============================================================================
# Case Management Errors (N2-E-100 to N2-E-149)
# =============================================================================


class CaseManagementError(Noodle2Error):
    """Base class for case management errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, details)


class InvalidCaseIdentifierError(CaseManagementError):
    """Raised when case identifier format is invalid."""

    def __init__(self, case_id: str, reason: Optional[str] = None):
        msg = f"Invalid case identifier format: {case_id}"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg, "N2-E-100", {"case_id": case_id})


class DuplicateCaseError(CaseManagementError):
    """Raised when attempting to add duplicate case to graph."""

    def __init__(self, case_id: str):
        msg = f"Case '{case_id}' already exists in case graph"
        super().__init__(msg, "N2-E-101", {"case_id": case_id})


class ParentCaseNotFoundError(CaseManagementError):
    """Raised when parent case doesn't exist in graph."""

    def __init__(self, case_id: str, parent_id: str):
        msg = f"Parent case '{parent_id}' not found for case '{case_id}'"
        super().__init__(
            msg, "N2-E-102", {"case_id": case_id, "parent_id": parent_id}
        )


class CaseNotFoundError(CaseManagementError):
    """Raised when case is not found in graph."""

    def __init__(self, case_id: str):
        msg = f"Case '{case_id}' not found in case graph"
        super().__init__(msg, "N2-E-103", {"case_id": case_id})


# =============================================================================
# ECO Execution Errors (N2-E-150 to N2-E-199)
# =============================================================================


class ECOExecutionError(Noodle2Error):
    """Base class for ECO execution errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, details)


class ECONotAllowedError(ECOExecutionError):
    """Raised when ECO is not allowed by Study configuration."""

    def __init__(self, eco_name: str, reason: str):
        msg = f"ECO '{eco_name}' is not allowed: {reason}"
        super().__init__(msg, "N2-E-150", {"eco_name": eco_name, "reason": reason})


class ECOParameterError(ECOExecutionError):
    """Raised when ECO parameter is invalid."""

    def __init__(self, eco_name: str, param_name: str, message: str):
        msg = f"Invalid parameter '{param_name}' for ECO '{eco_name}': {message}"
        super().__init__(
            msg, "N2-E-151", {"eco_name": eco_name, "param_name": param_name}
        )


class RiskEnvelopeViolationError(ECOExecutionError):
    """Raised when ECO violates risk envelope constraints."""

    def __init__(self, eco_name: str, violations: list[str]):
        msg = f"ECO '{eco_name}' violated risk envelope: {', '.join(violations)}"
        super().__init__(
            msg, "N2-E-152", {"eco_name": eco_name, "violations": violations}
        )


# =============================================================================
# Trial Execution Errors (N2-E-200 to N2-E-249)
# =============================================================================


class TrialExecutionError(Noodle2Error):
    """Base class for trial execution errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, details)


class DockerImageNotFoundError(TrialExecutionError):
    """Raised when Docker image is not available."""

    def __init__(self, image: str):
        msg = f"Docker image not found: {image}"
        super().__init__(msg, "N2-E-200", {"image": image})


class SnapshotNotFoundError(TrialExecutionError):
    """Raised when snapshot directory/file is not found."""

    def __init__(self, snapshot_path: str):
        msg = f"Snapshot not found: {snapshot_path}"
        super().__init__(msg, "N2-E-201", {"snapshot_path": snapshot_path})


class TrialTimeoutError(TrialExecutionError):
    """Raised when trial exceeds timeout."""

    def __init__(self, timeout_seconds: int, trial_id: Optional[str] = None):
        msg = f"Trial exceeded timeout of {timeout_seconds} seconds"
        if trial_id:
            msg = f"Trial '{trial_id}' {msg}"
        super().__init__(
            msg, "N2-E-202", {"timeout_seconds": timeout_seconds, "trial_id": trial_id}
        )


class ContainerExecutionError(TrialExecutionError):
    """Raised when container execution fails."""

    def __init__(self, return_code: int, stderr: Optional[str] = None):
        msg = f"Container execution failed with return code {return_code}"
        super().__init__(
            msg, "N2-E-203", {"return_code": return_code, "stderr": stderr}
        )


# =============================================================================
# Parsing Errors (N2-E-250 to N2-E-299)
# =============================================================================


class ParsingError(Noodle2Error):
    """Base class for parsing errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, details)


class TimingReportParseError(ParsingError):
    """Raised when timing report cannot be parsed."""

    def __init__(self, file_path: str, reason: str):
        msg = f"Failed to parse timing report '{file_path}': {reason}"
        super().__init__(msg, "N2-E-250", {"file_path": file_path, "reason": reason})


class CongestionReportParseError(ParsingError):
    """Raised when congestion report cannot be parsed."""

    def __init__(self, file_path: str, reason: str):
        msg = f"Failed to parse congestion report '{file_path}': {reason}"
        super().__init__(msg, "N2-E-251", {"file_path": file_path, "reason": reason})


class CustomMetricParseError(ParsingError):
    """Raised when custom metric extraction fails."""

    def __init__(self, metric_name: str, reason: str):
        msg = f"Failed to extract custom metric '{metric_name}': {reason}"
        super().__init__(
            msg, "N2-E-252", {"metric_name": metric_name, "reason": reason}
        )


# =============================================================================
# Safety and Policy Errors (N2-E-300 to N2-E-349)
# =============================================================================


class SafetyError(Noodle2Error):
    """Base class for safety and policy errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, details)


class IllegalStudyConfigurationError(SafetyError):
    """Raised when Study configuration violates safety rules."""

    def __init__(self, reason: str):
        msg = f"Illegal Study configuration: {reason}"
        super().__init__(msg, "N2-E-300", {"reason": reason})


class AbortThresholdExceededError(SafetyError):
    """Raised when abort threshold is exceeded."""

    def __init__(self, metric_name: str, value: float, threshold: float):
        msg = f"Abort threshold exceeded: {metric_name} = {value} (threshold: {threshold})"
        super().__init__(
            msg,
            "N2-E-301",
            {"metric_name": metric_name, "value": value, "threshold": threshold},
        )


class StageGateFailureError(SafetyError):
    """Raised when stage gate conditions are not met."""

    def __init__(self, stage_idx: int, reason: str):
        msg = f"Stage {stage_idx} gate failure: {reason}"
        super().__init__(msg, "N2-E-302", {"stage_idx": stage_idx, "reason": reason})


# =============================================================================
# File and I/O Errors (N2-E-350 to N2-E-399)
# =============================================================================


class FileOperationError(Noodle2Error):
    """Base class for file and I/O errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict] = None):
        super().__init__(message, error_code, details)


class ArtifactNotFoundError(FileOperationError):
    """Raised when expected artifact file is not found."""

    def __init__(self, artifact_path: str, artifact_type: str):
        msg = f"{artifact_type} artifact not found: {artifact_path}"
        super().__init__(
            msg,
            "N2-E-350",
            {"artifact_path": artifact_path, "artifact_type": artifact_type},
        )


class TelemetryWriteError(FileOperationError):
    """Raised when telemetry cannot be written."""

    def __init__(self, file_path: str, reason: str):
        msg = f"Failed to write telemetry to '{file_path}': {reason}"
        super().__init__(msg, "N2-E-351", {"file_path": file_path, "reason": reason})


class YAMLParseError(FileOperationError):
    """Raised when YAML configuration cannot be parsed."""

    def __init__(self, file_path: str, reason: str):
        msg = f"Failed to parse YAML file '{file_path}': {reason}"
        super().__init__(msg, "N2-E-352", {"file_path": file_path, "reason": reason})


# =============================================================================
# Error Code Registry
# =============================================================================

ERROR_CODE_REGISTRY = {
    # Configuration and Validation Errors (001-099)
    "N2-E-001": "Study name cannot be empty",
    "N2-E-002": "Study must have at least one stage",
    "N2-E-003": "Study must specify a snapshot_path",
    "N2-E-004": "Stage trial_budget must be positive",
    "N2-E-005": "Stage survivor_count must be positive",
    "N2-E-006": "Stage survivor_count cannot exceed trial_budget",
    "N2-E-007": "Invalid timeout configuration",
    "N2-E-008": "ECO cannot be in both blacklist and whitelist",
    # Case Management Errors (100-149)
    "N2-E-100": "Invalid case identifier format",
    "N2-E-101": "Case already exists in case graph",
    "N2-E-102": "Parent case not found for derived case",
    "N2-E-103": "Case not found in case graph",
    # ECO Execution Errors (150-199)
    "N2-E-150": "ECO not allowed by Study configuration",
    "N2-E-151": "Invalid ECO parameter",
    "N2-E-152": "ECO violated risk envelope constraints",
    # Trial Execution Errors (200-249)
    "N2-E-200": "Docker image not found",
    "N2-E-201": "Snapshot not found",
    "N2-E-202": "Trial exceeded timeout",
    "N2-E-203": "Container execution failed",
    # Parsing Errors (250-299)
    "N2-E-250": "Failed to parse timing report",
    "N2-E-251": "Failed to parse congestion report",
    "N2-E-252": "Failed to extract custom metric",
    # Safety and Policy Errors (300-349)
    "N2-E-300": "Illegal Study configuration",
    "N2-E-301": "Abort threshold exceeded",
    "N2-E-302": "Stage gate conditions not met",
    # File and I/O Errors (350-399)
    "N2-E-350": "Artifact not found",
    "N2-E-351": "Failed to write telemetry",
    "N2-E-352": "Failed to parse YAML configuration",
}


def get_error_code_description(error_code: str) -> Optional[str]:
    """
    Get human-readable description for an error code.

    Args:
        error_code: Error code (e.g., "N2-E-001")

    Returns:
        Description string if found, None otherwise
    """
    return ERROR_CODE_REGISTRY.get(error_code)
