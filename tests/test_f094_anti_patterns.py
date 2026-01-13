"""Tests for F094: Prior repository tracks anti-patterns and failure modes."""

from pathlib import Path

import pytest
from controller.eco import ECOEffectiveness, ECOPrior
from controller.prior_repository_sqlite import SQLitePriorRepository
from controller.prior_sharing import PriorProvenance


class TestF094TrackECOFailuresWithContext:
    """Test Step 1: Track ECO failures with context (e.g., resize on congested region)."""

    def test_step_1_track_eco_failures_with_context(self, tmp_path: Path):
        """Step 1: Track ECO failures with context (e.g., resize on congested region)."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Track a failure with context
        repo.track_failure(
            eco_name="resize_buffer",
            context={
                "region": "congested",
                "utilization": 0.95,
                "hotspot": True,
            },
            reason="Resize caused overflow in high-utilization region",
        )

        # Verify failure is tracked
        failures = repo.get_failures("resize_buffer")
        assert len(failures) == 1
        assert failures[0]["eco_name"] == "resize_buffer"
        assert failures[0]["context"]["region"] == "congested"
        assert failures[0]["reason"] == "Resize caused overflow in high-utilization region"


class TestF094IdentifyAntiPattern:
    """Test Step 2: Identify anti-pattern when failure_rate > 0.7."""

    def test_step_2_identify_anti_pattern(self, tmp_path: Path):
        """Step 2: Identify anti-pattern when failure_rate > 0.7."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Track 8 failures and 2 successes (80% failure rate)
        for i in range(8):
            repo.track_failure(
                eco_name="resize_in_congested",
                context={"region": "congested", "utilization": 0.9},
                reason=f"Failure {i}: Overflow in congested region",
            )

        for i in range(2):
            repo.track_success(
                eco_name="resize_in_congested",
                context={"region": "congested", "utilization": 0.5},
            )

        # Identify anti-patterns
        anti_patterns = repo.identify_anti_patterns(failure_threshold=0.7)

        # Should have one or more anti-patterns for this ECO+context combination
        assert len(anti_patterns) >= 1
        pattern = next(p for p in anti_patterns if p["eco_name"] == "resize_in_congested")
        assert pattern["failure_rate"] >= 0.7
        # Pattern should identify either "region" or "utilization" as the problematic context
        assert pattern["context_pattern"] is not None
        assert len(pattern["context_pattern"]) > 0


class TestF094AntiPatternStored:
    """Test Step 3: Verify anti-pattern is stored with pattern description."""

    def test_step_3_anti_pattern_stored(self, tmp_path: Path):
        """Step 3: Verify anti-pattern is stored with pattern description."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Store an anti-pattern
        repo.store_anti_pattern(
            eco_name="resize_in_congested",
            context_pattern={"region": "congested", "utilization": ">0.8"},
            failure_rate=0.85,
            failure_count=17,
            success_count=3,
            description="Resizing buffers in congested regions causes placement overflow",
        )

        # Verify anti-pattern is stored
        patterns = repo.get_anti_patterns()
        assert len(patterns) == 1
        assert patterns[0]["eco_name"] == "resize_in_congested"
        assert patterns[0]["failure_rate"] == 0.85
        assert patterns[0]["description"] == "Resizing buffers in congested regions causes placement overflow"


class TestF094RecommendationGenerated:
    """Test Step 4: Verify recommendation is generated."""

    def test_step_4_recommendation_generated(self, tmp_path: Path):
        """Step 4: Verify recommendation is generated."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Store an anti-pattern with recommendation
        repo.store_anti_pattern(
            eco_name="resize_in_congested",
            context_pattern={"region": "congested"},
            failure_rate=0.85,
            failure_count=17,
            success_count=3,
            description="Resizing in congested regions causes overflow",
            recommendation="Avoid resize_in_congested when utilization > 0.8",
        )

        # Get anti-pattern and verify recommendation
        patterns = repo.get_anti_patterns()
        assert len(patterns) == 1
        assert patterns[0]["recommendation"] == "Avoid resize_in_congested when utilization > 0.8"

    def test_auto_recommendation_generated(self, tmp_path: Path):
        """Verify auto-generated recommendation when not provided."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Store without explicit recommendation
        repo.store_anti_pattern(
            eco_name="resize_buffer",
            context_pattern={"region": "congested"},
            failure_rate=0.9,
            failure_count=18,
            success_count=2,
            description="High failure rate in congested regions",
        )

        # Should auto-generate recommendation
        patterns = repo.get_anti_patterns()
        assert len(patterns) == 1
        assert patterns[0]["recommendation"] is not None
        assert "resize_buffer" in patterns[0]["recommendation"]


class TestF094AntiPatternsInExports:
    """Test Step 5: Verify anti-patterns are included in prior exports."""

    def test_step_5_anti_patterns_in_exports(self, tmp_path: Path):
        """Step 5: Verify anti-patterns are included in prior exports."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Store an anti-pattern
        repo.store_anti_pattern(
            eco_name="resize_buffer",
            context_pattern={"region": "congested"},
            failure_rate=0.85,
            failure_count=17,
            success_count=3,
            description="Resizing in congested regions causes overflow",
            recommendation="Avoid when utilization > 0.8",
        )

        # Export to JSON
        export_path = tmp_path / "priors_export.json"
        repo.export_to_json(export_path)

        # Verify export includes anti-patterns
        import json
        with open(export_path) as f:
            data = json.load(f)

        assert "anti_patterns" in data
        assert len(data["anti_patterns"]) == 1
        assert data["anti_patterns"][0]["eco_name"] == "resize_buffer"
        assert data["anti_patterns"][0]["failure_rate"] == 0.85

    def test_import_anti_patterns_from_json(self, tmp_path: Path):
        """Verify anti-patterns can be imported from JSON."""
        repo = SQLitePriorRepository(tmp_path / "test.db")

        # Create export with anti-patterns
        export_data = {
            "eco_priors": {},
            "anti_patterns": [
                {
                    "eco_name": "resize_buffer",
                    "context_pattern": {"region": "congested"},
                    "failure_rate": 0.85,
                    "failure_count": 17,
                    "success_count": 3,
                    "description": "Test pattern",
                    "recommendation": "Test recommendation",
                }
            ],
        }

        import json
        export_path = tmp_path / "import_test.json"
        with open(export_path, "w") as f:
            json.dump(export_data, f)

        # Import and verify
        repo.import_from_json(export_path)
        patterns = repo.get_anti_patterns()
        assert len(patterns) == 1
        assert patterns[0]["eco_name"] == "resize_buffer"
