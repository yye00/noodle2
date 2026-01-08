"""
Controller module - Study orchestration and stage progression logic.
"""

from src.controller.eco import (
    BufferInsertionECO,
    ECO,
    ECOClassStats,
    ECOClassTracker,
    ECOEffectiveness,
    ECOMetadata,
    ECOPrior,
    ECOResult,
    NoOpECO,
    PlacementDensityECO,
    create_eco,
)
from src.controller.eco_containment import (
    ECOClassContainmentTracker,
    ECOClassStatus,
)
from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)
from src.controller.ranking import (
    RankingPolicy,
    RankingWeights,
    create_survivor_selector,
    rank_by_congestion_delta,
    rank_by_wns_delta,
    rank_multi_objective,
)
from src.controller.snapshot import (
    SnapshotHash,
    compute_file_hash,
    compute_snapshot_hash,
    detect_snapshot_tampering,
    verify_snapshot_hash,
)
from src.controller.stage_abort import (
    AbortReason,
    StageAbortDecision,
    check_catastrophic_failure_rate,
    check_no_survivors,
    check_wns_threshold_violation,
    evaluate_stage_abort,
)
from src.controller.telemetry import (
    CaseTelemetry,
    StageTelemetry,
    StudyTelemetry,
    TelemetryEmitter,
)
from src.controller.safety_trace import (
    SafetyGateEvaluation,
    SafetyGateStatus,
    SafetyGateType,
    SafetyTrace,
)
from src.controller.summary_report import (
    SummaryReportConfig,
    SummaryReportGenerator,
)
from src.controller.eco_leaderboard import (
    ECOLeaderboard,
    ECOLeaderboardEntry,
    ECOLeaderboardGenerator,
)
from src.controller.diff_report import (
    CaseDiffReport,
    MetricDelta,
    generate_diff_report,
    save_diff_report,
)
from src.controller.graceful_shutdown import (
    GracefulShutdownHandler,
    ShutdownRequest,
    create_shutdown_handler,
)
from src.controller.ci_runner import (
    CIConfig,
    CIResult,
    CIRunner,
    RegressionBaseline,
    create_ci_config,
)

# Note: StudyExecutor, StudyResult, and StageResult are not exported here
# to avoid circular imports. Import them directly from src.controller.executor

__all__ = [
    "FailureType",
    "FailureSeverity",
    "FailureClassification",
    "FailureClassifier",
    "ECOClassContainmentTracker",
    "ECOClassStatus",
    "CaseTelemetry",
    "StageTelemetry",
    "StudyTelemetry",
    "TelemetryEmitter",
    "ECO",
    "ECOMetadata",
    "ECOResult",
    "ECOEffectiveness",
    "ECOPrior",
    "ECOClassStats",
    "ECOClassTracker",
    "NoOpECO",
    "BufferInsertionECO",
    "PlacementDensityECO",
    "create_eco",
    "RankingPolicy",
    "RankingWeights",
    "rank_by_wns_delta",
    "rank_by_congestion_delta",
    "rank_multi_objective",
    "create_survivor_selector",
    "SnapshotHash",
    "compute_file_hash",
    "compute_snapshot_hash",
    "verify_snapshot_hash",
    "detect_snapshot_tampering",
    "AbortReason",
    "StageAbortDecision",
    "check_wns_threshold_violation",
    "check_catastrophic_failure_rate",
    "check_no_survivors",
    "evaluate_stage_abort",
    "SafetyTrace",
    "SafetyGateEvaluation",
    "SafetyGateType",
    "SafetyGateStatus",
    "SummaryReportConfig",
    "SummaryReportGenerator",
    "ECOLeaderboard",
    "ECOLeaderboardEntry",
    "ECOLeaderboardGenerator",
    "CaseDiffReport",
    "MetricDelta",
    "generate_diff_report",
    "save_diff_report",
    "GracefulShutdownHandler",
    "ShutdownRequest",
    "create_shutdown_handler",
    "CIConfig",
    "CIResult",
    "CIRunner",
    "RegressionBaseline",
    "create_ci_config",
]
