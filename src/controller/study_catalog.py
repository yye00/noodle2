"""Study catalog management with tag-based organization and filtering."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.controller.types import StudyConfig


@dataclass
class StudyMetadata:
    """
    Metadata summary for a Study in the catalog.

    Lightweight representation for browsing and filtering Studies
    without loading full Study configurations.
    """

    name: str
    pdk: str
    safety_domain: str
    tags: list[str] = field(default_factory=list)
    author: str | None = None
    creation_date: str | None = None
    description: str | None = None
    snapshot_path: str = ""
    num_stages: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "pdk": self.pdk,
            "safety_domain": self.safety_domain,
            "tags": self.tags,
            "author": self.author,
            "creation_date": self.creation_date,
            "description": self.description,
            "snapshot_path": self.snapshot_path,
            "num_stages": self.num_stages,
        }

    @classmethod
    def from_study_config(cls, config: StudyConfig) -> "StudyMetadata":
        """Create StudyMetadata from full StudyConfig."""
        return cls(
            name=config.name,
            pdk=config.pdk,
            safety_domain=config.safety_domain.value,
            tags=config.tags.copy(),
            author=config.author,
            creation_date=config.creation_date,
            description=config.description,
            snapshot_path=config.snapshot_path,
            num_stages=len(config.stages),
        )


@dataclass
class StudyCatalog:
    """
    Catalog of Studies with tag-based filtering and search.

    Enables organization and discovery of Studies by tags,
    PDK, safety domain, and other metadata.
    """

    studies: list[StudyMetadata] = field(default_factory=list)

    def add_study(self, study: StudyConfig | StudyMetadata) -> None:
        """Add a Study to the catalog."""
        if isinstance(study, StudyConfig):
            metadata = StudyMetadata.from_study_config(study)
        else:
            metadata = study

        self.studies.append(metadata)

    def filter_by_tags(
        self, tags: list[str], match_all: bool = False
    ) -> list[StudyMetadata]:
        """
        Filter Studies by tags.

        Args:
            tags: List of tags to filter by
            match_all: If True, Study must have all tags (AND).
                      If False, Study must have at least one tag (OR).

        Returns:
            List of matching StudyMetadata
        """
        if not tags:
            return self.studies.copy()

        results = []
        for study in self.studies:
            study_tags = set(study.tags)
            filter_tags = set(tags)

            if match_all:
                # Study must have all requested tags
                if filter_tags.issubset(study_tags):
                    results.append(study)
            else:
                # Study must have at least one requested tag
                if filter_tags & study_tags:
                    results.append(study)

        return results

    def filter_by_pdk(self, pdk: str) -> list[StudyMetadata]:
        """Filter Studies by PDK."""
        return [study for study in self.studies if study.pdk == pdk]

    def filter_by_safety_domain(self, safety_domain: str) -> list[StudyMetadata]:
        """Filter Studies by safety domain."""
        return [
            study for study in self.studies if study.safety_domain == safety_domain
        ]

    def filter_by_author(self, author: str) -> list[StudyMetadata]:
        """Filter Studies by author."""
        return [
            study for study in self.studies if study.author and study.author == author
        ]

    def search(self, query: str) -> list[StudyMetadata]:
        """
        Search Studies by name, description, or tags.

        Args:
            query: Search string (case-insensitive)

        Returns:
            List of matching StudyMetadata
        """
        query_lower = query.lower()
        results = []

        for study in self.studies:
            # Search in name
            if query_lower in study.name.lower():
                results.append(study)
                continue

            # Search in description
            if study.description and query_lower in study.description.lower():
                results.append(study)
                continue

            # Search in tags
            if any(query_lower in tag.lower() for tag in study.tags):
                results.append(study)
                continue

        return results

    def get_all_tags(self) -> set[str]:
        """Get all unique tags across all Studies in catalog."""
        all_tags = set()
        for study in self.studies:
            all_tags.update(study.tags)
        return all_tags

    def to_dict(self) -> dict[str, Any]:
        """Convert catalog to dictionary for JSON serialization."""
        return {"studies": [study.to_dict() for study in self.studies]}

    def generate_tag_report(self) -> str:
        """Generate human-readable report of tags and their usage."""
        # Count Studies per tag
        tag_counts: dict[str, int] = {}
        for study in self.studies:
            for tag in study.tags:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Sort by count (descending), then alphabetically
        sorted_tags = sorted(
            tag_counts.items(), key=lambda x: (-x[1], x[0].lower())
        )

        lines = [
            "=== Study Tag Report ===",
            f"Total Studies: {len(self.studies)}",
            f"Unique Tags: {len(tag_counts)}",
            "",
            "Tag Usage:",
        ]

        for tag, count in sorted_tags:
            lines.append(f"  {tag}: {count} {'study' if count == 1 else 'studies'}")

        return "\n".join(lines)


def write_study_metadata(
    study: StudyConfig, artifact_dir: Path | str
) -> None:
    """
    Write Study metadata (including tags) to artifact directory.

    Args:
        study: StudyConfig to write metadata for
        artifact_dir: Directory to write metadata file to
    """
    import json

    artifact_path = Path(artifact_dir)
    artifact_path.mkdir(parents=True, exist_ok=True)

    metadata = StudyMetadata.from_study_config(study)
    metadata_file = artifact_path / "study_metadata.json"

    with open(metadata_file, "w") as f:
        json.dump(metadata.to_dict(), f, indent=2)


def load_study_metadata(artifact_dir: Path | str) -> StudyMetadata:
    """
    Load Study metadata from artifact directory.

    Args:
        artifact_dir: Directory containing study_metadata.json

    Returns:
        StudyMetadata object
    """
    import json

    metadata_file = Path(artifact_dir) / "study_metadata.json"
    with open(metadata_file, "r") as f:
        data = json.load(f)

    return StudyMetadata(
        name=data["name"],
        pdk=data["pdk"],
        safety_domain=data["safety_domain"],
        tags=data.get("tags", []),
        author=data.get("author"),
        creation_date=data.get("creation_date"),
        description=data.get("description"),
        snapshot_path=data.get("snapshot_path", ""),
        num_stages=data.get("num_stages", 0),
    )
