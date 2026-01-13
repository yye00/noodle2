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


class ObjectiveMode(str, Enum):
    """Objective function mode for multi-objective optimization."""

    PARETO = "pareto"  # Pareto frontier - select non-dominated solutions
    WEIGHTED_SUM = "weighted_sum"  # Weighted sum of objectives
    LEXICOGRAPHIC = "lexicographic"  # Prioritize primary, use secondary as tiebreaker


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
    show_summary: bool = True  # Display stage results summary at approval gate
    show_visualizations: bool = False  # Display heatmaps and charts at approval gate
    # Stage dependency enforcement
    requires_approval: str | None = None  # Name of approval gate stage that must be completed before this stage can execute

    def __post_init__(self) -> None:
        """Validate stage configuration based on stage type.

        Note: Most validation is deferred to StudyConfig.validate() where we have
        access to the stage index for better error messages. This method only validates
        fields that can provide good error messages without the index.
        """
        if self.stage_type == StageType.EXECUTION:
            # Validate timeout configuration (can provide good error messages)
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
class ObjectiveConfig:
    """Configuration for multi-objective optimization.

    Defines how multiple objectives (timing, congestion, area, power) are
    combined and optimized during survivor selection.
    """

    mode: ObjectiveMode = ObjectiveMode.WEIGHTED_SUM  # Optimization mode
    primary: str = "wns_ps"  # Primary objective (e.g., "wns_ps", "hot_ratio")
    secondary: str | None = None  # Secondary objective for tiebreaking or Pareto
    weights: list[float] | None = None  # Weights for weighted_sum mode [primary_weight, secondary_weight]

    def __post_init__(self) -> None:
        """Validate objective configuration."""
        if not self.primary:
            raise ValueError("primary objective must be specified")

        if self.mode == ObjectiveMode.WEIGHTED_SUM:
            if self.weights is None:
                # Default weights if not specified
                self.weights = [0.6, 0.4] if self.secondary else [1.0]
            if self.secondary and len(self.weights) != 2:
                raise ValueError("weighted_sum mode with secondary objective requires exactly 2 weights")
            if self.weights:
                if any(w < 0 or w > 1 for w in self.weights):
                    raise ValueError("weights must be between 0.0 and 1.0")
                if abs(sum(self.weights) - 1.0) > 0.01:
                    raise ValueError(f"weights must sum to 1.0, got {sum(self.weights)}")

        elif self.mode in (ObjectiveMode.PARETO, ObjectiveMode.LEXICOGRAPHIC):
            if not self.secondary:
                raise ValueError(f"{self.mode.value} mode requires both primary and secondary objectives")


@dataclass
class DiagnosisConfig:
    """Configuration for auto-diagnosis analysis.

    Controls how timing and congestion diagnosis is performed during
    study execution, including analysis depth and thresholds.
    """

    enabled: bool = True  # Enable auto-diagnosis
    timing_paths: int = 20  # Number of critical paths to analyze
    hotspot_threshold: float = 0.7  # Congestion ratio threshold for hotspot identification
    wire_delay_threshold: float = 0.65  # Wire delay ratio for wire-dominated classification

    def __post_init__(self) -> None:
        """Validate diagnosis configuration."""
        if self.timing_paths < 1:
            raise ValueError("timing_paths must be at least 1")
        if not (0.0 < self.hotspot_threshold <= 1.0):
            raise ValueError("hotspot_threshold must be between 0.0 and 1.0")
        if not (0.0 < self.wire_delay_threshold <= 1.0):
            raise ValueError("wire_delay_threshold must be between 0.0 and 1.0")


@dataclass
class AbortRailConfig:
    """Abort rail configuration - stops individual trials."""

    wns_ps: int | None = None  # Abort trial if WNS worse than this (e.g., -10000 = -10ns)
    timeout_seconds: int | None = None  # Abort trial if execution exceeds this

    def __post_init__(self) -> None:
        """Validate abort rail configuration."""
        if self.timeout_seconds is not None and self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


@dataclass
class StageRailConfig:
    """Stage rail configuration - stops stages early."""

    failure_rate: float | None = None  # Stop stage if failure rate exceeds this (0.0-1.0)

    def __post_init__(self) -> None:
        """Validate stage rail configuration."""
        if self.failure_rate is not None:
            if not (0.0 < self.failure_rate <= 1.0):
                raise ValueError("failure_rate must be between 0.0 and 1.0")


@dataclass
class StudyRailConfig:
    """Study rail configuration - stops entire study."""

    catastrophic_failures: int | None = None  # Stop study after N catastrophic failures
    max_runtime_hours: int | None = None  # Stop study after N hours total

    def __post_init__(self) -> None:
        """Validate study rail configuration."""
        if self.catastrophic_failures is not None and self.catastrophic_failures <= 0:
            raise ValueError("catastrophic_failures must be positive")
        if self.max_runtime_hours is not None and self.max_runtime_hours <= 0:
            raise ValueError("max_runtime_hours must be positive")


@dataclass
class RailsConfig:
    """Safety rails configuration for a Study.

    Rails provide safety-critical limits to prevent runaway computation,
    pathological ECOs, or wasting resources on fundamentally broken experiments.
    """

    abort: AbortRailConfig = field(default_factory=AbortRailConfig)
    stage: StageRailConfig = field(default_factory=StageRailConfig)
    study: StudyRailConfig = field(default_factory=StudyRailConfig)


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
    # Diagnosis configuration for auto-analysis
    diagnosis: DiagnosisConfig = field(default_factory=DiagnosisConfig)  # Auto-diagnosis configuration
    # Objective configuration for multi-objective optimization
    objective: ObjectiveConfig = field(default_factory=ObjectiveConfig)  # Multi-objective optimization configuration
    # Safety rails configuration
    rails: RailsConfig = field(default_factory=RailsConfig)  # Safety rails for abort/stage/study limits

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
                if stage.execution_mode is None:
                    raise ValueError(f"Stage {idx} execution_mode is required for execution stages")
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
