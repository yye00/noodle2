"""Complete provenance chain generation for trial reproducibility and audit."""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.controller.case import Case, CaseGraph
from src.trial_runner.provenance import ToolProvenance


@dataclass
class SnapshotProvenance:
    """
    Provenance information for the design snapshot.

    Captures the starting state of the design for reproducibility.
    """

    snapshot_path: str
    snapshot_hash: str  # SHA256 or similar
    pdk_name: str
    pdk_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "snapshot_path": self.snapshot_path,
            "snapshot_hash": self.snapshot_hash,
            "pdk_name": self.pdk_name,
            "pdk_version": self.pdk_version,
            "metadata": self.metadata,
        }


@dataclass
class ECOApplicationRecord:
    """
    Record of a single ECO application in the provenance chain.

    Captures the ECO transformation applied at a specific point.
    """

    eco_name: str
    eco_class: str  # topology_neutral, placement_local, etc.
    parameters: dict[str, Any]
    applied_at_stage: int
    timestamp: str  # ISO 8601 format
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "eco_name": self.eco_name,
            "eco_class": self.eco_class,
            "parameters": self.parameters,
            "applied_at_stage": self.applied_at_stage,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class CaseProvenanceRecord:
    """
    Provenance record for a single case in the lineage chain.

    Captures the complete history of case derivation.
    """

    case_id: str
    parent_case_id: str | None  # None for base case
    stage_index: int
    derived_index: int
    eco_applied: ECOApplicationRecord | None  # None for base case
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "case_id": self.case_id,
            "parent_case_id": self.parent_case_id,
            "stage_index": self.stage_index,
            "derived_index": self.derived_index,
            "eco_applied": self.eco_applied.to_dict() if self.eco_applied else None,
            "metadata": self.metadata,
        }


@dataclass
class ProvenanceChain:
    """
    Complete provenance chain for a trial result.

    Captures all information needed to reproduce, audit, and validate a trial:
    - Snapshot provenance (design starting point)
    - Tool provenance (container, tool versions)
    - Case lineage (parent-child relationships, ECO sequence)
    - Study configuration (policy, safety domain, stages)

    This provides a complete audit trail from base snapshot to final result.
    """

    # Design snapshot provenance
    snapshot: SnapshotProvenance

    # Tool execution provenance
    tool_provenance: ToolProvenance

    # Case lineage (base case → ... → current case)
    case_lineage: list[CaseProvenanceRecord]

    # Study configuration snapshot
    study_config: dict[str, Any]

    # Generation metadata
    generated_at: str  # ISO 8601 timestamp
    format_version: str = "1.0"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert provenance chain to dictionary for serialization.

        Returns a complete, machine-readable representation suitable for:
        - JSON export
        - Audit systems
        - Compliance frameworks
        - Reproducibility verification
        """
        return {
            "format_version": self.format_version,
            "generated_at": self.generated_at,
            "snapshot": self.snapshot.to_dict(),
            "tool_provenance": self.tool_provenance.to_dict(),
            "case_lineage": [case.to_dict() for case in self.case_lineage],
            "study_config": self.study_config,
            "metadata": self.metadata,
        }

    def get_eco_sequence(self) -> list[ECOApplicationRecord]:
        """
        Extract the sequence of ECOs applied to reach this case.

        Returns:
            List of ECO application records in chronological order
        """
        return [
            case.eco_applied
            for case in self.case_lineage
            if case.eco_applied is not None
        ]

    def get_lineage_depth(self) -> int:
        """
        Get the depth of the lineage chain.

        Returns:
            Number of derivation steps from base case (0 for base case)
        """
        return len(self.case_lineage) - 1


def generate_provenance_chain(
    case_id: str,
    case_graph: CaseGraph,
    snapshot: SnapshotProvenance,
    tool_provenance: ToolProvenance,
    study_config: dict[str, Any],
    timestamp: str | None = None,
) -> ProvenanceChain:
    """
    Generate complete provenance chain for a case.

    Traces the case lineage back to the base case and captures:
    - Snapshot provenance
    - Tool provenance
    - Complete case lineage with ECO sequence
    - Study configuration

    Args:
        case_id: ID of the case to generate provenance for
        case_graph: Case graph containing all cases
        snapshot: Snapshot provenance information
        tool_provenance: Tool execution provenance
        study_config: Study configuration dictionary
        timestamp: Optional timestamp (defaults to now)

    Returns:
        Complete provenance chain for the case

    Raises:
        ValueError: If case_id not found in case graph
    """
    # Get the case
    if case_id not in case_graph.cases:
        raise ValueError(f"Case {case_id} not found in case graph")

    case = case_graph.cases[case_id]

    # Get lineage from base case to current case
    lineage = case_graph.get_lineage(case_id)

    # Build case provenance records
    case_lineage: list[CaseProvenanceRecord] = []

    # Add ancestor cases (they are in order from base to parent)
    for i, ancestor_id in enumerate(lineage.ancestors):
        ancestor = case_graph.cases[ancestor_id]

        # First ancestor (base case) has no ECO
        # Subsequent ancestors have the ECO that led to them
        eco_applied = None
        if i < len(lineage.ecos_applied):
            eco_name = lineage.ecos_applied[i]
            if eco_name and hasattr(ancestor, "eco_metadata") and ancestor.eco_metadata:
                eco_meta = ancestor.eco_metadata
                eco_applied = ECOApplicationRecord(
                    eco_name=eco_meta.name,
                    eco_class=eco_meta.eco_class,
                    parameters=eco_meta.parameters,
                    applied_at_stage=ancestor.stage_index,
                    timestamp=timestamp or datetime.now().isoformat(),
                )

        case_prov = CaseProvenanceRecord(
            case_id=ancestor.case_id,
            parent_case_id=ancestor.parent_id,
            stage_index=ancestor.identifier.stage_index,
            derived_index=ancestor.identifier.derived_index,
            eco_applied=eco_applied,
        )

        case_lineage.append(case_prov)

    # Add the current case itself
    current_eco_applied = None
    if case.eco_applied and hasattr(case, "eco_metadata") and case.eco_metadata:
        eco_meta = case.eco_metadata
        current_eco_applied = ECOApplicationRecord(
            eco_name=eco_meta.name,
            eco_class=eco_meta.eco_class,
            parameters=eco_meta.parameters,
            applied_at_stage=case.identifier.stage_index,
            timestamp=timestamp or datetime.now().isoformat(),
        )

    current_case_prov = CaseProvenanceRecord(
        case_id=case.case_id,
        parent_case_id=case.parent_id,
        stage_index=case.identifier.stage_index,
        derived_index=case.identifier.derived_index,
        eco_applied=current_eco_applied,
    )

    case_lineage.append(current_case_prov)

    # Create provenance chain
    chain = ProvenanceChain(
        snapshot=snapshot,
        tool_provenance=tool_provenance,
        case_lineage=case_lineage,
        study_config=study_config,
        generated_at=timestamp or datetime.now().isoformat(),
    )

    return chain


def export_provenance_chain(
    chain: ProvenanceChain,
    output_path: str | Path,
    indent: int = 2,
) -> None:
    """
    Export provenance chain to JSON file.

    Creates a human-readable, machine-parseable JSON document
    suitable for audit, compliance, and reproducibility verification.

    Args:
        chain: Provenance chain to export
        output_path: Path to write JSON file
        indent: JSON indentation (default 2 for readability)
    """
    output_path = Path(output_path)

    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize to JSON with indentation for human readability
    data = chain.to_dict()

    with open(output_path, "w") as f:
        json.dump(data, f, indent=indent, sort_keys=False)


def compute_snapshot_hash(snapshot_path: str | Path) -> str:
    """
    Compute SHA256 hash of snapshot directory contents.

    Args:
        snapshot_path: Path to snapshot directory

    Returns:
        SHA256 hex digest of snapshot contents

    Note:
        This is a simplified implementation. Production use should handle:
        - Recursive directory hashing
        - File ordering for determinism
        - Exclusion of metadata files
    """
    snapshot_path = Path(snapshot_path)

    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot path not found: {snapshot_path}")

    # Simplified: just hash the path string
    # Real implementation should hash actual file contents
    hasher = hashlib.sha256()
    hasher.update(str(snapshot_path).encode())

    return hasher.hexdigest()


def format_provenance_summary(chain: ProvenanceChain) -> str:
    """
    Format provenance chain as human-readable summary.

    Args:
        chain: Provenance chain to format

    Returns:
        Multi-line human-readable summary
    """
    lines = [
        "=== Provenance Chain Summary ===",
        "",
        "Snapshot:",
        f"  Path: {chain.snapshot.snapshot_path}",
        f"  Hash: {chain.snapshot.snapshot_hash}",
        f"  PDK: {chain.snapshot.pdk_name}",
        "",
        "Tool Execution:",
        f"  Container: {chain.tool_provenance.container_image}:{chain.tool_provenance.container_tag}",
        f"  Tool: {chain.tool_provenance.tool_name}",
        f"  Version: {chain.tool_provenance.tool_version or '(unavailable)'}",
        "",
        f"Case Lineage (depth {chain.get_lineage_depth()}):",
    ]

    for case_prov in chain.case_lineage:
        if case_prov.eco_applied:
            lines.append(
                f"  {case_prov.case_id} ← {case_prov.eco_applied.eco_name} "
                f"({case_prov.eco_applied.eco_class})"
            )
        else:
            lines.append(f"  {case_prov.case_id} (base case)")

    eco_sequence = chain.get_eco_sequence()
    if eco_sequence:
        lines.append("")
        lines.append(f"ECO Sequence ({len(eco_sequence)} transformations):")
        for i, eco in enumerate(eco_sequence, 1):
            lines.append(
                f"  {i}. {eco.eco_name} ({eco.eco_class}) "
                f"@ stage {eco.applied_at_stage}"
            )

    lines.append("")
    lines.append(f"Study: {chain.study_config.get('study_name', 'unknown')}")
    lines.append(f"Safety Domain: {chain.study_config.get('safety_domain', 'unknown')}")
    lines.append(f"Generated: {chain.generated_at}")

    return "\n".join(lines)
