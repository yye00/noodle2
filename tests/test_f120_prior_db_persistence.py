"""
Test F120: Prior repository database file exists at ~/.noodle2/priors/priors.db after demo

This test validates that:
1. Demo execution creates the prior repository database
2. The database is a valid SQLite file
3. ECO priors are persisted and can be queried
4. Priors persist across demo runs
5. Database file exists at the correct location

Feature Steps:
1. Run demo to completion
2. Check if ~/.noodle2/priors/priors.db file exists
3. Verify file is a valid SQLite database
4. Query database to verify ECO prior records exist
5. Verify priors persist across demo runs
"""

import json
import os
import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from src.controller.prior_repository_sqlite import SQLitePriorRepository


class TestF120PriorDatabasePersistence:
    """Test F120: Prior repository database file exists after demo"""

    @pytest.fixture
    def priors_db_path(self) -> Path:
        """Get the path to the priors database."""
        return Path.home() / ".noodle2" / "priors" / "priors.db"

    @pytest.fixture
    def backup_existing_db(self, priors_db_path: Path):
        """Backup existing database before test, restore after."""
        backup_path = None
        if priors_db_path.exists():
            backup_path = priors_db_path.with_suffix(".db.backup")
            shutil.copy(priors_db_path, backup_path)

        yield

        # Restore backup if it existed
        if backup_path and backup_path.exists():
            shutil.copy(backup_path, priors_db_path)
            backup_path.unlink()

    def test_step_1_run_demo_to_completion(self, backup_existing_db):
        """
        Step 1: Run demo to completion

        This test runs the nangate45 extreme demo which should
        create and populate the prior repository database.
        """
        # Run demo (this may take a while)
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )

        # Verify demo completed successfully
        assert result.returncode == 0, (
            f"Demo failed with exit code {result.returncode}\n"
            f"STDERR: {result.stderr[-1000:]}\n"
            f"STDOUT: {result.stdout[-1000:]}"
        )

        # Verify demo output directory was created
        demo_output = Path("demo_output/nangate45_extreme_demo")
        assert demo_output.exists(), "Demo output directory not created"

        # Verify summary.json exists
        summary_path = demo_output / "summary.json"
        assert summary_path.exists(), "summary.json not created"

        print("\n✓ Demo completed successfully")

    def test_step_2_verify_database_file_exists(self, priors_db_path: Path, backup_existing_db):
        """
        Step 2: Check if ~/.noodle2/priors/priors.db file exists

        The database should be automatically created when the StudyExecutor
        initializes its SQLitePriorRepository.
        """
        # Run demo to ensure database is created
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        # Verify database file exists at correct location
        assert priors_db_path.exists(), (
            f"Prior repository database not found at: {priors_db_path}\n"
            f"Expected location: ~/.noodle2/priors/priors.db"
        )

        # Verify parent directory was created
        assert priors_db_path.parent.exists(), (
            f"Priors directory not created: {priors_db_path.parent}"
        )

        # Verify it's a file (not a directory)
        assert priors_db_path.is_file(), (
            f"Database path exists but is not a file: {priors_db_path}"
        )

        # Verify file has reasonable size (not empty, not too large)
        file_size = priors_db_path.stat().st_size
        assert file_size > 0, "Database file is empty"
        assert file_size < 100_000_000, f"Database file is suspiciously large: {file_size} bytes"

        print(f"\n✓ Database file exists at: {priors_db_path}")
        print(f"  File size: {file_size:,} bytes")

    def test_step_3_verify_valid_sqlite_database(self, priors_db_path: Path, backup_existing_db):
        """
        Step 3: Verify file is a valid SQLite database

        Test that the database file is a valid SQLite database with
        the correct schema.
        """
        # Run demo to create database
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        assert priors_db_path.exists(), "Database file not found"

        # Try to connect to the database
        try:
            conn = sqlite3.connect(priors_db_path)
            cursor = conn.cursor()

            # Verify table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='eco_priors'
            """)
            tables = cursor.fetchall()
            assert len(tables) == 1, "eco_priors table not found"

            # Verify table schema
            cursor.execute("PRAGMA table_info(eco_priors)")
            columns = cursor.fetchall()
            column_names = [col[1] for col in columns]

            expected_columns = [
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
            ]

            for expected_col in expected_columns:
                assert expected_col in column_names, (
                    f"Missing column: {expected_col}\n"
                    f"Found columns: {column_names}"
                )

            # Verify index exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='index' AND name='idx_last_updated'
            """)
            indexes = cursor.fetchall()
            assert len(indexes) == 1, "idx_last_updated index not found"

            conn.close()

            print("\n✓ Database is valid SQLite with correct schema")
            print(f"  Columns: {len(column_names)}")
            print(f"  Indexes: {len(indexes)}")

        except sqlite3.Error as e:
            pytest.fail(f"Database is not a valid SQLite file: {e}")

    def test_step_4_verify_eco_prior_records_exist(self, priors_db_path: Path, backup_existing_db):
        """
        Step 4: Query database to verify ECO prior records exist

        After running the demo, the database should contain ECO prior
        records from the executed trials.
        """
        # Run demo to populate database
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        assert priors_db_path.exists(), "Database file not found"

        # Query database using SQLitePriorRepository
        repository = SQLitePriorRepository(db_path=priors_db_path)

        # Get all priors
        all_priors = repository.get_all_priors()

        # Verify we have some priors
        assert len(all_priors) > 0, (
            "No ECO priors found in database after demo run\n"
            "Demo should have created and tracked ECO effectiveness data"
        )

        print(f"\n✓ Found {len(all_priors)} ECO priors in database")

        # Verify each prior has expected data
        for eco_name, effectiveness in all_priors.items():
            print(f"  {eco_name}:")
            print(f"    Applications: {effectiveness.total_applications}")
            print(f"    Success: {effectiveness.successful_applications}")
            print(f"    Failures: {effectiveness.failed_applications}")
            print(f"    Success rate: {effectiveness.success_rate:.1%}")
            print(f"    Prior state: {effectiveness.prior.value}")

            # Verify data is reasonable
            assert effectiveness.total_applications > 0, (
                f"ECO {eco_name} has 0 applications"
            )
            assert effectiveness.total_applications == (
                effectiveness.successful_applications + effectiveness.failed_applications
            ), f"Application counts don't match for {eco_name}"

        # Verify we can query by success rate
        high_success_priors = repository.query_by_success_rate(
            min_success_rate=0.5,
            min_applications=1,
        )
        print(f"\n✓ Found {len(high_success_priors)} high-success ECOs (>50% success rate)")

    def test_step_5_verify_priors_persist_across_runs(self, priors_db_path: Path, backup_existing_db):
        """
        Step 5: Verify priors persist across demo runs

        Run the demo twice and verify that:
        1. Priors from first run are preserved
        2. Priors are updated (not replaced) on second run
        3. Application counts accumulate correctly
        """
        # Clear database before test
        if priors_db_path.exists():
            priors_db_path.unlink()

        # Run demo first time
        print("\n--- Running demo first time ---")
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        repository = SQLitePriorRepository(db_path=priors_db_path)
        priors_after_first_run = repository.get_all_priors()

        assert len(priors_after_first_run) > 0, "No priors after first run"

        # Get statistics from first run
        stats_first_run = repository.get_statistics()
        total_apps_first = stats_first_run["total_applications"]

        print(f"After first run: {len(priors_after_first_run)} ECOs, {total_apps_first} applications")

        # Run demo second time
        print("\n--- Running demo second time ---")
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        # Check priors after second run
        priors_after_second_run = repository.get_all_priors()
        stats_second_run = repository.get_statistics()
        total_apps_second = stats_second_run["total_applications"]

        print(f"After second run: {len(priors_after_second_run)} ECOs, {total_apps_second} applications")

        # Verify priors were updated, not replaced
        assert len(priors_after_second_run) >= len(priors_after_first_run), (
            "Priors decreased after second run - data was lost"
        )

        # Verify application counts increased
        assert total_apps_second > total_apps_first, (
            f"Application counts did not increase after second run\n"
            f"First run: {total_apps_first}\n"
            f"Second run: {total_apps_second}\n"
            f"Priors should accumulate across runs"
        )

        # Verify individual ECO counts increased or stayed the same
        for eco_name, first_effectiveness in priors_after_first_run.items():
            if eco_name in priors_after_second_run:
                second_effectiveness = priors_after_second_run[eco_name]
                assert second_effectiveness.total_applications >= first_effectiveness.total_applications, (
                    f"ECO {eco_name} application count decreased:\n"
                    f"First run: {first_effectiveness.total_applications}\n"
                    f"Second run: {second_effectiveness.total_applications}"
                )

        print("\n✓ Priors persist and accumulate correctly across demo runs")


class TestF120IntegrationWithExecutor:
    """Integration tests for prior persistence in StudyExecutor"""

    def test_executor_creates_prior_repository_on_init(self):
        """Verify that StudyExecutor initializes SQLitePriorRepository"""
        from src.controller.demo_study import create_nangate45_extreme_demo_study
        from src.controller.executor import StudyExecutor

        study_config = create_nangate45_extreme_demo_study()

        executor = StudyExecutor(
            config=study_config,
            artifacts_root="test_outputs/artifacts",
            telemetry_root="test_outputs/telemetry",
            skip_base_case_verification=True,
        )

        # Verify prior_repository exists
        assert hasattr(executor, "prior_repository"), (
            "StudyExecutor does not have prior_repository attribute"
        )

        assert isinstance(executor.prior_repository, SQLitePriorRepository), (
            f"prior_repository is not SQLitePriorRepository: {type(executor.prior_repository)}"
        )

        # Verify database path is correct
        expected_path = Path.home() / ".noodle2" / "priors" / "priors.db"
        assert executor.prior_repository.db_path == expected_path, (
            f"Database path incorrect:\n"
            f"Expected: {expected_path}\n"
            f"Actual: {executor.prior_repository.db_path}"
        )

        print("\n✓ StudyExecutor initializes SQLitePriorRepository correctly")

    def test_prior_repository_stores_eco_effectiveness(self, tmp_path):
        """Verify that ECOEffectiveness can be stored and retrieved"""
        from src.controller.eco import ECOEffectiveness, ECOPrior

        # Create temporary database
        db_path = tmp_path / "test_priors.db"
        repository = SQLitePriorRepository(db_path=db_path)

        # Create test ECO effectiveness
        eco = ECOEffectiveness(eco_name="test_buffer_insertion")
        eco.update(success=True, wns_delta_ps=50.0)
        eco.update(success=True, wns_delta_ps=60.0)
        eco.update(success=False, wns_delta_ps=-20.0)

        # Store to database
        repository.store_prior(eco)

        # Retrieve from database
        retrieved = repository.get_prior("test_buffer_insertion")

        assert retrieved is not None, "Failed to retrieve stored prior"
        assert retrieved.eco_name == "test_buffer_insertion"
        assert retrieved.total_applications == 3
        assert retrieved.successful_applications == 2
        assert retrieved.failed_applications == 1
        # 2/3 = 66.7% success -> MIXED (requires >= 0.8 for TRUSTED)
        assert retrieved.prior == ECOPrior.MIXED

        print("\n✓ ECOEffectiveness stores and retrieves correctly")

    def test_database_statistics_after_demo(self):
        """Verify database statistics are reasonable after demo"""
        # Run demo
        subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            timeout=1800,
        )

        db_path = Path.home() / ".noodle2" / "priors" / "priors.db"
        repository = SQLitePriorRepository(db_path=db_path)

        stats = repository.get_statistics()

        # Verify statistics are reasonable
        assert stats["total_ecos"] > 0, "No ECOs tracked"
        assert stats["total_applications"] > 0, "No applications tracked"
        assert 0 <= stats["average_success_rate"] <= 1, (
            f"Invalid success rate: {stats['average_success_rate']}"
        )
        assert stats["database_path"] == str(db_path)

        print("\n✓ Database statistics:")
        print(f"  Total ECOs: {stats['total_ecos']}")
        print(f"  Total applications: {stats['total_applications']}")
        print(f"  Average success rate: {stats['average_success_rate']:.1%}")
        print(f"  Oldest update: {stats['oldest_update']}")
        print(f"  Newest update: {stats['newest_update']}")
