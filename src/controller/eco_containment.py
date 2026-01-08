"""ECO class containment for catastrophic failure isolation."""

from dataclasses import dataclass, field
from typing import Any

from .failure import FailureClassification, FailureClassifier
from .types import ECOClass


@dataclass
class ECOClassStatus:
    """Tracks the status of an ECO class within a Study."""

    eco_class: ECOClass
    allowed: bool = True
    catastrophic_failures: int = 0
    total_trials: int = 0
    failure_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_class": self.eco_class.value,
            "allowed": self.allowed,
            "catastrophic_failures": self.catastrophic_failures,
            "total_trials": self.total_trials,
            "failure_reason": self.failure_reason,
        }


class ECOClassContainmentTracker:
    """
    Tracks ECO class status and enforces containment on catastrophic failures.

    When an ECO from a specific class causes a catastrophic failure (e.g.,
    segfault, core dump, OOM), the entire ECO class is marked as
    catastrophically failed and prevented from future use in the Study.

    This prevents a single bad ECO from repeatedly crashing trials and
    wasting compute resources.
    """

    def __init__(self) -> None:
        """Initialize containment tracker with all ECO classes allowed."""
        self.eco_class_status: dict[ECOClass, ECOClassStatus] = {
            eco_class: ECOClassStatus(eco_class=eco_class)
            for eco_class in ECOClass
        }
        self.total_catastrophic_failures = 0

    def record_trial_result(
        self,
        eco_class: ECOClass,
        failure: FailureClassification | None,
    ) -> bool:
        """
        Record a trial result and check for catastrophic failure.

        Args:
            eco_class: ECO class used in the trial
            failure: Failure classification (None if success)

        Returns:
            True if ECO class should be contained (blocked), False otherwise
        """
        status = self.eco_class_status[eco_class]
        status.total_trials += 1

        # Check if this is a catastrophic failure
        if failure and FailureClassifier.is_catastrophic(failure):
            status.catastrophic_failures += 1
            self.total_catastrophic_failures += 1

            # Contain the ECO class immediately on first catastrophic failure
            status.allowed = False
            status.failure_reason = f"Catastrophic failure: {failure.reason}"

            return True  # Should be contained

        return False  # No containment needed

    def is_eco_class_allowed(self, eco_class: ECOClass) -> bool:
        """
        Check if an ECO class is allowed for use.

        Args:
            eco_class: ECO class to check

        Returns:
            True if allowed, False if contained
        """
        return self.eco_class_status[eco_class].allowed

    def get_blocked_eco_classes(self) -> list[ECOClass]:
        """
        Get list of ECO classes that have been blocked due to catastrophic failures.

        Returns:
            List of blocked ECO classes
        """
        return [
            eco_class
            for eco_class, status in self.eco_class_status.items()
            if not status.allowed
        ]

    def get_containment_summary(self) -> dict[str, Any]:
        """
        Get summary of ECO class containment status.

        Returns:
            Dictionary with containment statistics
        """
        blocked_classes = self.get_blocked_eco_classes()

        return {
            "total_catastrophic_failures": self.total_catastrophic_failures,
            "blocked_eco_classes": [c.value for c in blocked_classes],
            "blocked_count": len(blocked_classes),
            "eco_class_details": {
                eco_class.value: status.to_dict()
                for eco_class, status in self.eco_class_status.items()
            },
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert tracker state to dictionary for serialization."""
        return self.get_containment_summary()
