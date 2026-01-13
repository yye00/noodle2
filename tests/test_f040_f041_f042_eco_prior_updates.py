"""Tests for F040-F042: ECO prior state transitions.

F040: ECO priors update to TRUSTED after consistent improvements
F041: ECO priors update to SUSPICIOUS after failures
F042: ECO priors update to MIXED after variable results
"""

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior


class TestF040TrustedPriorUpdates:
    """Test F040: ECO priors update to TRUSTED after consistent improvements."""

    def test_consistent_improvements_become_trusted(self):
        """Test that consistent improvements change prior to TRUSTED."""
        eco = ECOEffectiveness(eco_name="buffer_insertion")

        # Add 5 successful applications with positive WNS improvements
        for i in range(5):
            eco.update(success=True, wns_delta_ps=100.0)

        # Success rate: 100%, Average improvement: 100ps
        # Should be classified as TRUSTED
        assert eco.prior == ECOPrior.TRUSTED

    def test_high_success_rate_with_improvements_is_trusted(self):
        """Test that >= 80% success rate with positive improvements is TRUSTED."""
        eco = ECOEffectiveness(eco_name="gate_resize")

        # 4 successes, 1 failure = 80% success rate
        eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=True, wns_delta_ps=150.0)
        eco.update(success=True, wns_delta_ps=200.0)
        eco.update(success=True, wns_delta_ps=120.0)
        eco.update(success=False, wns_delta_ps=-50.0)

        # Success rate: 80%, Average improvement > 0
        assert eco.success_rate == 0.8
        assert eco.average_wns_improvement_ps > 0
        assert eco.prior == ECOPrior.TRUSTED

    def test_trusted_requires_both_success_and_improvement(self):
        """Test that TRUSTED requires both high success rate AND positive improvement."""
        eco = ECOEffectiveness(eco_name="test_eco")

        # High success rate but no actual improvement
        for i in range(5):
            eco.update(success=True, wns_delta_ps=-10.0)  # Negative delta

        # Success rate is 100% but average improvement is negative
        # Should NOT be TRUSTED
        assert eco.prior != ECOPrior.TRUSTED


class TestF041SuspiciousPriorUpdates:
    """Test F041: ECO priors update to SUSPICIOUS after failures."""

    def test_frequent_failures_become_suspicious(self):
        """Test that frequent failures change prior to SUSPICIOUS."""
        eco = ECOEffectiveness(eco_name="problematic_eco")

        # Add 5 failed applications
        for i in range(5):
            eco.update(success=False, wns_delta_ps=-500.0)

        # Success rate: 0% (< 30%)
        # Should be classified as SUSPICIOUS
        assert eco.prior == ECOPrior.SUSPICIOUS

    def test_low_success_rate_is_suspicious(self):
        """Test that success rate < 30% is SUSPICIOUS."""
        eco = ECOEffectiveness(eco_name="failing_eco")

        # 1 success, 4 failures = 20% success rate
        eco.update(success=True, wns_delta_ps=50.0)
        eco.update(success=False, wns_delta_ps=-100.0)
        eco.update(success=False, wns_delta_ps=-150.0)
        eco.update(success=False, wns_delta_ps=-200.0)
        eco.update(success=False, wns_delta_ps=-100.0)

        # Success rate: 20% (< 30%)
        assert eco.success_rate < 0.3
        assert eco.prior == ECOPrior.SUSPICIOUS

    def test_consistently_degrades_timing_is_suspicious(self):
        """Test that consistent timing degradation (< -1000ps avg) with low success is SUSPICIOUS."""
        eco = ECOEffectiveness(eco_name="timing_killer")

        # Low success rate with terrible timing impact
        eco.update(success=True, wns_delta_ps=-1500.0)
        eco.update(success=False, wns_delta_ps=-2000.0)
        eco.update(success=False, wns_delta_ps=-1800.0)
        eco.update(success=False, wns_delta_ps=-1000.0)
        eco.update(success=False, wns_delta_ps=-1200.0)

        # Low success rate (20%) and average degradation < -1000ps
        assert eco.success_rate < 0.3
        assert eco.average_wns_improvement_ps < -1000
        assert eco.prior == ECOPrior.SUSPICIOUS


class TestF042MixedPriorUpdates:
    """Test F042: ECO priors update to MIXED after variable results."""

    def test_variable_results_become_mixed(self):
        """Test that variable results change prior to MIXED."""
        eco = ECOEffectiveness(eco_name="variable_eco")

        # Mix of successes and failures
        eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=False, wns_delta_ps=-50.0)
        eco.update(success=True, wns_delta_ps=150.0)
        eco.update(success=True, wns_delta_ps=80.0)
        eco.update(success=False, wns_delta_ps=-30.0)

        # Success rate: 60% (between 30% and 80%)
        assert 0.5 <= eco.success_rate < 0.8
        assert eco.prior == ECOPrior.MIXED

    def test_moderate_success_rate_is_mixed(self):
        """Test that success rate >= 50% but < 80% is MIXED."""
        eco = ECOEffectiveness(eco_name="moderate_eco")

        # 3 successes, 2 failures = 60% success rate
        eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=True, wns_delta_ps=120.0)
        eco.update(success=False, wns_delta_ps=-80.0)
        eco.update(success=True, wns_delta_ps=90.0)
        eco.update(success=False, wns_delta_ps=-50.0)

        # Success rate: 60%
        assert eco.success_rate == 0.6
        assert eco.prior == ECOPrior.MIXED

    def test_mixed_is_between_trusted_and_suspicious(self):
        """Test that MIXED represents middle ground between TRUSTED and SUSPICIOUS."""
        # MIXED ECO: 50% success rate
        mixed_eco = ECOEffectiveness(eco_name="mixed")
        for i in range(5):
            mixed_eco.update(success=(i % 2 == 0), wns_delta_ps=50.0 if i % 2 == 0 else -50.0)

        # TRUSTED ECO: 80% success rate
        trusted_eco = ECOEffectiveness(eco_name="trusted")
        for i in range(5):
            trusted_eco.update(success=True, wns_delta_ps=100.0)

        # SUSPICIOUS ECO: 20% success rate
        suspicious_eco = ECOEffectiveness(eco_name="suspicious")
        for i in range(5):
            suspicious_eco.update(success=(i == 0), wns_delta_ps=-100.0)

        assert mixed_eco.prior == ECOPrior.MIXED
        assert trusted_eco.prior == ECOPrior.TRUSTED
        assert suspicious_eco.prior == ECOPrior.SUSPICIOUS


class TestPriorStateTransitions:
    """Test prior state transitions through lifecycle."""

    def test_transition_from_unknown_to_trusted(self):
        """Test transition: UNKNOWN -> TRUSTED."""
        eco = ECOEffectiveness(eco_name="improving_eco")

        # Starts as UNKNOWN
        assert eco.prior == ECOPrior.UNKNOWN

        # Add successful applications
        for i in range(5):
            eco.update(success=True, wns_delta_ps=100.0)

        # Should transition to TRUSTED
        assert eco.prior == ECOPrior.TRUSTED

    def test_transition_from_unknown_to_suspicious(self):
        """Test transition: UNKNOWN -> SUSPICIOUS."""
        eco = ECOEffectiveness(eco_name="failing_eco")

        # Starts as UNKNOWN
        assert eco.prior == ECOPrior.UNKNOWN

        # Add failed applications
        for i in range(5):
            eco.update(success=False, wns_delta_ps=-200.0)

        # Should transition to SUSPICIOUS
        assert eco.prior == ECOPrior.SUSPICIOUS

    def test_transition_from_unknown_to_mixed(self):
        """Test transition: UNKNOWN -> MIXED."""
        eco = ECOEffectiveness(eco_name="variable_eco")

        # Starts as UNKNOWN
        assert eco.prior == ECOPrior.UNKNOWN

        # Add mixed results
        eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=True, wns_delta_ps=120.0)
        eco.update(success=False, wns_delta_ps=-50.0)
        eco.update(success=True, wns_delta_ps=80.0)

        # Should transition to MIXED
        assert eco.prior == ECOPrior.MIXED

    def test_prior_updates_dynamically(self):
        """Test that prior updates dynamically as evidence accumulates."""
        eco = ECOEffectiveness(eco_name="dynamic_eco")

        # Start: UNKNOWN (< 3 applications)
        eco.update(success=True, wns_delta_ps=100.0)
        assert eco.prior == ECOPrior.UNKNOWN

        eco.update(success=True, wns_delta_ps=100.0)
        assert eco.prior == ECOPrior.UNKNOWN

        # After 3rd application: Becomes TRUSTED (100% success, positive improvement)
        eco.update(success=True, wns_delta_ps=100.0)
        assert eco.prior == ECOPrior.TRUSTED

        # Add failures: Should transition to MIXED
        eco.update(success=False, wns_delta_ps=-50.0)
        eco.update(success=False, wns_delta_ps=-80.0)
        # Now: 3 success, 2 failures = 60% success rate
        assert eco.prior == ECOPrior.MIXED


class TestFeatureStepValidation:
    """Validate all steps from features F040, F041, F042."""

    # F040 Step Validation
    def test_f040_step1_eco_has_consistent_improvements(self):
        """F040 Step 1: Run ECO multiple times with consistent improvements."""
        eco = ECOEffectiveness(eco_name="consistent_eco")

        # Run 5 times with consistent improvements
        for i in range(5):
            eco.update(success=True, wns_delta_ps=100.0 + i * 10)

        # All successful with positive improvements
        assert eco.total_applications == 5
        assert eco.successful_applications == 5
        assert eco.average_wns_improvement_ps > 0

    def test_f040_step2_verify_prior_updates_to_trusted(self):
        """F040 Step 2: Verify prior updates to 'trusted'."""
        eco = ECOEffectiveness(eco_name="trusted_eco")

        # Consistent successes
        for i in range(5):
            eco.update(success=True, wns_delta_ps=150.0)

        # Should be TRUSTED
        assert eco.prior == ECOPrior.TRUSTED
        assert eco.prior.value == "trusted"

    def test_f040_step3_verify_success_rate_threshold(self):
        """F040 Step 3: Verify success rate >= 80% for TRUSTED."""
        eco = ECOEffectiveness(eco_name="test_eco")

        # 4 successes, 1 failure = exactly 80%
        for i in range(4):
            eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=False, wns_delta_ps=-50.0)

        assert eco.success_rate == 0.8
        assert eco.average_wns_improvement_ps > 0
        assert eco.prior == ECOPrior.TRUSTED

    # F041 Step Validation
    def test_f041_step1_eco_fails_frequently(self):
        """F041 Step 1: Run ECO that fails frequently."""
        eco = ECOEffectiveness(eco_name="failing_eco")

        # 5 failures
        for i in range(5):
            eco.update(success=False, wns_delta_ps=-200.0)

        assert eco.failed_applications == 5
        assert eco.success_rate == 0.0

    def test_f041_step2_verify_prior_updates_to_suspicious(self):
        """F041 Step 2: Verify prior updates to 'suspicious'."""
        eco = ECOEffectiveness(eco_name="suspicious_eco")

        # Frequent failures
        for i in range(5):
            eco.update(success=False, wns_delta_ps=-150.0)

        assert eco.prior == ECOPrior.SUSPICIOUS
        assert eco.prior.value == "suspicious"

    def test_f041_step3_verify_failure_rate_threshold(self):
        """F041 Step 3: Verify success rate < 30% for SUSPICIOUS."""
        eco = ECOEffectiveness(eco_name="test_eco")

        # 1 success, 4 failures = 20% success rate
        eco.update(success=True, wns_delta_ps=50.0)
        for i in range(4):
            eco.update(success=False, wns_delta_ps=-200.0)

        assert eco.success_rate < 0.3
        assert eco.prior == ECOPrior.SUSPICIOUS

    # F042 Step Validation
    def test_f042_step1_eco_has_variable_results(self):
        """F042 Step 1: Run ECO with variable results."""
        eco = ECOEffectiveness(eco_name="variable_eco")

        # Mix of successes and failures
        eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=False, wns_delta_ps=-50.0)
        eco.update(success=True, wns_delta_ps=120.0)
        eco.update(success=False, wns_delta_ps=-30.0)
        eco.update(success=True, wns_delta_ps=80.0)

        # Variable results
        assert eco.successful_applications > 0
        assert eco.failed_applications > 0

    def test_f042_step2_verify_prior_updates_to_mixed(self):
        """F042 Step 2: Verify prior updates to 'mixed'."""
        eco = ECOEffectiveness(eco_name="mixed_eco")

        # Variable results: 3 successes, 2 failures
        eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=True, wns_delta_ps=120.0)
        eco.update(success=False, wns_delta_ps=-50.0)
        eco.update(success=True, wns_delta_ps=90.0)
        eco.update(success=False, wns_delta_ps=-30.0)

        assert eco.prior == ECOPrior.MIXED
        assert eco.prior.value == "mixed"

    def test_f042_step3_verify_moderate_success_rate(self):
        """F042 Step 3: Verify success rate between 30% and 80% for MIXED."""
        eco = ECOEffectiveness(eco_name="test_eco")

        # 3 successes, 2 failures = 60% success rate
        for i in range(3):
            eco.update(success=True, wns_delta_ps=100.0)
        for i in range(2):
            eco.update(success=False, wns_delta_ps=-50.0)

        assert 0.3 <= eco.success_rate < 0.8
        assert eco.prior == ECOPrior.MIXED


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_80_percent_success_with_improvement_is_trusted(self):
        """Test boundary: exactly 80% success rate with improvement."""
        eco = ECOEffectiveness(eco_name="boundary_eco")

        # 4 successes, 1 failure = 80%
        for i in range(4):
            eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=False, wns_delta_ps=-50.0)

        assert eco.success_rate == 0.8
        assert eco.average_wns_improvement_ps > 0
        assert eco.prior == ECOPrior.TRUSTED

    def test_exactly_30_percent_success_boundary(self):
        """Test boundary: success rate near 30% threshold."""
        eco = ECOEffectiveness(eco_name="boundary_eco")

        # 3 successes, 7 failures = 30%
        for i in range(3):
            eco.update(success=True, wns_delta_ps=50.0)
        for i in range(7):
            eco.update(success=False, wns_delta_ps=-100.0)

        # At 30%, should not be SUSPICIOUS (need < 30%)
        assert eco.success_rate == 0.3
        # Should be MIXED
        assert eco.prior == ECOPrior.MIXED

    def test_high_success_but_negative_average_not_trusted(self):
        """Test that high success rate alone isn't enough for TRUSTED."""
        eco = ECOEffectiveness(eco_name="high_success_no_improvement")

        # 90% success rate but negative average improvement
        for i in range(9):
            eco.update(success=True, wns_delta_ps=-50.0)  # Successful but hurts timing
        eco.update(success=False, wns_delta_ps=-100.0)

        assert eco.success_rate == 0.9  # High success rate
        assert eco.average_wns_improvement_ps < 0  # But negative improvement
        assert eco.prior != ECOPrior.TRUSTED  # Should NOT be trusted
