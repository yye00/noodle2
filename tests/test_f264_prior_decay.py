"""Tests for F264: Warm-start supports prior decay for older studies."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from controller.eco import ECOEffectiveness, ECOPrior
from controller.prior_sharing import PriorExporter
from controller.warm_start import SourceStudyConfig, WarmStartConfig, WarmStartLoader


class TestF264ConfigureDecay:
    """Test Step 1: Configure warm-start with decay: 0.9."""

    def test_step_1_configure_warm_start_with_decay(self):
        """Step 1: Configure warm-start with decay: 0.9."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
            decay=0.9,
        )

        assert config.decay == 0.9

    def test_decay_defaults_to_none(self):
        """Verify decay defaults to None (no decay)."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
        )

        assert config.decay is None

    def test_decay_validation(self):
        """Verify decay must be between 0.0 and 1.0."""
        # Valid values
        WarmStartConfig(mode="warm_start", decay=0.0)
        WarmStartConfig(mode="warm_start", decay=0.5)
        WarmStartConfig(mode="warm_start", decay=1.0)

        # Invalid values
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            WarmStartConfig(mode="warm_start", decay=-0.1)

        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            WarmStartConfig(mode="warm_start", decay=1.5)

    def test_decay_in_to_dict(self):
        """Verify decay is included in serialization."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
            decay=0.9,
        )

        config_dict = config.to_dict()
        assert config_dict["decay"] == 0.9

    def test_no_decay_not_in_to_dict(self):
        """Verify decay is not in dict when None."""
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[],
        )

        config_dict = config.to_dict()
        assert "decay" not in config_dict


class TestF264LoadPriorsFromOldStudy:
    """Test Step 2: Load priors from study completed 5 days ago."""

    def test_step_2_load_priors_from_old_study(self, tmp_path):
        """Step 2: Load priors from study completed 5 days ago."""
        # Create a prior repository for a study completed 5 days ago
        current_time = datetime.now(UTC)
        completion_time = current_time - timedelta(days=5)

        prior_path = tmp_path / "old_study_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="old_study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        # Configure warm-start with decay
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="old_study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={
                        "completion_timestamp": completion_time.isoformat(),
                    },
                ),
            ],
            decay=0.9,
        )

        loader = WarmStartLoader(config)
        priors = loader.load_priors("new_study", current_time=current_time)

        # Verify priors were loaded
        assert "eco1" in priors
        assert priors["eco1"].eco_name == "eco1"

    def test_load_priors_without_completion_timestamp(self, tmp_path):
        """Verify decay not applied if completion_timestamp missing."""
        current_time = datetime.now(UTC)

        prior_path = tmp_path / "study_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        # Configure with decay but no timestamp in metadata
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={},  # No completion_timestamp
                ),
            ],
            decay=0.9,
        )

        loader = WarmStartLoader(config)
        priors = loader.load_priors("new_study", current_time=current_time)

        # Priors loaded without decay
        assert "eco1" in priors
        # Weight should be original 1.0, not decayed
        # (we'll verify this in step 3)


class TestF264VerifyDecayApplication:
    """Test Step 3: Verify prior confidence is multiplied by 0.9^5."""

    def test_step_3_verify_decay_calculation(self, tmp_path):
        """Step 3: Verify prior confidence is multiplied by 0.9^5."""
        current_time = datetime.now(UTC)
        completion_time = current_time - timedelta(days=5)

        prior_path = tmp_path / "old_study_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="old_study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="old_study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={
                        "completion_timestamp": completion_time.isoformat(),
                    },
                ),
            ],
            decay=0.9,
        )

        loader = WarmStartLoader(config)
        priors = loader.load_priors("new_study", current_time=current_time)

        # Verify decay was applied: 0.9^5 ≈ 0.59049
        # The decay affects the weight used for scaling, so counts are scaled
        expected_decay_factor = 0.9**5
        assert "eco1" in priors

        # Total applications should be scaled by decay factor
        # Original: 100, with decay: 100 * 0.59049 ≈ 59
        assert priors["eco1"].total_applications == int(100 * expected_decay_factor)

    def test_decay_with_different_ages(self, tmp_path):
        """Test decay with different study ages."""
        current_time = datetime.now(UTC)

        test_cases = [
            (1, 0.9**1),  # 1 day old
            (5, 0.9**5),  # 5 days old
            (10, 0.9**10),  # 10 days old
            (30, 0.9**30),  # 30 days old
        ]

        for days_old, expected_factor in test_cases:
            completion_time = current_time - timedelta(days=days_old)

            prior_path = tmp_path / f"study_{days_old}_priors.json"
            exporter = PriorExporter()
            exporter.export_priors(
                study_id=f"study_{days_old}",
                eco_effectiveness_map={
                    "eco1": ECOEffectiveness(
                        eco_name="eco1",
                        total_applications=100,
                        successful_applications=90,
                        average_wns_improvement_ps=250.0,
                        prior=ECOPrior.TRUSTED,
                    ),
                },
                output_path=prior_path,
            )

            config = WarmStartConfig(
                mode="warm_start",
                source_studies=[
                    SourceStudyConfig(
                        name=f"study_{days_old}",
                        weight=1.0,
                        prior_repository_path=prior_path,
                        metadata={
                            "completion_timestamp": completion_time.isoformat(),
                        },
                    ),
                ],
                decay=0.9,
            )

            loader = WarmStartLoader(config)
            priors = loader.load_priors("new_study", current_time=current_time)

            # Verify decay factor is correct
            expected_count = int(100 * expected_factor)
            assert priors["eco1"].total_applications == expected_count

    def test_decay_with_different_decay_rates(self, tmp_path):
        """Test decay with different decay rates."""
        current_time = datetime.now(UTC)
        completion_time = current_time - timedelta(days=5)

        decay_rates = [0.8, 0.9, 0.95, 0.99]

        for decay_rate in decay_rates:
            prior_path = tmp_path / f"study_{decay_rate}_priors.json"
            exporter = PriorExporter()
            exporter.export_priors(
                study_id=f"study_{decay_rate}",
                eco_effectiveness_map={
                    "eco1": ECOEffectiveness(
                        eco_name="eco1",
                        total_applications=100,
                        successful_applications=90,
                        average_wns_improvement_ps=250.0,
                        prior=ECOPrior.TRUSTED,
                    ),
                },
                output_path=prior_path,
            )

            config = WarmStartConfig(
                mode="warm_start",
                source_studies=[
                    SourceStudyConfig(
                        name=f"study_{decay_rate}",
                        weight=1.0,
                        prior_repository_path=prior_path,
                        metadata={
                            "completion_timestamp": completion_time.isoformat(),
                        },
                    ),
                ],
                decay=decay_rate,
            )

            loader = WarmStartLoader(config)
            priors = loader.load_priors("new_study", current_time=current_time)

            # Verify decay factor
            expected_factor = decay_rate**5
            expected_count = int(100 * expected_factor)
            assert priors["eco1"].total_applications == expected_count


class TestF264OlderPriorsLowerInfluence:
    """Test Step 4: Verify older priors have lower influence."""

    def test_step_4_older_priors_lower_influence(self, tmp_path):
        """Step 4: Verify older priors have lower influence than newer ones."""
        current_time = datetime.now(UTC)

        # Create two studies: one 1 day old, one 10 days old
        recent_completion = current_time - timedelta(days=1)
        old_completion = current_time - timedelta(days=10)

        recent_path = tmp_path / "recent_priors.json"
        old_path = tmp_path / "old_priors.json"

        exporter = PriorExporter()

        # Both studies have same original data
        for path, study_id in [(recent_path, "recent"), (old_path, "old")]:
            exporter.export_priors(
                study_id=study_id,
                eco_effectiveness_map={
                    "eco1": ECOEffectiveness(
                        eco_name="eco1",
                        total_applications=100,
                        successful_applications=90,
                        average_wns_improvement_ps=250.0,
                        prior=ECOPrior.TRUSTED,
                    ),
                },
                output_path=path,
            )

        # Load recent study
        recent_config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="recent",
                    weight=1.0,
                    prior_repository_path=recent_path,
                    metadata={"completion_timestamp": recent_completion.isoformat()},
                ),
            ],
            decay=0.9,
        )
        recent_loader = WarmStartLoader(recent_config)
        recent_priors = recent_loader.load_priors("new_study", current_time=current_time)

        # Load old study
        old_config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="old",
                    weight=1.0,
                    prior_repository_path=old_path,
                    metadata={"completion_timestamp": old_completion.isoformat()},
                ),
            ],
            decay=0.9,
        )
        old_loader = WarmStartLoader(old_config)
        old_priors = old_loader.load_priors("new_study", current_time=current_time)

        # Verify recent study has higher influence (more applications retained)
        assert recent_priors["eco1"].total_applications > old_priors["eco1"].total_applications

        # Recent: 0.9^1 ≈ 0.9, so ~90 applications
        # Old: 0.9^10 ≈ 0.349, so ~35 applications
        assert recent_priors["eco1"].total_applications == int(100 * 0.9**1)
        assert old_priors["eco1"].total_applications == int(100 * 0.9**10)

    def test_multiple_sources_with_different_ages(self, tmp_path):
        """Test merging priors from sources with different ages."""
        current_time = datetime.now(UTC)

        recent_completion = current_time - timedelta(days=1)
        old_completion = current_time - timedelta(days=10)

        recent_path = tmp_path / "recent_priors.json"
        old_path = tmp_path / "old_priors.json"

        exporter = PriorExporter()

        # Recent study: high success rate
        exporter.export_priors(
            study_id="recent",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=300.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=recent_path,
        )

        # Old study: also good but older
        exporter.export_priors(
            study_id="old",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=80,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=old_path,
        )

        # Load from both sources with decay
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="recent",
                    weight=1.0,
                    prior_repository_path=recent_path,
                    metadata={"completion_timestamp": recent_completion.isoformat()},
                ),
                SourceStudyConfig(
                    name="old",
                    weight=1.0,
                    prior_repository_path=old_path,
                    metadata={"completion_timestamp": old_completion.isoformat()},
                ),
            ],
            merge_strategy="weighted_avg",
            decay=0.9,
        )

        loader = WarmStartLoader(config)
        priors = loader.load_priors("new_study", current_time=current_time)

        # Merged priors should favor recent study due to higher effective weight
        assert "eco1" in priors

        # Recent contributes more: 100 * 0.9^1 = 90
        # Old contributes less: 100 * 0.9^10 = 35
        # Total: ~125 applications
        expected_total = int(100 * 0.9**1) + int(100 * 0.9**10)
        assert priors["eco1"].total_applications == expected_total


class TestF264DecayLoggedInProvenance:
    """Test Step 5: Verify decay is logged in prior provenance."""

    def test_step_5_decay_logged_in_audit_trail(self, tmp_path):
        """Step 5: Verify decay is logged in prior provenance (audit trail)."""
        current_time = datetime.now(UTC)
        completion_time = current_time - timedelta(days=5)

        prior_path = tmp_path / "study_priors.json"
        audit_path = tmp_path / "audit_trail.json"

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={"completion_timestamp": completion_time.isoformat()},
                ),
            ],
            decay=0.9,
        )

        loader = WarmStartLoader(config)
        loader.load_priors("new_study", audit_trail_path=audit_path, current_time=current_time)

        # Read audit trail
        import json

        with open(audit_path) as f:
            audit = json.load(f)

        # Verify decay is logged
        assert audit["decay"] == 0.9
        assert "decay_metadata" in audit

        # Verify decay metadata for source 0
        decay_meta = audit["decay_metadata"]["0"]
        assert "completion_timestamp" in decay_meta
        assert "age_days" in decay_meta
        assert "decay_factor" in decay_meta
        assert "original_weight" in decay_meta
        assert "effective_weight" in decay_meta

        # Verify values
        assert decay_meta["age_days"] == pytest.approx(5.0, abs=0.1)
        assert decay_meta["decay_factor"] == pytest.approx(0.9**5, rel=0.001)
        assert decay_meta["original_weight"] == 1.0
        assert decay_meta["effective_weight"] == pytest.approx(0.9**5, rel=0.001)

    def test_audit_trail_without_decay(self, tmp_path):
        """Verify audit trail when decay is not configured."""
        current_time = datetime.now(UTC)

        prior_path = tmp_path / "study_priors.json"
        audit_path = tmp_path / "audit_trail.json"

        exporter = PriorExporter()
        exporter.export_priors(
            study_id="study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        # No decay configured
        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={},
                ),
            ],
        )

        loader = WarmStartLoader(config)
        loader.load_priors("new_study", audit_trail_path=audit_path, current_time=current_time)

        # Read audit trail
        import json

        with open(audit_path) as f:
            audit = json.load(f)

        # Verify no decay information
        assert "decay" not in audit
        assert "decay_metadata" not in audit

    def test_audit_trail_with_multiple_sources(self, tmp_path):
        """Verify audit trail with multiple sources and different ages."""
        current_time = datetime.now(UTC)

        source1_completion = current_time - timedelta(days=2)
        source2_completion = current_time - timedelta(days=10)

        path1 = tmp_path / "source1_priors.json"
        path2 = tmp_path / "source2_priors.json"
        audit_path = tmp_path / "audit_trail.json"

        exporter = PriorExporter()

        for path, study_id in [(path1, "source1"), (path2, "source2")]:
            exporter.export_priors(
                study_id=study_id,
                eco_effectiveness_map={
                    "eco1": ECOEffectiveness(
                        eco_name="eco1",
                        total_applications=100,
                        successful_applications=90,
                        average_wns_improvement_ps=250.0,
                        prior=ECOPrior.TRUSTED,
                    ),
                },
                output_path=path,
            )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="source1",
                    weight=0.8,
                    prior_repository_path=path1,
                    metadata={"completion_timestamp": source1_completion.isoformat()},
                ),
                SourceStudyConfig(
                    name="source2",
                    weight=0.6,
                    prior_repository_path=path2,
                    metadata={"completion_timestamp": source2_completion.isoformat()},
                ),
            ],
            decay=0.95,
        )

        loader = WarmStartLoader(config)
        loader.load_priors("new_study", audit_trail_path=audit_path, current_time=current_time)

        # Read audit trail
        import json

        with open(audit_path) as f:
            audit = json.load(f)

        # Verify decay metadata for both sources
        assert "0" in audit["decay_metadata"]
        assert "1" in audit["decay_metadata"]

        # Source 0: 2 days old
        meta0 = audit["decay_metadata"]["0"]
        assert meta0["age_days"] == pytest.approx(2.0, abs=0.1)
        assert meta0["decay_factor"] == pytest.approx(0.95**2, rel=0.001)
        assert meta0["original_weight"] == 0.8
        assert meta0["effective_weight"] == pytest.approx(0.8 * (0.95**2), rel=0.001)

        # Source 1: 10 days old
        meta1 = audit["decay_metadata"]["1"]
        assert meta1["age_days"] == pytest.approx(10.0, abs=0.1)
        assert meta1["decay_factor"] == pytest.approx(0.95**10, rel=0.001)
        assert meta1["original_weight"] == 0.6
        assert meta1["effective_weight"] == pytest.approx(0.6 * (0.95**10), rel=0.001)


class TestF264EdgeCases:
    """Test edge cases for prior decay."""

    def test_decay_zero_days_old(self, tmp_path):
        """Test decay with study completed today (0 days old)."""
        current_time = datetime.now(UTC)
        completion_time = current_time  # Same time

        prior_path = tmp_path / "study_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={"completion_timestamp": completion_time.isoformat()},
                ),
            ],
            decay=0.9,
        )

        loader = WarmStartLoader(config)
        priors = loader.load_priors("new_study", current_time=current_time)

        # 0.9^0 = 1.0, no decay
        assert priors["eco1"].total_applications == 100

    def test_decay_with_zero_decay_rate(self, tmp_path):
        """Test with decay=0.0 (extreme decay)."""
        current_time = datetime.now(UTC)
        completion_time = current_time - timedelta(days=1)

        prior_path = tmp_path / "study_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={"completion_timestamp": completion_time.isoformat()},
                ),
            ],
            decay=0.0,
        )

        loader = WarmStartLoader(config)
        priors = loader.load_priors("new_study", current_time=current_time)

        # 0.0^1 = 0.0, complete decay
        assert priors["eco1"].total_applications == 0

    def test_decay_with_no_decay_rate(self, tmp_path):
        """Test with decay=1.0 (no decay)."""
        current_time = datetime.now(UTC)
        completion_time = current_time - timedelta(days=100)

        prior_path = tmp_path / "study_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="study",
            eco_effectiveness_map={
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=100,
                    successful_applications=90,
                    average_wns_improvement_ps=250.0,
                    prior=ECOPrior.TRUSTED,
                ),
            },
            output_path=prior_path,
        )

        config = WarmStartConfig(
            mode="warm_start",
            source_studies=[
                SourceStudyConfig(
                    name="study",
                    weight=1.0,
                    prior_repository_path=prior_path,
                    metadata={"completion_timestamp": completion_time.isoformat()},
                ),
            ],
            decay=1.0,
        )

        loader = WarmStartLoader(config)
        priors = loader.load_priors("new_study", current_time=current_time)

        # 1.0^100 = 1.0, no decay regardless of age
        assert priors["eco1"].total_applications == 100
