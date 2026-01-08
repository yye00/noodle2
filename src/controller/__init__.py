"""
Controller module - Study orchestration and stage progression logic.
"""

from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)

# Note: StudyExecutor, StudyResult, and StageResult are not exported here
# to avoid circular imports. Import them directly from src.controller.executor

__all__ = [
    "FailureType",
    "FailureSeverity",
    "FailureClassification",
    "FailureClassifier",
]
