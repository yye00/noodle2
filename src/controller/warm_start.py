"""Warm-start prior loading from source studies with weighting.

This module enables loading ECO priors from completed studies with
configurable weighting, allowing new studies to benefit from historical
effectiveness data.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .eco import ECOEffectiveness, ECOPrior
from .prior_sharing import PriorRepository


@dataclass
class SourceStudyConfig:
    """Configuration for a source study to load priors from.

    Attributes:
        name: Name of the source study
        weight: Weight to apply to priors from this study (0.0 to 1.0)
        prior_repository_path: Path to the prior repository file
        metadata: Optional metadata about the source study
    """

    name: str
    weight: float
    prior_repository_path: Path
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate configuration."""
        if not 0.0 <= self.weight <= 1.0:
            raise ValueError(f"Weight must be between 0.0 and 1.0, got {self.weight}")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "weight": self.weight,
            "prior_repository_path": str(self.prior_repository_path),
            "metadata": self.metadata,
        }


@dataclass
class WarmStartConfig:
    """Configuration for warm-start prior loading.

    Attributes:
        mode: Prior loading mode ("warm_start", "cold_start", etc.)
        source_studies: List of source studies to load priors from
        merge_strategy: How to merge priors from multiple sources ("weighted_avg", "max", etc.)
    """

    mode: str
    source_studies: list[SourceStudyConfig] = field(default_factory=list)
    merge_strategy: str = "weighted_avg"

    def normalize_weights(self) -> list[float]:
        """Normalize weights to sum to 1.0.

        Returns:
            List of normalized weights
        """
        if not self.source_studies:
            return []

        total_weight = sum(s.weight for s in self.source_studies)

        if total_weight == 0.0:
            # Equal weights if all are zero
            return [1.0 / len(self.source_studies)] * len(self.source_studies)

        return [s.weight / total_weight for s in self.source_studies]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "mode": self.mode,
            "source_studies": [s.to_dict() for s in self.source_studies],
            "merge_strategy": self.merge_strategy,
        }


class WarmStartLoader:
    """Loads ECO priors from source studies with weighting."""

    def __init__(self, config: WarmStartConfig) -> None:
        """Initialize warm-start loader.

        Args:
            config: Warm-start configuration
        """
        self.config = config

    def load_priors(
        self,
        target_study_id: str,
        audit_trail_path: Path | None = None,
    ) -> dict[str, ECOEffectiveness]:
        """Load and merge priors from configured source studies.

        Args:
            target_study_id: ID of the target study
            audit_trail_path: Optional path to write audit trail

        Returns:
            Dictionary mapping ECO names to weighted effectiveness data

        Raises:
            FileNotFoundError: If any source repository doesn't exist
        """
        if not self.config.source_studies:
            return {}

        # Load priors from each source
        source_priors: dict[str, list[tuple[ECOEffectiveness, float, int]]] = {}

        for source_idx, source_config in enumerate(self.config.source_studies):
            # Load repository
            if not source_config.prior_repository_path.exists():
                raise FileNotFoundError(
                    f"Prior repository not found: {source_config.prior_repository_path}"
                )

            with open(source_config.prior_repository_path) as f:
                data = json.load(f)

            repository = PriorRepository.from_dict(data)

            # Scale each prior by weight and collect
            for eco_name, effectiveness in repository.eco_priors.items():
                scaled = self._scale_effectiveness(effectiveness, source_config.weight)

                if eco_name not in source_priors:
                    source_priors[eco_name] = []

                # Store: (effectiveness, weight, source_index)
                source_priors[eco_name].append((scaled, source_config.weight, source_idx))

        # Merge priors using configured strategy
        merged_priors = self._merge_priors(source_priors)

        # Write audit trail if requested
        if audit_trail_path:
            self._write_audit_trail(
                target_study_id=target_study_id,
                merged_priors=merged_priors,
                audit_trail_path=audit_trail_path,
            )

        return merged_priors

    def _scale_effectiveness(
        self, effectiveness: ECOEffectiveness, weight: float
    ) -> ECOEffectiveness:
        """Scale ECO effectiveness by weight.

        Counts (applications, successes, failures) are scaled.
        Averages and extremes (best/worst) remain unchanged.

        Args:
            effectiveness: Original effectiveness data
            weight: Weight to scale by

        Returns:
            Scaled effectiveness data
        """
        return ECOEffectiveness(
            eco_name=effectiveness.eco_name,
            total_applications=int(effectiveness.total_applications * weight),
            successful_applications=int(effectiveness.successful_applications * weight),
            failed_applications=int(effectiveness.failed_applications * weight),
            average_wns_improvement_ps=effectiveness.average_wns_improvement_ps,
            best_wns_improvement_ps=effectiveness.best_wns_improvement_ps,
            worst_wns_degradation_ps=effectiveness.worst_wns_degradation_ps,
            prior=effectiveness.prior,
        )

    def _merge_priors(
        self, source_priors: dict[str, list[tuple[ECOEffectiveness, float, int]]]
    ) -> dict[str, ECOEffectiveness]:
        """Merge priors from multiple sources.

        Args:
            source_priors: Map of ECO names to list of (effectiveness, weight, source_idx) tuples

        Returns:
            Dictionary of merged ECO effectiveness data
        """
        merged: dict[str, ECOEffectiveness] = {}

        for eco_name, priors_list in source_priors.items():
            if len(priors_list) == 1:
                # Only one source, use directly
                merged[eco_name] = priors_list[0][0]
            else:
                # Multiple sources, merge based on strategy
                if self.config.merge_strategy == "weighted_avg":
                    merged[eco_name] = self._merge_weighted_average(priors_list)
                elif self.config.merge_strategy == "highest_weight":
                    merged[eco_name] = self._merge_highest_weight(priors_list)
                elif self.config.merge_strategy == "newest":
                    merged[eco_name] = self._merge_newest(priors_list)
                else:
                    # Default to weighted average
                    merged[eco_name] = self._merge_weighted_average(priors_list)

        return merged

    def _merge_weighted_average(
        self, priors_list: list[tuple[ECOEffectiveness, float, int]]
    ) -> ECOEffectiveness:
        """Merge multiple ECO effectiveness records using weighted average.

        Args:
            priors_list: List of (effectiveness, weight, source_idx) tuples

        Returns:
            Merged effectiveness data
        """
        # Sum up counts from all sources (already scaled by weight)
        total_apps = sum(eff.total_applications for eff, _, _ in priors_list)
        successful_apps = sum(eff.successful_applications for eff, _, _ in priors_list)
        failed_apps = sum(eff.failed_applications for eff, _, _ in priors_list)

        # Weighted average for improvement metrics
        total_weight = sum(weight for _, weight, _ in priors_list)

        if total_weight > 0:
            avg_wns = sum(
                eff.average_wns_improvement_ps * weight
                for eff, weight, _ in priors_list
            ) / total_weight
        else:
            avg_wns = 0.0

        # Best and worst across all sources
        best_wns = max(eff.best_wns_improvement_ps for eff, _, _ in priors_list)
        worst_wns = min(eff.worst_wns_degradation_ps for eff, _, _ in priors_list)

        # Use the most conservative prior
        priors = [eff.prior for eff, _, _ in priors_list]
        if ECOPrior.SUSPICIOUS in priors or ECOPrior.BLACKLISTED in priors:
            merged_prior = ECOPrior.SUSPICIOUS
        elif ECOPrior.MIXED in priors:
            merged_prior = ECOPrior.MIXED
        elif all(p == ECOPrior.TRUSTED for p in priors):
            merged_prior = ECOPrior.TRUSTED
        else:
            merged_prior = ECOPrior.UNKNOWN

        # Use name from first source
        eco_name = priors_list[0][0].eco_name

        return ECOEffectiveness(
            eco_name=eco_name,
            total_applications=total_apps,
            successful_applications=successful_apps,
            failed_applications=failed_apps,
            average_wns_improvement_ps=avg_wns,
            best_wns_improvement_ps=best_wns,
            worst_wns_degradation_ps=worst_wns,
            prior=merged_prior,
        )

    def _merge_highest_weight(
        self, priors_list: list[tuple[ECOEffectiveness, float, int]]
    ) -> ECOEffectiveness:
        """Merge by selecting the prior from the source with highest weight.

        Args:
            priors_list: List of (effectiveness, weight, source_idx) tuples

        Returns:
            Effectiveness data from source with highest weight
        """
        # Find source with highest weight
        highest_weight_idx = max(range(len(priors_list)), key=lambda i: priors_list[i][1])
        return priors_list[highest_weight_idx][0]

    def _merge_newest(
        self, priors_list: list[tuple[ECOEffectiveness, float, int]]
    ) -> ECOEffectiveness:
        """Merge by selecting the prior from the most recent source.

        Uses timestamp from source config metadata to determine recency.

        Args:
            priors_list: List of (effectiveness, weight, source_idx) tuples

        Returns:
            Effectiveness data from most recent source
        """
        # Find the source with the newest timestamp using source_idx
        newest_timestamp = None
        newest_prior = None

        for eff, weight, source_idx in priors_list:
            source_config = self.config.source_studies[source_idx]
            timestamp = source_config.metadata.get("timestamp", "1970-01-01T00:00:00Z")

            if newest_timestamp is None or timestamp > newest_timestamp:
                newest_timestamp = timestamp
                newest_prior = eff

        # Fallback to first prior if no timestamp found
        if newest_prior is None:
            newest_prior = priors_list[0][0]

        return newest_prior

    def _write_audit_trail(
        self,
        target_study_id: str,
        merged_priors: dict[str, ECOEffectiveness],
        audit_trail_path: Path,
    ) -> None:
        """Write audit trail for warm-start loading.

        Args:
            target_study_id: ID of the target study
            merged_priors: Merged prior data
            audit_trail_path: Path to write audit trail
        """
        audit_record = {
            "import_timestamp": datetime.now(UTC).isoformat(),
            "target_study_id": target_study_id,
            "mode": self.config.mode,
            "source_studies": [s.to_dict() for s in self.config.source_studies],
            "merge_strategy": self.config.merge_strategy,
            "eco_count": len(merged_priors),
            "loaded_ecos": list(merged_priors.keys()),
        }

        audit_trail_path.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_trail_path, "w") as f:
            json.dump(audit_record, f, indent=2)
