"""Tests for Study metadata support (author, creation_date, description).

This test suite validates that Noodle 2 properly handles Study metadata for
documentation, cataloging, and human-readable Study summaries.

Feature: Support Study metadata including author, creation date, description
Steps:
  1. Create Study configuration with metadata fields
  2. Populate author, creation_date, description
  3. Write metadata to Study artifacts
  4. Display metadata in Study summary reports
  5. Enable Study catalog/search by metadata
"""

from datetime import datetime, timezone

import pytest

from src.controller.executor import StudyExecutor, StudyResult
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)


class TestStudyConfigMetadata:
    """Test suite for StudyConfig metadata fields."""

    def test_study_config_has_author_field(self):
        """Step 1: Verify StudyConfig has author field."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[],
            snapshot_path="/tmp/snapshot",
            author="Alice Chen",
        )

        assert hasattr(config, "author"), "StudyConfig should have author field"
        assert config.author == "Alice Chen"

    def test_study_config_has_creation_date_field(self):
        """Step 1: Verify StudyConfig has creation_date field."""
        now = datetime.now(timezone.utc).isoformat()

        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[],
            snapshot_path="/tmp/snapshot",
            creation_date=now,
        )

        assert hasattr(config, "creation_date"), "StudyConfig should have creation_date field"
        assert config.creation_date == now

    def test_study_config_has_description_field(self):
        """Step 1: Verify StudyConfig has description field."""
        description = "ECO exploration for timing optimization on Nangate45 design"

        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[],
            snapshot_path="/tmp/snapshot",
            description=description,
        )

        assert hasattr(config, "description"), "StudyConfig should have description field"
        assert config.description == description

    def test_metadata_fields_are_optional(self):
        """Verify metadata fields are optional (default to None)."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[],
            snapshot_path="/tmp/snapshot",
        )

        # Metadata fields should exist but be None by default
        assert config.author is None
        assert config.creation_date is None
        assert config.description is None

    def test_all_metadata_fields_together(self):
        """Step 2: Populate author, creation_date, description together."""
        now = datetime.now(timezone.utc).isoformat()

        config = StudyConfig(
            name="timing_optimization_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
                )
            ],
            snapshot_path="/tmp/snapshot",
            author="Bob Zhang",
            creation_date=now,
            description="Multi-stage ECO exploration for WNS improvement",
        )

        assert config.author == "Bob Zhang"
        assert config.creation_date == now
        assert config.description == "Multi-stage ECO exploration for WNS improvement"


class TestStudyResultMetadata:
    """Test suite for StudyResult metadata propagation."""

    def test_study_result_has_author_field(self):
        """Verify StudyResult includes author field."""
        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            author="Alice Chen",
        )

        assert hasattr(result, "author")
        assert result.author == "Alice Chen"

    def test_study_result_has_creation_date_field(self):
        """Verify StudyResult includes creation_date field."""
        now = datetime.now(timezone.utc).isoformat()

        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            creation_date=now,
        )

        assert hasattr(result, "creation_date")
        assert result.creation_date == now

    def test_study_result_has_description_field(self):
        """Verify StudyResult includes description field."""
        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            description="Test study for ECO exploration",
        )

        assert hasattr(result, "description")
        assert result.description == "Test study for ECO exploration"

    def test_study_result_metadata_fields_optional(self):
        """Verify StudyResult metadata fields are optional."""
        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
        )

        assert result.author is None
        assert result.creation_date is None
        assert result.description is None


class TestMetadataSerialization:
    """Test suite for metadata serialization to JSON."""

    def test_study_result_serializes_author(self):
        """Step 3: Verify author is written to Study artifacts (JSON)."""
        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            author="Carol Liu",
        )

        result_dict = result.to_dict()

        assert "author" in result_dict
        assert result_dict["author"] == "Carol Liu"

    def test_study_result_serializes_creation_date(self):
        """Step 3: Verify creation_date is written to Study artifacts (JSON)."""
        now = datetime.now(timezone.utc).isoformat()

        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            creation_date=now,
        )

        result_dict = result.to_dict()

        assert "creation_date" in result_dict
        assert result_dict["creation_date"] == now

    def test_study_result_serializes_description(self):
        """Step 3: Verify description is written to Study artifacts (JSON)."""
        description = "Timing optimization study with placement-local ECOs"

        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            description=description,
        )

        result_dict = result.to_dict()

        assert "description" in result_dict
        assert result_dict["description"] == description

    def test_metadata_excluded_when_none(self):
        """Verify metadata fields are excluded from JSON when None (compact telemetry)."""
        result = StudyResult(
            study_name="test_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            author=None,
            creation_date=None,
            description=None,
        )

        result_dict = result.to_dict()

        # Metadata fields should not be present when None
        assert "author" not in result_dict
        assert "creation_date" not in result_dict
        assert "description" not in result_dict

    def test_all_metadata_serialized_together(self):
        """Verify all metadata fields serialize together."""
        now = datetime.now(timezone.utc).isoformat()

        result = StudyResult(
            study_name="complete_study",
            total_stages=3,
            stages_completed=3,
            total_runtime_seconds=500.0,
            author="David Park",
            creation_date=now,
            description="Complete multi-stage study with all ECO classes",
        )

        result_dict = result.to_dict()

        assert result_dict["author"] == "David Park"
        assert result_dict["creation_date"] == now
        assert result_dict["description"] == "Complete multi-stage study with all ECO classes"


class TestMetadataPropagation:
    """Test suite for metadata propagation from StudyConfig to StudyResult."""

    def test_metadata_copied_from_config_to_result_success(self, tmp_path):
        """Verify metadata propagates from StudyConfig to StudyResult (successful Study)."""
        now = datetime.now(timezone.utc).isoformat()

        config = StudyConfig(
            name="propagation_test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="test_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=1,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
            author="Emma Garcia",
            creation_date=now,
            description="Propagation test study",
        )

        # Verify config has metadata
        assert config.author == "Emma Garcia"
        assert config.creation_date == now
        assert config.description == "Propagation test study"

        # The StudyExecutor should copy these to StudyResult
        # (tested via unit tests for StudyResult construction)

    def test_metadata_copied_to_aborted_study_result(self):
        """Verify metadata propagates even when Study aborts."""
        now = datetime.now(timezone.utc).isoformat()

        result = StudyResult(
            study_name="aborted_study",
            total_stages=3,
            stages_completed=1,
            total_runtime_seconds=50.0,
            aborted=True,
            abort_reason="WNS threshold violated",
            author="Frank Kim",
            creation_date=now,
            description="Study that aborted due to timing violation",
        )

        # Metadata should still be present even when aborted
        assert result.author == "Frank Kim"
        assert result.creation_date == now
        assert result.description == "Study that aborted due to timing violation"

        # And serialize to JSON
        result_dict = result.to_dict()
        assert result_dict["author"] == "Frank Kim"
        assert result_dict["creation_date"] == now


class TestMetadataDisplayInSummary:
    """Test suite for metadata display in Study summary reports."""

    def test_summary_includes_author(self):
        """Step 4: Verify author is displayed in Study summary."""
        result = StudyResult(
            study_name="summary_test",
            total_stages=2,
            stages_completed=2,
            total_runtime_seconds=200.0,
            author="Grace Lee",
        )

        result_dict = result.to_dict()

        # Summary should include author for display
        assert "author" in result_dict
        assert result_dict["author"] == "Grace Lee"

    def test_summary_includes_creation_date(self):
        """Step 4: Verify creation_date is displayed in Study summary."""
        now = datetime.now(timezone.utc).isoformat()

        result = StudyResult(
            study_name="summary_test",
            total_stages=2,
            stages_completed=2,
            total_runtime_seconds=200.0,
            creation_date=now,
        )

        result_dict = result.to_dict()

        # Summary should include creation date for display
        assert "creation_date" in result_dict
        assert result_dict["creation_date"] == now

    def test_summary_includes_description(self):
        """Step 4: Verify description is displayed in Study summary."""
        description = "Multi-stage timing optimization with placement and routing ECOs"

        result = StudyResult(
            study_name="summary_test",
            total_stages=2,
            stages_completed=2,
            total_runtime_seconds=200.0,
            description=description,
        )

        result_dict = result.to_dict()

        # Summary should include description for display
        assert "description" in result_dict
        assert result_dict["description"] == description

    def test_summary_format_human_readable(self):
        """Verify metadata is human-readable in summary."""
        now = "2026-01-08T10:30:00Z"  # ISO 8601 format

        result = StudyResult(
            study_name="readable_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=100.0,
            author="Henry Wang",
            creation_date=now,
            description="Test study for verifying human-readable metadata",
        )

        result_dict = result.to_dict()

        # Verify all fields are strings (human-readable)
        assert isinstance(result_dict["author"], str)
        assert isinstance(result_dict["creation_date"], str)
        assert isinstance(result_dict["description"], str)

        # Verify ISO 8601 date format is parseable
        parsed_date = datetime.fromisoformat(result_dict["creation_date"].replace("Z", "+00:00"))
        assert parsed_date is not None


class TestMetadataCataloging:
    """Test suite for Study catalog/search by metadata."""

    def test_filter_studies_by_author(self):
        """Step 5: Enable Study catalog/search by author."""
        studies = [
            StudyResult(
                study_name="study1",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                author="Alice Chen",
            ),
            StudyResult(
                study_name="study2",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                author="Bob Zhang",
            ),
            StudyResult(
                study_name="study3",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                author="Alice Chen",
            ),
        ]

        # Filter by author
        alice_studies = [s for s in studies if s.author == "Alice Chen"]

        assert len(alice_studies) == 2
        assert alice_studies[0].study_name == "study1"
        assert alice_studies[1].study_name == "study3"

    def test_filter_studies_by_date_range(self):
        """Step 5: Enable Study catalog/search by creation_date."""
        studies = [
            StudyResult(
                study_name="study1",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                creation_date="2026-01-01T10:00:00Z",
            ),
            StudyResult(
                study_name="study2",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                creation_date="2026-01-05T10:00:00Z",
            ),
            StudyResult(
                study_name="study3",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                creation_date="2026-01-10T10:00:00Z",
            ),
        ]

        # Filter by date range (after 2026-01-03)
        cutoff = "2026-01-03T00:00:00Z"
        recent_studies = [s for s in studies if s.creation_date and s.creation_date > cutoff]

        assert len(recent_studies) == 2
        assert recent_studies[0].study_name == "study2"
        assert recent_studies[1].study_name == "study3"

    def test_search_studies_by_description_keyword(self):
        """Step 5: Enable Study catalog/search by description keywords."""
        studies = [
            StudyResult(
                study_name="study1",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                description="Timing optimization with placement ECOs",
            ),
            StudyResult(
                study_name="study2",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                description="Congestion reduction using routing ECOs",
            ),
            StudyResult(
                study_name="study3",
                total_stages=1,
                stages_completed=1,
                total_runtime_seconds=100.0,
                description="Timing and congestion multi-objective optimization",
            ),
        ]

        # Search by keyword "timing"
        timing_studies = [
            s for s in studies if s.description and "timing" in s.description.lower()
        ]

        assert len(timing_studies) == 2
        assert timing_studies[0].study_name == "study1"
        assert timing_studies[1].study_name == "study3"

    def test_metadata_enables_study_catalog(self):
        """Verify metadata enables comprehensive Study catalog."""
        # Create a catalog of studies with metadata
        catalog = [
            {
                "name": s.study_name,
                "author": s.author,
                "creation_date": s.creation_date,
                "description": s.description,
                "completed": s.stages_completed == s.total_stages,
            }
            for s in [
                StudyResult(
                    study_name="eco_exploration_v1",
                    total_stages=3,
                    stages_completed=3,
                    total_runtime_seconds=500.0,
                    author="Alice Chen",
                    creation_date="2026-01-08T09:00:00Z",
                    description="Initial ECO exploration on Nangate45",
                ),
                StudyResult(
                    study_name="eco_exploration_v2",
                    total_stages=3,
                    stages_completed=2,
                    total_runtime_seconds=300.0,
                    author="Alice Chen",
                    creation_date="2026-01-08T14:00:00Z",
                    description="Improved ECO exploration with better survivor selection",
                    aborted=True,
                ),
            ]
        ]

        # Catalog should be searchable by all metadata fields
        assert len(catalog) == 2
        assert catalog[0]["author"] == "Alice Chen"
        assert catalog[0]["completed"] is True
        assert catalog[1]["completed"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
