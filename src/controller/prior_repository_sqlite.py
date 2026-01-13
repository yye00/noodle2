"""SQLite-backed prior repository for cross-project ECO prior persistence.

This module extends the PriorRepository with SQLite database persistence,
enabling ECO priors to be shared across projects and sessions.
"""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .eco import ECOEffectiveness, ECOPrior
from .prior_sharing import PriorProvenance, PriorRepository


class SQLitePriorRepository:
    """SQLite-backed repository for persisting ECO priors across sessions.

    This repository stores ECO effectiveness data in a SQLite database,
    enabling:
    - Cross-project prior sharing
    - Historical prior tracking
    - Query-based prior retrieval
    - Persistent storage across sessions

    Database Schema:
        eco_priors:
            - eco_name TEXT PRIMARY KEY
            - total_applications INTEGER
            - successful_applications INTEGER
            - failed_applications INTEGER
            - average_wns_improvement_ps REAL
            - best_wns_improvement_ps REAL
            - worst_wns_degradation_ps REAL
            - prior TEXT
            - last_updated TEXT
            - provenance_json TEXT
    """

    def __init__(self, db_path: Path | str | None = None):
        """Initialize SQLite prior repository.

        Args:
            db_path: Path to SQLite database file.
                    If None, uses ~/.noodle2/priors/priors.db
        """
        if db_path is None:
            db_path = Path.home() / ".noodle2" / "priors" / "priors.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eco_priors (
                    eco_name TEXT PRIMARY KEY,
                    total_applications INTEGER NOT NULL DEFAULT 0,
                    successful_applications INTEGER NOT NULL DEFAULT 0,
                    failed_applications INTEGER NOT NULL DEFAULT 0,
                    average_wns_improvement_ps REAL NOT NULL DEFAULT 0.0,
                    best_wns_improvement_ps REAL NOT NULL DEFAULT 0.0,
                    worst_wns_degradation_ps REAL NOT NULL DEFAULT 0.0,
                    prior TEXT NOT NULL DEFAULT 'unknown',
                    last_updated TEXT NOT NULL,
                    provenance_json TEXT
                )
            """)

            # Create index on last_updated for temporal queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_updated
                ON eco_priors(last_updated)
            """)

            conn.commit()

    def store_prior(
        self,
        effectiveness: ECOEffectiveness,
        provenance: PriorProvenance | None = None
    ) -> None:
        """Store or update an ECO prior in the database.

        Args:
            effectiveness: ECO effectiveness data to store
            provenance: Optional provenance information
        """
        provenance_json = None
        if provenance:
            provenance_json = json.dumps(provenance.to_dict())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO eco_priors (
                    eco_name,
                    total_applications,
                    successful_applications,
                    failed_applications,
                    average_wns_improvement_ps,
                    best_wns_improvement_ps,
                    worst_wns_degradation_ps,
                    prior,
                    last_updated,
                    provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                effectiveness.eco_name,
                effectiveness.total_applications,
                effectiveness.successful_applications,
                effectiveness.failed_applications,
                effectiveness.average_wns_improvement_ps,
                effectiveness.best_wns_improvement_ps,
                effectiveness.worst_wns_degradation_ps,
                effectiveness.prior.value,
                datetime.now(UTC).isoformat(),
                provenance_json,
            ))
            conn.commit()

    def get_prior(self, eco_name: str) -> ECOEffectiveness | None:
        """Retrieve an ECO prior from the database.

        Args:
            eco_name: Name of the ECO to retrieve

        Returns:
            ECOEffectiveness if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM eco_priors WHERE eco_name = ?
            """, (eco_name,))

            row = cursor.fetchone()
            if row is None:
                return None

            return ECOEffectiveness(
                eco_name=row["eco_name"],
                total_applications=row["total_applications"],
                successful_applications=row["successful_applications"],
                failed_applications=row["failed_applications"],
                average_wns_improvement_ps=row["average_wns_improvement_ps"],
                best_wns_improvement_ps=row["best_wns_improvement_ps"],
                worst_wns_degradation_ps=row["worst_wns_degradation_ps"],
                prior=ECOPrior(row["prior"]),
            )

    def get_all_priors(self) -> dict[str, ECOEffectiveness]:
        """Retrieve all ECO priors from the database.

        Returns:
            Dictionary mapping ECO names to effectiveness data
        """
        priors = {}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM eco_priors")

            for row in cursor:
                effectiveness = ECOEffectiveness(
                    eco_name=row["eco_name"],
                    total_applications=row["total_applications"],
                    successful_applications=row["successful_applications"],
                    failed_applications=row["failed_applications"],
                    average_wns_improvement_ps=row["average_wns_improvement_ps"],
                    best_wns_improvement_ps=row["best_wns_improvement_ps"],
                    worst_wns_degradation_ps=row["worst_wns_degradation_ps"],
                    prior=ECOPrior(row["prior"]),
                )
                priors[effectiveness.eco_name] = effectiveness

        return priors

    def import_from_json(self, json_path: Path) -> int:
        """Import priors from a JSON file into the database.

        Args:
            json_path: Path to JSON file containing prior repository

        Returns:
            Number of priors imported
        """
        with open(json_path) as f:
            data = json.load(f)

        repository = PriorRepository.from_dict(data)

        count = 0
        for eco_name, effectiveness in repository.eco_priors.items():
            self.store_prior(effectiveness, repository.provenance)
            count += 1

        return count

    def export_to_json(self, json_path: Path) -> None:
        """Export all priors from database to a JSON file.

        Args:
            json_path: Path to write JSON file
        """
        priors = self.get_all_priors()

        repository = PriorRepository()
        for effectiveness in priors.values():
            repository.add_eco_prior(effectiveness)

        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(repository.to_dict(), f, indent=2)

    def query_by_success_rate(
        self,
        min_success_rate: float = 0.0,
        min_applications: int = 1
    ) -> dict[str, ECOEffectiveness]:
        """Query priors by success rate.

        Args:
            min_success_rate: Minimum success rate (0.0 to 1.0)
            min_applications: Minimum number of applications required

        Returns:
            Dictionary of ECO priors meeting the criteria
        """
        priors = {}

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM eco_priors
                WHERE total_applications >= ?
                AND (CAST(successful_applications AS REAL) / total_applications) >= ?
            """, (min_applications, min_success_rate))

            for row in cursor:
                effectiveness = ECOEffectiveness(
                    eco_name=row["eco_name"],
                    total_applications=row["total_applications"],
                    successful_applications=row["successful_applications"],
                    failed_applications=row["failed_applications"],
                    average_wns_improvement_ps=row["average_wns_improvement_ps"],
                    best_wns_improvement_ps=row["best_wns_improvement_ps"],
                    worst_wns_degradation_ps=row["worst_wns_degradation_ps"],
                    prior=ECOPrior(row["prior"]),
                )
                priors[effectiveness.eco_name] = effectiveness

        return priors

    def get_statistics(self) -> dict[str, Any]:
        """Get repository statistics.

        Returns:
            Dictionary with repository statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_ecos,
                    SUM(total_applications) as total_applications,
                    SUM(successful_applications) as total_successful,
                    SUM(failed_applications) as total_failed,
                    AVG(CAST(successful_applications AS REAL) /
                        NULLIF(total_applications, 0)) as avg_success_rate,
                    MIN(last_updated) as oldest_update,
                    MAX(last_updated) as newest_update
                FROM eco_priors
            """)

            row = cursor.fetchone()

            return {
                "total_ecos": row[0] or 0,
                "total_applications": row[1] or 0,
                "total_successful": row[2] or 0,
                "total_failed": row[3] or 0,
                "average_success_rate": row[4] or 0.0,
                "oldest_update": row[5],
                "newest_update": row[6],
                "database_path": str(self.db_path),
            }

    def clear(self) -> None:
        """Clear all priors from the database.

        WARNING: This is a destructive operation.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM eco_priors")
            conn.commit()
