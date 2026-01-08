"""Tests for ECO prior sharing across Studies."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior
from src.controller.prior_sharing import (
    PriorExporter,
    PriorImporter,
    PriorProvenance,
    PriorRepository,
    PriorSharingConfig,
)


class TestPriorProvenance:
    """Tests for PriorProvenance."""

    def test_create_provenance(self) -> None:
        """Test creating provenance record."""
        provenance = PriorProvenance(
            source_study_id="study_a",
            export_timestamp="2024-01-01T00:00:00Z",
            source_study_snapshot_hash="abc123",
        )

        assert provenance.source_study_id == "study_a"
        assert provenance.export_timestamp == "2024-01-01T00:00:00Z"
        assert provenance.source_study_snapshot_hash == "abc123"

    def test_provenance_to_dict(self) -> None:
        """Test converting provenance to dict."""
        provenance = PriorProvenance(
            source_study_id="study_a",
            export_timestamp="2024-01-01T00:00:00Z",
            export_metadata={"key": "value"},
        )

        data = provenance.to_dict()
        assert data["source_study_id"] == "study_a"
        assert data["export_timestamp"] == "2024-01-01T00:00:00Z"
        assert data["export_metadata"] == {"key": "value"}


class TestPriorRepository:
    """Tests for PriorRepository."""

    def test_create_empty_repository(self) -> None:
        """Test creating an empty repository."""
        repo = PriorRepository()

        assert len(repo.eco_priors) == 0
        assert repo.provenance is None

    def test_add_eco_prior(self) -> None:
        """Test adding an ECO prior to repository."""
        repo = PriorRepository()
        effectiveness = ECOEffectiveness(
            eco_name="eco1",
            total_applications=10,
            successful_applications=8,
            average_wns_improvement_ps=50.0,
            prior=ECOPrior.TRUSTED,
        )

        repo.add_eco_prior(effectiveness)

        assert "eco1" in repo.eco_priors
        assert repo.eco_priors["eco1"].eco_name == "eco1"
        assert repo.eco_priors["eco1"].prior == ECOPrior.TRUSTED

    def test_get_eco_prior(self) -> None:
        """Test retrieving an ECO prior."""
        repo = PriorRepository()
        effectiveness = ECOEffectiveness(eco_name="eco1", prior=ECOPrior.MIXED)
        repo.add_eco_prior(effectiveness)

        retrieved = repo.get_eco_prior("eco1")
        assert retrieved is not None
        assert retrieved.eco_name == "eco1"
        assert retrieved.prior == ECOPrior.MIXED

    def test_get_nonexistent_prior(self) -> None:
        """Test retrieving a nonexistent prior."""
        repo = PriorRepository()

        retrieved = repo.get_eco_prior("nonexistent")
        assert retrieved is None

    def test_repository_to_dict(self) -> None:
        """Test converting repository to dict."""
        provenance = PriorProvenance(
            source_study_id="study_a", export_timestamp="2024-01-01T00:00:00Z"
        )
        repo = PriorRepository(provenance=provenance)

        effectiveness = ECOEffectiveness(
            eco_name="eco1",
            total_applications=5,
            successful_applications=4,
            average_wns_improvement_ps=100.0,
            prior=ECOPrior.TRUSTED,
        )
        repo.add_eco_prior(effectiveness)

        data = repo.to_dict()
        assert "eco_priors" in data
        assert "eco1" in data["eco_priors"]
        assert data["eco_priors"]["eco1"]["eco_name"] == "eco1"
        assert data["eco_priors"]["eco1"]["prior"] == "trusted"
        assert data["provenance"]["source_study_id"] == "study_a"

    def test_repository_from_dict(self) -> None:
        """Test creating repository from dict."""
        data = {
            "eco_priors": {
                "eco1": {
                    "eco_name": "eco1",
                    "total_applications": 5,
                    "successful_applications": 4,
                    "failed_applications": 1,
                    "average_wns_improvement_ps": 100.0,
                    "best_wns_improvement_ps": 150.0,
                    "worst_wns_degradation_ps": -10.0,
                    "prior": "trusted",
                }
            },
            "provenance": {
                "source_study_id": "study_a",
                "export_timestamp": "2024-01-01T00:00:00Z",
                "source_study_snapshot_hash": "abc123",
                "export_metadata": {},
            },
            "repository_metadata": {"version": "1.0"},
        }

        repo = PriorRepository.from_dict(data)

        assert "eco1" in repo.eco_priors
        assert repo.eco_priors["eco1"].eco_name == "eco1"
        assert repo.eco_priors["eco1"].prior == ECOPrior.TRUSTED
        assert repo.provenance is not None
        assert repo.provenance.source_study_id == "study_a"


class TestPriorExporter:
    """Tests for PriorExporter."""

    def test_export_priors(self) -> None:
        """Test exporting priors to a file."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "priors.json"

            # Create effectiveness data
            eco_map = {
                "eco1": ECOEffectiveness(
                    eco_name="eco1",
                    total_applications=10,
                    successful_applications=8,
                    average_wns_improvement_ps=75.0,
                    prior=ECOPrior.TRUSTED,
                ),
                "eco2": ECOEffectiveness(
                    eco_name="eco2",
                    total_applications=5,
                    successful_applications=2,
                    average_wns_improvement_ps=-20.0,
                    prior=ECOPrior.SUSPICIOUS,
                ),
            }

            # Export
            exporter = PriorExporter()
            repo = exporter.export_priors(
                study_id="study_a",
                eco_effectiveness_map=eco_map,
                output_path=output_path,
                snapshot_hash="hash123",
                metadata={"note": "test export"},
            )

            # Verify file was created
            assert output_path.exists()

            # Verify repository contents
            assert len(repo.eco_priors) == 2
            assert "eco1" in repo.eco_priors
            assert "eco2" in repo.eco_priors

            # Verify provenance
            assert repo.provenance is not None
            assert repo.provenance.source_study_id == "study_a"
            assert repo.provenance.source_study_snapshot_hash == "hash123"

            # Verify file contents
            with open(output_path) as f:
                data = json.load(f)

            assert "eco_priors" in data
            assert len(data["eco_priors"]) == 2
            assert data["provenance"]["source_study_id"] == "study_a"

    def test_export_creates_directories(self) -> None:
        """Test that export creates parent directories if needed."""
        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "subdir" / "nested" / "priors.json"

            eco_map = {
                "eco1": ECOEffectiveness(eco_name="eco1", prior=ECOPrior.UNKNOWN)
            }

            exporter = PriorExporter()
            exporter.export_priors(
                study_id="study_a",
                eco_effectiveness_map=eco_map,
                output_path=output_path,
            )

            assert output_path.exists()
            assert output_path.parent.exists()


class TestPriorImporter:
    """Tests for PriorImporter."""

    def test_import_priors(self) -> None:
        """Test importing priors from a file."""
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "priors.json"

            # Create a repository file
            data = {
                "eco_priors": {
                    "eco1": {
                        "eco_name": "eco1",
                        "total_applications": 10,
                        "successful_applications": 8,
                        "failed_applications": 2,
                        "average_wns_improvement_ps": 75.0,
                        "best_wns_improvement_ps": 100.0,
                        "worst_wns_degradation_ps": -5.0,
                        "prior": "trusted",
                    }
                },
                "provenance": {
                    "source_study_id": "study_a",
                    "export_timestamp": "2024-01-01T00:00:00Z",
                    "source_study_snapshot_hash": None,
                    "export_metadata": {},
                },
                "repository_metadata": {},
            }

            with open(repo_path, "w") as f:
                json.dump(data, f)

            # Import
            importer = PriorImporter()
            eco_priors = importer.import_priors(
                repository_path=repo_path, target_study_id="study_b"
            )

            # Verify imported priors
            assert "eco1" in eco_priors
            assert eco_priors["eco1"].eco_name == "eco1"
            assert eco_priors["eco1"].total_applications == 10
            assert eco_priors["eco1"].prior == ECOPrior.TRUSTED

    def test_import_with_audit_trail(self) -> None:
        """Test importing priors with audit trail."""
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "priors.json"
            audit_path = Path(tmpdir) / "audit.json"

            # Create a repository file
            data = {
                "eco_priors": {
                    "eco1": {
                        "eco_name": "eco1",
                        "total_applications": 5,
                        "successful_applications": 5,
                        "failed_applications": 0,
                        "average_wns_improvement_ps": 50.0,
                        "best_wns_improvement_ps": 50.0,
                        "worst_wns_degradation_ps": 0.0,
                        "prior": "mixed",
                    }
                },
                "provenance": {
                    "source_study_id": "study_a",
                    "export_timestamp": "2024-01-01T00:00:00Z",
                    "source_study_snapshot_hash": "abc123",
                    "export_metadata": {"note": "test"},
                },
                "repository_metadata": {},
            }

            with open(repo_path, "w") as f:
                json.dump(data, f)

            # Import with audit trail
            importer = PriorImporter()
            eco_priors = importer.import_priors(
                repository_path=repo_path,
                target_study_id="study_b",
                audit_trail_path=audit_path,
            )

            # Verify audit trail was created
            assert audit_path.exists()

            with open(audit_path) as f:
                audit_data = json.load(f)

            assert audit_data["target_study_id"] == "study_b"
            assert audit_data["eco_count"] == 1
            assert "eco1" in audit_data["imported_ecos"]
            assert audit_data["provenance"]["source_study_id"] == "study_a"

    def test_import_nonexistent_file(self) -> None:
        """Test importing from a nonexistent file."""
        importer = PriorImporter()

        with pytest.raises(FileNotFoundError):
            importer.import_priors(
                repository_path=Path("/nonexistent/priors.json"),
                target_study_id="study_b",
            )


class TestPriorSharingConfig:
    """Tests for PriorSharingConfig."""

    def test_disabled_config(self) -> None:
        """Test disabled prior sharing config."""
        config = PriorSharingConfig(enabled=False)
        config.validate()  # Should not raise

    def test_enabled_requires_import_path(self) -> None:
        """Test that enabled config requires import path."""
        config = PriorSharingConfig(enabled=True)

        with pytest.raises(ValueError, match="import_repository_path"):
            config.validate()

    def test_export_requires_export_path(self) -> None:
        """Test that export requires export path."""
        config = PriorSharingConfig(
            enabled=True,
            import_repository_path=Path("/tmp/import.json"),
            export_on_completion=True,
        )

        with pytest.raises(ValueError, match="export_repository_path"):
            config.validate()

    def test_valid_config_with_import(self) -> None:
        """Test valid config with import."""
        config = PriorSharingConfig(
            enabled=True, import_repository_path=Path("/tmp/priors.json")
        )

        config.validate()  # Should not raise

    def test_valid_config_with_import_and_export(self) -> None:
        """Test valid config with import and export."""
        config = PriorSharingConfig(
            enabled=True,
            import_repository_path=Path("/tmp/import.json"),
            export_on_completion=True,
            export_repository_path=Path("/tmp/export.json"),
        )

        config.validate()  # Should not raise


class TestPriorSharingEndToEnd:
    """End-to-end tests for prior sharing workflow."""

    def test_export_then_import_workflow(self) -> None:
        """
        Feature #67: Enable optional prior sharing across Studies with explicit configuration.

        Steps:
            1. Execute Study A with ECO priors accumulated
            2. Export Study A priors to shared repository
            3. Create Study B with explicit prior import enabled
            4. Verify Study B initializes ECOs with imported priors
            5. Confirm import is audited in Study B provenance
        """
        with TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / "shared_priors.json"
            audit_path = Path(tmpdir) / "study_b_audit.json"

            # Step 1 & 2: Study A accumulates priors and exports them
            study_a_priors = {
                "buffer_insertion": ECOEffectiveness(
                    eco_name="buffer_insertion",
                    total_applications=20,
                    successful_applications=18,
                    failed_applications=2,
                    average_wns_improvement_ps=120.0,
                    best_wns_improvement_ps=200.0,
                    worst_wns_degradation_ps=-10.0,
                    prior=ECOPrior.TRUSTED,
                ),
                "gate_sizing": ECOEffectiveness(
                    eco_name="gate_sizing",
                    total_applications=15,
                    successful_applications=10,
                    failed_applications=5,
                    average_wns_improvement_ps=50.0,
                    best_wns_improvement_ps=100.0,
                    worst_wns_degradation_ps=-30.0,
                    prior=ECOPrior.MIXED,
                ),
            }

            exporter = PriorExporter()
            exported_repo = exporter.export_priors(
                study_id="study_a",
                eco_effectiveness_map=study_a_priors,
                output_path=repo_path,
                snapshot_hash="study_a_snapshot_hash",
                metadata={"description": "Study A prior export"},
            )

            # Verify export
            assert repo_path.exists()
            assert len(exported_repo.eco_priors) == 2
            assert exported_repo.provenance is not None
            assert exported_repo.provenance.source_study_id == "study_a"

            # Step 3 & 4: Study B imports priors
            importer = PriorImporter()
            study_b_priors = importer.import_priors(
                repository_path=repo_path,
                target_study_id="study_b",
                audit_trail_path=audit_path,
            )

            # Verify imported priors
            assert len(study_b_priors) == 2
            assert "buffer_insertion" in study_b_priors
            assert "gate_sizing" in study_b_priors

            # Verify buffer_insertion prior
            buffer_prior = study_b_priors["buffer_insertion"]
            assert buffer_prior.eco_name == "buffer_insertion"
            assert buffer_prior.total_applications == 20
            assert buffer_prior.prior == ECOPrior.TRUSTED
            assert buffer_prior.average_wns_improvement_ps == 120.0

            # Verify gate_sizing prior
            gate_prior = study_b_priors["gate_sizing"]
            assert gate_prior.eco_name == "gate_sizing"
            assert gate_prior.total_applications == 15
            assert gate_prior.prior == ECOPrior.MIXED

            # Step 5: Verify audit trail
            assert audit_path.exists()

            with open(audit_path) as f:
                audit_data = json.load(f)

            assert audit_data["target_study_id"] == "study_b"
            assert audit_data["eco_count"] == 2
            assert set(audit_data["imported_ecos"]) == {"buffer_insertion", "gate_sizing"}
            assert audit_data["provenance"]["source_study_id"] == "study_a"
            assert audit_data["provenance"]["source_study_snapshot_hash"] == "study_a_snapshot_hash"

    def test_config_based_workflow(self) -> None:
        """Test prior sharing using PriorSharingConfig."""
        with TemporaryDirectory() as tmpdir:
            import_path = Path(tmpdir) / "import_priors.json"
            export_path = Path(tmpdir) / "export_priors.json"

            # Create initial repository
            initial_priors = {
                "eco1": ECOEffectiveness(eco_name="eco1", prior=ECOPrior.TRUSTED)
            }

            exporter = PriorExporter()
            exporter.export_priors(
                study_id="initial_study",
                eco_effectiveness_map=initial_priors,
                output_path=import_path,
            )

            # Create config for Study B
            config = PriorSharingConfig(
                enabled=True,
                import_repository_path=import_path,
                export_on_completion=True,
                export_repository_path=export_path,
                audit_trail_enabled=True,
            )

            # Validate config
            config.validate()

            # Import priors using config
            importer = PriorImporter()
            priors = importer.import_priors(
                repository_path=config.import_repository_path,
                target_study_id="study_b",
            )

            assert "eco1" in priors
            assert priors["eco1"].prior == ECOPrior.TRUSTED
