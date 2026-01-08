"""Failure classification and detection for Noodle 2 trials."""

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any


class FailureType(str, Enum):
    """Types of trial failures."""

    # Early failures (before meaningful work)
    TOOL_CRASH = "tool_crash"  # Non-zero exit code
    MISSING_OUTPUT = "missing_output"  # Required files not produced
    PARSE_FAILURE = "parse_failure"  # Output parsing failed
    TIMEOUT = "timeout"  # Trial exceeded time limit
    OOM = "out_of_memory"  # Out of memory error
    TOOL_MISSING = "tool_missing"  # Required tool not in container
    VISUALIZATION_UNAVAILABLE = "visualization_unavailable"  # GUI mode not available

    # Execution failures (during meaningful work)
    PLACEMENT_FAILED = "placement_failed"
    ROUTING_FAILED = "routing_failed"
    STA_FAILED = "sta_failed"
    DRC_VIOLATION = "drc_violation"
    LVS_VIOLATION = "lvs_violation"

    # Configuration/input failures
    INVALID_ECO = "invalid_eco"
    INVALID_SNAPSHOT = "invalid_snapshot"
    CONFIGURATION_ERROR = "configuration_error"

    # Catastrophic failures
    SEGFAULT = "segfault"  # Segmentation fault
    CORE_DUMP = "core_dump"  # Core dump detected

    # Transient failures (may succeed on retry)
    NETWORK_ERROR = "network_error"  # Network connectivity issues
    RESOURCE_BUSY = "resource_busy"  # Resource temporarily unavailable
    CONTAINER_ERROR = "container_error"  # Container orchestration failure
    FILESYSTEM_ERROR = "filesystem_error"  # Temporary filesystem issues

    # Unknown/other
    UNKNOWN = "unknown"


class FailureSeverity(str, Enum):
    """Severity levels for failures."""

    CRITICAL = "critical"  # Unrecoverable, stop immediately
    HIGH = "high"  # Serious issue, likely not fixable
    MEDIUM = "medium"  # Recoverable with intervention
    LOW = "low"  # Minor issue, may be transient
    INFO = "info"  # Not really a failure, just informational


@dataclass
class FailureClassification:
    """
    Deterministic classification of a trial failure.

    This is a first-class, auditable record of why a trial failed.
    """

    failure_type: FailureType
    severity: FailureSeverity
    reason: str  # Human-readable rationale
    log_excerpt: str = ""  # Relevant log snippet
    metrics: dict[str, Any] | None = None
    recoverable: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "failure_type": self.failure_type.value,
            "severity": self.severity.value,
            "reason": self.reason,
            "log_excerpt": self.log_excerpt,
            "metrics": self.metrics or {},
            "recoverable": self.recoverable,
        }


class FailureClassifier:
    """
    Deterministically classify trial failures.

    This class examines trial execution results and classifies failures
    according to type, severity, and recoverability.
    """

    @staticmethod
    def classify_trial_failure(
        return_code: int,
        stdout: str,
        stderr: str,
        artifacts_dir: Path,
        expected_outputs: list[str] | None = None,
    ) -> FailureClassification | None:
        """
        Classify a trial failure deterministically.

        Args:
            return_code: Tool exit code
            stdout: Standard output
            stderr: Standard error
            artifacts_dir: Directory where artifacts should be
            expected_outputs: List of expected output files

        Returns:
            FailureClassification if failure detected, None if success
        """
        # Success case
        if return_code == 0:
            # Even if rc=0, check for missing outputs
            if expected_outputs:
                missing = FailureClassifier._check_missing_outputs(
                    artifacts_dir, expected_outputs
                )
                if missing:
                    return FailureClassification(
                        failure_type=FailureType.MISSING_OUTPUT,
                        severity=FailureSeverity.HIGH,
                        reason=f"Required outputs not produced: {', '.join(missing)}",
                        log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                        recoverable=False,
                    )
            return None  # True success

        # Tool crash (non-zero exit code)
        if return_code != 0:
            # Check for specific error types in output
            combined_output = (stderr + "\n" + stdout).lower()

            # OOM detection
            if any(
                marker in combined_output
                for marker in ["out of memory", "oom", "killed", "signal 9"]
            ):
                return FailureClassification(
                    failure_type=FailureType.OOM,
                    severity=FailureSeverity.CRITICAL,
                    reason=f"Out of memory error (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Segfault detection (catastrophic)
            if any(
                marker in combined_output
                for marker in ["segmentation fault", "segfault", "sigsegv", "signal 11"]
            ) or return_code == 139:  # 139 = 128 + 11 (SIGSEGV)
                return FailureClassification(
                    failure_type=FailureType.SEGFAULT,
                    severity=FailureSeverity.CRITICAL,
                    reason=f"Segmentation fault detected (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Core dump detection (catastrophic)
            if "core dumped" in combined_output or return_code == 134:  # 134 = 128 + 6 (SIGABRT)
                return FailureClassification(
                    failure_type=FailureType.CORE_DUMP,
                    severity=FailureSeverity.CRITICAL,
                    reason=f"Core dump detected (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Transient failures - network errors (check before generic timeout)
            if any(
                marker in combined_output
                for marker in [
                    "network error",
                    "connection refused",
                    "connection timeout",
                    "connection reset",
                    "no route to host",
                    "temporary failure in name resolution",
                ]
            ):
                return FailureClassification(
                    failure_type=FailureType.NETWORK_ERROR,
                    severity=FailureSeverity.MEDIUM,
                    reason=f"Network connectivity issue (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=True,
                )

            # Timeout detection (trial execution timeout, not network)
            if ("timeout" in combined_output and "connection" not in combined_output) or return_code == 124:
                return FailureClassification(
                    failure_type=FailureType.TIMEOUT,
                    severity=FailureSeverity.HIGH,
                    reason=f"Trial exceeded timeout limit (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Tool missing
            if "command not found" in combined_output or "no such file" in combined_output:
                return FailureClassification(
                    failure_type=FailureType.TOOL_MISSING,
                    severity=FailureSeverity.CRITICAL,
                    reason=f"Required tool not found (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Transient failures - resource busy
            if any(
                marker in combined_output
                for marker in [
                    "resource temporarily unavailable",
                    "resource busy",
                    "device busy",
                    "try again later",
                ]
            ):
                return FailureClassification(
                    failure_type=FailureType.RESOURCE_BUSY,
                    severity=FailureSeverity.LOW,
                    reason=f"Resource temporarily unavailable (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=True,
                )

            # Transient failures - container errors
            if any(
                marker in combined_output
                for marker in [
                    "container not found",
                    "container start failed",
                    "container error",
                    "docker error",
                    "failed to create container",
                ]
            ):
                return FailureClassification(
                    failure_type=FailureType.CONTAINER_ERROR,
                    severity=FailureSeverity.MEDIUM,
                    reason=f"Container orchestration failure (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=True,
                )

            # Transient failures - filesystem errors
            if any(
                marker in combined_output
                for marker in [
                    "no space left on device",
                    "disk quota exceeded",
                    "filesystem full",
                    "stale file handle",
                    "input/output error",
                ]
            ) and "oom" not in combined_output:  # Avoid misclassifying OOM
                return FailureClassification(
                    failure_type=FailureType.FILESYSTEM_ERROR,
                    severity=FailureSeverity.MEDIUM,
                    reason=f"Temporary filesystem issue (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=True,
                )

            # ASAP7-specific configuration errors (check before generic placement/routing failures)
            # These require specific workarounds in the TCL script
            if any(
                pattern in combined_output
                for pattern in [
                    "routing track",
                    "routing layer",
                    "infer routing",
                    "routing track information",
                    "routing track spacing",
                    "routing track configuration",
                ]
            ) and any(
                marker in combined_output
                for marker in ["infer", "inference", "cannot determine", "missing", "not specified"]
            ):
                return FailureClassification(
                    failure_type=FailureType.CONFIGURATION_ERROR,
                    severity=FailureSeverity.HIGH,
                    reason=(
                        "ASAP7 routing track inference failed. "
                        "This PDK requires explicit routing layer specification. "
                        "Add set_routing_layers command with metal2-metal9 (signal) and metal6-metal9 (clock) "
                        "to the TCL script before routing."
                    ),
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # ASAP7 site specification errors
            if any(
                pattern in combined_output
                for pattern in [
                    "floorplan site",
                    "site specification",
                    "site dimensions",
                    "determine site",
                    "infer site",
                ]
            ) and any(
                marker in combined_output
                for marker in ["cannot", "missing", "not specified", "unable to infer"]
            ):
                return FailureClassification(
                    failure_type=FailureType.CONFIGURATION_ERROR,
                    severity=FailureSeverity.HIGH,
                    reason=(
                        "ASAP7 site specification failed. "
                        "This PDK requires explicit site specification for floorplanning. "
                        "Add site specification (asap7sc7p5t_28_R_24_NP_162NW_34O) "
                        "to the floorplan commands in the TCL script."
                    ),
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # ASAP7 pin placement/access errors
            if "pin" in combined_output and any(
                pattern in combined_output
                for pattern in [
                    "cannot access pins",
                    "pin access failed",
                    "pin placement failed",
                    "pin layer",
                ]
            ) and "asap7" in combined_output:
                return FailureClassification(
                    failure_type=FailureType.CONFIGURATION_ERROR,
                    severity=FailureSeverity.HIGH,
                    reason=(
                        "ASAP7 pin placement/access failed. "
                        "This PDK requires specific pin layer constraints. "
                        "Add pin placement constraints specifying metal4/metal5 layers "
                        "to the TCL script."
                    ),
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Generic placement failure (after ASAP7-specific checks)
            if "placement" in combined_output and any(
                marker in combined_output for marker in ["failed", "error", "cannot"]
            ):
                return FailureClassification(
                    failure_type=FailureType.PLACEMENT_FAILED,
                    severity=FailureSeverity.HIGH,
                    reason=f"Placement failed (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Generic routing failure (after ASAP7-specific checks)
            if "routing" in combined_output and any(
                marker in combined_output for marker in ["failed", "error", "cannot"]
            ):
                return FailureClassification(
                    failure_type=FailureType.ROUTING_FAILED,
                    severity=FailureSeverity.HIGH,
                    reason=f"Routing failed (exit code {return_code})",
                    log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                    recoverable=False,
                )

            # Generic tool crash
            return FailureClassification(
                failure_type=FailureType.TOOL_CRASH,
                severity=FailureSeverity.HIGH,
                reason=f"Tool exited with non-zero code: {return_code}",
                log_excerpt=FailureClassifier._extract_log_excerpt(stderr, stdout),
                recoverable=False,
            )

        # Shouldn't reach here
        return None

    @staticmethod
    def _check_missing_outputs(
        artifacts_dir: Path, expected_outputs: list[str]
    ) -> list[str]:
        """
        Check for missing output files.

        Args:
            artifacts_dir: Directory to check
            expected_outputs: List of expected filenames

        Returns:
            List of missing filenames
        """
        missing = []
        for output in expected_outputs:
            path = artifacts_dir / output
            if not path.exists():
                missing.append(output)
        return missing

    @staticmethod
    def _extract_log_excerpt(stderr: str, stdout: str, max_lines: int = 20) -> str:
        """
        Extract relevant log excerpt for failure analysis.

        Args:
            stderr: Standard error
            stdout: Standard output
            max_lines: Maximum lines to include

        Returns:
            Log excerpt showing error context
        """
        # Prefer stderr for errors
        if stderr.strip():
            lines = stderr.strip().split("\n")
            # Take last N lines (most recent errors)
            excerpt_lines = lines[-max_lines:]
            return "\n".join(excerpt_lines)

        # Fall back to stdout
        if stdout.strip():
            lines = stdout.strip().split("\n")
            excerpt_lines = lines[-max_lines:]
            return "\n".join(excerpt_lines)

        return ""

    @staticmethod
    def classify_parse_failure(file_path: Path, error_message: str) -> FailureClassification:
        """
        Classify a parsing failure.

        Args:
            file_path: Path to file that failed to parse
            error_message: Parse error message

        Returns:
            FailureClassification for parse failure
        """
        return FailureClassification(
            failure_type=FailureType.PARSE_FAILURE,
            severity=FailureSeverity.HIGH,
            reason=f"Failed to parse {file_path.name}: {error_message}",
            log_excerpt=error_message,
            recoverable=False,
        )

    @staticmethod
    def classify_invalid_eco(eco_name: str, reason: str) -> FailureClassification:
        """
        Classify an invalid ECO configuration.

        Args:
            eco_name: Name of the ECO
            reason: Why it's invalid

        Returns:
            FailureClassification for invalid ECO
        """
        return FailureClassification(
            failure_type=FailureType.INVALID_ECO,
            severity=FailureSeverity.MEDIUM,
            reason=f"Invalid ECO '{eco_name}': {reason}",
            recoverable=True,  # Can be fixed by correcting ECO config
        )

    @staticmethod
    def classify_visualization_unavailable(reason: str) -> FailureClassification:
        """
        Classify visualization unavailability.

        Args:
            reason: Why visualization is not available

        Returns:
            FailureClassification for visualization unavailable
        """
        return FailureClassification(
            failure_type=FailureType.VISUALIZATION_UNAVAILABLE,
            severity=FailureSeverity.INFO,
            reason=f"Visualization not available: {reason}",
            recoverable=True,  # Can fall back to non-GUI mode
        )

    @staticmethod
    def is_catastrophic(failure: FailureClassification) -> bool:
        """
        Determine if a failure is catastrophic.

        Catastrophic failures are unrecoverable and indicate serious
        tool/system issues that require immediate attention. These failures
        should trigger stage abort and ECO class containment.

        Args:
            failure: FailureClassification to check

        Returns:
            True if failure is catastrophic, False otherwise
        """
        # Catastrophic failure types
        catastrophic_types = {
            FailureType.SEGFAULT,
            FailureType.CORE_DUMP,
            FailureType.OOM,
        }

        return failure.failure_type in catastrophic_types or failure.severity == FailureSeverity.CRITICAL

    @staticmethod
    def is_transient(failure: FailureClassification) -> bool:
        """
        Determine if a failure is transient and may succeed on retry.

        Transient failures are temporary issues (network, resource contention,
        container orchestration) that may resolve themselves and are worth
        retrying with exponential backoff.

        Args:
            failure: FailureClassification to check

        Returns:
            True if failure is transient and retriable, False otherwise
        """
        # Transient failure types that are worth retrying
        transient_types = {
            FailureType.NETWORK_ERROR,
            FailureType.RESOURCE_BUSY,
            FailureType.CONTAINER_ERROR,
            FailureType.FILESYSTEM_ERROR,
        }

        return failure.failure_type in transient_types
