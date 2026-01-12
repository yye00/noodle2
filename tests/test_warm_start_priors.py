"""Tests for F262: Support warm-start prior loading from source studies with weighting."""

import json
from pathlib import Path

import pytest
from controller.eco import ECOEffectiveness, ECOPrior
from controller.prior_sharing import PriorExporter, PriorRepository
from controller.warm_start import (
    SourceStudyConfig,
    WarmStartConfig,
    WarmStartLoader,
)


class TestF262WarmStartPriorLoading:
    """Test warm-start prior loading from source studies with weighting."""

    def test_step_1_complete_study_with_eco_effectiveness_history(self, tmp_path):
        """Step 1: Complete study nangate45_fix_v1 with ECO effectiveness history."""
        # Simulate a completed study with ECO effectiveness data
        eco_effectiveness_map = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                failed_applications=5,
                average_wns_improvement_ps=250.0,
                best_wns_improvement_ps=500.0,
                worst_wns_degradation_ps=-50.0,
                prior=ECOPrior.TRUSTED,
            ),
            "cell_resizing": ECOEffectiveness(
                eco_name="cell_resizing",
                total_applications=30,
                successful_applications=25,
                failed_applications=5,
                average_wns_improvement_ps=150.0,
                best_wns_improvement_ps=300.0,
                worst_wns_degradation_ps=-20.0,
                prior=ECOPrior.MIXED,
            ),
        }

        # Export priors from the completed study
        output_path = tmp_path / "nangate45_fix_v1_priors.json"
        exporter = PriorExporter()
        repository = exporter.export_priors(
            study_id="nangate45_fix_v1",
            eco_effectiveness_map=eco_effectiveness_map,
            output_path=output_path,
            snapshot_hash="abc123def456",
            metadata={"study_type": "fix_extreme"},
        )

        # Verify repository was created
        assert output_path.exists()
        assert len(repository.eco_priors) == 2
        assert "buffer_insertion" in repository.eco_priors
        assert "cell_resizing" in repository.eco_priors

    def test_step_2_create_new_study_with_priors_mode_warm_start(self):
        """Step 2: Create new study with priors mode: warm_start."""
        # Create warm-start configuration
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
        )

        assert config.mode == "warm_start"
        assert isinstance(config.source_studies, list)

    def test_step_3_set_source_studies_with_weight(self, tmp_path):
        """Step 3: Set source_studies: [{name: nangate45_fix_v1, weight: 0.8}]."""
        # Create prior repository for source study
        prior_repo_path = tmp_path / "nangate45_fix_v1_priors.json"

        eco_effectiveness_map = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                average_wns_improvement_ps=250.0,
                prior=ECOPrior.TRUSTED,
            ),
        }

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="nangate45_fix_v1",
            eco_effectiveness_map=eco_effectiveness_map,
            output_path=prior_repo_path,
        )

        # Configure source study with weight
        source_study = SourceStudyConfig(
            name="nangate45_fix_v1",
            weight=0.8,
            prior_repository_path=prior_repo_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[source_study],
        )

        assert len(config.source_studies) == 1
        assert config.source_studies[0].name == "nangate45_fix_v1"
        assert config.source_studies[0].weight == 0.8
        assert config.source_studies[0].prior_repository_path == prior_repo_path

    def test_step_4_initialize_new_study(self, tmp_path):
        """Step 4: Initialize new study."""
        # Create prior repository
        prior_repo_path = tmp_path / "source_priors.json"

        eco_effectiveness_map = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                average_wns_improvement_ps=250.0,
                prior=ECOPrior.TRUSTED,
            ),
        }

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="source_study",
            eco_effectiveness_map=eco_effectiveness_map,
            output_path=prior_repo_path,
        )

        # Configure warm-start
        source_study = SourceStudyConfig(
            name="source_study",
            weight=1.0,
            prior_repository_path=prior_repo_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[source_study],
        )

        # Load priors
        loader = WarmStartLoader(config)
        loaded_priors = loader.load_priors(
            target_study_id="new_study",
            audit_trail_path=tmp_path / "audit_trail.json",
        )

        # Verify initialization succeeded
        assert isinstance(loaded_priors, dict)
        assert len(loaded_priors) > 0

    def test_step_5_verify_eco_priors_are_loaded_from_v1(self, tmp_path):
        """Step 5: Verify ECO priors are loaded from v1."""
        # Create prior repository with known data
        prior_repo_path = tmp_path / "nangate45_fix_v1_priors.json"

        eco_effectiveness_map = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                average_wns_improvement_ps=250.0,
                prior=ECOPrior.TRUSTED,
            ),
            "cell_resizing": ECOEffectiveness(
                eco_name="cell_resizing",
                total_applications=30,
                successful_applications=25,
                average_wns_improvement_ps=150.0,
                prior=ECOPrior.MIXED,
            ),
        }

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="nangate45_fix_v1",
            eco_effectiveness_map=eco_effectiveness_map,
            output_path=prior_repo_path,
        )

        # Configure warm-start
        source_study = SourceStudyConfig(
            name="nangate45_fix_v1",
            weight=1.0,
            prior_repository_path=prior_repo_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[source_study],
        )

        # Load priors
        loader = WarmStartLoader(config)
        loaded_priors = loader.load_priors(target_study_id="new_study")

        # Verify priors were loaded
        assert "buffer_insertion" in loaded_priors
        assert "cell_resizing" in loaded_priors

        # Verify data matches source
        assert loaded_priors["buffer_insertion"].eco_name == "buffer_insertion"
        assert loaded_priors["buffer_insertion"].total_applications == 50
        assert loaded_priors["buffer_insertion"].successful_applications == 45

    def test_step_6_verify_prior_confidence_is_scaled_by_weight_0_8(self, tmp_path):
        """Step 6: Verify prior confidence is scaled by weight 0.8."""
        # Create prior repository
        prior_repo_path = tmp_path / "source_priors.json"

        eco_effectiveness_map = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=100,
                successful_applications=90,
                average_wns_improvement_ps=250.0,
                prior=ECOPrior.TRUSTED,
            ),
        }

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="source_study",
            eco_effectiveness_map=eco_effectiveness_map,
            output_path=prior_repo_path,
        )

        # Configure warm-start with weight 0.8
        source_study = SourceStudyConfig(
            name="source_study",
            weight=0.8,
            prior_repository_path=prior_repo_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[source_study],
        )

        # Load priors with weighting
        loader = WarmStartLoader(config)
        loaded_priors = loader.load_priors(target_study_id="new_study")

        # Verify confidence is scaled by weight
        buffer_prior = loaded_priors["buffer_insertion"]

        # With weight 0.8, the total applications should be scaled
        # 100 * 0.8 = 80
        assert buffer_prior.total_applications == 80
        assert buffer_prior.successful_applications == 72  # 90 * 0.8

        # Average improvement should remain the same (it's a ratio)
        assert buffer_prior.average_wns_improvement_ps == 250.0

    def test_step_7_verify_warm_start_is_logged(self, tmp_path):
        """Step 7: Verify warm-start is logged."""
        # Create prior repository
        prior_repo_path = tmp_path / "source_priors.json"

        eco_effectiveness_map = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                average_wns_improvement_ps=250.0,
                prior=ECOPrior.TRUSTED,
            ),
        }

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="source_study",
            eco_effectiveness_map=eco_effectiveness_map,
            output_path=prior_repo_path,
        )

        # Configure warm-start
        source_study = SourceStudyConfig(
            name="source_study",
            weight=0.9,
            prior_repository_path=prior_repo_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[source_study],
        )

        # Load priors with audit trail
        audit_path = tmp_path / "warm_start_audit.json"
        loader = WarmStartLoader(config)
        loader.load_priors(
            target_study_id="new_study",
            audit_trail_path=audit_path,
        )

        # Verify audit trail was created
        assert audit_path.exists()

        # Load and verify audit trail content
        with open(audit_path) as f:
            audit = json.load(f)

        assert "import_timestamp" in audit
        assert audit["target_study_id"] == "new_study"
        assert audit["mode"] == "warm_start"
        assert len(audit["source_studies"]) == 1
        assert audit["source_studies"][0]["name"] == "source_study"
        assert audit["source_studies"][0]["weight"] == 0.9


class TestWarmStartConfigDetails:
    """Test warm-start configuration in detail."""

    def test_source_study_config_creation(self, tmp_path):
        """Test creating source study configuration."""
        prior_path = tmp_path / "priors.json"
        prior_path.write_text("{}")

        config = SourceStudyConfig(
            name="study_v1",
            weight=0.7,
            prior_repository_path=prior_path,
        )

        assert config.name == "study_v1"
        assert config.weight == 0.7
        assert config.prior_repository_path == prior_path

    def test_warm_start_config_with_multiple_sources(self, tmp_path):
        """Test warm-start config with multiple source studies."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="study_v1",
                    weight=0.6,
                    prior_repository_path=tmp_path / "v1.json",
                ),
                SourceStudyConfig(
                    name="study_v2",
                    weight=0.4,
                    prior_repository_path=tmp_path / "v2.json",
                ),
            ],
        )

        assert len(config.source_studies) == 2
        assert config.source_studies[0].weight == 0.6
        assert config.source_studies[1].weight == 0.4

    def test_weight_normalization(self):
        """Test weight normalization to sum to 1.0."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="s1", weight=0.6, prior_repository_path=Path("p1.json")),
                SourceStudyConfig(name="s2", weight=0.3, prior_repository_path=Path("p2.json")),
            ],
        )

        # Weights don't sum to 1.0, should be normalized
        normalized = config.normalize_weights()

        # 0.6 / 0.9 = 0.667
        # 0.3 / 0.9 = 0.333
        assert abs(normalized[0] - 0.667) < 0.01
        assert abs(normalized[1] - 0.333) < 0.01
        assert abs(sum(normalized) - 1.0) < 0.001


class TestWarmStartLoaderDetails:
    """Test warm-start loader implementation details."""

    def test_load_from_single_source(self, tmp_path):
        """Test loading priors from a single source."""
        # Create prior repository
        prior_repo_path = tmp_path / "source.json"

        eco_effectiveness_map = {
            "eco1": ECOEffectiveness(
                eco_name="eco1",
                total_applications=100,
                successful_applications=80,
                average_wns_improvement_ps=200.0,
                prior=ECOPrior.TRUSTED,
            ),
        }

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="source",
            eco_effectiveness_map=eco_effectiveness_map,
            output_path=prior_repo_path,
        )

        # Load with weight 1.0
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="source",
                    weight=1.0,
                    prior_repository_path=prior_repo_path,
                ),
            ],
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        assert "eco1" in loaded
        assert loaded["eco1"].total_applications == 100
        assert loaded["eco1"].successful_applications == 80

    def test_scale_effectiveness_by_weight(self):
        """Test scaling ECO effectiveness by weight."""
        effectiveness = ECOEffectiveness(
            eco_name="test_eco",
            total_applications=100,
            successful_applications=80,
            failed_applications=20,
            average_wns_improvement_ps=250.0,
            best_wns_improvement_ps=500.0,
            worst_wns_degradation_ps=-100.0,
            prior=ECOPrior.TRUSTED,
        )

        loader = WarmStartLoader(WarmStartConfig(mode="warm_start", source_studies=[]))
        scaled = loader._scale_effectiveness(effectiveness, weight=0.5)

        # Counts should be scaled
        assert scaled.total_applications == 50  # 100 * 0.5
        assert scaled.successful_applications == 40  # 80 * 0.5
        assert scaled.failed_applications == 10  # 20 * 0.5

        # Averages and extremes should remain the same
        assert scaled.average_wns_improvement_ps == 250.0
        assert scaled.best_wns_improvement_ps == 500.0
        assert scaled.worst_wns_degradation_ps == -100.0

    def test_merge_from_multiple_sources(self, tmp_path):
        """Test merging priors from multiple source studies."""
        # Create two prior repositories
        repo1_path = tmp_path / "source1.json"
        repo2_path = tmp_path / "source2.json"

        # Source 1 has eco1 and eco2
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="source1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=200.0,
                    prior=ECOPrior.TRUSTED,
                ),
                "eco2": ECOEffectiveness(
                    eco_name="eco2",
                    total_applications=50,
                    successful_applications=40,
                    average_wns_improvement_ps=100.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=repo1_path,
        )

        # Source 2 has eco1 and eco3
        exporter.export_priors(
            study_id="source2",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=50,
                    successful_applications=40,
                    average_wns_improvement_ps=150.0,
                    prior=ECOPrior.TRUSTED,
                ),
                "eco3": ECOEffectiveness(
                    eco_name="eco3",
                    total_applications=30,
                    successful_applications=20,
                    average_wns_improvement_ps=80.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=repo2_path,
        )

        # Configure warm-start with both sources
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="source1", weight=0.6, prior_repository_path=repo1_path),
                SourceStudyConfig(name="source2", weight=0.4, prior_repository_path=repo2_path),
            ],
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Should have all three ECOs
        assert "eco1" in loaded
        assert "eco2" in loaded
        assert "eco3" in loaded

        # eco1 should be merged from both sources
        # eco2 should come from source1 only
        # eco3 should come from source2 only


class TestWarmStartEdgeCases:
    """Test edge cases for warm-start loading."""

    def test_load_with_zero_weight(self, tmp_path):
        """Test loading with zero weight."""
        prior_repo_path = tmp_path / "source.json"

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="source",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=80,
                    average_wns_improvement_ps=200.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_repo_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="source", weight=0.0, prior_repository_path=prior_repo_path),
            ],
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # With zero weight, should still load but with zero applications
        assert "eco1" in loaded
        assert loaded["eco1"].total_applications == 0

    def test_load_with_missing_repository(self, tmp_path):
        """Test loading when repository file doesn't exist."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="missing",
                    weight=1.0,
                    prior_repository_path=tmp_path / "missing.json",
                ),
            ],
        )

        loader = WarmStartLoader(config)

        with pytest.raises(FileNotFoundError):
            loader.load_priors(target_study_id="target")

    def test_empty_source_studies(self):
        """Test warm-start with no source studies."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Should return empty dict
        assert loaded == {}
