"""Tests for Study tags organization and filtering."""

import json
from pathlib import Path

import pytest

from src.controller.study_catalog import (
    StudyCatalog,
    StudyMetadata,
    load_study_metadata,
    write_study_metadata,
)
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)


@pytest.fixture
def sample_study_config():
    """Create a sample StudyConfig with tags."""
    stage = StageConfig(
        name="stage_0",
        execution_mode=ExecutionMode.STA_ONLY,
        trial_budget=10,
        survivor_count=3,
        allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
    )

    return StudyConfig(
        name="nangate45_exploration",
        safety_domain=SafetyDomain.SANDBOX,
        base_case_name="base",
        pdk="Nangate45",
        stages=[stage],
        snapshot_path="/snapshots/nangate45_base",
        tags=["nangate45", "exploration", "wip"],
        author="test_user",
        creation_date="2026-01-08T00:00:00Z",
        description="Exploratory study on Nangate45",
    )


class TestStudyConfigTags:
    """Tests for tags field in StudyConfig."""

    def test_study_config_with_tags(self, sample_study_config):
        """Test that StudyConfig includes tags field."""
        assert hasattr(sample_study_config, "tags")
        assert sample_study_config.tags == ["nangate45", "exploration", "wip"]

    def test_study_config_default_tags(self):
        """Test that tags default to empty list."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
        )

        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="base",
            pdk="Nangate45",
            stages=[stage],
            snapshot_path="/snapshots/test",
        )

        assert config.tags == []

    def test_study_config_with_multiple_tags(self):
        """Test StudyConfig with various tag types."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
        )

        config = StudyConfig(
            name="asap7_regression",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="base",
            pdk="ASAP7",
            stages=[stage],
            snapshot_path="/snapshots/asap7",
            tags=["asap7", "regression", "production", "timing-critical"],
        )

        assert len(config.tags) == 4
        assert "asap7" in config.tags
        assert "regression" in config.tags
        assert "production" in config.tags
        assert "timing-critical" in config.tags


class TestStudyMetadata:
    """Tests for StudyMetadata dataclass."""

    def test_study_metadata_from_config(self, sample_study_config):
        """Test creating StudyMetadata from StudyConfig."""
        metadata = StudyMetadata.from_study_config(sample_study_config)

        assert metadata.name == "nangate45_exploration"
        assert metadata.pdk == "Nangate45"
        assert metadata.safety_domain == "sandbox"
        assert metadata.tags == ["nangate45", "exploration", "wip"]
        assert metadata.author == "test_user"
        assert metadata.creation_date == "2026-01-08T00:00:00Z"
        assert metadata.description == "Exploratory study on Nangate45"
        assert metadata.num_stages == 1

    def test_study_metadata_to_dict(self, sample_study_config):
        """Test converting StudyMetadata to dictionary."""
        metadata = StudyMetadata.from_study_config(sample_study_config)
        data = metadata.to_dict()

        assert data["name"] == "nangate45_exploration"
        assert data["pdk"] == "Nangate45"
        assert data["tags"] == ["nangate45", "exploration", "wip"]
        assert data["author"] == "test_user"


class TestWriteStudyMetadata:
    """Tests for writing Study metadata to artifacts."""

    def test_write_study_metadata(self, sample_study_config, tmp_path):
        """Test writing Study metadata to artifact directory."""
        # Step 1: Add tags to Study configuration
        assert sample_study_config.tags == ["nangate45", "exploration", "wip"]

        # Step 2: Write tags to Study metadata
        write_study_metadata(sample_study_config, tmp_path)

        # Verify file was created
        metadata_file = tmp_path / "study_metadata.json"
        assert metadata_file.exists()

        # Verify content
        with open(metadata_file) as f:
            data = json.load(f)

        assert data["name"] == "nangate45_exploration"
        assert data["tags"] == ["nangate45", "exploration", "wip"]

    def test_load_study_metadata(self, sample_study_config, tmp_path):
        """Test loading Study metadata from artifact directory."""
        # Write metadata
        write_study_metadata(sample_study_config, tmp_path)

        # Load it back
        metadata = load_study_metadata(tmp_path)

        assert metadata.name == "nangate45_exploration"
        assert metadata.tags == ["nangate45", "exploration", "wip"]
        assert metadata.pdk == "Nangate45"
        assert metadata.author == "test_user"


class TestStudyCatalog:
    """Tests for StudyCatalog with tag-based filtering."""

    def test_create_empty_catalog(self):
        """Test creating an empty Study catalog."""
        catalog = StudyCatalog()
        assert len(catalog.studies) == 0

    def test_add_study_to_catalog(self, sample_study_config):
        """Test adding Study to catalog."""
        catalog = StudyCatalog()
        catalog.add_study(sample_study_config)

        assert len(catalog.studies) == 1
        assert catalog.studies[0].name == "nangate45_exploration"
        assert catalog.studies[0].tags == ["nangate45", "exploration", "wip"]

    def test_add_multiple_studies(self):
        """Test adding multiple Studies to catalog."""
        catalog = StudyCatalog()

        # Create multiple Studies with different tags
        studies = [
            StudyMetadata(
                name="study1",
                pdk="Nangate45",
                safety_domain="sandbox",
                tags=["nangate45", "exploration"],
            ),
            StudyMetadata(
                name="study2",
                pdk="ASAP7",
                safety_domain="locked",
                tags=["asap7", "regression"],
            ),
            StudyMetadata(
                name="study3",
                pdk="Sky130",
                safety_domain="guarded",
                tags=["sky130", "exploration"],
            ),
        ]

        for study in studies:
            catalog.add_study(study)

        assert len(catalog.studies) == 3


class TestFilterByTags:
    """Tests for tag-based filtering."""

    @pytest.fixture
    def populated_catalog(self):
        """Create a catalog with multiple Studies."""
        catalog = StudyCatalog()

        studies = [
            StudyMetadata(
                name="study1",
                pdk="Nangate45",
                safety_domain="sandbox",
                tags=["nangate45", "exploration", "wip"],
            ),
            StudyMetadata(
                name="study2",
                pdk="ASAP7",
                safety_domain="locked",
                tags=["asap7", "regression", "production"],
            ),
            StudyMetadata(
                name="study3",
                pdk="Nangate45",
                safety_domain="guarded",
                tags=["nangate45", "regression"],
            ),
            StudyMetadata(
                name="study4",
                pdk="Sky130",
                safety_domain="sandbox",
                tags=["sky130", "exploration"],
            ),
        ]

        for study in studies:
            catalog.add_study(study)

        return catalog

    def test_filter_by_single_tag_or_mode(self, populated_catalog):
        """Test filtering by single tag (OR mode)."""
        # Step 3: Enable Study catalog filtering by tags
        results = populated_catalog.filter_by_tags(["exploration"])

        assert len(results) == 2
        assert results[0].name == "study1"
        assert results[1].name == "study4"

    def test_filter_by_multiple_tags_or_mode(self, populated_catalog):
        """Test filtering by multiple tags (OR mode - at least one match)."""
        results = populated_catalog.filter_by_tags(["nangate45", "asap7"], match_all=False)

        # Studies with nangate45 OR asap7 tags
        assert len(results) == 3
        names = {study.name for study in results}
        assert names == {"study1", "study2", "study3"}

    def test_filter_by_multiple_tags_and_mode(self, populated_catalog):
        """Test filtering by multiple tags (AND mode - all must match)."""
        results = populated_catalog.filter_by_tags(
            ["nangate45", "exploration"], match_all=True
        )

        # Only studies with BOTH nangate45 AND exploration tags
        assert len(results) == 1
        assert results[0].name == "study1"

    def test_filter_by_nonexistent_tag(self, populated_catalog):
        """Test filtering by tag that doesn't exist."""
        results = populated_catalog.filter_by_tags(["nonexistent"])
        assert len(results) == 0

    def test_filter_by_empty_tags(self, populated_catalog):
        """Test filtering with empty tag list returns all Studies."""
        results = populated_catalog.filter_by_tags([])
        assert len(results) == 4


class TestAdditionalFilters:
    """Tests for other filtering capabilities."""

    @pytest.fixture
    def populated_catalog(self):
        """Create a catalog with multiple Studies."""
        catalog = StudyCatalog()

        studies = [
            StudyMetadata(
                name="study1",
                pdk="Nangate45",
                safety_domain="sandbox",
                tags=["nangate45", "exploration"],
                author="alice",
            ),
            StudyMetadata(
                name="study2",
                pdk="ASAP7",
                safety_domain="locked",
                tags=["asap7", "regression"],
                author="bob",
            ),
            StudyMetadata(
                name="study3",
                pdk="Nangate45",
                safety_domain="guarded",
                tags=["nangate45", "regression"],
                author="alice",
            ),
        ]

        for study in studies:
            catalog.add_study(study)

        return catalog

    def test_filter_by_pdk(self, populated_catalog):
        """Test filtering Studies by PDK."""
        results = populated_catalog.filter_by_pdk("Nangate45")
        assert len(results) == 2
        assert all(study.pdk == "Nangate45" for study in results)

    def test_filter_by_safety_domain(self, populated_catalog):
        """Test filtering Studies by safety domain."""
        results = populated_catalog.filter_by_safety_domain("sandbox")
        assert len(results) == 1
        assert results[0].name == "study1"

    def test_filter_by_author(self, populated_catalog):
        """Test filtering Studies by author."""
        results = populated_catalog.filter_by_author("alice")
        assert len(results) == 2
        assert all(study.author == "alice" for study in results)


class TestTagReport:
    """Tests for tag report generation."""

    def test_generate_tag_report(self):
        """Test generating tag-based Study report."""
        catalog = StudyCatalog()

        studies = [
            StudyMetadata(
                name="study1", pdk="Nangate45", safety_domain="sandbox",
                tags=["nangate45", "exploration", "wip"]
            ),
            StudyMetadata(
                name="study2", pdk="ASAP7", safety_domain="locked",
                tags=["asap7", "regression"]
            ),
            StudyMetadata(
                name="study3", pdk="Nangate45", safety_domain="guarded",
                tags=["nangate45", "exploration"]
            ),
        ]

        for study in studies:
            catalog.add_study(study)

        # Step 4: Generate tag-based Study reports
        report = catalog.generate_tag_report()

        assert "=== Study Tag Report ===" in report
        assert "Total Studies: 3" in report
        assert "Unique Tags: 5" in report
        assert "nangate45: 2 studies" in report
        assert "exploration: 2 studies" in report
        assert "wip: 1 study" in report

    def test_get_all_tags(self):
        """Test getting all unique tags from catalog."""
        catalog = StudyCatalog()

        studies = [
            StudyMetadata(
                name="study1", pdk="Nangate45", safety_domain="sandbox",
                tags=["nangate45", "exploration"]
            ),
            StudyMetadata(
                name="study2", pdk="ASAP7", safety_domain="locked",
                tags=["asap7", "regression"]
            ),
            StudyMetadata(
                name="study3", pdk="Nangate45", safety_domain="guarded",
                tags=["nangate45", "wip"]
            ),
        ]

        for study in studies:
            catalog.add_study(study)

        all_tags = catalog.get_all_tags()
        assert all_tags == {"nangate45", "exploration", "asap7", "regression", "wip"}


class TestStudySearch:
    """Tests for Study search functionality."""

    @pytest.fixture
    def populated_catalog(self):
        """Create a catalog with multiple Studies."""
        catalog = StudyCatalog()

        studies = [
            StudyMetadata(
                name="nangate45_timing_opt",
                pdk="Nangate45",
                safety_domain="sandbox",
                tags=["nangate45", "timing"],
                description="Timing optimization study",
            ),
            StudyMetadata(
                name="asap7_congestion_test",
                pdk="ASAP7",
                safety_domain="locked",
                tags=["asap7", "congestion"],
                description="Congestion analysis for ASAP7",
            ),
            StudyMetadata(
                name="nangate45_exploration",
                pdk="Nangate45",
                safety_domain="guarded",
                tags=["nangate45", "exploration"],
                description="General exploration study",
            ),
        ]

        for study in studies:
            catalog.add_study(study)

        return catalog

    def test_search_by_name(self, populated_catalog):
        """Test searching Studies by name."""
        # Step 5: Support tag-based Study search
        results = populated_catalog.search("timing")

        assert len(results) == 1
        assert results[0].name == "nangate45_timing_opt"

    def test_search_by_description(self, populated_catalog):
        """Test searching Studies by description."""
        results = populated_catalog.search("congestion")

        # Matches both in name and description
        assert len(results) == 1
        assert results[0].name == "asap7_congestion_test"

    def test_search_by_tag(self, populated_catalog):
        """Test searching Studies by tag."""
        results = populated_catalog.search("exploration")

        assert len(results) == 1
        assert results[0].name == "nangate45_exploration"

    def test_search_case_insensitive(self, populated_catalog):
        """Test that search is case-insensitive."""
        results = populated_catalog.search("ASAP7")

        assert len(results) == 1
        assert results[0].name == "asap7_congestion_test"

    def test_search_no_results(self, populated_catalog):
        """Test search with no matches."""
        results = populated_catalog.search("nonexistent")
        assert len(results) == 0


class TestCatalogSerialization:
    """Tests for catalog serialization."""

    def test_catalog_to_dict(self):
        """Test converting catalog to dictionary."""
        catalog = StudyCatalog()

        studies = [
            StudyMetadata(
                name="study1",
                pdk="Nangate45",
                safety_domain="sandbox",
                tags=["nangate45", "test"],
            ),
            StudyMetadata(
                name="study2",
                pdk="ASAP7",
                safety_domain="locked",
                tags=["asap7"],
            ),
        ]

        for study in studies:
            catalog.add_study(study)

        data = catalog.to_dict()

        assert "studies" in data
        assert len(data["studies"]) == 2
        assert data["studies"][0]["name"] == "study1"
        assert data["studies"][0]["tags"] == ["nangate45", "test"]

    def test_catalog_json_serialization(self):
        """Test that catalog can be JSON serialized."""
        catalog = StudyCatalog()

        catalog.add_study(
            StudyMetadata(
                name="study1",
                pdk="Nangate45",
                safety_domain="sandbox",
                tags=["nangate45", "test"],
            )
        )

        data = catalog.to_dict()
        json_str = json.dumps(data, indent=2)

        # Should not raise
        assert json_str is not None
        assert "nangate45" in json_str
        assert "test" in json_str
