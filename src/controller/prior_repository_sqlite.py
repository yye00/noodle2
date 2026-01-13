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

            # Table for multi-project priors with weights
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eco_priors_multi (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eco_name TEXT NOT NULL,
                    total_applications INTEGER NOT NULL DEFAULT 0,
                    successful_applications INTEGER NOT NULL DEFAULT 0,
                    failed_applications INTEGER NOT NULL DEFAULT 0,
                    average_wns_improvement_ps REAL NOT NULL DEFAULT 0.0,
                    best_wns_improvement_ps REAL NOT NULL DEFAULT 0.0,
                    worst_wns_degradation_ps REAL NOT NULL DEFAULT 0.0,
                    prior TEXT NOT NULL DEFAULT 'unknown',
                    weight REAL NOT NULL DEFAULT 1.0,
                    import_timestamp TEXT NOT NULL,
                    provenance_json TEXT
                )
            """)

            # Create index on eco_name for multi-project queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_multi_eco_name
                ON eco_priors_multi(eco_name)
            """)

            # Table for decay configuration
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decay_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            # Table for tracking ECO failures with context
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eco_failures (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eco_name TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    reason TEXT,
                    timestamp TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_failures_eco_name
                ON eco_failures(eco_name)
            """)

            # Table for tracking ECO successes with context
            conn.execute("""
                CREATE TABLE IF NOT EXISTS eco_successes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eco_name TEXT NOT NULL,
                    context_json TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_successes_eco_name
                ON eco_successes(eco_name)
            """)

            # Table for anti-patterns
            conn.execute("""
                CREATE TABLE IF NOT EXISTS anti_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    eco_name TEXT NOT NULL,
                    context_pattern_json TEXT NOT NULL,
                    failure_rate REAL NOT NULL,
                    failure_count INTEGER NOT NULL,
                    success_count INTEGER NOT NULL,
                    description TEXT,
                    recommendation TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(eco_name, context_pattern_json)
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_anti_patterns_eco_name
                ON anti_patterns(eco_name)
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

        # Import anti-patterns if present
        if "anti_patterns" in data:
            for pattern in data["anti_patterns"]:
                self.store_anti_pattern(
                    eco_name=pattern["eco_name"],
                    context_pattern=pattern["context_pattern"],
                    failure_rate=pattern["failure_rate"],
                    failure_count=pattern["failure_count"],
                    success_count=pattern["success_count"],
                    description=pattern.get("description"),
                    recommendation=pattern.get("recommendation"),
                )

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

        # Convert to dict and add anti-patterns
        data = repository.to_dict()
        data["anti_patterns"] = self.get_anti_patterns()

        json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)

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
            conn.execute("DELETE FROM eco_priors_multi")
            conn.commit()

    def import_prior_with_weight(
        self,
        effectiveness: ECOEffectiveness,
        provenance: PriorProvenance,
        weight: float = 1.0
    ) -> None:
        """Import a prior from another project with an assigned weight.

        This allows multiple priors for the same ECO to be stored and
        aggregated with different weights.

        Args:
            effectiveness: ECO effectiveness data
            provenance: Provenance information for tracking source
            weight: Weight for this prior (default: 1.0)
        """
        provenance_json = json.dumps(provenance.to_dict())

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO eco_priors_multi (
                    eco_name,
                    total_applications,
                    successful_applications,
                    failed_applications,
                    average_wns_improvement_ps,
                    best_wns_improvement_ps,
                    worst_wns_degradation_ps,
                    prior,
                    weight,
                    import_timestamp,
                    provenance_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                effectiveness.eco_name,
                effectiveness.total_applications,
                effectiveness.successful_applications,
                effectiveness.failed_applications,
                effectiveness.average_wns_improvement_ps,
                effectiveness.best_wns_improvement_ps,
                effectiveness.worst_wns_degradation_ps,
                effectiveness.prior.value,
                weight,
                datetime.now(UTC).isoformat(),
                provenance_json,
            ))
            conn.commit()

    def get_all_priors_with_weights(self, eco_name: str) -> list[dict[str, Any]]:
        """Get all priors for an ECO with their weights.

        Args:
            eco_name: Name of the ECO

        Returns:
            List of dictionaries containing effectiveness, weight, and provenance
        """
        priors = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM eco_priors_multi WHERE eco_name = ?
            """, (eco_name,))

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

                provenance_data = json.loads(row["provenance_json"]) if row["provenance_json"] else {}
                provenance = PriorProvenance(
                    source_study_id=provenance_data.get("source_study_id", "unknown"),
                    export_timestamp=provenance_data.get("export_timestamp", ""),
                    source_study_snapshot_hash=provenance_data.get("source_study_snapshot_hash"),
                    export_metadata=provenance_data.get("export_metadata", {}),
                )

                priors.append({
                    "effectiveness": effectiveness,
                    "weight": row["weight"],
                    "provenance": provenance_data,
                    "import_timestamp": row["import_timestamp"],
                })

        return priors

    def configure_decay(self, half_life_days: int) -> None:
        """Configure time-based decay for priors.

        Args:
            half_life_days: Number of days for prior weight to decay to half
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO decay_config (key, value)
                VALUES ('half_life_days', ?)
            """, (str(half_life_days),))
            conn.commit()

    def get_decay_config(self) -> dict[str, int] | None:
        """Get current decay configuration.

        Returns:
            Dictionary with decay configuration or None if not configured
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT value FROM decay_config WHERE key = 'half_life_days'
            """)
            row = cursor.fetchone()

            if row:
                return {"half_life_days": int(row[0])}
            return None

    def get_all_priors_with_decay(self, eco_name: str) -> list[dict[str, Any]]:
        """Get all priors for an ECO with decay applied to weights.

        Args:
            eco_name: Name of the ECO

        Returns:
            List of dictionaries with effective_weight after decay
        """
        priors = self.get_all_priors_with_weights(eco_name)
        decay_config = self.get_decay_config()

        if decay_config is None:
            # No decay configured, return priors with effective_weight = weight
            for prior in priors:
                prior["effective_weight"] = prior["weight"]
            return priors

        half_life_days = decay_config["half_life_days"]
        now = datetime.now(UTC)

        for prior in priors:
            # Parse the import timestamp
            import_time = datetime.fromisoformat(prior["provenance"]["export_timestamp"].replace("Z", "+00:00"))
            age_days = (now - import_time).total_seconds() / 86400

            # Calculate decay factor: weight * (0.5 ** (age_days / half_life_days))
            decay_factor = 0.5 ** (age_days / half_life_days)
            prior["effective_weight"] = prior["weight"] * decay_factor

        return priors

    def get_aggregated_prior(self, eco_name: str) -> ECOEffectiveness | None:
        """Get aggregated prior for an ECO with weighted averaging.

        Applies decay if configured.

        Args:
            eco_name: Name of the ECO

        Returns:
            Aggregated ECO effectiveness or None if no priors exist
        """
        priors = self.get_all_priors_with_decay(eco_name)

        if not priors:
            return None

        # Calculate weighted averages
        total_weight = sum(p["effective_weight"] for p in priors)
        if total_weight == 0:
            return None

        weighted_avg_wns = sum(
            p["effectiveness"].average_wns_improvement_ps * p["effective_weight"]
            for p in priors
        ) / total_weight

        weighted_best_wns = max(p["effectiveness"].best_wns_improvement_ps for p in priors)
        weighted_worst_wns = min(p["effectiveness"].worst_wns_degradation_ps for p in priors)

        total_applications = sum(p["effectiveness"].total_applications for p in priors)
        total_successful = sum(p["effectiveness"].successful_applications for p in priors)
        total_failed = sum(p["effectiveness"].failed_applications for p in priors)

        # Determine aggregated prior based on success rate
        success_rate = total_successful / total_applications if total_applications > 0 else 0
        if success_rate >= 0.8:
            aggregated_prior = ECOPrior.TRUSTED
        elif success_rate >= 0.5:
            aggregated_prior = ECOPrior.MIXED
        elif success_rate >= 0.3:
            aggregated_prior = ECOPrior.SUSPICIOUS
        else:
            aggregated_prior = ECOPrior.BLACKLISTED

        return ECOEffectiveness(
            eco_name=eco_name,
            total_applications=total_applications,
            successful_applications=total_successful,
            failed_applications=total_failed,
            average_wns_improvement_ps=weighted_avg_wns,
            best_wns_improvement_ps=weighted_best_wns,
            worst_wns_degradation_ps=weighted_worst_wns,
            prior=aggregated_prior,
        )

    def track_failure(
        self,
        eco_name: str,
        context: dict[str, Any],
        reason: str | None = None
    ) -> None:
        """Track an ECO failure with context information.

        Args:
            eco_name: Name of the ECO that failed
            context: Context information (e.g., region type, utilization)
            reason: Optional reason for the failure
        """
        context_json = json.dumps(context, sort_keys=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO eco_failures (eco_name, context_json, reason, timestamp)
                VALUES (?, ?, ?, ?)
            """, (eco_name, context_json, reason, datetime.now(UTC).isoformat()))
            conn.commit()

    def track_success(
        self,
        eco_name: str,
        context: dict[str, Any]
    ) -> None:
        """Track an ECO success with context information.

        Args:
            eco_name: Name of the ECO that succeeded
            context: Context information
        """
        context_json = json.dumps(context, sort_keys=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO eco_successes (eco_name, context_json, timestamp)
                VALUES (?, ?, ?)
            """, (eco_name, context_json, datetime.now(UTC).isoformat()))
            conn.commit()

    def get_failures(self, eco_name: str) -> list[dict[str, Any]]:
        """Get all tracked failures for an ECO.

        Args:
            eco_name: Name of the ECO

        Returns:
            List of failure records with context and reason
        """
        failures = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM eco_failures WHERE eco_name = ?
            """, (eco_name,))

            for row in cursor:
                failures.append({
                    "eco_name": row["eco_name"],
                    "context": json.loads(row["context_json"]),
                    "reason": row["reason"],
                    "timestamp": row["timestamp"],
                })

        return failures

    def identify_anti_patterns(
        self,
        failure_threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """Identify anti-patterns based on failure rates.

        Analyzes tracked failures and successes to find patterns where
        certain ECO+context combinations fail frequently.

        Args:
            failure_threshold: Minimum failure rate to be considered anti-pattern

        Returns:
            List of identified anti-patterns
        """
        anti_patterns = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Get all ECO names with failures
            cursor = conn.execute("""
                SELECT DISTINCT eco_name FROM eco_failures
            """)
            eco_names = [row["eco_name"] for row in cursor]

            for eco_name in eco_names:
                # Get failure contexts
                failures_cursor = conn.execute("""
                    SELECT context_json FROM eco_failures WHERE eco_name = ?
                """, (eco_name,))
                failure_contexts = [json.loads(row["context_json"]) for row in failures_cursor]

                # Get success contexts
                successes_cursor = conn.execute("""
                    SELECT context_json FROM eco_successes WHERE eco_name = ?
                """, (eco_name,))
                success_contexts = [json.loads(row["context_json"]) for row in successes_cursor]

                # Analyze common patterns in failures
                if failure_contexts:
                    # Extract common keys from failure contexts
                    common_keys = set.intersection(
                        *[set(ctx.keys()) for ctx in failure_contexts]
                    ) if failure_contexts else set()

                    for key in common_keys:
                        # Check if this key has a common value in failures
                        values_in_failures = [ctx.get(key) for ctx in failure_contexts]
                        if values_in_failures:
                            # Count occurrences
                            from collections import Counter
                            value_counts = Counter(values_in_failures)
                            most_common_value = value_counts.most_common(1)[0][0] if value_counts else None

                            if most_common_value is not None:
                                # Count failures and successes with this pattern
                                pattern_failures = sum(
                                    1 for ctx in failure_contexts
                                    if ctx.get(key) == most_common_value
                                )
                                pattern_successes = sum(
                                    1 for ctx in success_contexts
                                    if ctx.get(key) == most_common_value
                                )

                                total = pattern_failures + pattern_successes
                                if total > 0:
                                    failure_rate = pattern_failures / total

                                    if failure_rate >= failure_threshold:
                                        anti_patterns.append({
                                            "eco_name": eco_name,
                                            "context_pattern": {key: most_common_value},
                                            "failure_rate": failure_rate,
                                            "failure_count": pattern_failures,
                                            "success_count": pattern_successes,
                                        })

        return anti_patterns

    def store_anti_pattern(
        self,
        eco_name: str,
        context_pattern: dict[str, Any],
        failure_rate: float,
        failure_count: int,
        success_count: int,
        description: str | None = None,
        recommendation: str | None = None
    ) -> None:
        """Store an identified anti-pattern.

        Args:
            eco_name: Name of the ECO
            context_pattern: Pattern of context that causes failures
            failure_rate: Failure rate for this pattern
            failure_count: Number of failures
            success_count: Number of successes
            description: Description of the anti-pattern
            recommendation: Recommendation to avoid the pattern
        """
        context_pattern_json = json.dumps(context_pattern, sort_keys=True)

        # Auto-generate recommendation if not provided
        if recommendation is None:
            pattern_str = ", ".join(f"{k}={v}" for k, v in context_pattern.items())
            recommendation = f"Avoid {eco_name} when {pattern_str} (failure rate: {failure_rate:.0%})"

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO anti_patterns (
                    eco_name,
                    context_pattern_json,
                    failure_rate,
                    failure_count,
                    success_count,
                    description,
                    recommendation,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                eco_name,
                context_pattern_json,
                failure_rate,
                failure_count,
                success_count,
                description,
                recommendation,
                datetime.now(UTC).isoformat(),
            ))
            conn.commit()

    def get_anti_patterns(self, eco_name: str | None = None) -> list[dict[str, Any]]:
        """Get stored anti-patterns.

        Args:
            eco_name: Optional ECO name to filter by

        Returns:
            List of anti-patterns
        """
        patterns = []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if eco_name:
                cursor = conn.execute("""
                    SELECT * FROM anti_patterns WHERE eco_name = ?
                    ORDER BY failure_rate DESC
                """, (eco_name,))
            else:
                cursor = conn.execute("""
                    SELECT * FROM anti_patterns
                    ORDER BY failure_rate DESC
                """)

            for row in cursor:
                patterns.append({
                    "eco_name": row["eco_name"],
                    "context_pattern": json.loads(row["context_pattern_json"]),
                    "failure_rate": row["failure_rate"],
                    "failure_count": row["failure_count"],
                    "success_count": row["success_count"],
                    "description": row["description"],
                    "recommendation": row["recommendation"],
                    "created_at": row["created_at"],
                })

        return patterns
