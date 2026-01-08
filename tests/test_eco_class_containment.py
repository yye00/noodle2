"""Tests for ECO class-level failure containment.

This module tests Gate 2 (Controlled Regression) feature: containing failures
at the ECO class scope when systematic failures occur across multiple instances.
"""

import pytest
from dataclasses import dataclass

from src.controller.eco import (
    ECO,
    ECOMetadata,
    ECOResult,
    ECOPrior,
    NoOpECO,
    BufferInsertionECO,
    PlacementDensityECO,
    create_eco,
    ECOClassStats,
    ECOClassTracker,
)
from src.controller.types import ECOClass


class TestECOClassStats:
    """Test ECO class statistics tracking."""

    def test_create_eco_class_stats(self):
        """Test creating ECO class statistics."""
        stats = ECOClassStats(eco_class=ECOClass.TOPOLOGY_NEUTRAL)

        assert stats.eco_class == ECOClass.TOPOLOGY_NEUTRAL
        assert stats.total_applications == 0
        assert stats.failed_applications == 0
        assert stats.is_blacklisted is False
        assert stats.failure_rate == 0.0

    def test_update_with_success(self):
        """Test updating stats with successful application."""
        stats = ECOClassStats(eco_class=ECOClass.TOPOLOGY_NEUTRAL)

        stats.update(success=True)

        assert stats.total_applications == 1
        assert stats.failed_applications == 0
        assert stats.failure_rate == 0.0
        assert stats.is_blacklisted is False

    def test_update_with_failure(self):
        """Test updating stats with failed application."""
        stats = ECOClassStats(eco_class=ECOClass.TOPOLOGY_NEUTRAL)

        stats.update(success=False)

        assert stats.total_applications == 1
        assert stats.failed_applications == 1
        assert stats.failure_rate == 1.0
        # Not blacklisted yet (need 3+ applications)
        assert stats.is_blacklisted is False

    def test_blacklist_on_high_failure_rate(self):
        """Test that class is blacklisted when failure rate exceeds threshold."""
        stats = ECOClassStats(eco_class=ECOClass.PLACEMENT_LOCAL)

        # Record 3 failures
        stats.update(success=False)
        stats.update(success=False)
        stats.update(success=False)

        assert stats.total_applications == 3
        assert stats.failed_applications == 3
        assert stats.failure_rate == 1.0
        assert stats.is_blacklisted is True

    def test_no_blacklist_with_low_failure_rate(self):
        """Test that class is not blacklisted with acceptable failure rate."""
        stats = ECOClassStats(eco_class=ECOClass.PLACEMENT_LOCAL)

        # Record 2 failures, 3 successes (40% failure rate)
        stats.update(success=False)
        stats.update(success=False)
        stats.update(success=True)
        stats.update(success=True)
        stats.update(success=True)

        assert stats.total_applications == 5
        assert stats.failed_applications == 2
        assert stats.failure_rate == 0.4
        assert stats.is_blacklisted is False

    def test_blacklist_threshold_at_70_percent(self):
        """Test blacklist threshold is 70% failure rate."""
        stats = ECOClassStats(eco_class=ECOClass.ROUTING_AFFECTING)

        # 3 failures, 1 success = 75% failure rate
        stats.update(success=False)
        stats.update(success=False)
        stats.update(success=False)
        stats.update(success=True)

        assert stats.failure_rate == 0.75
        assert stats.is_blacklisted is True

        # Test just below threshold
        stats2 = ECOClassStats(eco_class=ECOClass.ROUTING_AFFECTING)
        # 2 failures, 2 successes = 50% failure rate
        stats2.update(success=False)
        stats2.update(success=False)
        stats2.update(success=True)
        stats2.update(success=True)

        assert stats2.failure_rate == 0.5
        assert stats2.is_blacklisted is False


class TestECOClassTracker:
    """Test ECO class tracker."""

    def test_create_tracker(self):
        """Test creating ECO class tracker."""
        tracker = ECOClassTracker()

        assert len(tracker.class_stats) == 0
        assert tracker.get_blacklisted_classes() == []

    def test_record_eco_result(self):
        """Test recording ECO results."""
        tracker = ECOClassTracker()
        eco = NoOpECO()

        tracker.record_eco_result(eco, success=True)

        assert ECOClass.TOPOLOGY_NEUTRAL in tracker.class_stats
        assert tracker.class_stats[ECOClass.TOPOLOGY_NEUTRAL].total_applications == 1
        assert tracker.class_stats[ECOClass.TOPOLOGY_NEUTRAL].failed_applications == 0

    def test_multiple_instances_same_class(self):
        """Test tracking multiple instances of the same ECO class."""
        tracker = ECOClassTracker()

        # Create multiple ECOs of the same class
        eco1 = BufferInsertionECO(max_capacitance=0.2)
        eco2 = BufferInsertionECO(max_capacitance=0.5)

        # Both are PLACEMENT_LOCAL
        assert eco1.metadata.eco_class == ECOClass.PLACEMENT_LOCAL
        assert eco2.metadata.eco_class == ECOClass.PLACEMENT_LOCAL

        tracker.record_eco_result(eco1, success=True)
        tracker.record_eco_result(eco2, success=False)

        # Should have aggregated stats for PLACEMENT_LOCAL
        stats = tracker.class_stats[ECOClass.PLACEMENT_LOCAL]
        assert stats.total_applications == 2
        assert stats.failed_applications == 1
        assert stats.failure_rate == 0.5

    def test_is_eco_class_allowed(self):
        """Test checking if ECO class is allowed."""
        tracker = ECOClassTracker()

        # Unknown class is allowed
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL) is True

        # Record some failures but not enough to blacklist
        eco = NoOpECO()
        tracker.record_eco_result(eco, success=False)
        tracker.record_eco_result(eco, success=False)

        # Still allowed (only 2 applications)
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL) is True

        # Add one more failure to trigger blacklist
        tracker.record_eco_result(eco, success=False)

        # Now blacklisted
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL) is False

    def test_blacklisted_classes(self):
        """Test getting list of blacklisted classes."""
        tracker = ECOClassTracker()

        # Blacklist one class
        eco1 = NoOpECO()
        tracker.record_eco_result(eco1, success=False)
        tracker.record_eco_result(eco1, success=False)
        tracker.record_eco_result(eco1, success=False)

        # Another class with good success rate
        eco2 = BufferInsertionECO(max_capacitance=0.5)
        tracker.record_eco_result(eco2, success=True)
        tracker.record_eco_result(eco2, success=True)
        tracker.record_eco_result(eco2, success=True)

        blacklisted = tracker.get_blacklisted_classes()
        assert len(blacklisted) == 1
        assert ECOClass.TOPOLOGY_NEUTRAL in blacklisted
        assert ECOClass.PLACEMENT_LOCAL not in blacklisted

    def test_get_failure_rate(self):
        """Test getting failure rate for ECO class."""
        tracker = ECOClassTracker()

        # Unknown class has 0 failure rate
        assert tracker.get_failure_rate(ECOClass.GLOBAL_DISRUPTIVE) == 0.0

        # Record some results
        eco = PlacementDensityECO(target_density=0.6)
        tracker.record_eco_result(eco, success=False)
        tracker.record_eco_result(eco, success=False)
        tracker.record_eco_result(eco, success=True)

        # 2 failures out of 3 = 66.7%
        # PlacementDensityECO is ROUTING_AFFECTING, not PLACEMENT_LOCAL
        failure_rate = tracker.get_failure_rate(ECOClass.ROUTING_AFFECTING)
        assert abs(failure_rate - 0.6667) < 0.001


class TestECOClassContainmentIntegration:
    """Test ECO class containment integration with trials."""

    def test_systematic_failure_triggers_blacklist(self):
        """Test that systematic failures across a class trigger blacklisting."""
        tracker = ECOClassTracker()

        # Create 5 different buffer insertion ECOs (all PLACEMENT_LOCAL)
        ecos = [
            BufferInsertionECO(max_capacitance=0.2),
            BufferInsertionECO(max_capacitance=0.3),
            BufferInsertionECO(max_capacitance=0.4),
            BufferInsertionECO(max_capacitance=0.5),
            BufferInsertionECO(max_capacitance=0.6),
        ]

        # Simulate systematic failure (all fail)
        for eco in ecos[:3]:  # First 3 fail
            tracker.record_eco_result(eco, success=False)

        # Check that PLACEMENT_LOCAL is now blacklisted
        assert tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL) is False

        # Remaining ECOs of the same class should be skipped
        for eco in ecos[3:]:
            if not tracker.is_eco_class_allowed(eco.metadata.eco_class):
                # Skip this ECO
                pass
            else:
                # This shouldn't happen
                pytest.fail("Blacklisted ECO class was not skipped")

    def test_other_classes_remain_available(self):
        """Test that blacklisting one class doesn't affect others."""
        tracker = ECOClassTracker()

        # Blacklist PLACEMENT_LOCAL
        eco1 = BufferInsertionECO(max_capacitance=0.5)
        tracker.record_eco_result(eco1, success=False)
        tracker.record_eco_result(eco1, success=False)
        tracker.record_eco_result(eco1, success=False)

        assert tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL) is False

        # Other classes should still be allowed
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL) is True
        assert tracker.is_eco_class_allowed(ECOClass.ROUTING_AFFECTING) is True
        assert tracker.is_eco_class_allowed(ECOClass.GLOBAL_DISRUPTIVE) is True

    def test_future_trials_skip_blacklisted_class(self):
        """Test that future trials skip blacklisted ECO classes."""
        tracker = ECOClassTracker()

        # Initial trial: blacklist TOPOLOGY_NEUTRAL
        eco = NoOpECO()
        tracker.record_eco_result(eco, success=False)
        tracker.record_eco_result(eco, success=False)
        tracker.record_eco_result(eco, success=False)

        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL) is False

        # Simulate future trial preparation
        candidate_ecos = [
            NoOpECO(),  # TOPOLOGY_NEUTRAL - should be filtered
            BufferInsertionECO(max_capacitance=0.5),  # PLACEMENT_LOCAL - OK
            PlacementDensityECO(target_density=0.6),  # PLACEMENT_LOCAL - OK
        ]

        # Filter out blacklisted classes
        allowed_ecos = [
            eco
            for eco in candidate_ecos
            if tracker.is_eco_class_allowed(eco.metadata.eco_class)
        ]

        # Should have filtered out the NoOpECO
        assert len(allowed_ecos) == 2
        assert all(e.metadata.eco_class != ECOClass.TOPOLOGY_NEUTRAL for e in allowed_ecos)

    def test_partial_failure_does_not_blacklist(self):
        """Test that partial failures don't trigger blacklisting."""
        tracker = ECOClassTracker()

        # Mix of successes and failures (50% failure rate)
        eco1 = BufferInsertionECO(max_capacitance=0.2)
        eco2 = BufferInsertionECO(max_capacitance=0.3)
        eco3 = BufferInsertionECO(max_capacitance=0.4)
        eco4 = BufferInsertionECO(max_capacitance=0.5)

        tracker.record_eco_result(eco1, success=False)
        tracker.record_eco_result(eco2, success=True)
        tracker.record_eco_result(eco3, success=False)
        tracker.record_eco_result(eco4, success=True)

        # 50% failure rate shouldn't trigger blacklist (threshold is 70%)
        assert tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL) is True
        assert ECOClass.PLACEMENT_LOCAL not in tracker.get_blacklisted_classes()

    def test_recovery_not_supported(self):
        """Test that once blacklisted, class stays blacklisted.

        In the current design, blacklisting is permanent for the Study.
        Future enhancements could add recovery logic.
        """
        tracker = ECOClassTracker()

        # Blacklist the class
        eco = NoOpECO()
        tracker.record_eco_result(eco, success=False)
        tracker.record_eco_result(eco, success=False)
        tracker.record_eco_result(eco, success=False)

        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL) is False

        # Even if we record successes now, it stays blacklisted
        tracker.record_eco_result(eco, success=True)
        tracker.record_eco_result(eco, success=True)
        tracker.record_eco_result(eco, success=True)

        # Still blacklisted (permanent in current design)
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL) is False
