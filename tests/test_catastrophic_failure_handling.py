"""Tests for catastrophic failure detection and ECO class containment."""

import pytest
from pathlib import Path

from src.controller.eco_containment import ECOClassContainmentTracker, ECOClassStatus
from src.controller.failure import FailureClassification, FailureClassifier, FailureType, FailureSeverity
from src.controller.types import ECOClass


class TestCatastrophicFailureDetection:
    """Test detection of catastrophic failures."""

    def test_segfault_detected_by_exit_code(self):
        """Segfault should be detected by exit code 139."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=139,
            stdout="",
            stderr="",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.SEGFAULT
        assert classification.severity == FailureSeverity.CRITICAL
        assert not classification.recoverable
        assert "segmentation fault" in classification.reason.lower()

    def test_segfault_detected_by_output(self):
        """Segfault should be detected in stderr output."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Segmentation fault (core dumped)",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.SEGFAULT
        assert classification.severity == FailureSeverity.CRITICAL

    def test_core_dump_detected_by_exit_code(self):
        """Core dump should be detected by exit code 134."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=134,
            stdout="",
            stderr="",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.CORE_DUMP
        assert classification.severity == FailureSeverity.CRITICAL
        assert not classification.recoverable

    def test_core_dump_detected_by_output(self):
        """Core dump should be detected in stderr output."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=1,
            stdout="",
            stderr="Aborted (core dumped)",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.CORE_DUMP
        assert classification.severity == FailureSeverity.CRITICAL

    def test_oom_is_catastrophic(self):
        """OOM failures should be classified as catastrophic."""
        classification = FailureClassifier.classify_trial_failure(
            return_code=137,
            stdout="",
            stderr="Out of memory: Killed process 12345",
            artifacts_dir=Path("/tmp/test"),
            expected_outputs=None,
        )

        assert classification is not None
        assert classification.failure_type == FailureType.OOM
        assert classification.severity == FailureSeverity.CRITICAL

    def test_is_catastrophic_helper(self):
        """Test is_catastrophic helper method."""
        # Segfault is catastrophic
        segfault = FailureClassification(
            failure_type=FailureType.SEGFAULT,
            severity=FailureSeverity.CRITICAL,
            reason="Segfault detected",
        )
        assert FailureClassifier.is_catastrophic(segfault)

        # Core dump is catastrophic
        core_dump = FailureClassification(
            failure_type=FailureType.CORE_DUMP,
            severity=FailureSeverity.CRITICAL,
            reason="Core dump detected",
        )
        assert FailureClassifier.is_catastrophic(core_dump)

        # OOM is catastrophic
        oom = FailureClassification(
            failure_type=FailureType.OOM,
            severity=FailureSeverity.CRITICAL,
            reason="Out of memory",
        )
        assert FailureClassifier.is_catastrophic(oom)

        # Timeout is NOT catastrophic (high severity but recoverable)
        timeout = FailureClassification(
            failure_type=FailureType.TIMEOUT,
            severity=FailureSeverity.HIGH,
            reason="Timeout",
        )
        assert not FailureClassifier.is_catastrophic(timeout)

        # Parse failure is NOT catastrophic
        parse_fail = FailureClassification(
            failure_type=FailureType.PARSE_FAILURE,
            severity=FailureSeverity.HIGH,
            reason="Parse failure",
        )
        assert not FailureClassifier.is_catastrophic(parse_fail)


class TestECOClassContainmentTracker:
    """Test ECO class containment tracking."""

    def test_tracker_initializes_with_all_classes_allowed(self):
        """All ECO classes should be allowed initially."""
        tracker = ECOClassContainmentTracker()

        for eco_class in ECOClass:
            assert tracker.is_eco_class_allowed(eco_class)

        assert len(tracker.get_blocked_eco_classes()) == 0

    def test_successful_trial_does_not_block_eco_class(self):
        """Successful trials should not block ECO classes."""
        tracker = ECOClassContainmentTracker()

        # Record successful trial
        should_contain = tracker.record_trial_result(
            eco_class=ECOClass.PLACEMENT_LOCAL,
            failure=None,  # Success
        )

        assert not should_contain
        assert tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL)
        assert len(tracker.get_blocked_eco_classes()) == 0

    def test_non_catastrophic_failure_does_not_block_eco_class(self):
        """Non-catastrophic failures should not block ECO classes."""
        tracker = ECOClassContainmentTracker()

        # Record non-catastrophic failure (timeout)
        failure = FailureClassification(
            failure_type=FailureType.TIMEOUT,
            severity=FailureSeverity.HIGH,
            reason="Timeout",
        )

        should_contain = tracker.record_trial_result(
            eco_class=ECOClass.ROUTING_AFFECTING,
            failure=failure,
        )

        assert not should_contain
        assert tracker.is_eco_class_allowed(ECOClass.ROUTING_AFFECTING)

    def test_catastrophic_failure_blocks_eco_class(self):
        """Catastrophic failure should immediately block ECO class."""
        tracker = ECOClassContainmentTracker()

        # Record catastrophic failure (segfault)
        failure = FailureClassification(
            failure_type=FailureType.SEGFAULT,
            severity=FailureSeverity.CRITICAL,
            reason="Segmentation fault",
        )

        should_contain = tracker.record_trial_result(
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            failure=failure,
        )

        assert should_contain
        assert not tracker.is_eco_class_allowed(ECOClass.GLOBAL_DISRUPTIVE)
        assert ECOClass.GLOBAL_DISRUPTIVE in tracker.get_blocked_eco_classes()

    def test_catastrophic_failure_only_blocks_affected_eco_class(self):
        """Catastrophic failure should only block the affected ECO class."""
        tracker = ECOClassContainmentTracker()

        # Record catastrophic failure for one ECO class
        failure = FailureClassification(
            failure_type=FailureType.CORE_DUMP,
            severity=FailureSeverity.CRITICAL,
            reason="Core dump",
        )

        tracker.record_trial_result(
            eco_class=ECOClass.ROUTING_AFFECTING,
            failure=failure,
        )

        # Only the affected class should be blocked
        assert not tracker.is_eco_class_allowed(ECOClass.ROUTING_AFFECTING)
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL)
        assert tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL)
        assert tracker.is_eco_class_allowed(ECOClass.GLOBAL_DISRUPTIVE)

    def test_multiple_catastrophic_failures_tracked(self):
        """Multiple catastrophic failures should be tracked."""
        tracker = ECOClassContainmentTracker()

        # Record first catastrophic failure
        failure1 = FailureClassification(
            failure_type=FailureType.SEGFAULT,
            severity=FailureSeverity.CRITICAL,
            reason="Segfault",
        )
        tracker.record_trial_result(ECOClass.ROUTING_AFFECTING, failure1)

        # Record second catastrophic failure (different class)
        failure2 = FailureClassification(
            failure_type=FailureType.OOM,
            severity=FailureSeverity.CRITICAL,
            reason="OOM",
        )
        tracker.record_trial_result(ECOClass.GLOBAL_DISRUPTIVE, failure2)

        # Both classes should be blocked
        blocked = tracker.get_blocked_eco_classes()
        assert len(blocked) == 2
        assert ECOClass.ROUTING_AFFECTING in blocked
        assert ECOClass.GLOBAL_DISRUPTIVE in blocked

        # Total catastrophic failures should be 2
        summary = tracker.get_containment_summary()
        assert summary["total_catastrophic_failures"] == 2
        assert summary["blocked_count"] == 2

    def test_containment_summary(self):
        """Containment summary should provide complete status."""
        tracker = ECOClassContainmentTracker()

        # Record some trials
        segfault = FailureClassification(
            failure_type=FailureType.SEGFAULT,
            severity=FailureSeverity.CRITICAL,
            reason="Segfault",
        )
        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, segfault)
        tracker.record_trial_result(ECOClass.TOPOLOGY_NEUTRAL, None)  # Success

        summary = tracker.get_containment_summary()

        assert summary["total_catastrophic_failures"] == 1
        assert summary["blocked_count"] == 1
        assert "placement_local" in summary["blocked_eco_classes"]
        assert "eco_class_details" in summary

        # Check details for blocked class
        placement_details = summary["eco_class_details"]["placement_local"]
        assert not placement_details["allowed"]
        assert placement_details["catastrophic_failures"] == 1
        assert placement_details["total_trials"] == 1

    def test_eco_class_status_serialization(self):
        """ECOClassStatus should serialize to dict correctly."""
        status = ECOClassStatus(
            eco_class=ECOClass.ROUTING_AFFECTING,
            allowed=False,
            catastrophic_failures=2,
            total_trials=5,
            failure_reason="Segfault detected",
        )

        status_dict = status.to_dict()

        assert status_dict["eco_class"] == "routing_affecting"
        assert status_dict["allowed"] is False
        assert status_dict["catastrophic_failures"] == 2
        assert status_dict["total_trials"] == 5
        assert status_dict["failure_reason"] == "Segfault detected"


class TestCatastrophicFailureIntegration:
    """Integration tests for catastrophic failure handling."""

    def test_end_to_end_catastrophic_containment(self):
        """Test complete catastrophic failure containment workflow."""
        tracker = ECOClassContainmentTracker()

        # Simulate trial execution with catastrophic failure
        classification = FailureClassifier.classify_trial_failure(
            return_code=139,  # Segfault
            stdout="OpenROAD running...",
            stderr="Segmentation fault (core dumped)",
            artifacts_dir=Path("/tmp/test"),
        )

        # Verify it's classified as catastrophic
        assert FailureClassifier.is_catastrophic(classification)

        # Record in containment tracker
        should_block = tracker.record_trial_result(
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            failure=classification,
        )

        # Verify ECO class is blocked
        assert should_block
        assert not tracker.is_eco_class_allowed(ECOClass.GLOBAL_DISRUPTIVE)

        # Other classes should still be allowed
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL)

    def test_mixed_failure_types_handled_correctly(self):
        """Test tracker handles mix of catastrophic and normal failures."""
        tracker = ECOClassContainmentTracker()

        # Normal failure
        timeout = FailureClassification(
            failure_type=FailureType.TIMEOUT,
            severity=FailureSeverity.HIGH,
            reason="Timeout",
        )
        tracker.record_trial_result(ECOClass.TOPOLOGY_NEUTRAL, timeout)

        # Catastrophic failure
        segfault = FailureClassification(
            failure_type=FailureType.SEGFAULT,
            severity=FailureSeverity.CRITICAL,
            reason="Segfault",
        )
        tracker.record_trial_result(ECOClass.ROUTING_AFFECTING, segfault)

        # Success
        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, None)

        # Only routing_affecting should be blocked
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL)
        assert not tracker.is_eco_class_allowed(ECOClass.ROUTING_AFFECTING)
        assert tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL)

        # Only one catastrophic failure
        summary = tracker.get_containment_summary()
        assert summary["total_catastrophic_failures"] == 1
        assert summary["blocked_count"] == 1
