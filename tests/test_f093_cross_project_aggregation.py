"""Tests for F093: Prior repository supports cross-project aggregation with decay."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from controller.eco import ECOEffectiveness, ECOPrior
from controller.prior_repository_sqlite import SQLitePriorRepository
from controller.prior_sharing import PriorProvenance


class TestF093ImportMultipleProjectsWithWeights:
    """Test Step 1: Import priors from multiple projects with different weights."""

    def test_step_1_import_multiple_projects_with_weights(self, tmp_path: Path):
        """Step 1: Import priors from multiple projects with different weights."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Import from project 1 with weight 1.0
        eco1 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=10,
            successful_applications=8,
            failed_applications=2,
            average_wns_improvement_ps=100.0,
            best_wns_improvement_ps=200.0,
            worst_wns_degradation_ps=-50.0,
            prior=ECOPrior.TRUSTED,
        )
        prov1 = PriorProvenance(
            source_study_id="project1",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco1, prov1, weight=1.0)

        # Import from project 2 with weight 0.5
        eco2 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=20,
            successful_applications=10,
            failed_applications=10,
            average_wns_improvement_ps=50.0,
            best_wns_improvement_ps=150.0,
            worst_wns_degradation_ps=-100.0,
            prior=ECOPrior.MIXED,
        )
        prov2 = PriorProvenance(
            source_study_id="project2",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco2, prov2, weight=0.5)

        # Verify both priors are stored with weights
        priors = repo.get_all_priors_with_weights("resize_buffer")
        assert len(priors) == 2
        assert any(p["provenance"]["source_study_id"] == "project1" and p["weight"] == 1.0 for p in priors)
        assert any(p["provenance"]["source_study_id"] == "project2" and p["weight"] == 0.5 for p in priors)


class TestF093ConfigureDecayByAge:
    """Test Step 2: Configure decay_by_age with 30-day half-life."""

    def test_step_2_configure_decay_by_age(self, tmp_path: Path):
        """Step 2: Configure decay_by_age with 30-day half-life."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Configure decay with 30-day half-life
        repo.configure_decay(half_life_days=30)

        # Verify configuration is stored
        assert repo.get_decay_config() == {"half_life_days": 30}

    def test_decay_config_defaults_to_none(self, tmp_path: Path):
        """Verify decay configuration defaults to None (no decay)."""
        repo = SQLitePriorRepository(tmp_path / "test.db")
        assert repo.get_decay_config() is None


class TestF093QueryAggregatedPrior:
    """Test Step 3: Query aggregated prior for an ECO."""

    def test_step_3_query_aggregated_prior(self, tmp_path: Path):
        """Step 3: Query aggregated prior for an ECO."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Add two priors for the same ECO
        eco1 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=10,
            successful_applications=8,
            failed_applications=2,
            average_wns_improvement_ps=100.0,
            best_wns_improvement_ps=200.0,
            worst_wns_degradation_ps=-50.0,
            prior=ECOPrior.TRUSTED,
        )
        prov1 = PriorProvenance(
            source_study_id="project1",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco1, prov1, weight=1.0)

        eco2 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=20,
            successful_applications=10,
            failed_applications=10,
            average_wns_improvement_ps=50.0,
            best_wns_improvement_ps=150.0,
            worst_wns_degradation_ps=-100.0,
            prior=ECOPrior.MIXED,
        )
        prov2 = PriorProvenance(
            source_study_id="project2",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco2, prov2, weight=0.5)

        # Query aggregated prior
        aggregated = repo.get_aggregated_prior("resize_buffer")

        # Should return an ECOEffectiveness with weighted averages
        assert aggregated is not None
        assert aggregated.eco_name == "resize_buffer"
        assert aggregated.total_applications == 30  # 10 + 20
        assert aggregated.successful_applications == 18  # 8 + 10


class TestF093WeightedAverageComputation:
    """Test Step 4: Verify weighted_average is computed correctly."""

    def test_step_4_weighted_average_computation(self, tmp_path: Path):
        """Step 4: Verify weighted_average is computed correctly."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Project 1: 100ps improvement, weight 1.0
        eco1 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=10,
            successful_applications=8,
            failed_applications=2,
            average_wns_improvement_ps=100.0,
            best_wns_improvement_ps=200.0,
            worst_wns_degradation_ps=-50.0,
            prior=ECOPrior.TRUSTED,
        )
        prov1 = PriorProvenance(
            source_study_id="project1",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco1, prov1, weight=1.0)

        # Project 2: 50ps improvement, weight 0.5
        eco2 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=20,
            successful_applications=10,
            failed_applications=10,
            average_wns_improvement_ps=50.0,
            best_wns_improvement_ps=150.0,
            worst_wns_degradation_ps=-100.0,
            prior=ECOPrior.MIXED,
        )
        prov2 = PriorProvenance(
            source_study_id="project2",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco2, prov2, weight=0.5)

        # Query aggregated prior
        aggregated = repo.get_aggregated_prior("resize_buffer")

        # Weighted average = (100 * 1.0 + 50 * 0.5) / (1.0 + 0.5) = 150 / 1.5 = 83.33
        assert aggregated is not None
        assert abs(aggregated.average_wns_improvement_ps - 83.33) < 0.01


class TestF093OlderPriorsReducedWeight:
    """Test Step 5: Verify older priors have reduced weight due to decay."""

    def test_step_5_older_priors_reduced_weight(self, tmp_path: Path):
        """Step 5: Verify older priors have reduced weight due to decay."""
        repo = SQLitePriorRepository(tmp_path / "test.db")
        repo.configure_decay(half_life_days=30)

        # Recent prior (today)
        eco1 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=10,
            successful_applications=8,
            failed_applications=2,
            average_wns_improvement_ps=100.0,
            best_wns_improvement_ps=200.0,
            worst_wns_degradation_ps=-50.0,
            prior=ECOPrior.TRUSTED,
        )
        prov1 = PriorProvenance(
            source_study_id="recent_project",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco1, prov1, weight=1.0)

        # Old prior (60 days ago - 2 half-lives)
        old_timestamp = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        eco2 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=10,
            successful_applications=8,
            failed_applications=2,
            average_wns_improvement_ps=100.0,
            best_wns_improvement_ps=200.0,
            worst_wns_degradation_ps=-50.0,
            prior=ECOPrior.TRUSTED,
        )
        prov2 = PriorProvenance(
            source_study_id="old_project",
            export_timestamp=old_timestamp,
        )
        repo.import_prior_with_weight(eco2, prov2, weight=1.0)

        # Get priors with decay applied
        priors = repo.get_all_priors_with_decay("resize_buffer")

        # Find the old and recent priors
        recent = next(p for p in priors if p["provenance"]["source_study_id"] == "recent_project")
        old = next(p for p in priors if p["provenance"]["source_study_id"] == "old_project")

        # Recent prior should have full weight (1.0)
        assert abs(recent["effective_weight"] - 1.0) < 0.01

        # Old prior should have reduced weight (0.25 = 0.5^2 for 2 half-lives)
        assert abs(old["effective_weight"] - 0.25) < 0.01

    def test_decay_affects_aggregation(self, tmp_path: Path):
        """Verify that decay is applied when computing aggregated priors."""
        repo = SQLitePriorRepository(tmp_path / "test.db")
        repo.configure_decay(half_life_days=30)

        # Recent prior: 200ps improvement
        eco1 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=10,
            successful_applications=8,
            failed_applications=2,
            average_wns_improvement_ps=200.0,
            best_wns_improvement_ps=300.0,
            worst_wns_degradation_ps=-50.0,
            prior=ECOPrior.TRUSTED,
        )
        prov1 = PriorProvenance(
            source_study_id="recent_project",
            export_timestamp=datetime.now(UTC).isoformat(),
        )
        repo.import_prior_with_weight(eco1, prov1, weight=1.0)

        # Old prior (60 days): 100ps improvement
        old_timestamp = (datetime.now(UTC) - timedelta(days=60)).isoformat()
        eco2 = ECOEffectiveness(
            eco_name="resize_buffer",
            total_applications=10,
            successful_applications=8,
            failed_applications=2,
            average_wns_improvement_ps=100.0,
            best_wns_improvement_ps=150.0,
            worst_wns_degradation_ps=-100.0,
            prior=ECOPrior.MIXED,
        )
        prov2 = PriorProvenance(
            source_study_id="old_project",
            export_timestamp=old_timestamp,
        )
        repo.import_prior_with_weight(eco2, prov2, weight=1.0)

        # Get aggregated prior with decay
        aggregated = repo.get_aggregated_prior("resize_buffer")

        # With decay: recent gets weight 1.0, old gets weight 0.25
        # Weighted average = (200 * 1.0 + 100 * 0.25) / (1.0 + 0.25) = 225 / 1.25 = 180
        assert aggregated is not None
        assert abs(aggregated.average_wns_improvement_ps - 180.0) < 0.01
