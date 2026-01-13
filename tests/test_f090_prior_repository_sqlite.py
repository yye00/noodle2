"""
Test F090: Cross-project prior repository can persist priors to SQLite database

This test validates that ECO priors can be persisted to and retrieved from
a SQLite database for cross-project sharing.

Feature F090 Steps:
1. Initialize PriorRepository with ~/.noodle2/priors/ path
2. Store ECO prior data (name, success_rate, average_improvement)
3. Verify priors.db file is created
4. Query priors from database
5. Verify data integrity across sessions
"""

import json
import sqlite3
from pathlib import Path

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior
from src.controller.prior_repository_sqlite import SQLitePriorRepository
from src.controller.prior_sharing import PriorProvenance


class TestF090SQLitePriorRepository:
    """Test F090: SQLite prior repository persistence"""

    @pytest.fixture
    def temp_db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path for testing."""
        return tmp_path / "test_priors.db"

    @pytest.fixture
    def repository(self, temp_db_path: Path) -> SQLitePriorRepository:
        """Create a SQLite prior repository for testing."""
        return SQLitePriorRepository(db_path=temp_db_path)

    @pytest.fixture
    def sample_eco_effectiveness(self) -> ECOEffectiveness:
        """Create sample ECO effectiveness data."""
        return ECOEffectiveness(
            eco_name="CellResizeECO",
            total_applications=100,
            successful_applications=85,
            failed_applications=15,
            average_wns_improvement_ps=150,
            best_wns_improvement_ps=500,
            worst_wns_degradation_ps=-50,
            prior=ECOPrior.TRUSTED,
        )

    def test_step_1_initialize_repository_with_default_path(self):
        """Step 1: Initialize PriorRepository with ~/.noodle2/priors/ path"""
        # Use default path
        repository = SQLitePriorRepository()

        # Verify database path uses ~/.noodle2/priors/
        expected_path = Path.home() / ".noodle2" / "priors" / "priors.db"
        assert repository.db_path == expected_path

        # Verify directory was created
        assert repository.db_path.parent.exists()

        # Verify database file was created
        assert repository.db_path.exists()

    def test_step_1_initialize_repository_with_custom_path(self, temp_db_path: Path):
        """Step 1: Initialize repository with custom path"""
        repository = SQLitePriorRepository(db_path=temp_db_path)

        # Verify database was created at custom path
        assert repository.db_path == temp_db_path
        assert temp_db_path.exists()

    def test_step_1_database_schema_is_created(self, repository: SQLitePriorRepository):
        """Step 1: Verify database schema is properly initialized"""
        # Connect to database and check schema
        with sqlite3.connect(repository.db_path) as conn:
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='eco_priors'
            """)
            table = cursor.fetchone()
            assert table is not None, "eco_priors table not created"

            # Check table schema
            cursor = conn.execute("PRAGMA table_info(eco_priors)")
            columns = {row[1] for row in cursor.fetchall()}

            required_columns = {
                "eco_name",
                "total_applications",
                "successful_applications",
                "failed_applications",
                "average_wns_improvement_ps",
                "best_wns_improvement_ps",
                "worst_wns_degradation_ps",
                "prior",
                "last_updated",
                "provenance_json",
            }

            assert required_columns.issubset(columns), (
                f"Missing required columns. Expected {required_columns}, got {columns}"
            )

    def test_step_2_store_eco_prior_data(
        self,
        repository: SQLitePriorRepository,
        sample_eco_effectiveness: ECOEffectiveness
    ):
        """Step 2: Store ECO prior data (name, success_rate, average_improvement)"""
        # Store prior
        repository.store_prior(sample_eco_effectiveness)

        # Verify data was stored by querying directly
        with sqlite3.connect(repository.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM eco_priors WHERE eco_name = ?",
                (sample_eco_effectiveness.eco_name,)
            )
            row = cursor.fetchone()

            assert row is not None, "Prior not stored in database"
            assert row["eco_name"] == "CellResizeECO"
            assert row["total_applications"] == 100
            assert row["successful_applications"] == 85
            assert row["failed_applications"] == 15
            assert row["average_wns_improvement_ps"] == 150
            assert row["best_wns_improvement_ps"] == 500
            assert row["worst_wns_degradation_ps"] == -50
            assert row["prior"] == "trusted"

    def test_step_2_store_multiple_eco_priors(self, repository: SQLitePriorRepository):
        """Step 2: Store multiple different ECO priors"""
        ecos = [
            ECOEffectiveness(
                eco_name="CellResizeECO",
                total_applications=100,
                successful_applications=85,
                failed_applications=15,
                average_wns_improvement_ps=150,
                best_wns_improvement_ps=500,
                worst_wns_degradation_ps=-50,
                prior=ECOPrior.TRUSTED,
            ),
            ECOEffectiveness(
                eco_name="BufferInsertionECO",
                total_applications=50,
                successful_applications=30,
                failed_applications=20,
                average_wns_improvement_ps=75,
                best_wns_improvement_ps=200,
                worst_wns_degradation_ps=-100,
                prior=ECOPrior.MIXED,
            ),
            ECOEffectiveness(
                eco_name="CellSwapECO",
                total_applications=20,
                successful_applications=5,
                failed_applications=15,
                average_wns_improvement_ps=10,
                best_wns_improvement_ps=50,
                worst_wns_degradation_ps=-200,
                prior=ECOPrior.SUSPICIOUS,
            ),
        ]

        # Store all priors
        for eco in ecos:
            repository.store_prior(eco)

        # Verify count
        with sqlite3.connect(repository.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM eco_priors")
            count = cursor.fetchone()[0]
            assert count == 3, f"Expected 3 priors, found {count}"

    def test_step_2_store_with_provenance(
        self,
        repository: SQLitePriorRepository,
        sample_eco_effectiveness: ECOEffectiveness
    ):
        """Step 2: Store ECO prior with provenance information"""
        provenance = PriorProvenance(
            source_study_id="nangate45_study_001",
            export_timestamp="2026-01-13T12:00:00Z",
            source_study_snapshot_hash="sha256:abc123",
            export_metadata={"project": "test_project"},
        )

        repository.store_prior(sample_eco_effectiveness, provenance)

        # Verify provenance was stored
        with sqlite3.connect(repository.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT provenance_json FROM eco_priors WHERE eco_name = ?",
                (sample_eco_effectiveness.eco_name,)
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["provenance_json"] is not None

            prov_data = json.loads(row["provenance_json"])
            assert prov_data["source_study_id"] == "nangate45_study_001"
            assert prov_data["export_timestamp"] == "2026-01-13T12:00:00Z"

    def test_step_3_priors_db_file_is_created(self, temp_db_path: Path):
        """Step 3: Verify priors.db file is created"""
        # Initialize repository
        repository = SQLitePriorRepository(db_path=temp_db_path)

        # Verify file exists
        assert temp_db_path.exists(), "Database file not created"
        assert temp_db_path.is_file(), "Database path is not a file"

        # Verify it's a valid SQLite database
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            assert version is not None, "Not a valid SQLite database"

    def test_step_3_database_file_persists_after_closing(
        self,
        temp_db_path: Path,
        sample_eco_effectiveness: ECOEffectiveness
    ):
        """Step 3: Verify database file persists after repository is closed"""
        # Create repository and store data
        repository = SQLitePriorRepository(db_path=temp_db_path)
        repository.store_prior(sample_eco_effectiveness)

        # Delete repository object
        del repository

        # Verify file still exists
        assert temp_db_path.exists(), "Database file deleted after repository closed"

        # Verify data is still there
        with sqlite3.connect(temp_db_path) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM eco_priors WHERE eco_name = ?",
                (sample_eco_effectiveness.eco_name,)
            )
            count = cursor.fetchone()[0]
            assert count == 1, "Data lost after repository closed"

    def test_step_4_query_priors_from_database(
        self,
        repository: SQLitePriorRepository,
        sample_eco_effectiveness: ECOEffectiveness
    ):
        """Step 4: Query priors from database"""
        # Store prior
        repository.store_prior(sample_eco_effectiveness)

        # Query it back
        retrieved = repository.get_prior("CellResizeECO")

        assert retrieved is not None, "Prior not found"
        assert retrieved.eco_name == sample_eco_effectiveness.eco_name
        assert retrieved.total_applications == sample_eco_effectiveness.total_applications
        assert retrieved.successful_applications == sample_eco_effectiveness.successful_applications
        assert retrieved.average_wns_improvement_ps == sample_eco_effectiveness.average_wns_improvement_ps
        assert retrieved.prior == sample_eco_effectiveness.prior

    def test_step_4_query_nonexistent_prior_returns_none(
        self,
        repository: SQLitePriorRepository
    ):
        """Step 4: Query for nonexistent prior returns None"""
        result = repository.get_prior("NonexistentECO")
        assert result is None, "Should return None for nonexistent prior"

    def test_step_4_query_all_priors(self, repository: SQLitePriorRepository):
        """Step 4: Query all priors from database"""
        # Store multiple priors
        eco1 = ECOEffectiveness(
            eco_name="ECO1", total_applications=10, successful_applications=8,
            failed_applications=2, average_wns_improvement_ps=100,
            best_wns_improvement_ps=200, worst_wns_degradation_ps=-20,
            prior=ECOPrior.TRUSTED
        )
        eco2 = ECOEffectiveness(
            eco_name="ECO2", total_applications=20, successful_applications=15,
            failed_applications=5, average_wns_improvement_ps=150,
            best_wns_improvement_ps=300, worst_wns_degradation_ps=-30,
            prior=ECOPrior.MIXED
        )

        repository.store_prior(eco1)
        repository.store_prior(eco2)

        # Query all
        all_priors = repository.get_all_priors()

        assert len(all_priors) == 2, f"Expected 2 priors, got {len(all_priors)}"
        assert "ECO1" in all_priors
        assert "ECO2" in all_priors

    def test_step_4_query_by_success_rate(self, repository: SQLitePriorRepository):
        """Step 4: Query priors filtered by success rate"""
        # Store priors with different success rates
        high_success = ECOEffectiveness(
            eco_name="HighSuccessECO",
            total_applications=100,
            successful_applications=90,  # 90% success
            failed_applications=10,
            average_wns_improvement_ps=200,
            best_wns_improvement_ps=400,
            worst_wns_degradation_ps=-10,
            prior=ECOPrior.TRUSTED,
        )

        low_success = ECOEffectiveness(
            eco_name="LowSuccessECO",
            total_applications=100,
            successful_applications=40,  # 40% success
            failed_applications=60,
            average_wns_improvement_ps=50,
            best_wns_improvement_ps=100,
            worst_wns_degradation_ps=-200,
            prior=ECOPrior.SUSPICIOUS,
        )

        repository.store_prior(high_success)
        repository.store_prior(low_success)

        # Query for ECOs with >70% success rate
        high_performers = repository.query_by_success_rate(
            min_success_rate=0.7,
            min_applications=10
        )

        assert len(high_performers) == 1, "Should find only high success ECO"
        assert "HighSuccessECO" in high_performers
        assert "LowSuccessECO" not in high_performers

    def test_step_5_data_integrity_across_sessions(
        self,
        temp_db_path: Path,
        sample_eco_effectiveness: ECOEffectiveness
    ):
        """Step 5: Verify data integrity across sessions"""
        # Session 1: Store data
        repository1 = SQLitePriorRepository(db_path=temp_db_path)
        repository1.store_prior(sample_eco_effectiveness)
        del repository1

        # Session 2: Retrieve data
        repository2 = SQLitePriorRepository(db_path=temp_db_path)
        retrieved = repository2.get_prior(sample_eco_effectiveness.eco_name)

        assert retrieved is not None, "Data lost across sessions"
        assert retrieved.eco_name == sample_eco_effectiveness.eco_name
        assert retrieved.total_applications == sample_eco_effectiveness.total_applications
        assert retrieved.successful_applications == sample_eco_effectiveness.successful_applications
        assert retrieved.average_wns_improvement_ps == sample_eco_effectiveness.average_wns_improvement_ps

    def test_step_5_update_existing_prior_maintains_integrity(
        self,
        repository: SQLitePriorRepository,
        sample_eco_effectiveness: ECOEffectiveness
    ):
        """Step 5: Updating a prior maintains data integrity"""
        # Store initial prior
        repository.store_prior(sample_eco_effectiveness)

        # Update with new data
        updated = ECOEffectiveness(
            eco_name=sample_eco_effectiveness.eco_name,
            total_applications=150,  # Updated
            successful_applications=120,  # Updated
            failed_applications=30,
            average_wns_improvement_ps=180,  # Updated
            best_wns_improvement_ps=600,
            worst_wns_degradation_ps=-40,
            prior=ECOPrior.TRUSTED,
        )

        repository.store_prior(updated)

        # Verify update
        retrieved = repository.get_prior(sample_eco_effectiveness.eco_name)
        assert retrieved.total_applications == 150
        assert retrieved.successful_applications == 120
        assert retrieved.average_wns_improvement_ps == 180

        # Verify only one entry exists (not duplicated)
        all_priors = repository.get_all_priors()
        assert len(all_priors) == 1, "Prior was duplicated instead of updated"


class TestF090PriorRepositoryIntegration:
    """Integration tests for prior repository"""

    @pytest.fixture
    def temp_db_path(self, tmp_path: Path) -> Path:
        """Create a temporary database path for testing."""
        return tmp_path / "integration_priors.db"

    @pytest.fixture
    def repository(self, temp_db_path: Path) -> SQLitePriorRepository:
        """Create a SQLite prior repository for testing."""
        return SQLitePriorRepository(db_path=temp_db_path)

    def test_import_from_json_file(
        self,
        repository: SQLitePriorRepository,
        tmp_path: Path
    ):
        """Test importing priors from JSON file"""
        # Create JSON file with prior data
        json_data = {
            "eco_priors": {
                "ECO1": {
                    "eco_name": "ECO1",
                    "total_applications": 50,
                    "successful_applications": 40,
                    "failed_applications": 10,
                    "average_wns_improvement_ps": 120,
                    "best_wns_improvement_ps": 300,
                    "worst_wns_degradation_ps": -50,
                    "prior": "trusted"
                },
                "ECO2": {
                    "eco_name": "ECO2",
                    "total_applications": 30,
                    "successful_applications": 20,
                    "failed_applications": 10,
                    "average_wns_improvement_ps": 80,
                    "best_wns_improvement_ps": 200,
                    "worst_wns_degradation_ps": -30,
                    "prior": "mixed"
                }
            },
            "provenance": None,
            "repository_metadata": {}
        }

        json_path = tmp_path / "test_priors.json"
        with open(json_path, "w") as f:
            json.dump(json_data, f)

        # Import
        count = repository.import_from_json(json_path)
        assert count == 2, f"Expected to import 2 priors, imported {count}"

        # Verify data
        eco1 = repository.get_prior("ECO1")
        assert eco1 is not None
        assert eco1.total_applications == 50

    def test_export_to_json_file(
        self,
        repository: SQLitePriorRepository,
        tmp_path: Path
    ):
        """Test exporting priors to JSON file"""
        # Store some priors
        eco1 = ECOEffectiveness(
            eco_name="ExportECO1", total_applications=25, successful_applications=20,
            failed_applications=5, average_wns_improvement_ps=110,
            best_wns_improvement_ps=250, worst_wns_degradation_ps=-25,
            prior=ECOPrior.TRUSTED
        )
        repository.store_prior(eco1)

        # Export
        json_path = tmp_path / "exported_priors.json"
        repository.export_to_json(json_path)

        # Verify file was created
        assert json_path.exists()

        # Verify content
        with open(json_path) as f:
            data = json.load(f)

        assert "eco_priors" in data
        assert "ExportECO1" in data["eco_priors"]
        assert data["eco_priors"]["ExportECO1"]["total_applications"] == 25

    def test_get_repository_statistics(self, repository: SQLitePriorRepository):
        """Test repository statistics"""
        # Store multiple priors
        for i in range(5):
            eco = ECOEffectiveness(
                eco_name=f"ECO{i}",
                total_applications=10 * (i + 1),
                successful_applications=8 * (i + 1),
                failed_applications=2 * (i + 1),
                average_wns_improvement_ps=100 + i * 10,
                best_wns_improvement_ps=200 + i * 20,
                worst_wns_degradation_ps=-20 - i * 5,
                prior=ECOPrior.TRUSTED,
            )
            repository.store_prior(eco)

        # Get statistics
        stats = repository.get_statistics()

        assert stats["total_ecos"] == 5
        assert stats["total_applications"] == 10 + 20 + 30 + 40 + 50  # Sum of all
        assert stats["total_successful"] == 8 + 16 + 24 + 32 + 40
        assert "average_success_rate" in stats
        assert "database_path" in stats

    def test_clear_repository(self, repository: SQLitePriorRepository):
        """Test clearing all priors from repository"""
        # Store some priors
        eco = ECOEffectiveness(
            eco_name="TempECO", total_applications=10, successful_applications=8,
            failed_applications=2, average_wns_improvement_ps=100,
            best_wns_improvement_ps=200, worst_wns_degradation_ps=-20,
            prior=ECOPrior.TRUSTED
        )
        repository.store_prior(eco)

        # Verify it's there
        assert repository.get_prior("TempECO") is not None

        # Clear
        repository.clear()

        # Verify it's gone
        assert repository.get_prior("TempECO") is None
        all_priors = repository.get_all_priors()
        assert len(all_priors) == 0, "Repository not cleared"
