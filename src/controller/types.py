"""Core type definitions for Noodle 2 controller."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


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
    execution_mode: ExecutionMode
    trial_budget: int
    survivor_count: int
    allowed_eco_classes: list[ECOClass]
    abort_threshold_wns_ps: int | None = None  # If WNS worse than this, abort
    visualization_enabled: bool = False
    timeout_seconds: int = 3600  # 1 hour default


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

    def validate(self) -> None:
        """Validate Study configuration."""
        if not self.name:
            raise ValueError("Study name cannot be empty")
        if not self.stages:
            raise ValueError("Study must have at least one stage")
        if not self.snapshot_path:
            raise ValueError("Study must specify a snapshot_path")

        # Validate stage indices are sequential
        for idx, stage in enumerate(self.stages):
            if stage.trial_budget <= 0:
                raise ValueError(f"Stage {idx} trial_budget must be positive")
            if stage.survivor_count <= 0:
                raise ValueError(f"Stage {idx} survivor_count must be positive")
            if stage.survivor_count > stage.trial_budget:
                raise ValueError(
                    f"Stage {idx} survivor_count ({stage.survivor_count}) "
                    f"cannot exceed trial_budget ({stage.trial_budget})"
                )


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
            raise ValueError(f"Invalid case identifier format: {case_id}")
        case_name, stage_str, derived_str = parts
        try:
            stage_index = int(stage_str)
            derived_index = int(derived_str)
        except ValueError as e:
            raise ValueError(f"Invalid case identifier format: {case_id}") from e
        return cls(case_name=case_name, stage_index=stage_index, derived_index=derived_index)


@dataclass
class TimingMetrics:
    """Timing analysis results."""

    wns_ps: int  # Worst Negative Slack in picoseconds
    tns_ps: int | None = None  # Total Negative Slack in picoseconds
    failing_endpoints: int | None = None
    critical_path_delay_ps: int | None = None


@dataclass
class CongestionMetrics:
    """Congestion analysis results."""

    bins_total: int
    bins_hot: int
    hot_ratio: float
    max_overflow: int | None = None
    layer_metrics: dict[str, Any] = field(default_factory=dict)


@dataclass
class TrialMetrics:
    """Complete metrics for a single trial."""

    timing: TimingMetrics
    congestion: CongestionMetrics | None = None
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
