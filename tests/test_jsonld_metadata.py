"""Tests for JSON-LD metadata generation."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)
from trial_runner.jsonld_metadata import (
    JSONLDStudyMetadata,
    create_jsonld_metadata_from_study,
    generate_study_jsonld,
    validate_jsonld_structure,
    write_jsonld_metadata,
)


class TestJSONLDStudyMetadata:
    """Test JSON-LD metadata generation."""

    def test_create_minimal_metadata(self):
        """Test creating minimal JSON-LD metadata."""
        metadata = JSONLDStudyMetadata(
            study_name="test_study",
            description="Test study for validation",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            num_stages=3,
            base_case_name="base",
        )

        assert metadata.study_name == "test_study"
        assert metadata.pdk == "Nangate45"
        assert metadata.safety_domain == "sandbox"

    def test_to_jsonld_minimal(self):
        """Test converting minimal metadata to JSON-LD format."""
        metadata = JSONLDStudyMetadata(
            study_name="test_study",
            description="Test study",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
        )

        jsonld = metadata.to_jsonld()

        # Check required schema.org fields
        assert jsonld["@context"] == "https://schema.org/"
        assert jsonld["@type"] == "Dataset"
        assert jsonld["name"] == "test_study"
        assert jsonld["description"] == "Test study"
        assert jsonld["dateCreated"] == "2026-01-08T10:00:00Z"

    def test_to_jsonld_includes_pdk_metadata(self):
        """Test that PDK information is included in additionalProperty."""
        metadata = JSONLDStudyMetadata(
            study_name="asap7_study",
            description="ASAP7 test",
            pdk="ASAP7",
            safety_domain="guarded",
            creation_date="2026-01-08T10:00:00Z",
        )

        jsonld = metadata.to_jsonld()

        # Check additionalProperty contains PDK
        assert "additionalProperty" in jsonld
        properties = jsonld["additionalProperty"]
        pdk_prop = next((p for p in properties if p["name"] == "PDK"), None)
        assert pdk_prop is not None
        assert pdk_prop["value"] == "ASAP7"

    def test_to_jsonld_includes_safety_domain(self):
        """Test that safety domain is included in metadata."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="locked",
            creation_date="2026-01-08T10:00:00Z",
        )

        jsonld = metadata.to_jsonld()

        properties = jsonld["additionalProperty"]
        safety_prop = next((p for p in properties if p["name"] == "Safety Domain"), None)
        assert safety_prop is not None
        assert safety_prop["value"] == "locked"

    def test_to_jsonld_with_creator(self):
        """Test JSON-LD with creator information."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            creator_name="Alice Engineer",
            creator_email="alice@example.com",
        )

        jsonld = metadata.to_jsonld()

        # Check creator field
        assert "creator" in jsonld
        creator = jsonld["creator"]
        assert creator["@type"] == "Person"
        assert creator["name"] == "Alice Engineer"
        assert creator["email"] == "alice@example.com"

    def test_to_jsonld_with_organization(self):
        """Test JSON-LD with organization/provider."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            organization="Example Corporation",
        )

        jsonld = metadata.to_jsonld()

        assert "provider" in jsonld
        provider = jsonld["provider"]
        assert provider["@type"] == "Organization"
        assert provider["name"] == "Example Corporation"

    def test_to_jsonld_with_keywords_and_tags(self):
        """Test that keywords and tags are merged."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            keywords=["timing", "eco"],
            tags=["experiment", "timing"],  # "timing" appears in both
        )

        jsonld = metadata.to_jsonld()

        assert "keywords" in jsonld
        keywords = jsonld["keywords"]
        # Should be deduplicated
        assert "timing" in keywords
        assert "eco" in keywords
        assert "experiment" in keywords
        # Count should be 3 (deduplicated)
        assert keywords.count("timing") == 1

    def test_to_jsonld_with_artifact_urls(self):
        """Test JSON-LD with artifact distribution URLs."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            artifact_base_url="http://artifacts.example.com/studies/test_study",
            artifact_paths=["stage_0/summary.json", "stage_1/heatmap.png"],
        )

        jsonld = metadata.to_jsonld()

        # Check distribution field
        assert "distribution" in jsonld
        distributions = jsonld["distribution"]
        assert len(distributions) == 2

        # Check first distribution
        assert distributions[0]["@type"] == "DataDownload"
        assert "stage_0/summary.json" in distributions[0]["contentUrl"]
        assert distributions[0]["name"] == "summary.json"

    def test_to_jsonld_without_base_url_uses_haspart(self):
        """Test that artifacts without base URL use hasPart instead of distribution."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            artifact_paths=["stage_0/summary.json", "README.md"],
        )

        jsonld = metadata.to_jsonld()

        # Should use hasPart, not distribution
        assert "distribution" not in jsonld
        assert "hasPart" in jsonld

        parts = jsonld["hasPart"]
        assert len(parts) == 2
        assert parts[0]["@type"] == "Dataset"
        assert parts[0]["identifier"] == "stage_0/summary.json"

    def test_to_jsonld_with_license(self):
        """Test JSON-LD with license URL."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            license_url="https://opensource.org/licenses/MIT",
        )

        jsonld = metadata.to_jsonld()

        assert "license" in jsonld
        assert jsonld["license"] == "https://opensource.org/licenses/MIT"

    def test_to_jsonld_with_date_published(self):
        """Test JSON-LD with publication date."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
            date_published="2026-01-08T15:30:00Z",
        )

        jsonld = metadata.to_jsonld()

        assert "datePublished" in jsonld
        assert jsonld["datePublished"] == "2026-01-08T15:30:00Z"


class TestCreateJSONLDFromStudy:
    """Test creating JSON-LD metadata from StudyConfig."""

    def test_create_from_study_config(self, tmp_path):
        """Test creating JSON-LD metadata from StudyConfig."""
        study_config = StudyConfig(
            name="nangate45_test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
            author="Test Engineer",
            description="Test study for validation",
            tags=["test", "nangate45"],
        )

        metadata = create_jsonld_metadata_from_study(study_config)

        assert metadata.study_name == "nangate45_test"
        assert metadata.pdk == "Nangate45"
        assert metadata.safety_domain == "sandbox"
        assert metadata.num_stages == 1
        assert metadata.base_case_name == "base"
        assert metadata.creator_name == "Test Engineer"
        assert "nangate45" in metadata.tags

    def test_create_from_study_with_artifacts(self, tmp_path):
        """Test creating JSON-LD with artifact discovery."""
        # Create some artifact files
        artifact_root = tmp_path / "artifacts"
        artifact_root.mkdir()
        (artifact_root / "stage_0").mkdir()
        (artifact_root / "stage_0" / "summary.json").write_text("{}")
        (artifact_root / "README.md").write_text("# Test")

        study_config = StudyConfig(
            name="test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
        )

        metadata = create_jsonld_metadata_from_study(
            study_config, artifact_root=artifact_root
        )

        # Should have discovered artifacts
        assert len(metadata.artifact_paths) > 0
        assert any("summary.json" in p for p in metadata.artifact_paths)
        assert any("README.md" in p for p in metadata.artifact_paths)

    def test_create_with_organization(self, tmp_path):
        """Test creating JSON-LD with organization."""
        study_config = StudyConfig(
            name="test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
        )

        metadata = create_jsonld_metadata_from_study(
            study_config, organization="Example Corp"
        )

        assert metadata.organization == "Example Corp"

    def test_create_with_base_url(self, tmp_path):
        """Test creating JSON-LD with artifact base URL."""
        study_config = StudyConfig(
            name="test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
        )

        metadata = create_jsonld_metadata_from_study(
            study_config, artifact_base_url="http://example.com/artifacts"
        )

        assert metadata.artifact_base_url == "http://example.com/artifacts"


class TestWriteJSONLD:
    """Test writing JSON-LD metadata to files."""

    def test_write_jsonld_metadata(self, tmp_path):
        """Test writing JSON-LD metadata to file."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test study",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
        )

        output_path = tmp_path / "metadata.jsonld"
        write_jsonld_metadata(metadata, output_path)

        # Verify file was written
        assert output_path.exists()

        # Verify content is valid JSON
        with open(output_path) as f:
            data = json.load(f)

        assert data["@type"] == "Dataset"
        assert data["name"] == "test"

    def test_write_creates_parent_directories(self, tmp_path):
        """Test that write_jsonld_metadata creates parent directories."""
        metadata = JSONLDStudyMetadata(
            study_name="test",
            description="Test",
            pdk="Nangate45",
            safety_domain="sandbox",
            creation_date="2026-01-08T10:00:00Z",
        )

        output_path = tmp_path / "deep" / "nested" / "metadata.jsonld"
        write_jsonld_metadata(metadata, output_path)

        assert output_path.exists()


class TestGenerateStudyJSONLD:
    """Test convenience function for generating Study JSON-LD."""

    def test_generate_study_jsonld(self, tmp_path):
        """Test end-to-end JSON-LD generation."""
        artifact_root = tmp_path / "artifacts"
        artifact_root.mkdir()

        study_config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
            author="Test User",
        )

        output_path = generate_study_jsonld(study_config, artifact_root)

        # Verify file was created
        assert output_path.exists()
        assert output_path.name == "study_metadata.jsonld"

        # Verify content
        with open(output_path) as f:
            data = json.load(f)

        assert data["@type"] == "Dataset"
        assert data["name"] == "test_study"
        assert "creator" in data

    def test_generate_with_custom_filename(self, tmp_path):
        """Test generating JSON-LD with custom filename."""
        artifact_root = tmp_path / "artifacts"
        artifact_root.mkdir()

        study_config = StudyConfig(
            name="test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
        )

        output_path = generate_study_jsonld(
            study_config, artifact_root, output_filename="custom.jsonld"
        )

        assert output_path.name == "custom.jsonld"


class TestValidateJSONLDStructure:
    """Test JSON-LD structure validation."""

    def test_valid_structure(self):
        """Test validation of valid JSON-LD structure."""
        jsonld = {
            "@context": "https://schema.org/",
            "@type": "Dataset",
            "name": "Test",
            "description": "Test dataset",
        }

        assert validate_jsonld_structure(jsonld) is True

    def test_missing_context(self):
        """Test that missing @context fails validation."""
        jsonld = {
            "@type": "Dataset",
            "name": "Test",
            "description": "Test dataset",
        }

        assert validate_jsonld_structure(jsonld) is False

    def test_missing_type(self):
        """Test that missing @type fails validation."""
        jsonld = {
            "@context": "https://schema.org/",
            "name": "Test",
            "description": "Test dataset",
        }

        assert validate_jsonld_structure(jsonld) is False

    def test_missing_name(self):
        """Test that missing name fails validation."""
        jsonld = {
            "@context": "https://schema.org/",
            "@type": "Dataset",
            "description": "Test dataset",
        }

        assert validate_jsonld_structure(jsonld) is False

    def test_missing_description(self):
        """Test that missing description fails validation."""
        jsonld = {
            "@context": "https://schema.org/",
            "@type": "Dataset",
            "name": "Test",
        }

        assert validate_jsonld_structure(jsonld) is False

    def test_wrong_context(self):
        """Test that non-schema.org context fails validation."""
        jsonld = {
            "@context": "https://example.com/",
            "@type": "Dataset",
            "name": "Test",
            "description": "Test dataset",
        }

        assert validate_jsonld_structure(jsonld) is False

    def test_wrong_type(self):
        """Test that non-Dataset type fails validation."""
        jsonld = {
            "@context": "https://schema.org/",
            "@type": "Thing",
            "name": "Test",
            "description": "Test dataset",
        }

        assert validate_jsonld_structure(jsonld) is False


class TestJSONLDEndToEnd:
    """End-to-end JSON-LD generation and validation tests."""

    def test_complete_workflow(self, tmp_path):
        """Test complete JSON-LD generation workflow."""
        # Create Study with comprehensive metadata
        artifact_root = tmp_path / "study_artifacts"
        artifact_root.mkdir()
        (artifact_root / "stage_0").mkdir()
        (artifact_root / "stage_0" / "trial_0_summary.json").write_text("{}")

        study_config = StudyConfig(
            name="complete_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="base_case",
            pdk="ASAP7",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage_1",
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.PLACEMENT_LOCAL,
                    ],
                ),
            ],
            snapshot_path=str(tmp_path / "snapshot"),
            author="Jane Engineer",
            description="Comprehensive ASAP7 timing optimization study",
            tags=["asap7", "timing", "production"],
        )

        # Generate JSON-LD
        output_path = generate_study_jsonld(
            study_config,
            artifact_root,
            artifact_base_url="http://artifacts.example.com/studies/complete_study",
            organization="Example Semiconductor",
        )

        # Verify file exists
        assert output_path.exists()

        # Load and validate
        with open(output_path) as f:
            jsonld = json.load(f)

        # Validate structure
        assert validate_jsonld_structure(jsonld)

        # Verify comprehensive fields
        assert jsonld["@context"] == "https://schema.org/"
        assert jsonld["@type"] == "Dataset"
        assert jsonld["name"] == "complete_study"
        assert "ASAP7" in jsonld["description"]

        # Verify creator
        assert jsonld["creator"]["name"] == "Jane Engineer"

        # Verify provider/organization
        assert jsonld["provider"]["name"] == "Example Semiconductor"

        # Verify keywords include tags
        assert "asap7" in jsonld["keywords"]
        assert "timing" in jsonld["keywords"]

        # Verify additional properties
        props = {p["name"]: p["value"] for p in jsonld["additionalProperty"]}
        assert props["PDK"] == "ASAP7"
        assert props["Safety Domain"] == "guarded"
        assert props["Number of Stages"] == "2"
        assert props["Base Case"] == "base_case"

        # Verify artifacts with URLs
        assert "distribution" in jsonld
        assert len(jsonld["distribution"]) > 0

    def test_generated_jsonld_is_machine_readable(self, tmp_path):
        """Test that generated JSON-LD can be parsed by standard tools."""
        artifact_root = tmp_path / "artifacts"
        artifact_root.mkdir()

        study_config = StudyConfig(
            name="machine_readable_test",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path=str(tmp_path / "snapshot"),
        )

        output_path = generate_study_jsonld(study_config, artifact_root)

        # Verify it's valid JSON
        with open(output_path) as f:
            data = json.load(f)

        # Verify it has JSON-LD context
        assert "@context" in data
        assert "@type" in data

        # Verify all values are JSON-serializable (no custom objects)
        json_str = json.dumps(data)
        assert len(json_str) > 0
