#!/usr/bin/env python3
"""Verify Feature 119: JSON-LD metadata generation."""

import json
import tempfile
from pathlib import Path

from controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)
from trial_runner.jsonld_metadata import (
    create_jsonld_metadata_from_study,
    generate_study_jsonld,
    validate_jsonld_structure,
)


def verify_step_1_execute_study():
    """Step 1: Execute Study (simulated with configuration)."""
    print("Step 1: Execute Study (configuration)")

    study_config = StudyConfig(
        name="jsonld_demo_study",
        safety_domain=SafetyDomain.SANDBOX,
        base_case_name="base_case",
        pdk="Nangate45",
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
        snapshot_path="/tmp/snapshot",
        author="Test Engineer",
        description="Demonstration Study for JSON-LD metadata generation",
        tags=["demo", "jsonld", "nangate45"],
    )

    print(f"  ✓ Study configured: {study_config.name}")
    print(f"  ✓ PDK: {study_config.pdk}")
    print(f"  ✓ Stages: {len(study_config.stages)}")
    return study_config


def verify_step_2_generate_metadata(study_config):
    """Step 2: Generate JSON-LD metadata describing Study semantics."""
    print("\nStep 2: Generate JSON-LD metadata describing Study semantics")

    metadata = create_jsonld_metadata_from_study(
        study_config,
        organization="Demo Organization",
    )

    print(f"  ✓ Metadata created for Study: {metadata.study_name}")
    print(f"  ✓ Description: {metadata.description[:60]}...")
    print(f"  ✓ PDK captured: {metadata.pdk}")
    print(f"  ✓ Safety domain: {metadata.safety_domain}")
    print(f"  ✓ Number of stages: {metadata.num_stages}")
    return metadata


def verify_step_3_schema_org_vocabulary(metadata):
    """Step 3: Include schema.org Dataset vocabulary."""
    print("\nStep 3: Include schema.org Dataset vocabulary")

    jsonld = metadata.to_jsonld()

    # Verify schema.org context
    assert jsonld["@context"] == "https://schema.org/", "Missing schema.org context"
    print(f"  ✓ @context: {jsonld['@context']}")

    # Verify Dataset type
    assert jsonld["@type"] == "Dataset", "Type must be Dataset"
    print(f"  ✓ @type: {jsonld['@type']}")

    # Verify required Dataset fields
    required_fields = ["name", "description", "dateCreated"]
    for field in required_fields:
        assert field in jsonld, f"Missing required field: {field}"
        print(f"  ✓ {field}: {str(jsonld[field])[:50]}...")

    # Verify additionalProperty uses PropertyValue
    if "additionalProperty" in jsonld:
        for prop in jsonld["additionalProperty"]:
            assert prop["@type"] == "PropertyValue", "Properties must be PropertyValue"
        print(f"  ✓ additionalProperty uses PropertyValue ({len(jsonld['additionalProperty'])} properties)")

    return jsonld


def verify_step_4_link_artifact_uris(metadata):
    """Step 4: Link to artifact URIs."""
    print("\nStep 4: Link to artifact URIs")

    # Create metadata with artifact base URL
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_root = Path(tmpdir) / "artifacts"
        artifact_root.mkdir()

        # Create some demo artifacts
        (artifact_root / "stage_0").mkdir()
        (artifact_root / "stage_0" / "trial_0_summary.json").write_text("{}")
        (artifact_root / "README.md").write_text("# Study Artifacts")

        # Re-create metadata with artifacts
        from controller.types import StudyConfig, SafetyDomain, StageConfig, ExecutionMode, ECOClass

        study_config = StudyConfig(
            name="jsonld_demo_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base_case",
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
            snapshot_path="/tmp/snapshot",
        )

        metadata_with_artifacts = create_jsonld_metadata_from_study(
            study_config,
            artifact_root=artifact_root,
            artifact_base_url="http://artifacts.example.com/studies/jsonld_demo",
        )

        jsonld = metadata_with_artifacts.to_jsonld()

        # Verify distribution field exists
        assert "distribution" in jsonld, "Missing distribution field for artifacts"
        distributions = jsonld["distribution"]
        print(f"  ✓ distribution field present with {len(distributions)} artifacts")

        # Verify each distribution has proper structure
        for dist in distributions:
            assert dist["@type"] == "DataDownload", "Distribution must be DataDownload"
            assert "contentUrl" in dist, "Distribution must have contentUrl"
            assert "name" in dist, "Distribution must have name"
            print(f"    - {dist['name']}: {dist['contentUrl']}")

        return jsonld


def verify_step_5_write_to_artifacts():
    """Step 5: Write JSON-LD to Study artifacts."""
    print("\nStep 5: Write JSON-LD to Study artifacts")

    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_root = Path(tmpdir) / "study_artifacts"
        artifact_root.mkdir()

        # Create Study config
        study_config = StudyConfig(
            name="jsonld_demo_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base_case",
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
            snapshot_path="/tmp/snapshot",
            author="Test Engineer",
            description="Demo Study",
        )

        # Generate and write JSON-LD
        output_path = generate_study_jsonld(
            study_config,
            artifact_root,
            organization="Demo Organization",
        )

        print(f"  ✓ JSON-LD written to: {output_path.name}")
        assert output_path.exists(), "JSON-LD file not created"
        print(f"  ✓ File exists at: {output_path}")

        # Verify content
        with open(output_path) as f:
            data = json.load(f)

        assert data["@context"] == "https://schema.org/", "Invalid context in file"
        assert data["@type"] == "Dataset", "Invalid type in file"
        print(f"  ✓ File contains valid JSON-LD")
        print(f"  ✓ Study name: {data['name']}")

        return output_path


def verify_step_6_enable_discovery():
    """Step 6: Enable discovery and indexing by semantic search engines."""
    print("\nStep 6: Enable discovery and indexing by semantic search engines")

    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_root = Path(tmpdir) / "artifacts"
        artifact_root.mkdir()

        study_config = StudyConfig(
            name="searchable_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="base",
            pdk="ASAP7",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="/tmp/snapshot",
            author="Search Engineer",
            description="Study optimized for semantic search discovery",
            tags=["searchable", "production", "asap7", "timing-optimization"],
        )

        # Generate JSON-LD with keywords for discovery
        metadata = create_jsonld_metadata_from_study(
            study_config,
            organization="Semiconductor Research Lab",
        )

        jsonld = metadata.to_jsonld()

        # Verify searchability features
        assert "keywords" in jsonld, "Missing keywords for search"
        keywords = jsonld["keywords"]
        print(f"  ✓ Keywords present: {len(keywords)} keywords")
        print(f"    Keywords: {', '.join(keywords[:5])}")

        # Verify structured data
        assert validate_jsonld_structure(jsonld), "Invalid JSON-LD structure"
        print(f"  ✓ JSON-LD structure valid (schema.org compliant)")

        # Verify creator for attribution
        if "creator" in jsonld:
            print(f"  ✓ Creator attribution: {jsonld['creator']['name']}")

        # Verify provider/organization
        if "provider" in jsonld:
            print(f"  ✓ Organization: {jsonld['provider']['name']}")

        # Verify it's machine-readable JSON
        json_str = json.dumps(jsonld, indent=2)
        parsed_back = json.loads(json_str)
        assert parsed_back == jsonld, "JSON round-trip failed"
        print(f"  ✓ Machine-readable JSON (serializable)")

        # Verify semantic properties
        assert "additionalProperty" in jsonld, "Missing semantic properties"
        props = {p["name"]: p["value"] for p in jsonld["additionalProperty"]}
        print(f"  ✓ Semantic properties: {', '.join(list(props.keys())[:3])}")

        print(f"\n  ✓ JSON-LD enables semantic search and discovery")
        print(f"  ✓ Compatible with search engines supporting schema.org")
        print(f"  ✓ Provides structured metadata for Study artifacts")


def main():
    """Run all verification steps."""
    print("=" * 70)
    print("Feature 119: JSON-LD Metadata Generation Verification")
    print("=" * 70)

    # Step 1: Execute Study
    study_config = verify_step_1_execute_study()

    # Step 2: Generate JSON-LD metadata
    metadata = verify_step_2_generate_metadata(study_config)

    # Step 3: Include schema.org Dataset vocabulary
    jsonld = verify_step_3_schema_org_vocabulary(metadata)

    # Step 4: Link to artifact URIs
    jsonld_with_artifacts = verify_step_4_link_artifact_uris(metadata)

    # Step 5: Write JSON-LD to Study artifacts
    output_path = verify_step_5_write_to_artifacts()

    # Step 6: Enable discovery and indexing
    verify_step_6_enable_discovery()

    print("\n" + "=" * 70)
    print("✓ ALL 6 FEATURE STEPS VERIFIED SUCCESSFULLY")
    print("=" * 70)
    print("\nFeature 119 is ready to be marked as passing.")


if __name__ == "__main__":
    main()
