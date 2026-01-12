"""Core type definitions for Noodle 2 controller."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .exceptions import (
    ECOBlacklistWhitelistConflictError,
    InvalidCaseIdentifierError,
    NoStagesError,
    SnapshotPathError,
    StudyNameError,
    SurvivorBudgetMismatchError,
    SurvivorCountError,
    TimeoutConfigError,
    TrialBudgetError,
)


class SafetyDomain(str, Enum):
    """Safety domain for a Study."""

    SANDBOX = "sandbox"  # exploratory, permissive
    GUARDED = "guarded"  # default, production-like
    LOCKED = "locked"  # conservative, regression-only


class ECOClass(str, Enum):
    """ECO classification by blast radius."""

    TOPOLOGY_NEUTRAL = "topology_neutral"
    PLACEMENT_LOCAL = "placement_local"
    ROUTING_AFFECTING = "routing_affecting"
    GLOBAL_DISRUPTIVE = "global_disruptive"


class StageType(str, Enum):
    """Type of stage - execution or approval gate."""

    EXECUTION = "execution"  # Normal execution stage with trials
    HUMAN_APPROVAL = "human_approval"  # Human approval gate between stages


class ExecutionMode(str, Enum):
    """Execution mode for a Stage."""

    STA_ONLY = "sta_only"
    STA_CONGESTION = "sta_congestion"
    FULL_ROUTE = "full_route"


class FailureType(str, Enum):
    """Classification of trial failures."""

    EARLY_CRASH = "early_crash"
    TOOL_ERROR = "tool_error"
    PARSE_FAILURE = "parse_failure"
    TIMEOUT = "timeout"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    VIOLATION_THRESHOLD = "violation_threshold"
    VISUALIZATION_UNAVAILABLE = "visualization_unavailable"


class FailureSeverity(str, Enum):
    """Severity classification for failures."""

    BENIGN = "benign"
    MODERATE = "moderate"
    SEVERE = "severe"
    CATASTROPHIC = "catastrophic"


@dataclass
class StageConfig:
    """Configuration for a single Stage within a Study."""

    name: str
    stage_type: StageType = StageType.EXECUTION  # Type of stage
    # Execution stage fields
    execution_mode: ExecutionMode | None = None
    trial_budget: int = 0
    survivor_count: int = 0
    allowed_eco_classes: list[ECOClass] = field(default_factory=list)
    abort_threshold_wns_ps: int | None = None  # If WNS worse than this, abort
    visualization_enabled: bool = False
    timeout_seconds: int = 3600  # 1 hour default (hard timeout)
    soft_timeout_seconds: int | None = None  # Optional warning threshold
    # Human approval gate fields
    required_approvers: int = 1  # Number of required approvers
    timeout_hours: int = 24  # Timeout for approval in hours

    def __post_init__(self) -> None:
        """Validate stage configuration based on stage type."""
        if self.stage_type == StageType.EXECUTION:
            # Validate execution stage fields
            if self.execution_mode is None:
                raise ValueError("execution_mode is required for execution stages")
            if self.trial_budget <= 0:
                raise ValueError("trial_budget must be positive for execution stages")
            if self.survivor_count <= 0:
                raise ValueError("survivor_count must be positive for execution stages")
            if self.survivor_count > self.trial_budget:
                raise ValueError(f"survivor_count ({self.survivor_count}) cannot exceed trial_budget ({self.trial_budget})")
            # Validate timeout configuration
            if self.soft_timeout_seconds is not None:
                if self.soft_timeout_seconds <= 0:
                    raise TimeoutConfigError("soft_timeout_seconds must be positive")
                if self.soft_timeout_seconds >= self.timeout_seconds:
                    raise TimeoutConfigError("soft_timeout_seconds must be less than timeout_seconds (hard timeout)")
        elif self.stage_type == StageType.HUMAN_APPROVAL:
            # Validate approval gate fields
            if self.required_approvers < 1:
                raise ValueError("required_approvers must be at least 1")
            if self.timeout_hours < 1:
                raise ValueError("timeout_hours must be at least 1")


@dataclass
class StudyConfig:
    """Complete Study definition."""

    name: str
    safety_domain: SafetyDomain
    base_case_name: str
    pdk: str  # e.g., "Nangate45", "ASAP7", "Sky130"
    stages: list[StageConfig]
    snapshot_path: str  # Path to design snapshot/checkpoint
    metadata: dict[str, Any] = field(default_factory=dict)
    snapshot_hash: str | None = None  # SHA-256 hash for integrity verification
    # Study metadata for documentation and cataloging
    author: str | None = None  # Study author/creator
    creation_date: str | None = None  # ISO 8601 format creation timestamp
    description: str | None = None  # Human-readable Study description
    # ECO filtering constraints
    eco_blacklist: list[str] = field(default_factory=list)  # ECOs to exclude
    eco_whitelist: list[str] | None = None  # If set, only these ECOs allowed
    # Study organization and cataloging
    tags: list[str] = field(default_factory=list)  # Tags for organization and filtering
    # Environment variables for trial execution
    environment: dict[str, str] = field(default_factory=dict)  # Environment variables passed to Docker
    # Notification configuration
    notification_webhook_url: str | None = None  # URL to send notifications
    notification_events: list[str] | None = None  # Events to notify about (defaults to completion/failure)
    # Custom script mounting for ECO execution
    custom_script_mounts: dict[str, str] = field(default_factory=dict)  # {host_path: container_path} for custom ECO scripts
    # PDK override for versioned PDK bind mounting
    pdk_override: Any = None  # PDKOverride instance for bind-mounted versioned PDK

    def validate(self) -> None:
        """Validate Study configuration."""
        if not self.name:
            raise StudyNameError()
        if not self.stages:
            raise NoStagesError()
        if not self.snapshot_path:
            raise SnapshotPathError()

        # Validate stage configurations
        for idx, stage in enumerate(self.stages):
            # Only validate execution-specific fields for execution stages
            if stage.stage_type == StageType.EXECUTION:
                if stage.trial_budget <= 0:
                    raise TrialBudgetError(idx)
                if stage.survivor_count <= 0:
                    raise SurvivorCountError(idx)
                if stage.survivor_count > stage.trial_budget:
                    raise SurvivorBudgetMismatchError(
                        idx, stage.survivor_count, stage.trial_budget
                    )

        # Validate ECO blacklist and whitelist are mutually sensible
        if self.eco_whitelist is not None and self.eco_blacklist:
            # Check for overlap between blacklist and whitelist
            overlap = set(self.eco_blacklist) & set(self.eco_whitelist)
            if overlap:
                raise ECOBlacklistWhitelistConflictError(sorted(overlap))

    def is_eco_allowed(self, eco_name: str) -> tuple[bool, str | None]:
        """Check if an ECO is allowed by this Study's constraints.

        Args:
            eco_name: Name of the ECO to check

        Returns:
            Tuple of (allowed: bool, reason: str | None)
            If allowed=False, reason explains why
        """
        # Check whitelist first (if configured, it's a hard constraint)
        if self.eco_whitelist is not None:
            if eco_name not in self.eco_whitelist:
                return False, f"ECO '{eco_name}' not in Study whitelist"
            # ECO is whitelisted, continue to blacklist check

        # Check blacklist
        if eco_name in self.eco_blacklist:
            return False, f"ECO '{eco_name}' is blacklisted in this Study"

        # ECO is allowed
        return True, None


@dataclass
class CaseIdentifier:
    """Deterministic case naming: <case_name>_<stage_index>_<derived_index>."""

    case_name: str
    stage_index: int
    derived_index: int

    def __str__(self) -> str:
        """Generate deterministic case name."""
        return f"{self.case_name}_{self.stage_index}_{self.derived_index}"

    @classmethod
    def from_string(cls, case_id: str) -> "CaseIdentifier":
        """Parse case identifier from string."""
        parts = case_id.rsplit("_", 2)
        if len(parts) != 3:
            raise InvalidCaseIdentifierError(case_id, "must have format <name>_<stage>_<derived>")
        case_name, stage_str, derived_str = parts
        try:
            stage_index = int(stage_str)
            derived_index = int(derived_str)
        except ValueError as e:
            raise InvalidCaseIdentifierError(case_id, "stage and derived indices must be integers") from e
        return cls(case_name=case_name, stage_index=stage_index, derived_index=derived_index)


@dataclass
class TimingPath:
    """Detailed timing path information."""

    slack_ps: int  # Path slack in picoseconds
    startpoint: str  # Starting point (e.g., input port or register)
    endpoint: str  # Ending point (e.g., register or output port)
    path_group: str | None = None  # Path group (e.g., clock name)
    path_type: str | None = None  # Path type (e.g., "max", "min")


@dataclass
class TimingViolationBreakdown:
    """Breakdown of timing violations by type."""

    setup_violations: int = 0  # Number of setup (max path) violations
    hold_violations: int = 0  # Number of hold (min path) violations
    total_violations: int = 0  # Total number of violations
    worst_setup_slack_ps: int | None = None  # Worst setup path slack
    worst_hold_slack_ps: int | None = None  # Worst hold path slack


@dataclass
class TimingMetrics:
    """Timing analysis results."""

    wns_ps: int  # Worst Negative Slack in picoseconds
    tns_ps: int | None = None  # Total Negative Slack in picoseconds
    failing_endpoints: int | None = None
    critical_path_delay_ps: int | None = None
    top_paths: list[TimingPath] = field(default_factory=list)  # Top N critical paths
    violation_breakdown: TimingViolationBreakdown | None = None  # Violation classification


@dataclass
class CongestionMetrics:
    """Congestion analysis results."""

    bins_total: int
    bins_hot: int
    hot_ratio: float
    max_overflow: int | None = None
    layer_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class DRVMetrics:
    """Design Rule Violation (DRV) analysis results."""

    total_violations: int  # Total number of DRC violations
    violation_types: dict[str, int] = field(default_factory=dict)  # Count by type (spacing, width, etc)
    critical_violations: int | None = None  # Count of critical/blocking violations
    warning_violations: int | None = None  # Count of non-critical warnings


@dataclass
class TrialMetrics:
    """Complete metrics for a single trial."""

    timing: TimingMetrics
    congestion: CongestionMetrics | None = None
    drv: DRVMetrics | None = None  # Design rule violations
    runtime_seconds: float = 0.0
    memory_mb: float = 0.0


@dataclass
class TrialResult:
    """Result of executing a single trial."""

    case_id: str
    eco_name: str
    success: bool
    metrics: TrialMetrics | None = None
    failure_type: FailureType | None = None
    failure_severity: FailureSeverity | None = None
    failure_reason: str | None = None
    artifact_path: str | None = None
    log_excerpt: str | None = None
    return_code: int = 0
    timestamp: str = ""
