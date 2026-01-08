"""Prior sharing across Studies with explicit configuration and audit trails.

This module enables optional sharing of ECO effectiveness priors between Studies
while maintaining full provenance tracking and audit trails.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .eco import ECOEffectiveness, ECOPrior


@dataclass
class PriorProvenance:
    """Tracks the provenance of imported ECO priors."""

    source_study_id: str
    export_timestamp: str
    source_study_snapshot_hash: str | None = None
    export_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_study_id": self.source_study_id,
            "export_timestamp": self.export_timestamp,
            "source_study_snapshot_hash": self.source_study_snapshot_hash,
            "export_metadata": self.export_metadata,
        }


@dataclass
class PriorRepository:
    """Repository of ECO priors that can be shared across Studies."""

    eco_priors: dict[str, ECOEffectiveness] = field(default_factory=dict)
    provenance: PriorProvenance | None = None
    repository_metadata: dict[str, Any] = field(default_factory=dict)

    def add_eco_prior(self, effectiveness: ECOEffectiveness) -> None:
        """Add or update an ECO prior in the repository.

        Args:
            effectiveness: ECO effectiveness data to add
        """
        self.eco_priors[effectiveness.eco_name] = effectiveness

    def get_eco_prior(self, eco_name: str) -> ECOEffectiveness | None:
        """Get prior for a specific ECO.

        Args:
            eco_name: Name of the ECO

        Returns:
            ECO effectiveness data if found, None otherwise
        """
        return self.eco_priors.get(eco_name)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_priors": {
                name: {
                    "eco_name": eff.eco_name,
                    "total_applications": eff.total_applications,
                    "successful_applications": eff.successful_applications,
                    "failed_applications": eff.failed_applications,
                    "average_wns_improvement_ps": eff.average_wns_improvement_ps,
                    "best_wns_improvement_ps": eff.best_wns_improvement_ps,
                    "worst_wns_degradation_ps": eff.worst_wns_degradation_ps,
                    "prior": eff.prior.value,
                }
                for name, eff in self.eco_priors.items()
            },
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "repository_metadata": self.repository_metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PriorRepository":
        """Create from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            PriorRepository instance
        """
        eco_priors = {}
        for name, eff_data in data.get("eco_priors", {}).items():
            eco_priors[name] = ECOEffectiveness(
                eco_name=eff_data["eco_name"],
                total_applications=eff_data["total_applications"],
                successful_applications=eff_data["successful_applications"],
                failed_applications=eff_data["failed_applications"],
                average_wns_improvement_ps=eff_data["average_wns_improvement_ps"],
                best_wns_improvement_ps=eff_data["best_wns_improvement_ps"],
                worst_wns_degradation_ps=eff_data["worst_wns_degradation_ps"],
                prior=ECOPrior(eff_data["prior"]),
            )

        provenance = None
        if data.get("provenance"):
            prov_data = data["provenance"]
            provenance = PriorProvenance(
                source_study_id=prov_data["source_study_id"],
                export_timestamp=prov_data["export_timestamp"],
                source_study_snapshot_hash=prov_data.get("source_study_snapshot_hash"),
                export_metadata=prov_data.get("export_metadata", {}),
            )

        return cls(
            eco_priors=eco_priors,
            provenance=provenance,
            repository_metadata=data.get("repository_metadata", {}),
        )


class PriorExporter:
    """Exports ECO priors from a Study to a shared repository."""

    def export_priors(
        self,
        study_id: str,
        eco_effectiveness_map: dict[str, ECOEffectiveness],
        output_path: Path,
        snapshot_hash: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PriorRepository:
        """Export ECO priors from a Study.

        Args:
            study_id: ID of the source Study
            eco_effectiveness_map: Map of ECO names to effectiveness data
            output_path: Path to write the prior repository
            snapshot_hash: Optional hash of the source Study snapshot
            metadata: Optional additional metadata

        Returns:
            PriorRepository that was exported
        """
        # Create provenance record
        provenance = PriorProvenance(
            source_study_id=study_id,
            export_timestamp=datetime.now(UTC).isoformat(),
            source_study_snapshot_hash=snapshot_hash,
            export_metadata=metadata or {},
        )

        # Create repository
        repository = PriorRepository(
            provenance=provenance,
            repository_metadata={
                "eco_count": len(eco_effectiveness_map),
                "export_version": "1.0",
            },
        )

        # Add all ECO priors
        for eco_name, effectiveness in eco_effectiveness_map.items():
            repository.add_eco_prior(effectiveness)

        # Write to file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(repository.to_dict(), f, indent=2)

        return repository


class PriorImporter:
    """Imports ECO priors from a shared repository into a Study."""

    def import_priors(
        self,
        repository_path: Path,
        target_study_id: str,
        audit_trail_path: Path | None = None,
    ) -> dict[str, ECOEffectiveness]:
        """Import ECO priors from a repository.

        Args:
            repository_path: Path to the prior repository file
            target_study_id: ID of the target Study
            audit_trail_path: Optional path to write audit trail

        Returns:
            Dictionary mapping ECO names to effectiveness data

        Raises:
            FileNotFoundError: If repository file doesn't exist
            ValueError: If repository format is invalid
        """
        if not repository_path.exists():
            raise FileNotFoundError(f"Prior repository not found: {repository_path}")

        # Load repository
        with open(repository_path) as f:
            data = json.load(f)

        repository = PriorRepository.from_dict(data)

        # Create audit trail
        if audit_trail_path:
            audit_record = {
                "import_timestamp": datetime.now(UTC).isoformat(),
                "target_study_id": target_study_id,
                "source_repository": str(repository_path),
                "provenance": repository.provenance.to_dict() if repository.provenance else None,
                "eco_count": len(repository.eco_priors),
                "imported_ecos": list(repository.eco_priors.keys()),
            }

            audit_trail_path.parent.mkdir(parents=True, exist_ok=True)
            with open(audit_trail_path, "w") as f:
                json.dump(audit_record, f, indent=2)

        return repository.eco_priors


@dataclass
class PriorSharingConfig:
    """Configuration for prior sharing in a Study."""

    enabled: bool = False
    import_repository_path: Path | None = None
    export_on_completion: bool = False
    export_repository_path: Path | None = None
    audit_trail_enabled: bool = True

    def validate(self) -> None:
        """Validate the configuration.

        Raises:
            ValueError: If configuration is invalid
        """
        if self.enabled and self.import_repository_path is None:
            raise ValueError(
                "import_repository_path must be specified when prior sharing is enabled"
            )

        if self.export_on_completion and self.export_repository_path is None:
            raise ValueError(
                "export_repository_path must be specified when export_on_completion is True"
            )
