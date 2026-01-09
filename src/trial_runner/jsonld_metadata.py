"""JSON-LD metadata generation for Study artifacts to enable semantic search.

This module generates JSON-LD (JSON for Linking Data) metadata describing
Study execution and artifacts using schema.org vocabulary. This enables:
- Semantic search and discovery
- Machine-readable provenance
- Integration with knowledge graphs
- Standardized metadata interchange
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from controller.types import StudyConfig


@dataclass
class JSONLDStudyMetadata:
    """
    JSON-LD metadata for a Study using schema.org Dataset vocabulary.

    Provides semantic description of Study execution, enabling discovery
    by search engines and integration with semantic web tools.
    """

    # Core metadata
    study_name: str
    description: str
    pdk: str
    safety_domain: str

    # Temporal metadata
    creation_date: str  # ISO 8601 format
    date_published: str | None = None  # When Study was completed/published

    # Creator/attribution
    creator_name: str | None = None
    creator_email: str | None = None
    organization: str | None = None

    # Study configuration
    num_stages: int = 0
    base_case_name: str = ""

    # Artifact metadata
    artifact_base_url: str | None = None  # Base URL for artifact URIs
    artifact_paths: list[str] = field(default_factory=list)

    # Keywords and categorization
    keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    # Additional metadata
    license_url: str | None = None
    version: str = "1.0"

    def to_jsonld(self) -> dict[str, Any]:
        """
        Convert to JSON-LD format using schema.org vocabulary.

        Returns:
            JSON-LD dictionary compliant with schema.org Dataset
        """
        # Build JSON-LD structure
        jsonld: dict[str, Any] = {
            "@context": "https://schema.org/",
            "@type": "Dataset",
            "name": self.study_name,
            "description": self.description,
            "version": self.version,
            "dateCreated": self.creation_date,
        }

        # Add optional date published
        if self.date_published:
            jsonld["datePublished"] = self.date_published

        # Add creator information
        if self.creator_name:
            creator: dict[str, Any] = {
                "@type": "Person",
                "name": self.creator_name,
            }
            if self.creator_email:
                creator["email"] = self.creator_email
            jsonld["creator"] = creator

        # Add organization
        if self.organization:
            jsonld["provider"] = {
                "@type": "Organization",
                "name": self.organization,
            }

        # Add keywords (combine keywords and tags)
        all_keywords = list(set(self.keywords + self.tags))
        if all_keywords:
            jsonld["keywords"] = all_keywords

        # Add Study-specific metadata as additionalProperty
        additional_properties = [
            {
                "@type": "PropertyValue",
                "name": "PDK",
                "value": self.pdk,
            },
            {
                "@type": "PropertyValue",
                "name": "Safety Domain",
                "value": self.safety_domain,
            },
            {
                "@type": "PropertyValue",
                "name": "Number of Stages",
                "value": str(self.num_stages),
            },
            {
                "@type": "PropertyValue",
                "name": "Base Case",
                "value": self.base_case_name,
            },
        ]
        jsonld["additionalProperty"] = additional_properties

        # Add license if provided
        if self.license_url:
            jsonld["license"] = self.license_url

        # Add distribution/download URLs if artifacts are accessible
        if self.artifact_base_url and self.artifact_paths:
            distributions = []
            for artifact_path in self.artifact_paths:
                # Construct full URL
                full_url = f"{self.artifact_base_url.rstrip('/')}/{artifact_path.lstrip('/')}"
                distributions.append({
                    "@type": "DataDownload",
                    "contentUrl": full_url,
                    "name": Path(artifact_path).name,
                })
            if distributions:
                jsonld["distribution"] = distributions

        # Add hasPart for artifact listing without full URLs
        if self.artifact_paths and not self.artifact_base_url:
            parts = []
            for artifact_path in self.artifact_paths:
                parts.append({
                    "@type": "Dataset",
                    "name": Path(artifact_path).name,
                    "identifier": artifact_path,
                })
            if parts:
                jsonld["hasPart"] = parts

        return jsonld


def create_jsonld_metadata_from_study(
    study_config: StudyConfig,
    artifact_root: Path | str | None = None,
    artifact_base_url: str | None = None,
    date_published: str | None = None,
    organization: str | None = None,
) -> JSONLDStudyMetadata:
    """
    Create JSON-LD metadata from a StudyConfig.

    Args:
        study_config: StudyConfig object
        artifact_root: Path to artifact directory (for discovering files)
        artifact_base_url: Base URL for accessing artifacts (e.g., http://artifacts.example.com/studies/)
        date_published: ISO 8601 date when Study was published (defaults to now)
        organization: Organization name for provider field

    Returns:
        JSONLDStudyMetadata object
    """
    # Extract creation date from config or use current time
    creation_date = study_config.creation_date or datetime.now().isoformat()

    # Use date_published or default to None (unpublished)
    if date_published is None and study_config.metadata.get("completed"):
        date_published = datetime.now().isoformat()

    # Extract creator from config
    creator_name = study_config.author
    creator_email = study_config.metadata.get("author_email")

    # Build description
    description = study_config.description or f"Noodle 2 Study: {study_config.name}"
    description += f" | PDK: {study_config.pdk} | Stages: {len(study_config.stages)}"

    # Collect artifact paths if artifact_root provided
    artifact_paths: list[str] = []
    if artifact_root:
        artifact_path = Path(artifact_root)
        if artifact_path.exists():
            # Find key artifact files
            artifact_patterns = [
                "**/*summary.json",  # Matches both summary.json and trial_0_summary.json
                "**/*index.json",    # Matches both index.json and artifact_index.json
                "**/*.csv",
                "**/*.png",
                "**/README.md",
                "**/study_config.json",
                "**/*.jsonld",
            ]
            # Use set to avoid duplicates
            artifact_set: set[str] = set()
            for pattern in artifact_patterns:
                for file_path in artifact_path.glob(pattern):
                    # Get relative path from artifact root
                    rel_path = file_path.relative_to(artifact_path)
                    artifact_set.add(str(rel_path))
            artifact_paths = sorted(artifact_set)

    # Build keywords from PDK, safety domain, tags
    keywords = [
        study_config.pdk,
        study_config.safety_domain.value,
        "physical-design",
        "openroad",
        "noodle2",
    ]

    return JSONLDStudyMetadata(
        study_name=study_config.name,
        description=description,
        pdk=study_config.pdk,
        safety_domain=study_config.safety_domain.value,
        creation_date=creation_date,
        date_published=date_published,
        creator_name=creator_name,
        creator_email=creator_email,
        organization=organization,
        num_stages=len(study_config.stages),
        base_case_name=study_config.base_case_name,
        artifact_base_url=artifact_base_url,
        artifact_paths=artifact_paths[:50],  # Limit to 50 artifacts
        keywords=keywords,
        tags=study_config.tags,
    )


def write_jsonld_metadata(
    metadata: JSONLDStudyMetadata,
    output_path: Path | str,
) -> None:
    """
    Write JSON-LD metadata to file.

    Args:
        metadata: JSONLDStudyMetadata object
        output_path: Path to write JSON-LD file
    """
    import json

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(metadata.to_jsonld(), f, indent=2)


def generate_study_jsonld(
    study_config: StudyConfig,
    artifact_root: Path | str,
    output_filename: str = "study_metadata.jsonld",
    artifact_base_url: str | None = None,
    organization: str | None = None,
) -> Path:
    """
    Generate and write JSON-LD metadata for a Study.

    Convenience function that creates metadata and writes it to the
    artifact directory.

    Args:
        study_config: StudyConfig object
        artifact_root: Path to Study artifact directory
        output_filename: Filename for JSON-LD output (default: study_metadata.jsonld)
        artifact_base_url: Base URL for accessing artifacts
        organization: Organization name

    Returns:
        Path to written JSON-LD file
    """
    # Create metadata
    metadata = create_jsonld_metadata_from_study(
        study_config,
        artifact_root=artifact_root,
        artifact_base_url=artifact_base_url,
        organization=organization,
    )

    # Write to file
    output_path = Path(artifact_root) / output_filename
    write_jsonld_metadata(metadata, output_path)

    return output_path


def validate_jsonld_structure(jsonld: dict[str, Any]) -> bool:
    """
    Validate that JSON-LD structure has required schema.org fields.

    Args:
        jsonld: JSON-LD dictionary

    Returns:
        True if valid, False otherwise
    """
    # Check required fields
    required_fields = ["@context", "@type", "name", "description"]
    for field in required_fields:
        if field not in jsonld:
            return False

    # Check @context is schema.org
    if jsonld["@context"] != "https://schema.org/":
        return False

    # Check @type is Dataset
    if jsonld["@type"] != "Dataset":
        return False

    return True
