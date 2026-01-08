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
from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)
from src.controller.telemetry import (
    CaseTelemetry,
    StageTelemetry,
    StudyTelemetry,
    TelemetryEmitter,
)

# Note: StudyExecutor, StudyResult, and StageResult are not exported here
# to avoid circular imports. Import them directly from src.controller.executor

__all__ = [
    "FailureType",
    "FailureSeverity",
    "FailureClassification",
    "FailureClassifier",
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
]
