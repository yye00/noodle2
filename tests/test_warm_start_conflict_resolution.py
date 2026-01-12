"""Tests for F263: Warm-start supports multiple source studies with conflict resolution."""

from pathlib import Path

import pytest
from controller.eco import ECOEffectiveness, ECOPrior
from controller.prior_sharing import PriorExporter
from controller.warm_start import SourceStudyConfig, WarmStartConfig, WarmStartLoader


class TestF263WarmStartConflictResolution:
    """Test warm-start with multiple sources and conflict resolution strategies."""

    def test_step_1_create_study_with_two_source_studies(self, tmp_path):
        """Step 1: Create study with two source studies: v1 (weight 0.8) and v2 (weight 0.5)."""
        # Create two prior repositories
        v1_path = tmp_path / "v1_priors.json"
        v2_path = tmp_path / "v2_priors.json"

        exporter = PriorExporter()

        # v1 with weight 0.8
        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=v1_path,
        )

        # v2 with weight 0.5
        exporter.export_priors(
            study_id="v2",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=50,
                    successful_applications=30,
                    average_wns_improvement_ps=150.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=v2_path,
        )

        # Create config with both sources
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="v1", weight=0.8, prior_repository_path=v1_path),
                SourceStudyConfig(name="v2", weight=0.5, prior_repository_path=v2_path),
            ],
        )

        assert len(config.source_studies) == 2
        assert config.source_studies[0].weight == 0.8
        assert config.source_studies[1].weight == 0.5

    def test_step_2_configure_conflict_resolution_highest_weight(self):
        """Step 2: Configure conflict_resolution: highest_weight."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
            merge_strategy="highest_weight",
        )

        assert config.merge_strategy == "highest_weight"

    def test_step_3_initialize_study_with_conflicting_priors(self, tmp_path):
        """Step 3: Initialize study where v1 and v2 have conflicting priors for same ECO."""
        # Create two repositories with conflicting data for the same ECO
        v1_path = tmp_path / "v1_priors.json"
        v2_path = tmp_path / "v2_priors.json"

        exporter = PriorExporter()

        # v1: eco1 is TRUSTED with good performance
        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=v1_path,
        )

        # v2: eco1 is MIXED with mediocre performance
        exporter.export_priors(
            study_id="v2",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=50,
                    successful_applications=30,
                    average_wns_improvement_ps=150.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=v2_path,
        )

        # Configure with highest_weight strategy
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="v1", weight=0.8, prior_repository_path=v1_path),
                SourceStudyConfig(name="v2", weight=0.5, prior_repository_path=v2_path),
            ],
            merge_strategy="highest_weight",
        )

        # Load priors
        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Verify conflict was resolved
        assert "eco1" in loaded

    def test_step_4_verify_prior_from_v1_highest_weight_is_used(self, tmp_path):
        """Step 4: Verify prior from v1 (highest weight) is used."""
        # Create two repositories
        v1_path = tmp_path / "v1_priors.json"
        v2_path = tmp_path / "v2_priors.json"

        exporter = PriorExporter()

        # v1: 250 ps improvement, weight 0.8
        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=v1_path,
        )

        # v2: 150 ps improvement, weight 0.5
        exporter.export_priors(
            study_id="v2",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=50,
                    successful_applications=30,
                    average_wns_improvement_ps=150.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=v2_path,
        )

        # Use highest_weight strategy
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="v1", weight=0.8, prior_repository_path=v1_path),
                SourceStudyConfig(name="v2", weight=0.5, prior_repository_path=v2_path),
            ],
            merge_strategy="highest_weight",
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Should use v1's data (highest weight)
        eco1 = loaded["eco1"]
        # Scaled by 0.8
        assert eco1.total_applications == 80
        assert eco1.average_wns_improvement_ps == 250.0  # v1's value
        assert eco1.prior == ECOPrior.TRUSTED  # v1's prior

    def test_step_5_change_to_conflict_resolution_newest(self):
        """Step 5: Change to conflict_resolution: newest."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
            merge_strategy="newest",
        )

        assert config.merge_strategy == "newest"

    def test_step_6_verify_prior_from_most_recent_source_study_is_used(self, tmp_path):
        """Step 6: Verify prior from most recent source study is used."""
        # Create two repositories with different timestamps
        v1_path = tmp_path / "v1_priors.json"
        v2_path = tmp_path / "v2_priors.json"

        exporter = PriorExporter()

        # v1: older study
        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=v1_path,
            metadata={"timestamp": "2026-01-01T00:00:00Z"},
        )

        # v2: newer study
        exporter.export_priors(
            study_id="v2",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=50,
                    successful_applications=30,
                    average_wns_improvement_ps=150.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=v2_path,
            metadata={"timestamp": "2026-01-10T00:00:00Z"},
        )

        # Use newest strategy
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="v1",
                    weight=0.8,
                    prior_repository_path=v1_path,
                    metadata={"timestamp": "2026-01-01T00:00:00Z"},
                ),
                SourceStudyConfig(
                    name="v2",
                    weight=0.5,
                    prior_repository_path=v2_path,
                    metadata={"timestamp": "2026-01-10T00:00:00Z"},
                ),
            ],
            merge_strategy="newest",
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Should use v2's data (newest)
        eco1 = loaded["eco1"]
        assert eco1.average_wns_improvement_ps == 150.0  # v2's value
        assert eco1.prior == ECOPrior.MIXED  # v2's prior

    def test_step_7_test_conflict_resolution_average(self):
        """Step 7: Test conflict_resolution: average."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
            merge_strategy="weighted_avg",
        )

        assert config.merge_strategy == "weighted_avg"

    def test_step_8_verify_averaged_prior_is_computed(self, tmp_path):
        """Step 8: Verify averaged prior is computed."""
        # Create two repositories
        v1_path = tmp_path / "v1_priors.json"
        v2_path = tmp_path / "v2_priors.json"

        exporter = PriorExporter()

        # v1: 250 ps improvement, weight 0.6
        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    best_wns_improvement_ps=500.0,
                    worst_wns_degradation_ps=-50.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=v1_path,
        )

        # v2: 150 ps improvement, weight 0.4
        exporter.export_priors(
            study_id="v2",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=50,
                    successful_applications=30,
                    average_wns_improvement_ps=150.0,
                    best_wns_improvement_ps=300.0,
                    worst_wns_degradation_ps=-20.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=v2_path,
        )

        # Use weighted_avg strategy
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="v1", weight=0.6, prior_repository_path=v1_path),
                SourceStudyConfig(name="v2", weight=0.4, prior_repository_path=v2_path),
            ],
            merge_strategy="weighted_avg",
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        eco1 = loaded["eco1"]

        # Applications should be summed (after scaling)
        # v1: 100 * 0.6 = 60
        # v2: 50 * 0.4 = 20
        # Total: 80
        assert eco1.total_applications == 80

        # Average should be weighted average
        # (250 * 0.6 + 150 * 0.4) / 1.0 = (150 + 60) / 1.0 = 210
        assert abs(eco1.average_wns_improvement_ps - 210.0) < 1.0

        # Best should be max across all sources
        assert eco1.best_wns_improvement_ps == 500.0

        # Worst should be min across all sources
        assert eco1.worst_wns_degradation_ps == -50.0


class TestConflictResolutionStrategies:
    """Test different conflict resolution strategies in detail."""

    def test_highest_weight_strategy_with_three_sources(self, tmp_path):
        """Test highest_weight with three sources."""
        # Create three repositories
        paths = []
        exporter = PriorExporter()

        for i, (weight, improvement) in enumerate([(0.5, 200.0), (0.8, 250.0), (0.3, 180.0)]):
            path = tmp_path / f"v{i+1}_priors.json"
            paths.append(path)

            exporter.export_priors(
                study_id=f"v{i+1}",
                eco_effectiveness_map={
                    "eco1": ECOEffectiveness(
                        eco_name="eco1",
                        total_applications=100,
                        successful_applications=80,
                        average_wns_improvement_ps=improvement,
                        prior=ECOPrior.TRUSTED,
                    ),
                },
                output_path=path,
            )

        # Use highest_weight strategy
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="v1", weight=0.5, prior_repository_path=paths[0]),
                SourceStudyConfig(name="v2", weight=0.8, prior_repository_path=paths[1]),
                SourceStudyConfig(name="v3", weight=0.3, prior_repository_path=paths[2]),
            ],
            merge_strategy="highest_weight",
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Should use v2's data (weight 0.8, highest)
        assert loaded["eco1"].average_wns_improvement_ps == 250.0

    def test_newest_strategy_uses_timestamp_from_metadata(self, tmp_path):
        """Test newest strategy uses timestamp from source config metadata."""
        # Create two repositories
        v1_path = tmp_path / "v1_priors.json"
        v2_path = tmp_path / "v2_priors.json"

        exporter = PriorExporter()

        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    average_wns_improvement_ps=200.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=v1_path,
        )

        exporter.export_priors(
            study_id="v2",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=50,
                    average_wns_improvement_ps=150.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=v2_path,
        )

        # Configure with timestamps in metadata
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="v1",
                    weight=0.8,
                    prior_repository_path=v1_path,
                    metadata={"timestamp": "2026-01-01T00:00:00Z"},
                ),
                SourceStudyConfig(
                    name="v2",
                    weight=0.5,
                    prior_repository_path=v2_path,
                    metadata={"timestamp": "2026-01-10T00:00:00Z"},
                ),
            ],
            merge_strategy="newest",
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Should use v2 (newest timestamp)
        assert loaded["eco1"].average_wns_improvement_ps == 150.0

    def test_weighted_avg_is_default_strategy(self):
        """Test weighted_avg is the default strategy."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
        )

        assert config.merge_strategy == "weighted_avg"


class TestConflictResolutionEdgeCases:
    """Test edge cases in conflict resolution."""

    def test_single_source_no_conflict(self, tmp_path):
        """Test single source has no conflicts."""
        path = tmp_path / "v1_priors.json"

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    average_wns_improvement_ps=200.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=path,
        )

        # Any strategy should work the same with single source
        for strategy in ["highest_weight", "newest", "weighted_avg"]:
            config = WarmStartConfig(
                mode="warm_start",
                source_studies=[
                    SourceStudyConfig(name="v1", weight=1.0, prior_repository_path=path),
                ],
                merge_strategy=strategy,
            )

            loader = WarmStartLoader(config)
            loaded = loader.load_priors(target_study_id="target")

            assert loaded["eco1"].average_wns_improvement_ps == 200.0

    def test_no_overlap_between_sources(self, tmp_path):
        """Test sources with no overlapping ECOs."""
        v1_path = tmp_path / "v1_priors.json"
        v2_path = tmp_path / "v2_priors.json"

        exporter = PriorExporter()

        # v1 has eco1
        exporter.export_priors(
            study_id="v1",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    average_wns_improvement_ps=200.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=v1_path,
        )

        # v2 has eco2
        exporter.export_priors(
            study_id="v2",
            eco_effectiveness_map={
                "eco2": ECOEffectiveness(
                    eco_name="eco2",
                    total_applications=50,
                    average_wns_improvement_ps=150.0,
                    prior=ECOPrior.MIXED,
                ),
            },
            output_path=v2_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(name="v1", weight=0.8, prior_repository_path=v1_path),
                SourceStudyConfig(name="v2", weight=0.5, prior_repository_path=v2_path),
            ],
            merge_strategy="highest_weight",
        )

        loader = WarmStartLoader(config)
        loaded = loader.load_priors(target_study_id="target")

        # Should have both ECOs (no conflict)
        assert "eco1" in loaded
        assert "eco2" in loaded
        assert loaded["eco1"].average_wns_improvement_ps == 200.0
        assert loaded["eco2"].average_wns_improvement_ps == 150.0
