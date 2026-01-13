"""Tests for F039: ECO priors track unknown state by default."""

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior


class TestECOPriorUnknownState:
    """Test that ECO priors default to UNKNOWN state."""

    def test_new_eco_has_unknown_prior(self):
        """Test that newly created ECO effectiveness has UNKNOWN prior."""
        eco = ECOEffectiveness(eco_name="buffer_insertion")

        assert eco.prior == ECOPrior.UNKNOWN

    def test_eco_prior_enum_has_unknown_value(self):
        """Test that ECOPrior enum has UNKNOWN state."""
        assert hasattr(ECOPrior, "UNKNOWN")
        assert ECOPrior.UNKNOWN.value == "unknown"

    def test_zero_applications_remains_unknown(self):
        """Test that ECO with zero applications stays UNKNOWN."""
        eco = ECOEffectiveness(eco_name="gate_resize")

        # No applications yet
        assert eco.total_applications == 0
        assert eco.prior == ECOPrior.UNKNOWN

    def test_eco_with_default_stats_is_unknown(self):
        """Test that ECO with default statistics has UNKNOWN prior."""
        eco = ECOEffectiveness(eco_name="pin_swap")

        # Verify all stats are at defaults
        assert eco.total_applications == 0
        assert eco.successful_applications == 0
        assert eco.failed_applications == 0
        assert eco.average_wns_improvement_ps == 0.0
        assert eco.best_wns_improvement_ps == 0.0
        assert eco.worst_wns_degradation_ps == 0.0

        # Prior should be UNKNOWN
        assert eco.prior == ECOPrior.UNKNOWN


class TestECOPriorNoHistoricalData:
    """Test ECO priors when no historical effectiveness data exists."""

    def test_no_historical_effectiveness_data(self):
        """Test that new ECO has no historical effectiveness data."""
        eco = ECOEffectiveness(eco_name="new_eco")

        # Verify no history exists
        assert eco.total_applications == 0
        assert eco.successful_applications == 0
        assert eco.failed_applications == 0

    def test_serialized_eco_shows_unknown_prior(self):
        """Test that serialized ECO shows UNKNOWN prior."""
        eco = ECOEffectiveness(eco_name="untested_eco")

        data = eco.to_dict()

        assert data["prior"] == "unknown"
        assert data["total_applications"] == 0


class TestFeatureStepValidation:
    """Validate all steps from feature F039."""

    def test_step1_create_new_study_with_eco_never_run(self):
        """Step 1: Create new study with ECO that has never been run."""
        # Create a new ECO that has never been executed before
        eco = ECOEffectiveness(eco_name="novel_eco_never_used")

        # This ECO has no prior execution history
        assert eco.total_applications == 0

    def test_step2_check_eco_prior_state(self):
        """Step 2: Check ECO prior state."""
        eco = ECOEffectiveness(eco_name="untested_eco")

        # Check the prior state
        prior_state = eco.prior

        assert prior_state is not None
        assert isinstance(prior_state, ECOPrior)

    def test_step3_verify_state_is_unknown(self):
        """Step 3: Verify state is 'unknown'."""
        eco = ECOEffectiveness(eco_name="new_eco")

        # Verify the prior state is exactly UNKNOWN
        assert eco.prior == ECOPrior.UNKNOWN
        assert eco.prior.value == "unknown"

    def test_step4_verify_no_historical_effectiveness_data_exists(self):
        """Step 4: Verify no historical effectiveness data exists."""
        eco = ECOEffectiveness(eco_name="fresh_eco")

        # Verify no effectiveness data
        assert eco.total_applications == 0
        assert eco.successful_applications == 0
        assert eco.failed_applications == 0
        assert eco.average_wns_improvement_ps == 0.0
        assert eco.best_wns_improvement_ps == 0.0
        assert eco.worst_wns_degradation_ps == 0.0

        # Success rate should also be 0
        assert eco.success_rate == 0.0


class TestECOPriorWithFewApplications:
    """Test ECO prior behavior with few applications (< 3)."""

    def test_one_application_remains_unknown(self):
        """Test that ECO with 1 application stays UNKNOWN."""
        eco = ECOEffectiveness(eco_name="test_eco")

        # Add one application
        eco.update(success=True, wns_delta_ps=100.0)

        # Should still be UNKNOWN (not enough evidence)
        assert eco.prior == ECOPrior.UNKNOWN

    def test_two_applications_remains_unknown(self):
        """Test that ECO with 2 applications stays UNKNOWN."""
        eco = ECOEffectiveness(eco_name="test_eco")

        # Add two applications
        eco.update(success=True, wns_delta_ps=100.0)
        eco.update(success=True, wns_delta_ps=150.0)

        # Should still be UNKNOWN (not enough evidence)
        assert eco.prior == ECOPrior.UNKNOWN

    def test_less_than_three_applications_is_unknown(self):
        """Test that ECO with < 3 applications stays UNKNOWN.

        This implements the threshold: need at least 3 applications
        before prior can change from UNKNOWN.
        """
        eco = ECOEffectiveness(eco_name="test_eco")

        # Verify starts as UNKNOWN
        assert eco.prior == ECOPrior.UNKNOWN

        # Add 2 applications (any combination of success/failure)
        eco.update(success=True, wns_delta_ps=50.0)
        eco.update(success=False, wns_delta_ps=-100.0)

        # Should remain UNKNOWN
        assert eco.total_applications == 2
        assert eco.prior == ECOPrior.UNKNOWN


class TestMultipleECOs:
    """Test that multiple ECOs all start with UNKNOWN prior."""

    def test_multiple_ecos_all_start_unknown(self):
        """Test that all new ECOs start with UNKNOWN prior."""
        ecos = [
            ECOEffectiveness(eco_name="buffer_insertion"),
            ECOEffectiveness(eco_name="gate_resize"),
            ECOEffectiveness(eco_name="pin_swap"),
            ECOEffectiveness(eco_name="logic_optimization"),
            ECOEffectiveness(eco_name="clock_tree_synthesis"),
        ]

        for eco in ecos:
            assert eco.prior == ECOPrior.UNKNOWN
            assert eco.total_applications == 0

    def test_eco_dictionary_all_unknown(self):
        """Test that a dictionary of ECOs all have UNKNOWN prior."""
        eco_dict = {
            "eco1": ECOEffectiveness(eco_name="eco1"),
            "eco2": ECOEffectiveness(eco_name="eco2"),
            "eco3": ECOEffectiveness(eco_name="eco3"),
        }

        for eco_name, effectiveness in eco_dict.items():
            assert effectiveness.prior == ECOPrior.UNKNOWN


class TestECOPriorEnumValues:
    """Test ECOPrior enum values for completeness."""

    def test_eco_prior_enum_has_all_states(self):
        """Test that ECOPrior enum has all expected states."""
        # Verify all expected states exist
        assert hasattr(ECOPrior, "UNKNOWN")
        assert hasattr(ECOPrior, "TRUSTED")
        assert hasattr(ECOPrior, "MIXED")
        assert hasattr(ECOPrior, "SUSPICIOUS")
        assert hasattr(ECOPrior, "BLACKLISTED")

    def test_eco_prior_unknown_is_default(self):
        """Test that UNKNOWN is the default prior state."""
        eco = ECOEffectiveness(eco_name="test")

        # Default should be UNKNOWN, not TRUSTED or any other state
        assert eco.prior == ECOPrior.UNKNOWN
        assert eco.prior != ECOPrior.TRUSTED
        assert eco.prior != ECOPrior.MIXED
        assert eco.prior != ECOPrior.SUSPICIOUS
        assert eco.prior != ECOPrior.BLACKLISTED
